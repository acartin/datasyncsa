from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.services.llm_service import llm_service
from app.services.response_contracts_loader import response_contracts_loader


class LeadFollowupPlanner:
    def __init__(self) -> None:
        contracts = response_contracts_loader.get_section("lead_followup_planner")
        self._field_goal_map = {
            str(key).strip(): str(value).strip()
            for key, value in (contracts.get("field_goal_map") or {}).items()
        }
        self._capture_goals = set(contracts.get("capture_goals") or [])
        self._capture_goal_priority = list(contracts.get("capture_goal_priority") or [])
        self._default_capture_questions = {
            str(key).strip(): str(value).strip()
            for key, value in (contracts.get("default_capture_questions") or {}).items()
        }
        self._blocked_statuses = {str(item).strip().lower() for item in (contracts.get("blocked_statuses") or [])}
        self._first_cards_capture_goal = str(contracts.get("first_cards_capture_goal") or "capture_name").strip()
        self._min_turn_gap_between_capture_attempts = int(contracts.get("min_turn_gap_between_capture_attempts") or 2)
        self._first_cards_capture_wait_turns = int(contracts.get("first_cards_capture_wait_turns") or 0)
        self._require_cards_before_capture = bool(contracts.get("require_cards_before_capture", True))
        self._meaningless_value_markers = {
            str(item).strip().casefold() for item in (contracts.get("meaningless_value_markers") or [])
        }

    def _default_progression_state(self) -> Dict[str, Any]:
        return {
            "name": {"status": "missing", "value": None},
            "email": {"status": "missing", "value": None},
            "phone": {"status": "missing", "value": None},
            "budget": {"status": "missing", "value": None},
            "urgency": {"status": "missing", "value": None},
            "agent_contact_consent": {"status": "missing", "value": None},
            "appointment_status": "not_started",
            "appointment_window": {"status": "missing", "value": None},
            "free_preference": {"status": "missing", "value": None},
            "next_goal": None,
            "last_asked_field": None,
            "has_shown_cards": False,
            "capture_attempt_count": 0,
            "assistant_turns_since_last_capture_attempt": 999,
            "assistant_turns_since_first_cards_shown": 999,
            "last_capture_goal": None,
        }

    async def plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        tenant_runtime = state.get("tenant_runtime") or {}
        prompts = tenant_runtime.get("prompts") or {}
        prompt = prompts.get("lead_followup_planner")
        if not prompt:
            return self._fallback(state)

        current_components = state.get("components") or []
        last_result_set = state.get("last_result_set") or {}
        current_progression = state.get("lead_progression_state") or self._default_progression_state()
        previous_cards_seen = bool(current_progression.get("has_shown_cards"))
        shown_cards_ever = bool(previous_cards_seen or current_components)
        first_cards_shown_now = bool(current_components) and not previous_cards_seen
        payload = {
            "user_text": state.get("query_text") or "",
            "vertical_slug": state.get("vertical_slug") or "generic",
            "active_subflow": state.get("active_subflow") or "generic_answer",
            "conversation_memory": state.get("conversation_memory") or {"common": {}, "vertical": {}},
            "lead_progression_state": current_progression,
            "execution_facts": state.get("execution_facts") or {},
            "last_result_set": last_result_set,
            "current_status": str(last_result_set.get("status") or "").strip().lower(),
            "components_count": len(current_components),
            "current_turn_has_components": bool(current_components),
            "previous_cards_seen": previous_cards_seen,
            "has_shown_cards_ever": shown_cards_ever,
            "first_cards_shown_now": first_cards_shown_now,
            "current_turn_visible_count": len(current_components),
            "current_turn_total_matches": int(last_result_set.get("total_matches") or 0),
            "capture_attempt_count": self._safe_int(current_progression.get("capture_attempt_count"), default=0),
            "assistant_turns_since_last_capture_attempt": self._safe_int(
                current_progression.get("assistant_turns_since_last_capture_attempt"),
                default=999,
            ),
            "assistant_turns_since_first_cards_shown": self._safe_int(
                current_progression.get("assistant_turns_since_first_cards_shown"),
                default=999,
            ),
            "history_excerpt": self._history_excerpt(state.get("history") or []),
            "conversation_extraction_result": state.get("conversation_extraction_result") or {},
        }
        try:
            raw_plan = await llm_service.generate_json(
                system_instruction=prompt,
                payload=payload,
                temperature=0.1,
                max_output_tokens=900,
            )
            return self._normalize_plan(raw_plan, state)
        except Exception:
            return self._fallback(state)

    def _normalize_plan(self, raw_plan: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        plan = raw_plan if isinstance(raw_plan, dict) else {}
        memory_updates = plan.get("memory_updates") if isinstance(plan.get("memory_updates"), dict) else {}
        common_updates = memory_updates.get("common") if isinstance(memory_updates.get("common"), dict) else {}
        vertical_updates = memory_updates.get("vertical") if isinstance(memory_updates.get("vertical"), dict) else {}

        followup_goal = str(plan.get("followup_goal") or "none").strip() or "none"
        should_ask = bool(plan.get("should_ask"))
        question = str(plan.get("question") or "").strip() or None
        cta_type = str(plan.get("cta_type") or "none").strip() or "none"
        reasoning = str(plan.get("reasoning") or "").strip() or None

        common_memory = dict((state.get("conversation_memory") or {}).get("common") or {})
        common_memory.update({key: value for key, value in common_updates.items() if value not in (None, "")})
        vertical_memory = dict((state.get("conversation_memory") or {}).get("vertical") or {})
        vertical_memory.update({key: value for key, value in vertical_updates.items() if value not in (None, "")})

        current_progression = state.get("lead_progression_state") or {}
        previous_cards_seen = bool(current_progression.get("has_shown_cards"))
        first_cards_shown_now = bool(state.get("components")) and not previous_cards_seen
        shown_cards_ever = bool(previous_cards_seen or state.get("components"))
        capture_attempt_count = self._safe_int(current_progression.get("capture_attempt_count"), default=0)
        turns_since_capture = self._safe_int(
            current_progression.get("assistant_turns_since_last_capture_attempt"),
            default=999,
        )
        turns_since_first_cards_shown = self._safe_int(
            current_progression.get("assistant_turns_since_first_cards_shown"),
            default=999,
        )
        current_status = str((state.get("last_result_set") or {}).get("status") or "").strip().lower()
        is_capture_attempt = followup_goal in self._capture_goals and should_ask and bool(question)
        is_followup_attempt = should_ask and bool(question)
        if first_cards_shown_now and is_followup_attempt:
            followup_goal = "none"
            should_ask = False
            question = None
            cta_type = "none"
            if is_capture_attempt:
                reasoning = "capture_blocked_on_first_cards_turn"
            else:
                reasoning = "followup_blocked_on_first_cards_turn"
        is_capture_attempt = followup_goal in self._capture_goals and should_ask and bool(question)
        capture_allowed = (shown_cards_ever or not self._require_cards_before_capture) and (
            capture_attempt_count == 0 or turns_since_capture >= self._min_turn_gap_between_capture_attempts
        )
        if is_capture_attempt and (not capture_allowed or current_status == "empty"):
            followup_goal = "none"
            should_ask = False
            question = None
            cta_type = "none"
            if current_status == "empty":
                reasoning = "capture_blocked_on_empty_results"
            elif not shown_cards_ever:
                reasoning = "capture_blocked_until_cards_are_shown"
            else:
                reasoning = "capture_delayed_until_two_turns_after_last_attempt"
        is_capture_attempt = followup_goal in self._capture_goals and should_ask and bool(question)

        progression_override = self._recommended_capture_goal(
            common_memory=common_memory,
            progression=current_progression,
            shown_cards_ever=shown_cards_ever,
            first_cards_shown_now=first_cards_shown_now,
            turns_since_first_cards_shown=turns_since_first_cards_shown,
            capture_allowed=capture_allowed,
            current_status=current_status,
            current_followup_goal=followup_goal,
        )
        if progression_override:
            followup_goal = progression_override
            should_ask = True
            question = self._default_capture_questions.get(progression_override)
            cta_type = "soft_question"
            reasoning = f"progression_override:{progression_override}"
            is_capture_attempt = True

        progression = self._merge_progression_state(
            current_progression,
            common_memory,
            followup_goal,
            should_ask,
            shown_cards_ever=shown_cards_ever,
            current_turn_has_components=bool(state.get("components")),
            capture_attempted=is_capture_attempt,
        )

        return {
            "memory_updates": {
                "common": common_updates,
                "vertical": vertical_updates,
            },
            "conversation_memory": {
                "common": common_memory,
                "vertical": vertical_memory,
            },
            "lead_progression_state": progression,
            "followup_goal": followup_goal,
            "should_ask": should_ask and bool(question),
            "question": question,
            "cta_type": cta_type,
            "reasoning": reasoning,
        }

    def _merge_progression_state(
        self,
        current: Dict[str, Any],
        common_memory: Dict[str, Any],
        followup_goal: str,
        should_ask: bool,
        *,
        shown_cards_ever: bool,
        current_turn_has_components: bool,
        capture_attempted: bool,
    ) -> Dict[str, Any]:
        merged = self._default_progression_state()
        for key, value in current.items():
            merged[key] = value

        now = datetime.now(timezone.utc).isoformat()
        for field in ("name", "email", "phone", "budget", "urgency", "agent_contact_consent", "appointment_window", "free_preference"):
            existing = merged.get(field) if isinstance(merged.get(field), dict) else {"status": "missing", "value": None}
            if self._has_meaningful_value(common_memory.get(field)):
                merged[field] = {
                    "status": "provided",
                    "value": common_memory.get(field),
                    "source": "conversation_memory",
                    "updated_at": now,
                }
            else:
                merged[field] = {
                    "status": existing.get("status") or "missing",
                    "value": existing.get("value"),
                    "source": existing.get("source"),
                    "updated_at": existing.get("updated_at"),
                }

        if followup_goal in self._field_goal_map and should_ask:
            field_name = self._field_goal_map[followup_goal]
            field_state = merged.get(field_name) if isinstance(merged.get(field_name), dict) else {"status": "missing", "value": None}
            if field_state.get("status") != "provided":
                field_state["status"] = "asked"
            field_state.setdefault("updated_at", now)
            merged[field_name] = field_state
            merged["last_asked_field"] = field_name

        merged["next_goal"] = followup_goal if followup_goal != "none" else None
        merged["has_shown_cards"] = bool(shown_cards_ever)
        if current_turn_has_components:
            merged["assistant_turns_since_first_cards_shown"] = 0
        elif shown_cards_ever:
            merged["assistant_turns_since_first_cards_shown"] = (
                self._safe_int(merged.get("assistant_turns_since_first_cards_shown"), default=999) + 1
            )
        else:
            merged["assistant_turns_since_first_cards_shown"] = 999
        previous_attempts = self._safe_int(merged.get("capture_attempt_count"), default=0)
        previous_turns = self._safe_int(
            merged.get("assistant_turns_since_last_capture_attempt"),
            default=999,
        )
        if capture_attempted:
            merged["capture_attempt_count"] = previous_attempts + 1
            merged["assistant_turns_since_last_capture_attempt"] = 0
            merged["last_capture_goal"] = followup_goal
        elif previous_attempts > 0:
            merged["capture_attempt_count"] = previous_attempts
            merged["assistant_turns_since_last_capture_attempt"] = previous_turns + 1
            merged["last_capture_goal"] = merged.get("last_capture_goal")
        else:
            merged["capture_attempt_count"] = previous_attempts
            merged["assistant_turns_since_last_capture_attempt"] = previous_turns
        if not merged.get("appointment_status"):
            merged["appointment_status"] = "not_started"
        return merged

    def _fallback(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current_memory = state.get("conversation_memory") or {"common": {}, "vertical": {}}
        current_progression = state.get("lead_progression_state") or {}
        shown_cards_ever = bool(
            current_progression.get("has_shown_cards")
            or state.get("components")
            or state.get("last_shown_components")
        )
        progression = self._merge_progression_state(
            current_progression,
            dict(current_memory.get("common") or {}),
            "none",
            False,
            shown_cards_ever=shown_cards_ever,
            current_turn_has_components=bool(state.get("components")),
            capture_attempted=False,
        )
        return {
            "memory_updates": {"common": {}, "vertical": {}},
            "conversation_memory": {
                "common": dict(current_memory.get("common") or {}),
                "vertical": dict(current_memory.get("vertical") or {}),
            },
            "lead_progression_state": progression,
            "followup_goal": "none",
            "should_ask": False,
            "question": None,
            "cta_type": "none",
            "reasoning": None,
        }

    def _recommended_capture_goal(
        self,
        *,
        common_memory: Dict[str, Any],
        progression: Dict[str, Any],
        shown_cards_ever: bool,
        first_cards_shown_now: bool,
        turns_since_first_cards_shown: int,
        capture_allowed: bool,
        current_status: str,
        current_followup_goal: str,
    ) -> str | None:
        if not shown_cards_ever or not capture_allowed:
            return None
        if first_cards_shown_now:
            return None
        if turns_since_first_cards_shown < self._first_cards_capture_wait_turns:
            return None
        if current_status in self._blocked_statuses:
            return None
        name_missing = not self._has_meaningful_value(common_memory.get("name"))
        if current_followup_goal in self._capture_goals:
            return None

        for goal in self._capture_goal_priority:
            if goal == "capture_name" and name_missing:
                return goal
            if goal == "capture_budget" and not self._has_meaningful_value(common_memory.get("budget")):
                return goal
            if goal == "capture_urgency" and not self._has_meaningful_value(common_memory.get("urgency")):
                return goal
            if goal == "offer_agent_contact" and not self._has_meaningful_value(common_memory.get("agent_contact_consent")):
                return goal
            if goal == "capture_email" and not self._has_meaningful_value(common_memory.get("email")):
                return goal
            if goal == "capture_phone" and not self._has_meaningful_value(common_memory.get("phone")):
                return goal
            if goal == "offer_appointment":
                appointment_status = str(progression.get("appointment_status") or "not_started").strip().lower()
                if appointment_status in {"", "not_started"}:
                    return goal
        return None

    @staticmethod
    def _history_excerpt(history: list[Dict[str, Any]], limit: int = 6) -> list[Dict[str, Any]]:
        excerpt = []
        for item in history[-limit:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if role and content:
                excerpt.append({"role": role, "content": content})
        return excerpt

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _has_meaningful_value(self, value: Any) -> bool:
        if value in (None, ""):
            return False
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if not normalized:
                return False
            if normalized in self._meaningless_value_markers:
                return False
        return True


lead_followup_planner = LeadFollowupPlanner()
