"""
Scoring Engine with Gemini LLM Integration

Implements real scoring using Gemini LLM with dynamic prompts from database.
"""

import logging
import json
import asyncio
import re
import time
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.services.prompt_linter import PromptLinter

logger = logging.getLogger("inference-core-v2.scoring_engine")

DEFAULT_EXTRACTION_FIELDS = [
    # Intentionally empty: extraction field contract must come from DB prompt config.
]


class ScoringEngine:
    """
    Scoring engine that uses Gemini LLM for lead analysis.
    
    Features:
    - Dynamic prompts from database configuration
    - Structured JSON output
    - Retry logic with exponential backoff
    - Timeout handling
    """
    
    def __init__(self):
        self._client = None
        self._model_id = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_retries = max(1, int(settings.scoring_llm_max_retries or 1))
        self._timeout = settings.scoring_llm_timeout_secs
    
    @property
    def client(self):
        """Lazy initialization of Gemini client"""
        if self._client is None:
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY not configured")
            
            try:
                from google import genai
                self._client = genai.Client(api_key=settings.google_api_key)
            except ImportError:
                raise ImportError("google-genai package not installed. Run: pip install google-genai")
        
        return self._client
    
    async def analyze_conversation(
        self,
        conversation_text: str,
        model_config: Dict[str, Any],
        prompt_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze a conversation and return scoring results.
        
        Args:
            conversation_text: Full conversation text to analyze
            model_config: Model configuration with criteria and bands
            prompt_config: Prompt configuration with template and extraction_schema
        
        Returns:
            Dict with:
            - scores: Dict[criterion_key, score]
            - explanations: Dict[criterion_key, explanation]
            - extraction_result: Dict with extracted data
            - reasoning: str
            - prompt_snapshot: str (the actual prompt used)
        """
        analysis_start = time.perf_counter()
        vertical_name = model_config.get("vertical_name", "leads")
        vertical_slug = model_config.get("vertical_slug", "")
        criteria = model_config.get("criteria", [])
        bands = self._extract_bands_from_criteria(criteria)
        
        prompt_template = prompt_config.get("prompt_template")
        if not prompt_template:
            raise ValueError("No prompt_template found in prompt_config - prompt must be configured in database")
        lint = PromptLinter().validate_template(prompt_template)
        prompt_template = lint["normalized_template"]
        
        builder = PromptBuilder(custom_template=prompt_template)
        schema_config = self._parse_extraction_schema_config(prompt_config.get("extraction_schema"))
        extraction_fields = self._merge_extraction_fields(
            builder.get_extraction_fields_from_prompt(),
            schema_config["extraction_fields"],
        )
        extraction_fields = self._merge_extraction_fields(
            extraction_fields,
            DEFAULT_EXTRACTION_FIELDS,
        )
        
        system_prompt = builder.build_prompt(
            vertical_name=vertical_name,
            criteria=criteria,
            bands=bands,
            extraction_fields=extraction_fields,
            business_domain=model_config.get("business_domain"),
            locale=model_config.get("locale"),
            timestamp_utc=model_config.get("timestamp_utc")
        )
        
        response_schema = builder.build_response_schema(
            criteria,
            extraction_fields,
            slot_hints_schema=schema_config["slot_hints_schema"],
            response_schema_override=schema_config["response_schema_override"],
        )
        try:
            schema_chars = len(json.dumps(response_schema, ensure_ascii=False, default=str))
        except Exception:
            schema_chars = 0
        logger.info(
            "SCORING_INPUT model=%s criteria=%s conversation_chars=%s conversation_lines=%s prompt_chars=%s schema_chars=%s",
            self._model_id,
            len(criteria),
            len(conversation_text or ""),
            len((conversation_text or "").splitlines()),
            len(system_prompt or ""),
            schema_chars,
        )

        used_fallback = False
        llm_meta = {
            "json_valid": False,
            "response_chars": 0,
            "llm_latency_ms": None,
        }
        result: Dict[str, Any] = {}
        try:
            llm_response = await self._call_gemini(
                system_prompt=system_prompt,
                conversation_text=conversation_text,
                response_schema=response_schema
            )
            result = llm_response.get("payload", {}) if isinstance(llm_response, dict) else {}
            llm_meta = llm_response.get("meta", llm_meta) if isinstance(llm_response, dict) else llm_meta
        except Exception as exc:
            logger.error("LLM scoring unavailable, using conservative fallback: %s", exc)
            used_fallback = True
        
        extraction_result: Dict[str, Any] = {}
        slot_state: Dict[str, Any] = {}
        confidence = None
        if isinstance(result.get("slot_hints"), dict):
            slot_state = result.get("slot_hints") or {}
        
        extracted_data_container = result.get("extracted_data", {})
        if not isinstance(extracted_data_container, dict):
            extracted_data_container = {}

        for field in extraction_fields:
            key = field.get("key")
            if not key or key not in extracted_data_container:
                continue
            value = extracted_data_container[key]
            if self._is_meaningful_value(value):
                extraction_result[key] = value

        extraction_result = self._enrich_extraction_from_text(conversation_text, extraction_result)
        scores, explanations, missing_score_keys = self._extract_scores_and_explanations(
            criteria=criteria,
            payload=result,
        )
        if missing_score_keys:
            used_fallback = True
            logger.warning(
                "LLM payload missing/invalid scores for criteria=%s; conservative defaults applied",
                ",".join(missing_score_keys),
            )
        
        if "confidence" in result and result["confidence"] is not None:
            parsed_conf = self._coerce_float(result["confidence"])
            if parsed_conf is not None:
                confidence = max(0.0, min(1.0, parsed_conf))

        reasoning_parts = []
        llm_reasoning = (result.get("reasoning") or "").strip() if isinstance(result, dict) else ""
        if llm_reasoning:
            reasoning_parts.append(llm_reasoning)
        elif used_fallback:
            reasoning_parts.append("Scoring conservador por ausencia de salida valida del LLM.")
        if missing_score_keys:
            reasoning_parts.append(
                f"Criteria con default conservador: {', '.join(missing_score_keys)}."
            )
        final_reasoning = " | ".join(reasoning_parts)

        total_ms = (time.perf_counter() - analysis_start) * 1000.0
        logger.info(
            "SCORING_OUTPUT duration_ms=%.1f fallback=%s scores=%s extraction_fields=%s slots=%s json_valid=%s response_chars=%s",
            total_ms,
            used_fallback,
            len(scores),
            len(extraction_result),
            len(slot_state),
            llm_meta.get("json_valid"),
            llm_meta.get("response_chars"),
        )
        
        return {
            "scores": scores,
            "explanations": explanations,
            "extraction_result": extraction_result,
            "reasoning": final_reasoning,
            "confidence": confidence,
            "prompt_snapshot": system_prompt,
            "fallback_used": used_fallback,
            "slot_state": slot_state,
            "json_valid": bool(llm_meta.get("json_valid")),
            "response_chars": llm_meta.get("response_chars"),
            "latency_ms": int(total_ms),
        }

    @staticmethod
    def _is_meaningful_value(value: Any) -> bool:
        """Ignore empty/placeholder values to avoid wiping accumulated extraction."""
        if value is None:
            return False
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return False
            if normalized.lower() in {"null", "none", "n/a", "na", "unknown", "desconocido"}:
                return False
            return True
        return True

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", ".")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _extract_scores_and_explanations(
        self,
        *,
        criteria: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> Tuple[Dict[str, float], Dict[str, str], List[str]]:
        raw_scores = payload.get("scores") if isinstance(payload, dict) else {}
        if not isinstance(raw_scores, dict):
            raw_scores = {}
        raw_score_reasons = payload.get("score_reasons") if isinstance(payload, dict) else {}
        if not isinstance(raw_score_reasons, dict):
            raw_score_reasons = {}
        generic_reasoning = (payload.get("reasoning") or "").strip() if isinstance(payload, dict) else ""

        scores: Dict[str, float] = {}
        explanations: Dict[str, str] = {}
        missing: List[str] = []

        for criterion in criteria or []:
            criterion_key = str(criterion.get("criterion_key") or "").strip()
            if not criterion_key:
                continue
            min_score = float(criterion.get("min_score", 0))
            max_score = float(criterion.get("max_score", 10))
            conservative_default = (min_score + max_score) / 2.0

            raw_value = raw_scores.get(criterion_key)
            criterion_reason = ""
            if isinstance(raw_value, dict):
                raw_score_value = (
                    raw_value.get("score")
                    if raw_value.get("score") is not None
                    else raw_value.get("value")
                )
                criterion_reason = str(
                    raw_value.get("reason") or raw_value.get("explanation") or ""
                ).strip()
            else:
                raw_score_value = raw_value

            parsed_score = self._coerce_float(raw_score_value)
            if parsed_score is None:
                parsed_score = conservative_default
                missing.append(criterion_key)
            parsed_score = max(min_score, min(max_score, float(parsed_score)))
            scores[criterion_key] = parsed_score

            if not criterion_reason:
                reason_from_map = raw_score_reasons.get(criterion_key)
                if isinstance(reason_from_map, str):
                    criterion_reason = reason_from_map.strip()
            if not criterion_reason:
                if criterion_key in missing:
                    criterion_reason = (
                        f"Evidencia insuficiente para {criterion_key}; "
                        f"default conservador {parsed_score:.1f}."
                    )
                else:
                    criterion_reason = generic_reasoning or f"LLM score for {criterion_key}."
            explanations[criterion_key] = criterion_reason

        return scores, explanations, missing

    def _enrich_extraction_from_text(self, conversation_text: str, extraction: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(extraction or {})
        text = conversation_text or ""

        if not data.get("extracted_email"):
            email_match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)
            if email_match:
                data["extracted_email"] = email_match.group(0)

        if not data.get("extracted_phone"):
            phone_match = re.search(r"\b(?:\+?\d{1,3}[-\s]?)?(?:\d{4}[-\s]?\d{4})\b", text)
            if phone_match:
                data["extracted_phone"] = phone_match.group(0).replace(" ", "")

        if not data.get("extracted_name"):
            name_match = re.search(r"\bme llamo\s+([A-Za-zÁÉÍÓÚáéíóúÑñ\s]{4,60})", text, re.IGNORECASE)
            if name_match:
                data["extracted_name"] = " ".join(name_match.group(1).strip().split())

        return data
    
    async def _call_gemini(
        self,
        system_prompt: str,
        conversation_text: str,
        response_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call Gemini API with retries and timeout handling.
        
        Args:
            system_prompt: System instruction for the LLM
            conversation_text: The conversation to analyze
            response_schema: JSON schema for structured output
        
        Returns:
            Parsed JSON response from the LLM
        """
        last_error = None
        
        for attempt in range(1, self._max_retries + 1):
            attempt_start = time.perf_counter()
            try:
                result = await asyncio.wait_for(
                    self._call_gemini_internal(system_prompt, conversation_text, response_schema),
                    timeout=self._timeout
                )
                duration_ms = (time.perf_counter() - attempt_start) * 1000.0
                logger.info(
                    "SCORING_LLM_CALL_SUCCESS attempt=%s duration_ms=%.1f timeout_secs=%s",
                    attempt,
                    duration_ms,
                    self._timeout,
                )
                return result
            
            except asyncio.TimeoutError:
                duration_ms = (time.perf_counter() - attempt_start) * 1000.0
                logger.warning(
                    "Gemini API timeout on attempt %s/%s after %.1fms (timeout=%ss)",
                    attempt,
                    self._max_retries,
                    duration_ms,
                    self._timeout,
                )
                last_error = TimeoutError(f"LLM request timed out after {self._timeout}s")
                # Fail fast on timeout to avoid long stalls in async scoring.
                break
            
            except Exception as e:
                duration_ms = (time.perf_counter() - attempt_start) * 1000.0
                logger.warning(
                    "Gemini API error on attempt %s/%s after %.1fms: %s",
                    attempt,
                    self._max_retries,
                    duration_ms,
                    e,
                )
                last_error = e
            
            if attempt < self._max_retries:
                delay = min(2 ** attempt, 10)
                await asyncio.sleep(delay)
        
        logger.error(f"All Gemini API attempts failed: {last_error}")
        raise last_error or Exception("Unknown error in Gemini API")
    
    async def _call_gemini_internal(
        self,
        system_prompt: str,
        conversation_text: str,
        response_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Internal method to call Gemini API.
        
        Uses structured output with JSON schema for reliable parsing.
        """
        try:
            from google.genai import types
        except ImportError:
            raise ImportError("google-genai package not installed")
        
        prompt = (
            "Analiza la conversacion y devuelve SOLO JSON valido que cumpla "
            "estrictamente el schema solicitado.\n\n"
            "CONVERSACION:\n"
            f"{conversation_text}"
        )
        call_start = time.perf_counter()
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self._model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self._temperature,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        gen_ms = (time.perf_counter() - call_start) * 1000.0
        raw_text = response.text or ""
        logger.info(
            "SCORING_LLM_RAW duration_ms=%.1f response_chars=%s prompt_chars=%s",
            gen_ms,
            len(raw_text),
            len(prompt),
        )
        
        parse_start = time.perf_counter()
        try:
            parsed = json.loads(raw_text)
            parse_ms = (time.perf_counter() - parse_start) * 1000.0
            logger.info("SCORING_LLM_PARSE_SUCCESS duration_ms=%.1f", parse_ms)
            return {
                "payload": parsed,
                "meta": {
                    "json_valid": True,
                    "response_chars": len(raw_text),
                    "llm_latency_ms": float(gen_ms + parse_ms),
                },
            }
        except json.JSONDecodeError as e:
            parse_ms = (time.perf_counter() - parse_start) * 1000.0
            logger.error("SCORING_LLM_PARSE_ERROR duration_ms=%.1f error=%s", parse_ms, e)
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.debug(f"Raw response: {raw_text[:1000]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
    
    def _extract_bands_from_criteria(self, criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract bands list from criteria (bands are nested in criteria)"""
        all_bands = []
        for criterion in criteria:
            bands = criterion.get("bands", [])
            for band in bands:
                band["criterion_id"] = criterion.get("id")
            all_bands.extend(bands)
        return all_bands

    @staticmethod
    def _merge_extraction_fields(
        prompt_fields: Optional[List[Dict[str, Any]]],
        default_fields: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Merge prompt-defined and default extraction fields without duplicates."""
        merged: List[Dict[str, Any]] = []
        seen = set()

        for field in (prompt_fields or []):
            key = field.get("key")
            if not key or key in seen:
                continue
            merged.append(field)
            seen.add(key)

        for field in (default_fields or []):
            key = field.get("key")
            if not key or key in seen:
                continue
            merged.append(field)
            seen.add(key)

        return merged
    
    def _parse_extraction_schema_config(self, extraction_schema: Any) -> Dict[str, Any]:
        schema = extraction_schema if isinstance(extraction_schema, dict) else {}

        fields: List[Dict[str, Any]] = []
        raw_fields = schema.get("fields")
        if isinstance(raw_fields, list):
            for field in raw_fields:
                if not isinstance(field, dict):
                    continue
                key = str(field.get("key") or "").strip()
                if not key:
                    continue
                fields.append(
                    {
                        "key": key,
                        "type": str(field.get("type") or "string"),
                        "description": str(field.get("description") or ""),
                    }
                )
        response_schema_override = schema.get("response_schema")
        if not isinstance(response_schema_override, dict):
            response_schema_override = {}
        response_schema_override = self._sanitize_schema_for_gemini(response_schema_override)

        if not response_schema_override and isinstance(schema.get("properties"), dict):
            props = schema.get("properties") or {}
            # Backward compatibility: treat extraction_schema as response_schema root only
            # when it clearly defines scoring/extraction response objects.
            if "scores" in props or "extracted_data" in props:
                response_schema_override = schema

        if not fields and isinstance(response_schema_override, dict):
            extracted_data_schema = (response_schema_override.get("properties") or {}).get("extracted_data")
            if isinstance(extracted_data_schema, dict):
                fields = self._extract_fields_from_properties(extracted_data_schema.get("properties"))

        if not fields and isinstance(schema.get("properties"), dict):
            fields = self._extract_fields_from_properties(schema.get("properties"))

        deterministic_config = schema.get("deterministic_scoring")
        if not isinstance(deterministic_config, dict):
            deterministic_config = {}

        slot_hints_schema = schema.get("slot_hints_schema")
        if not isinstance(slot_hints_schema, dict):
            slot_hints_schema = self._build_slot_hints_schema_from_config(deterministic_config)
        slot_hints_schema = self._sanitize_schema_for_gemini(slot_hints_schema)

        return {
            "extraction_fields": fields,
            "slot_hints_schema": slot_hints_schema,
            "response_schema_override": response_schema_override,
        }

    @staticmethod
    def _extract_fields_from_properties(raw_properties: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_properties, dict):
            return []
        fields: List[Dict[str, Any]] = []
        for key, meta in raw_properties.items():
            if not key:
                continue
            meta_dict = meta if isinstance(meta, dict) else {}
            fields.append(
                {
                    "key": str(key),
                    "type": str(meta_dict.get("type") or "string"),
                    "description": str(meta_dict.get("description") or ""),
                }
            )
        return fields

    @staticmethod
    def _sanitize_schema_for_gemini(schema: Any) -> Any:
        """
        Drop schema keys that trigger INVALID_ARGUMENT in Gemini response_schema.
        """
        unsupported_keys = {"additionalProperties", "additional_properties"}
        if isinstance(schema, dict):
            clean: Dict[str, Any] = {}
            for key, value in schema.items():
                if key in unsupported_keys:
                    continue
                clean[key] = ScoringEngine._sanitize_schema_for_gemini(value)
            return clean
        if isinstance(schema, list):
            return [ScoringEngine._sanitize_schema_for_gemini(item) for item in schema]
        return schema

    @staticmethod
    def _build_slot_hints_schema_from_config(deterministic_config: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(deterministic_config, dict):
            return {"type": "object"}

        explicit = deterministic_config.get("slot_hints_schema")
        if isinstance(explicit, dict):
            base = dict(explicit)
            base.setdefault("type", "object")
            return base

        properties: Dict[str, Any] = {}
        slots = deterministic_config.get("slots") or {}
        if isinstance(slots, dict):
            for slot_key, slot_cfg in slots.items():
                if not slot_key:
                    continue
                values = set()
                if isinstance(slot_cfg, dict):
                    if slot_cfg.get("default") is not None:
                        values.add(str(slot_cfg.get("default")))
                    for rule in slot_cfg.get("rules") or []:
                        if isinstance(rule, dict) and rule.get("set") is not None:
                            values.add(str(rule.get("set")))
                prop: Dict[str, Any] = {"type": "string"}
                if values:
                    prop["enum"] = sorted(values)
                properties[str(slot_key)] = prop

        for rule in deterministic_config.get("derived_slots") or []:
            if not isinstance(rule, dict):
                continue
            slot_key = str(rule.get("slot") or "").strip()
            if not slot_key:
                continue
            prop = properties.get(slot_key, {"type": "string"})
            values = set(prop.get("enum") or [])
            if rule.get("default") is not None:
                values.add(str(rule.get("default")))
            for thr in rule.get("thresholds") or []:
                if isinstance(thr, dict) and thr.get("set") is not None:
                    values.add(str(thr.get("set")))
            for key_name in ("high_value", "medium_value", "low_value"):
                if rule.get(key_name) is not None:
                    values.add(str(rule.get(key_name)))
            mapping = rule.get("mapping")
            if isinstance(mapping, dict):
                for mapped in mapping.values():
                    values.add(str(mapped))
            if values:
                prop["enum"] = sorted(values)
            properties[slot_key] = prop

        if not properties:
            return {"type": "object"}
        return {"type": "object", "properties": properties}


scoring_engine = ScoringEngine()
