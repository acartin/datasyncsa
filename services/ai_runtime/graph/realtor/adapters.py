"""Helpers to access realtor-owned adapters from the shared dependency container."""

from __future__ import annotations

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.vertical_adapters import RealtorAdapters


def get_realtor_adapters(deps: GraphDependencies) -> RealtorAdapters:
    adapters = deps.get_adapters("realtor")
    if not isinstance(adapters, RealtorAdapters):
        raise TypeError(f"Expected RealtorAdapters for 'realtor', got {type(adapters).__name__}")
    return adapters
