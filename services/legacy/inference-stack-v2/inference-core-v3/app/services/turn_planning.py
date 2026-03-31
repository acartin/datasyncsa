from __future__ import annotations

from typing import Any, Dict, List

from app.services.llm_service import llm_service


_ROUTE_MODES = {"answer_only", "tool_required", "clarify", "handoff"}
_INTENTS = {
    "PROPERTY_SEARCH",
    "PROPERTY_INVENTORY",
    "PROPERTY_PRICE_RANGE",
    "RAG",
    "CLARIFICATION",
    "NONE",
}
_REALTOR_INTENTS = {"PROPERTY_SEARCH", "PROPERTY_INVENTORY", "PROPERTY_PRICE_RANGE"}
_SUBFLOWS = {"realtor_search", "generic_rag", "generic_answer", "workflow"}
_REALTOR_FILTER_KEYS = {
    "desired_location",
    "property_type",
    "bedrooms_min",
    "bathrooms_min",
    "garage_min",
    "price_min",
    "price_max",
    "listing_intent",
}
_SEARCH_TRANSITIONS = {"new_search", "refine_current", "ask_about_current_results"}
_SEARCH_RESET_ANCHOR_KEYS = {"desired_location", "listing_intent"}
_USER_GOALS = {
    "search",
    "inventory",
    "price_range",
    "reference_question",
    "search_state",
    "capture_reply",
    "rag",
    "workflow",
    "clarify",
}
_QUERY_SCOPES = {"new_query", "active_search", "shown_result", "document_knowledge"}
_CONTINUITY_MODES = {"replace", "refine", "reuse_current_set"}
_TARGET_ENTITIES = {"result_set", "single_shown_property", "search_state", "none"}
_REFERENCE_TARGETS = {"last", "first", "index", "single"}
_REFERENCE_FIELDS = {
    "bathrooms",
    "baños",
    "banos",
    "bedrooms",
    "habitaciones",
    "garage",
    "cochera",
    "price",
    "precio",
    "location",
    "ubicacion",
    "ubicación",
    "title",
    "titulo",
    "título",
    "image_url",
    "imagen",
    "foto",
    "all_known_fields",
}
_REQUESTED_FIELD_ALIASES = {
    **{key: value for key, value in {
        "bathrooms": "bathrooms",
        "baños": "bathrooms",
        "banos": "bathrooms",
        "bedrooms": "bedrooms",
        "habitaciones": "bedrooms",
        "garage": "garage",
        "cochera": "garage",
        "precio": "price",
        "price": "price",
        "ubicacion": "location",
        "ubicación": "location",
        "location": "location",
        "title": "title",
        "titulo": "title",
        "título": "title",
        "image_url": "image_url",
        "imagen": "image_url",
        "foto": "image_url",
        "count": "count",
        "cantidad": "count",
        "rango_precio": "price_range",
        "price_range": "price_range",
        "min_price": "min_price",
        "max_price": "max_price",
        "filters": "filters",
        "filtros": "filters",
        "search_summary": "search_summary",
        "resumen_busqueda": "search_summary",
        "all_known_fields": "all_known_fields",
        "all": "all_known_fields",
        "todo": "all_known_fields",
        "todos": "all_known_fields",
        "details": "all_known_fields",
        "detalles": "all_known_fields",
        "caracteristicas": "all_known_fields",
        "características": "all_known_fields",
    }.items()},
}
_CAPTURE_FIELD_ALIASES = {
    "name": "name",
    "nombre": "name",
    "email": "email",
    "correo": "email",
    "mail": "email",
    "phone": "phone",
    "telefono": "phone",
    "teléfono": "phone",
    "budget": "budget",
    "presupuesto": "budget",
    "urgency": "urgency",
    "urgencia": "urgency",
    "agent_contact_consent": "agent_contact_consent",
    "contacto_agente": "agent_contact_consent",
    "appointment_window": "appointment_window",
    "ventana_cita": "appointment_window",
    "free_preference": "free_preference",
    "preferencia": "free_preference",
}
_CAPTURE_TO_FILTER_KEY = {
    "budget": "price_max",
}


