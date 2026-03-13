from __future__ import annotations

from typing import Any, Dict

from pydantic import ValidationError

from app.core.config import settings
from app.core.llm_client import llm_service
from app.core.llm_contract_normalizer import normalize_router_decision
from app.core.prompt_service import prompt_service
from app.models.contracts import RouterDecision


class PlannerService:
    async def run(
        self,
        *,
        raw_input: Dict[str, Any],
        normalized_input: Dict[str, Any],
        history: list[Dict[str, Any]],
    ) -> RouterDecision:
        tenant_id = str(raw_input.get("tenant_id") or raw_input.get("clientId") or "default").strip()
        vertical = str(raw_input.get("vertical") or normalized_input.get("vertical") or "generic").strip()
        channel = str(raw_input.get("channel") or "web_html").strip()

        prompts = await prompt_service.resolve_prompts(
            tenant_id=tenant_id,
            vertical=vertical,
            channel=channel,
        )

        payload = {
            "query_text": raw_input.get("queryText") or raw_input.get("text") or "",
            "history": history[-10:],
            "normalized_input": normalized_input,
            "context_snapshot": {
                "conversation_summary": normalized_input.get("conversation_summary", ""),
                "vertical": vertical,
                "conversation_state": normalized_input.get("conversation_state", {}),
            },
            "tenant_id": tenant_id,
            "channel": channel,
            "contract": {
                "goal": "answer|clarify|rag|realtor_search|realtor_refine|workflow",
                "confidence": "float 0..1",
                "tool_calls": "optional tool calls",
                "missing_slots": "list",
                "clarify_message": "required when goal=clarify",
                "response_mode": "text_only|text_plus_cards",
            },
        }

        raw = await llm_service.generate_json(
            system_instruction=prompts.planner_system_prompt,
            payload=payload,
            temperature=0.1,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        normalized = normalize_router_decision(raw)

        try:
            return RouterDecision.model_validate(normalized)
        except ValidationError as exc:
            raise ValueError(f"planner_output_invalid:{exc}") from exc


planner_service = PlannerService()
