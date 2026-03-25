"""Dependency bootstrap for the AI runtime."""

from __future__ import annotations

from services.ai_runtime.config.tenant_loader import TenantLoader
from services.ai_runtime.domain.contracts import MailDispatchResult
from services.ai_runtime.domain.ports import GraphDependencies
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


class PlaceholderMailer:
    async def send(self, payload: dict[str, object]):
        return MailDispatchResult(
            enviado=False,
            destinatarios=list(payload.get("destinatarios", [])),
            error="mail provider not configured",
        )


class InlineWorkerDispatcher:
    async def fire_and_forget(self, task_name: str, payload: dict[str, object]) -> None:
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
dependencies = GraphDependencies(
    llm=llm,
    session_store=SessionStore(),
    lead_store=LeadStore(),
    tenant_cache=tenant_cache,
    tenant_repository=tenant_repository,
    conversation_repository=ConversationRepository(engine),
    property_repository=PropertyRepository(engine),
    agent_repository=agent_repository,
    agency_rag_repository=AgencyRAGRepository(engine),
    documents_rag_repository=DocumentsRAGRepository(engine),
    mailer=PlaceholderMailer(),
    worker_dispatcher=InlineWorkerDispatcher(),
    trace_store=trace_store,
)
runtime = ConversationRuntime(
    tenant_loader=tenant_loader,
    graph_registry=GraphRegistry(),
    dependencies=dependencies,
)
