"""Shared mail placeholder."""

from __future__ import annotations

from services.ai_runtime.domain.contracts import MailDispatchResult, TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies


async def mensajear(
    *,
    dependencies: GraphDependencies,
    client_id: str,
    tipo: str,
    destinatarios: list[str],
    datos_cita: dict[str, object],
    tenant_config: TenantConfig,
) -> MailDispatchResult:
    """Dispatch a placeholder confirmation email without blocking the graph."""

    payload = {
        "client_id": client_id,
        "tipo": tipo,
        "destinatarios": destinatarios,
        "datos_cita": datos_cita,
        "tenant_config": tenant_config.model_dump(mode="json"),
    }
    result = await dependencies.mailer.send(payload)
    if isinstance(result, MailDispatchResult):
        return result
    return MailDispatchResult.model_validate(result)

