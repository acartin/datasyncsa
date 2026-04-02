"""Fast-path node for conversational memory questions.

Business facts come from structured state.
Casual self-referential facts should fall back to transcript recall only.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any

from services.ai_runtime.domain.contracts import ConversationEntity
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


_MEMORY_QUERY_PATTERNS: dict[str, tuple[str, ...]] = {
    "nombre": (
        r"\bcomo me llamo\b",
        r"\bcual es mi nombre\b",
        r"\brecord[aá]s?(?: .*?)?(?:mi nombre|como me llamo)\b",
        r"\brecuerdas?(?: .*?)?(?:mi nombre|como me llamo)\b",
        r"\bte acord[aá]s?(?: .*?)?(?:mi nombre|como me llamo)\b",
    ),
    "edad": (
        r"\bque edad tengo\b",
        r"\bcuantos anos tengo\b",
        r"\brecuerdas?(?: .*?)?mi edad\b",
        r"\brecord[aá]s?(?: .*?)?mi edad\b",
    ),
    "presupuesto": (
        r"\bcual era mi presupuesto\b",
        r"\bque presupuesto te dije\b",
        r"\brecord[aá]s?(?: .*?)?mi presupuesto\b",
        r"\brecuerdas?(?: .*?)?mi presupuesto\b",
    ),
    "email": (
        r"\bcual es mi correo\b",
        r"\bcual es mi email\b",
        r"\brecord[aá]s?(?: .*?)?(?:mi correo|mi email)\b",
        r"\brecuerdas?(?: .*?)?(?:mi correo|mi email)\b",
    ),
    "telefono": (
        r"\bcual es mi telefono\b",
        r"\bcual es mi numero\b",
        r"\brecord[aá]s?(?: .*?)?(?:mi telefono|mi numero)\b",
        r"\brecuerdas?(?: .*?)?(?:mi telefono|mi numero)\b",
    ),
}

_PHONE_SCAN_PATTERN = re.compile(r"(?:\+?\d[\d\s-]{6,}\d)")
_EMAIL_SCAN_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", flags=re.IGNORECASE)


def _normalize_text(value: str) -> str:
    raw = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in raw if not unicodedata.combining(char)).lower().strip()


def _detect_memory_key(message: str) -> str | None:
    normalized = _normalize_text(message)
    if not normalized:
        return None
    for key, patterns in _MEMORY_QUERY_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            return key
    return None


def _normalize_entity_key(value: str) -> str:
    cleaned = re.sub(r"\s+", "_", (value or "").strip().lower())
    return re.sub(r"[^a-z0-9_]+", "", cleaned)


def _format_money(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    quantized = amount.quantize(Decimal("1"))
    return f"{quantized:,.0f}".replace(",", ".")


def _find_entity(state: BaseGraphState, *keys: str) -> tuple[Any, str | None]:
    wanted = {_normalize_entity_key(key) for key in keys}
    for entity in reversed(state.memory.entities):
        entity_model = entity if isinstance(entity, ConversationEntity) else ConversationEntity.model_validate(entity)
        if _normalize_entity_key(entity_model.key) in wanted:
            return entity_model.value, "memory.entities"
    return None, None


def _scan_messages_for_value(state: BaseGraphState, key: str) -> tuple[Any, str | None]:
    for message in reversed(state.messages):
        if message.role != "user":
            continue
        text = message.content.strip()
        normalized = _normalize_text(text)
        if key == "nombre":
            match = re.search(
                r"\b(?:me llamo|mi nombre es|soy)\s+([a-záéíóúñ][a-záéíóúñ' -]{0,40}?)(?=$|[,.!?]|\s+y\s|\s+pero\s|\s+porque\s)",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).strip().title(), "messages"
        if key == "edad":
            match = re.search(r"\btengo\s+(\d{1,3})\s+a(?:ñ|n)os\b", normalized)
            if match:
                return int(match.group(1)), "messages"
        if key == "email":
            match = _EMAIL_SCAN_PATTERN.search(text)
            if match:
                return match.group(0), "messages"
        if key == "telefono":
            match = _PHONE_SCAN_PATTERN.search(text)
            if match:
                return match.group(0), "messages"
        if key == "presupuesto":
            match = re.search(
                r"\b(?:presupuesto|maximo|maximo de|cuento con|puedo pagar)\D{0,20}(\d[\d.,]*)",
                normalized,
            )
            if match:
                return match.group(1), "messages"
    return None, None


def _build_answer(key: str, value: Any | None) -> str:
    if key == "nombre":
        return (
            f"Sí, me dijiste que te llamás {value}."
            if value
            else "Todavía no tengo tu nombre guardado. Si querés, decime cómo te llamás y lo tomo en cuenta."
        )
    if key == "edad":
        return (
            f"Sí, me comentaste que tenés {value} años."
            if value not in (None, "")
            else "No tengo tu edad guardada todavía."
        )
    if key == "presupuesto":
        return (
            f"Sí, me dijiste un presupuesto aproximado de {_format_money(value)}."
            if value not in (None, "")
            else "No tengo tu presupuesto guardado todavía."
        )
    if key == "email":
        return (
            f"Sí, tengo registrado este correo: {value}."
            if value
            else "Todavía no tengo un correo tuyo guardado."
        )
    if key == "telefono":
        return (
            f"Sí, tengo registrado este número: {value}."
            if value
            else "Todavía no tengo un teléfono tuyo guardado."
        )
    return "Todavía no tengo ese dato guardado."


async def memory_lookup(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    """Answer simple self-referential memory questions from structured state before routing elsewhere."""

    del deps
    graph_state = BaseGraphState.model_validate(state)
    latest_message = graph_state.messages[-1].content
    analysis = graph_state.turn_analysis
    lookup_key = analysis.memory_lookup_key if analysis and analysis.memory_lookup_key else _detect_memory_key(latest_message)
    if not lookup_key:
        return {}

    source: str | None = None
    value: Any | None = None
    canonical_fields = graph_state.lead_advisor.lead_extracted
    if lookup_key == "nombre" and canonical_fields.nombre:
        value, source = canonical_fields.nombre, "lead_advisor.lead_extracted"
    elif lookup_key == "presupuesto" and canonical_fields.presupuesto is not None:
        value, source = canonical_fields.presupuesto, "lead_advisor.lead_extracted"
    elif lookup_key == "email" and canonical_fields.email:
        value, source = canonical_fields.email, "lead_advisor.lead_extracted"
    elif lookup_key == "telefono" and canonical_fields.telefono:
        value, source = canonical_fields.telefono, "lead_advisor.lead_extracted"

    if value in (None, "") and lookup_key != "edad":
        entity_keys = {
            "nombre": ("nombre",),
            "presupuesto": ("presupuesto", "presupuesto_maximo"),
            "email": ("email", "correo"),
            "telefono": ("telefono", "telefono_principal", "numero"),
        }
        value, source = _find_entity(graph_state, *entity_keys.get(lookup_key, (lookup_key,)))

    if value in (None, ""):
        value, source = _scan_messages_for_value(graph_state, lookup_key)

    answer = _build_answer(lookup_key, value)
    memory_state = graph_state.memory.model_copy(
        update={
            "last_lookup": {
                "handled": True,
                "key": lookup_key,
                "answer": answer,
                "source": source,
            }
        }
    )
    return {
        "memory": memory_state.model_dump(mode="json"),
        "final_response": answer,
        "messages": [
            *[message.model_dump(mode="json") for message in graph_state.messages],
            {"role": "assistant", "content": answer},
        ],
    }
