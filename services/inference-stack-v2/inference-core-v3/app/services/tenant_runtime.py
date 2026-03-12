from dataclasses import dataclass, asdict
from datetime import datetime
from uuid import UUID
from typing import Any, Dict, Optional

from app.repositories.vertical_runtime_repository import VerticalRuntimeRepository


@dataclass(frozen=True)
class ToolSpec:
    name: str
    enabled: bool
    requires_authorization: bool = False
    description: str = ""
    tags: tuple[str, ...] | tuple = ()


@dataclass
class TenantRuntime:
    client_id: str
    vertical_slug: str
    vertical_graph_id: str
    system_prompts: Dict[str, Optional[str]]
    tenant_prompts: Dict[str, Optional[str]]
    resolved_prompts: Dict[str, Optional[str]]
    prompts: Dict[str, Optional[str]]
    tool_registry: Dict[str, ToolSpec]
    runtime_policy: Dict[str, Any]
    generated_at: str


class TenantRuntimeResolver:
    SYSTEM_PROMPT_SLOTS = (
        "route_turn",
        "realtor_turn_planner",
        "realtor_search_transition_judge",
        "generic_turn_planner",
        "lead_followup_planner",
        "realtor_answer_synthesis",
        "generic_answer_synthesis",
        "workflow_planner",
        "workflow_answer_synthesis",
    )

    TENANT_PROMPT_MAP = {
        "primary_chat": "primary_chat",
        "business_context": "business_context",
        "route_turn": "route_turn",
        "generic_turn_planner": "generic_planner_system",
        "generic_answer_synthesis": "generic_answer_synthesis",
        "realtor_turn_planner": "realtor_turn_system",
        "realtor_answer_synthesis": "realtor_answer_synthesis",
        "lead_followup_planner": "lead_followup_planner",
        "workflow_planner": "workflow_planner_system",
        "workflow_answer_synthesis": "workflow_answer_synthesis",
    }

    def __init__(self, cache_service, cache_ttl_seconds: int = 300) -> None:
        self.cache_service = cache_service
        self.cache_ttl_seconds = cache_ttl_seconds

    def _normalize_vertical_slug(self, vertical_slug: str) -> str:
        normalized = (vertical_slug or "").strip().lower().replace("_", "-")
        return normalized or "generic"

    def _is_property_vertical(self, vertical_slug: str) -> bool:
        normalized = self._normalize_vertical_slug(vertical_slug)
        return normalized in {"realtor", "real-estate", "realestate", "property"}

    def _vertical_tools(self, vertical_slug: str) -> Dict[str, ToolSpec]:
        common_tools = {
            "semantic_retrieval": ToolSpec(
                name="semantic_retrieval",
                enabled=True,
                description="Search contextual documents in vector store",
                tags=("rag", "retrieval"),
            ),
            "conversation_memory_read": ToolSpec(
                name="conversation_memory_read",
                enabled=True,
                description="Read conversation memory snapshot",
                tags=("memory",),
            ),
            "lead_snapshot_read": ToolSpec(
                name="lead_snapshot_read",
                enabled=True,
                description="Read lead snapshot",
                tags=("memory", "lead"),
            ),
            "scoring_enqueue": ToolSpec(
                name="scoring_enqueue",
                enabled=True,
                description="Enqueue async scoring side effect",
                tags=("side_effect", "scoring"),
            ),
            "workflow_handoff": ToolSpec(
                name="workflow_handoff",
                enabled=True,
                description="Run workflow planning/handoff subgraph",
                tags=("workflow",),
            ),
        }

        if self._is_property_vertical(vertical_slug):
            realtor_tools = {
                "realtor_sql_search": ToolSpec(
                    name="realtor_sql_search",
                    enabled=True,
                    requires_authorization=False,
                    description="Search realtor listings in lead_properties",
                    tags=("sql", "realtor"),
                ),
                "realtor_inventory": ToolSpec(
                    name="realtor_inventory",
                    enabled=True,
                    description="Count available properties for inventory requests",
                    tags=("realtor",),
                ),
                "realtor_price_range": ToolSpec(
                    name="realtor_price_range",
                    enabled=True,
                    description="Compute property price context",
                    tags=("realtor",),
                ),
            }
            return {**common_tools, **realtor_tools}

        return common_tools

    def _compose_prompt(
        self,
        *,
        system_prompt: Optional[str],
        primary_chat: Optional[str],
        business_context: Optional[str],
        tenant_prompt: Optional[str],
    ) -> Optional[str]:
        parts = []
        if system_prompt:
            parts.append(system_prompt.strip())
        if primary_chat:
            parts.append(f"Contexto base del tenant:\n{primary_chat.strip()}")
        if business_context:
            parts.append(f"Contexto adicional del negocio:\n{business_context.strip()}")
        if tenant_prompt:
            parts.append(f"Politica especifica del tenant para este nodo:\n{tenant_prompt.strip()}")

        merged = "\n\n".join(part for part in parts if part)
        return merged or None

    def _resolve_prompt_bundle(
        self,
        *,
        system_prompts: Dict[str, Optional[str]],
        tenant_prompts: Dict[str, Optional[str]],
    ) -> Dict[str, Optional[str]]:
        primary_chat = tenant_prompts.get("primary_chat")
        business_context = tenant_prompts.get("business_context")
        resolved: Dict[str, Optional[str]] = {
            "primary_chat": primary_chat,
            "business_context": business_context,
        }
        answer_slots = {
            "realtor_answer_synthesis",
            "generic_answer_synthesis",
            "workflow_answer_synthesis",
        }
        for slot in self.SYSTEM_PROMPT_SLOTS:
            resolved[slot] = self._compose_prompt(
                system_prompt=system_prompts.get(slot),
                primary_chat=primary_chat if slot in answer_slots else None,
                business_context=business_context,
                tenant_prompt=tenant_prompts.get(slot),
            )
        return resolved

    async def resolve(self, client_id: UUID, repo: VerticalRuntimeRepository, channel: str = "web") -> TenantRuntime:
        client_id_value = str(client_id)

        if cached := await self.cache_service.get("tenant_runtime", client_id_value, channel):
            if "generated_at" not in cached:
                cached["generated_at"] = datetime.utcnow().isoformat()
            tool_registry_payload = cached.get("tool_registry") or {}
            if isinstance(tool_registry_payload, dict):
                cached["tool_registry"] = {
                    name: (
                        value
                        if isinstance(value, ToolSpec)
                        else ToolSpec(
                            name=value.get("name", name),
                            enabled=bool(value.get("enabled", False)),
                            requires_authorization=bool(value.get("requires_authorization", False)),
                            description=str(value.get("description", "")),
                            tags=tuple(value.get("tags", ())),
                        )
                    )
                    for name, value in tool_registry_payload.items()
                }
            return TenantRuntime(**cached)

        vertical_ctx = await repo.get_client_vertical_context(client_id)
        if not vertical_ctx or not vertical_ctx.get("client_exists"):
            raise ValueError("CLIENT_NOT_FOUND")

        vertical_slug = self._normalize_vertical_slug(str(vertical_ctx.get("vertical_slug") or "generic"))
        vertical_graph_id = f"vertical_graph::{vertical_slug}"

        system_vertical_slug = "real-estate" if self._is_property_vertical(vertical_slug) else vertical_slug
        system_prompts = await repo.get_active_ai_system_prompt_bundle(
            node_slugs=self.SYSTEM_PROMPT_SLOTS,
            vertical_slug=system_vertical_slug,
        )
        tenant_prompts = await repo.get_client_prompt_bundle(
            client_id=client_id,
            slugs=self.TENANT_PROMPT_MAP.values(),
        )
        normalized_tenant_prompts = {
            slot: tenant_prompts.get(prompt_slug)
            for slot, prompt_slug in self.TENANT_PROMPT_MAP.items()
        }
        resolved_prompts = self._resolve_prompt_bundle(
            system_prompts=system_prompts,
            tenant_prompts=normalized_tenant_prompts,
        )

        runtime_policy = {
            "channel": channel,
            "vertical_slug": vertical_slug,
            "allow_fallback_to_last_results": True,
            "max_tool_steps": 2,
            "workflow_enabled": True,
            "prompt_runtime": "ai_system_prompts+lead_ai_prompts",
        }

        tool_registry = self._vertical_tools(vertical_slug)
        serialized_tools = {
            name: {
                "name": spec.name,
                "enabled": spec.enabled,
                "requires_authorization": spec.requires_authorization,
                "description": spec.description,
                "tags": list(spec.tags),
            }
            for name, spec in tool_registry.items()
        }

        payload = {
            "client_id": client_id_value,
            "vertical_slug": vertical_slug,
            "vertical_graph_id": vertical_graph_id,
            "system_prompts": system_prompts,
            "tenant_prompts": normalized_tenant_prompts,
            "resolved_prompts": resolved_prompts,
            "prompts": resolved_prompts,
            "tool_registry": serialized_tools,
            "runtime_policy": runtime_policy,
            "generated_at": datetime.utcnow().isoformat(),
        }
        await self.cache_service.set("tenant_runtime", payload, client_id_value, channel)

        return TenantRuntime(
            client_id=client_id_value,
            vertical_slug=vertical_slug,
            vertical_graph_id=vertical_graph_id,
            system_prompts=system_prompts,
            tenant_prompts=normalized_tenant_prompts,
            resolved_prompts=resolved_prompts,
            prompts=resolved_prompts,
            tool_registry={
                name: ToolSpec(
                    name=value["name"],
                    enabled=value["enabled"],
                    requires_authorization=value["requires_authorization"],
                    description=value["description"],
                    tags=tuple(value["tags"]),
                )
                for name, value in serialized_tools.items()
            },
            runtime_policy=runtime_policy,
            generated_at=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def serialize(runtime: TenantRuntime) -> Dict[str, Any]:
        data = asdict(runtime)
        data["tool_registry"] = {
            name: {
                "name": spec.name,
                "enabled": spec.enabled,
                "requires_authorization": spec.requires_authorization,
                "description": spec.description,
                "tags": list(spec.tags),
            }
            for name, spec in runtime.tool_registry.items()
        }
        return data