def history_excerpt(history: list[Dict[str, Any]], limit: int = 8) -> list[Dict[str, Any]]:
    excerpt = []
    for item in history[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role and content:
            excerpt.append({"role": role, "content": content})
    return excerpt


def _numeric_text_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    filtered = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    if not filtered:
        return None
    return filtered


class TurnRouter:
    async def route(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tenant_runtime = state.get("tenant_runtime") or {}
        prompts = tenant_runtime.get("prompts") or {}
        prompt = prompts.get("route_turn")
        payload = {
            "vertical_slug": state.get("vertical_slug") or "generic",
            "query_text": state.get("query_text") or "",
            "history_excerpt": history_excerpt(state.get("history") or []),
            "conversation_memory": state.get("conversation_memory") or {"common": {}, "vertical": {}},
            "active_search_state": state.get("active_search_state") or {},
            "last_result_set": state.get("last_result_set") or {},
            "available_tools": sorted((tenant_runtime.get("tool_registry") or {}).keys()),
        }
        try:
            raw = await llm_service.generate_json(
                system_instruction=prompt,
                payload=payload,
                temperature=0.1,
                max_output_tokens=600,
            )
            return self._normalize(raw, state)
        except Exception:
            return self._fallback(state)

    def _normalize(self, raw: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        vertical_slug = str(state.get("vertical_slug") or "generic")
        route_mode = str(raw.get("route_mode") or "answer_only").strip().lower()
        if route_mode not in _ROUTE_MODES:
            route_mode = "answer_only"

        intent = str(raw.get("intent") or "NONE").strip().upper()
        if intent not in _INTENTS:
            intent = "NONE"

        active_subflow = str(raw.get("active_subflow") or "generic_answer").strip()
        if active_subflow not in _SUBFLOWS:
            active_subflow = self._fallback(state)["active_subflow"]

        if active_subflow == "generic_rag":
            route_mode = "tool_required"
            if intent == "NONE":
                intent = "RAG"
        if active_subflow == "realtor_search" and intent not in _REALTOR_INTENTS:
            intent = "PROPERTY_SEARCH"
        if active_subflow == "workflow":
            route_mode = "handoff"

        selected_tools = raw.get("selected_tools")
        if not isinstance(selected_tools, list):
            selected_tools = self._derive_tools(active_subflow, intent)
        else:
            selected_tools = [str(item).strip() for item in selected_tools if str(item).strip()]
            if not selected_tools:
                selected_tools = self._derive_tools(active_subflow, intent)

        requires_tools = route_mode == "tool_required" or active_subflow in {"realtor_search", "generic_rag"}
        if active_subflow == "workflow":
            requires_tools = True
        return {
            "route_mode": route_mode,
            "intent": intent,
            "active_subflow": active_subflow,
            "active_vertical_subgraph": self._subgraph_for(active_subflow, vertical_slug),
            "selected_tools": selected_tools,
            "requires_tools": requires_tools,
            "reasoning": str(raw.get("reasoning") or "").strip() or None,
        }

    def _fallback(self, state: Dict[str, Any]) -> Dict[str, Any]:
        vertical_slug = str(state.get("vertical_slug") or "generic")
        query_text = str(state.get("query_text") or "").strip()
        if self._is_property_vertical(vertical_slug) and query_text:
            return {
                "route_mode": "tool_required",
                "intent": "PROPERTY_SEARCH",
                "active_subflow": "realtor_search",
                "active_vertical_subgraph": "realtor_subgraph",
                "selected_tools": ["realtor_sql_search"],
                "requires_tools": True,
                "reasoning": "fallback_realtor_search",
            }
        return {
            "route_mode": "answer_only",
            "intent": "NONE",
            "active_subflow": "generic_answer",
            "active_vertical_subgraph": "generic_subgraph",
            "selected_tools": [],
            "requires_tools": False,
            "reasoning": "fallback_generic_answer",
        }

    @staticmethod
    def _derive_tools(active_subflow: str, intent: str) -> list[str]:
        if active_subflow == "realtor_search":
            if intent == "PROPERTY_INVENTORY":
                return ["realtor_inventory"]
            if intent == "PROPERTY_PRICE_RANGE":
                return ["realtor_price_range"]
            return ["realtor_sql_search"]
        if active_subflow == "generic_rag":
            return ["semantic_retrieval"]
        if active_subflow == "workflow":
            return ["workflow_handoff"]
        return []

    @staticmethod
    def _subgraph_for(active_subflow: str, vertical_slug: str) -> str:
        if active_subflow == "workflow":
            return "workflow_subgraph"
        if active_subflow == "realtor_search" and TurnRouter._is_property_vertical(vertical_slug):
            return "realtor_subgraph"
        return "generic_subgraph"

    @staticmethod
    def _is_property_vertical(vertical_slug: str) -> bool:
        normalized = (vertical_slug or "").strip().lower().replace("_", "-")
        return normalized in {"realtor", "real-estate", "realestate", "property"}


class RealtorTurnPlanner:
    async def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tenant_runtime = state.get("tenant_runtime") or {}
        prompts = tenant_runtime.get("prompts") or {}
        prompt = prompts.get("realtor_turn_planner")
        payload = {
            "user_text": state.get("query_text") or "",
            "route_mode": state.get("route_mode") or "tool_required",
            "intent": state.get("intent") or "PROPERTY_SEARCH",
            "active_search_state": state.get("active_search_state") or {},
            "conversation_memory": state.get("conversation_memory") or {"common": {}, "vertical": {}},
            "history_excerpt": history_excerpt(state.get("history") or []),
            "last_result_set": state.get("last_result_set") or {},
        }
        try:
            raw = await llm_service.generate_json(
                system_instruction=prompt,
                payload=payload,
                temperature=0.1,
                max_output_tokens=1000,
            )
            return self._normalize(raw, state)
        except Exception:
            return self._fallback(state)

    def _normalize(self, raw: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        active_search_state = state.get("active_search_state") or {}
        active_filters = active_search_state.get("filters") if isinstance(active_search_state.get("filters"), dict) else {}
        incoming_filters = self._normalize_filters(payload.get("filters"))
        turn_filters = self._normalize_filters(payload.get("turn_filters"))
        clear_filters = self._normalize_clear_filters(payload.get("clear_filters"))
        search_text = payload.get("search_text")
        if isinstance(search_text, list):
            normalized_search_text = [str(item).strip() for item in search_text if str(item).strip()]
        elif isinstance(search_text, str) and search_text.strip():
            normalized_search_text = [search_text.strip()]
        else:
            normalized_search_text = []

        search_transition = str(payload.get("search_transition") or "").strip().lower()
        if search_transition not in _SEARCH_TRANSITIONS:
            search_transition = "refine_current" if active_filters else "new_search"

        if not turn_filters and incoming_filters:
            turn_filters = dict(incoming_filters)

        reference_request = self._normalize_reference_request(payload.get("reference_request"))
        capture_reply = self._normalize_capture_reply(payload, state)
        continuation_requested = bool(payload.get("continuation_requested"))
        user_goal = self._normalize_user_goal(payload, state, capture_reply)
        query_scope = self._normalize_query_scope(
            payload=payload,
            state=state,
            active_filters=active_filters,
            search_transition=search_transition,
            user_goal=user_goal,
            reference_request=reference_request,
            capture_reply=capture_reply,
        )
        continuity_mode = self._normalize_continuity_mode(
            payload=payload,
            search_transition=search_transition,
            user_goal=user_goal,
            query_scope=query_scope,
            active_filters=active_filters,
            continuation_requested=continuation_requested,
            capture_reply=capture_reply,
        )
        target_entity = self._normalize_target_entity(
            payload=payload,
            user_goal=user_goal,
            query_scope=query_scope,
            reference_request=reference_request,
        )
        requested_fields = self._normalize_requested_fields(
            payload=payload,
            user_goal=user_goal,
            reference_request=reference_request,
        )
        requested_field = requested_fields[0] if requested_fields else None

        if capture_reply and capture_reply.get("field") == "budget":
            budget_filter = self._capture_filter_value(capture_reply)
            if budget_filter is not None:
                if "price_max" not in turn_filters:
                    turn_filters["price_max"] = budget_filter
                if "price_max" not in incoming_filters:
                    incoming_filters["price_max"] = budget_filter

        if user_goal in {"inventory", "price_range"} and query_scope == "shown_result":
            query_scope = "active_search"
            continuity_mode = "reuse_current_set"
            target_entity = "result_set"
            reference_request = {}

        if query_scope == "shown_result" and target_entity == "single_shown_property":
            search_transition = "ask_about_current_results"
            if not reference_request:
                reference_request = {
                    "mode": "shown_result",
                    "target": str(payload.get("reference_target") or "last").strip().lower() or "last",
                    "index": payload.get("reference_index"),
                    "field": requested_field,
                    "fields": requested_fields,
                }
                reference_request = self._normalize_reference_request(reference_request)
        else:
            reference_request = {}
            if continuity_mode == "refine":
                search_transition = "refine_current"
            elif continuity_mode == "reuse_current_set":
                search_transition = "refine_current"
            else:
                search_transition = "new_search"

        intent = str(payload.get("intent") or state.get("intent") or "PROPERTY_SEARCH").strip().upper()
        if intent not in _INTENTS:
            intent = "PROPERTY_SEARCH"

        operation = str(payload.get("operation") or "search").strip().lower()
        if operation not in {"search", "inventory", "price_range", "clarify", "answer"}:
            operation = "search"

        result_mode = str(payload.get("result_mode") or "show_cards").strip().lower()
        if result_mode not in {"show_cards", "count_only", "stats_only", "clarify", "answer_only"}:
            result_mode = "show_cards"

        if user_goal == "inventory" or intent == "PROPERTY_INVENTORY":
            intent = "PROPERTY_INVENTORY"
            operation = "inventory"
            result_mode = "count_only"
            requested_field = requested_field or "count"
        elif user_goal == "price_range" or intent == "PROPERTY_PRICE_RANGE":
            intent = "PROPERTY_PRICE_RANGE"
            operation = "price_range"
            result_mode = "stats_only"
            requested_field = requested_field or "price_range"
        elif user_goal == "clarify" or intent == "CLARIFICATION":
            intent = "CLARIFICATION"
            operation = "clarify"
            result_mode = "clarify"
        elif user_goal == "search_state":
            intent = "PROPERTY_SEARCH"
            operation = "answer"
            result_mode = "answer_only"
        elif user_goal == "capture_reply":
            if capture_reply.get("field") == "budget":
                intent = "PROPERTY_SEARCH"
                operation = "search"
                result_mode = "show_cards"
                if query_scope == "new_query" and active_filters:
                    query_scope = "active_search"
                if continuity_mode == "replace" and active_filters:
                    continuity_mode = "refine"
            else:
                intent = "PROPERTY_SEARCH"
                operation = "answer"
                result_mode = "answer_only"
        elif query_scope == "shown_result" and target_entity == "single_shown_property":
            user_goal = "reference_question"
            intent = "PROPERTY_SEARCH"
            operation = "answer"
            result_mode = "answer_only"
        else:
            intent = "PROPERTY_SEARCH"
            operation = "search"
            result_mode = "show_cards"

        effective_filters = self._apply_filter_transition(
            active_filters=active_filters,
            incoming_filters=incoming_filters,
            clear_filters=clear_filters,
            search_transition=search_transition,
        )

        return {
            "intent": intent,
            "user_goal": user_goal,
            "query_scope": query_scope,
            "continuity_mode": continuity_mode,
            "target_entity": target_entity,
            "requested_field": requested_field,
            "requested_fields": requested_fields,
            "capture_reply": capture_reply,
            "operation": operation,
            "result_mode": result_mode,
            "search_transition": search_transition,
            "continuation_requested": continuation_requested,
            "clear_filters": clear_filters,
            "reference_request": reference_request,
            "filters": effective_filters,
            "turn_filters": turn_filters,
            "search_text": normalized_search_text,
            "sort_by": str(payload.get("sort_by") or "relevant").strip().lower() or "relevant",
            "search_summary": str(payload.get("search_summary") or "").strip() or None,
            "clarification": str(payload.get("clarification") or "").strip() or None,
            "reasoning": str(payload.get("reasoning") or "").strip() or None,
        }

    def _fallback(self, state: Dict[str, Any]) -> Dict[str, Any]:
        active_search_state = state.get("active_search_state") or {}
        active_filters = active_search_state.get("filters") if isinstance(active_search_state.get("filters"), dict) else {}
        return {
            "intent": state.get("intent") or "PROPERTY_SEARCH",
            "user_goal": "search",
            "query_scope": "active_search" if active_filters else "new_query",
            "continuity_mode": "refine" if active_filters else "replace",
            "target_entity": "result_set",
            "requested_field": None,
            "requested_fields": [],
            "capture_reply": {},
            "operation": "search",
            "result_mode": "show_cards",
            "search_transition": "refine_current" if active_filters else "new_search",
            "continuation_requested": False,
            "clear_filters": [],
            "reference_request": {},
            "filters": dict(active_filters),
            "turn_filters": {},
            "search_text": [str(state.get("query_text") or "").strip()] if state.get("query_text") else [],
            "sort_by": "relevant",
            "search_summary": active_search_state.get("search_summary"),
            "clarification": None,
            "reasoning": "fallback_structured_realtor_plan",
        }

    @staticmethod
    def _normalize_filters(raw_filters: Any) -> Dict[str, Any]:
        filters = raw_filters if isinstance(raw_filters, dict) else {}
        normalized: Dict[str, Any] = {}
        for key, value in filters.items():
            if key not in _REALTOR_FILTER_KEYS or value is None:
                continue
            if isinstance(value, str):
                cleaned = value.strip()
                if not cleaned:
                    continue
                normalized[key] = cleaned
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _normalize_clear_filters(raw_clear_filters: Any) -> list[str]:
        if not isinstance(raw_clear_filters, list):
            return []
        normalized = []
        for item in raw_clear_filters:
            key = str(item).strip()
            if key in _REALTOR_FILTER_KEYS and key not in normalized:
                normalized.append(key)
        return normalized

    def _normalize_reference_request(self, raw_reference: Any) -> Dict[str, Any]:
        payload = raw_reference if isinstance(raw_reference, dict) else {}
        if not payload:
            return {}
        mode = str(payload.get("mode") or "").strip().lower()
        if mode != "shown_result":
            return {}
        target = str(payload.get("target") or "last").strip().lower()
        if target not in _REFERENCE_TARGETS:
            target = "last"
        index = payload.get("index")
        try:
            normalized_index = int(index) if index is not None else None
        except (TypeError, ValueError):
            normalized_index = None
        fields = self._normalize_requested_fields(
            payload={"requested_fields": payload.get("fields"), "requested_field": payload.get("field")},
            user_goal="reference_question",
            reference_request={},
        )
        field = fields[0] if fields else None
        return {
            "mode": "shown_result",
            "target": target,
            "index": normalized_index,
            "field": field or None,
            "fields": fields,
        }

    @staticmethod
    def _normalize_user_goal(payload: Dict[str, Any], state: Dict[str, Any], capture_reply: Dict[str, Any]) -> str:
        value = str(payload.get("user_goal") or "").strip().lower()
        if value in _USER_GOALS:
            return value
        if capture_reply:
            return "capture_reply"
        intent = str(payload.get("intent") or state.get("intent") or "").strip().upper()
        operation = str(payload.get("operation") or "").strip().lower()
        reference_request = payload.get("reference_request")
        if isinstance(reference_request, dict) and str(reference_request.get("mode") or "").strip().lower() == "shown_result":
            return "reference_question"
        if intent == "PROPERTY_INVENTORY" or operation == "inventory":
            return "inventory"
        if intent == "PROPERTY_PRICE_RANGE" or operation == "price_range":
            return "price_range"
        if intent == "CLARIFICATION" or operation == "clarify":
            return "clarify"
        if intent == "RAG":
            return "rag"
        if operation == "answer":
            return "search_state"
        return "search"

    @staticmethod
    def _normalize_query_scope(
        *,
        payload: Dict[str, Any],
        state: Dict[str, Any],
        active_filters: Dict[str, Any],
        search_transition: str,
        user_goal: str,
        reference_request: Dict[str, Any],
        capture_reply: Dict[str, Any],
    ) -> str:
        value = str(payload.get("query_scope") or "").strip().lower()
        if value in _QUERY_SCOPES:
            return value
        if reference_request:
            return "shown_result"
        if user_goal == "search_state":
            return "active_search"
        if user_goal == "capture_reply":
            return "active_search" if active_filters else "new_query"
        if search_transition == "ask_about_current_results":
            if user_goal in {"inventory", "price_range"}:
                return "active_search"
            return "shown_result"
        if user_goal in {"inventory", "price_range"} and active_filters:
            return "active_search"
        if search_transition == "refine_current":
            return "active_search"
        if user_goal == "rag":
            return "document_knowledge"
        return "new_query"

    @staticmethod
    def _normalize_continuity_mode(
        *,
        payload: Dict[str, Any],
        search_transition: str,
        user_goal: str,
        query_scope: str,
        active_filters: Dict[str, Any],
        continuation_requested: bool,
        capture_reply: Dict[str, Any],
    ) -> str:
        value = str(payload.get("continuity_mode") or "").strip().lower()
        if value in _CONTINUITY_MODES:
            return value
        if query_scope == "shown_result":
            return "reuse_current_set"
        if user_goal == "search_state":
            return "reuse_current_set"
        if user_goal == "capture_reply":
            if capture_reply.get("field") == "budget":
                return "refine" if active_filters else "replace"
            return "reuse_current_set"
        if search_transition == "ask_about_current_results":
            return "reuse_current_set"
        if continuation_requested and active_filters:
            if user_goal in {"inventory", "price_range"}:
                return "reuse_current_set"
            return "refine"
        if user_goal in {"inventory", "price_range"} and query_scope == "active_search":
            return "reuse_current_set"
        if search_transition == "refine_current":
            return "refine"
        return "replace"

    @staticmethod
    def _normalize_target_entity(
        *,
        payload: Dict[str, Any],
        user_goal: str,
        query_scope: str,
        reference_request: Dict[str, Any],
    ) -> str:
        value = str(payload.get("target_entity") or "").strip().lower()
        if value in _TARGET_ENTITIES:
            return value
        if reference_request or query_scope == "shown_result":
            return "single_shown_property"
        if user_goal == "search_state":
            return "search_state"
        if user_goal in {"search", "inventory", "price_range"} and query_scope in {"new_query", "active_search"}:
            return "result_set"
        return "none"

    @staticmethod
    def _normalize_requested_fields(
        *,
        payload: Dict[str, Any],
        user_goal: str,
        reference_request: Dict[str, Any],
    ) -> list[str]:
        raw_values: list[Any] = []
        explicit_list = payload.get("requested_fields")
        if isinstance(explicit_list, list):
            raw_values.extend(explicit_list)
        raw_value = payload.get("requested_field")
        if raw_value is not None:
            raw_values.append(raw_value)
        if not raw_values and reference_request:
            fields = reference_request.get("fields")
            if isinstance(fields, list):
                raw_values.extend(fields)
            elif reference_request.get("field") is not None:
                raw_values.append(reference_request.get("field"))

        normalized_values: list[str] = []
        for item in raw_values:
            normalized = _REQUESTED_FIELD_ALIASES.get(str(item or "").strip().lower())
            if normalized and normalized not in normalized_values:
                normalized_values.append(normalized)
        if normalized_values:
            return normalized_values
        if user_goal == "inventory":
            return ["count"]
        if user_goal == "price_range":
            return ["price_range"]
        return []

    def _normalize_capture_reply(self, payload: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        raw_capture = payload.get("capture_reply") if isinstance(payload.get("capture_reply"), dict) else {}
        field_raw = raw_capture.get("field")
        if field_raw is None:
            field_raw = payload.get("capture_reply_field")
        if field_raw is None and str(payload.get("user_goal") or "").strip().lower() == "capture_reply":
            field_raw = ((state.get("lead_progression_state") or {}).get("last_asked_field"))
        if field_raw is None:
            last_asked_field = str(((state.get("lead_progression_state") or {}).get("last_asked_field")) or "").strip().lower()
            if last_asked_field == "budget" and _numeric_text_value(state.get("query_text")) is not None:
                field_raw = "budget"
        normalized_field = _CAPTURE_FIELD_ALIASES.get(str(field_raw or "").strip().lower())
        if not normalized_field:
            return {}

        raw_value = raw_capture.get("value")
        if raw_value is None:
            raw_value = payload.get("capture_reply_value")
        if raw_value in (None, ""):
            raw_value = state.get("query_text")
        normalized_value = self._normalize_capture_value(normalized_field, raw_value)
        if normalized_value in (None, ""):
            return {}
        return {
            "field": normalized_field,
            "value": normalized_value,
        }

    @staticmethod
    def _normalize_capture_value(field: str, value: Any) -> Any:
        if value in (None, ""):
            return None
        if field == "budget":
            numeric = _numeric_text_value(value)
            if numeric is None:
                return str(value).strip()
            try:
                return int(float(numeric))
            except (TypeError, ValueError):
                return numeric
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _capture_filter_value(capture_reply: Dict[str, Any]) -> int | None:
        if capture_reply.get("field") != "budget":
            return None
        numeric = _numeric_text_value(capture_reply.get("value"))
        if numeric is None:
            return None
        try:
            return int(float(numeric))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _apply_filter_transition(
        *,
        active_filters: Dict[str, Any],
        incoming_filters: Dict[str, Any],
        clear_filters: list[str],
        search_transition: str,
    ) -> Dict[str, Any]:
        if search_transition == "new_search":
            base: Dict[str, Any] = {}
        else:
            base = dict(active_filters or {})

        for key in clear_filters:
            base.pop(key, None)
        for key, value in incoming_filters.items():
            base[key] = value
        return base


class RealtorFilterCarryoverGuard:
    def guard(
        self,
        *,
        plan: Dict[str, Any],
        decision: Dict[str, Any],
        active_filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return self._normalize(decision, plan, active_filters or {})

    @staticmethod
    def _normalize(raw: Dict[str, Any], plan: Dict[str, Any], active_filters: Dict[str, Any]) -> Dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        normalized = dict(plan)
        previous_filters = RealtorTurnPlanner._normalize_filters(active_filters)
        planned_filters = RealtorTurnPlanner._normalize_filters(plan.get("filters"))
        turn_filters = RealtorTurnPlanner._normalize_filters(plan.get("turn_filters"))
        clear_filters = RealtorTurnPlanner._normalize_clear_filters(plan.get("clear_filters"))
        effective_query_scope = str(payload.get("effective_query_scope") or plan.get("query_scope") or "new_query").strip().lower()
        if effective_query_scope not in _QUERY_SCOPES:
            effective_query_scope = str(plan.get("query_scope") or "new_query").strip().lower() or "new_query"
        effective_continuity_mode = str(payload.get("effective_continuity_mode") or plan.get("continuity_mode") or "replace").strip().lower()
        if effective_continuity_mode not in _CONTINUITY_MODES:
            effective_continuity_mode = str(plan.get("continuity_mode") or "replace").strip().lower() or "replace"
        effective_target_entity = str(payload.get("effective_target_entity") or plan.get("target_entity") or "none").strip().lower()
        if effective_target_entity not in _TARGET_ENTITIES:
            effective_target_entity = str(plan.get("target_entity") or "none").strip().lower() or "none"

        filter_universe: Dict[str, bool] = {}
        for source in (previous_filters, planned_filters, turn_filters):
            for key in source.keys():
                if key in _REALTOR_FILTER_KEYS:
                    filter_universe[key] = True

        filter_keep_map = payload.get("filter_keep_map")
        if isinstance(filter_keep_map, dict):
            normalized_keep_map = {
                key: bool(filter_keep_map.get(key))
                for key in filter_universe.keys()
            }
        else:
            retained_filter_keys = payload.get("retained_filter_keys")
            if isinstance(retained_filter_keys, list):
                retained = {
                    str(item).strip()
                    for item in retained_filter_keys
                    if str(item).strip() in filter_universe
                }
                normalized_keep_map = {key: key in retained for key in filter_universe.keys()}
            else:
                if effective_continuity_mode == "replace":
                    seed = turn_filters or planned_filters
                    normalized_keep_map = {key: key in seed for key in filter_universe.keys()}
                else:
                    normalized_keep_map = {key: True for key in filter_universe.keys()}

        continuation_requested = bool(plan.get("continuation_requested"))
        prior_only_keys = {
            key
            for key in previous_filters.keys()
            if key not in turn_filters
        }
        if (
            not continuation_requested
            and effective_query_scope != "shown_result"
            and effective_continuity_mode != "reuse_current_set"
            and set(turn_filters.keys()).intersection(_SEARCH_RESET_ANCHOR_KEYS)
            and prior_only_keys
        ):
            effective_continuity_mode = "replace"
            for key in prior_only_keys:
                normalized_keep_map[key] = False

        if effective_query_scope == "shown_result" and effective_target_entity == "single_shown_property":
            final_filters = dict(previous_filters or planned_filters)
        else:
            if effective_continuity_mode == "replace":
                candidate_filters: Dict[str, Any] = {}
            else:
                candidate_filters = dict(previous_filters)

            for key in clear_filters:
                candidate_filters.pop(key, None)

            source_turn_filters = turn_filters or (planned_filters if effective_continuity_mode == "replace" else {})
            for key, value in source_turn_filters.items():
                candidate_filters[key] = value

            final_filters = {
                key: value
                for key, value in candidate_filters.items()
                if normalized_keep_map.get(
                    key,
                    False if effective_continuity_mode == "replace" else True,
                )
            }

            if effective_continuity_mode == "replace" and source_turn_filters:
                final_filters = {
                    key: value
                    for key, value in final_filters.items()
                    if key in source_turn_filters
                }

        normalized["filters"] = final_filters
        normalized["turn_filters"] = turn_filters
        normalized["continuation_requested"] = continuation_requested
        normalized["query_scope"] = effective_query_scope
        normalized["continuity_mode"] = effective_continuity_mode
        normalized["target_entity"] = effective_target_entity
        if effective_query_scope == "shown_result" and effective_target_entity == "single_shown_property":
            normalized["search_transition"] = "ask_about_current_results"
        elif effective_continuity_mode == "refine":
            normalized["search_transition"] = "refine_current"
        elif effective_continuity_mode == "reuse_current_set":
            normalized["search_transition"] = "refine_current"
        else:
            normalized["search_transition"] = "new_search"
        reasoning = str(plan.get("reasoning") or "").strip()
        guard_reasoning = str(payload.get("reasoning") or "").strip()
        if (
            final_filters != planned_filters
            or effective_query_scope != str(plan.get("query_scope") or "").strip().lower()
            or effective_continuity_mode != str(plan.get("continuity_mode") or "").strip().lower()
            or effective_target_entity != str(plan.get("target_entity") or "").strip().lower()
        ):
            normalized["search_summary"] = None
        if guard_reasoning:
            normalized["reasoning"] = f"{reasoning} | carryover_guard:{guard_reasoning}".strip(" |")
        return normalized


class RealtorSearchTransitionJudge:
    async def judge(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tenant_runtime = state.get("tenant_runtime") or {}
        prompts = tenant_runtime.get("prompts") or {}
        prompt = prompts.get("realtor_search_transition_judge")
        tool_plan = state.get("tool_plan") or []
        plan = dict(tool_plan[0]) if tool_plan else {}
        if not prompt or not plan:
            return {
                "effective_query_scope": str(plan.get("query_scope") or "new_query").strip().lower() or "new_query",
                "effective_continuity_mode": str(plan.get("continuity_mode") or "replace").strip().lower() or "replace",
                "effective_target_entity": str(plan.get("target_entity") or "none").strip().lower() or "none",
                "filter_keep_map": self._default_keep_map(plan, state.get("active_search_state")),
                "reasoning": "fallback_transition_judge",
            }

        active_filters = RealtorTurnPlanner._normalize_filters(
            (state.get("active_search_state") or {}).get("filters")
        )
        payload = {
            "user_text": state.get("query_text") or "",
            "history_excerpt": history_excerpt(state.get("history") or []),
            "active_search_state": state.get("active_search_state") or {},
            "active_filters": active_filters,
            "last_result_set": state.get("last_result_set") or {},
            "planner_output": plan,
            "conversation_memory": state.get("conversation_memory") or {"common": {}, "vertical": {}},
        }
        try:
            raw = await llm_service.generate_json(
                system_instruction=prompt,
                payload=payload,
                temperature=0.1,
                max_output_tokens=500,
            )
            return self._normalize(raw, plan, active_filters)
        except Exception:
            return {
                "effective_query_scope": str(plan.get("query_scope") or "new_query").strip().lower() or "new_query",
                "effective_continuity_mode": str(plan.get("continuity_mode") or "replace").strip().lower() or "replace",
                "effective_target_entity": str(plan.get("target_entity") or "none").strip().lower() or "none",
                "filter_keep_map": self._default_keep_map(plan, state.get("active_search_state")),
                "reasoning": "fallback_transition_judge",
            }

    @staticmethod
    def _default_keep_map(plan: Dict[str, Any], active_search_state: Dict[str, Any] | None) -> Dict[str, bool]:
        active_filters = RealtorTurnPlanner._normalize_filters(
            (active_search_state or {}).get("filters")
        )
        turn_filters = RealtorTurnPlanner._normalize_filters(plan.get("turn_filters"))
        planned_filters = RealtorTurnPlanner._normalize_filters(plan.get("filters"))
        effective_continuity_mode = str(plan.get("continuity_mode") or "replace").strip().lower() or "replace"
        if effective_continuity_mode == "replace":
            seed = turn_filters or planned_filters
            universe = {**active_filters, **seed}
            return {key: key in seed for key in universe.keys()}
        universe = {**active_filters, **planned_filters, **turn_filters}
        return {key: True for key in universe.keys()}

    @staticmethod
    def _normalize(raw: Dict[str, Any], plan: Dict[str, Any], active_filters: Dict[str, Any]) -> Dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        planned_filters = RealtorTurnPlanner._normalize_filters(plan.get("filters"))
        turn_filters = RealtorTurnPlanner._normalize_filters(plan.get("turn_filters"))
        effective_query_scope = str(payload.get("effective_query_scope") or plan.get("query_scope") or "new_query").strip().lower()
        if effective_query_scope not in _QUERY_SCOPES:
            effective_query_scope = str(plan.get("query_scope") or "new_query").strip().lower() or "new_query"
        effective_continuity_mode = str(payload.get("effective_continuity_mode") or plan.get("continuity_mode") or "replace").strip().lower()
        if effective_continuity_mode not in _CONTINUITY_MODES:
            effective_continuity_mode = str(plan.get("continuity_mode") or "replace").strip().lower() or "replace"
        effective_target_entity = str(payload.get("effective_target_entity") or plan.get("target_entity") or "none").strip().lower()
        if effective_target_entity not in _TARGET_ENTITIES:
            effective_target_entity = str(plan.get("target_entity") or "none").strip().lower() or "none"

        universe = {**active_filters, **planned_filters, **turn_filters}
        filter_keep_map = payload.get("filter_keep_map")
        if isinstance(filter_keep_map, dict):
            normalized_keep_map = {
                key: bool(filter_keep_map.get(key))
                for key in universe.keys()
            }
        else:
            retained_filter_keys = payload.get("retained_filter_keys")
            if isinstance(retained_filter_keys, list):
                retained = {
                    str(item).strip()
                    for item in retained_filter_keys
                    if str(item).strip() in universe
                }
                normalized_keep_map = {key: key in retained for key in universe.keys()}
            else:
                if effective_continuity_mode == "replace":
                    seed = turn_filters or planned_filters
                    normalized_keep_map = {key: key in seed for key in universe.keys()}
                else:
                    normalized_keep_map = {key: True for key in universe.keys()}

        return {
            "effective_query_scope": effective_query_scope,
            "effective_continuity_mode": effective_continuity_mode,
            "effective_target_entity": effective_target_entity,
            "filter_keep_map": normalized_keep_map,
            "reasoning": str(payload.get("reasoning") or "").strip() or None,
        }


class GenericTurnPlanner:
    async def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tenant_runtime = state.get("tenant_runtime") or {}
        prompts = tenant_runtime.get("prompts") or {}
        prompt = prompts.get("generic_turn_planner")
        payload = {
            "user_text": state.get("query_text") or "",
            "router_hint": {
                "route_mode": state.get("route_mode") or "answer_only",
                "intent": state.get("intent") or "NONE",
                "active_subflow": state.get("active_subflow") or "generic_answer",
            },
            "conversation_memory": state.get("conversation_memory") or {"common": {}, "vertical": {}},
            "history_excerpt": history_excerpt(state.get("history") or []),
            "last_result_set": state.get("last_result_set") or {},
        }
        try:
            raw = await llm_service.generate_json(
                system_instruction=prompt,
                payload=payload,
                temperature=0.1,
                max_output_tokens=700,
            )
            return self._normalize(raw, state)
        except Exception:
            return self._fallback(state)

    def _normalize(self, raw: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        intent = str(payload.get("intent") or state.get("intent") or "RAG").strip().upper()
        if intent not in _INTENTS:
            intent = "RAG"
        operation = str(payload.get("operation") or ("rag" if state.get("active_subflow") == "generic_rag" else "answer")).strip().lower()
        if operation not in {"rag", "answer", "clarify", "workflow"}:
            operation = "answer"
        top_k = payload.get("top_k")
        try:
            top_k_int = max(1, min(8, int(top_k or 4)))
        except (TypeError, ValueError):
            top_k_int = 4
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        return {
            "intent": intent,
            "operation": operation,
            "retrieval_query": str(payload.get("retrieval_query") or state.get("query_text") or "").strip(),
            "top_k": top_k_int,
            "filters": filters,
            "clarification": str(payload.get("clarification") or "").strip() or None,
            "reasoning": str(payload.get("reasoning") or "").strip() or None,
        }

    def _fallback(self, state: Dict[str, Any]) -> Dict[str, Any]:
        operation = "rag" if state.get("active_subflow") == "generic_rag" else "answer"
        return {
            "intent": state.get("intent") or ("RAG" if operation == "rag" else "NONE"),
            "operation": operation,
            "retrieval_query": str(state.get("query_text") or "").strip(),
            "top_k": 4,
            "filters": {},
            "clarification": None,
            "reasoning": "fallback_generic_plan",
        }


class WorkflowTurnPlanner:
    async def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tenant_runtime = state.get("tenant_runtime") or {}
        prompts = tenant_runtime.get("prompts") or {}
        prompt = prompts.get("workflow_planner")
        payload = {
            "user_text": state.get("query_text") or "",
            "conversation_memory": state.get("conversation_memory") or {"common": {}, "vertical": {}},
            "lead_progression_state": state.get("lead_progression_state") or {},
            "history_excerpt": history_excerpt(state.get("history") or []),
        }
        try:
            raw = await llm_service.generate_json(
                system_instruction=prompt,
                payload=payload,
                temperature=0.1,
                max_output_tokens=500,
            )
            return self._normalize(raw)
        except Exception:
            return self._fallback()

    @staticmethod
    def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        goal = str(payload.get("workflow_goal") or "external_action").strip() or "external_action"
        status = str(payload.get("status") or "pending_provider").strip() or "pending_provider"
        return {
            "workflow_goal": goal,
            "status": status,
            "clarification": str(payload.get("clarification") or "").strip() or None,
            "reasoning": str(payload.get("reasoning") or "").strip() or None,
        }

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "workflow_goal": "external_action",
            "status": "pending_provider",
            "clarification": None,
            "reasoning": "fallback_workflow_plan",
        }


turn_router = TurnRouter()
realtor_turn_planner = RealtorTurnPlanner()
realtor_search_transition_judge = RealtorSearchTransitionJudge()
realtor_filter_carryover_guard = RealtorFilterCarryoverGuard()
generic_turn_planner = GenericTurnPlanner()
workflow_turn_planner = WorkflowTurnPlanner()
