"""Summarize prompt-context usage from turn traces and compare two runs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iter_trace_documents(trace_root: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(trace_root.rglob("turn-*.json")):
        try:
            document = json.loads(path.read_text())
        except Exception:
            continue
        if not isinstance(document, dict):
            continue
        document["_path"] = str(path)
        documents.append(document)
    return documents


def _matches_filters(document: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.user_id and document.get("user_id") not in set(args.user_id):
        return False
    request_metadata = document.get("request_metadata") or {}
    if args.channel and request_metadata.get("channel") not in set(args.channel):
        return False
    if args.purpose and request_metadata.get("purpose") not in set(args.purpose):
        return False
    started_at = _parse_datetime(document.get("started_at"))
    if args.started_after and (started_at is None or started_at < _parse_datetime(args.started_after)):
        return False
    if args.started_before and (started_at is None or started_at > _parse_datetime(args.started_before)):
        return False
    return True


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=True, indent=2, default=str))


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _effective_prompt_chars(*, full_chars: int, dynamic_chars: int, cache_status: str) -> int:
    if cache_status == "hit":
        return dynamic_chars
    return full_chars


def _cache_status(cache_payload: dict[str, Any], cacheable: bool) -> str:
    status = str(cache_payload.get("status") or "").strip().lower()
    if status:
        return status
    if cacheable:
        return "eligible_without_status"
    return "not_cacheable"


def _extract_llm_calls(document: dict[str, Any]) -> list[dict[str, Any]]:
    events = list(document.get("events") or [])
    pending_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    llm_calls: list[dict[str, Any]] = []
    for event in events:
        kind = str(event.get("kind") or "")
        name = str(event.get("name") or "")
        payload = event.get("payload") or {}
        if kind == "llm_start":
            pending_by_name[name].append(payload)
            continue
        if kind != "llm_end":
            continue
        if not pending_by_name[name]:
            continue
        start_payload = pending_by_name[name].pop(0)
        prompt = start_payload.get("prompt") or {}
        prompt_cache = payload.get("prompt_cache") or {}
        stable_prefix = str(prompt.get("stable_prefix") or "")
        dynamic_context = str(prompt.get("dynamic_context") or "")
        full_prompt = str(prompt.get("full_prompt") or "")
        cacheable = bool(prompt.get("cacheable"))
        cache_status = _cache_status(prompt_cache, cacheable)
        effective_chars = _effective_prompt_chars(
            full_chars=len(full_prompt),
            dynamic_chars=len(dynamic_context),
            cache_status=cache_status,
        )
        top_level_sizes: dict[str, int] = {}
        try:
            dynamic_payload = json.loads(dynamic_context)
        except Exception:
            dynamic_payload = None
        if isinstance(dynamic_payload, dict):
            top_level_sizes = {
                str(key): _json_size(value)
                for key, value in dynamic_payload.items()
            }
        llm_calls.append(
            {
                "method_name": name,
                "node_type": str(prompt.get("node_type") or name),
                "stable_chars": len(stable_prefix),
                "dynamic_chars": len(dynamic_context),
                "full_chars": len(full_prompt),
                "effective_chars": effective_chars,
                "saved_chars": max(0, len(full_prompt) - effective_chars),
                "cacheable": cacheable,
                "cache_status": cache_status,
                "top_level_sizes": top_level_sizes,
                "duration_ms": payload.get("duration_ms"),
            }
        )
    return llm_calls


def _round(value: float) -> float:
    return round(value, 2)


def _build_summary(documents: list[dict[str, Any]]) -> dict[str, Any]:
    session_ids = {str(document.get("session_id") or "") for document in documents if document.get("session_id")}
    trace_paths = [str(document.get("_path")) for document in documents]
    llm_calls: list[dict[str, Any]] = []
    for document in documents:
        llm_calls.extend(_extract_llm_calls(document))

    calls_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cache_status_counts: Counter[str] = Counter()
    for call in llm_calls:
        calls_by_node[call["node_type"]].append(call)
        cache_status_counts[call["cache_status"]] += 1

    summary_by_node: dict[str, Any] = {}
    for node_type, node_calls in sorted(calls_by_node.items()):
        stable_values = [int(call["stable_chars"]) for call in node_calls]
        dynamic_values = [int(call["dynamic_chars"]) for call in node_calls]
        full_values = [int(call["full_chars"]) for call in node_calls]
        effective_values = [int(call["effective_chars"]) for call in node_calls]
        saved_values = [int(call["saved_chars"]) for call in node_calls]
        node_cache_statuses = Counter(str(call["cache_status"]) for call in node_calls)
        top_level_sizes: Counter[str] = Counter()
        top_level_counts: Counter[str] = Counter()
        for call in node_calls:
            for key, size in dict(call["top_level_sizes"]).items():
                top_level_sizes[key] += int(size)
                top_level_counts[key] += 1
        top_keys = [
            {
                "key": key,
                "total_chars": int(total),
                "avg_chars": _round(total / max(1, top_level_counts[key])),
                "calls_present": int(top_level_counts[key]),
            }
            for key, total in top_level_sizes.most_common(8)
        ]
        summary_by_node[node_type] = {
            "calls": len(node_calls),
            "stable_chars_total": sum(stable_values),
            "dynamic_chars_total": sum(dynamic_values),
            "full_chars_total": sum(full_values),
            "effective_chars_total": sum(effective_values),
            "saved_chars_total": sum(saved_values),
            "avg_dynamic_chars": _round(sum(dynamic_values) / len(dynamic_values)),
            "avg_full_chars": _round(sum(full_values) / len(full_values)),
            "avg_effective_chars": _round(sum(effective_values) / len(effective_values)),
            "p95_dynamic_chars": _percentile(dynamic_values, 0.95),
            "p95_full_chars": _percentile(full_values, 0.95),
            "p95_effective_chars": _percentile(effective_values, 0.95),
            "cache_status_counts": dict(sorted(node_cache_statuses.items())),
            "top_level_keys": top_keys,
        }

    effective_values = [int(call["effective_chars"]) for call in llm_calls]
    full_values = [int(call["full_chars"]) for call in llm_calls]
    dynamic_values = [int(call["dynamic_chars"]) for call in llm_calls]
    saved_values = [int(call["saved_chars"]) for call in llm_calls]
    total_full = sum(full_values)
    total_effective = sum(effective_values)

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "documents": len(documents),
        "sessions": len(session_ids),
        "llm_calls": len(llm_calls),
        "trace_paths": trace_paths,
        "filters_summary": {
            "user_ids": sorted({str(document.get("user_id") or "") for document in documents if document.get("user_id")}),
            "channels": sorted(
                {
                    str((document.get("request_metadata") or {}).get("channel") or "")
                    for document in documents
                    if (document.get("request_metadata") or {}).get("channel")
                }
            ),
            "purposes": sorted(
                {
                    str((document.get("request_metadata") or {}).get("purpose") or "")
                    for document in documents
                    if (document.get("request_metadata") or {}).get("purpose")
                }
            ),
        },
        "totals": {
            "stable_chars_total": sum(int(call["stable_chars"]) for call in llm_calls),
            "dynamic_chars_total": sum(dynamic_values),
            "full_chars_total": total_full,
            "effective_chars_total": total_effective,
            "saved_chars_total": sum(saved_values),
            "saved_percent": _round((sum(saved_values) / total_full) * 100) if total_full else 0.0,
            "avg_dynamic_chars": _round(sum(dynamic_values) / len(dynamic_values)) if dynamic_values else 0.0,
            "avg_full_chars": _round(total_full / len(full_values)) if full_values else 0.0,
            "avg_effective_chars": _round(total_effective / len(effective_values)) if effective_values else 0.0,
            "p95_dynamic_chars": _percentile(dynamic_values, 0.95),
            "p95_full_chars": _percentile(full_values, 0.95),
            "p95_effective_chars": _percentile(effective_values, 0.95),
            "cache_status_counts": dict(sorted(cache_status_counts.items())),
        },
        "by_node": summary_by_node,
    }


def _safe_get(payload: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _compare_node(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    metrics = (
        "calls",
        "stable_chars_total",
        "dynamic_chars_total",
        "full_chars_total",
        "effective_chars_total",
        "saved_chars_total",
        "avg_dynamic_chars",
        "avg_full_chars",
        "avg_effective_chars",
        "p95_dynamic_chars",
        "p95_full_chars",
        "p95_effective_chars",
    )
    delta_metrics = {}
    for metric in metrics:
        before_value = _safe_get(before, metric)
        after_value = _safe_get(after, metric)
        delta_metrics[metric] = {
            "before": before_value,
            "after": after_value,
            "delta": _round(float(after_value) - float(before_value)),
            "delta_percent": _round(((float(after_value) - float(before_value)) / float(before_value)) * 100)
            if before_value not in (0, 0.0)
            else None,
        }
    before_keys = {
        str(item.get("key")): item
        for item in list(before.get("top_level_keys") or [])
        if item.get("key")
    }
    after_keys = {
        str(item.get("key")): item
        for item in list(after.get("top_level_keys") or [])
        if item.get("key")
    }
    key_names = sorted(set(before_keys) | set(after_keys))
    top_level_keys = []
    for key in key_names:
        before_total = int((before_keys.get(key) or {}).get("total_chars") or 0)
        after_total = int((after_keys.get(key) or {}).get("total_chars") or 0)
        top_level_keys.append(
            {
                "key": key,
                "before_total_chars": before_total,
                "after_total_chars": after_total,
                "delta_total_chars": after_total - before_total,
            }
        )
    top_level_keys.sort(key=lambda item: abs(int(item["delta_total_chars"])), reverse=True)
    return {
        "metrics": delta_metrics,
        "cache_status_counts": {
            "before": before.get("cache_status_counts") or {},
            "after": after.get("cache_status_counts") or {},
        },
        "top_level_keys": top_level_keys[:8],
    }


def _compare_summaries(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_nodes = before.get("by_node") or {}
    after_nodes = after.get("by_node") or {}
    all_nodes = sorted(set(before_nodes) | set(after_nodes))
    compared_nodes = {
        node_type: _compare_node(
            dict(before_nodes.get(node_type) or {}),
            dict(after_nodes.get(node_type) or {}),
        )
        for node_type in all_nodes
    }
    totals = _compare_node(
        dict(before.get("totals") or {}),
        dict(after.get("totals") or {}),
    )
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "before_filters_summary": before.get("filters_summary") or {},
        "after_filters_summary": after.get("filters_summary") or {},
        "documents": {
            "before": before.get("documents"),
            "after": after.get("documents"),
        },
        "sessions": {
            "before": before.get("sessions"),
            "after": after.get("sessions"),
        },
        "llm_calls": {
            "before": before.get("llm_calls"),
            "after": after.get("llm_calls"),
        },
        "totals": totals,
        "by_node": compared_nodes,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _print_summary(summary: dict[str, Any]) -> None:
    totals = summary.get("totals") or {}
    print(
        json.dumps(
            {
                "documents": summary.get("documents"),
                "sessions": summary.get("sessions"),
                "llm_calls": summary.get("llm_calls"),
                "saved_percent": totals.get("saved_percent"),
                "avg_effective_chars": totals.get("avg_effective_chars"),
                "top_nodes_by_effective_chars": sorted(
                    (
                        {
                            "node_type": node_type,
                            "effective_chars_total": payload.get("effective_chars_total"),
                            "avg_effective_chars": payload.get("avg_effective_chars"),
                        }
                        for node_type, payload in dict(summary.get("by_node") or {}).items()
                    ),
                    key=lambda item: int(item["effective_chars_total"] or 0),
                    reverse=True,
                )[:5],
            },
            ensure_ascii=True,
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    summarize = subparsers.add_parser("summarize", help="Summarize turn traces")
    summarize.add_argument("--trace-root", default="log/turn-traces")
    summarize.add_argument("--user-id", action="append")
    summarize.add_argument("--channel", action="append")
    summarize.add_argument("--purpose", action="append")
    summarize.add_argument("--started-after")
    summarize.add_argument("--started-before")
    summarize.add_argument("--output")

    compare = subparsers.add_parser("compare", help="Compare two summary JSON files")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    compare.add_argument("--output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "summarize":
        documents = [
            document
            for document in _iter_trace_documents(Path(args.trace_root))
            if _matches_filters(document, args)
        ]
        summary = _build_summary(documents)
        if args.output:
            _write_json(Path(args.output), summary)
        _print_summary(summary)
        return 0

    before = json.loads(Path(args.before).read_text())
    after = json.loads(Path(args.after).read_text())
    comparison = _compare_summaries(before, after)
    if args.output:
        _write_json(Path(args.output), comparison)
    _print_summary(
        {
            "documents": comparison.get("documents"),
            "sessions": comparison.get("sessions"),
            "llm_calls": comparison.get("llm_calls"),
            "totals": {
                "saved_percent": _safe_get(comparison, "totals", "metrics", "saved_chars_total", "delta_percent", default=None),
                "avg_effective_chars": _safe_get(
                    comparison,
                    "totals",
                    "metrics",
                    "avg_effective_chars",
                    "delta",
                    default=None,
                ),
            },
            "by_node": {
                node_type: {
                    "effective_chars_total": _safe_get(
                        payload,
                        "metrics",
                        "effective_chars_total",
                        "delta",
                        default=0,
                    ),
                    "avg_effective_chars": _safe_get(
                        payload,
                        "metrics",
                        "avg_effective_chars",
                        "delta",
                        default=0,
                    ),
                }
                for node_type, payload in dict(comparison.get("by_node") or {}).items()
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
