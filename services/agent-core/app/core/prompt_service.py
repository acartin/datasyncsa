from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.repositories.prompt_repository import prompt_repository


@dataclass(frozen=True)
class PromptBundle:
    planner_system_prompt: str
    synthesizer_system_prompt: str


class PromptService:
    @staticmethod
    def _canonical_vertical(vertical: str | None) -> str:
        token = str(vertical or "").strip().lower()
        if token in {"realtor", "real-estate", "real_estate"}:
            return "realtor"
        return "generic"

    @staticmethod
    def _ai_vertical_slug(vertical: str) -> str | None:
        if vertical == "realtor":
            return "real-estate"
        return None

    async def resolve_runtime_vertical(self, *, tenant_id: str | None, requested_vertical: str | None) -> str:
        requested = self._canonical_vertical(requested_vertical)
        if requested != "generic":
            return requested
        db_vertical = await prompt_repository.get_client_vertical_slug(tenant_id)
        return self._canonical_vertical(db_vertical or requested)

    async def resolve_planner_prompt(
        self,
        *,
        vertical: str,
        tenant_id: str,
        channel: str,
    ) -> str:
        runtime_vertical = await self.resolve_runtime_vertical(
            tenant_id=tenant_id,
            requested_vertical=vertical,
        )
        lead_prompt = await prompt_repository.get_lead_prompt(
            client_id=tenant_id,
            slug="planner_system",
        )
        ai_system_prompt = await prompt_repository.get_ai_system_prompt(
            node_slug="planner_system",
            vertical_slug=self._ai_vertical_slug(runtime_vertical),
        )
        base_prompt = lead_prompt or ai_system_prompt or settings.planner_system_prompt_default

        return (
            f"Tenant={tenant_id or 'default'} | Channel={channel} | Vertical={runtime_vertical}. "
            + base_prompt
            + " "
            + "Contrato RouterDecision estricto: "
            + "goal (answer|clarify|rag|realtor_search|realtor_refine|workflow), "
            + "confidence (0..1), tool_calls (lista), missing_slots (lista), "
            + "clarify_message (requerido si goal=clarify), "
            + "response_mode (text_only|text_plus_cards). "
            + "tool_calls debe usar 'tool_name' literal, no 'name'. "
            + "Para tool_name='realtor_sql' usa SIEMPRE 'realtor_slots' (no 'parameters', no 'params', no SQL libre). "
            + "En realtor_slots, property_type debe ser exactamente apartment|house|land|office. "
            + "Para tool_name='rag' usa SIEMPRE 'rag'. "
            + "Para tool_name='workflow' usa SIEMPRE 'workflow'. "
            + "Si goal=clarify, tool_calls debe ser []. "
            + "No recrees logica de estado; usa state_json/context_snapshot como fuente canonica. "
            + "Contrato de salida:\n{router_decision_schema}"
        )

    async def resolve_synthesizer_prompt(
        self,
        *,
        vertical: str,
        tenant_id: str,
        channel: str,
    ) -> str:
        runtime_vertical = await self.resolve_runtime_vertical(
            tenant_id=tenant_id,
            requested_vertical=vertical,
        )
        lead_prompt = await prompt_repository.get_lead_prompt(
            client_id=tenant_id,
            slug="synthesizer_system",
        )
        ai_system_prompt = await prompt_repository.get_ai_system_prompt(
            node_slug="synthesizer_system",
            vertical_slug=self._ai_vertical_slug(runtime_vertical),
        )
        style_overlay = await prompt_repository.get_lead_prompt(
            client_id=tenant_id,
            slug="primary_chat",
        )
        base_prompt = lead_prompt or ai_system_prompt or settings.synthesizer_system_prompt_default
        if style_overlay:
            base_prompt = (
                base_prompt
                + "\n\n"
                + "Overlay de estilo del tenant (aplica solo tono/forma, no routing ni negocio):\n"
                + style_overlay
            )

        return (
            f"Tenant={tenant_id or 'default'} | Channel={channel} | Vertical={runtime_vertical}. "
            + base_prompt
            + " "
            + "Contrato: "
            + "{\"text\":\"string\",\"evidence_ids\":[\"id\"],\"needs_cards\":true|false}. "
            + "No uses claves alternativas ni markdown. "
            + "No agregues logica de negocio ni decisiones de routing; solo sintetiza."
        )

    async def resolve_prompts(self, *, tenant_id: str, vertical: str, channel: str) -> PromptBundle:
        return PromptBundle(
            planner_system_prompt=await self.resolve_planner_prompt(
                vertical=vertical,
                tenant_id=tenant_id,
                channel=channel,
            ),
            synthesizer_system_prompt=await self.resolve_synthesizer_prompt(
                vertical=vertical,
                tenant_id=tenant_id,
                channel=channel,
            ),
        )


prompt_service = PromptService()
