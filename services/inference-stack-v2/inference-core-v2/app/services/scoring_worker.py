import asyncio
import logging
from datetime import datetime, timezone
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
            running_generation = claimed.get("running_generation")
            logger.info(
                "Processing scoring job id=%s lead_id=%s conversation_id=%s attempt=%s/%s generation=%s",
                job_id,
                claimed.get("lead_id"),
                claimed.get("conversation_id"),
                claimed.get("attempts"),
                claimed.get("max_attempts"),
                running_generation,
            )

            try:
                await self._run_job_payload(claimed, db_session, repo)
                return True
            except Exception as exc:
                error_text = str(exc) or exc.__class__.__name__
                error_code = error_text.split(":", 1)[0].strip()[:64] or "SCORING_WORKER_ERROR"
                retry_delay = settings.scoring_retry_delay_secs * max(1, int(claimed.get("attempts") or 1))
                try:
                    await db_session.rollback()
                except Exception:
                    logger.exception("Failed to rollback worker session before fail_scoring_job")
                failed = await repo.fail_scoring_job(
                    job_id=job_id,
                    error_code=error_code,
                    error_message=error_text,
                    retry_delay_secs=retry_delay,
                    expected_running_generation=(
                        int(running_generation) if running_generation is not None else None
                    ),
                )
                if failed:
                    logger.exception(
                        "Failed scoring job id=%s error_code=%s retry_delay_secs=%s generation=%s",
                        job_id,
                        error_code,
                        retry_delay,
                        running_generation,
                    )
                else:
                    logger.info(
                        "Ignored fail update for stale claim id=%s generation=%s",
                        job_id,
                        running_generation,
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
        running_generation_raw = job.get("running_generation")
        if running_generation_raw is None:
            raise ValueError("MISSING_RUNNING_GENERATION")
        running_generation = int(running_generation_raw)

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
            rescheduled = await repo.reschedule_scoring_job(
                job_id=job_id,
                # New user turn arrived while this job was pending/running.
                # Requeue immediately so the freshest context is scored next.
                next_scheduled_for=datetime.now(timezone.utc),
                error_code="STALE_CONVERSATION",
                error_message=(
                    f"Conversation advanced from expected={expected_lead_messages} "
                    f"to latest={latest_lead_messages}; rescheduled."
                ),
                expected_running_generation=running_generation,
            )
            if rescheduled:
                logger.info(
                    "Rescheduled stale scoring job id=%s generation=%s",
                    job_id,
                    running_generation,
                )
            else:
                logger.info(
                    "Skipped stale reschedule for superseded job id=%s generation=%s",
                    job_id,
                    running_generation,
                )
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

        # Re-check claim ownership right before the expensive LLM call.
        claim_is_current = await repo.is_scoring_job_claim_current(
            job_id=job_id,
            running_generation=running_generation,
        )
        if not claim_is_current:
            logger.info(
                "Skipping pre-LLM execution for superseded job id=%s generation=%s",
                job_id,
                running_generation,
            )
            return

        result = await scoring_engine.analyze_conversation(
            conversation_text=conversation_text,
            model_config={
                **model_data,
                "vertical_name": vertical_ctx.get("vertical_name", "leads"),
                "vertical_slug": vertical_ctx.get("vertical_slug", ""),
            },
            prompt_config=prompt_config,
        )

        # Re-check claim ownership right before persisting scorecard results.
        # If a newer generation was enqueued while this worker was running,
        # drop this stale write.
        claim_is_current = await repo.is_scoring_job_claim_current(
            job_id=job_id,
            running_generation=running_generation,
        )
        if not claim_is_current:
            logger.info(
                "Skipping stale scoring persistence for job id=%s generation=%s",
                job_id,
                running_generation,
            )
            return

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

        completed = await repo.complete_scoring_job(
            job_id=job_id,
            expected_running_generation=running_generation,
            fallback_used=bool(result.get("fallback_used")),
            json_valid=result.get("json_valid"),
            latency_ms=result.get("latency_ms"),
            response_chars=result.get("response_chars"),
        )
        if completed:
            logger.info(
                "Completed scoring job id=%s lead_id=%s generation=%s",
                job_id,
                lead_id,
                running_generation,
            )
        else:
            logger.info(
                "Skipped completion update for superseded job id=%s generation=%s",
                job_id,
                running_generation,
            )
