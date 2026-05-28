"""Deterministic retail signal generation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .db import Database
from .llm import DEFAULT_MODEL, PROMPT_VERSION, fallback_narrative, synthesize_with_gemini


ENGINE_VERSION = "retail_signal_engine_v1"


@dataclass(frozen=True)
class SignalRunConfig:
    business_date: str | None = None
    campaign_id: int | None = None
    client_id: int | None = None
    category: str | None = None
    max_signals: int = 12
    brand_over_threshold: float = 105.0
    brand_under_threshold: float = 95.0
    sku_gap_threshold_pct: float = 10.0
    driver_concentration_threshold_pct: float = 60.0
    promo_break_discount_threshold_pct: float = 15.0
    promo_break_market_gap_threshold_pct: float = 20.0
    promo_break_min_visible_locations: int = 3
    promo_break_min_promo_share_pct: float = 50.0
    dry_run: bool = False
    skip_llm: bool = False


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def stable_key(*parts: Any) -> str:
    payload = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def signal_identity(context: dict[str, Any], evidence: dict[str, Any]) -> str | None:
    signal_type = str(context.get("event_type") or "")
    if signal_type in {"brand_over_market", "brand_under_market"}:
        return None
    if signal_type == "driver_sku_detected":
        return evidence.get("group_identity") or evidence.get("group_key")
    return evidence.get("product_key") or evidence.get("gtin") or evidence.get("product") or evidence.get("group_identity")


def event_fingerprint_key(context: dict[str, Any], evidence: dict[str, Any]) -> str:
    return stable_key(
        "market_event_fingerprint",
        context.get("event_type"),
        context.get("campaign_id"),
        context.get("category"),
        context.get("brand"),
        context.get("chain"),
        signal_identity(context, evidence),
    )


def build_navigation(context: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "campaign_id": context.get("campaign_id"),
        "date_key": context.get("date_key"),
        "brand": context.get("brand"),
        "chain": context.get("chain"),
    }
    products: list[dict[str, Any]] = []
    if evidence.get("product") or evidence.get("product_key") or evidence.get("gtin"):
        products.append(
            {
                "product_key": evidence.get("product_key"),
                "gtin": evidence.get("gtin"),
                "product": evidence.get("product"),
            }
        )
    for driver in evidence.get("drivers") or []:
        if not isinstance(driver, dict):
            continue
        products.append(
            {
                "product_key": driver.get("product_key"),
                "gtin": driver.get("gtin"),
                "product": driver.get("product"),
            }
        )
    if products:
        filters["products"] = products

    signal_type = str(context.get("event_type") or "")
    if signal_type in {"sku_price_gap", "driver_sku_detected", "promo_price_break"}:
        target_view = "sku_detail"
        preferred_dataset = "mw_bi_sku_price_drivers"
        evidence_dataset = "mw_bi_sku_store_price_evidence"
    else:
        target_view = "brand_chain_benchmark"
        preferred_dataset = "mw_bi_brand_chain_price_index"
        evidence_dataset = "mw_bi_sku_price_drivers"

    return {
        "dashboard": "pricing_competitive_basket",
        "target_view": target_view,
        "preferred_dataset": preferred_dataset,
        "evidence_dataset": evidence_dataset,
        "filters": {key: value for key, value in filters.items() if value not in (None, "", [])},
    }


def client_signal_fingerprint_key(context: dict[str, Any], evidence: dict[str, Any]) -> str:
    return stable_key(
        "client_signal_fingerprint",
        context.get("event_type"),
        context.get("client_id"),
        context.get("campaign_id"),
        context.get("category"),
        context.get("brand"),
        context.get("chain"),
        signal_identity(context, evidence),
    )


def as_decimal(value: str | int | float | Decimal | None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def as_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def as_float(value: str | int | float | Decimal | None) -> float | None:
    number = as_decimal(value)
    return float(number) if number is not None else None


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def severity_from_gap(gap_abs: float) -> str:
    if gap_abs >= 15:
        return "high"
    if gap_abs >= 8:
        return "medium"
    return "low"


def scope_where(config: SignalRunConfig, *, alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    clauses: list[str] = []
    if config.campaign_id is not None:
        clauses.append(f"{prefix}campaign_id = {int(config.campaign_id)}")
    if config.client_id is not None:
        clauses.append(f"{prefix}client_id = {int(config.client_id)}")
    return "\n  and ".join(clauses)


def resolve_date(db: Database, config: SignalRunConfig) -> tuple[int, str]:
    if config.business_date:
        parsed = datetime.strptime(config.business_date, "%Y-%m-%d").date()
        return int(parsed.strftime("%Y%m%d")), parsed.isoformat()

    extra = scope_where(config)
    where = f"where {extra}" if extra else ""
    output = db.run_psql(
        f"""
select date_key, business_date::text
from public.mw_signal_brand_chain_daily
{where}
order by date_key desc
limit 1;
""",
        tuples_only=True,
    )
    if not output.strip():
        raise RuntimeError("No hay fechas disponibles para el scope solicitado.")
    date_key_text, business_date = output.splitlines()[-1].split("\t", 1)
    return int(date_key_text), business_date


def fetch_brand_rows(db: Database, config: SignalRunConfig, date_key: int) -> list[dict[str, str]]:
    clauses = [f"date_key = {int(date_key)}"]
    extra = scope_where(config)
    if extra:
        clauses.append(extra)
    return db.fetch_csv(
        """
