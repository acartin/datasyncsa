from __future__ import annotations

from typing import Any, Dict


class WorkflowExecutor:
    async def execute(self, workflow_plan: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        plan = workflow_plan if isinstance(workflow_plan, dict) else {}
        status = str(plan.get("status") or "pending_provider").strip() or "pending_provider"
        clarification = str(plan.get("clarification") or "").strip() or None
        goal = str(plan.get("workflow_goal") or "external_action").strip() or "external_action"

        if status == "clarify" and clarification:
            return {
                "handled": True,
                "status": "clarify",
                "operation": goal,
                "components": [],
                "facts": {
                    "workflow_goal": goal,
                    "workflow_status": status,
                },
                "clarification": clarification,
            }

        return {
            "handled": True,
            "status": "pending_provider",
            "operation": goal,
            "components": [],
            "facts": {
                "workflow_goal": goal,
                "workflow_status": status,
                "provider_connected": False,
            },
        }


workflow_executor = WorkflowExecutor()
