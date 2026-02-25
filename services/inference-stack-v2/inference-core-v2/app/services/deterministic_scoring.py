import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


class DeterministicScoringService:
    """
    Config-driven deterministic scoring service.

    All business rules (tokens, slot mapping, criterion mapping) are loaded from
    prompt_config.extraction_schema.deterministic_scoring.
    """

    def evaluate(
        self,
        *,
        conversation_text: str,
        extracted_data: Dict[str, Any],
        criteria: List[Dict[str, Any]],
        deterministic_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        config = deterministic_config if isinstance(deterministic_config, dict) else {}
        if not config:
            raise ValueError("DETERMINISTIC_CONFIG_EMPTY")

        normalized_conversation = self._normalize_text(conversation_text or "")
        normalized_fields = self._normalize_extracted_fields(extracted_data or {})

        slots = self._evaluate_slots(
            conversation_text=conversation_text or "",
            normalized_conversation=normalized_conversation,
            extracted_data=extracted_data or {},
            normalized_fields=normalized_fields,
            config=config,
        )
        scores, explanations = self._evaluate_criteria(
            slots=slots,
            criteria=criteria,
            config=config,
        )

        return {
            "slot_state": slots,
            "scores": scores,
            "explanations": explanations,
            "reasoning": self._build_reasoning(slots),
        }

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return ascii_text.lower()

    def _normalize_extracted_fields(self, extracted_data: Dict[str, Any]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key, value in extracted_data.items():
            if value is None:
                continue
            normalized[str(key)] = self._normalize_text(str(value))
        return normalized

    def _evaluate_slots(
        self,
        *,
        conversation_text: str,
        normalized_conversation: str,
        extracted_data: Dict[str, Any],
        normalized_fields: Dict[str, str],
        config: Dict[str, Any],
    ) -> Dict[str, str]:
        slot_defs = config.get("slots") or {}
        if not isinstance(slot_defs, dict) or not slot_defs:
            raise ValueError("DETERMINISTIC_CONFIG_SLOTS_MISSING")

        slots: Dict[str, str] = {}
        for slot_key, slot_cfg in slot_defs.items():
            if not isinstance(slot_cfg, dict):
                continue
            default_value = str(slot_cfg.get("default", "unknown"))
            slots[str(slot_key)] = default_value

        # Base slot rules.
        for slot_key, slot_cfg in slot_defs.items():
            if not isinstance(slot_cfg, dict):
                continue
            for rule in slot_cfg.get("rules") or []:
                if not isinstance(rule, dict):
                    continue
                if self._match_rule(
                    rule=rule,
                    conversation_text=conversation_text,
                    normalized_conversation=normalized_conversation,
                    extracted_data=extracted_data,
                    normalized_fields=normalized_fields,
                    slots=slots,
                ):
                    slots[str(slot_key)] = str(rule.get("set", slots.get(str(slot_key), "unknown")))
                    if bool(rule.get("stop", True)):
                        break

        # Derived slots run after base slots.
        for derived in config.get("derived_slots") or []:
            if not isinstance(derived, dict):
                continue
            slot_key = str(derived.get("slot") or "").strip()
            if not slot_key:
                continue
            computed = self._compute_derived_slot(
                rule=derived,
                conversation_text=conversation_text,
                normalized_conversation=normalized_conversation,
                extracted_data=extracted_data,
                normalized_fields=normalized_fields,
                slots=slots,
            )
            if computed is not None:
                slots[slot_key] = str(computed)

        return slots

    def _match_rule(
        self,
        *,
        rule: Dict[str, Any],
        conversation_text: str,
        normalized_conversation: str,
        extracted_data: Dict[str, Any],
        normalized_fields: Dict[str, str],
        slots: Dict[str, str],
    ) -> bool:
        source_text = self._resolve_rule_source_text(
            rule=rule,
            conversation_text=conversation_text,
            normalized_conversation=normalized_conversation,
            extracted_data=extracted_data,
            normalized_fields=normalized_fields,
        )

        contains_any = [self._normalize_text(str(v)) for v in (rule.get("contains_any") or [])]
        if contains_any and not any(token and token in source_text for token in contains_any):
            return False

        contains_all = [self._normalize_text(str(v)) for v in (rule.get("contains_all") or [])]
        if contains_all and not all(token and token in source_text for token in contains_all):
            return False

        regex = rule.get("regex")
        if regex:
            try:
                if not re.search(str(regex), source_text, re.IGNORECASE):
                    return False
            except re.error:
                return False

        if bool(rule.get("has_number", False)):
            if self._extract_first_number(source_text) is None:
                return False

        slot_equals = rule.get("slot_equals")
        if slot_equals:
            if not isinstance(slot_equals, dict):
                return False
            slot_name = str(slot_equals.get("slot") or "")
            expected = slot_equals.get("value")
            any_of = slot_equals.get("any_of")
            current = slots.get(slot_name)
            if expected is not None and current != str(expected):
                return False
            if isinstance(any_of, list) and current not in [str(v) for v in any_of]:
                return False

        return True

    def _resolve_rule_source_text(
        self,
        *,
        rule: Dict[str, Any],
        conversation_text: str,
        normalized_conversation: str,
        extracted_data: Dict[str, Any],
        normalized_fields: Dict[str, str],
    ) -> str:
        source_field = rule.get("source_field")
        if source_field:
            return normalized_fields.get(str(source_field), "")

        source = str(rule.get("source", "conversation_text"))
        if source == "conversation_text":
            return normalized_conversation
        if source.startswith("field:"):
            field = source.split(":", 1)[1].strip()
            return normalized_fields.get(field, "")
        if source in {"raw_conversation", "conversation_raw"}:
            return self._normalize_text(conversation_text)
        # Unknown source defaults to normalized conversation.
        return normalized_conversation

    def _compute_derived_slot(
        self,
        *,
        rule: Dict[str, Any],
        conversation_text: str,
        normalized_conversation: str,
        extracted_data: Dict[str, Any],
        normalized_fields: Dict[str, str],
        slots: Dict[str, str],
    ) -> Optional[str]:
        derived_type = str(rule.get("type") or "").strip().lower()
        default_value = str(rule.get("default", "unknown"))

        if derived_type == "map_from_slot":
            source_slot = str(rule.get("source_slot") or "")
            mapping = rule.get("mapping") or {}
            source_value = slots.get(source_slot)
            if source_value is None:
                return default_value
            return str(mapping.get(source_value, default_value))

        if derived_type == "count_present_fields":
            fields = [str(f) for f in (rule.get("fields") or [])]
            count = 0
            for field in fields:
                raw_value = extracted_data.get(field)
                if raw_value is None:
                    continue
                if isinstance(raw_value, str) and not raw_value.strip():
                    continue
                count += 1
            return self._map_count_to_value(
                count=count,
                thresholds=rule.get("thresholds") or [],
                default_value=default_value,
            )

        if derived_type == "keyword_bucket_count":
            bucket_count = 0
            for bucket in rule.get("buckets") or []:
                if not isinstance(bucket, dict):
                    continue
                matched = False
                contains_any = [self._normalize_text(str(v)) for v in (bucket.get("contains_any") or [])]
                if contains_any and any(token and token in normalized_conversation for token in contains_any):
                    matched = True

                slot_condition = bucket.get("slot_condition")
                if isinstance(slot_condition, dict):
                    slot_name = str(slot_condition.get("slot") or "")
                    current = slots.get(slot_name)
                    expected = slot_condition.get("value")
                    any_of = slot_condition.get("any_of")
                    if expected is not None and current == str(expected):
                        matched = True
                    if isinstance(any_of, list) and current in [str(v) for v in any_of]:
                        matched = True
                if matched:
                    bucket_count += 1

            return self._map_count_to_value(
                count=bucket_count,
                thresholds=rule.get("thresholds") or [],
                default_value=default_value,
            )

        if derived_type == "engagement_blend":
            fields = [str(f) for f in (rule.get("fields") or [])]
            field_count = 0
            for field in fields:
                raw_value = extracted_data.get(field)
                if raw_value is None:
                    continue
                if isinstance(raw_value, str) and not raw_value.strip():
                    continue
                field_count += 1

            user_turns = self._count_user_turns(conversation_text)
            text_chars = len(conversation_text or "")

            if (
                user_turns >= int(rule.get("user_turns_high", 4))
                or field_count >= int(rule.get("field_count_high", 4))
                or text_chars >= int(rule.get("text_chars_high", 600))
            ):
                return str(rule.get("high_value", "high"))
            if (
                user_turns >= int(rule.get("user_turns_medium", 2))
                or field_count >= int(rule.get("field_count_medium", 2))
                or text_chars >= int(rule.get("text_chars_medium", 250))
            ):
                return str(rule.get("medium_value", "medium"))
            return str(rule.get("low_value", default_value))

        return default_value

    @staticmethod
    def _map_count_to_value(
        *,
        count: int,
        thresholds: List[Dict[str, Any]],
        default_value: str,
    ) -> str:
        valid_thresholds: List[Tuple[int, str]] = []
        for item in thresholds:
            if not isinstance(item, dict):
                continue
            try:
                minimum = int(item.get("min"))
            except Exception:
                continue
            value = str(item.get("set", default_value))
            valid_thresholds.append((minimum, value))
        valid_thresholds.sort(key=lambda t: t[0], reverse=True)
        for minimum, value in valid_thresholds:
            if count >= minimum:
                return value
        return default_value

    def _evaluate_criteria(
        self,
        *,
        slots: Dict[str, str],
        criteria: List[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> Tuple[Dict[str, float], Dict[str, str]]:
        criteria_rules = config.get("criteria_rules") or {}
        if not isinstance(criteria_rules, dict) or not criteria_rules:
            raise ValueError("DETERMINISTIC_CONFIG_CRITERIA_RULES_MISSING")

        scores: Dict[str, float] = {}
        explanations: Dict[str, str] = {}

        for criterion in criteria or []:
            criterion_key = str(criterion.get("criterion_key") or "").strip()
            if not criterion_key:
                continue

            rule = criteria_rules.get(criterion_key)
            if not isinstance(rule, dict):
                raise ValueError(f"DETERMINISTIC_RULE_MISSING_FOR_CRITERION:{criterion_key}")

            raw_score, explanation = self._score_from_rule(criterion_key=criterion_key, rule=rule, slots=slots)
            min_score = float(criterion.get("min_score", 0.0))
            max_score = float(criterion.get("max_score", 10.0))
            scaled = self._scale_score(raw_score, min_score, max_score)
            scores[criterion_key] = scaled
            explanations[criterion_key] = explanation

        return scores, explanations

    def _score_from_rule(
        self,
        *,
        criterion_key: str,
        rule: Dict[str, Any],
        slots: Dict[str, str],
    ) -> Tuple[float, str]:
        rule_type = str(rule.get("type") or "").strip().lower()
        default_score = float(rule.get("default", 0.0))

        if rule_type == "slot_map":
            slot_name = str(rule.get("slot") or "")
            if not slot_name:
                return default_score, f"{criterion_key}: slot_map missing slot; default applied."
            slot_value = slots.get(slot_name, "unknown")
            mapping = rule.get("mapping") or {}
            score = float(mapping.get(slot_value, default_score))
            return score, f"{criterion_key} from slot {slot_name}={slot_value}."

        if rule_type == "matrix":
            slot_names = [str(v) for v in (rule.get("slots") or [])]
            if not slot_names:
                return default_score, f"{criterion_key}: matrix missing slots; default applied."
            separator = str(rule.get("separator", "|"))
            key_parts = [slots.get(slot, "unknown") for slot in slot_names]
            matrix_key = separator.join(key_parts)
            mapping = rule.get("mapping") or {}
            score = float(mapping.get(matrix_key, default_score))
            return score, f"{criterion_key} from matrix key {matrix_key}."

        return default_score, f"{criterion_key}: unknown rule type {rule_type}; default applied."

    @staticmethod
    def _scale_score(raw_0_10: float, min_score: float, max_score: float) -> float:
        if max_score <= min_score:
            return float(min_score)
        clamped = max(0.0, min(10.0, float(raw_0_10)))
        mapped = min_score + (clamped / 10.0) * (max_score - min_score)
        return float(round(mapped, 4))

    @staticmethod
    def _extract_first_number(text: str) -> Optional[float]:
        match = re.search(r"(\d[\d,.\s]{1,20})", text or "")
        if not match:
            return None
        raw = match.group(1).replace(" ", "").replace(",", "")
        try:
            return float(raw)
        except Exception:
            return None

    @staticmethod
    def _count_user_turns(conversation_text: str) -> int:
        turns = 0
        for raw_line in (conversation_text or "").splitlines():
            if raw_line.strip().lower().startswith("usuario:"):
                turns += 1
        return turns

    @staticmethod
    def _build_reasoning(slots: Dict[str, str]) -> str:
        ordered = sorted((slots or {}).items(), key=lambda x: x[0])
        pairs = ", ".join([f"{k}={v}" for k, v in ordered])
        return f"Deterministic slot state: {pairs}."


deterministic_scoring_service = DeterministicScoringService()