select
  date_key as fecha_key,
  business_date::text as fecha,
  client_id::text as client_id,
  campaign_id::text as campaign_id,
  client_name as cliente,
  campaign_name as campana,
  brand_name as marca,
  chain_label as cadena,
  tracked_product_count::text as productos_monitoreados,
  avg_price_position_index::text as indice_precio,
  (avg_price_position_index - 100)::text as diferencia_vs_mercado_pct,
  brand_chain_price_rank::text as ranking_precio,
  (avg_visibility_rate * 100)::text as visibilidad_pct,
  (avg_availability_rate * 100)::text as disponibilidad_pct,
  (avg_promo_share * 100)::text as promocion_pct,
  lowest_price_product_count::text as productos_con_mejor_precio,
  competitive_product_count::text as productos_competitivos,
  over_market_product_count::text as productos_sobre_mercado,
  price_reading as lectura_precio,
  visibility_reading as lectura_visibilidad
from public.mw_signal_brand_chain_daily
where """
        + "\n  and ".join(clauses)
    )


def fetch_sku_rows(db: Database, config: SignalRunConfig, date_key: int) -> list[dict[str, str]]:
    clauses = [f"date_key = {int(date_key)}"]
    extra = scope_where(config)
    if extra:
        clauses.append(extra)
    return db.fetch_csv(
        """
select
  date_key as fecha_key,
  business_date::text as fecha,
  client_id::text as client_id,
  campaign_id::text as campaign_id,
  client_name as cliente,
  campaign_name as campana,
  brand_name as marca,
  product_name as producto,
  gtin_norm as gtin,
  product_key::text as product_key,
  chain_label as cadena,
  content_quantity::text as contenido,
  content_unit as unidad,
  avg_price_amount::text as precio_promedio,
  market_best_price_amount::text as mejor_precio_mercado,
  gap_vs_market_best_amount::text as brecha_colones,
  (gap_vs_market_best_pct * 100)::text as brecha_pct,
  price_position_index::text as indice_precio,
  chain_price_rank::text as ranking_precio,
  monitored_locations_count::text as tiendas_monitoreadas,
  visible_locations_count::text as tiendas_visibles,
  competing_chain_count::text as cadenas_compitiendo,
  promo_detected::text as promocion_detectada,
  (promo_share * 100)::text as promocion_pct_sku,
  (max_discount_pct * 100)::text as descuento_max_pct,
  market_avg_price_amount::text as precio_promedio_mercado,
  (visibility_rate * 100)::text as visibilidad_pct,
  price_reading as lectura_precio,
  suggested_action as accion_sugerida,
  product_url as producto_url,
  best_price_chain_label as cadena_mejor_precio,
  best_price_product_url as mejor_precio_url
