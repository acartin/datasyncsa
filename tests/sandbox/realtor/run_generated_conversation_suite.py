#!/usr/bin/env python3
"""
Runner JSON-driven para baterias conversacionales realtor.

Uso:
  python3 tests/sandbox/realtor/run_generated_conversation_suite.py \
    --suite tests/sandbox/realtor/generated_conversation_suite.template.json

Opciones comunes:
  --json-out /tmp/realtor_generated_suite_report.json
  --stop-on-failure

Notas:
- Ejecuta contra ai-runtime directo.
- Si INTERNAL_API_TOKEN esta disponible, intenta leer turn-trace para validar
  dialogue_act y otros datos estructurados del turno.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests no esta instalado. Instala con: pip install requests")
    sys.exit(1)


DEFAULT_CLIENT_ID = os.getenv("CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")
DEFAULT_USER_ID = os.getenv("REALTOR_SANDBOX_USER_ID", "generated-suite-user")
DEFAULT_RUNTIME_URL = os.getenv(
    "AI_RUNTIME_SANDBOX_API",
    f"http://127.0.0.1:{os.getenv('AI_RUNTIME_PORT', '8096')}/api/v1",
).rstrip("/")
DEFAULT_INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN")
SUITE_TYPES = {"generated", "regression", "manual"}
STRUCTURED_EXPECTATION_KEYS = {
    "expected_should_ask",
    "expected_capture_exposure_count",
    "expected_field_to_ask",
    "expected_field_to_ask_any",
    "forbidden_field_to_ask_any",
    "expected_question_contains_any",
    "expected_completed_fields_all",
    "expected_lead_extracted_contains",
    "expected_criteria_min",
    "expected_criteria_max",
}
FIELD_ALIASES = {
    "extracted_name": "nombre",
    "name": "nombre",
    "correo": "email",
    "mail": "email",
    "extracted_email": "email",
    "phone": "telefono",
    "extracted_phone": "telefono",
    "budget": "presupuesto",
    "timeline": "fecha_preferida",
    "date_preferred": "fecha_preferida",
    "extracted_preferred_date": "fecha_preferida",
    "extracted_approval": "aprobacion",
    "extracted_budget": "presupuesto",
    "extracted_preference": "preferencias",
    "extracted_preferences": "preferencias",
    "extracted_appointment_type": "tipo_cita",
    "appointment_type": "tipo_cita",
    "extracted_appointment_intent": "appointment_intent",
}
CRITERION_ALIASES = {
    "intent": "intencion",
    "purchase_intent": "intencion",
    "urgencia": "plazo",
    "timeline": "plazo",
    "urgency": "plazo",
    "emergencia": "plazo",
    "fit": "match",
    "solvency": "solvencia",
    "finance": "solvencia",
    "financial": "solvencia",
}
VALUE_ALIASES = {
    "visita": "visit",
    "visit": "visit",
    "videollamada": "video_call",
    "video call": "video_call",
    "video_call": "video_call",
    "llamada": "call",
    "call": "call",
    "positivo": "positive",
    "positive": "positive",
    "negativo": "negative",
    "negative": "negative",
    "incierto": "uncertain",
    "uncertain": "uncertain",
}


@dataclass
class Issue:
    severity: str
    conversation_id: str
    turn_index: int
    message: str
    user_text: str
    answer: str


@dataclass
class TurnResult:
    turn_index: int
    user_text: str
    answer: str
    components_count: int
    render_mode: str | None
    cards_mode: str | None
    trace_id: str | None
    dialogue_act: str | None = None
    turn_output_types: list[str] = field(default_factory=list)
    search_match_scope: str | None = None
    search_filters: dict[str, Any] | None = None
    effective_search_filters: dict[str, Any] | None = None
    lead_should_ask: bool | None = None
    lead_capture_exposure_count: int | None = None
    lead_field_to_ask: str | None = None
    lead_question_to_ask: str | None = None
    lead_completed_fields: list[str] = field(default_factory=list)
    lead_extracted: dict[str, Any] = field(default_factory=dict)
    lead_criteria_scores: dict[str, Any] = field(default_factory=dict)
    passed: bool = True
    issues: list[str] = field(default_factory=list)
    manual_review_focus: list[str] = field(default_factory=list)


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _lower(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _merge_expectations(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults or {})
    merged.update(overrides or {})
    return merged


def _normalize_field_key(value: Any) -> str:
    normalized = _lower(value).replace(" ", "_")
    return FIELD_ALIASES.get(normalized, normalized)


def _normalize_criterion_key(value: Any) -> str:
    normalized = _lower(value).replace(" ", "_")
    return CRITERION_ALIASES.get(normalized, normalized)


def _expect_requires_trace(expect: dict[str, Any]) -> bool:
    return any(key in expect for key in STRUCTURED_EXPECTATION_KEYS)


def _normalize_value_token(value: Any) -> Any:
    if isinstance(value, str):
        normalized = _lower(value).replace(" ", "_")
        return VALUE_ALIASES.get(normalized, normalized)
    return value


def _value_matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, expected_value in expected.items():
            actual_key = _normalize_field_key(key)
            if actual_key not in actual:
                return False
            if not _value_matches(expected_value, actual.get(actual_key)):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        normalized_actual = [
            _normalize_value_token(item)
            for item in actual
        ]
        for item in expected:
            if isinstance(item, str):
                if _normalize_value_token(item) not in normalized_actual:
                    return False
            elif item not in actual:
                return False
        return True
    if isinstance(expected, str):
        return _normalize_value_token(expected) == _normalize_value_token(actual)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 1e-6
    return expected == actual


def _infer_suite_type(suite: dict[str, Any], suite_path: str | None = None) -> str:
    explicit = str(suite.get("suite_type") or "").strip().lower()
    if explicit in SUITE_TYPES:
        return explicit

    candidates = [
        str(suite.get("suite_id") or ""),
        str(Path(suite_path).stem if suite_path else ""),
    ]
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if "regression" in normalized:
            return "regression"
        if "manual" in normalized:
            return "manual"
        if "generated" in normalized:
            return "generated"
    return "manual"


class GeneratedConversationSuiteRunner:
    def __init__(
        self,
        *,
        runtime_url: str,
        client_id: str,
        user_id: str,
        internal_token: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.runtime_url = runtime_url.rstrip("/")
        self.client_id = client_id
        self.user_id = user_id
        self.internal_token = (internal_token or "").strip() or None
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def _trace_headers(self) -> dict[str, str]:
        if not self.internal_token:
            return {}
        return {"X-Internal-Token": self.internal_token}

    def _chat(self, *, session_id: str, conversation_id: str, user_text: str) -> dict[str, Any]:
        payload = {
            "clientId": self.client_id,
            "userId": self.user_id,
            "flow": "realtor_flow",
            "message": user_text,
            "sessionId": session_id,
            "conversationId": conversation_id,
            "metadata": {
                "sandbox": "realtor",
                "purpose": "generated-conversation-suite",
            },
        }
        response = self.session.post(
            f"{self.runtime_url}/chat",
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_trace(self, *, session_id: str, turn_index: int) -> dict[str, Any] | None:
        if not self.internal_token:
            return None
        response = self.session.get(
            f"{self.runtime_url}/debug/turn-traces/clients/{self.client_id}/sessions/{session_id}/turns/{turn_index}",
            headers=self._trace_headers(),
            timeout=20,
        )
        if response.status_code != 200:
            return None
        return response.json()

    @staticmethod
    def _extract_trace_facts(trace_payload: dict[str, Any] | None) -> dict[str, Any]:
        if not trace_payload:
            return {}
        summary = trace_payload.get("final_state_summary") or {}
        lead_advisor = summary.get("lead_advisor") or {}
        facts: dict[str, Any] = {
            "dialogue_act": (((summary.get("turn_analysis") or {}).get("dialogue_act"))),
            "turn_output_types": summary.get("turn_output_types") or [],
            "search_filters": (((summary.get("realtor") or {}).get("search_filters"))),
            "effective_search_filters": (((summary.get("realtor") or {}).get("effective_search_filters"))),
            "search_match_scope": None,
            "lead_should_ask": lead_advisor.get("should_ask"),
            "lead_capture_exposure_count": lead_advisor.get("capture_exposure_count"),
            "lead_field_to_ask": lead_advisor.get("field_to_ask"),
            "lead_question_to_ask": lead_advisor.get("question_to_ask"),
            "lead_completed_fields": list(lead_advisor.get("completed_fields") or []),
            "lead_extracted": dict(lead_advisor.get("lead_extracted") or {}),
            "lead_criteria_scores": dict(lead_advisor.get("criteria_scores") or {}),
        }
        for event in reversed(trace_payload.get("events") or []):
            if event.get("kind") == "node_end" and event.get("name") == "search":
                turn_outputs = ((event.get("payload") or {}).get("state_updates") or {}).get("turn_outputs") or []
                if turn_outputs:
                    facts["search_match_scope"] = turn_outputs[-1].get("match_scope")
                    break
        return facts

    @staticmethod
    def _evaluate_turn(
        *,
        conversation_id: str,
        turn_index: int,
        user_text: str,
        response: dict[str, Any],
        trace_facts: dict[str, Any],
        expect: dict[str, Any],
    ) -> TurnResult:
        answer = str(response.get("answer") or "")
        components = response.get("components") or []
        result = TurnResult(
            turn_index=turn_index,
            user_text=user_text,
            answer=answer,
            components_count=len(components),
            render_mode=response.get("render_mode"),
            cards_mode=response.get("cards_mode"),
            trace_id=((response.get("metadata") or {}).get("trace_id")),
            dialogue_act=trace_facts.get("dialogue_act"),
            turn_output_types=list(trace_facts.get("turn_output_types") or []),
            search_match_scope=trace_facts.get("search_match_scope"),
            search_filters=trace_facts.get("search_filters"),
            effective_search_filters=trace_facts.get("effective_search_filters"),
            lead_should_ask=trace_facts.get("lead_should_ask"),
            lead_capture_exposure_count=trace_facts.get("lead_capture_exposure_count"),
            lead_field_to_ask=trace_facts.get("lead_field_to_ask"),
            lead_question_to_ask=trace_facts.get("lead_question_to_ask"),
            lead_completed_fields=list(trace_facts.get("lead_completed_fields") or []),
            lead_extracted=dict(trace_facts.get("lead_extracted") or {}),
            lead_criteria_scores=dict(trace_facts.get("lead_criteria_scores") or {}),
            manual_review_focus=list(expect.get("manual_review_focus") or []),
        )

        lowered_answer = _lower(answer)
        answer_contains_any = [_lower(item) for item in expect.get("answer_contains_any", [])]
        answer_contains_all = [_lower(item) for item in expect.get("answer_contains_all", [])]
        answer_excludes = [_lower(item) for item in expect.get("answer_excludes", [])]

        if answer_contains_any and not any(item in lowered_answer for item in answer_contains_any):
            result.issues.append(f"la respuesta no contiene ninguna de las pistas esperadas: {answer_contains_any}")
        for item in answer_contains_all:
            if item not in lowered_answer:
                result.issues.append(f"la respuesta no contiene el texto esperado: {item}")
        for item in answer_excludes:
            if item in lowered_answer:
                result.issues.append(f"la respuesta contiene texto prohibido: {item}")

        min_components = expect.get("min_components")
        max_components = expect.get("max_components")
        max_questions = expect.get("max_questions")
        if min_components is not None and result.components_count < int(min_components):
            result.issues.append(f"esperaba al menos {min_components} components y llegaron {result.components_count}")
        if max_components is not None and result.components_count > int(max_components):
            result.issues.append(f"esperaba como maximo {max_components} components y llegaron {result.components_count}")
        if max_questions is not None and answer.count("?") > int(max_questions):
            result.issues.append(f"esperaba como maximo {max_questions} preguntas y llegaron {answer.count('?')}")

        require_cards = expect.get("require_cards")
        if require_cards is True and result.components_count == 0:
            result.issues.append("se esperaban cards y no llegaron")
        if require_cards is False and result.components_count > 0:
            result.issues.append("no se esperaban cards y el turno devolvio components")

        expected_render_mode = expect.get("expected_render_mode")
        if expected_render_mode and result.render_mode != expected_render_mode:
            result.issues.append(f"render_mode esperado={expected_render_mode} real={result.render_mode}")

        expected_cards_mode = expect.get("expected_cards_mode")
        if expected_cards_mode and result.cards_mode != expected_cards_mode:
            result.issues.append(f"cards_mode esperado={expected_cards_mode} real={result.cards_mode}")

        expected_dialogue_acts = set(expect.get("expected_dialogue_act_any") or [])
        if expected_dialogue_acts and result.dialogue_act is not None and result.dialogue_act not in expected_dialogue_acts:
            result.issues.append(f"dialogue_act esperado en {sorted(expected_dialogue_acts)} real={result.dialogue_act}")

        expected_turn_output_types = set(expect.get("expected_turn_output_types_any") or [])
        if expected_turn_output_types and result.turn_output_types and not expected_turn_output_types.intersection(result.turn_output_types):
            result.issues.append(
                f"turn_output_types esperados intersectan {sorted(expected_turn_output_types)} y llegaron {result.turn_output_types}"
            )

        expected_match_scopes = set(expect.get("expected_search_match_scope_any") or [])
        if expected_match_scopes and result.search_match_scope is not None and result.search_match_scope not in expected_match_scopes:
            result.issues.append(
                f"search_match_scope esperado en {sorted(expected_match_scopes)} real={result.search_match_scope}"
            )

        if _expect_requires_trace(expect) and not trace_facts:
            result.issues.append("faltan turn traces para validar expectativas estructuradas; usa --internal-token")
        else:
            if "expected_should_ask" in expect and result.lead_should_ask != expect.get("expected_should_ask"):
                result.issues.append(
                    f"lead_advisor.should_ask esperado={expect.get('expected_should_ask')} real={result.lead_should_ask}"
                )

            if "expected_capture_exposure_count" in expect:
                expected_count = int(expect.get("expected_capture_exposure_count"))
                if int(result.lead_capture_exposure_count or 0) != expected_count:
                    result.issues.append(
                        "lead_advisor.capture_exposure_count "
                        f"esperado={expected_count} real={result.lead_capture_exposure_count}"
                    )

            if "expected_field_to_ask" in expect:
                expected_field = expect.get("expected_field_to_ask")
                actual_field = result.lead_field_to_ask
                if expected_field is None:
                    if actual_field is not None:
                        result.issues.append(f"field_to_ask esperado=None real={actual_field}")
                elif _normalize_field_key(actual_field) != _normalize_field_key(expected_field):
                    result.issues.append(f"field_to_ask esperado={expected_field} real={actual_field}")

            expected_fields_any = expect.get("expected_field_to_ask_any") or []
            if expected_fields_any:
                actual_field = result.lead_field_to_ask
                normalized_expected = {_normalize_field_key(item) for item in expected_fields_any}
                normalized_actual = None if actual_field is None else _normalize_field_key(actual_field)
                if normalized_actual not in normalized_expected:
                    result.issues.append(
                        f"field_to_ask esperado en {sorted(normalized_expected)} real={actual_field}"
                    )

            forbidden_fields = expect.get("forbidden_field_to_ask_any") or []
            if forbidden_fields and result.lead_field_to_ask is not None:
                normalized_forbidden = {_normalize_field_key(item) for item in forbidden_fields}
                if _normalize_field_key(result.lead_field_to_ask) in normalized_forbidden:
                    result.issues.append(f"field_to_ask prohibido={result.lead_field_to_ask}")

            expected_question_contains_any = [_lower(item) for item in expect.get("expected_question_contains_any", [])]
            if expected_question_contains_any:
                normalized_question = _lower(result.lead_question_to_ask)
                if not any(item in normalized_question for item in expected_question_contains_any):
                    result.issues.append(
                        "question_to_ask no contiene ninguna pista esperada: "
                        f"{expected_question_contains_any}"
                    )

            expected_completed_fields = expect.get("expected_completed_fields_all") or []
            if expected_completed_fields:
                normalized_completed = {_normalize_field_key(item) for item in result.lead_completed_fields}
                missing_fields = [
                    field for field in expected_completed_fields
                    if _normalize_field_key(field) not in normalized_completed
                ]
                if missing_fields:
                    result.issues.append(f"faltan completed_fields esperados: {missing_fields}")

            expected_lead_extracted = expect.get("expected_lead_extracted_contains")
            if expected_lead_extracted:
                normalized_actual = {
                    _normalize_field_key(key): value
                    for key, value in result.lead_extracted.items()
                }
                normalized_expected = {
                    _normalize_field_key(key): value
                    for key, value in expected_lead_extracted.items()
                }
                if not _value_matches(normalized_expected, normalized_actual):
                    result.issues.append(
                        f"lead_extracted no contiene el parcial esperado: {expected_lead_extracted}"
                    )

            expected_criteria_min = expect.get("expected_criteria_min") or {}
            for criterion_key, min_value in expected_criteria_min.items():
                normalized_key = _normalize_criterion_key(criterion_key)
                actual_value = None
                for actual_key, score in result.lead_criteria_scores.items():
                    if _normalize_criterion_key(actual_key) == normalized_key:
                        actual_value = score
                        break
                if actual_value is None:
                    result.issues.append(f"no existe criterio {criterion_key} en criteria_scores")
                    continue
                if float(actual_value) < float(min_value):
                    result.issues.append(
                        f"criteria_scores[{criterion_key}] esperado >= {min_value} real={actual_value}"
                    )

            expected_criteria_max = expect.get("expected_criteria_max") or {}
            for criterion_key, max_value in expected_criteria_max.items():
                normalized_key = _normalize_criterion_key(criterion_key)
                actual_value = None
                for actual_key, score in result.lead_criteria_scores.items():
                    if _normalize_criterion_key(actual_key) == normalized_key:
                        actual_value = score
                        break
                if actual_value is None:
                    result.issues.append(f"no existe criterio {criterion_key} en criteria_scores")
                    continue
                if float(actual_value) > float(max_value):
                    result.issues.append(
                        f"criteria_scores[{criterion_key}] esperado <= {max_value} real={actual_value}"
                    )

        result.passed = not result.issues
        return result

    def run_suite(self, suite: dict[str, Any], *, suite_type: str, stop_on_failure: bool = False) -> dict[str, Any]:
        defaults = ((suite.get("defaults") or {}).get("expect")) or {}
        conversations = suite.get("conversations") or []
        report: dict[str, Any] = {
            "suite_id": suite.get("suite_id"),
            "suite_type": suite_type,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "summary": {
                "conversations_total": len(conversations),
                "turns_total": 0,
                "turns_passed": 0,
                "turns_failed": 0,
            },
            "conversations": [],
        }

        total_conversations = len(conversations)
        for conversation_index, conversation in enumerate(conversations, start=1):
            conversation_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            turns_report: list[dict[str, Any]] = []
            print(
                f"[suite {conversation_index}/{total_conversations}] conversation={conversation.get('id')} session_id={session_id} turns={len(conversation.get('turns') or [])}",
                flush=True,
            )
            total_turns = len(conversation.get("turns") or [])
            for idx, turn in enumerate(conversation.get("turns") or [], start=1):
                user_text = str(turn.get("user") or "")
                expect = _merge_expectations(defaults, turn.get("expect") or {})
                print(
                    f"  [turn {idx}/{total_turns}] user={user_text!r}",
                    flush=True,
                )
                response = self._chat(
                    session_id=session_id,
                    conversation_id=conversation_id,
                    user_text=user_text,
                )
                trace_payload = self._fetch_trace(session_id=session_id, turn_index=idx)
                trace_facts = self._extract_trace_facts(trace_payload)
                result = self._evaluate_turn(
                    conversation_id=str(conversation.get("id") or "unknown"),
                    turn_index=idx,
                    user_text=user_text,
                    response=response,
                    trace_facts=trace_facts,
                    expect=expect,
                )
                report["summary"]["turns_total"] += 1
                if result.passed:
                    report["summary"]["turns_passed"] += 1
                else:
                    report["summary"]["turns_failed"] += 1
                print(
                    f"  [turn {idx}/{total_turns}] status={'PASS' if result.passed else 'FAIL'} components={result.components_count} dialogue_act={result.dialogue_act}",
                    flush=True,
                )
                turns_report.append(
                    {
                        "turn_index": result.turn_index,
                        "user_text": result.user_text,
                        "answer": result.answer,
                        "components_count": result.components_count,
                        "render_mode": result.render_mode,
                        "cards_mode": result.cards_mode,
                        "trace_id": result.trace_id,
                        "dialogue_act": result.dialogue_act,
                        "turn_output_types": result.turn_output_types,
                        "search_match_scope": result.search_match_scope,
                        "search_filters": result.search_filters,
                        "effective_search_filters": result.effective_search_filters,
                        "lead_should_ask": result.lead_should_ask,
                        "lead_capture_exposure_count": result.lead_capture_exposure_count,
                        "lead_field_to_ask": result.lead_field_to_ask,
                        "lead_question_to_ask": result.lead_question_to_ask,
                        "lead_completed_fields": result.lead_completed_fields,
                        "lead_extracted": result.lead_extracted,
                        "lead_criteria_scores": result.lead_criteria_scores,
                        "passed": result.passed,
                        "issues": result.issues,
                        "manual_review_focus": result.manual_review_focus,
                    }
                )
                if stop_on_failure and not result.passed:
                    break

            report["conversations"].append(
                {
                    "id": conversation.get("id"),
                    "description": conversation.get("description"),
                    "tags": conversation.get("tags") or [],
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "turns": turns_report,
                    "passed": all(turn["passed"] for turn in turns_report),
                }
            )

        return report


def _print_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") or {}
    print("=" * 72)
    print("CONVERSATION SUITE")
    print("=" * 72)
    print(f"suite_id: {report.get('suite_id')}")
    print(f"suite_type: {report.get('suite_type')}")
    print(f"turns_total: {summary.get('turns_total')}")
    print(f"turns_passed: {summary.get('turns_passed')}")
    print(f"turns_failed: {summary.get('turns_failed')}")

    for conversation in report.get("conversations") or []:
        status = "PASS" if conversation.get("passed") else "FAIL"
        print()
        print(f"[{status}] {conversation.get('id')} :: {conversation.get('description')}")
        print(f"session_id={conversation.get('session_id')} conversation_id={conversation.get('conversation_id')}")
        for turn in conversation.get("turns") or []:
            turn_status = "ok" if turn.get("passed") else "fail"
            print(f"  - turno {turn.get('turn_index')} [{turn_status}] user={turn.get('user_text')!r}")
            print(f"    answer={turn.get('answer')!r}")
            lead_field = turn.get("lead_field_to_ask")
            lead_should_ask = turn.get("lead_should_ask")
            if lead_should_ask is not None or lead_field is not None:
                print(
                    "    lead_advisor="
                    f"capture_exposure_count={turn.get('lead_capture_exposure_count')} "
                    f"should_ask={lead_should_ask} "
                    f"field_to_ask={lead_field!r} "
                    f"question_to_ask={turn.get('lead_question_to_ask')!r}"
                )
            if turn.get("issues"):
                for issue in turn.get("issues") or []:
                    print(f"    issue: {issue}")
            if turn.get("manual_review_focus"):
                print(f"    manual_review_focus={turn.get('manual_review_focus')}")


def _publish_debug_bundle(*, suite: dict[str, Any], report: dict[str, Any], publish_dir: str) -> str:
    root = Path(publish_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_id = f"{suite.get('suite_id', 'suite')}-{stamp}"
    bundle_dir = root / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    with open(bundle_dir / "suite.json", "w", encoding="utf-8") as handle:
        json.dump(suite, handle, ensure_ascii=False, indent=2)
    with open(bundle_dir / "report.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    with open(bundle_dir / "meta.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "bundle_id": bundle_id,
                "suite_id": suite.get("suite_id"),
                "suite_type": report.get("suite_type"),
                "client_id": report.get("client_id"),
                "user_id": report.get("user_id"),
                "generated_at": stamp,
                "conversations_total": (report.get("summary") or {}).get("conversations_total"),
                "turns_total": (report.get("summary") or {}).get("turns_total"),
                "turns_failed": (report.get("summary") or {}).get("turns_failed"),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
    return str(bundle_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Runner JSON-driven para conversaciones realtor")
    parser.add_argument(
        "--suite",
        required=True,
        help="Ruta al JSON con la suite generada",
    )
    parser.add_argument(
        "--runtime-url",
        default=DEFAULT_RUNTIME_URL,
        help=f"Base URL de ai-runtime (default: {DEFAULT_RUNTIME_URL})",
    )
    parser.add_argument(
        "--client-id",
        default=DEFAULT_CLIENT_ID,
        help=f"Client ID realtor (default: {DEFAULT_CLIENT_ID})",
    )
    parser.add_argument(
        "--user-id",
        default=DEFAULT_USER_ID,
        help=f"User ID del sandbox (default: {DEFAULT_USER_ID})",
    )
    parser.add_argument(
        "--internal-token",
        default=DEFAULT_INTERNAL_TOKEN,
        help="INTERNAL_API_TOKEN para leer traces (opcional)",
    )
    parser.add_argument(
        "--json-out",
        help="Si se pasa, guarda el reporte completo en JSON",
    )
    parser.add_argument(
        "--debug-publish-dir",
        default="log/generated-conversation-suites",
        help="Directorio donde publicar bundles debug con suite+report (default: log/generated-conversation-suites)",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Detiene cada conversacion al primer turno fallido",
    )
    args = parser.parse_args()

    suite = _load_json(args.suite)
    suite_type = _infer_suite_type(suite, args.suite)
    runner = GeneratedConversationSuiteRunner(
        runtime_url=args.runtime_url,
        client_id=args.client_id,
        user_id=args.user_id,
        internal_token=args.internal_token,
    )
    report = runner.run_suite(suite, suite_type=suite_type, stop_on_failure=args.stop_on_failure)
    _print_report(report)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print()
        print(f"JSON report escrito en: {args.json_out}")

    if args.debug_publish_dir:
        bundle_dir = _publish_debug_bundle(
            suite=suite,
            report=report,
            publish_dir=args.debug_publish_dir,
        )
        print(f"Debug bundle publicado en: {bundle_dir}")

    return 0 if (report.get("summary") or {}).get("turns_failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
