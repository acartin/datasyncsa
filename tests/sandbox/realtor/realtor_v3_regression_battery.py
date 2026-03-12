#!/usr/bin/env python3
"""
Bateria intensiva de regresion conversacional para realtor v3.

Objetivo:
- Ejecutar conversaciones densas contra /api/v3/chat
- Detectar incongruencias de routing, memoria, cards, follow-up y redaccion
- Generar un reporte legible y tambien JSON para analisis posterior

Uso:
  python3 tests/sandbox/realtor/realtor_v3_regression_battery.py
  python3 tests/sandbox/realtor/realtor_v3_regression_battery.py --scenario inventory_active_search
  python3 tests/sandbox/realtor/realtor_v3_regression_battery.py --scenario inventory_active_search,rag_after_search_hours
  python3 tests/sandbox/realtor/realtor_v3_regression_battery.py --json-out /tmp/realtor_battery.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    import requests
except ImportError:
    print("ERROR: requests no esta instalado. Instala con: pip install requests")
    sys.exit(1)


CLIENT_ID = os.getenv("REALTOR_BATTERY_CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")
INFERENCE_V3_URL = os.getenv("INFERENCE_V3_API", "http://127.0.0.1:8095/api/v3")

NAME_PROMPT_MARKERS = (
    "como te gustaria que te llame",
    "como te gustaría que te llame",
    "cómo te gustaria que te llame",
    "cómo te gustaría que te llame",
    "con quien tengo el gusto",
    "con quién tengo el gusto",
)
SHOW_PERMISSION_MARKERS = (
    "quieres que te muestre",
    "te gustaria que te muestre",
    "te gustaría que te muestre",
    "quieres verlas",
    "quieres que te las muestre",
    "te gustaria verlas",
    "te gustaría verlas",
)
SHOW_MARKERS = (
    "te muestro",
    "te las muestro",
    "te muestro estas",
    "te muestro 4",
    "te muestro 3",
    "te muestro ambas",
)
EMPTY_MARKERS = (
    "no encontre",
    "no encontré",
    "no tengo opciones",
    "no tengo propiedades",
    "no hay propiedades",
    "en este momento no encontre",
    "en este momento no encontré",
)


@dataclass
class Issue:
    severity: str
    scenario_id: str
    turn_index: int
    rule: str
    message: str
    user_text: str
    answer: str
    trace: List[str] = field(default_factory=list)


@dataclass
class TurnExpectation:
    expected_intent: Optional[str] = None
    expected_route_mode: Optional[str] = None
    expected_subflow: Optional[str] = None
    min_components: Optional[int] = None
    max_components: Optional[int] = None
    trace_contains: List[str] = field(default_factory=list)
    trace_excludes: List[str] = field(default_factory=list)
    answer_contains_any: List[str] = field(default_factory=list)
    answer_contains_all: List[str] = field(default_factory=list)
    answer_excludes: List[str] = field(default_factory=list)
    custom_checks: List[Callable[[Dict[str, Any], List[Dict[str, Any]]], List[str]]] = field(default_factory=list)


@dataclass
class TurnSpec:
    user_text: str
    expectation: TurnExpectation


@dataclass
class Scenario:
    scenario_id: str
    description: str
    turns: List[TurnSpec]
    tags: List[str] = field(default_factory=list)


def _lower_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_number(text: str) -> bool:
    return bool(re.search(r"\b\d+\b", text or ""))


def _answer_asks_name(answer: str) -> bool:
    lowered = _lower_text(answer)
    return any(marker in lowered for marker in NAME_PROMPT_MARKERS)


def _answer_mentions_empty(answer: str) -> bool:
    lowered = _lower_text(answer)
    return any(marker in lowered for marker in EMPTY_MARKERS)


def _forbidden_show_prompt_when_cards(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    answer = _lower_text(response.get("answer"))
    components = response.get("components") or []
    if not components:
        return []
    if any(marker in answer for marker in SHOW_PERMISSION_MARKERS):
        return ["pregunta permiso para mostrar cards en el mismo turno en que ya las renderiza"]
    return []


def _no_te_muestro_without_cards(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    answer = _lower_text(response.get("answer"))
    components = response.get("components") or []
    if components:
        return []
    if any(marker in answer for marker in SHOW_MARKERS):
        return ["dice que muestra resultados pero el turno no trae cards"]
    return []


def _inventory_should_not_route_to_reference(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    intent = str(response.get("intent") or "").strip().upper()
    trace = (response.get("tracing") or {}).get("trace") or []
    if intent == "PROPERTY_INVENTORY" and "shown_results_reference_resolver" in trace:
        return ["inventario del set actual cayo en shown_results_reference_resolver"]
    return []


def _price_range_should_not_route_to_reference(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    intent = str(response.get("intent") or "").strip().upper()
    trace = (response.get("tracing") or {}).get("trace") or []
    if intent == "PROPERTY_PRICE_RANGE" and "shown_results_reference_resolver" in trace:
        return ["price_range del set actual cayo en shown_results_reference_resolver"]
    return []


def _reference_question_should_use_reference_resolver(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    trace = (response.get("tracing") or {}).get("trace") or []
    if "shown_results_reference_resolver" not in trace:
        return ["pregunta referencial sobre card no uso shown_results_reference_resolver"]
    return []


def _inventory_answer_should_look_like_count(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    intent = str(response.get("intent") or "").strip().upper()
    answer = str(response.get("answer") or "").strip()
    if intent != "PROPERTY_INVENTORY":
        return []
    lowered = answer.lower()
    if not _contains_number(answer):
        return ["respuesta de inventario no contiene conteo visible"]
    if "puedo decirte el precio" in lowered:
        return ["respuesta de inventario parece aclaracion de card, no conteo"]
    return []


def _range_answer_should_look_like_range(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    intent = str(response.get("intent") or "").strip().upper()
    answer = _lower_text(response.get("answer"))
    if intent != "PROPERTY_PRICE_RANGE":
        return []
    if not any(token in answer for token in ("rango", "min", "max", "entre", "desde", "hasta")):
        return ["respuesta de rango de precios no parece rango"]
    return []


def _should_use_generic_rag(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    trace = (response.get("tracing") or {}).get("trace") or []
    if "generic_tool_executor" not in trace:
        return ["pregunta documental no paso por generic_tool_executor"]
    if "realtor_query_compiler" in trace:
        return ["pregunta documental no debio caer en compiler realtor"]
    return []


def _new_base_search_should_not_echo_old_filters(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    answer = _lower_text(response.get("answer"))
    bad_terms = ("dos habitaciones", "estacionamiento", "cochera", "garage", "dos baños", "dos banos")
    leaked = [term for term in bad_terms if term in answer]
    if leaked:
        return [f"respuesta de nueva busqueda siguio mencionando filtros viejos: {', '.join(leaked)}"]
    return []


def _capture_name_after_cards(response: Dict[str, Any], history: List[Dict[str, Any]]) -> List[str]:
    components = response.get("components") or []
    if not components:
        return []
    cards_seen_before = any((item.get("components_count") or 0) > 0 for item in history)
    if cards_seen_before:
        return []
    if not _answer_asks_name(response.get("answer")):
        return ["despues de la primera tanda de cards no inicio progresion comercial con nombre"]
    return []


def _cooldown_should_not_repeat_name_request(response: Dict[str, Any], history: List[Dict[str, Any]]) -> List[str]:
    if not _answer_asks_name(response.get("answer")):
        return []
    recent = history[-2:]
    if any(_answer_asks_name(item.get("answer")) for item in recent):
        return ["repitio captura de nombre demasiado pronto"]
    return []


def _empty_results_should_not_ask_for_name(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    answer = str(response.get("answer") or "")
    if _answer_mentions_empty(answer) and _answer_asks_name(answer):
        return ["pidio nombre en un turno de resultados vacios"]
    return []


def _answer_should_mention_bathrooms(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    answer = _lower_text(response.get("answer"))
    if "bañ" not in answer and "ban" not in answer:
        return ["respuesta referencial de baños no menciona baños"]
    return []


def _answer_should_mention_price(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    answer = _lower_text(response.get("answer"))
    if not any(token in answer for token in ("precio", "$", "usd", "dolar", "cuesta", "costa")):
        return ["respuesta referencial de precio no menciona precio"]
    return []


def _search_should_not_reask_zone(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    answer = _lower_text(response.get("answer"))
    if any(token in answer for token in ("que zona", "qué zona", "cual zona", "cuál zona")):
        return ["refinamiento sobre busqueda activa volvio a pedir zona"]
    return []


def _impossible_search_should_not_render_cards(response: Dict[str, Any], _: List[Dict[str, Any]]) -> List[str]:
    components = response.get("components") or []
    answer = str(response.get("answer") or "")
    if components and _answer_mentions_empty(answer):
        return ["el turno dice que no encontro resultados pero igualmente renderiza cards"]
    return []


SCENARIOS: List[Scenario] = [
    Scenario(
        scenario_id="search_zone_only",
        description="Busqueda solo por zona debe mostrar cards y arrancar progresion comercial",
        tags=["search", "cards", "lead"],
        turns=[
            TurnSpec(
                "en heredia",
                TurnExpectation(
                    expected_intent="PROPERTY_SEARCH",
                    expected_route_mode="tool_required",
                    expected_subflow="realtor_search",
                    min_components=1,
                    trace_contains=["realtor_tool_executor"],
                    custom_checks=[_capture_name_after_cards],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="search_house_buy",
        description="Busqueda de casa para compra en Heredia",
        tags=["search"],
        turns=[
            TurnSpec(
                "hola, busco una casa para comprar en heredia",
                TurnExpectation(
                    expected_intent="PROPERTY_SEARCH",
                    expected_route_mode="tool_required",
                    expected_subflow="realtor_search",
                    min_components=1,
                    trace_contains=["realtor_tool_executor"],
                    custom_checks=[_capture_name_after_cards],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="search_without_zone_then_any_zone",
        description="Busqueda sin zona y luego cualquier zona no debe explotar",
        tags=["search", "clarify"],
        turns=[
            TurnSpec("busco una casa con dos habitaciones", TurnExpectation(answer_excludes=["hubo un error"])),
            TurnSpec(
                "en cualquier zona",
                TurnExpectation(
                    expected_intent="PROPERTY_SEARCH",
                    expected_route_mode="tool_required",
                    trace_contains=["realtor_tool_executor"],
                    answer_excludes=["hubo un error"],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="refine_active_search_bedrooms",
        description="Refinamiento de habitaciones mantiene busqueda activa",
        tags=["refine", "search"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec(
                "con dos habitaciones",
                TurnExpectation(
                    expected_intent="PROPERTY_SEARCH",
                    trace_contains=["realtor_tool_executor"],
                    custom_checks=[_search_should_not_reask_zone],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="refine_active_search_bathrooms",
        description="Refinamiento de baños mantiene busqueda activa",
        tags=["refine", "search"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec(
                "con dos baños",
                TurnExpectation(
                    expected_intent="PROPERTY_SEARCH",
                    trace_contains=["realtor_tool_executor"],
                    custom_checks=[_search_should_not_reask_zone],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="refine_active_search_garage",
        description="Refinamiento de cochera mantiene busqueda activa",
        tags=["refine", "search"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec(
                "con cochera para dos carros",
                TurnExpectation(
                    expected_intent="PROPERTY_SEARCH",
                    trace_contains=["realtor_tool_executor"],
                    custom_checks=[_search_should_not_reask_zone],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="inventory_active_search",
        description="Conteo del set actual no debe caer en referencia de card",
        tags=["inventory", "search"],
        turns=[
            TurnSpec("hola, busco una casa para comprar en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec(
                "cuantas casas tienes en heredia?",
                TurnExpectation(
                    expected_intent="PROPERTY_INVENTORY",
                    expected_route_mode="tool_required",
                    max_components=0,
                    trace_contains=["realtor_tool_executor"],
                    trace_excludes=["shown_results_reference_resolver"],
                    custom_checks=[_inventory_should_not_route_to_reference, _inventory_answer_should_look_like_count],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="inventory_after_rag_return_to_search",
        description="Volver de RAG a inventario del set actual",
        tags=["inventory", "rag"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("cual es el horario?", TurnExpectation(max_components=0, custom_checks=[_should_use_generic_rag])),
            TurnSpec(
                "cuantas casas tienes en heredia?",
                TurnExpectation(
                    expected_intent="PROPERTY_INVENTORY",
                    max_components=0,
                    trace_contains=["realtor_tool_executor"],
                    trace_excludes=["shown_results_reference_resolver"],
                    custom_checks=[_inventory_should_not_route_to_reference, _inventory_answer_should_look_like_count],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="price_range_active_search",
        description="Rango de precios sobre el set actual",
        tags=["price_range", "search"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec(
                "cual es el rango de precios?",
                TurnExpectation(
                    expected_intent="PROPERTY_PRICE_RANGE",
                    max_components=0,
                    trace_contains=["realtor_tool_executor"],
                    trace_excludes=["shown_results_reference_resolver"],
                    custom_checks=[_price_range_should_not_route_to_reference, _range_answer_should_look_like_range],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="reference_last_bathrooms",
        description="Pregunta referencial sobre la ultima card mostrada",
        tags=["reference"],
        turns=[
            TurnSpec("en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec(
                "la ultima casa que me mostraste cuantos baños tiene",
                TurnExpectation(
                    max_components=0,
                    trace_contains=["shown_results_reference_resolver"],
                    custom_checks=[_reference_question_should_use_reference_resolver, _answer_should_mention_bathrooms],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="reference_first_price",
        description="Pregunta referencial por precio de la primera card",
        tags=["reference", "price"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec(
                "y la primera cuanto cuesta",
                TurnExpectation(
                    max_components=0,
                    trace_contains=["shown_results_reference_resolver"],
                    custom_checks=[_reference_question_should_use_reference_resolver, _answer_should_mention_price],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="new_search_resets_old_filters",
        description="Nueva busqueda base no debe arrastrar filtros viejos",
        tags=["transition", "search"],
        turns=[
            TurnSpec(
                "busco una casa con dos habitaciones y un estacionamiento",
                TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1),
            ),
            TurnSpec(
                "que tienes en santo domingo en renta",
                TurnExpectation(
                    expected_intent="PROPERTY_SEARCH",
                    trace_contains=["realtor_tool_executor"],
                    custom_checks=[_new_base_search_should_not_echo_old_filters],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="search_memory_summary",
        description="El bot debe poder resumir la busqueda activa",
        tags=["memory", "search"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("con dos habitaciones", TurnExpectation(expected_intent="PROPERTY_SEARCH", trace_contains=["realtor_tool_executor"])),
            TurnSpec(
                "que ando buscando yo?",
                TurnExpectation(
                    max_components=0,
                    answer_contains_all=["heredia", "habit"],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="name_memory_recall",
        description="Debe recordar el nombre dado por el usuario",
        tags=["memory", "lead"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("me llamo alvaro", TurnExpectation(max_components=0)),
            TurnSpec(
                "como me llamo?",
                TurnExpectation(
                    max_components=0,
                    answer_contains_any=["alvaro", "álvaro"],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="budget_memory_recall",
        description="Debe recordar el presupuesto dado por el usuario",
        tags=["memory", "lead"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("tengo cien mil dolares", TurnExpectation(max_components=0)),
            TurnSpec(
                "que presupuesto te dije?",
                TurnExpectation(
                    max_components=0,
                    answer_contains_any=["100", "cien mil", "100 mil"],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="rag_after_search_hours",
        description="Pregunta documental de horario despues de una busqueda",
        tags=["rag"],
        turns=[
            TurnSpec("en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("cual es el horario?", TurnExpectation(max_components=0, custom_checks=[_should_use_generic_rag])),
        ],
    ),
    Scenario(
        scenario_id="rag_after_search_business",
        description="Pregunta documental sobre actividad de la empresa",
        tags=["rag"],
        turns=[
            TurnSpec("en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("a que se dedican?", TurnExpectation(max_components=0, custom_checks=[_should_use_generic_rag])),
        ],
    ),
    Scenario(
        scenario_id="offtopic_no_cards",
        description="Off-topic no debe disparar path realtor ni cards",
        tags=["offtopic"],
        turns=[
            TurnSpec(
                "venden helados?",
                TurnExpectation(
                    max_components=0,
                    trace_excludes=["realtor_query_compiler", "realtor_tool_executor"],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="solo_esa_inventory",
        description="Confirmacion de si solo existe esa opcion",
        tags=["inventory", "search"],
        turns=[
            TurnSpec(
                "quiero una casa con dos habitaciones y estacionamiento para dos carros",
                TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1),
            ),
            TurnSpec(
                "solo esa tienes en costa rica?",
                TurnExpectation(
                    expected_intent="PROPERTY_INVENTORY",
                    max_components=0,
                    trace_contains=["realtor_tool_executor"],
                    custom_checks=[_inventory_should_not_route_to_reference],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="followup_name_cooldown",
        description="No repetir captura de nombre demasiado pronto",
        tags=["lead", "followup"],
        turns=[
            TurnSpec("casas en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1, custom_checks=[_capture_name_after_cards])),
            TurnSpec("cual es el horario?", TurnExpectation(max_components=0, custom_checks=[_should_use_generic_rag])),
            TurnSpec(
                "venden helados?",
                TurnExpectation(
                    max_components=0,
                    custom_checks=[_cooldown_should_not_repeat_name_request],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="empty_results_no_name_capture",
        description="Resultados vacios no deben gatillar captura de nombre",
        tags=["empty", "lead"],
        turns=[
            TurnSpec(
                "busco casas en santo domingo en renta con 15 habitaciones, 10 cocheras y 12 baños",
                TurnExpectation(
                    max_components=0,
                    custom_checks=[_empty_results_should_not_ask_for_name, _impossible_search_should_not_render_cards],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="search_specific_then_reference_after_transition",
        description="Referencia debe seguir apuntando al ultimo set mostrado",
        tags=["transition", "reference"],
        turns=[
            TurnSpec("en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("que tienes en santo domingo?", TurnExpectation(expected_intent="PROPERTY_SEARCH")),
            TurnSpec(
                "la ultima casa que me mostraste cuantos baños tiene",
                TurnExpectation(
                    max_components=0,
                    trace_contains=["shown_results_reference_resolver"],
                    custom_checks=[_reference_question_should_use_reference_resolver, _answer_should_mention_bathrooms],
                ),
            ),
        ],
    ),
    Scenario(
        scenario_id="search_filters_visibility",
        description="Debe poder explicar filtros activos actuales",
        tags=["memory", "search"],
        turns=[
            TurnSpec("en heredia", TurnExpectation(expected_intent="PROPERTY_SEARCH", min_components=1)),
            TurnSpec("con dos baños", TurnExpectation(expected_intent="PROPERTY_SEARCH", trace_contains=["realtor_tool_executor"])),
            TurnSpec(
                "que filtros estas usando en este momento",
                TurnExpectation(
                    max_components=0,
                    answer_contains_all=["heredia", "bañ"],
                ),
            ),
        ],
    ),
]


class RealtorV3Battery:
    def __init__(self, base_url: str, client_id: str, request_timeout: int = 45) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.request_timeout = request_timeout
        self.session = requests.Session()

    def check_health(self) -> None:
        response = self.session.get(f"{self.base_url}/health", timeout=20)
        response.raise_for_status()
        payload = response.json()
        print(f"Servicio: {payload.get('service')}")
        print(f"Version: {payload.get('version')}")
        print(f"Cache: {payload.get('cache')}")

    def _chat(self, *, conversation_id: str, query_text: str) -> Dict[str, Any]:
        payload = {
            "clientId": self.client_id,
            "conversationId": conversation_id,
            "queryText": query_text,
        }
        response = self.session.post(
            f"{self.base_url}/chat",
            json=payload,
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    def run_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        issues: List[Issue] = []
        history: List[Dict[str, Any]] = []
        rendered_responses: List[Dict[str, Any]] = []

        print(f"[RUN] {scenario.scenario_id} ({len(scenario.turns)} turns)", flush=True)

        for idx, turn in enumerate(scenario.turns, start=1):
            try:
                response = self._chat(conversation_id=conversation_id, query_text=turn.user_text)
            except Exception as exc:
                issues.append(
                    Issue(
                        severity="error",
                        scenario_id=scenario.scenario_id,
                        turn_index=idx,
                        rule="transport_error",
                        message=str(exc),
                        user_text=turn.user_text,
                        answer="",
                        trace=[],
                    )
                )
                break

            rendered_responses.append(
                {
                    "user_text": turn.user_text,
                    "answer": response.get("answer"),
                    "intent": response.get("intent"),
                    "route_mode": response.get("routeMode") or response.get("route_mode"),
                    "active_subflow": response.get("activeSubflow") or response.get("active_subflow"),
                    "components_count": len(response.get("components") or []),
                    "trace": (response.get("tracing") or {}).get("trace") or [],
                }
            )
            issues.extend(self._analyze_turn(scenario, idx, turn, response, history))
            history.append(rendered_responses[-1])

        return {
            "scenario_id": scenario.scenario_id,
            "description": scenario.description,
            "tags": scenario.tags,
            "conversation_id": conversation_id,
            "issues": [issue.__dict__ for issue in issues],
            "responses": rendered_responses,
        }

    def _analyze_turn(
        self,
        scenario: Scenario,
        turn_index: int,
        turn: TurnSpec,
        response: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> List[Issue]:
        expectation = turn.expectation
        issues: List[Issue] = []
        answer = str(response.get("answer") or "")
        trace = (response.get("tracing") or {}).get("trace") or []
        components = response.get("components") or []
        intent = str(response.get("intent") or "").strip()
        route_mode = str(response.get("routeMode") or response.get("route_mode") or "").strip()
        active_subflow = str(response.get("activeSubflow") or response.get("active_subflow") or "").strip()

        def add(rule: str, message: str, severity: str = "error") -> None:
            issues.append(
                Issue(
                    severity=severity,
                    scenario_id=scenario.scenario_id,
                    turn_index=turn_index,
                    rule=rule,
                    message=message,
                    user_text=turn.user_text,
                    answer=answer,
                    trace=list(trace),
                )
            )

        if not answer.strip():
            add("non_empty_answer", "respuesta vacia")

        if expectation.expected_intent and intent != expectation.expected_intent:
            add("expected_intent", f"intent esperado={expectation.expected_intent} obtenido={intent or 'EMPTY'}")

        if expectation.expected_route_mode and route_mode != expectation.expected_route_mode:
            add("expected_route_mode", f"route_mode esperado={expectation.expected_route_mode} obtenido={route_mode or 'EMPTY'}")

        if expectation.expected_subflow and active_subflow != expectation.expected_subflow:
            add("expected_subflow", f"active_subflow esperado={expectation.expected_subflow} obtenido={active_subflow or 'EMPTY'}")

        if expectation.min_components is not None and len(components) < expectation.min_components:
            add("min_components", f"components esperados >= {expectation.min_components}, obtenidos={len(components)}")

        if expectation.max_components is not None and len(components) > expectation.max_components:
            add("max_components", f"components esperados <= {expectation.max_components}, obtenidos={len(components)}")

        for node in expectation.trace_contains:
            if node not in trace:
                add("trace_contains", f"falta nodo esperado en trace: {node}")

        for node in expectation.trace_excludes:
            if node in trace:
                add("trace_excludes", f"trace contiene nodo prohibido: {node}")

        answer_lower = _lower_text(answer)
        if expectation.answer_contains_any:
            if not any(token.lower() in answer_lower for token in expectation.answer_contains_any):
                add("answer_contains_any", f"la respuesta no contiene ninguno de: {', '.join(expectation.answer_contains_any)}")

        for token in expectation.answer_contains_all:
            if token.lower() not in answer_lower:
                add("answer_contains_all", f"la respuesta no contiene el fragmento requerido: {token}")

        for token in expectation.answer_excludes:
            if token.lower() in answer_lower:
                add("answer_excludes", f"la respuesta contiene texto prohibido: {token}")

        baseline_checks = [
            _forbidden_show_prompt_when_cards,
            _no_te_muestro_without_cards,
            _empty_results_should_not_ask_for_name,
        ]
        for check in baseline_checks + expectation.custom_checks:
            for message in check(response, history):
                add(check.__name__, message)

        return issues


def _print_report(report: Dict[str, Any]) -> None:
    scenarios = report["scenarios"]
    all_issues = [issue for scenario in scenarios for issue in scenario["issues"]]

    print()
    print("=" * 96)
    print("REALTOR V3 INTENSIVE REGRESSION BATTERY")
    print("=" * 96)
    print(f"API: {report['base_url']}")
    print(f"Client ID: {report['client_id']}")
    print(f"Scenarios: {len(scenarios)}")
    print(f"Issues: {len(all_issues)}")
    print()

    for scenario in scenarios:
        marker = "OK" if not scenario["issues"] else f"FAIL ({len(scenario['issues'])})"
        tags = ", ".join(scenario.get("tags") or [])
        print(f"[{marker}] {scenario['scenario_id']}: {scenario['description']}")
        if tags:
            print(f"  tags={tags}")
        for response in scenario["responses"]:
            print(f"  - user: {response['user_text']}")
            print(
                "    "
                f"intent={response['intent']} route_mode={response['route_mode']} "
                f"subflow={response['active_subflow']} components={response['components_count']}"
            )
            print(f"    answer={response['answer']}")
        for issue in scenario["issues"]:
            print(
                f"    ISSUE turn={issue['turn_index']} rule={issue['rule']} "
                f"severity={issue['severity']}: {issue['message']}"
            )
        print()

    if all_issues:
        print("Resumen de reglas rotas:")
        counts: Dict[str, int] = {}
        for issue in all_issues:
            counts[issue["rule"]] = counts.get(issue["rule"], 0) + 1
        for rule, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"  - {rule}: {count}")
    else:
        print("No se detectaron incongruencias en esta corrida.")


def _select_scenarios(requested: Optional[str]) -> List[Scenario]:
    if not requested:
        return SCENARIOS
    requested_ids = {item.strip() for item in requested.split(",") if item.strip()}
    selected = [scenario for scenario in SCENARIOS if scenario.scenario_id in requested_ids]
    if not selected:
        valid = ", ".join(s.scenario_id for s in SCENARIOS)
        raise SystemExit(f"Scenario invalido. Usa uno de: {valid}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Bateria intensiva de regresion realtor v3")
    parser.add_argument("--url", default=INFERENCE_V3_URL, help=f"Base URL API v3 (default: {INFERENCE_V3_URL})")
    parser.add_argument("--client-id", default=CLIENT_ID, help=f"Client ID (default: {CLIENT_ID})")
    parser.add_argument("--scenario", default=None, help="Scenario id o lista separada por comas")
    parser.add_argument("--json-out", default=None, help="Ruta para guardar reporte JSON")
    parser.add_argument("--request-timeout", type=int, default=45, help="Timeout por request en segundos")
    args = parser.parse_args()

    selected_scenarios = _select_scenarios(args.scenario)
    runner = RealtorV3Battery(base_url=args.url, client_id=args.client_id, request_timeout=args.request_timeout)
    runner.check_health()
    results = [runner.run_scenario(scenario) for scenario in selected_scenarios]
    report = {
        "base_url": args.url.rstrip("/"),
        "client_id": args.client_id,
        "scenarios": results,
    }
    _print_report(report)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print()
        print(f"Reporte JSON guardado en: {args.json_out}")

    total_issues = sum(len(item["issues"]) for item in results)
    raise SystemExit(1 if total_issues else 0)


if __name__ == "__main__":
    main()