from public.mw_signal_sku_chain_daily
where """
        + "\n  and ".join(clauses)
    )


def base_context(row: dict[str, str], config: SignalRunConfig, *, signal_type: str) -> dict[str, Any]:
    return {
        "event_type": signal_type,
        "business_date": row["fecha"],
        "date_key": as_int(row["fecha_key"]),
        "client_id": as_int(row.get("client_id")),
        "campaign_id": as_int(row.get("campaign_id")),
        "campaign_name": row.get("campana") or None,
        "category": config.category,
        "chain": row.get("cadena") or None,
        "brand": row.get("marca") or None,
    }


def build_event_and_signal(
    *,
    context: dict[str, Any],
    severity: str,
    impact_score: float,
    confidence_score: float,
    effect: str,
    metrics: dict[str, Any],
    evidence: dict[str, Any],
    source_view: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    fingerprint = event_fingerprint_key(context, evidence)
    event_key = stable_key(
        "market_event",
        context["event_type"],
        context["date_key"],
        context.get("campaign_id"),
        context.get("brand"),
        context.get("chain"),
        evidence.get("product"),
        evidence.get("group_key"),
    )
    signal_key = stable_key(
        "client_signal",
        event_key,
        context.get("brand"),
        effect,
    )
    signal_fingerprint = client_signal_fingerprint_key(context, evidence)
    affected = [context["brand"]] if context.get("brand") else []
    event = {
        "event_key": event_key,
        "event_fingerprint_key": fingerprint,
        "event_type": context["event_type"],
        "business_date": context["business_date"],
        "date_key": context["date_key"],
        "client_id": context.get("client_id"),
        "campaign_id": context.get("campaign_id"),
        "campaign_name": context.get("campaign_name"),
        "category": context.get("category"),
        "chain": context.get("chain"),
        "affected_brands": affected,
        "beneficiary_brands": affected if effect == "positive" else [],
        "disadvantaged_brands": affected if effect == "negative" else [],
        "neutral_entities": [],
        "severity": severity,
        "impact_score": round(impact_score, 2),
        "confidence_score": round(confidence_score, 2),
        "metrics": metrics,
        "evidence": evidence,
        "source_view": source_view,
    }
    signal = {
        "signal_key": signal_key,
        "fingerprint_key": signal_fingerprint,
        "event_key": event_key,
        "signal_type": context["event_type"],
        "business_date": context["business_date"],
        "date_key": context["date_key"],
        "perspective_client_id": context.get("client_id"),
        "campaign_id": context.get("campaign_id"),
        "campaign_name": context.get("campaign_name"),
        "category": context.get("category"),
        "perspective_brand": context.get("brand"),
        "counterparty_brand": evidence.get("counterparty_brand"),
        "chain": context.get("chain"),
        "effect": effect,
        "audience": "brand_manager",
        "severity": severity,
        "impact_score": round(impact_score, 2),
        "confidence_score": round(confidence_score, 2),
        "metrics": metrics,
        "evidence": evidence,
        "navigation": build_navigation(context, evidence),
    }
    return event, signal


def generate_brand_position(brand_rows: list[dict[str, str]], config: SignalRunConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for row in brand_rows:
        index = as_float(row.get("indice_precio"))
        gap = as_float(row.get("diferencia_vs_mercado_pct"))
        if index is None or gap is None:
            continue
        if index > config.brand_over_threshold:
            signal_type = "brand_over_market"
            effect = "negative"
        elif index < config.brand_under_threshold:
            signal_type = "brand_under_market"
            effect = "positive"
        else:
            continue

        visibility = as_float(row.get("visibilidad_pct")) or 0.0
        availability = as_float(row.get("disponibilidad_pct")) or 0.0
        product_count = as_int(row.get("productos_monitoreados")) or 0
        impact = clamp(abs(gap) * 3.0 + min(product_count, 20))
        confidence = clamp((visibility * 0.7) + (availability * 0.3))
        metrics = {
            "price_index": index,
            "gap_pct": gap,
            "market_reference": 100,
            "tracked_products": product_count,
            "visibility_pct": visibility,
            "availability_pct": availability,
            "promo_pct": as_float(row.get("promocion_pct")),
            "price_rank": as_int(row.get("ranking_precio")),
        }
        evidence = {
            "brand": row.get("marca"),
            "chain": row.get("cadena"),
            "campaign": row.get("campana"),
            "reading": row.get("lectura_precio"),
            "visibility_reading": row.get("lectura_visibilidad"),
        }
        event, signal = build_event_and_signal(
            context=base_context(row, config, signal_type=signal_type),
            severity=severity_from_gap(abs(gap)),
            impact_score=impact,
            confidence_score=confidence,
            effect=effect,
            metrics=metrics,
            evidence=evidence,
            source_view="mw_signal_brand_chain_daily",
        )
        events.append(event)
        signals.append(signal)
    return events, signals


def generate_sku_price_gaps(sku_rows: list[dict[str, str]], config: SignalRunConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for row in sku_rows:
        gap_pct = as_float(row.get("brecha_pct"))
        if gap_pct is None or gap_pct < config.sku_gap_threshold_pct:
            continue
        stores_visible = as_int(row.get("tiendas_visibles")) or 0
        stores_monitored = as_int(row.get("tiendas_monitoreadas")) or 0
        visibility = as_float(row.get("visibilidad_pct")) or 0.0
        impact = clamp(gap_pct * 3.5 + min(stores_visible, 15) * 2)
        confidence = clamp(visibility)
        metrics = {
            "avg_price": as_float(row.get("precio_promedio")),
            "market_best_price": as_float(row.get("mejor_precio_mercado")),
            "gap_amount": as_float(row.get("brecha_colones")),
            "gap_pct": gap_pct,
            "price_index": as_float(row.get("indice_precio")),
            "price_rank": as_int(row.get("ranking_precio")),
            "visible_locations": stores_visible,
            "monitored_locations": stores_monitored,
            "visibility_pct": visibility,
        }
        evidence = {
            "product": row.get("producto"),
            "product_key": row.get("product_key"),
            "gtin": row.get("gtin"),
            "brand": row.get("marca"),
            "chain": row.get("cadena"),
            "best_price_chain": row.get("cadena_mejor_precio"),
            "counterparty_brand": None,
            "product_url": row.get("producto_url") or None,
            "best_price_url": row.get("mejor_precio_url") or None,
            "suggested_action": row.get("accion_sugerida"),
            "reading": row.get("lectura_precio"),
        }
        event, signal = build_event_and_signal(
            context=base_context(row, config, signal_type="sku_price_gap"),
            severity=severity_from_gap(gap_pct),
            impact_score=impact,
            confidence_score=confidence,
            effect="negative",
            metrics=metrics,
            evidence=evidence,
            source_view="mw_signal_sku_chain_daily",
        )
        events.append(event)
        signals.append(signal)
    return events, signals


def generate_driver_sku_signals(sku_rows: list[dict[str, str]], config: SignalRunConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, str]]] = {}
    for row in sku_rows:
        gap_pct = as_float(row.get("brecha_pct")) or 0.0
        gap_amount = as_float(row.get("brecha_colones")) or 0.0
        if gap_pct <= 0 or gap_amount <= 0:
            continue
        key = (
            row.get("fecha_key"),
            row.get("client_id"),
            row.get("campaign_id"),
            row.get("marca"),
            row.get("cadena"),
        )
        groups.setdefault(key, []).append(row)

    events: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for key, rows in groups.items():
        if len(rows) < 2:
            continue
        ranked = sorted(rows, key=lambda item: as_float(item.get("brecha_colones")) or 0.0, reverse=True)
        total_gap = sum(as_float(row.get("brecha_colones")) or 0.0 for row in ranked)
        if total_gap <= 0:
            continue
        top_drivers = ranked[:3]
        driver_gap = sum(as_float(row.get("brecha_colones")) or 0.0 for row in top_drivers)
        concentration = (driver_gap / total_gap) * 100
        if concentration < config.driver_concentration_threshold_pct:
            continue

        sample = top_drivers[0]
        avg_gap_pct = sum(as_float(row.get("brecha_pct")) or 0.0 for row in top_drivers) / len(top_drivers)
        visibility_values = [as_float(row.get("visibilidad_pct")) or 0.0 for row in top_drivers]
        confidence = clamp(sum(visibility_values) / len(visibility_values))
        impact = clamp(avg_gap_pct * 2.5 + concentration * 0.6)
        drivers = [
            {
                "product": row.get("producto"),
                "product_key": row.get("product_key"),
                "gtin": row.get("gtin"),
                "gap_pct": as_float(row.get("brecha_pct")),
                "gap_amount": as_float(row.get("brecha_colones")),
                "avg_price": as_float(row.get("precio_promedio")),
                "market_best_price": as_float(row.get("mejor_precio_mercado")),
                "best_price_chain": row.get("cadena_mejor_precio"),
                "product_url": row.get("producto_url") or None,
                "best_price_url": row.get("mejor_precio_url") or None,
            }
            for row in top_drivers
        ]
        metrics = {
            "driver_count": len(top_drivers),
            "candidate_sku_count": len(ranked),
            "contribution_pct": round(concentration, 2),
            "total_gap_amount": round(total_gap, 2),
            "driver_gap_amount": round(driver_gap, 2),
            "avg_driver_gap_pct": round(avg_gap_pct, 2),
        }
        evidence = {
            "group_key": "|".join("" if part is None else str(part) for part in key),
            "group_identity": "|".join(
                "" if part is None else str(part)
                for part in (sample.get("client_id"), sample.get("campaign_id"), sample.get("marca"), sample.get("cadena"))
            ),
            "brand": sample.get("marca"),
            "chain": sample.get("cadena"),
            "drivers": drivers,
        }
        event, signal = build_event_and_signal(
            context=base_context(sample, config, signal_type="driver_sku_detected"),
            severity=severity_from_gap(avg_gap_pct),
            impact_score=impact,
            confidence_score=confidence,
            effect="negative",
            metrics=metrics,
            evidence=evidence,
            source_view="mw_signal_sku_chain_daily",
        )
        events.append(event)
        signals.append(signal)
    return events, signals


def generate_promo_price_breaks(sku_rows: list[dict[str, str]], config: SignalRunConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for row in sku_rows:
        promo_detected = str(row.get("promocion_detectada") or "").lower() in {"t", "true", "1", "yes"}
        if not promo_detected:
            continue

        avg_price = as_float(row.get("precio_promedio"))
        market_avg_price = as_float(row.get("precio_promedio_mercado"))
        market_best_price = as_float(row.get("mejor_precio_mercado"))
        discount_pct = as_float(row.get("descuento_max_pct")) or 0.0
        promo_share = as_float(row.get("promocion_pct_sku")) or 0.0
        visible_locations = as_int(row.get("tiendas_visibles")) or 0
        competing_chains = as_int(row.get("cadenas_compitiendo")) or 0
        if avg_price is None or market_avg_price is None or market_avg_price <= 0:
            continue
        market_gap_pct = ((market_avg_price - avg_price) / market_avg_price) * 100
        if market_gap_pct < config.promo_break_market_gap_threshold_pct:
            continue
        if discount_pct < config.promo_break_discount_threshold_pct:
            continue
        if promo_share < config.promo_break_min_promo_share_pct:
            continue
        if visible_locations < config.promo_break_min_visible_locations:
            continue
        if competing_chains < 2:
            continue

        impact = clamp(market_gap_pct * 2.0 + discount_pct * 1.5 + min(visible_locations, 20))
        confidence = clamp((promo_share * 0.7) + min(visible_locations, 10) * 3)
        metrics = {
            "avg_price": avg_price,
            "market_avg_price": market_avg_price,
            "market_best_price": market_best_price,
            "gap_vs_market_avg_pct": round(market_gap_pct, 2),
            "discount_pct": discount_pct,
            "promo_share_pct": promo_share,
            "visible_locations": visible_locations,
            "competing_chains": competing_chains,
            "price_index": as_float(row.get("indice_precio")),
        }
        evidence = {
            "product": row.get("producto"),
            "product_key": row.get("product_key"),
            "gtin": row.get("gtin"),
            "brand": row.get("marca"),
            "chain": row.get("cadena"),
            "product_url": row.get("producto_url") or None,
            "best_price_url": row.get("mejor_precio_url") or row.get("producto_url") or None,
            "reading": row.get("lectura_precio"),
            "suggested_action": "validate_promo_price_break",
            "promo_detected": True,
        }
        event, signal = build_event_and_signal(
            context=base_context(row, config, signal_type="promo_price_break"),
            severity=severity_from_gap(market_gap_pct),
            impact_score=impact,
            confidence_score=confidence,
            effect="positive",
            metrics=metrics,
            evidence=evidence,
            source_view="mw_signal_sku_chain_daily",
        )
        events.append(event)
        signals.append(signal)
    return events, signals


def enrich_signal_narratives(db: Database, signals: list[dict[str, Any]], *, skip_llm: bool) -> tuple[list[dict[str, Any]], bool]:
    env = db.env
    model = env.get("LLM_DEFAULT_MODEL") or DEFAULT_MODEL
    api_key = env.get("GOOGLE_API_KEY")
    llm_used = bool(api_key and not skip_llm)

    enriched: list[dict[str, Any]] = []
    for signal in signals:
        llm_payload = {
            "signal_type": signal["signal_type"],
            "lifecycle_status": signal.get("lifecycle_status"),
            "perspective_brand": signal.get("perspective_brand"),
            "chain": signal.get("chain"),
            "effect": signal.get("effect"),
            "severity": signal.get("severity"),
            "impact_score": signal.get("impact_score"),
            "confidence_score": signal.get("confidence_score"),
            "repeat_count": signal.get("repeat_count"),
            "delta_metrics": signal.get("delta_metrics"),
            "metrics": signal.get("metrics"),
            "evidence": signal.get("evidence"),
        }
        narrative = (
            fallback_narrative(llm_payload)
            if skip_llm
            else synthesize_with_gemini(api_key=api_key, model=model, signal=llm_payload)
        )
        enriched.append(
            {
                **signal,
                **narrative,
                "narrative": narrative,
                "llm_provider": "google" if llm_used else None,
                "llm_model": model if llm_used else None,
                "llm_prompt_version": PROMPT_VERSION if llm_used else None,
            }
        )
    return enriched, llm_used


def dedupe_by_key(rows: list[dict[str, Any]], key_name: str) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row[key_name])
        existing = result.get(key)
        if existing is None or row.get("impact_score", 0) > existing.get("impact_score", 0):
            result[key] = row
    return list(result.values())


def select_diverse_signals(signals: list[dict[str, Any]], max_signals: int) -> list[dict[str, Any]]:
    if max_signals <= 0:
        return []

    ranked = sorted(
        signals,
        key=lambda signal: (
            float(signal.get("impact_score") or 0),
            float(signal.get("confidence_score") or 0),
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    type_counts: dict[str, int] = {}
    brand_chain_counts: dict[tuple[str | None, str | None], int] = {}
    type_limits = {
        "sku_price_gap": 4,
        "driver_sku_detected": 3,
        "promo_price_break": 3,
        "brand_over_market": 3,
        "brand_under_market": 3,
    }

    def try_add(signal: dict[str, Any], *, enforce_limits: bool) -> None:
        if len(selected) >= max_signals or signal["signal_key"] in selected_keys:
            return
        signal_type = str(signal.get("signal_type"))
        brand_chain = (signal.get("perspective_brand"), signal.get("chain"))
        if enforce_limits:
            if type_counts.get(signal_type, 0) >= type_limits.get(signal_type, 2):
                return
            if brand_chain_counts.get(brand_chain, 0) >= 2:
                return
        selected.append(signal)
        selected_keys.add(signal["signal_key"])
        type_counts[signal_type] = type_counts.get(signal_type, 0) + 1
        brand_chain_counts[brand_chain] = brand_chain_counts.get(brand_chain, 0) + 1

    # First pass: preserve story diversity.
    for signal in ranked:
        try_add(signal, enforce_limits=True)

    # Second pass: fill remaining slots by pure score.
    for signal in ranked:
        try_add(signal, enforce_limits=False)

    return selected


def load_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def signal_strength(signal: dict[str, Any]) -> tuple[float, str, float]:
    metrics = signal.get("metrics") or {}
    if metrics.get("gap_pct") is not None:
        return abs(float(metrics["gap_pct"])), "gap_pct_abs", 2.0
    if metrics.get("avg_driver_gap_pct") is not None:
        return abs(float(metrics["avg_driver_gap_pct"])), "avg_driver_gap_pct_abs", 2.0
    if metrics.get("contribution_pct") is not None:
        return abs(float(metrics["contribution_pct"])), "contribution_pct_abs", 5.0
    return float(signal.get("impact_score") or 0), "impact_score", 5.0


def fetch_previous_signals(
    db: Database,
    *,
    fingerprints: set[str],
    date_key: int,
    config: SignalRunConfig,
) -> dict[str, dict[str, Any]]:
    if not fingerprints:
        return {}

    clauses = [
        f"s.engine_version = {sql_literal(ENGINE_VERSION)}",
        f"s.date_key < {int(date_key)}",
    ]
    if config.campaign_id is not None:
        clauses.append(f"s.campaign_id = {int(config.campaign_id)}")
    if config.client_id is not None:
        clauses.append(f"s.perspective_client_id = {int(config.client_id)}")
    if config.category is not None:
        clauses.append(f"s.category = {sql_literal(config.category)}")

    rows = db.fetch_csv(
        f"""
