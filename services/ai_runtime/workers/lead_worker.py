"""Fire-and-forget lead worker placeholder for v1."""

from __future__ import annotations

from services.ai_runtime.config.prompt_composer import compose
from services.ai_runtime.domain.contracts import LeadExtracted, LeadScores
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState


class LeadWorker:
    """Evaluates the latest turn without blocking the main assistant flow."""

    def __init__(self, dependencies: GraphDependencies):
        self.dependencies = dependencies

    async def process(self, state: BaseGraphState) -> None:
        prompt = compose(
            "lead_data_collector",
            state.tenant_config,
            state.vertical,
            {
                "messages": [message.model_dump(mode="json") for message in state.messages[-8:]],
                "policy": {
                    "recency_policy": "latest_user_turn_priority",
                    "negation_policy": "explicit_negation_overrides_positive",
                    "missing_evidence_default": {"min": 1, "max": 2},
                },
                "task": "Score the turn and extract lead fields.",
            },
        )
        result = await self.dependencies.llm.score_turn(prompt)
        scores = LeadScores(
            apertura=float(result.get("apertura", 1)),
            intencion=float(result.get("intencion", 1)),
            urgencia=float(result.get("urgencia", 1)),
            match=float(result.get("match", 1)),
            solvencia=float(result.get("solvencia", 1)),
        )
        extracted = LeadExtracted.model_validate(result.get("fields", {}))
        await self.dependencies.lead_store.set_lead_state(
            state.client_id,
            state.session_id,
            {
                "lead_scores": scores.model_dump(mode="json"),
                "lead_extracted": extracted.model_dump(mode="json"),
            },
            state.tenant_config.redis_ttl_seconds,
        )

