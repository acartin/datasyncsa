from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

from app.core.config import settings
from app.models.agent_state import AgentState
from app.services.answer_synthesizer import answer_synthesizer
from app.services.lead_followup_planner import lead_followup_planner
from app.services.rag_retriever import RagRetriever
from app.services.realtor_context_resolver import realtor_context_resolver
from app.services.realtor_query_compiler import RealtorQueryCompiler
from app.services.realtor_search_executor import RealtorSearchExecutor
from app.services.scoring_client import ScoringClientError, scoring_core_client
from app.services.shown_results_reference_resolver import shown_results_reference_resolver
from app.services.turn_planning import (
    generic_turn_planner,
    realtor_filter_carryover_guard,
    realtor_search_transition_judge,
    realtor_turn_planner,
    turn_router,
    workflow_turn_planner,
)
from app.services.workflow_executor import workflow_executor


logger = logging.getLogger("inference-core-v3.graph")


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base or {})
    for key, value in (extra or {}).items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _coerce_uuid(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


def _default_conversation_memory() -> Dict[str, Dict[str, Any]]:
    return {"common": {}, "vertical": {}}


def _default_lead_progression_state() -> Dict[str, Any]:
    return {
        "name": {"status": "missing", "value": None},
        "email": {"status": "missing", "value": None},
        "phone": {"status": "missing", "value": None},
        "budget": {"status": "missing", "value": None},
        "urgency": {"status": "missing", "value": None},
        "agent_contact_consent": {"status": "missing", "value": None},
        "appointment_status": "not_started",
        "appointment_window": {"status": "missing", "value": None},
        "free_preference": {"status": "missing", "value": None},
        "next_goal": None,
        "last_asked_field": None,
        "has_shown_cards": False,
        "capture_attempt_count": 0,
        "assistant_turns_since_last_capture_attempt": 999,
        "assistant_turns_since_first_cards_shown": 999,
        "last_capture_goal": None,
    }


def _is_placeholder_lead_name(value: str) -> bool:
    candidate = str(value or "").strip()
    if not candidate:
        return True
    return bool(re.fullmatch(r"Lead\s+[0-9a-fA-F]{8}", candidate))


def _merge_lead_snapshot_into_memory(
    conversation_memory: Dict[str, Any],
    lead_progression_state: Dict[str, Any],
    lead_snapshot: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    memory = _deep_merge(_default_conversation_memory(), conversation_memory)
    progression = _deep_merge(_default_lead_progression_state(), lead_progression_state)
    common = _as_dict(memory.get("common"))
    now = datetime.now(timezone.utc).isoformat()

    snapshot_name = str(lead_snapshot.get("full_name") or "").strip()
    snapshot_email = str(lead_snapshot.get("email") or "").strip()
    snapshot_phone = str(lead_snapshot.get("phone") or "").strip()

    if snapshot_name and not _is_placeholder_lead_name(snapshot_name) and not common.get("name"):
        common["name"] = snapshot_name
    if snapshot_email and not common.get("email"):
        common["email"] = snapshot_email
    if snapshot_phone and not common.get("phone"):
        common["phone"] = snapshot_phone

    for field in ("name", "email", "phone"):
        field_state = progression.get(field) if isinstance(progression.get(field), dict) else {"status": "missing"}
        if common.get(field):
            progression[field] = {
                "status": "provided",
                "value": common.get(field),
                "source": field_state.get("source") or "lead_snapshot",
                "updated_at": field_state.get("updated_at") or now,
            }

    memory["common"] = common
    return memory, progression


def _merge_extraction_snapshot_into_memory(
    conversation_memory: Dict[str, Any],
    extraction_result: Dict[str, Any],
) -> Dict[str, Any]:
    memory = _deep_merge(_default_conversation_memory(), conversation_memory)
    extraction = _as_dict(extraction_result)
    common = _as_dict(extraction.get("common"))
    vertical = _as_dict(extraction.get("vertical"))
    if common:
        memory["common"] = _deep_merge(_as_dict(memory.get("common")), common)
    if vertical:
        memory["vertical"] = _deep_merge(_as_dict(memory.get("vertical")), vertical)
    return memory


def _project_vertical_memory_from_search_state(
    conversation_memory: Dict[str, Any],
    active_search_state: Dict[str, Any],
) -> Dict[str, Any]:
    memory = _deep_merge(_default_conversation_memory(), conversation_memory)
    vertical = _as_dict(memory.get("vertical"))
    filters = _as_dict(active_search_state.get("filters"))
    for key in (
        "desired_location",
        "property_type",
        "bedrooms_min",
        "bathrooms_min",
        "garage_min",
        "price_min",
        "price_max",
        "listing_intent",
    ):
        if filters.get(key) not in (None, ""):
            vertical[key] = filters.get(key)
    if active_search_state.get("search_summary"):
        vertical["active_search_summary"] = active_search_state.get("search_summary")
    memory["vertical"] = vertical
    return memory


def _execution_to_last_result_set(execution: Dict[str, Any], components: List[Dict[str, Any]]) -> Dict[str, Any]:
    facts = _as_dict(execution.get("facts"))
    search_state = _as_dict(execution.get("search_state"))
    return {
        "status": execution.get("status") or "empty",
        "operation": execution.get("operation") or search_state.get("intent") or "NONE",
        "total_matches": int(facts.get("total_matches") or facts.get("count") or 0),
        "visible_count": int(facts.get("visible_count") or len(components) or 0),
        "search_summary": facts.get("search_summary") or search_state.get("search_summary"),
        "filters": _as_dict(search_state.get("filters")),
        "property_ids": [str(item.get("id")) for item in components if isinstance(item, dict) and item.get("id")],
        "result_mode": search_state.get("result_mode"),
        "clarification": execution.get("clarification"),
        "min_price": facts.get("min_price"),
        "max_price": facts.get("max_price"),
        "grounded_answer": facts.get("reference_answer"),
    }


def _merge_capture_reply_into_state(state: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    capture = _as_dict(plan.get("capture_reply"))
    field = str(capture.get("field") or "").strip().lower()
    value = capture.get("value")
    if not field or value in (None, ""):
        return {}

    now = datetime.now(timezone.utc).isoformat()
    memory = _deep_merge(_default_conversation_memory(), state.get("conversation_memory") or {})
    common = _as_dict(memory.get("common"))
    if field in {"name", "email", "phone", "budget", "urgency", "agent_contact_consent", "appointment_window", "free_preference"}:
        common[field] = value
    memory["common"] = common

    progression = _deep_merge(_default_lead_progression_state(), state.get("lead_progression_state") or {})
    field_state = _as_dict(progression.get(field))
    progression[field] = {
        "status": "provided",
        "value": value,
        "source": "capture_reply",
        "updated_at": now,
    }
    progression["last_asked_field"] = field

    return {
        "conversation_memory": memory,
        "lead_progression_state": progression,
    }


def _documents_to_last_result_set(query_text: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "status": "results" if documents else "empty",
        "operation": "RAG",
        "total_matches": len(documents),
        "visible_count": len(documents),
        "search_summary": query_text,
        "filters": {},
        "property_ids": [],
        "result_mode": "answer_only",
        "documents_count": len(documents),
    }


async def load_request(state: AgentState) -> Dict[str, Any]:
    raw_request = _as_dict(state.get("raw_request"))
    conversation_id = _coerce_uuid(raw_request.get("conversation_id")) or str(uuid4())
    user_metadata = _as_dict(raw_request.get("user_metadata"))
    return {
        "client_id": str(raw_request.get("client_id") or "").strip(),
        "query_text": str(raw_request.get("query_text") or "").strip(),
        "conversation_id": conversation_id,
        "user_metadata": user_metadata,
        "filters": _as_dict(raw_request.get("filters")),
        "answer": "",
        "components": [],
        "tool_outputs": [],
        "tool_results": [],
        "execution_facts": {},
        "followup_plan": {},
        "reference_resolution": {},
        "grounded_answer": None,
        "side_effects": [],
        "errors": [],
        "trace": list(state.get("trace") or []) + ["load_request"],
    }


async def load_tenant_runtime(state: AgentState) -> Dict[str, Any]:
    tenant_runtime = _as_dict(state.get("tenant_runtime_payload"))
    return {
        "tenant_runtime": tenant_runtime,
        "vertical_slug": str(tenant_runtime.get("vertical_slug") or "generic").strip() or "generic",
        "vertical_graph_id": str(tenant_runtime.get("vertical_graph_id") or "vertical_graph::generic").strip(),
        "trace": list(state.get("trace") or []) + ["load_tenant_runtime"],
    }


async def load_conversation_memory(state: AgentState) -> Dict[str, Any]:
    repo = state.get("repo")
    client_id = _coerce_uuid(state.get("client_id"))
    conversation_id = _coerce_uuid(state.get("conversation_id"))
    trace = list(state.get("trace") or []) + ["load_conversation_memory"]
    if not repo or not client_id or not conversation_id:
        return {"trace": trace}

    lead_id = await repo.get_or_create_lead(
        client_id=UUID(client_id),
        user_metadata=state.get("user_metadata") or {},
        conversation_id=conversation_id,
    )
    history = await repo.get_conversation_messages(conversation_id, UUID(client_id), max_messages=20)
    snapshot = await repo.get_conversation_context_snapshot_by_ids(conversation_id, lead_id) or {}
    lead_snapshot = await repo.get_lead_snapshot(lead_id) or {}

    conversation_memory = _deep_merge(
        _default_conversation_memory(),
        _as_dict(snapshot.get("conversation_memory")),
    )
    if not conversation_memory["common"] and not conversation_memory["vertical"]:
        conversation_memory = _merge_extraction_snapshot_into_memory(
            conversation_memory,
            _as_dict(snapshot.get("conversation_extraction_result")),
        )

    active_search_state = _as_dict(snapshot.get("active_search_state")) or _as_dict(snapshot.get("realtor_search_state"))
    last_result_set = _as_dict(snapshot.get("last_result_set"))
    lead_progression_state = _deep_merge(
        _default_lead_progression_state(),
        _as_dict(snapshot.get("lead_progression_state")),
    )

    conversation_state = {
        "history": history,
        "conversation_snapshot": snapshot,
        "realtor_search_state": active_search_state,
        "conversation_extraction_result": _as_dict(snapshot.get("conversation_extraction_result")),
        "lead_progression_state": lead_progression_state,
        "conversation_memory": conversation_memory,
        "last_result_set": last_result_set,
        "last_shown_components": snapshot.get("last_shown_components") or [],
        "last_tool_contract": _as_dict(snapshot.get("last_tool_contract")),
        "last_agent_route": _as_dict(snapshot.get("last_agent_route")),
    }

    return {
        "lead_id": str(lead_id),
        "history": history,
        "lead_snapshot": lead_snapshot,
        "conversation_snapshot": snapshot,
        "conversation_extraction_result": _as_dict(snapshot.get("conversation_extraction_result")),
        "conversation_memory": conversation_memory,
        "lead_progression_state": lead_progression_state,
        "active_search_state": active_search_state,
        "realtor_search_state": active_search_state,
        "last_result_set": last_result_set,
        "last_shown_components": snapshot.get("last_shown_components") or [],
        "last_tool_contract": _as_dict(snapshot.get("last_tool_contract")),
        "last_agent_route": _as_dict(snapshot.get("last_agent_route")),
        "conversation_state": conversation_state,
        "trace": trace,
    }


async def load_live_lead_state(state: AgentState) -> Dict[str, Any]:
    trace = list(state.get("trace") or []) + ["load_live_lead_state"]
    memory, progression = _merge_lead_snapshot_into_memory(
        state.get("conversation_memory") or {},
        state.get("lead_progression_state") or {},
        state.get("lead_snapshot") or {},
    )
    memory = _merge_extraction_snapshot_into_memory(memory, state.get("conversation_extraction_result") or {})
    memory = _project_vertical_memory_from_search_state(memory, state.get("active_search_state") or {})

    return {
        "conversation_memory": memory,
        "lead_progression_state": progression,
        "trace": trace,
    }


async def route_turn(state: AgentState) -> Dict[str, Any]:
    route = await turn_router.route(state)
    return {
        **route,
        "last_agent_route": {
            "route_mode": route.get("route_mode"),
            "intent": route.get("intent"),
            "active_subflow": route.get("active_subflow"),
            "reasoning": route.get("reasoning"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "trace": list(state.get("trace") or []) + ["route_turn"],
    }


async def realtor_turn_planner_node(state: AgentState) -> Dict[str, Any]:
    plan = await realtor_turn_planner.plan(state)
    capture_updates = _merge_capture_reply_into_state(state, plan)
    return {
        **capture_updates,
        "tool_plan": [plan],
        "intent": plan.get("intent") or state.get("intent"),
        "route_mode": "clarify"
        if str(plan.get("operation") or "").strip().lower() == "clarify"
        else state.get("route_mode"),
        "trace": list(state.get("trace") or []) + ["realtor_turn_planner"],
    }


async def realtor_search_transition_judge_node(state: AgentState) -> Dict[str, Any]:
    tool_plan = state.get("tool_plan") or []
    plan = dict(tool_plan[0]) if tool_plan else {}
    if not plan:
        return {
            "trace": list(state.get("trace") or []) + ["realtor_search_transition_judge"],
        }
    decision = await realtor_search_transition_judge.judge(state)
    return {
        "search_transition_decision": decision,
        "trace": list(state.get("trace") or []) + ["realtor_search_transition_judge"],
    }


async def realtor_filter_carryover_guard_node(state: AgentState) -> Dict[str, Any]:
    tool_plan = state.get("tool_plan") or []
    plan = dict(tool_plan[0]) if tool_plan else {}
    if not plan:
        return {
            "trace": list(state.get("trace") or []) + ["realtor_filter_carryover_guard"],
        }
    decision = _as_dict(state.get("search_transition_decision"))
    guarded = realtor_filter_carryover_guard.guard(
        plan=plan,
        decision=decision,
        active_filters=_as_dict(_as_dict(state.get("active_search_state")).get("filters")),
    )
    return {
        "tool_plan": [guarded],
        "trace": list(state.get("trace") or []) + ["realtor_filter_carryover_guard"],
    }


async def realtor_query_compiler_node(state: AgentState) -> Dict[str, Any]:
    tool_plan = state.get("tool_plan") or []
    plan = tool_plan[0] if tool_plan else {}
    operation = str(plan.get("operation") or "search").strip().lower()
    if operation in {"clarify", "answer"}:
        result_set = {
            "status": "clarify" if operation == "clarify" else "results",
            "operation": plan.get("intent") or state.get("intent"),
            "search_summary": plan.get("search_summary"),
            "filters": _as_dict(plan.get("filters")),
            "result_mode": plan.get("result_mode"),
            "clarification": plan.get("clarification"),
        }
        return {
            "last_tool_contract": plan,
            "last_result_set": result_set,
            "trace": list(state.get("trace") or []) + ["realtor_query_compiler"],
        }

    compiler = RealtorQueryCompiler(search_limit=4)
    compiled = compiler.compile(client_id=str(state.get("client_id")), plan=plan)
    compiled["operation"] = plan.get("intent")
    compiled["tool_name"] = _tool_name_for_realtor_intent(str(plan.get("intent") or state.get("intent") or "PROPERTY_SEARCH"))
    compiled["result_mode"] = plan.get("result_mode")
    return {
        "last_tool_contract": compiled,
        "trace": list(state.get("trace") or []) + ["realtor_query_compiler"],
    }


async def realtor_tool_executor_node(state: AgentState) -> Dict[str, Any]:
    contract = _as_dict(state.get("last_tool_contract"))
    trace = list(state.get("trace") or []) + ["realtor_tool_executor"]
    if str(contract.get("operation") or "").lower() == "clarify" or not contract.get("sql"):
        clarification = str(contract.get("clarification") or "Necesito un poco más de precisión para ayudarte mejor.").strip()
        result_set = _deep_merge(
            _as_dict(state.get("last_result_set")),
            {
                "status": "clarify",
                "clarification": clarification,
            },
        )
        return {
            "tool_outputs": [],
            "tool_results": [],
            "components": [],
            "execution_facts": {"status": "clarify", "pending_clarification": clarification},
            "last_result_set": result_set,
            "trace": trace,
        }

    repo = state.get("repo")
    executor = RealtorSearchExecutor(db_session=repo.session, search_limit=4)
    execution = await executor.execute(
        realtor_turn={
            "intent": contract.get("intent") or state.get("intent"),
            "sql": contract.get("sql"),
            "search_summary": contract.get("search_summary"),
            "filters": contract.get("filters"),
        },
        user_query=str(state.get("query_text") or ""),
        client_id=UUID(str(state.get("client_id"))),
    )
    components = execution.get("components") or []
    tool_output = {
        "tool": contract.get("tool_name") or _tool_name_for_realtor_intent(str(contract.get("intent") or state.get("intent") or "PROPERTY_SEARCH")),
        "execution": execution,
    }
    active_search_state = _as_dict(execution.get("search_state"))
    if contract.get("result_mode"):
        active_search_state["result_mode"] = contract.get("result_mode")
    conversation_memory = _project_vertical_memory_from_search_state(
        state.get("conversation_memory") or {},
        active_search_state,
    )
    last_result_set = _execution_to_last_result_set(execution, components)
    return {
        "tool_outputs": [tool_output],
        "tool_results": [tool_output],
        "components": components,
        "reference_resolution": {},
        "grounded_answer": None,
        "execution_facts": {
            "status": execution.get("status"),
            "total_matches": last_result_set.get("total_matches"),
            "visible_count": last_result_set.get("visible_count"),
            "search_summary": last_result_set.get("search_summary"),
            "filters": last_result_set.get("filters"),
            "pending_clarification": execution.get("clarification"),
        },
        "active_search_state": active_search_state,
        "realtor_search_state": active_search_state,
        "conversation_memory": conversation_memory,
        "last_result_set": last_result_set,
        "last_shown_components": components or state.get("last_shown_components") or [],
        "trace": trace,
    }


async def shown_results_reference_resolver_node(state: AgentState) -> Dict[str, Any]:
    resolution = shown_results_reference_resolver.resolve(state)
    return {
        **resolution,
        "trace": list(state.get("trace") or []) + ["shown_results_reference_resolver"],
    }


async def realtor_context_resolver_node(state: AgentState) -> Dict[str, Any]:
    resolution = realtor_context_resolver.resolve(state)
    return {
        **resolution,
        "trace": list(state.get("trace") or []) + ["realtor_context_resolver"],
    }


async def generic_turn_planner_node(state: AgentState) -> Dict[str, Any]:
    plan = await generic_turn_planner.plan(state)
    operation = str(plan.get("operation") or "").strip().lower()
    next_active_subflow = state.get("active_subflow")
    next_intent = state.get("intent")
    next_route_mode = state.get("route_mode")
    if operation == "rag":
        next_active_subflow = "generic_rag"
        next_intent = "RAG"
        next_route_mode = "tool_required"
    elif operation == "clarify":
        next_intent = "CLARIFICATION"
        next_route_mode = "clarify"
    return {
        "tool_plan": [plan],
        "active_subflow": next_active_subflow,
        "intent": next_intent,
        "route_mode": next_route_mode,
        "trace": list(state.get("trace") or []) + ["generic_turn_planner"],
    }


async def generic_tool_executor_node(state: AgentState) -> Dict[str, Any]:
    tool_plan = state.get("tool_plan") or []
    plan = tool_plan[0] if tool_plan else {}
    operation = str(plan.get("operation") or "answer").strip().lower()
    trace = list(state.get("trace") or []) + ["generic_tool_executor"]
    if operation == "clarify":
        clarification = str(plan.get("clarification") or "¿Podrías darme un poco más de contexto?").strip()
        return {
            "tool_outputs": [],
            "tool_results": [],
            "components": [],
            "execution_facts": {"status": "clarify", "pending_clarification": clarification},
            "last_result_set": {
                "status": "clarify",
                "operation": "RAG",
                "clarification": clarification,
                "search_summary": plan.get("retrieval_query") or state.get("query_text"),
                "filters": _as_dict(plan.get("filters")),
                "result_mode": "answer_only",
            },
            "trace": trace,
        }

    if operation != "rag":
        return {
            "tool_outputs": [],
            "tool_results": [],
            "components": [],
            "execution_facts": {"status": "answer_only"},
            "last_result_set": {
                "status": "answer_only",
                "operation": state.get("intent") or "NONE",
                "search_summary": state.get("query_text"),
                "filters": {},
                "result_mode": "answer_only",
            },
            "trace": trace,
        }

    retriever = RagRetriever()
    query_text = str(plan.get("retrieval_query") or state.get("query_text") or "").strip()
    documents = await retriever.search(
        query_text=query_text,
        client_id=str(state.get("client_id")),
        filters=_as_dict(plan.get("filters")),
        top_k=int(plan.get("top_k") or 4),
    )
    tool_output = {
        "tool": "semantic_retrieval",
        "documents": documents,
        "query": query_text,
        "top_k": int(plan.get("top_k") or 4),
    }
    return {
        "tool_outputs": [tool_output],
        "tool_results": [tool_output],
        "components": [],
        "execution_facts": {
            "status": "results" if documents else "empty",
            "documents_count": len(documents),
            "retrieval_query": query_text,
        },
        "last_result_set": _documents_to_last_result_set(query_text, documents),
        "trace": trace,
    }


async def workflow_planner_node(state: AgentState) -> Dict[str, Any]:
    plan = await workflow_turn_planner.plan(state)
    return {
        "tool_plan": [plan],
        "route_mode": "clarify"
        if str(plan.get("status") or "").strip().lower() == "clarify"
        else state.get("route_mode"),
        "trace": list(state.get("trace") or []) + ["workflow_planner"],
    }


async def workflow_executor_node(state: AgentState) -> Dict[str, Any]:
    tool_plan = state.get("tool_plan") or []
    plan = tool_plan[0] if tool_plan else {}
    execution = await workflow_executor.execute(plan, state)
    facts = _as_dict(execution.get("facts"))
    return {
        "tool_outputs": [{"tool": "workflow_handoff", "execution": execution}],
        "tool_results": [{"tool": "workflow_handoff", "execution": execution}],
        "components": [],
        "execution_facts": _deep_merge({"status": execution.get("status")}, facts),
        "last_result_set": {
            "status": execution.get("status"),
            "operation": execution.get("operation"),
            "search_summary": state.get("query_text"),
            "filters": {},
            "result_mode": "answer_only",
            "clarification": execution.get("clarification"),
        },
        "trace": list(state.get("trace") or []) + ["workflow_executor"],
    }


async def lead_followup_planner_node(state: AgentState) -> Dict[str, Any]:
    plan = await lead_followup_planner.plan(state)
    return {
        "followup_plan": {
            "followup_goal": plan.get("followup_goal"),
            "should_ask": plan.get("should_ask"),
            "question": plan.get("question"),
            "cta_type": plan.get("cta_type"),
            "reasoning": plan.get("reasoning"),
        },
        "conversation_memory": plan.get("conversation_memory") or state.get("conversation_memory") or _default_conversation_memory(),
        "lead_progression_state": plan.get("lead_progression_state") or state.get("lead_progression_state") or _default_lead_progression_state(),
        "trace": list(state.get("trace") or []) + ["lead_followup_planner"],
    }


async def answer_synthesizer_node(state: AgentState) -> Dict[str, Any]:
    answer = await answer_synthesizer.synthesize(state)
    return {
        "answer": answer,
        "trace": list(state.get("trace") or []) + ["answer_synthesizer"],
    }


async def persist_memory(state: AgentState) -> Dict[str, Any]:
    repo = state.get("repo")
    client_id = _coerce_uuid(state.get("client_id"))
    conversation_id = _coerce_uuid(state.get("conversation_id"))
    lead_id = _coerce_uuid(state.get("lead_id"))
    trace = list(state.get("trace") or []) + ["persist_memory"]
    if not repo or not client_id or not conversation_id or not lead_id:
        return {"trace": trace}

    snapshot = {
        "conversation_memory": state.get("conversation_memory") or _default_conversation_memory(),
        "lead_progression_state": state.get("lead_progression_state") or _default_lead_progression_state(),
        "active_search_state": state.get("active_search_state") or {},
        "realtor_search_state": state.get("realtor_search_state") or state.get("active_search_state") or {},
        "last_result_set": state.get("last_result_set") or {},
        "last_shown_components": state.get("components") or state.get("last_shown_components") or [],
        "last_tool_contract": state.get("last_tool_contract") or {},
        "last_agent_route": state.get("last_agent_route") or {},
        "last_tool_results": state.get("tool_results") or [],
        "last_execution_facts": state.get("execution_facts") or {},
        "last_side_effects": state.get("side_effects") or [],
        "conversation_extraction_result": {
            "common": _as_dict(_as_dict(state.get("conversation_memory")).get("common")),
            "vertical": _as_dict(_as_dict(state.get("conversation_memory")).get("vertical")),
        },
        "conversation_meta": {
            "lead_id": lead_id,
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    await repo.upsert_conversation_context_snapshot(
        conversation_id=UUID(conversation_id),
        lead_id=UUID(lead_id),
        snapshot=snapshot,
    )
    counters = await repo.append_conversation_turn(
        conversation_id=conversation_id,
        lead_id=UUID(lead_id),
        user_message=str(state.get("query_text") or ""),
        bot_message=str(state.get("answer") or ""),
    )
    return {
        "trace": trace,
        "counters": counters,
    }


async def enqueue_side_effects(state: AgentState) -> Dict[str, Any]:
    trace = list(state.get("trace") or []) + ["enqueue_side_effects"]
    client_id = _coerce_uuid(state.get("client_id"))
    conversation_id = _coerce_uuid(state.get("conversation_id"))
    lead_id = _coerce_uuid(state.get("lead_id"))
    channel = str(state.get("channel") or "webchat")

    side_effects: List[Dict[str, Any]] = []
    if not client_id or not conversation_id or not lead_id:
        return {
            "trace": trace,
            "side_effects": side_effects,
            "scoring_status": None,
            "scoring_job_id": None,
            "scoring_eta": None,
        }

    tenant_runtime = state.get("tenant_runtime") or {}
    tool_registry = tenant_runtime.get("tool_registry") or {}
    if "scoring_enqueue" not in tool_registry or not settings.scoring_bg_enabled:
        return {
            "trace": trace,
            "side_effects": side_effects,
            "scoring_status": "disabled",
            "scoring_job_id": None,
            "scoring_eta": None,
        }

    try:
        job_data = await scoring_core_client.enqueue_scoring_job(
            client_id=client_id,
            lead_id=lead_id,
            conversation_id=conversation_id,
            channel=channel,
        )
        side_effects.append(
            {
                "tool": "scoring_enqueue",
                "status": str(job_data.get("status") or "queued"),
                "job_id": job_data.get("id"),
            }
        )
        return {
            "trace": trace,
            "side_effects": side_effects,
            "scoring_status": "pending",
            "scoring_job_id": job_data.get("id"),
            "scoring_eta": job_data.get("scheduled_for"),
        }
    except ScoringClientError as exc:
        if exc.status_code in {400, 404, 422}:
            logger.info(
                "Scoring side effect disabled by scoring-core conversation=%s status=%s detail=%s",
                conversation_id,
                exc.status_code,
                exc.detail,
            )
            side_effects.append(
                {
                    "tool": "scoring_enqueue",
                    "status": "disabled",
                    "reason": exc.detail,
                }
            )
            return {
                "trace": trace,
                "side_effects": side_effects,
                "scoring_status": "disabled",
                "scoring_job_id": None,
                "scoring_eta": None,
            }
        logger.warning(
            "Scoring side effect enqueue failed conversation=%s status=%s detail=%s",
            conversation_id,
            exc.status_code,
            exc.detail,
        )
        side_effects.append({"tool": "scoring_enqueue", "status": "error"})
        return {
            "trace": trace,
            "side_effects": side_effects,
            "scoring_status": "error",
            "scoring_job_id": None,
            "scoring_eta": None,
        }
    except Exception:
        logger.exception("Failed to enqueue scoring side effect conversation=%s", conversation_id)
        side_effects.append({"tool": "scoring_enqueue", "status": "error"})
        return {
            "trace": trace,
            "side_effects": side_effects,
            "scoring_status": "error",
            "scoring_job_id": None,
            "scoring_eta": None,
        }


def return_response(state: AgentState) -> Dict[str, Any]:
    return {
        "trace": list(state.get("trace") or []) + ["return_response"],
    }


def select_realtor_compiler_route(state: AgentState) -> str:
    tool_plan = state.get("tool_plan") or []
    plan = tool_plan[0] if tool_plan else {}
    operation = str(plan.get("operation") or "search").strip().lower()
    query_scope = str(plan.get("query_scope") or "").strip().lower()
    target_entity = str(plan.get("target_entity") or "").strip().lower()
    if query_scope == "shown_result" and target_entity == "single_shown_property":
        return "shown_results_reference_resolver"
    if operation == "answer":
        return "realtor_context_resolver"
    if operation in {"search", "inventory", "price_range"}:
        return "realtor_search_transition_judge"
    return "lead_followup_planner"


def select_generic_executor_route(state: AgentState) -> str:
    tool_plan = state.get("tool_plan") or []
    plan = tool_plan[0] if tool_plan else {}
    operation = str(plan.get("operation") or "answer").strip().lower()
    if operation == "rag":
        return "generic_tool_executor"
    return "lead_followup_planner"


def _tool_name_for_realtor_intent(intent: str) -> str:
    normalized = str(intent or "PROPERTY_SEARCH").strip().upper()
    if normalized == "PROPERTY_INVENTORY":
        return "realtor_inventory"
    if normalized == "PROPERTY_PRICE_RANGE":
        return "realtor_price_range"
    return "realtor_sql_search"