with wanted as (
  select value as fingerprint_key
  from jsonb_array_elements_text({sql_literal(json_text(sorted(fingerprints)))}::jsonb)
)
select distinct on (s.fingerprint_key)
  s.fingerprint_key,
  s.client_signal_id::text as client_signal_id,
  s.date_key::text as date_key,
  s.business_date::text as business_date,
  s.lifecycle_status,
  s.first_detected_at::text as first_detected_at,
  s.last_detected_at::text as last_detected_at,
  s.generated_at::text as generated_at,
  s.repeat_count::text as repeat_count,
  s.impact_score::text as impact_score,
  s.metrics_json::text as metrics_json,
  s.severity
from public.mkt_client_signal s
join wanted w
  on w.fingerprint_key = s.fingerprint_key
where {" and ".join(clauses)}
order by s.fingerprint_key, s.date_key desc, s.updated_at desc
"""
    )
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        row["metrics"] = load_json_object(row.get("metrics_json"))
        result[row["fingerprint_key"]] = row
    return result


def classify_lifecycle(signal: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if previous is None:
        return {
            "lifecycle_status": "new",
            "previous_client_signal_id": None,
            "first_detected_at": None,
            "previous_detected_at": None,
            "repeat_count": 1,
            "delta_metrics": {},
            "notification_status": "not_scheduled",
            "notification_reason": "new_signal",
        }

    current_strength, basis, threshold = signal_strength(signal)
    previous_strength, _previous_basis, _previous_threshold = signal_strength(
        {
            "metrics": previous.get("metrics") or {},
            "impact_score": as_float(previous.get("impact_score")) or 0,
        }
    )
    change_abs = current_strength - previous_strength
    effect = signal.get("effect")

    if abs(change_abs) < threshold:
        status = "active"
    elif effect == "positive":
        status = "improved" if change_abs > 0 else "worsened"
    else:
        status = "worsened" if change_abs > 0 else "improved"

    previous_repeat_count = as_int(previous.get("repeat_count")) or 1
    notification_reason = {
        "active": "repeated_no_material_change",
        "improved": "signal_improved",
        "worsened": "signal_worsened",
    }.get(status, "signal_state_changed")
    delta_metrics = {
        "metric_basis": basis,
        "current_strength": round(current_strength, 2),
        "previous_strength": round(previous_strength, 2),
        "change_abs": round(change_abs, 2),
        "change_pct": round((change_abs / previous_strength) * 100, 2) if previous_strength else None,
        "previous_date_key": as_int(previous.get("date_key")),
        "previous_business_date": previous.get("business_date"),
        "threshold": threshold,
    }
    return {
        "lifecycle_status": status,
        "previous_client_signal_id": as_int(previous.get("client_signal_id")),
        "first_detected_at": previous.get("first_detected_at") or previous.get("generated_at"),
        "previous_detected_at": previous.get("last_detected_at") or previous.get("generated_at"),
        "repeat_count": previous_repeat_count + 1,
        "delta_metrics": delta_metrics,
        "notification_status": "not_scheduled",
        "notification_reason": notification_reason,
    }


def apply_lifecycle_state(
    db: Database,
    signals: list[dict[str, Any]],
    *,
    date_key: int,
    config: SignalRunConfig,
) -> list[dict[str, Any]]:
    fingerprints = {str(signal["fingerprint_key"]) for signal in signals}
    previous_by_fingerprint = fetch_previous_signals(
        db,
        fingerprints=fingerprints,
        date_key=date_key,
        config=config,
    )
    enriched: list[dict[str, Any]] = []
    for signal in signals:
        lifecycle = classify_lifecycle(
            signal,
            previous_by_fingerprint.get(str(signal["fingerprint_key"])),
        )
        enriched.append({**signal, **lifecycle})
    return enriched


def delete_existing_scope(db: Database, *, date_key: int, config: SignalRunConfig) -> None:
    clauses = [f"date_key = {int(date_key)}", f"engine_version = {sql_literal(ENGINE_VERSION)}"]
    if config.campaign_id is not None:
        clauses.append(f"campaign_id = {int(config.campaign_id)}")
    if config.client_id is not None:
        clauses.append(f"perspective_client_id = {int(config.client_id)}")
    if config.category is not None:
        clauses.append(f"category = {sql_literal(config.category)}")
    signal_where = " and ".join(clauses)

    event_clauses = [f"date_key = {int(date_key)}", f"engine_version = {sql_literal(ENGINE_VERSION)}"]
    if config.campaign_id is not None:
        event_clauses.append(f"campaign_id = {int(config.campaign_id)}")
    if config.client_id is not None:
        event_clauses.append(f"client_id = {int(config.client_id)}")
    if config.category is not None:
        event_clauses.append(f"category = {sql_literal(config.category)}")
    event_where = " and ".join(event_clauses)

    db.run_psql(
        f"""
