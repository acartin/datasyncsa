from __future__ import annotations

from typing import Any, Dict, List


class RealtorContextResolver:
    def resolve(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tool_plan = state.get("tool_plan") or []
        plan = tool_plan[0] if tool_plan else {}
        user_goal = str(plan.get("user_goal") or "").strip().lower()

        if user_goal == "search_state":
            return self._resolve_search_state(state, plan)
        if user_goal == "capture_reply":
            return self._resolve_capture_reply(state, plan)
        return self._clarify_result(
            state,
            "Puedo ayudarte a revisar la búsqueda actual, pero necesito un poco más de precisión.",
        )

    def _resolve_search_state(self, state: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        active_search_state = state.get("active_search_state") or {}
        filters = active_search_state.get("filters") if isinstance(active_search_state.get("filters"), dict) else {}
        summary = str(active_search_state.get("search_summary") or "").strip()
        requested_fields = plan.get("requested_fields") if isinstance(plan.get("requested_fields"), list) else []

        if not filters and not summary:
            return self._clarify_result(
                state,
                "No tengo una búsqueda activa lo bastante clara en este momento para resumírtela.",
            )

        wants_filters = "filters" in requested_fields
        wants_summary = not requested_fields or "search_summary" in requested_fields

        parts: List[str] = []
        if wants_summary:
            summary_text = self._build_search_summary(filters, summary)
            if summary_text:
                parts.append(summary_text)

        if wants_filters:
            filters_text = self._build_filters_summary(filters)
            if filters_text:
                parts.append(filters_text)

        answer = " ".join(part for part in parts if part).strip()
        if not answer:
            answer = self._build_search_summary(filters, summary) or self._build_filters_summary(filters)
        if not answer:
            return self._clarify_result(
                state,
                "No tengo suficientes datos estructurados para explicarte la búsqueda actual con precisión.",
            )

        return self._answer_result(state, answer)

    def _resolve_capture_reply(self, state: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        capture = plan.get("capture_reply") if isinstance(plan.get("capture_reply"), dict) else {}
        field = str(capture.get("field") or "").strip().lower()
        value = capture.get("value")
        if not field or value in (None, ""):
            return self._clarify_result(
                state,
                "Entendí que me estabas dando un dato, pero no pude identificar con precisión cuál.",
            )

        if field == "budget":
            answer = f"Perfecto, tomo ${self._format_price(value)} como tu presupuesto máximo."
        elif field == "name":
            answer = f"Mucho gusto, {value}."
        elif field == "email":
            answer = f"Perfecto, tomo {value} como tu correo de contacto."
        elif field == "phone":
            answer = f"Perfecto, tomo {value} como tu número de contacto."
        elif field == "urgency":
            answer = f"Entendido, tomo eso como tu nivel de urgencia: {value}."
        else:
            answer = f"Perfecto, tomo ese dato como referencia: {value}."

        return self._answer_result(state, answer)

    @staticmethod
    def _build_search_summary(filters: Dict[str, Any], summary: str) -> str:
        if summary and summary.lower() not in {"propiedades", "propiedades disponibles"}:
            return f"Estás buscando {summary}."

        parts: List[str] = []
        property_type = filters.get("property_type")
        desired_location = filters.get("desired_location")
        bedrooms_min = filters.get("bedrooms_min")
        bathrooms_min = filters.get("bathrooms_min")
        garage_min = filters.get("garage_min")
        price_max = filters.get("price_max")
        listing_intent = filters.get("listing_intent")

        parts.append(str(property_type or "propiedades").strip())
        if desired_location:
            parts.append(f"en {desired_location}")
        if bedrooms_min not in (None, ""):
            parts.append(f"con al menos {bedrooms_min} habitaciones")
        if bathrooms_min not in (None, ""):
            parts.append(f"con al menos {bathrooms_min} baños")
        if garage_min not in (None, ""):
            parts.append(f"con cochera para {garage_min} carros")
        if price_max not in (None, ""):
            parts.append(f"con presupuesto máximo de ${RealtorContextResolver._format_price(price_max)}")
        if listing_intent == "rent":
            parts.append("en renta")
        elif listing_intent == "buy":
            parts.append("para compra")

        joined = " ".join(str(item).strip() for item in parts if str(item).strip()).strip()
        if not joined:
            return ""
        return f"Estás buscando {joined}."

    @staticmethod
    def _build_filters_summary(filters: Dict[str, Any]) -> str:
        items: List[str] = []
        if filters.get("desired_location"):
            items.append(f"ubicación en {filters['desired_location']}")
        if filters.get("property_type"):
            items.append(f"tipo de propiedad {filters['property_type']}")
        if filters.get("bedrooms_min") not in (None, ""):
            items.append(f"mínimo de {filters['bedrooms_min']} habitaciones")
        if filters.get("bathrooms_min") not in (None, ""):
            items.append(f"mínimo de {filters['bathrooms_min']} baños")
        if filters.get("garage_min") not in (None, ""):
            items.append(f"mínimo de {filters['garage_min']} cocheras")
        if filters.get("price_max") not in (None, ""):
            items.append(f"presupuesto máximo de ${RealtorContextResolver._format_price(filters['price_max'])}")
        if filters.get("listing_intent") == "rent":
            items.append("intención de renta")
        elif filters.get("listing_intent") == "buy":
            items.append("intención de compra")

        if not items:
            return ""
        return "Ahora mismo estoy usando estos filtros: " + ", ".join(items) + "."

    @staticmethod
    def _answer_result(state: Dict[str, Any], answer: str) -> Dict[str, Any]:
        return {
            "tool_outputs": [],
            "tool_results": [],
            "components": [],
            "grounded_answer": answer,
            "execution_facts": {
                "status": "results",
                "context_answer": answer,
            },
            "last_result_set": {
                "status": "results",
                "operation": "CONTEXT_ANSWER",
                "search_summary": (state.get("last_result_set") or {}).get("search_summary"),
                "filters": (state.get("active_search_state") or {}).get("filters") or {},
                "visible_count": 0,
                "total_matches": 0,
                "result_mode": "answer_only",
                "grounded_answer": answer,
            },
        }

    @staticmethod
    def _clarify_result(state: Dict[str, Any], clarification: str) -> Dict[str, Any]:
        return {
            "tool_outputs": [],
            "tool_results": [],
            "components": [],
            "grounded_answer": None,
            "execution_facts": {
                "status": "clarify",
                "pending_clarification": clarification,
            },
            "last_result_set": {
                "status": "clarify",
                "operation": "CONTEXT_ANSWER",
                "search_summary": (state.get("last_result_set") or {}).get("search_summary"),
                "filters": (state.get("active_search_state") or {}).get("filters") or {},
                "result_mode": "answer_only",
                "clarification": clarification,
            },
        }

    @staticmethod
    def _format_price(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{numeric:,.0f}"


realtor_context_resolver = RealtorContextResolver()
