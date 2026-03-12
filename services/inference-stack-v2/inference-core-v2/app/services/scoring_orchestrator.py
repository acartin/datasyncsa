import logging
import asyncio
import re
import json
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
from app.services.prompt_selector import prompt_selector
from app.services.realtor_turn_executor import RealtorTurnExecutor
from app.core.config import settings

logger = logging.getLogger("inference-core-v2.orchestrator")

MISCONFIGURED_CHAT_MESSAGE = "Lo siento, no puedo conversar, estoy desconfigurado."


class ScoringOrchestrator:
    """Orchestrator for v2 chat and scoring"""
    _PROPERTY_SEARCH_LIMIT = 4
    _conversation_locks: Dict[str, asyncio.Lock] = {}
    _scheduled_scoring_tasks: Dict[str, asyncio.Task] = {}
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repo = ScoringRepository(db_session)
        self.job_service = ScoringJobService(self.repo)
        self.hybrid_retriever = HybridRetriever()
        self.realtor_turn_executor = RealtorTurnExecutor(
            db_session,
            search_limit=self._PROPERTY_SEARCH_LIMIT,
        )
        self._scoring_engine = None
        self._llm_client = None
        self._planner_prompt_cache: Dict[str, str] = {}
        self._realtor_intents = {
            "PROPERTY_SEARCH",
            "PROPERTY_INVENTORY",
            "PROPERTY_PRICE_RANGE",
            "RAG",
            "CLARIFICATION",
            "NONE",
        }

    _REALTOR_TURN_GUARDRAILS = """
MANDATORY EXECUTION RULES (append as hard constraint, after any prompt text from DB):
- You must return only JSON. Do not include markdown, surrounding quotes, or explanatory text.
- If intent is PROPERTY_SEARCH / PROPERTY_INVENTORY / PROPERTY_PRICE_RANGE, SQL must be a single SELECT over lead_properties.
- If intent is PROPERTY_SEARCH / PROPERTY_INVENTORY / PROPERTY_PRICE_RANGE, include search_summary with a short natural summary of the active search.
- Include filters as a JSON object when you can infer them from the current turn or confirmed session context.
- Allowed filter keys: desired_location, property_type, bedrooms_min, bathrooms_min, garage_min, price_min, price_max, listing_intent.
- Always include hard tenant scoping: client_id = '{client_id}'.
- Always include published price constraint: COALESCE(price, 0) > 0.
- For direct user location requests (includes "en X", "zona X", "en el"), generate a new SQL from scratch using current message and do not inherit prior filters.
- Use previous search only when user explicitly references prior results (examples: "de esas", "más baratas de esas", "las mismas").
- Prefer title, description, features->>'address' for textual filtering.
""".strip()

    _REALTOR_ANSWER_GUARDRAILS = """
You are the final user-facing response synthesizer for the realtor flow.
You receive the user message, the realtor_turn plan, execution facts and recent realtor session state.
Write ONLY the final answer for the user. Do not output JSON, markdown, labels, or internal field names.

Rules:
- Use only the provided facts and conversation context. Do not invent properties, availability or unsupported details.
- If search_summary is available, mention it naturally instead of saying "con ese criterio".
- If results were found and visible_count > 0, acknowledge the results naturally.
- If total_matches > visible_count and visible_count > 0, mention naturally that you are showing only a few to start.
- If no results were found, say so honestly and suggest one useful next refinement.
- If the execution failed, apologize briefly and ask for a concrete retry input like zone or property type.
- For price range, mention min/max only if they are present in the facts.
- Keep the answer concise, natural and advisor-like. Normally 1 or 2 sentences.
- Never mention SQL, tools, prompts, execution status codes or internal contracts.
""".strip()

    _REALTOR_VERTICAL_MEMORY_KEYS = (
        "desired_location",
        "property_type",
        "bedrooms_min",
        "bathrooms_min",
        "garage_min",
        "price_min",
        "price_max",
        "listing_intent",
        "search_summary",
    )
    
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
        vertical_ctx: Dict[str, Any],
        client_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Get active prompt - must be configured in database"""
        model_id = UUID(model_data["id"])
        if client_id:
            cached_prompt = await cache_service.get_scoring_prompt(client_id=client_id, model_id=model_id)
            if cached_prompt:
                return cached_prompt

        prompt_config = await self.repo.get_active_prompt(model_id)
        
        if not prompt_config:
            raise ValueError(f"No active prompt found for model {model_id} - please configure prompt in database")
        if client_id:
            await cache_service.set_scoring_prompt(client_id=client_id, model_id=model_id, prompt_data=prompt_config)
        return prompt_config

    @staticmethod
    def _resolve_channel_from_metadata(user_metadata: Optional[Dict[str, Any]]) -> str:
        if not isinstance(user_metadata, dict):
            return "web_html"
        raw = (
            user_metadata.get("channel")
            or user_metadata.get("channel_slug")
            or user_metadata.get("channel_type")
        )
        if not isinstance(raw, str):
            return "web_html"
        normalized = raw.strip().lower()
        return normalized if normalized in {"web_html", "meta_whatsapp", "meta_ig", "api"} else "web_html"

    def _select_chat_prompt_slug(
        self,
        vertical_ctx: Dict[str, Any],
        user_metadata: Optional[Dict[str, Any]],
    ) -> str:
        vertical = (vertical_ctx.get("vertical_slug") or "generic").strip().lower()
        channel = self._resolve_channel_from_metadata(user_metadata)
        return prompt_selector.get_prompt_slug(vertical=vertical, channel=channel)

    async def _resolve_client_chat_prompt(
        self,
        client_id: UUID,
        preferred_slug: str,
    ) -> tuple[str, Optional[str]]:
        slug = (preferred_slug or "primary_chat").strip() or "primary_chat"
        cached_prompt = await cache_service.get_client_chat_prompt(client_id=client_id, slug=slug)
        if cached_prompt:
            return slug, cached_prompt

        prompt_text = await self.repo.get_client_system_prompt(client_id, slug=slug)
        if prompt_text:
            await cache_service.set_client_chat_prompt(client_id=client_id, slug=slug, prompt_text=prompt_text)
            return slug, prompt_text
        if slug != "primary_chat":
            cached_fallback = await cache_service.get_client_chat_prompt(client_id=client_id, slug="primary_chat")
            if cached_fallback:
                logger.warning(
                    "Prompt slug '%s' not found for client_id=%s; using cached fallback slug 'primary_chat'",
                    slug,
                    client_id,
                )
                return "primary_chat", cached_fallback
            fallback_prompt = await self.repo.get_client_system_prompt(client_id, slug="primary_chat")
            if fallback_prompt:
                await cache_service.set_client_chat_prompt(
                    client_id=client_id,
                    slug="primary_chat",
                    prompt_text=fallback_prompt,
                )
                logger.warning(
                    "Prompt slug '%s' not found for client_id=%s; using fallback slug 'primary_chat'",
                    slug,
                    client_id,
                )
                return "primary_chat", fallback_prompt
        return slug, None

    async def _resolve_realtor_turn_prompt(self, client_id: UUID) -> Optional[str]:
        """
        Resolve the realtor-turn planner prompt (planner/system prompt) for a client.
        """
        primary_slug = "realtor_turn_system"
        secondary_slug = "realtor_turn"

        cached_prompt = await cache_service.get_client_chat_prompt(
            client_id=client_id,
            slug=primary_slug,
        )
        if cached_prompt:
            resolved = str(cached_prompt).replace("{search_limit}", str(self._PROPERTY_SEARCH_LIMIT)).replace(
                "{client_id}", str(client_id)
            )
            resolved = self._append_guardrails(resolved, self._REALTOR_TURN_GUARDRAILS)
            self._planner_prompt_cache[str(client_id)] = resolved
            return resolved

        prompt_text = await self.repo.get_client_system_prompt(client_id, slug=primary_slug)
        if not prompt_text:
            prompt_text = await self.repo.get_client_system_prompt(client_id, slug=secondary_slug)
        if not prompt_text:
            logger.warning("Realtor turn prompt missing for client_id=%s", client_id)
            return None

        if prompt_text:
            prompt_text = str(prompt_text).replace("{search_limit}", str(self._PROPERTY_SEARCH_LIMIT)).replace(
                "{client_id}",
                str(client_id),
            )
            prompt_text = self._append_guardrails(prompt_text, self._REALTOR_TURN_GUARDRAILS)

        await cache_service.set_client_chat_prompt(
            client_id=client_id,
            slug=primary_slug,
            prompt_text=prompt_text,
        )
        self._planner_prompt_cache[str(client_id)] = prompt_text
        return prompt_text

    @staticmethod
    def _extract_realtor_turn_payload(raw: str) -> Dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            raise ValueError("Empty realtor turn response")
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Realtor turn response is not JSON object")
        return payload

    @staticmethod
    def _normalize_realtor_turn_payload(raw_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = raw_payload or {}
        intent = str(payload.get("intent") or "NONE").strip().upper()
        if intent not in {
            "PROPERTY_SEARCH",
            "PROPERTY_INVENTORY",
            "PROPERTY_PRICE_RANGE",
            "RAG",
            "CLARIFICATION",
            "NONE",
        }:
            intent = "NONE"

        sql = payload.get("sql")
        if sql is not None:
            sql = str(sql).strip()
        clarification = payload.get("clarification")
        if clarification is not None:
            clarification = str(clarification).strip() or None

        reasoning = payload.get("reasoning")
        if reasoning is not None:
            reasoning = str(reasoning).strip() or None

        search_summary = payload.get("search_summary")
        if search_summary is not None:
            search_summary = str(search_summary).strip() or None

        filters = ScoringOrchestrator._normalize_memory_dict(payload.get("filters"))

        return {
            "intent": intent,
            "sql": sql if sql else None,
            "clarification": clarification,
            "reasoning": reasoning,
            "search_summary": search_summary,
            "filters": filters,
            "success": intent in {"PROPERTY_SEARCH", "PROPERTY_INVENTORY", "PROPERTY_PRICE_RANGE"},
        }

    @classmethod
    def _normalize_memory_value(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            if cleaned.lower() in {"null", "none", "n/a", "na", "unknown", "desconocido"}:
                return None
            return cleaned
        if isinstance(value, dict):
            normalized_dict = cls._normalize_memory_dict(value)
            return normalized_dict or None
        if isinstance(value, list):
            normalized_items = [cls._normalize_memory_value(item) for item in value]
            filtered_items = [item for item in normalized_items if item is not None]
            return filtered_items or None
        return cls._json_safe(value)

    @classmethod
    def _normalize_memory_dict(cls, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        normalized: Dict[str, Any] = {}
        for key, value in data.items():
            cleaned = cls._normalize_memory_value(value)
            if cleaned is not None:
                normalized[str(key)] = cleaned
        return normalized

    @classmethod
    def _normalize_conversation_common(cls, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        normalized = cls._normalize_memory_dict(data)
        return {
            key: value
            for key, value in normalized.items()
            if str(key).startswith("extracted_")
        }

    @classmethod
    def _normalize_conversation_extraction_result(
        cls,
        raw_payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload = raw_payload or {}
        if not isinstance(payload, dict):
            payload = {}

        common = cls._normalize_conversation_common(payload.get("common"))
        vertical = cls._normalize_memory_dict(payload.get("vertical"))

        normalized: Dict[str, Any] = {}
        if common:
            normalized["common"] = common
        if vertical:
            normalized["vertical"] = vertical
        return normalized

    @classmethod
    def _merge_conversation_extraction_result(
        cls,
        current: Optional[Dict[str, Any]],
        *,
        common_update: Optional[Dict[str, Any]] = None,
        vertical_update: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_current = cls._normalize_conversation_extraction_result(current)
        merged_common = dict(normalized_current.get("common") or {})
        merged_vertical = dict(normalized_current.get("vertical") or {})

        cleaned_common = cls._normalize_conversation_common(common_update)
        if cleaned_common:
            merged_common.update(cleaned_common)

        cleaned_vertical = cls._normalize_memory_dict(vertical_update)
        if cleaned_vertical:
            merged_vertical.update(cleaned_vertical)

        merged: Dict[str, Any] = {}
        if merged_common:
            merged["common"] = merged_common
        if merged_vertical:
            merged["vertical"] = merged_vertical
        return merged

    @classmethod
    def _build_realtor_vertical_memory(cls, runtime_ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        realtor_search_state = ((runtime_ctx or {}).get("realtor_search_state") or {})
        filters = cls._normalize_memory_dict(realtor_search_state.get("filters"))
        search_summary = cls._normalize_memory_value(realtor_search_state.get("search_summary"))

        vertical_memory: Dict[str, Any] = {}
        for key in cls._REALTOR_VERTICAL_MEMORY_KEYS:
            if key in filters:
                vertical_memory[key] = filters[key]
        if search_summary:
            vertical_memory["search_summary"] = search_summary
        return vertical_memory

    @classmethod
    def _build_conversation_extraction_updates(
        cls,
        *,
        query_text: str,
        vertical_ctx: Dict[str, Any],
        runtime_ctx: Optional[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        common_update = cls._normalize_conversation_common(
            cls._extract_contact_seed_from_text(query_text),
        )

        vertical_slug = str((vertical_ctx or {}).get("vertical_slug") or "").strip().lower()
        vertical_update: Dict[str, Any] = {}
        if vertical_slug in {"realtor", "real-estate", "real_estate", "inmobiliaria"}:
            vertical_update = cls._build_realtor_vertical_memory(runtime_ctx)

        return {
            "common": common_update,
            "vertical": vertical_update,
        }

    async def _build_realtor_turn_context(self, request: ChatV2Request, runtime_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build minimal context required by the realtor turn prompt.
        """
        conversation_id = request.conversation_id
        history = []
        if conversation_id:
            history = await self.repo.get_conversation_messages(
                conversation_id=conversation_id,
                client_id=request.client_id,
                max_messages=max(1, settings.chat_history_max_messages),
            )

        recent_history = []
        for row in history[-6:] if isinstance(history, list) else []:
            role = str((row or {}).get("role") or "").strip().lower()
            content = str((row or {}).get("content") or "").strip()
            if role and content:
                recent_history.append({"role": role, "content": content})

        return {
            "planner_last_property_query": (runtime_ctx.get("realtor_search_state") or {}).get(
                "planner_last_property_query",
            ),
            "planner_last_sql": (runtime_ctx.get("realtor_search_state") or {}).get("planner_last_sql"),
            "planner_last_search_summary": (runtime_ctx.get("realtor_search_state") or {}).get("search_summary"),
            "realtor_search_intent": (runtime_ctx.get("realtor_search_state") or {}).get("intent"),
            "awaiting_property_confirmation": bool(
                (runtime_ctx.get("realtor_search_state") or {}).get("awaiting_property_confirmation")
            ),
            "conversation_extraction_result": self._normalize_conversation_extraction_result(
                runtime_ctx.get("conversation_extraction_result"),
            ),
            "history_tail": recent_history,
        }

    async def _resolve_realtor_answer_prompt(self, client_id: UUID) -> Optional[str]:
        for slug in ("realtor_answer_synthesis", "realtor_web_v1", "primary_chat"):
            cached_prompt = await cache_service.get_client_chat_prompt(client_id=client_id, slug=slug)
            if cached_prompt:
                return self._append_guardrails(cached_prompt, self._REALTOR_ANSWER_GUARDRAILS)

            prompt_text = await self.repo.get_client_system_prompt(client_id, slug=slug)
            if prompt_text:
                await cache_service.set_client_chat_prompt(
                    client_id=client_id,
                    slug=slug,
                    prompt_text=prompt_text,
                )
                return self._append_guardrails(prompt_text, self._REALTOR_ANSWER_GUARDRAILS)
        return None

    async def _generate_realtor_answer(
        self,
        *,
        request: ChatV2Request,
        conversation_id: UUID,
        realtor_turn: Dict[str, Any],
        execution_result: Dict[str, Any],
        runtime_ctx: Dict[str, Any],
    ) -> str:
        if not self.llm_client:
            return ""

        system_prompt = await self._resolve_realtor_answer_prompt(request.client_id)
        if not system_prompt:
            return ""

        payload = {
            "user_text": request.query_text,
            "realtor_turn": realtor_turn,
            "execution_result": execution_result,
            "realtor_search_state": runtime_ctx.get("realtor_search_state") or {},
        }

        try:
            from google.genai import types

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm_client.models.generate_content,
                    model=settings.llm_model,
                    contents=[json.dumps(payload, ensure_ascii=False)],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2,
                        max_output_tokens=max(64, int(settings.chat_llm_max_output_tokens or 220)),
                    ),
                ),
                timeout=max(1, int(settings.llm_timeout_secs or 30)),
            )
            return str(response.text or "").strip()
        except Exception:
            logger.exception(
                "Failed to synthesize realtor answer for client=%s conversation=%s",
                request.client_id,
                conversation_id,
            )
            return ""

    async def _plan_realtor_turn(self, request: ChatV2Request, runtime_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs a lightweight planning pass for realtor routing.
        """
        if not self.llm_client:
            return {"intent": "NONE"}

        system_prompt = await self._resolve_realtor_turn_prompt(request.client_id)
        if not system_prompt:
            return {"intent": "NONE"}

        planning_payload = {
            "user_text": request.query_text,
            "session_data": await self._build_realtor_turn_context(request, runtime_ctx),
        }

        start_ms = time.perf_counter()
        try:
            from google.genai import types

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm_client.models.generate_content,
                    model=settings.llm_model,
                    contents=[json.dumps(planning_payload, ensure_ascii=False)],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,
                        max_output_tokens=max(64, int(settings.chat_llm_max_output_tokens or 256)),
                    ),
                ),
                timeout=max(1, int(settings.llm_timeout_secs or 30)),
            )

            llm_ms = (time.perf_counter() - start_ms) * 1000.0
            logger.debug("REALTOR_TURN_PLANNER output_ms=%.1f response_chars=%s", llm_ms, len(response.text or ""))
            payload = self._extract_realtor_turn_payload(response.text or "")
            normalized = self._normalize_realtor_turn_payload(payload)
            normalized["llm_duration_ms"] = llm_ms
            return normalized

        except asyncio.TimeoutError:
            logger.warning(
                "Realtor turn planner LLM timeout for client=%s conversation=%s",
                request.client_id,
                request.conversation_id,
            )
        except Exception as exc:
            logger.exception("Realtor turn planner failed for client=%s: %s", request.client_id, exc)

        return {"intent": "NONE"}

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
                snapshot_prompt_slug = (snapshot.get("chat_prompt_slug") or "").strip()
                if vertical_ctx and model_data and prompt_config:
                    chat_prompt_slug = snapshot_prompt_slug or self._select_chat_prompt_slug(
                        vertical_ctx=vertical_ctx,
                        user_metadata=request.user_metadata,
                    )
                    if not client_prompt_text:
                        chat_prompt_slug, client_prompt_text = await self._resolve_client_chat_prompt(
                            client_id=request.client_id,
                            preferred_slug=chat_prompt_slug,
                        )
                    return {
                        "vertical_ctx": vertical_ctx,
                        "model_data": model_data,
                        "prompt_config": prompt_config,
                        "client_prompt_text": client_prompt_text,
                        "chat_prompt_slug": chat_prompt_slug,
                        "realtor_search_state": snapshot.get("realtor_search_state") or {},
                        "conversation_extraction_result": self._normalize_conversation_extraction_result(
                            snapshot.get("conversation_extraction_result"),
                        ),
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

        prompt_config = await self.get_or_create_prompt(model_data, vertical_ctx, client_id=request.client_id)
        preferred_chat_prompt_slug = self._select_chat_prompt_slug(
            vertical_ctx=vertical_ctx,
            user_metadata=request.user_metadata,
        )
        chat_prompt_slug, client_prompt_text = await self._resolve_client_chat_prompt(
            client_id=request.client_id,
            preferred_slug=preferred_chat_prompt_slug,
        )

        return {
            "vertical_ctx": vertical_ctx,
            "model_data": model_data,
            "prompt_config": prompt_config,
            "client_prompt_text": client_prompt_text,
            "chat_prompt_slug": chat_prompt_slug,
            "realtor_search_state": {},
            "conversation_extraction_result": {},
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
        chat_prompt_slug: str,
        realtor_search_state: Optional[Dict[str, Any]] = None,
        conversation_extraction_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "vertical_ctx": ScoringOrchestrator._json_safe(vertical_ctx or {}),
            "model_data": ScoringOrchestrator._json_safe(model_data or {}),
            "scoring_prompt": ScoringOrchestrator._json_safe(prompt_config or {}),
            "client_prompt_text": client_prompt_text,
            "chat_prompt_slug": chat_prompt_slug,
            "realtor_search_state": ScoringOrchestrator._json_safe(realtor_search_state or {}),
            "conversation_extraction_result": ScoringOrchestrator._json_safe(
                ScoringOrchestrator._normalize_conversation_extraction_result(conversation_extraction_result),
            ),
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
    def _build_history_bot_message(
        answer: str,
        realtor_turn: Optional[Dict[str, Any]],
    ) -> str:
        text = (answer or "").strip()
        if text:
            return text

        payload = realtor_turn if isinstance(realtor_turn, dict) else {}
        clarification = str(payload.get("clarification") or "").strip()

        if clarification:
            return clarification
        return "Estoy para ayudarte con propiedades y consultas inmobiliarias en Costa Rica."

    @staticmethod
    def _append_guardrails(prompt_text: Optional[str], guardrails: str) -> Optional[str]:
        base = str(prompt_text or "").strip()
        if not base:
            return None
        if guardrails in base:
            return base
        return f"{base}\n\n{guardrails}"

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
        return json.dumps(structured, ensure_ascii=False, default=str)

    @staticmethod
    def _format_confirmed_lead_profile(structured: Dict[str, Any]) -> str:
        if not isinstance(structured, dict):
            return "[sin datos confirmados del lead]"
        lead_snapshot = structured.get("lead_snapshot") or {}
        if not isinstance(lead_snapshot, dict):
            return "[sin datos confirmados del lead]"

        lines: List[str] = []
        full_name = str(lead_snapshot.get("full_name") or "").strip()
        email = str(lead_snapshot.get("email") or "").strip()
        phone = str(lead_snapshot.get("phone") or "").strip()

        if full_name:
            lines.append(f"Nombre: {full_name}")
        if email:
            lines.append(f"Email: {email}")
        if phone:
            lines.append(f"Telefono: {phone}")

        if not lines:
            return "[sin datos confirmados del lead]"
        return "\n".join(lines)

    @classmethod
    def _format_confirmed_conversation_extraction(cls, structured: Dict[str, Any]) -> str:
        if not isinstance(structured, dict):
            return "[sin datos confirmados de la conversación]"

        extraction = cls._normalize_conversation_extraction_result(
            structured.get("conversation_extraction_result"),
        )
        common = extraction.get("common") or {}
        vertical = extraction.get("vertical") or {}

        lines: List[str] = []
        common_labels = {
            "extracted_name": "Nombre",
            "extracted_email": "Email",
            "extracted_phone": "Telefono",
            "extracted_budget": "Presupuesto",
            "extracted_approval": "Aprobacion financiera",
            "extracted_preference": "Preferencia libre",
            "extracted_preferred_date": "Fecha o ventana deseada",
            "extracted_appointment_intent": "Intencion de cita",
            "extracted_appointment_type": "Tipo de cita",
        }
        for key, label in common_labels.items():
            value = common.get(key)
            if value is not None:
                lines.append(f"{label}: {value}")

        vertical_labels = {
            "desired_location": "Zona deseada",
            "property_type": "Tipo de propiedad",
            "bedrooms_min": "Habitaciones",
            "bathrooms_min": "Banos",
            "garage_min": "Cochera",
            "price_min": "Precio minimo",
            "price_max": "Precio maximo",
            "listing_intent": "Intencion inmobiliaria",
            "search_summary": "Busqueda activa",
        }
        for key, label in vertical_labels.items():
            value = vertical.get(key)
            if value is not None:
                lines.append(f"{label}: {value}")

        if not lines:
            return "[sin datos confirmados de la conversación]"
        return "\n".join(lines)

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
        runtime_ctx: Optional[Dict[str, Any]] = None,
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
                "realtor_search_state": (runtime_ctx or {}).get("realtor_search_state") or {},
                "conversation_extraction_result": self._normalize_conversation_extraction_result(
                    (runtime_ctx or {}).get("conversation_extraction_result"),
                ),
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
            "realtor_search_state": (runtime_ctx or {}).get("realtor_search_state") or {},
            "conversation_extraction_result": self._normalize_conversation_extraction_result(
                (runtime_ctx or {}).get("conversation_extraction_result"),
            ),
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
        runtime_ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        history = await self.repo.get_conversation_messages(
            conversation_id=conversation_id,
            client_id=request.client_id,
            max_messages=settings.chat_history_max_messages,
        )
        vector_chunks = await self._retrieve_vertical_vector_context(request, vertical_ctx)
        structured_facts = await self._retrieve_structured_business_context(
            request,
            vertical_ctx,
            runtime_ctx=runtime_ctx,
        )
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
        prompt_slug: str = "primary_chat",
        runtime_ctx: Optional[Dict[str, Any]] = None,
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
                runtime_ctx=runtime_ctx,
            )
            history_text = self._truncate_history_context(
                self._format_conversation_history(hybrid_ctx["history"]),
                max_chars=max(0, int(settings.chat_history_context_max_chars or 0)),
            )

            # Get system prompt from lead_ai_prompts unless snapshot provided one.
            if not system_prompt:
                resolved_slug, resolved_prompt = await self._resolve_client_chat_prompt(
                    client_id=request.client_id,
                    preferred_slug=prompt_slug or "primary_chat",
                )
                prompt_slug = resolved_slug
                system_prompt = resolved_prompt
            
            if not system_prompt:
                raise ValueError("CLIENT_CHAT_PROMPT_NOT_CONFIGURED")
            
            vector_section = hybrid_ctx["vector_chunks"]
            structured_section = hybrid_ctx["structured_facts"]
            vector_context_text = self._format_vector_context(vector_section)
            structured_context_text = self._format_structured_context(structured_section)
            confirmed_lead_profile_text = self._format_confirmed_lead_profile(structured_section)
            confirmed_conversation_extraction_text = self._format_confirmed_conversation_extraction(
                structured_section,
            )
            composed_user_prompt = (
                "Contexto conversacional previo:\n"
                f"{history_text or '[sin historial]'}\n\n"
                "Datos confirmados del lead:\n"
                f"{confirmed_lead_profile_text}\n\n"
                "Datos confirmados de la conversación:\n"
                f"{confirmed_conversation_extraction_text}\n\n"
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
            chat_prompt_slug = runtime_ctx.get("chat_prompt_slug") or "primary_chat"
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

            vertical_slug = str(vertical_ctx.get("vertical_slug") or "").strip().lower()
            vertical_is_realtor = vertical_slug in {"realtor", "real-estate", "real_estate", "inmobiliaria"}
            realtor_turn = None
            realtor_intent = None
            answer = ""
            final_components: List[Dict[str, Any]] = []
            if vertical_is_realtor:
                realtor_turn = await self._plan_realtor_turn(
                    request=request,
                    runtime_ctx=runtime_ctx,
                )
                realtor_intent = realtor_turn.get("intent") if isinstance(realtor_turn, dict) else None
                if realtor_intent == "CLARIFICATION":
                    next_search_state = dict(runtime_ctx.get("realtor_search_state") or {})
                    if realtor_turn.get("search_summary"):
                        next_search_state["search_summary"] = realtor_turn.get("search_summary")
                    answer = str(realtor_turn.get("clarification") or "").strip()
                    if not answer:
                        answer = "¿Qué aspecto quieres precisar de la búsqueda?"
                    next_search_state["awaiting_property_confirmation"] = True
                    if next_search_state:
                        runtime_ctx["realtor_search_state"] = next_search_state
                elif realtor_intent in {"PROPERTY_SEARCH", "PROPERTY_INVENTORY", "PROPERTY_PRICE_RANGE"}:
                    executed_realtor_turn = await self.realtor_turn_executor.execute(
                        realtor_turn=realtor_turn,
                        user_query=request.query_text,
                        client_id=request.client_id,
                    )
                    if executed_realtor_turn.get("handled"):
                        final_components = list(executed_realtor_turn.get("components") or [])
                        answer = await self._generate_realtor_answer(
                            request=request,
                            conversation_id=conversation_id,
                            realtor_turn=realtor_turn,
                            execution_result=executed_realtor_turn,
                            runtime_ctx=runtime_ctx,
                        )

                        if not answer:
                            facts = dict(executed_realtor_turn.get("facts") or {})
                            summary = str(facts.get("search_summary") or "").strip()
                            total_matches = int(facts.get("total_matches") or facts.get("count") or 0)
                            visible_count = int(facts.get("visible_count") or 0)
                            status = str(executed_realtor_turn.get("status") or "").strip().lower()
                            if status == "execution_error":
                                answer = "No pude procesar esa búsqueda en este momento. Intenta de nuevo con una zona o tipo de propiedad."
                            elif status == "empty":
                                answer = (
                                    f"No encontré opciones para {summary}."
                                    if summary
                                    else "No encontré propiedades con esa búsqueda."
                                )
                            elif total_matches > 0 and visible_count > 0:
                                answer = (
                                    f"Encontré {total_matches} opciones para {summary}."
                                    if summary
                                    else f"Encontré {total_matches} propiedades."
                                )
                            else:
                                answer = "Listo, ya procesé esa búsqueda."

                        next_search_state = dict(runtime_ctx.get("realtor_search_state") or {})
                        resolved_search_state = executed_realtor_turn.get("search_state") or {}
                        if resolved_search_state:
                            next_search_state.update(resolved_search_state)
                        facts = dict(executed_realtor_turn.get("facts") or {})
                        if facts:
                            next_search_state["last_result_count"] = facts.get("total_matches") or facts.get("count")
                            next_search_state["last_visible_count"] = facts.get("visible_count")
                            if facts.get("search_summary"):
                                next_search_state["search_summary"] = facts.get("search_summary")
                        next_search_state["awaiting_property_confirmation"] = False
                        runtime_ctx["realtor_search_state"] = next_search_state

            runtime_ctx_realtor_state = runtime_ctx.get("realtor_search_state") or {}
            conversation_extraction_updates = self._build_conversation_extraction_updates(
                query_text=request.query_text,
                vertical_ctx=vertical_ctx,
                runtime_ctx=runtime_ctx,
            )
            runtime_ctx["conversation_extraction_result"] = self._merge_conversation_extraction_result(
                runtime_ctx.get("conversation_extraction_result"),
                common_update=conversation_extraction_updates.get("common"),
                vertical_update=conversation_extraction_updates.get("vertical"),
            )

            should_generate_chat = not bool(answer)
            if should_generate_chat:
                # Generate chat response using hybrid context (history + placeholders for retrieval)
                answer = await self._generate_chat_response(
                    request=request,
                    vertical_ctx=vertical_ctx,
                    conversation_id=conversation_id,
                    system_prompt=client_prompt_text,
                    prompt_slug=chat_prompt_slug,
                    runtime_ctx=runtime_ctx,
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
                    chat_prompt_slug=chat_prompt_slug,
                    realtor_search_state=runtime_ctx_realtor_state,
                    conversation_extraction_result=runtime_ctx.get("conversation_extraction_result"),
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
                    bot_message=self._build_history_bot_message(answer=answer, realtor_turn=realtor_turn),
                )
            except Exception as e:
                logger.error(f"Error saving conversation: {e}")

            # Persist contact data early from user message so name/email/phone are not
            # blocked by async scoring failures/timeouts.
            try:
                contact_seed = conversation_extraction_updates.get("common") or {}
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
                intent=realtor_intent,
                components=final_components,
                conversation_id=conversation_id,
                lead_id=lead_id,
                scorecard_id=scorecard_id,
                scorecard=scorecard,
                realtor_turn=realtor_turn,
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
                            client_id=client_id,
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
        client_id: UUID,
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

            common_update = self._normalize_conversation_common(extraction_result)
            if common_update:
                try:
                    existing_snapshot = await repo.get_conversation_context_snapshot(
                        conversation_id=conversation_id,
                        client_id=client_id,
                    )
                    if existing_snapshot:
                        merged_conversation_extraction = self._merge_conversation_extraction_result(
                            existing_snapshot.get("conversation_extraction_result"),
                            common_update=common_update,
                        )
                        updated_snapshot = dict(existing_snapshot)
                        updated_snapshot["conversation_extraction_result"] = merged_conversation_extraction
                        await repo.set_conversation_context_snapshot(
                            conversation_id=conversation_id,
                            lead_id=lead_id,
                            snapshot=updated_snapshot,
                        )
                except Exception:
                    logger.exception(
                        "Failed to enrich conversation extraction snapshot for lead %s conversation %s",
                        lead_id,
                        conversation_id,
                    )
            
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
