import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from app.core.config import settings
from app.dependencies.database import AsyncSessionLocal
from app.repositories.scoring_repository import ScoringRepository
from app.services.scoring_engine import scoring_engine
from app.services.scoring_orchestrator import ScoringOrchestrator


logger = logging.getLogger("inference-core-v2.scoring-worker")


class ScoringWorker:
    """
    Polling worker that consumes persistent scoring jobs.
    """

    async def run_forever(self) -> None:
        logger.info(
            "ScoringWorker started (poll_secs=%s max_attempts=%s)",
            settings.scoring_worker_poll_secs,
            settings.scoring_job_max_attempts,
        )
        while True:
            processed = False
            try:
                processed = await self._process_one_job()
            except Exception:
                logger.exception("Unhandled error in scoring worker loop")

            if not processed:
                await asyncio.sleep(max(0.5, settings.scoring_worker_poll_secs))

    async def _process_one_job(self) -> bool:
        async with AsyncSessionLocal() as db_session:
            repo = ScoringRepository(db_session)
            claimed = await repo.claim_next_scoring_job(
                default_max_attempts=settings.scoring_job_max_attempts,
                lock_ttl_secs=settings.scoring_job_lock_ttl_secs,
            )
            if not claimed:
                return False

            job_id = UUID(str(claimed["id"]))
            logger.info(
                "Processing scoring job id=%s lead_id=%s conversation_id=%s attempt=%s/%s",
                job_id,
                claimed.get("lead_id"),
                claimed.get("conversation_id"),
                claimed.get("attempts"),
                claimed.get("max_attempts"),
            )

            try:
                await self._run_job_payload(claimed, db_session, repo)
                return True
            except Exception as exc:
                error_text = str(exc) or exc.__class__.__name__
                error_code = error_text.split(":", 1)[0].strip()[:64] or "SCORING_WORKER_ERROR"
                retry_delay = settings.scoring_retry_delay_secs * max(1, int(claimed.get("attempts") or 1))
                await repo.fail_scoring_job(
                    job_id=job_id,
                    error_code=error_code,
                    error_message=error_text,
                    retry_delay_secs=retry_delay,
                )
                logger.exception(
                    "Failed scoring job id=%s error_code=%s retry_delay_secs=%s",
                    job_id,
                    error_code,
                    retry_delay,
                )
                return True

    async def _run_job_payload(
        self,
        job: Dict[str, Any],
        db_session,
        repo: ScoringRepository,
    ) -> None:
        conversation_id = UUID(str(job["conversation_id"]))
        client_id = UUID(str(job["client_id"]))
        lead_id = UUID(str(job["lead_id"]))
        job_id = UUID(str(job["id"]))
        expected_lead_messages = job.get("expected_lead_messages")

        counters = await repo.get_conversation_message_counters(
            conversation_id=conversation_id,
            client_id=client_id,
        )
        latest_lead_messages = (counters or {}).get("lead_messages")
        if (
            expected_lead_messages is not None
            and latest_lead_messages is not None
            and latest_lead_messages > expected_lead_messages
        ):
            await repo.reschedule_scoring_job(
                job_id=job_id,
                next_scheduled_for=(
                    datetime.now(timezone.utc)
                    + timedelta(seconds=max(0.0, settings.scoring_idle_close_secs))
                ),
                error_code="STALE_CONVERSATION",
                error_message=(
                    f"Conversation advanced from expected={expected_lead_messages} "
                    f"to latest={latest_lead_messages}; rescheduled."
                ),
            )
            logger.info("Rescheduled stale scoring job id=%s", job_id)
            return

        snapshot = await repo.get_conversation_context_snapshot(
            conversation_id=conversation_id,
            client_id=client_id,
        )
        if not snapshot:
            raise ValueError("MISSING_CONTEXT_SNAPSHOT")

        vertical_ctx = snapshot.get("vertical_ctx") or {}
        model_data = snapshot.get("model_data") or {}
        prompt_config = snapshot.get("scoring_prompt") or {}
        if not model_data:
            raise ValueError("MISSING_MODEL_DATA_SNAPSHOT")
        if not prompt_config:
            raise ValueError("MISSING_PROMPT_CONFIG_SNAPSHOT")

        if not settings.google_api_key:
            raise ValueError("LLM_ENGINE_NOT_AVAILABLE")

        history_window = max(settings.chat_history_max_messages * 2, settings.chat_history_max_messages)
        history = await repo.get_conversation_messages(
            conversation_id=conversation_id,
            client_id=client_id,
            max_messages=history_window,
        )
        if not history:
            history = await repo.get_latest_lead_messages(
                lead_id=lead_id,
                max_messages=history_window,
            )

        conversation_text = ScoringOrchestrator._format_user_only_history(history)
        if not conversation_text:
            raise ValueError("EMPTY_CONVERSATION_CONTEXT")

        result = await scoring_engine.analyze_conversation(
            conversation_text=conversation_text,
            model_config={
                **model_data,
                "vertical_name": vertical_ctx.get("vertical_name", "leads"),
                "vertical_slug": vertical_ctx.get("vertical_slug", ""),
            },
            prompt_config=prompt_config,
        )

        orchestrator = ScoringOrchestrator(db_session)
        scorecard_data = orchestrator._build_scorecard_from_result(
            model_data=model_data,
            result=result,
        )
        await orchestrator._create_scorecard_with_engine(
            repo=repo,
            db_session=db_session,
            lead_id=lead_id,
            model_data=model_data,
            scorecard_data=scorecard_data,
            prompt_config=prompt_config,
            result=result,
            conversation_id=conversation_id,
        )

        await repo.complete_scoring_job(
            job_id=job_id,
            fallback_used=bool(result.get("fallback_used")),
            json_valid=result.get("json_valid"),
            latency_ms=result.get("latency_ms"),
            response_chars=result.get("response_chars"),
        )

        logger.info("Completed scoring job id=%s lead_id=%s", job_id, lead_id)
