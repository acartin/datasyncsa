from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any, Dict, List

from app.services.llm_service import llm_service
from app.services.response_contracts_loader import response_contracts_loader
from app.services.turn_planning import history_excerpt


class AnswerSynthesizer:
    def __init__(self) -> None:
        contracts = response_contracts_loader.get_section("answer_synthesizer")
        self._no_component_show_markers = tuple(contracts.get("no_component_show_markers") or [])
        self._followup_canonical_strip_prefixes = tuple(contracts.get("followup_canonical_strip_prefixes") or [])
        self._surface_canonical_strip_prefixes = tuple(contracts.get("surface_canonical_strip_prefixes") or [])
        self._presentation_permission_patterns = tuple(contracts.get("presentation_permission_patterns") or [])
        self._reference_field_markers = {
            str(key).strip().lower(): tuple(value or [])
            for key, value in (contracts.get("reference_field_markers") or {}).items()
        }

    async def synthesize(self, state: Dict[str, Any]) -> str:
        grounded_answer = self._grounded_answer(state)
        if grounded_answer:
            return grounded_answer
        tenant_runtime = state.get("tenant_runtime") or {}
        prompts = tenant_runtime.get("prompts") or {}
        prompt = self._select_prompt(state, prompts)
        payload = self._build_payload(state)
        if prompt:
            try:
                answer = await llm_service.generate_text(
                    system_instruction=prompt,
                    contents=[self._payload_to_text(payload)],
                    temperature=0.35,
                    max_output_tokens=900,
                )
                if answer:
                    normalized_answer = answer.strip()
                    if self._violates_presentation_contract(normalized_answer, state):
                        normalized_answer = self._rewrite_presentation_conflict(state)
                    if self._violates_absent_components_contract(normalized_answer, state):
                        normalized_answer = self._rewrite_absent_components_conflict(normalized_answer, state)
                    normalized_answer = self._normalize_surface_text(normalized_answer)
                    return self._enforce_followup_contract(normalized_answer, state)
            except Exception:
                pass
        fallback_answer = self._fallback_answer(state)
        if self._violates_absent_components_contract(fallback_answer, state):
            fallback_answer = self._rewrite_absent_components_conflict(fallback_answer, state)
        fallback_answer = self._normalize_surface_text(fallback_answer)
        return self._enforce_followup_contract(fallback_answer, state)

    @staticmethod
    def _select_prompt(state: Dict[str, Any], prompts: Dict[str, Any]) -> str | None:
        active_subflow = str(state.get("active_subflow") or "").strip()
        if active_subflow == "realtor_search":
            return prompts.get("realtor_answer_synthesis") or prompts.get("generic_answer_synthesis")
        if active_subflow == "workflow":
            return prompts.get("workflow_answer_synthesis") or prompts.get("generic_answer_synthesis")
        return prompts.get("generic_answer_synthesis") or prompts.get("primary_chat")

    def _build_payload(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_text": state.get("query_text") or "",
            "route": {
                "route_mode": state.get("route_mode"),
                "intent": state.get("intent"),
                "active_subflow": state.get("active_subflow"),
            },
            "presentation_contract": {
                "components_count": len(state.get("components") or []),
                "current_turn_has_components": bool(state.get("components")),
                "must_not_request_show_confirmation": bool(state.get("components")),
            },
            "conversation_memory": state.get("conversation_memory") or {"common": {}, "vertical": {}},
            "lead_progression_state": state.get("lead_progression_state") or {},
            "last_result_set": state.get("last_result_set") or {},
            "execution_facts": state.get("execution_facts") or {},
            "tool_outputs": state.get("tool_outputs") or [],
            "components_count": len(state.get("components") or []),
            "followup_plan": state.get("followup_plan") or {},
            "reference_resolution": state.get("reference_resolution") or {},
            "history_excerpt": history_excerpt(state.get("history") or []),
        }

    @staticmethod
    def _payload_to_text(payload: Dict[str, Any]) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False)

    def _fallback_answer(self, state: Dict[str, Any]) -> str:
        active_subflow = str(state.get("active_subflow") or "generic_answer")
        if active_subflow == "realtor_search":
            return self._fallback_realtor_answer(state)
        if active_subflow == "workflow":
            return self._fallback_workflow_answer(state)
        return self._fallback_generic_answer(state)

    def _fallback_realtor_answer(self, state: Dict[str, Any]) -> str:
        result = state.get("last_result_set") or {}
        followup = state.get("followup_plan") or {}
        status = str(result.get("status") or "").strip().lower()
        operation = str(result.get("operation") or state.get("intent") or "PROPERTY_SEARCH").strip().upper()
        total = int(result.get("total_matches") or 0)
        visible = int(result.get("visible_count") or 0)
        summary = str(result.get("search_summary") or "").strip()
        question = str(followup.get("question") or "").strip()

        if status == "clarify":
            answer = str(result.get("clarification") or "Necesito un poco más de precisión para ayudarte mejor.").strip()
        elif status == "empty":
            answer = f"No encontré opciones para {summary}." if summary else "No encontré opciones con ese criterio."
        elif operation == "PROPERTY_INVENTORY":
            if total == 1:
                answer = "Sí, por ahora solo tengo una opción que cumple con esos criterios."
            else:
                answer = f"Por ahora tengo {total} opciones que cumplen con esos criterios."
        elif operation == "PROPERTY_PRICE_RANGE":
            min_price = result.get("min_price")
            max_price = result.get("max_price")
            if min_price is not None and max_price is not None:
                answer = f"El rango de precios va aproximadamente de ${min_price} a ${max_price}."
            else:
                answer = "Puedo ayudarte a revisar el rango de precios si afinamos un poco más la búsqueda."
        else:
            if total == 1:
                answer = f"Encontré una opción para {summary}." if summary else "Encontré una opción que coincide con lo que buscas."
            elif visible and total and visible < total:
                answer = f"Encontré {total} opciones para {summary}. Te muestro {visible} para empezar." if summary else f"Encontré {total} opciones. Te muestro {visible} para empezar."
            elif total:
                answer = f"Encontré {total} opciones para {summary}." if summary else f"Encontré {total} opciones."
            else:
                answer = "Puedo seguir afinando la búsqueda contigo."

        if question:
            return f"{answer} {question}".strip()
        return answer

    def _enforce_followup_contract(self, answer: str, state: Dict[str, Any]) -> str:
        normalized_answer = str(answer or "").strip()
        followup = state.get("followup_plan") or {}
        should_ask = bool(followup.get("should_ask"))
        question = str(followup.get("question") or "").strip()
        if not normalized_answer or not should_ask or not question:
            return normalized_answer

        statements, questions = self._split_sentences(normalized_answer)
        if questions:
            filtered_questions = [
                fragment
                for fragment in questions
                if not self._is_redundant_followup_question(fragment, question)
            ]
        else:
            filtered_questions = []

        is_covered_by_existing = any(
            self._is_redundant_followup_question(fragment, question)
            for fragment in statements + filtered_questions
        )
        should_append_question = bool(question) and not is_covered_by_existing

        fragments = [fragment for fragment in statements if fragment]
        fragments.extend(filtered_questions)
        if should_append_question:
            fragments.append(question)
        combined = " ".join(fragments).strip()
        if not combined.strip():
            return self._normalize_surface_text(normalized_answer)
        return self._normalize_surface_text(combined)

    def _is_redundant_followup_question(self, answer: str, question: str) -> bool:
        canonical_answer = self._canonicalize_followup_match_text(answer)
        canonical_question = self._canonicalize_followup_match_text(question)
        if not canonical_answer or not canonical_question:
            return False
        if canonical_question in canonical_answer:
            return True

        # Similarity guard for paraphrased repetition (ej. "podemos" vs "te gustaría que")
        if len(canonical_question) >= 40:
            ratio = difflib.SequenceMatcher(None, canonical_answer, canonical_question).ratio()
            if ratio >= 0.78:
                return True
        elif len(canonical_question) >= 24:
            ratio = difflib.SequenceMatcher(None, canonical_answer, canonical_question).ratio()
            if ratio >= 0.74:
                return True

        overlap = self._token_overlap_ratio(
            answer_text=canonical_answer,
            question_text=canonical_question,
        )
        if overlap >= 0.60:
            return True

        question_tokens = set(self._extract_key_tokens(canonical_question))
        if len(question_tokens) >= 3:
            answer_tokens = set(self._extract_key_tokens(canonical_answer))
            overlap = len(question_tokens & answer_tokens) / max(len(question_tokens), 1)
            if overlap >= 0.70:
                return True
        return False

    def _token_overlap_ratio(self, answer_text: str, question_text: str) -> float:
        answer_tokens = set(self._extract_key_tokens_static(answer_text))
        question_tokens = set(self._extract_key_tokens_static(question_text))
        if not answer_tokens or not question_tokens:
            return 0.0
        intersection = len(question_tokens & answer_tokens)
        return intersection / max(len(question_tokens), 1)

    def _extract_key_tokens_static(self, value: str) -> List[str]:
        cleaned = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
        cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
        cleaned = re.sub(r"[¿?¡!.,:;()\"']", "", cleaned)
        tokens = [token for token in cleaned.split() if len(token) > 2]
        stop_words = {
            "como",
            "que",
            "te",
            "la",
            "el",
            "lo",
            "los",
            "las",
            "del",
            "de",
            "en",
            "para",
            "porque",
            "quieres",
            "quisieras",
            "quiere",
            "quiero",
            "podria",
            "podrias",
            "podriamos",
            "podriamos",
            "podemos",
            "podrias",
            "me",
            "mi",
            "con",
            "si",
            "sí",
            "por",
            "su",
            "una",
            "un",
            "mas",
            "más",
            "tambien",
            "también",
            "cual",
            "cuales",
            "gustaria",
            "gustaría",
            "esto",
            "a",
            "al",
            "y",
            "o",
            "siempre",
            "cuando",
            "como",
        }
        return [token for token in tokens if token not in stop_words]

    def _extract_key_tokens(self, text: str) -> List[str]:
        return self._extract_key_tokens_static(text)

    def _canonicalize_followup_match_text(self, value: str) -> str:
        text = " ".join(str(value or "").split()).casefold()
        if self._followup_canonical_strip_prefixes:
            prefix_pattern = "|".join(re.escape(prefix) for prefix in self._followup_canonical_strip_prefixes)
            text = re.sub(rf"^({prefix_pattern}),?\s+", "", text)
        text = re.sub(r"[¿?.,!]", "", text)
        return " ".join(text.split()).strip()

    def _fallback_generic_answer(self, state: Dict[str, Any]) -> str:
        last_result_set = state.get("last_result_set") or {}
        clarification = str(last_result_set.get("clarification") or "").strip()
        if clarification:
            return clarification
        tool_outputs = state.get("tool_outputs") or []
        followup = state.get("followup_plan") or {}
        question = str(followup.get("question") or "").strip()
        if tool_outputs:
            first = tool_outputs[0]
            docs = first.get("documents") if isinstance(first, dict) else None
            if isinstance(docs, list) and docs:
                snippets: List[str] = []
                for item in docs[:2]:
                    if not isinstance(item, dict):
                        continue
                    chunk = str(item.get("chunk_text") or item.get("content") or item.get("text") or "").strip()
                    if chunk:
                        snippets.append(chunk[:220])
                answer = " ".join(snippets).strip() or "Encontré información relevante para responderte."
            else:
                answer = "No encontré contexto suficiente para responder con precisión."
        else:
            answer = "Puedo ayudarte con eso."
        if question:
            return f"{answer} {question}".strip()
        return answer

    def _fallback_workflow_answer(self, state: Dict[str, Any]) -> str:
        workflow_result = state.get("last_result_set") or {}
        clarification = str(workflow_result.get("clarification") or "").strip()
        if clarification:
            return clarification
        return "Puedo ayudarte a coordinar ese siguiente paso. Si quieres, avanzamos con los datos necesarios."

    def _grounded_answer(self, state: Dict[str, Any]) -> str | None:
        execution_facts = state.get("execution_facts") or {}
        reference_resolution = state.get("reference_resolution") or execution_facts.get("reference_resolution") or {}
        answer = str(
            execution_facts.get("reference_answer")
            or (state.get("last_result_set") or {}).get("grounded_answer")
            or state.get("grounded_answer")
            or ""
        ).strip()
        if not answer:
            return None
        question = str(((state.get("followup_plan") or {}).get("question")) or "").strip()
        if question:
            normalized_answer = " ".join(answer.split()).casefold()
            normalized_question = " ".join(question.split()).casefold()
            if normalized_question.startswith(normalized_answer):
                trimmed = question[len(answer):].strip()
                question = trimmed.lstrip(" .") if trimmed else ""
        if question and self._question_repeats_resolved_reference_field(question, reference_resolution):
            question = ""
        if question:
            return f"{answer} {question}".strip()
        return answer

    def _question_repeats_resolved_reference_field(self, question: str, reference_resolution: Dict[str, Any]) -> bool:
        if not question or not isinstance(reference_resolution, dict):
            return False
        fields = reference_resolution.get("fields")
        if not isinstance(fields, list):
            fields = [reference_resolution.get("field")] if reference_resolution.get("field") else []
        normalized_question = str(question or "").strip().casefold()
        for field in fields:
            markers = self._reference_field_markers.get(str(field or "").strip().lower(), ())
            if any(marker.casefold() in normalized_question for marker in markers):
                return True
        return False

    def _violates_presentation_contract(self, answer: str, state: Dict[str, Any]) -> bool:
        if not state.get("components"):
            return False
        normalized = (answer or "").strip().lower()
        if not normalized:
            return False
        if "muestre" not in normalized and "mostrar" not in normalized:
            return False
        return any(re.search(pattern, normalized) for pattern in self._presentation_permission_patterns)

    def _rewrite_presentation_conflict(self, state: Dict[str, Any]) -> str:
        result = state.get("last_result_set") or {}
        followup = state.get("followup_plan") or {}
        summary = str(result.get("search_summary") or "").strip()
        total = int(result.get("total_matches") or len(state.get("components") or []) or 0)
        visible = int(result.get("visible_count") or len(state.get("components") or []) or 0)
        question = str(followup.get("question") or "").strip()

        if total > visible and visible > 0:
            answer = f"Encontré {total} opciones para {summary}. Te muestro {visible} para empezar." if summary else f"Encontré {total} opciones. Te muestro {visible} para empezar."
        elif total == 1:
            answer = f"Aquí te muestro la opción que encontré para {summary}." if summary else "Aquí te muestro la opción que encontré."
        else:
            answer = f"Aquí te muestro {visible or total} opciones para {summary}." if summary else f"Aquí te muestro {visible or total} opciones."

        if question and "muestre" not in question.lower() and "muestro" not in question.lower():
            return f"{answer} {question}".strip()
        return answer

    def _violates_absent_components_contract(self, answer: str, state: Dict[str, Any]) -> bool:
        if state.get("components"):
            return False
        normalized = (answer or "").strip().lower()
        if not normalized:
            return False
        return any(marker in normalized for marker in self._no_component_show_markers)


    def _rewrite_absent_components_conflict(self, answer: str, state: Dict[str, Any]) -> str:
        sanitized = self._sanitize_no_components_text(answer)
        if sanitized:
            return sanitized
        fallback = self._sanitize_no_components_text(self._fallback_answer(state))
        if fallback:
            return fallback
        return "Puedo ayudarte con eso."

    def _sanitize_no_components_text(self, answer: str) -> str:
        fragments = re.split(r"(?<=[?.!])\s+", str(answer or "").strip())
        kept = [
            fragment.strip()
            for fragment in fragments
            if fragment.strip()
            and not any(marker in fragment.casefold() for marker in self._no_component_show_markers)
        ]
        sanitized = " ".join(kept).strip()
        sanitized = re.sub(r"\s+([?.!])", r"\1", sanitized)
        return sanitized

    def _normalize_surface_text(self, answer: str) -> str:
        fragments = self._split_text_fragments(answer)
        deduped: List[str] = []
        seen: set[str] = set()
        for fragment in fragments:
            canonical = self._canonicalize_surface_fragment(fragment)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            deduped.append(fragment)
        normalized = " ".join(deduped).strip()
        normalized = re.sub(r"\s+([?.!])", r"\1", normalized)
        normalized = re.sub(r"\s{2,}", " ", normalized)
        return normalized.strip()

    @staticmethod
    def _split_text_fragments(value: str) -> List[str]:
        return [
            fragment.strip()
            for fragment in re.split(r"(?<=[?.!])\s+", str(value or "").strip())
            if fragment.strip()
        ]

    def _split_sentences(self, value: str) -> tuple[List[str], List[str]]:
        statements: List[str] = []
        questions: List[str] = []
        for fragment in self._split_text_fragments(value):
            if self._is_question_fragment(fragment):
                questions.append(fragment)
            else:
                statements.append(fragment)
        return statements, questions

    @staticmethod
    def _is_question_fragment(fragment: str) -> bool:
        stripped = str(fragment or "").strip()
        return "?" in stripped or stripped.startswith("¿")

    def _canonicalize_surface_fragment(self, value: str) -> str:
        text = " ".join(str(value or "").split()).casefold()
        if self._surface_canonical_strip_prefixes:
            prefix_pattern = "|".join(re.escape(prefix) for prefix in self._surface_canonical_strip_prefixes)
            text = re.sub(rf"^({prefix_pattern}),?\s+", "", text)
        text = re.sub(r",\s+[a-záéíóúñ][a-záéíóúñ'-]*([?.!])$", r"\1", text)
        text = re.sub(r"[¿?.,!]", "", text)
        return " ".join(text.split()).strip()


answer_synthesizer = AnswerSynthesizer()
