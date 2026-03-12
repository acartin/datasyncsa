import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.builder import V3FlowGraph
from app.models.chat_v3 import ChatV3Request
from app.repositories.vertical_runtime_repository import VerticalRuntimeRepository
from app.services.cache_service import cache_service
from app.services.tenant_runtime import TenantRuntimeResolver

logger = logging.getLogger("inference-core-v3.orchestrator")


class InferenceCoreV3Orchestrator:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repo = VerticalRuntimeRepository(db_session)
        self.runtime_resolver = TenantRuntimeResolver(cache_service, cache_ttl_seconds=60)
        self.graph = V3FlowGraph()

    async def load_tenant_runtime(self, client_id: UUID, user_metadata: dict | None) -> dict:
        channel = "web"
        if isinstance(user_metadata, dict):
            channel = str(
                user_metadata.get("channel")
                or user_metadata.get("channel_slug")
                or user_metadata.get("channel_type")
                or "web"
            )

        tenant_runtime = await self.runtime_resolver.resolve(
            client_id=client_id,
            repo=self.repo,
            channel=channel,
        )
        return self.runtime_resolver.serialize(tenant_runtime)

    async def process_chat(self, request: ChatV3Request) -> dict:
        tenant_runtime_payload = await self.load_tenant_runtime(request.client_id, request.user_metadata or {})

        state = {
            "raw_request": request.model_dump(mode="json"),
            "tenant_runtime_payload": tenant_runtime_payload,
            "repo": self.repo,
        }

        result = await self.graph.run(state)
        conversation_id = result.get("conversation_id") or request.conversation_id or str(uuid4())

        return {
            "answer": result.get("answer", ""),
            "conversation_id": str(conversation_id),
            "lead_id": result.get("lead_id"),
            "intent": result.get("intent"),
            "route_mode": result.get("route_mode"),
            "active_subflow": result.get("active_subflow"),
            "vertical_slug": result.get("vertical_slug", "generic"),
            "scoring_status": result.get("scoring_status"),
            "scoring_job_id": result.get("scoring_job_id"),
            "scoring_eta": result.get("scoring_eta"),
            "components": result.get("components", []),
            "metadata": {
                "source": "inference-core-v3",
                "side_effects": result.get("side_effects", []),
            },
            "tracing": {
                "trace": result.get("trace", []),
            },
        }
