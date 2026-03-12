from __future__ import annotations

from typing import Any, Dict, List


_FIELD_ALIASES = {
    "bathrooms": "bathrooms",
    "banos": "bathrooms",
    "baños": "bathrooms",
    "bedrooms": "bedrooms",
    "habitaciones": "bedrooms",
    "garage": "garage",
    "cochera": "garage",
    "garajes": "garage",
    "price": "price",
    "precio": "price",
    "location": "location",
    "ubicacion": "location",
    "ubicación": "location",
    "title": "title",
    "titulo": "title",
    "título": "title",
    "image_url": "image_url",
    "foto": "image_url",
    "imagen": "image_url",
    "all_known_fields": "all_known_fields",
    "all": "all_known_fields",
    "todo": "all_known_fields",
    "todos": "all_known_fields",
    "detalles": "all_known_fields",
    "caracteristicas": "all_known_fields",
    "características": "all_known_fields",
}

_FIELD_LABELS = {
    "bathrooms": "baños",
    "bedrooms": "habitaciones",
    "garage": "cochera",
    "price": "precio",
    "location": "ubicación",
    "title": "nombre",
    "image_url": "foto",
}


class ShownResultsReferenceResolver:
    def resolve(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tool_plan = state.get("tool_plan") or []
        plan = tool_plan[0] if tool_plan else {}
        request = self._normalize_request(plan.get("reference_request"))
        components = state.get("last_shown_components") or state.get("components") or []
        if not components:
            clarification = "No tengo una propiedad mostrada en este momento para responderte sobre esa referencia."
            return self._clarify_result(state, clarification)

        component = self._select_component(components, request)
        if not component:
            clarification = "No pude identificar con precisión a cuál de las propiedades mostradas te refieres."
            return self._clarify_result(state, clarification)

        requested_fields = self._resolve_requested_fields(request, component)
        if not requested_fields:
            clarification = "Puedo decirte el precio, ubicación, habitaciones, baños o cochera de esa propiedad. ¿Qué dato te interesa?"
            return self._clarify_result(state, clarification)

        field_key = requested_fields[0] if len(requested_fields) == 1 else "all_known_fields"
        values = {
            field: self._extract_value(component, field)
            for field in requested_fields
        }
        values = {
            key: value
            for key, value in values.items()
            if value not in (None, "", [])
        }
        if not values:
            clarification = "No tengo suficientes datos confirmados de esa propiedad para responderte con precisión."
            return self._clarify_result(state, clarification)

        if len(values) == 1 and field_key != "all_known_fields":
            sole_field = next(iter(values.keys()))
            answer_text = self._build_single_field_answer(component, request, sole_field, values[sole_field])
        else:
            answer_text = self._build_multi_field_answer(component, request, values)

        resolved_property = {
            "id": component.get("id"),
            "title": component.get("title"),
            "location": component.get("location"),
        }
        resolution = {
            "target": request.get("target"),
            "index": request.get("index"),
            "field": field_key,
            "fields": list(values.keys()),
            "value": values.get(field_key) if field_key != "all_known_fields" else None,
            "values": values,
            "property": resolved_property,
        }
        return {
            "tool_outputs": [{"tool": "shown_results_reference_resolver", "resolution": resolution}],
            "tool_results": [{"tool": "shown_results_reference_resolver", "resolution": resolution}],
            "components": [],
            "reference_resolution": resolution,
            "grounded_answer": answer_text,
            "execution_facts": {
                "status": "results",
                "reference_answer": answer_text,
                "reference_resolution": resolution,
            },
            "last_result_set": {
                "status": "results",
                "operation": "REFERENCE_ANSWER",
                "search_summary": component.get("title") or component.get("location"),
                "filters": (state.get("last_result_set") or {}).get("filters") or {},
                "property_ids": [str(component.get("id"))] if component.get("id") else [],
                "visible_count": 0,
                "total_matches": 1,
                "result_mode": "answer_only",
                "grounded_answer": answer_text,
            },
        }

    @staticmethod
    def _normalize_request(raw_request: Any) -> Dict[str, Any]:
        payload = raw_request if isinstance(raw_request, dict) else {}
        target = str(payload.get("target") or "last").strip().lower() or "last"
        if target not in {"last", "first", "index", "single"}:
            target = "last"

        index = payload.get("index")
        try:
            normalized_index = int(index) if index is not None else None
        except (TypeError, ValueError):
            normalized_index = None

        normalized_fields: List[str] = []
        fields_payload = payload.get("fields")
        if isinstance(fields_payload, list):
            for item in fields_payload:
                normalized = _FIELD_ALIASES.get(str(item or "").strip().lower())
                if normalized and normalized not in normalized_fields:
                    normalized_fields.append(normalized)

        field = str(payload.get("field") or "").strip().lower()
        normalized_field = _FIELD_ALIASES.get(field)
        if normalized_field and normalized_field not in normalized_fields:
            normalized_fields.append(normalized_field)

        return {
            "mode": str(payload.get("mode") or "shown_result").strip().lower() or "shown_result",
            "target": target,
            "index": normalized_index,
            "field": normalized_field,
            "fields": normalized_fields,
        }

    @staticmethod
    def _resolve_requested_fields(request: Dict[str, Any], component: Dict[str, Any]) -> List[str]:
        fields = request.get("fields") if isinstance(request.get("fields"), list) else []
        normalized = [str(item).strip() for item in fields if str(item).strip()]
        if not normalized and request.get("field"):
            normalized = [str(request.get("field")).strip()]
        if "all_known_fields" in normalized:
            normalized = ["price", "location", "bedrooms", "bathrooms", "garage"]

        available: List[str] = []
        for field in normalized:
            if field == "location" and component.get("location") not in (None, ""):
                available.append(field)
                continue
            if field == "title" and component.get("title") not in (None, ""):
                available.append(field)
                continue
            if field == "price" and component.get("price") not in (None, ""):
                available.append(field)
                continue
            if field == "image_url" and component.get("image_url") not in (None, ""):
                available.append(field)
                continue
            features = component.get("features") if isinstance(component.get("features"), dict) else {}
            if field in {"bathrooms", "bedrooms", "garage"} and features.get(field) not in (None, ""):
                available.append(field)
        return available

    @staticmethod
    def _select_component(components: List[Dict[str, Any]], request: Dict[str, Any]) -> Dict[str, Any] | None:
        if not components:
            return None
        target = request.get("target")
        if target == "single" and len(components) == 1:
            return components[0]
        if target == "first":
            return components[0]
        if target == "index":
            index = request.get("index")
            if isinstance(index, int) and index > 0 and index <= len(components):
                return components[index - 1]
            return None
        return components[-1]

    @staticmethod
    def _extract_value(component: Dict[str, Any], field_key: str) -> Any:
        features = component.get("features") if isinstance(component.get("features"), dict) else {}
        if field_key in {"bathrooms", "bedrooms", "garage"}:
            return features.get(field_key)
        if field_key == "location":
            return component.get("location")
        if field_key == "title":
            return component.get("title")
        if field_key == "price":
            return component.get("price")
        if field_key == "image_url":
            return component.get("image_url")
        return None

    @staticmethod
    def _clarify_result(state: Dict[str, Any], clarification: str) -> Dict[str, Any]:
        return {
            "tool_outputs": [],
            "tool_results": [],
            "components": [],
            "reference_resolution": {},
            "grounded_answer": None,
            "execution_facts": {
                "status": "clarify",
                "pending_clarification": clarification,
            },
            "last_result_set": {
                "status": "clarify",
                "operation": "REFERENCE_ANSWER",
                "search_summary": (state.get("last_result_set") or {}).get("search_summary"),
                "filters": (state.get("last_result_set") or {}).get("filters") or {},
                "result_mode": "answer_only",
                "clarification": clarification,
            },
        }

    def _build_single_field_answer(
        self,
        component: Dict[str, Any],
        request: Dict[str, Any],
        field_key: str,
        value: Any,
    ) -> str:
        reference_text = self._reference_prefix(request, component)
        if field_key == "bathrooms":
            return f"{reference_text} tiene {self._format_number(value)} baños."
        if field_key == "bedrooms":
            return f"{reference_text} tiene {self._format_number(value)} habitaciones."
        if field_key == "garage":
            return f"{reference_text} tiene espacio para {self._format_number(value)} carros."
        if field_key == "price":
            return f"{reference_text} tiene un precio de ${self._format_price(value)}."
        if field_key == "location":
            return f"{reference_text} está ubicada en {value}."
        if field_key == "title":
            return f"{reference_text} se llama {value}."
        if field_key == "image_url":
            return f"{reference_text} tiene una imagen disponible."
        return f"{reference_text} tiene este dato: {value}."

    def _build_multi_field_answer(
        self,
        component: Dict[str, Any],
        request: Dict[str, Any],
        values: Dict[str, Any],
    ) -> str:
        reference_text = self._reference_prefix(request, component)
        fragments: List[str] = []
        if "location" in values:
            fragments.append(f"está ubicada en {values['location']}")
        if "price" in values:
            fragments.append(f"cuesta ${self._format_price(values['price'])}")
        if "bedrooms" in values:
            fragments.append(f"tiene {self._format_number(values['bedrooms'])} habitaciones")
        if "bathrooms" in values:
            fragments.append(f"tiene {self._format_number(values['bathrooms'])} baños")
        if "garage" in values:
            fragments.append(f"tiene espacio para {self._format_number(values['garage'])} carros")
        if "title" in values:
            fragments.append(f"se llama {values['title']}")
        if not fragments:
            return f"{reference_text} tiene varios datos disponibles."
        if len(fragments) == 1:
            return f"{reference_text} {fragments[0]}."
        return f"{reference_text} " + ", ".join(fragments[:-1]) + f" y {fragments[-1]}."

    @staticmethod
    def _reference_prefix(request: Dict[str, Any], component: Dict[str, Any]) -> str:
        target = request.get("target")
        if target == "first":
            return "La primera propiedad que te mostré"
        if target == "index" and request.get("index"):
            return f"La propiedad número {request['index']} que te mostré"
        if target == "single":
            return "La propiedad que te mostré"
        return "La última propiedad que te mostré"

    @staticmethod
    def _format_number(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        if numeric.is_integer():
            return str(int(numeric))
        return str(numeric)

    @staticmethod
    def _format_price(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{numeric:,.0f}"


shown_results_reference_resolver = ShownResultsReferenceResolver()
