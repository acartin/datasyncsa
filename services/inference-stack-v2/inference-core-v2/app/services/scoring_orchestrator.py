import logging
import asyncio
import re
import time
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_v2 import ChatV2Request, ChatV2Response, ScoreItemV2, ScorecardV2
from app.repositories.scoring_repository import ScoringRepository
from app.services.cache_service import cache_service
from app.services.hybrid_retriever import HybridRetriever
from app.services.scoring_job_service import ScoringJobService
from app.core.config import settings

logger = logging.getLogger("inference-core-v2.orchestrator")

MISCONFIGURED_CHAT_MESSAGE = "Lo siento, no puedo conversar, estoy desconfigurado."


class ScoringOrchestrator:
    """Orchestrator for v2 chat and scoring"""
    _conversation_locks: Dict[str, asyncio.Lock] = {}
    _scheduled_scoring_tasks: Dict[str, asyncio.Task] = {}
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repo = ScoringRepository(db_session)
        self.job_service = ScoringJobService(self.repo)
        self.hybrid_retriever = HybridRetriever()
        self._scoring_engine = None
        self._llm_client = None
    
    @property
    def llm_client(self):
        """Lazy initialization of LLM client for chat"""
        if self._llm_client is None and settings.google_api_key:
            try:
                from google import genai
                self._llm_client = genai.Client(api_key=settings.google_api_key)
            except ImportError:
                logger.warning("google-genai not installed")
        return self._llm_client
    
    @property
    def scoring_engine(self):
        """Lazy initialization of scoring engine"""
        if self._scoring_engine is None and settings.google_api_key:
            try:
                from app.services.scoring_engine import scoring_engine
                self._scoring_engine = scoring_engine
            except ImportError:
                logger.warning("ScoringEngine not available - google-genai not installed")
        return self._scoring_engine
    
    async def get_active_scoring_model(
        self,
        client_id: UUID,
        vertical_id: int,
        scoring_model_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get active scoring model with caching"""
        cached = await cache_service.get_active_model(client_id)
        if cached:
            logger.debug(f"Cache hit for active model: client_id={client_id}")
            return cached
        
        model_data = await self.repo.get_active_scoring_model(
            vertical_id=vertical_id,
            scoring_model_id=scoring_model_id,
        )
        if not model_data:
            logger.warning(
                "No active model found: vertical=%s, scoring_model_id=%s",
                vertical_id,
                scoring_model_id,
            )
            return None
        
        await cache_service.set_active_model(client_id, model_data)
        return model_data

    async def resolve_vertical_for_client(self, client_id: UUID) -> Dict[str, Any]:
        """Resolve vertical context from tenant configuration."""
        vertical_ctx = await self.repo.get_client_vertical_context(client_id)
        if not vertical_ctx or not vertical_ctx.get("client_exists"):
            raise ValueError("CLIENT_NOT_FOUND")
        if vertical_ctx.get("vertical_id") is None:
            raise ValueError("TENANT_VERTICAL_NOT_CONFIGURED")
        if vertical_ctx.get("scoring_model_id") is None:
            raise ValueError("TENANT_SCORING_MODEL_NOT_CONFIGURED")
        return vertical_ctx

    async def get_or_create_prompt(
        self,
        model_data: Dict[str, Any],
        vertical_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get active prompt - must be configured in database"""
        model_id = UUID(model_data["id"])
        
        prompt_config = await self.repo.get_active_prompt(model_id)
        
        if not prompt_config:
            raise ValueError(f"No active prompt found for model {model_id} - please configure prompt in database")
        
        return prompt_config

    async def _resolve_runtime_context(
        self,
        request: ChatV2Request,
        conversation_id: UUID,
    ) -> Dict[str, Any]:
        """
        Resolve full runtime context for a chat turn.
        Prefers conversation snapshot when available.
        """
        snapshot = None
        if request.conversation_id:
            snapshot = await self.repo.get_conversation_context_snapshot(
                conversation_id=conversation_id,
                client_id=request.client_id,
            )

        if snapshot:
            vertical_ctx = snapshot.get("vertical_ctx") or {}
            model_data = snapshot.get("model_data") or {}
            prompt_config = snapshot.get("scoring_prompt") or {}
            client_prompt_text = snapshot.get("client_prompt_text")
            if vertical_ctx and model_data and prompt_config:
                if not client_prompt_text:
                    client_prompt_text = await self.repo.get_client_system_prompt(
                        request.client_id,
                        slug="primary_chat",
                    )
                return {
                    "vertical_ctx": vertical_ctx,
                    "model_data": model_data,
                    "prompt_config": prompt_config,
                    "client_prompt_text": client_prompt_text,
                    "from_snapshot": True,
                }

        vertical_ctx = await self.resolve_vertical_for_client(request.client_id)
        vertical_id = int(vertical_ctx["vertical_id"])
        scoring_model_id = UUID(str(vertical_ctx["scoring_model_id"]))

        model_data = await self.get_active_scoring_model(
            client_id=request.client_id,
            vertical_id=vertical_id,
            scoring_model_id=scoring_model_id,
        )
        if not model_data:
            raise ValueError(
                f"NO_ACTIVE_VERTICAL_SCORING_MODEL: vertical_id={vertical_id}, scoring_model_id={scoring_model_id}"
            )

        prompt_config = await self.get_or_create_prompt(model_data, vertical_ctx)
        client_prompt_text = await self.repo.get_client_system_prompt(
            request.client_id,
            slug="primary_chat",
        )

        return {
            "vertical_ctx": vertical_ctx,
            "model_data": model_data,
            "prompt_config": prompt_config,
            "client_prompt_text": client_prompt_text,
            "from_snapshot": False,
        }

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

    @classmethod
    def _get_conversation_lock(cls, conversation_id: UUID) -> asyncio.Lock:
        key = str(conversation_id)
        lock = cls._conversation_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            cls._conversation_locks[key] = lock
        return lock

    @staticmethod
    def _build_conversation_context_snapshot(
        vertical_ctx: Dict[str, Any],
        model_data: Dict[str, Any],
        prompt_config: Dict[str, Any],
        client_prompt_text: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "vertical_ctx": ScoringOrchestrator._json_safe(vertical_ctx or {}),
            "model_data": ScoringOrchestrator._json_safe(model_data or {}),
            "scoring_prompt": ScoringOrchestrator._json_safe(prompt_config or {}),
            "client_prompt_text": client_prompt_text,
        }

    @staticmethod
    def _format_conversation_history(messages: List[Dict[str, Any]]) -> str:
        if not messages:
            return ""
        lines: List[str] = []
        for item in messages:
            role = (item.get("role") or "unknown").strip().lower()
            content = (item.get("content") or "").strip()
            if not content:
                continue
            if role == "assistant":
                speaker = "Asistente"
            elif role == "user":
                speaker = "Usuario"
            else:
                speaker = role.capitalize() or "Mensaje"
            lines.append(f"{speaker}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _format_user_only_history(messages: List[Dict[str, Any]]) -> str:
        """
        Build scoring context strictly from user turns to avoid assistant leakage.
        """
        if not messages:
            return ""
        lines: List[str] = []
        for item in messages:
            role = (item.get("role") or "").strip().lower()
            if role != "user":
                continue
            content = (item.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"Usuario: {content}")
        return "\n".join(lines)

    @staticmethod
    def _extract_contact_seed_from_text(query_text: str) -> Dict[str, Any]:
        """
        Fast path extraction to persist core contact fields even if async scoring fails.
        """
        text = (query_text or "").strip()
        if not text:
            return {}

        extracted: Dict[str, Any] = {}

        email_match = re.search(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            text,
            re.IGNORECASE,
        )
        if email_match:
            extracted["extracted_email"] = email_match.group(0)

        phone_match = re.search(
            r"\b(?:\+?\d{1,3}[-\s]?)?(?:\d{4}[-\s]?\d{4})\b",
            text,
        )
        if phone_match:
            extracted["extracted_phone"] = phone_match.group(0).strip()

        name_match = re.search(
            r"\b(?:me llamo|soy)\s+([A-Za-zÁÉÍÓÚáéíóúÑñ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+){0,4})",
            text,
            re.IGNORECASE,
        )
        if name_match:
            candidate = " ".join(name_match.group(1).split()).strip()
            if len(candidate) >= 4:
                extracted["extracted_name"] = candidate

        return extracted

    async def _is_stale_scoring_task(
        self,
        repo: ScoringRepository,
        conversation_id: UUID,
        client_id: UUID,
        lead_id: UUID,
        expected_lead_messages: Optional[int],
    ) -> bool:
        if expected_lead_messages is None:
            return False

        counters = await repo.get_conversation_message_counters(
            conversation_id=conversation_id,
            client_id=client_id,
        )
        latest_lead_messages = (counters or {}).get("lead_messages")
        if latest_lead_messages and latest_lead_messages > expected_lead_messages:
            logger.info(
                "Skipping stale scoring task for lead %s conversation %s (expected_turn=%s latest_turn=%s)",
                lead_id,
                conversation_id,
                expected_lead_messages,
                latest_lead_messages,
            )
            return True
        return False

    @classmethod
    def _schedule_scoring_after_idle(
        cls,
        *,
        coroutine_factory,
        conversation_id: UUID,
        idle_delay_secs: float,
    ) -> None:
        key = str(conversation_id)
        existing = cls._scheduled_scoring_tasks.get(key)
        if existing and not existing.done():
            existing.cancel()

        async def _runner() -> None:
            try:
                await asyncio.sleep(max(0.0, idle_delay_secs))
                await coroutine_factory()
            except asyncio.CancelledError:
                logger.debug("Cancelled scheduled scoring task for conversation %s", conversation_id)
                raise
            finally:
                current = cls._scheduled_scoring_tasks.get(key)
                if current is asyncio.current_task():
                    cls._scheduled_scoring_tasks.pop(key, None)

        task = asyncio.create_task(_runner())
        cls._scheduled_scoring_tasks[key] = task

    @staticmethod
    def _format_vector_context(chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return "[sin resultados vectoriales]"
        lines: List[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            title = chunk.get("title") or f"chunk_{idx}"
            score = chunk.get("score")
            body = (chunk.get("body_content") or "").strip()
            snippet = body[:500]
            lines.append(f"[{idx}] {title} | score={score}\n{snippet}")
        return "\n\n".join(lines)

    @staticmethod
    def _format_structured_context(structured: Dict[str, Any]) -> str:
        if not structured:
            return "[sin contexto estructurado]"
        return str(structured)

    @staticmethod
    def _truncate_history_context(text: str, max_chars: int) -> str:
        value = (text or "").strip()
        if max_chars <= 0 or len(value) <= max_chars:
            return value
        # Keep the most recent tail because chat relevance is recency-biased.
        return "[historial truncado por longitud]\n" + value[-max_chars:]

    @staticmethod
    def _default_vector_category_for_vertical(vertical_slug: str) -> Optional[str]:
        slug = (vertical_slug or "").strip().lower()
        if slug in {"realtor", "real_estate", "inmobiliaria"}:
            return "property"
        return None

    async def _retrieve_vertical_vector_context(
        self,
        request: ChatV2Request,
        vertical_ctx: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Semantic retrieval for hybrid RAG, tenant and vertical scoped.
        """
        filters = dict(request.filters or {})
        default_category = self._default_vector_category_for_vertical(vertical_ctx.get("vertical_slug", ""))
        if default_category and "category" not in filters:
            filters["category"] = default_category

        return await self.hybrid_retriever.search(
            query_text=request.query_text,
            client_id=str(request.client_id),
            filters=filters,
            top_k=settings.rag_top_k,
        )

    async def _retrieve_structured_business_context(
        self,
        request: ChatV2Request,
        vertical_ctx: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Structured SQL context for hybrid RAG (tenant scoped).
        """
        if not request.conversation_id:
            return {
                "vertical_slug": vertical_ctx.get("vertical_slug"),
                "vertical_name": vertical_ctx.get("vertical_name"),
                "conversation_metrics": None,
                "lead_snapshot": None,
                "vertical_sql_placeholders": {
                    "property_inventory": "[placeholder: pending realtor inventory query]",
                },
                "realtor_hints": {
                    "brand_project": (request.user_metadata or {}).get("brand_project"),
                    "source_property_ref": (request.user_metadata or {}).get("source_property_ref"),
                },
            }

        metrics = await self.repo.get_conversation_metrics(
            conversation_id=request.conversation_id,
            client_id=request.client_id,
        )
        lead_snapshot = None
        if metrics and metrics.get("lead_id"):
            lead_snapshot = await self.repo.get_lead_snapshot(
                lead_id=UUID(metrics["lead_id"]),
                client_id=request.client_id,
            )

        return {
            "vertical_slug": vertical_ctx.get("vertical_slug"),
            "vertical_name": vertical_ctx.get("vertical_name"),
            "conversation_metrics": metrics,
            "lead_snapshot": lead_snapshot,
            "vertical_sql_placeholders": {
                "property_inventory": "[placeholder: pending realtor inventory query]",
            },
            "realtor_hints": {
                "brand_project": (request.user_metadata or {}).get("brand_project"),
                "source_property_ref": (request.user_metadata or {}).get("source_property_ref"),
            },
        }

    async def _build_hybrid_context(
        self,
        request: ChatV2Request,
        vertical_ctx: Dict[str, Any],
        conversation_id: UUID,
    ) -> Dict[str, Any]:
        history = await self.repo.get_conversation_messages(
            conversation_id=conversation_id,
            client_id=request.client_id,
            max_messages=settings.chat_history_max_messages,
        )
        vector_chunks = await self._retrieve_vertical_vector_context(request, vertical_ctx)
        structured_facts = await self._retrieve_structured_business_context(request, vertical_ctx)
        return {
            "history": history,
            "vector_chunks": vector_chunks,
            "structured_facts": structured_facts,
        }
    
    async def _generate_chat_response(
        self,
        request: ChatV2Request,
        vertical_ctx: Dict[str, Any],
        conversation_id: UUID,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate chat response using LLM with client's system prompt.
        """
        start_total = time.perf_counter()
        if not self.llm_client:
            return "Lo siento, el servicio de IA no está disponible."
        
        try:
            hybrid_ctx = await self._build_hybrid_context(
                request=request,
                vertical_ctx=vertical_ctx,
                conversation_id=conversation_id,
            )
            history_text = self._truncate_history_context(
                self._format_conversation_history(hybrid_ctx["history"]),
                max_chars=max(0, int(settings.chat_history_context_max_chars or 0)),
            )

            # Get system prompt from lead_ai_prompts unless snapshot provided one.
            if not system_prompt:
                system_prompt = await self.repo.get_client_system_prompt(
                    request.client_id,
                    slug="primary_chat"
                )
            
            if not system_prompt:
                raise ValueError("CLIENT_CHAT_PROMPT_NOT_CONFIGURED")
            
            vector_section = hybrid_ctx["vector_chunks"]
            structured_section = hybrid_ctx["structured_facts"]
            vector_context_text = self._format_vector_context(vector_section)
            structured_context_text = self._format_structured_context(structured_section)
            composed_user_prompt = (
                "Contexto conversacional previo:\n"
                f"{history_text or '[sin historial]'}\n\n"
                "Contexto vectorial recuperado (RAG vertical/tenant):\n"
                f"{vector_context_text}\n\n"
                "Contexto estructurado de negocio:\n"
                f"{structured_context_text}\n\n"
                "Mensaje actual del usuario:\n"
                f"{request.query_text}"
            )
            logger.info(
                "CHAT_INPUT conversation_id=%s history_chars=%s vector_chunks=%s vector_chars=%s structured_facts=%s structured_chars=%s system_prompt_chars=%s user_prompt_chars=%s",
                conversation_id,
                len(history_text or ""),
                len(vector_section or []),
                len(vector_context_text or ""),
                len(structured_section or []),
                len(structured_context_text or ""),
                len(system_prompt or ""),
                len(composed_user_prompt or ""),
            )

            # Generate response using LLM
            from google.genai import types
            llm_start = time.perf_counter()
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm_client.models.generate_content,
                    model=settings.llm_model,
                    contents=[composed_user_prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2,
                        max_output_tokens=max(64, int(settings.chat_llm_max_output_tokens or 320)),
                    ),
                ),
                timeout=max(1, int(settings.llm_timeout_secs or 30)),
            )
            llm_ms = (time.perf_counter() - llm_start) * 1000.0
            total_ms = (time.perf_counter() - start_total) * 1000.0
            logger.info(
                "CHAT_OUTPUT conversation_id=%s llm_duration_ms=%.1f total_duration_ms=%.1f response_chars=%s",
                conversation_id,
                llm_ms,
                total_ms,
                len(response.text or ""),
            )
            return response.text
        except asyncio.TimeoutError:
            logger.error(
                "Chat LLM timeout for conversation %s after %ss",
                conversation_id,
                max(1, int(settings.llm_timeout_secs or 30)),
            )
            return "Lo siento, en este momento la respuesta está tardando más de lo esperado. Intenta de nuevo en unos segundos."
        except Exception as e:
            logger.error(f"Error generating chat response: {e}")
            return "Lo siento, tuve un problema procesando tu solicitud."
    
    async def process_chat(self, request: ChatV2Request) -> ChatV2Response:
        """
        Process chat request with v2 scoring.
        
        Scoring runs in background and does not block the response.
        """
        try:
            conversation_id = request.conversation_id or uuid4()
            runtime_ctx = await self._resolve_runtime_context(request, conversation_id)
            vertical_ctx = runtime_ctx["vertical_ctx"]
            model_data = runtime_ctx["model_data"]
            prompt_config = runtime_ctx["prompt_config"]
            client_prompt_text = runtime_ctx.get("client_prompt_text")
            if not client_prompt_text:
                logger.error(
                    "Missing chat system prompt for client_id=%s; conversation blocked by policy",
                    request.client_id,
                )
                return ChatV2Response(
                    answer=MISCONFIGURED_CHAT_MESSAGE,
                    conversation_id=conversation_id,
                    lead_id=None,
                    scorecard_id=None,
                    scorecard=None,
                    scoring_status="disabled",
                    scoring_job_id=None,
                    scoring_eta=None,
                )
            
            # Generate chat response using hybrid context (history + placeholders for retrieval)
            answer = await self._generate_chat_response(
                request=request,
                vertical_ctx=vertical_ctx,
                conversation_id=conversation_id,
                system_prompt=client_prompt_text,
            )
            
            existing_lead_id = None
            if request.conversation_id:
                existing_lead_id = await self.repo.get_lead_by_conversation_id(
                    conversation_id=str(request.conversation_id),
                    client_id=request.client_id
                )
            
            if existing_lead_id:
                lead_id = existing_lead_id
                logger.info(f"Reusing existing lead {lead_id} for conversation {request.conversation_id}")
            else:
                lead_id = await self.repo.get_or_create_lead(
                    client_id=request.client_id,
                    user_metadata=request.user_metadata or {},
                    conversation_id=str(conversation_id),
                )
            
            await self.db_session.commit()
            
            # Save conversation
            conversation_counters: Optional[Dict[str, int]] = None
            try:
                await self.repo.get_or_create_conversation(
                    lead_id=lead_id,
                    conversation_id=conversation_id,
                    platform="webchat"
                )
                snapshot_payload = self._build_conversation_context_snapshot(
                    vertical_ctx=vertical_ctx,
                    model_data=model_data,
                    prompt_config=prompt_config,
                    client_prompt_text=client_prompt_text,
                )
                await self.repo.set_conversation_context_snapshot(
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                    snapshot=snapshot_payload,
                )
                conversation_counters = await self.repo.update_conversation(
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                    user_message=request.query_text,
                    bot_message=answer
                )
            except Exception as e:
                logger.error(f"Error saving conversation: {e}")

            # Persist contact data early from user message so name/email/phone are not
            # blocked by async scoring failures/timeouts.
            try:
                contact_seed = self._extract_contact_seed_from_text(request.query_text)
                if contact_seed:
                    updated = await self.repo.update_lead_from_extraction(
                        lead_id=lead_id,
                        extracted_data=contact_seed,
                    )
                    if updated:
                        await self.db_session.commit()
            except Exception:
                logger.exception(
                    "Failed to persist early contact seed for lead %s conversation %s",
                    lead_id,
                    conversation_id,
                )

            scoring_status: Optional[str] = "disabled"
            scoring_job_id: Optional[UUID] = None
            scoring_eta: Optional[str] = None

            if settings.scoring_bg_enabled and settings.google_api_key:
                try:
                    expected_lead_messages = (
                        conversation_counters.get("lead_messages")
                        if conversation_counters
                        else None
                    )
                    model_id = UUID(str(model_data.get("id"))) if model_data.get("id") else None
                    prompt_id = UUID(str(prompt_config.get("id"))) if prompt_config.get("id") else None
                    job_data = await self.job_service.enqueue_post_chat_scoring(
                        lead_id=lead_id,
                        conversation_id=conversation_id,
                        client_id=request.client_id,
                        expected_lead_messages=expected_lead_messages,
                        model_id=model_id,
                        prompt_id=prompt_id,
                    )
                    scoring_status = "pending"
                    if job_data.get("id"):
                        scoring_job_id = UUID(str(job_data["id"]))
                    scoring_eta = job_data.get("scheduled_for")
                except Exception:
                    scoring_status = "error"
                    logger.exception(
                        "Failed to enqueue scoring job for lead %s conversation %s",
                        lead_id,
                        conversation_id,
                    )
            elif not settings.scoring_bg_enabled:
                logger.info(
                    "Background scoring disabled by config for lead %s conversation %s",
                    lead_id,
                    conversation_id,
                )
            else:
                logger.warning(
                    "Scoring engine unavailable; chat returned without scoring for lead %s conversation %s",
                    lead_id,
                    conversation_id,
                )

            scorecard_id = None
            scorecard = None

            return ChatV2Response(
                answer=answer,
                conversation_id=conversation_id,
                lead_id=lead_id,
                scorecard_id=scorecard_id,
                scorecard=scorecard,
                scoring_status=scoring_status,
                scoring_job_id=scoring_job_id,
                scoring_eta=scoring_eta,
            )
            
        except Exception as e:
            logger.error(f"Error processing chat request: {e}")
            raise

    async def get_scoring_job_response(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Get scoring job state by id."""
        return await self.job_service.get_job(job_id)

    async def get_scoring_ops_summary(self, window_minutes: int = 60) -> Dict[str, Any]:
        """Get operational scoring metrics for SLO and alerting."""
        bounded_window = max(5, min(1440, int(window_minutes or 60)))
        return await self.job_service.get_ops_summary(window_minutes=bounded_window)
    
    async def _run_scoring_background(
        self,
        lead_id: UUID,
        client_id: UUID,
        model_data: Dict[str, Any],
        prompt_config: Dict[str, Any],
        vertical_ctx: Dict[str, Any],
        conversation_id: UUID,
        query_text: str,
        expected_lead_messages: Optional[int] = None,
    ):
        """Run scoring in background with retries"""
        from app.dependencies.database import AsyncSessionLocal
        
        max_retries = settings.scoring_max_retries
        retry_delay = settings.scoring_retry_delay_secs
        # Conversation rows store both user+assistant turns. Scoring uses only user turns,
        # so fetch 2x window to preserve the intended amount of user context.
        scoring_history_window = max(settings.chat_history_max_messages * 2, settings.chat_history_max_messages)
        
        async with AsyncSessionLocal() as db_session:
            local_repo = ScoringRepository(db_session)

            lock = self._get_conversation_lock(conversation_id)
            async with lock:
                for attempt in range(1, max_retries + 1):
                    try:
                        # Re-check staleness inside lock to avoid write races.
                        if await self._is_stale_scoring_task(
                            repo=local_repo,
                            conversation_id=conversation_id,
                            client_id=client_id,
                            lead_id=lead_id,
                            expected_lead_messages=expected_lead_messages,
                        ):
                            return

                        history = await local_repo.get_conversation_messages(
                            conversation_id=conversation_id,
                            client_id=client_id,
                            max_messages=scoring_history_window,
                        )
                        if not history:
                            history = await local_repo.get_latest_lead_messages(
                                lead_id=lead_id,
                                max_messages=scoring_history_window,
                            )
                            if history:
                                logger.warning(
                                    "Conversation history fallback-by-lead used for lead %s conversation %s",
                                    lead_id,
                                    conversation_id,
                                )
                        logger.info(
                            "Scoring history size=%s for lead %s conversation %s",
                            len(history),
                            lead_id,
                            conversation_id,
                        )
                        conversation_text = self._format_user_only_history(history) or f"Usuario: {query_text}"

                        result = await self.scoring_engine.analyze_conversation(
                            conversation_text=conversation_text,
                            model_config={
                                **model_data,
                                "vertical_name": vertical_ctx.get("vertical_name", "leads"),
                                "vertical_slug": vertical_ctx.get("vertical_slug", ""),
                            },
                            prompt_config=prompt_config
                        )

                        scorecard_data = self._build_scorecard_from_result(
                            model_data=model_data,
                            result=result
                        )

                        await self._create_scorecard_with_engine(
                            repo=local_repo,
                            db_session=db_session,
                            lead_id=lead_id,
                            model_data=model_data,
                            scorecard_data=scorecard_data,
                            prompt_config=prompt_config,
                            result=result,
                            conversation_id=conversation_id
                        )

                        logger.info(f"Background scoring completed for lead {lead_id}")
                        return

                    except Exception as e:
                        logger.error(f"Background scoring attempt {attempt}/{max_retries} failed: {e}")

                        if attempt < max_retries:
                            await asyncio.sleep(retry_delay * attempt)
                        else:
                            logger.error(f"All background scoring attempts failed for lead {lead_id}")
    
    def _build_scorecard_from_result(
        self,
        model_data: Dict[str, Any],
        result: Dict[str, Any]
    ) -> ScorecardV2:
        """Build ScorecardV2 from engine result"""
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
            
            score_items.append(ScoreItemV2(
                criterion_key=criterion_key,
                score=score,
                band_key=band_key,
                explanation=explanation,
                extracted_data=None
            ))
            
            weight = float(criterion.get("weight", 1.0))
            total_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            normalized_total = total_score / total_weight
        else:
            normalized_total = 0.0
        
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
            score_items=score_items
        )
    
    async def _create_scorecard_with_engine(
        self,
        repo: ScoringRepository,
        db_session: AsyncSession,
        lead_id: UUID,
        model_data: Dict[str, Any],
        scorecard_data: ScorecardV2,
        prompt_config: Dict[str, Any],
        result: Dict[str, Any],
        conversation_id: UUID
    ) -> UUID:
        """Create scorecard with prompt snapshot"""
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
                }
            )
            
            score_items_data = []
            for item in scorecard_data.score_items:
                item_data = {
                    "criterion_key": item.criterion_key,
                    "score": item.score,
                    "explanation": item.explanation,
                    "extracted_data": item.extracted_data
                }
                
                if item.band_key:
                    for criterion in model_data.get("criteria", []):
                        if criterion.get("criterion_key") == item.criterion_key:
                            for band in criterion.get("bands", []):
                                if band.get("band_key") == item.band_key:
                                    item_data["band_id"] = UUID(band["id"])
                                    break
                            break
                
                score_items_data.append(item_data)
            
            await repo.create_score_items(scorecard_id, score_items_data)
            await repo.update_lead_current_scorecard(lead_id, scorecard_id)
            await repo.update_lead_from_extraction(lead_id, extraction_result)
            await db_session.commit()
            
            return scorecard_id
            
        except Exception as e:
            logger.error(f"Error creating scorecard with engine: {e}")
            await db_session.rollback()
            raise
    
    async def _create_scorecard_sync(
        self,
        lead_id: UUID,
        model_data: Dict[str, Any],
        scorecard_data: ScorecardV2,
        conversation_id: UUID
    ) -> UUID:
        """Create scorecard synchronously (fallback)"""
        try:
            scorecard_id = await self.repo.create_scorecard(
                lead_id=lead_id,
                model_id=UUID(model_data["id"]),
                model_version=scorecard_data.model_version,
                prompt_version=scorecard_data.prompt_version,
                score_total=scorecard_data.score_total,
                priority_label=scorecard_data.priority_label,
                reasoning=scorecard_data.reasoning,
                conversation_id=conversation_id,
                raw_payload={
                    "scoring_metadata": {
                        "normalization_strategy": model_data.get("normalization_strategy"),
                        "criteria_count": len(scorecard_data.score_items),
                        "engine": "placeholder"
                    }
                }
            )
            
            score_items_data = []
            for item in scorecard_data.score_items:
                item_data = {
                    "criterion_key": item.criterion_key,
                    "score": item.score,
                    "explanation": item.explanation,
                    "extracted_data": item.extracted_data
                }
                
                if item.band_key:
                    for criterion in model_data["criteria"]:
                        if criterion["criterion_key"] == item.criterion_key:
                            for band in criterion["bands"]:
                                if band["band_key"] == item.band_key:
                                    item_data["band_id"] = UUID(band["id"])
                                    break
                            break
                
                score_items_data.append(item_data)
            
            await self.repo.create_score_items(scorecard_id, score_items_data)
            await self.repo.update_lead_current_scorecard(lead_id, scorecard_id)
            await self.db_session.commit()
            
            return scorecard_id
            
        except Exception as e:
            logger.error(f"Error creating scorecard: {e}")
            await self.db_session.rollback()
            raise
    
    async def get_latest_scorecard_response(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get latest scorecard for a lead"""
        scorecard = await self.repo.get_latest_scorecard(lead_id)
        if not scorecard:
            return None
        return self._build_scorecard_response(scorecard)
    
    async def get_scorecard_response(self, scorecard_id: UUID) -> Optional[Dict[str, Any]]:
        """Get specific scorecard"""
        scorecard = await self.repo.get_scorecard_with_items(scorecard_id)
        if not scorecard:
            return None
        return self._build_scorecard_response(scorecard)
    
    def _build_scorecard_response(self, scorecard: Dict[str, Any]) -> Dict[str, Any]:
        """Build scorecard response dictionary from repo dict"""
        extraction_result = scorecard.get("extraction_result")
        if extraction_result is None:
            extraction_result = {}

        score_items = []
        for item in scorecard.get("score_items", []):
            score_items.append({
                "criterion_key": item.get("criterion_key"),
                "score": item.get("score"),
                "band_id": str(item.get("band_id")) if item.get("band_id") else None,
                "explanation": item.get("explanation"),
                "extracted_data": item.get("extracted_data"),
                "created_at": item.get("created_at").isoformat() if item.get("created_at") else None
            })
        
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
            "score_items": score_items
        }
