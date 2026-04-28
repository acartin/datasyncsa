import unittest
from types import SimpleNamespace

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import BaseGraphState
from services.ai_runtime.verticals import get_supported_verticals, get_vertical_spec


def _deps_stub() -> GraphDependencies:
    placeholder = object()
    return GraphDependencies(
        llm=placeholder,
        session_store=placeholder,
        lead_store=placeholder,
        tenant_cache=placeholder,
        tenant_repository=placeholder,
        conversation_repository=placeholder,
        agent_repository=placeholder,
        agency_rag_repository=placeholder,
        documents_rag_repository=placeholder,
        mailer=placeholder,
        worker_dispatcher=placeholder,
        trace_store=SimpleNamespace(append_event=lambda *args, **kwargs: None),
        vertical_adapters={},
    )


class VerticalContractTests(unittest.TestCase):
    def test_supported_verticals_register_complete_specs(self) -> None:
        deps = _deps_stub()

        for slug in get_supported_verticals():
            spec = get_vertical_spec(slug)
            self.assertTrue(issubclass(spec.state_model, BaseGraphState))
            self.assertTrue(spec.scoring_criteria)
            self.assertTrue(callable(getattr(spec.policy, "snapshot_search_context")))
            self.assertTrue(callable(getattr(spec.policy, "resolve_visible_reference_items")))
            self.assertTrue(callable(getattr(spec.policy, "resolve_reference_candidates")))
            self.assertTrue(callable(getattr(spec.policy, "snapshot_focused_entity")))
            self.assertTrue(callable(getattr(spec.policy, "handle_quick_action")))
            self.assertTrue(callable(getattr(spec.policy, "resolve_journey")))
            self.assertTrue(callable(getattr(spec.policy, "progressive_field_plan")))
            graph = spec.graph_builder(deps)
            self.assertTrue(hasattr(graph, "ainvoke"))


if __name__ == "__main__":
    unittest.main()