begin;
delete from public.mkt_client_signal
where {signal_where};

delete from public.mkt_market_event
where {event_where}
  and not exists (
    select 1
    from public.mkt_client_signal s
    where s.market_event_id = public.mkt_market_event.market_event_id
  );
commit;
"""
    )


def save_signals(db: Database, events: list[dict[str, Any]], signals: list[dict[str, Any]]) -> tuple[int, int]:
    event_csv = io.StringIO()
    event_fields = [
        "event_key",
        "event_fingerprint_key",
        "event_type",
        "business_date",
        "date_key",
        "client_id",
        "campaign_id",
        "campaign_name",
        "category",
        "chain",
        "affected_brands",
        "beneficiary_brands",
        "disadvantaged_brands",
        "neutral_entities",
        "severity",
        "impact_score",
        "confidence_score",
        "metrics_json",
        "evidence_json",
        "source_view",
        "engine_version",
    ]
    writer = csv.DictWriter(event_csv, fieldnames=event_fields, lineterminator="\n")
    writer.writeheader()
    for event in events:
        writer.writerow(
            {
                "event_key": event["event_key"],
                "event_fingerprint_key": event["event_fingerprint_key"],
                "event_type": event["event_type"],
                "business_date": event["business_date"],
                "date_key": event["date_key"],
                "client_id": event.get("client_id"),
                "campaign_id": event.get("campaign_id"),
                "campaign_name": event.get("campaign_name"),
                "category": event.get("category"),
                "chain": event.get("chain"),
                "affected_brands": json_text(event.get("affected_brands") or []),
                "beneficiary_brands": json_text(event.get("beneficiary_brands") or []),
                "disadvantaged_brands": json_text(event.get("disadvantaged_brands") or []),
                "neutral_entities": json_text(event.get("neutral_entities") or []),
                "severity": event["severity"],
                "impact_score": event["impact_score"],
                "confidence_score": event["confidence_score"],
                "metrics_json": json_text(event.get("metrics") or {}),
                "evidence_json": json_text(event.get("evidence") or {}),
                "source_view": event.get("source_view"),
                "engine_version": ENGINE_VERSION,
            }
        )

    signal_csv = io.StringIO()
    signal_fields = [
        "signal_key",
        "fingerprint_key",
        "event_key",
        "signal_type",
        "lifecycle_status",
        "previous_client_signal_id",
        "business_date",
        "date_key",
        "perspective_client_id",
        "campaign_id",
        "campaign_name",
        "category",
        "perspective_brand",
        "counterparty_brand",
        "chain",
        "effect",
        "audience",
        "severity",
        "impact_score",
        "confidence_score",
        "headline",
        "summary",
        "business_reading",
        "recommended_action",
        "tone",
        "metrics_json",
        "evidence_json",
        "narrative_json",
        "delta_metrics_json",
        "navigation_json",
        "llm_provider",
        "llm_model",
        "llm_prompt_version",
        "first_detected_at",
        "previous_detected_at",
        "repeat_count",
        "notification_status",
        "notification_reason",
        "engine_version",
    ]
    writer = csv.DictWriter(signal_csv, fieldnames=signal_fields, lineterminator="\n")
    writer.writeheader()
    for signal in signals:
        writer.writerow(
            {
                "signal_key": signal["signal_key"],
                "fingerprint_key": signal["fingerprint_key"],
                "event_key": signal["event_key"],
                "signal_type": signal["signal_type"],
                "lifecycle_status": signal.get("lifecycle_status") or "new",
                "previous_client_signal_id": signal.get("previous_client_signal_id"),
                "business_date": signal["business_date"],
                "date_key": signal["date_key"],
                "perspective_client_id": signal.get("perspective_client_id"),
                "campaign_id": signal.get("campaign_id"),
                "campaign_name": signal.get("campaign_name"),
                "category": signal.get("category"),
                "perspective_brand": signal.get("perspective_brand"),
                "counterparty_brand": signal.get("counterparty_brand"),
                "chain": signal.get("chain"),
                "effect": signal["effect"],
                "audience": signal.get("audience") or "brand_manager",
                "severity": signal["severity"],
                "impact_score": signal["impact_score"],
                "confidence_score": signal["confidence_score"],
                "headline": signal.get("headline"),
                "summary": signal.get("summary"),
                "business_reading": signal.get("business_reading"),
                "recommended_action": signal.get("recommended_action"),
                "tone": signal.get("tone"),
                "metrics_json": json_text(signal.get("metrics") or {}),
                "evidence_json": json_text(signal.get("evidence") or {}),
                "narrative_json": json_text(signal.get("narrative") or {}),
                "delta_metrics_json": json_text(signal.get("delta_metrics") or {}),
                "navigation_json": json_text(signal.get("navigation") or {}),
                "llm_provider": signal.get("llm_provider"),
                "llm_model": signal.get("llm_model"),
                "llm_prompt_version": signal.get("llm_prompt_version"),
                "first_detected_at": signal.get("first_detected_at"),
                "previous_detected_at": signal.get("previous_detected_at"),
                "repeat_count": signal.get("repeat_count") or 1,
                "notification_status": signal.get("notification_status") or "not_scheduled",
                "notification_reason": signal.get("notification_reason"),
                "engine_version": ENGINE_VERSION,
            }
        )

    sql = f"""
