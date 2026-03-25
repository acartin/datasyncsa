"""Tenant configuration loading helpers for the AI service."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import TenantConfig
from services.data.cache.tenant_cache import TenantCache
from services.data.repositories.agent_repository import AgentRepository
from services.data.repositories.tenant_repository import TenantRepository


class TenantLoader:
    """Loads and caches tenant config plus active agents for the full session lifecycle."""

    def __init__(
        self,
        *,
        tenant_repository: TenantRepository,
        agent_repository: AgentRepository,
        tenant_cache: TenantCache,
    ):
        self.tenant_repository = tenant_repository
        self.agent_repository = agent_repository
        self.tenant_cache = tenant_cache

    async def load(self, client_id: str) -> TenantConfig:
        cached = await self.tenant_cache.get_config(client_id)
        if cached:
            return TenantConfig.model_validate(cached)

        tenant_config = await self.tenant_repository.load_tenant_config(client_id)
        if not tenant_config:
            raise ValueError(f"Unknown client_id: {client_id}")

        ttl = tenant_config.redis_ttl_seconds
        await self.tenant_cache.set_config(client_id, tenant_config.model_dump(mode="json"), ttl)

        agents = await self.agent_repository.load_active_agents(client_id)
        await self.tenant_cache.set_agents(
            client_id,
            [agent.model_dump(mode="json") for agent in agents],
            ttl,
        )
        return tenant_config

