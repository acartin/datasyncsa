"""Dependency bootstrap for the AI runtime."""

from __future__ import annotations

import logging

import httpx

from services.ai_runtime.config.tenant_loader import TenantLoader
from services.ai_runtime.domain.contracts import MailDispatchResult
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.vertical_adapters import (
    HealthcareAdapters,
    InsuranceAdapters,
    LegalAdapters,
    RealtorAdapters,
)
from services.ai_runtime.graph.registry import GraphRegistry
from services.ai_runtime.rag.agency.repository import AgencyRAGRepository
from services.ai_runtime.rag.documents.repository import DocumentsRAGRepository
from services.ai_runtime.runtime.llm import build_llm_port
from services.ai_runtime.runtime.service import ConversationRuntime
from services.ai_runtime.runtime.settings import settings
from services.ai_runtime.runtime.turn_trace import FileTurnTraceStore, TracingLLMPort
from services.data.cache.lead_store import LeadStore
from services.data.cache.session_store import SessionStore
from services.data.cache.tenant_cache import TenantCache
from services.data.repositories.agent_repository import AgentRepository
from services.data.repositories.base import build_engine
from services.data.repositories.conversation_repository import ConversationRepository
from services.data.repositories.property_repository import PropertyRepository
from services.data.repositories.tenant_repository import TenantRepository

logger = logging.getLogger("ai_runtime.worker_dispatcher")


class PlaceholderMailer:
    async def send(self, payload: dict[str, object]):
        return MailDispatchResult(
            enviado=False,
            destinatarios=list(payload.get("destinatarios", [])),
            error="mail provider not configured",
        )


async def _do_scoring_enqueue(
    *,
    url: str,
    payload: dict[str, object],
    token: str,
    timeout: float,
) -> dict[str, object] | None:
    """Fire-and-forget HTTP call to scoring-core enqueue endpoint."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["X-Internal-Token"] = token
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            logger.debug(
                "scoring_enqueue ok job_id=%s conversation_id=%s",
                data.get("id"),
                payload.get("conversation_id"),
            )
            return data if isinstance(data, dict) else None
    except Exception:
        logger.warning(
            "scoring_enqueue failed (fire-and-forget, non-blocking) "
            "conversation_id=%s",
            payload.get("conversation_id"),
            exc_info=True,
        )
    return None


class InlineWorkerDispatcher:
    """Dispatcher that handles fire-and-forget background tasks."""

    def __init__(
        self,
        *,
        scoring_enqueue_url: str,
        scoring_enqueue_enabled: bool,
        internal_token: str,
        enqueue_timeout: float,
    ) -> None:
        self._scoring_enqueue_url = scoring_enqueue_url
        self._scoring_enqueue_enabled = scoring_enqueue_enabled
        self._internal_token = internal_token
        self._enqueue_timeout = enqueue_timeout

    async def fire_and_forget(self, task_name: str, payload: dict[str, object]) -> dict[str, object] | None:
        if task_name == "scoring_enqueue" and self._scoring_enqueue_enabled:
            return await _do_scoring_enqueue(
                url=self._scoring_enqueue_url,
                payload=payload,
                token=self._internal_token,
                timeout=self._enqueue_timeout,
            )
        if task_name == "lead_worker":
            return None
        return None


engine = build_engine()
tenant_cache = TenantCache()
tenant_repository = TenantRepository(engine)
agent_repository = AgentRepository(engine)
trace_store = FileTurnTraceStore(settings.turn_trace_dir, enabled=settings.turn_trace_enabled)
tenant_loader = TenantLoader(
    tenant_repository=tenant_repository,
    agent_repository=agent_repository,
    tenant_cache=tenant_cache,
)
llm = TracingLLMPort(build_llm_port(settings), trace_store)

_scoring_enqueue_url = (
    f"{settings.scoring_core_api}{settings.scoring_core_api_prefix}/scoring/jobs/enqueue"
)

dependencies = GraphDependencies(
    llm=llm,
    session_store=SessionStore(),
    lead_store=LeadStore(),
    tenant_cache=tenant_cache,
    tenant_repository=tenant_repository,
    conversation_repository=ConversationRepository(engine),
    agent_repository=agent_repository,
    agency_rag_repository=AgencyRAGRepository(engine),
    documents_rag_repository=DocumentsRAGRepository(engine),
    mailer=PlaceholderMailer(),
    worker_dispatcher=InlineWorkerDispatcher(
        scoring_enqueue_url=_scoring_enqueue_url,
        scoring_enqueue_enabled=settings.scoring_enqueue_enabled,
        internal_token=settings.internal_api_token,
        enqueue_timeout=settings.scoring_enqueue_timeout_secs,
    ),
    trace_store=trace_store,
    vertical_adapters={
        "realtor": RealtorAdapters(property_repository=PropertyRepository(engine)),
        "healthcare": HealthcareAdapters(),
        "legal": LegalAdapters(),
        "insurance": InsuranceAdapters(),
    },
)
runtime = ConversationRuntime(
    tenant_loader=tenant_loader,
    graph_registry=GraphRegistry(),
    dependencies=dependencies,
)