begin;
create temp table tmp_market_event_load (
  event_key text,
  event_fingerprint_key text,
  event_type text,
  business_date date,
  date_key integer,
  client_id bigint,
  campaign_id bigint,
  campaign_name text,
  category text,
  chain text,
  affected_brands jsonb,
  beneficiary_brands jsonb,
  disadvantaged_brands jsonb,
  neutral_entities jsonb,
  severity text,
  impact_score numeric(8,2),
  confidence_score numeric(8,2),
  metrics_json jsonb,
  evidence_json jsonb,
  source_view text,
  engine_version text
);
copy tmp_market_event_load ({", ".join(event_fields)}) from stdin with (format csv, header true);
{event_csv.getvalue()}\\.

insert into public.mkt_market_event (
  event_key,
  event_fingerprint_key,
  event_type,
  business_date,
  date_key,
  client_id,
  campaign_id,
  campaign_name,
  category,
  chain,
  affected_brands,
  beneficiary_brands,
  disadvantaged_brands,
  neutral_entities,
  severity,
  impact_score,
  confidence_score,
  metrics_json,
  evidence_json,
  source_view,
  engine_version,
  updated_at
)
select
  event_key,
  event_fingerprint_key,
  event_type,
  business_date,
  date_key,
  client_id,
  campaign_id,
  campaign_name,
  category,
  chain,
  affected_brands,
  beneficiary_brands,
  disadvantaged_brands,
  neutral_entities,
  severity,
  impact_score,
  confidence_score,
  metrics_json,
  evidence_json,
  source_view,
  engine_version,
  now()
