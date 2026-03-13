from __future__ import annotations

import httpx

from app.core.config import settings
from app.models.contracts import WorkflowCall, WorkflowResult


class WorkflowExecutor:
    def _resolve_workflow(self, workflow: WorkflowCall) -> str:
        registry = settings.workflow_registry
        if workflow.workflow_name not in registry:
            raise ValueError("workflow_not_registered")
        entry = registry[workflow.workflow_name]
        return str(entry.get("url") or "").strip()

    async def execute(self, tenant_id: str, workflow: WorkflowCall) -> WorkflowResult:
        endpoint = self._resolve_workflow(workflow)
        if not endpoint:
            raise ValueError("workflow_missing_url")

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(endpoint, json={"tenant_id": tenant_id, "params": workflow.params})
            if response.status_code >= 400:
                text = response.text[:240]
                raise RuntimeError(f"workflow_http_error:{response.status_code}:{text}")
            data = response.json()

        return WorkflowResult(
            workflow_name=workflow.workflow_name,
            success=bool(data.get("success", False)),
            output=data if isinstance(data, dict) else {},
        )


workflow_executor = WorkflowExecutor()
