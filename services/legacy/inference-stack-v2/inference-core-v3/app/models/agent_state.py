from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class LeadFieldState(TypedDict, total=False):
    status: str
    value: Any
    source: Optional[str]
    updated_at: Optional[str]


class LeadProgressionState(TypedDict, total=False):
    name: LeadFieldState
    email: LeadFieldState
    phone: LeadFieldState
    budget: LeadFieldState
    urgency: LeadFieldState
    agent_contact_consent: LeadFieldState
    appointment_status: str
    appointment_window: LeadFieldState
    free_preference: LeadFieldState
    next_goal: Optional[str]
    last_asked_field: Optional[str]
    assistant_turns_since_first_cards_shown: Optional[int]


class ConversationMemory(TypedDict, total=False):
    common: Dict[str, Any]
    vertical: Dict[str, Any]


class LastResultSet(TypedDict, total=False):
    status: str
    operation: str
    total_matches: int
    visible_count: int
    search_summary: Optional[str]
    filters: Dict[str, Any]
    property_ids: List[str]
    result_mode: Optional[str]
    documents_count: int
    grounded_answer: Optional[str]


class FollowupPlan(TypedDict, total=False):
    followup_goal: str
    should_ask: bool
    question: Optional[str]
    cta_type: str
    reasoning: Optional[str]


class AgentState(TypedDict, total=False):
    raw_request: Dict[str, Any]
    tenant_runtime_payload: Dict[str, Any]
    repo: Any
    client_id: str
    query_text: str
    conversation_id: str
    lead_id: str
    user_metadata: Dict[str, Any]
    tenant_runtime: Dict[str, Any]
    vertical_slug: str
    vertical_graph_id: str
    active_vertical_subgraph: str

    conversation_state: Dict[str, Any]
    history: List[Dict[str, Any]]
    lead_snapshot: Dict[str, Any]
    conversation_snapshot: Dict[str, Any]
    conversation_extraction_result: Dict[str, Any]

    conversation_memory: ConversationMemory
    lead_progression_state: LeadProgressionState
    active_search_state: Dict[str, Any]
    realtor_search_state: Dict[str, Any]
    last_result_set: LastResultSet
    last_shown_components: List[Dict[str, Any]]
    last_tool_contract: Dict[str, Any]
    last_agent_route: Dict[str, Any]

    filters: Dict[str, Any]
    route_mode: str
    intent: str
    requires_tools: bool
    active_subflow: str
    reasoning: str
    routing_hint: Optional[str]

    tool_plan: List[Dict[str, Any]]
    search_transition_decision: Dict[str, Any]
    selected_tools: List[str]
    tool_outputs: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    execution_facts: Dict[str, Any]
    followup_plan: FollowupPlan
    reference_resolution: Dict[str, Any]
    grounded_answer: Optional[str]

    answer: str
    components: List[Dict[str, Any]]
    side_effects: List[Dict[str, Any]]
    errors: List[str]
    trace: List[str]

    scoring_status: Optional[str]
    scoring_job_id: Optional[str]
    scoring_eta: Optional[str]