from tmp_market_event_load
on conflict (event_key)
do update set
  event_type = excluded.event_type,
  event_fingerprint_key = excluded.event_fingerprint_key,
  business_date = excluded.business_date,
  date_key = excluded.date_key,
  client_id = excluded.client_id,
  campaign_id = excluded.campaign_id,
  campaign_name = excluded.campaign_name,
  category = excluded.category,
  chain = excluded.chain,
  affected_brands = excluded.affected_brands,
  beneficiary_brands = excluded.beneficiary_brands,
  disadvantaged_brands = excluded.disadvantaged_brands,
  neutral_entities = excluded.neutral_entities,
  severity = excluded.severity,
  impact_score = excluded.impact_score,
  confidence_score = excluded.confidence_score,
  metrics_json = excluded.metrics_json,
  evidence_json = excluded.evidence_json,
  source_view = excluded.source_view,
  engine_version = excluded.engine_version,
  updated_at = now();

create temp table tmp_client_signal_load (
  signal_key text,
  fingerprint_key text,
  event_key text,
  signal_type text,
  lifecycle_status text,
  previous_client_signal_id bigint,
  business_date date,
  date_key integer,
  perspective_client_id bigint,
  campaign_id bigint,
  campaign_name text,
  category text,
  perspective_brand text,
  counterparty_brand text,
  chain text,
  effect text,
  audience text,
  severity text,
  impact_score numeric(8,2),
  confidence_score numeric(8,2),
  headline text,
  summary text,
  business_reading text,
  recommended_action text,
  tone text,
  metrics_json jsonb,
  evidence_json jsonb,
  narrative_json jsonb,
  delta_metrics_json jsonb,
  navigation_json jsonb,
  llm_provider text,
  llm_model text,
  llm_prompt_version text,
  first_detected_at timestamptz,
  previous_detected_at timestamptz,
  repeat_count integer,
  notification_status text,
  notification_reason text,
  engine_version text
);
copy tmp_client_signal_load ({", ".join(signal_fields)}) from stdin with (format csv, header true);
{signal_csv.getvalue()}\\.

