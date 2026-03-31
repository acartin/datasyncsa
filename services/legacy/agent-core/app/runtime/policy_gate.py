from __future__ import annotations

from app.core.config import settings
from app.models.contracts import GateRejectCode, GateResult, GoalType, RouterDecision, ToolName
from app.runtime.runtime_registry import get_policy_gate_config


def run_policy_gate(decision: RouterDecision, tenant_id: str | None, vertical: str) -> GateResult:
    if settings.allowed_tenants and tenant_id and tenant_id not in settings.allowed_tenants:
        return GateResult(accepted=False, reject_code=GateRejectCode.tenant_not_authorized)

    try:
        gate_policy = get_policy_gate_config()
    except Exception:
        return GateResult(accepted=False, reject_code=GateRejectCode.schema_invalid)

    min_confidence = gate_policy.defaults.min_confidence
    max_tool_calls = gate_policy.defaults.max_tool_calls
    allow_side_effects = gate_policy.defaults.allow_side_effects

    if decision.confidence < min_confidence:
        return GateResult(accepted=False, reject_code=GateRejectCode.confidence_too_low)

    if len(decision.tool_calls) > max_tool_calls:
        return GateResult(accepted=False, reject_code=GateRejectCode.tool_not_permitted)

    vertical_key = vertical.lower() if vertical else "generic"
    policy = gate_policy.verticals.get(vertical_key) or gate_policy.verticals.get("generic")
    if policy is None:
        return GateResult(accepted=False, reject_code=GateRejectCode.schema_invalid)

    if decision.goal not in policy.allowed_goals:
        return GateResult(accepted=False, reject_code=GateRejectCode.tool_not_permitted)

    for tool_call in decision.tool_calls:
        if tool_call.tool_name not in policy.allowed_tools:
            return GateResult(accepted=False, reject_code=GateRejectCode.tool_not_permitted)

    required = gate_policy.required_tools_by_goal.get(decision.goal, set())
    used = {call.tool_name for call in decision.tool_calls}
    if required and not required.issubset(used):
        return GateResult(accepted=False, reject_code=GateRejectCode.missing_required_slots)

    if (
        not allow_side_effects
        and ToolName.workflow in used
    ):
        return GateResult(accepted=False, reject_code=GateRejectCode.side_effects_blocked)

    if decision.goal == GoalType.clarify and decision.tool_calls:
        return GateResult(accepted=False, reject_code=GateRejectCode.schema_invalid)

    return GateResult(accepted=True)
