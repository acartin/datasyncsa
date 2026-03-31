from __future__ import annotations

from typing import Any, Optional, TypedDict

from app.models.contracts import (
    AnswerEnvelope,
    GateResult,
    GuardrailResult,
    RouterDecision,
    SynthesizerOutput,
    ToolResult,
)


class AgentCoreState(TypedDict, total=False):
    raw_input: dict[str, Any]
    normalized_input: dict[str, Any]
    conversation_id: str
    tenant_id: Optional[str]
    channel: Optional[str]
    lead_id: Optional[str]
    router_decision: RouterDecision
    gate_result: GateResult
    tool_results: list[ToolResult]
    synthesizer_output: SynthesizerOutput
    guardrail_result: GuardrailResult
    answer_envelope: AnswerEnvelope
    error_code: Optional[str]
    errors: list[str]
    node_timings_ms: dict[str, float]
    scoring_job_id: str
    scoring_status: str