insert into public.mkt_client_signal (
  signal_key,
  fingerprint_key,
  market_event_id,
  previous_client_signal_id,
  event_key,
  signal_type,
  lifecycle_status,
  business_date,
  date_key,
  perspective_client_id,
  campaign_id,
  campaign_name,
  category,
  perspective_brand,
  counterparty_brand,
  chain,
  effect,
  audience,
  severity,
  impact_score,
  confidence_score,
  headline,
  summary,
  business_reading,
  recommended_action,
  tone,
  metrics_json,
  evidence_json,
  narrative_json,
  delta_metrics_json,
  navigation_json,
  llm_provider,
  llm_model,
  llm_prompt_version,
  first_detected_at,
  previous_detected_at,
  last_detected_at,
  repeat_count,
  notification_status,
  notification_reason,
  engine_version,
  updated_at
)
select
  s.signal_key,
  s.fingerprint_key,
  e.market_event_id,
  s.previous_client_signal_id,
  s.event_key,
  s.signal_type,
  s.lifecycle_status,
  s.business_date,
  s.date_key,
  s.perspective_client_id,
  s.campaign_id,
  s.campaign_name,
  s.category,
  s.perspective_brand,
  s.counterparty_brand,
  s.chain,
  s.effect,
  s.audience,
  s.severity,
  s.impact_score,
  s.confidence_score,
  s.headline,
  s.summary,
  s.business_reading,
  s.recommended_action,
  s.tone,
  s.metrics_json,
  s.evidence_json,
  s.narrative_json,
  s.delta_metrics_json,
  s.navigation_json,
  s.llm_provider,
  s.llm_model,
  s.llm_prompt_version,
  coalesce(s.first_detected_at, now()),
  s.previous_detected_at,
  now(),
  coalesce(s.repeat_count, 1),
  coalesce(s.notification_status, 'not_scheduled'),
  s.notification_reason,
  s.engine_version,
  now()
from tmp_client_signal_load s
join public.mkt_market_event e
  on e.event_key = s.event_key
on conflict (signal_key)
do update set
  fingerprint_key = excluded.fingerprint_key,
  market_event_id = excluded.market_event_id,
  previous_client_signal_id = excluded.previous_client_signal_id,
  event_key = excluded.event_key,
  signal_type = excluded.signal_type,
  lifecycle_status = excluded.lifecycle_status,
  business_date = excluded.business_date,
  date_key = excluded.date_key,
  perspective_client_id = excluded.perspective_client_id,
  campaign_id = excluded.campaign_id,
  campaign_name = excluded.campaign_name,
  category = excluded.category,
  perspective_brand = excluded.perspective_brand,
  counterparty_brand = excluded.counterparty_brand,
  chain = excluded.chain,
  effect = excluded.effect,
  audience = excluded.audience,
  severity = excluded.severity,
  impact_score = excluded.impact_score,
  confidence_score = excluded.confidence_score,
  headline = excluded.headline,
  summary = excluded.summary,
  business_reading = excluded.business_reading,
  recommended_action = excluded.recommended_action,
  tone = excluded.tone,
  metrics_json = excluded.metrics_json,
  evidence_json = excluded.evidence_json,
  narrative_json = excluded.narrative_json,
  delta_metrics_json = excluded.delta_metrics_json,
  navigation_json = excluded.navigation_json,
  llm_provider = excluded.llm_provider,
  llm_model = excluded.llm_model,
  llm_prompt_version = excluded.llm_prompt_version,
  first_detected_at = excluded.first_detected_at,
  previous_detected_at = excluded.previous_detected_at,
  last_detected_at = excluded.last_detected_at,
  repeat_count = excluded.repeat_count,
  notification_status = excluded.notification_status,
  notification_reason = excluded.notification_reason,
  engine_version = excluded.engine_version,
  updated_at = now();

select
  (select count(*) from tmp_market_event_load),
  (select count(*) from tmp_client_signal_load);
commit;
"""
    output = db.run_psql(sql, tuples_only=True)
    rows = [line for line in output.splitlines() if line.strip()]
    if not rows:
        return (0, 0)
    event_count, signal_count = rows[-1].split("\t", 1)
    return int(event_count), int(signal_count)


def run_signal_generation(db: Database, config: SignalRunConfig) -> dict[str, Any]:
    date_key, business_date = resolve_date(db, config)
    brand_rows = fetch_brand_rows(db, config, date_key)
    sku_rows = fetch_sku_rows(db, config, date_key)

    all_events: list[dict[str, Any]] = []
    all_signals: list[dict[str, Any]] = []
    for generator_events, generator_signals in [
        generate_brand_position(brand_rows, config),
        generate_sku_price_gaps(sku_rows, config),
        generate_promo_price_breaks(sku_rows, config),
        generate_driver_sku_signals(sku_rows, config),
    ]:
        all_events.extend(generator_events)
        all_signals.extend(generator_signals)

    all_events = dedupe_by_key(all_events, "event_key")
    all_signals = dedupe_by_key(all_signals, "signal_key")
    selected_signals = select_diverse_signals(all_signals, config.max_signals)
    selected_event_keys = {signal["event_key"] for signal in selected_signals}
    selected_events = [event for event in all_events if event["event_key"] in selected_event_keys]
    lifecycle_signals = apply_lifecycle_state(
        db,
        selected_signals,
        date_key=date_key,
        config=config,
    )

    enriched_signals, llm_used = enrich_signal_narratives(
        db,
        lifecycle_signals,
        skip_llm=config.skip_llm,
    )
    if config.dry_run:
        return {
            "date_key": date_key,
            "business_date": business_date,
            "market_events": len(selected_events),
            "client_signals": len(enriched_signals),
            "saved": False,
            "llm_used": llm_used,
        }

    delete_existing_scope(db, date_key=date_key, config=config)
    saved_events, saved_signals = save_signals(db, selected_events, enriched_signals)
    return {
        "date_key": date_key,
        "business_date": business_date,
        "market_events": saved_events,
        "client_signals": saved_signals,
        "saved": True,
        "llm_used": llm_used,
    }
