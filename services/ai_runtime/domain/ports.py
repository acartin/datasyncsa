"""Abstract integration ports used by the AI runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from services.ai_runtime.domain.contracts import (
    AgentRecord,
    IntentDefinition,
    TurnAnalysis,
    MailDispatchResult,
    Property,
    PropertyComparisonScore,
    ReferenceDecision,
    TenantConfig,
    TextToSQLResult,
)
from services.ai_runtime.domain.prompts import PromptInput


class LLMPort(Protocol):
    async def analyze_turn(self, prompt: PromptInput) -> TurnAnalysis: ...

    async def classify_reference(self, prompt: PromptInput) -> ReferenceDecision: ...

    async def detect_intents(self, prompt: PromptInput) -> list[IntentDefinition]: ...

    async def evaluate_lazy_condition(self, prompt: PromptInput) -> bool: ...

    async def extract_search_filters(self, prompt: PromptInput) -> dict[str, Any]: ...

    async def extract_memory_entities(self, prompt: PromptInput) -> dict[str, Any]: ...

    async def synthesize_response(self, prompt: PromptInput) -> str: ...

    async def redact_recommendation(self, prompt: PromptInput) -> str: ...

    async def translate_text_to_sql(self, prompt: PromptInput) -> TextToSQLResult: ...

    async def extract_lead_fields(self, prompt: PromptInput) -> dict[str, Any]: ...

    async def extract_appointment_fields(self, prompt: PromptInput) -> dict[str, Any]: ...

    async def score_turn(self, prompt: PromptInput) -> dict[str, Any]: ...


class SessionStorePort(Protocol):
    async def get_state(self, client_id: str, session_id: str) -> dict[str, Any] | None: ...

    async def set_state(self, client_id: str, session_id: str, payload: dict[str, Any], ttl: int) -> None: ...

    async def delete_session(self, client_id: str, session_id: str) -> bool: ...


class LeadStorePort(Protocol):
    async def get_lead_state(self, client_id: str, session_id: str) -> dict[str, Any] | None: ...

    async def set_lead_state(self, client_id: str, session_id: str, payload: dict[str, Any], ttl: int) -> None: ...

    async def delete_session(self, client_id: str, session_id: str) -> bool: ...


class TenantCachePort(Protocol):
    async def get_config(self, client_id: str) -> dict[str, Any] | None: ...

    async def set_config(self, client_id: str, payload: dict[str, Any], ttl: int) -> None: ...

    async def get_agents(self, client_id: str) -> list[dict[str, Any]] | None: ...

    async def set_agents(self, client_id: str, payload: list[dict[str, Any]], ttl: int) -> None: ...


class TenantRepositoryPort(Protocol):
    async def load_tenant_config(self, client_id: str) -> TenantConfig | None: ...


class ConversationRepositoryPort(Protocol):
    async def load_history(
        self,
        *,
        client_id: str,
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]: ...

    async def persist_turn(self, payload: dict[str, Any]) -> None: ...


class PropertyRepositoryPort(Protocol):
    async def load_property_types(self) -> list[str]: ...

    async def run_text_to_sql_query(
        self,
        *,
        client_id: str,
        sql: str,
        params: dict[str, Any],
    ) -> list[Property]: ...

    async def load_properties_by_ids(
        self,
        *,
        client_id: str,
        property_ids: Sequence[str],
    ) -> list[Property]: ...


class AgentRepositoryPort(Protocol):
    async def load_active_agents(self, client_id: str) -> list[AgentRecord]: ...

    async def assign_for_zone(self, *, client_id: str, zone: str | None) -> AgentRecord | None: ...


class VectorRepositoryPort(Protocol):
    async def search(
        self,
        *,
        client_id: str,
        query_embedding: Sequence[float],
        query_text: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]: ...


class MailerPort(Protocol):
    async def send(self, payload: dict[str, Any]) -> MailDispatchResult: ...


class WorkerDispatcherPort(Protocol):
    async def fire_and_forget(self, task_name: str, payload: dict[str, Any]) -> None: ...


class TraceStorePort(Protocol):
    def start_turn(self, context: Any, *, request_metadata: dict[str, Any], state_summary: dict[str, Any]) -> None: ...

    def append_event(self, kind: str, name: str, payload: dict[str, Any] | None = None) -> None: ...

    def finish_turn(
        self,
        *,
        status: str,
        final_state_summary: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None: ...

    def list_sessions(self, client_id: str) -> list[dict[str, Any]]: ...

    def list_turns(self, client_id: str, session_id: str) -> list[dict[str, Any]]: ...

    def delete_session(self, client_id: str, session_id: str) -> dict[str, Any]: ...

    def get_turn(self, client_id: str, session_id: str, turn: int) -> dict[str, Any] | None: ...


@dataclass(slots=True)
class GraphDependencies:
    llm: LLMPort
    session_store: SessionStorePort
    lead_store: LeadStorePort
    tenant_cache: TenantCachePort
    tenant_repository: TenantRepositoryPort
    conversation_repository: ConversationRepositoryPort
    property_repository: PropertyRepositoryPort
    agent_repository: AgentRepositoryPort
    agency_rag_repository: VectorRepositoryPort
    documents_rag_repository: VectorRepositoryPort
    mailer: MailerPort
    worker_dispatcher: WorkerDispatcherPort
    trace_store: TraceStorePort
