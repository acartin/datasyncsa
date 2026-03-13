from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contracts import ScoreConversationRequest, ScoreItemV2, ScorecardV2
from app.repositories.scoring_repository import ScoringRepository
from app.services.cache_service import cache_service
from app.services.scoring_job_service import ScoringJobService

logger = logging.getLogger("scoring-core.orchestrator")


class ScoringOrchestrator:
    """
    Scoring domain orchestrator.
    Owns model/prompt resolution, job enqueue and scorecard views.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repo = ScoringRepository(db_session)
        self.job_service = ScoringJobService(self.repo)

    async def resolve_vertical_for_client(self, client_id: UUID) -> Dict[str, Any]:
        vertical_ctx = await self.repo.get_client_vertical_context(client_id)
        if not vertical_ctx or not vertical_ctx.get("client_exists"):
            raise ValueError("CLIENT_NOT_FOUND")
        if vertical_ctx.get("vertical_id") is None:
            raise ValueError("TENANT_VERTICAL_NOT_CONFIGURED")
        if vertical_ctx.get("scoring_model_id") is None:
            raise ValueError("TENANT_SCORING_MODEL_NOT_CONFIGURED")
        return vertical_ctx

    async def get_active_scoring_model(
        self,
        *,
        client_id: UUID,
        vertical_id: int,
        scoring_model_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        cached = await cache_service.get_active_model(client_id)
        if cached:
            return cached

        model_data = await self.repo.get_active_scoring_model(
            vertical_id=vertical_id,
            scoring_model_id=scoring_model_id,
        )
        if not model_data:
            return None

        await cache_service.set_active_model(client_id, model_data)
        return model_data

    async def get_or_create_prompt(
        self,
        *,
        model_data: Dict[str, Any],
        client_id: UUID,
    ) -> Dict[str, Any]:
        model_id = UUID(str(model_data["id"]))
        cached_prompt = await cache_service.get_scoring_prompt(client_id=client_id, model_id=model_id)
        if cached_prompt:
            return cached_prompt

        prompt_config = await self.repo.get_active_prompt(model_id)
        if not prompt_config:
            raise ValueError(f"No active prompt found for model {model_id}")

        await cache_service.set_scoring_prompt(
            client_id=client_id,
            model_id=model_id,
            prompt_data=prompt_config,
        )
        return prompt_config

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): ScoringOrchestrator._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [ScoringOrchestrator._json_safe(v) for v in value]
        return value

    @staticmethod
    def _channel_to_platform(channel: Optional[str]) -> str:
        raw = str(channel or "").strip().lower()
        if raw in {"web_html", "api", "web", "webchat"}:
            return "webchat"
        if raw in {"meta_whatsapp", "whatsapp"}:
            return "whatsapp"
        if raw in {"meta_ig", "instagram"}:
            return "instagram"
        if raw in {"messenger", "meta_messenger"}:
            return "messenger"
        if raw in {"telegram", "meta_telegram"}:
            return "telegram"
        return "webchat"

    def _build_scoring_context_snapshot(
        self,
        *,
        vertical_ctx: Dict[str, Any],
        model_data: Dict[str, Any],
        prompt_config: Dict[str, Any],
        channel: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "vertical_ctx": self._json_safe(vertical_ctx or {}),
            "model_data": self._json_safe(model_data or {}),
            "scoring_prompt": self._json_safe(prompt_config or {}),
            "scoring_context": {
                "channel": str(channel or ""),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    async def resolve_scoring_context_for_job(
        self,
        *,
        client_id: UUID,
        conversation_id: UUID,
        model_id: Optional[UUID],
        prompt_id: Optional[UUID],
    ) -> Dict[str, Any]:
        snapshot = await self.repo.get_conversation_context_snapshot(
            conversation_id=conversation_id,
            client_id=client_id,
        )
        if not isinstance(snapshot, dict):
            snapshot = {}

        vertical_ctx = snapshot.get("vertical_ctx") or {}
        model_data = snapshot.get("model_data") or {}
        prompt_config = snapshot.get("scoring_prompt") or {}
        if vertical_ctx and model_data and prompt_config:
            return {
                "vertical_ctx": vertical_ctx,
                "model_data": model_data,
                "prompt_config": prompt_config,
            }

        vertical_ctx = await self.resolve_vertical_for_client(client_id)
        vertical_id = int(vertical_ctx["vertical_id"])
        preferred_model = model_id or (
            UUID(str(vertical_ctx["scoring_model_id"]))
            if vertical_ctx.get("scoring_model_id")
            else None
        )
        model_data = await self.get_active_scoring_model(
            client_id=client_id,
            vertical_id=vertical_id,
            scoring_model_id=preferred_model,
        )
        if not model_data:
            raise ValueError(
                f"NO_ACTIVE_VERTICAL_SCORING_MODEL: vertical_id={vertical_id}, scoring_model_id={preferred_model}"
            )

        if prompt_id:
            prompt_config = await self.repo.get_prompt_by_id(prompt_id)
        if not prompt_config:
            prompt_config = await self.get_or_create_prompt(
                model_data=model_data,
                client_id=client_id,
            )

        return {
            "vertical_ctx": vertical_ctx,
            "model_data": model_data,
            "prompt_config": prompt_config,
        }

    async def enqueue_scoring_job(self, request: ScoreConversationRequest) -> Dict[str, Any]:
        conversation_id = request.conversation_id
        client_id = request.client_id
        requested_lead_id = request.lead_id

        existing_lead = await self.repo.get_lead_by_conversation_id(
            conversation_id=str(conversation_id),
            client_id=client_id,
        )
        lead_id = existing_lead or requested_lead_id
        lead_snapshot = await self.repo.get_lead_snapshot(lead_id=lead_id, client_id=client_id)
        if not lead_snapshot:
            raise ValueError("LEAD_NOT_FOUND_FOR_CLIENT")

        vertical_ctx = await self.resolve_vertical_for_client(client_id)
        vertical_id = int(vertical_ctx["vertical_id"])
        scoring_model_id = UUID(str(vertical_ctx["scoring_model_id"]))
        model_data = await self.get_active_scoring_model(
            client_id=client_id,
            vertical_id=vertical_id,
            scoring_model_id=scoring_model_id,
        )
        if not model_data:
            raise ValueError(
                f"NO_ACTIVE_VERTICAL_SCORING_MODEL: vertical_id={vertical_id}, scoring_model_id={scoring_model_id}"
            )
        prompt_config = await self.get_or_create_prompt(model_data=model_data, client_id=client_id)

        await self.repo.get_or_create_conversation(
            lead_id=lead_id,
            conversation_id=conversation_id,
            platform=self._channel_to_platform(request.channel),
        )

        existing_snapshot = await self.repo.get_conversation_context_snapshot(
            conversation_id=conversation_id,
            client_id=client_id,
        )
        snapshot_payload = dict(existing_snapshot or {})
        snapshot_payload.update(
            self._build_scoring_context_snapshot(
                vertical_ctx=vertical_ctx,
                model_data=model_data,
                prompt_config=prompt_config,
                channel=request.channel,
            )
        )
        await self.repo.set_conversation_context_snapshot(
            conversation_id=conversation_id,
            lead_id=lead_id,
            snapshot=snapshot_payload,
        )

        counters = await self.repo.get_conversation_message_counters(
            conversation_id=conversation_id,
            client_id=client_id,
        )
        expected_lead_messages = (counters or {}).get("lead_messages")
        model_id = UUID(str(model_data["id"])) if model_data.get("id") else None
        prompt_id = UUID(str(prompt_config["id"])) if prompt_config.get("id") else None

        return await self.job_service.enqueue_post_chat_scoring(
            lead_id=lead_id,
            conversation_id=conversation_id,
            client_id=client_id,
            expected_lead_messages=expected_lead_messages,
            model_id=model_id,
            prompt_id=prompt_id,
        )

    async def get_scoring_job_response(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        return await self.job_service.get_job(job_id)

    async def get_scoring_ops_summary(self, window_minutes: int = 60) -> Dict[str, Any]:
        bounded_window = max(5, min(1440, int(window_minutes or 60)))
        return await self.job_service.get_ops_summary(window_minutes=bounded_window)

    async def get_latest_scorecard_response(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        scorecard = await self.repo.get_latest_scorecard(lead_id)
        if not scorecard:
            return None
        return self._build_scorecard_response(scorecard)

    async def get_scorecard_response(self, scorecard_id: UUID) -> Optional[Dict[str, Any]]:
        scorecard = await self.repo.get_scorecard_with_items(scorecard_id)
        if not scorecard:
            return None
        return self._build_scorecard_response(scorecard)

    @staticmethod
    def _build_scorecard_response(scorecard: Dict[str, Any]) -> Dict[str, Any]:
        extraction_result = scorecard.get("extraction_result")
        if extraction_result is None:
            extraction_result = {}

        score_items = []
        for item in scorecard.get("score_items", []):
            score_items.append(
                {
                    "criterion_key": item.get("criterion_key"),
                    "score": item.get("score"),
                    "band_id": str(item.get("band_id")) if item.get("band_id") else None,
                    "explanation": item.get("explanation"),
                    "extracted_data": item.get("extracted_data"),
                    "created_at": item.get("created_at").isoformat() if item.get("created_at") else None,
                }
            )

        return {
            "id": str(scorecard.get("id")),
            "lead_id": str(scorecard.get("lead_id")),
            "conversation_id": str(scorecard.get("conversation_id")) if scorecard.get("conversation_id") else None,
            "model_id": str(scorecard.get("model_id")),
            "model_version": scorecard.get("model_version"),
            "prompt_version": scorecard.get("prompt_version"),
            "prompt_id": str(scorecard.get("prompt_id")) if scorecard.get("prompt_id") else None,
            "score_total": scorecard.get("score_total"),
            "priority_label": scorecard.get("priority_label"),
            "reasoning": scorecard.get("reasoning"),
            "extraction_result": extraction_result,
            "created_at": scorecard.get("created_at").isoformat() if scorecard.get("created_at") else None,
            "score_items": score_items,
        }

    @staticmethod
    def _format_user_only_history(messages: List[Dict[str, Any]]) -> str:
        if not messages:
            return ""
        lines: List[str] = []
        for item in messages:
            role = str((item or {}).get("role") or "").strip().lower()
            if role != "user":
                continue
            content = str((item or {}).get("content") or "").strip()
            if not content:
                continue
            lines.append(f"Usuario: {content}")
        return "\n".join(lines)

    def _build_scorecard_from_result(
        self,
        *,
        model_data: Dict[str, Any],
        result: Dict[str, Any],
    ) -> ScorecardV2:
        scores = result.get("scores", {})
        explanations = result.get("explanations", {})

        score_items = []
        total_score = 0.0
        total_weight = 0.0

        for criterion in model_data.get("criteria", []):
            criterion_key = criterion.get("criterion_key")
            score = scores.get(criterion_key, 0.0)

            min_score = float(criterion.get("min_score", 0))
            max_score = float(criterion.get("max_score", 10))
            score = min(max(float(score), min_score), max_score)

            band_key = None
            bands = criterion.get("bands", [])
            for idx, band in enumerate(bands):
                band_min = float(band.get("min_score", 0))
                band_max = float(band.get("max_score", 10))
                is_last_band = idx == len(bands) - 1
                epsilon = 0.001
                if score >= band_min - epsilon and (score < band_max or (is_last_band and score <= band_max + epsilon)):
                    band_key = band.get("band_key")
                    break

            explanation = explanations.get(criterion_key, f"Score for {criterion_key}")
            score_items.append(
                ScoreItemV2(
                    criterion_key=criterion_key,
                    score=score,
                    band_key=band_key,
                    explanation=explanation,
                    extracted_data=None,
                )
            )

            weight = float(criterion.get("weight", 1.0))
            total_score += score * weight
            total_weight += weight

        normalized_total = total_score / total_weight if total_weight > 0 else 0.0
        priority_label = "Media"
        if normalized_total >= 8.0:
            priority_label = "Alta"
        elif normalized_total <= 3.0:
            priority_label = "Baja"

        return ScorecardV2(
            score_total=normalized_total,
            priority_label=priority_label,
            reasoning=result.get("reasoning", ""),
            model_version=model_data.get("version", 1),
            prompt_version=1,
            score_items=score_items,
        )

    async def _create_scorecard_with_engine(
        self,
        *,
        repo: ScoringRepository,
        db_session: AsyncSession,
        lead_id: UUID,
        client_id: Optional[UUID],
        model_data: Dict[str, Any],
        scorecard_data: ScorecardV2,
        prompt_config: Dict[str, Any],
        result: Dict[str, Any],
        conversation_id: UUID,
    ) -> UUID:
        try:
            model_id_raw = model_data.get("id")
            model_id = UUID(str(model_id_raw)) if model_id_raw else None

            prompt_id_raw = prompt_config.get("id")
            prompt_id = UUID(str(prompt_id_raw)) if prompt_id_raw else None
            prompt_version = int(prompt_config.get("version", scorecard_data.prompt_version))

            prompt_snapshot = result.get("prompt_snapshot", "")
            extraction_result = result.get("extraction_result", {})
            slot_state = result.get("slot_state") or {}

            scorecard_id = await repo.upsert_scorecard(
                lead_id=lead_id,
                model_id=model_id,
                model_version=scorecard_data.model_version,
                prompt_version=prompt_version,
                prompt_id=prompt_id,
                prompt_snapshot=prompt_snapshot,
                score_total=scorecard_data.score_total,
                priority_label=scorecard_data.priority_label,
                reasoning=scorecard_data.reasoning,
                conversation_id=conversation_id,
                new_extraction_result=extraction_result,
                raw_payload={
                    "scoring_metadata": {
                        "normalization_strategy": model_data.get("normalization_strategy"),
                        "criteria_count": len(scorecard_data.score_items),
                        "engine": "gemini_structured_json",
                    },
                    "slot_state": slot_state,
                    "llm_meta": {
                        "json_valid": result.get("json_valid"),
                        "response_chars": result.get("response_chars"),
                        "fallback_used": result.get("fallback_used"),
                    },
                },
            )

            score_items_data = []
            for item in scorecard_data.score_items:
                item_data = {
                    "criterion_key": item.criterion_key,
                    "score": item.score,
                    "explanation": item.explanation,
                    "extracted_data": item.extracted_data,
                }

                if item.band_key:
                    for criterion in model_data.get("criteria", []):
                        if criterion.get("criterion_key") == item.criterion_key:
                            for band in criterion.get("bands", []):
                                if band.get("band_key") == item.band_key:
                                    item_data["band_id"] = UUID(str(band["id"]))
                                    break
                            break
                score_items_data.append(item_data)

            await repo.create_score_items(scorecard_id, score_items_data)
            await repo.update_lead_current_scorecard(lead_id, scorecard_id)
            await repo.update_lead_from_extraction(lead_id, extraction_result)
            await db_session.commit()

            if client_id:
                try:
                    existing_snapshot = await repo.get_conversation_context_snapshot(
                        conversation_id=conversation_id,
                        client_id=client_id,
                    )
                    if existing_snapshot:
                        updated_snapshot = dict(existing_snapshot)
                        updated_snapshot["last_scoring"] = {
                            "scorecard_id": str(scorecard_id),
                            "scored_at": datetime.now(timezone.utc).isoformat(),
                        }
                        await repo.set_conversation_context_snapshot(
                            conversation_id=conversation_id,
                            lead_id=lead_id,
                            snapshot=updated_snapshot,
                        )
                except Exception:
                    logger.exception(
                        "Failed to enrich scoring snapshot lead=%s conversation=%s",
                        lead_id,
                        conversation_id,
                    )

            return scorecard_id
        except Exception:
            await db_session.rollback()
            raise
