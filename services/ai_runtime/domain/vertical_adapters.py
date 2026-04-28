"""Vertical-specific adapter bundles attached to the shared dependency container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Sequence

if TYPE_CHECKING:
    from services.ai_runtime.graph.realtor.contracts import Property


class VerticalAdapters(Protocol):
    """Marker protocol for vertical-owned dependency bundles."""


class RealtorPropertyRepositoryPort(Protocol):
    """Repository contract used by the realtor graph."""

    async def load_property_types(self) -> list[str]: ...

    async def run_text_to_sql_query(
        self,
        *,
        client_id: str,
        sql: str,
        params: dict[str, object],
    ) -> list["Property"]: ...

    async def load_properties_by_ids(
        self,
        *,
        client_id: str,
        property_ids: Sequence[str],
    ) -> list["Property"]: ...


@dataclass(frozen=True, slots=True)
class RealtorAdapters:
    property_repository: RealtorPropertyRepositoryPort


@dataclass(frozen=True, slots=True)
class HealthcareAdapters:
    pass


@dataclass(frozen=True, slots=True)
class LegalAdapters:
    pass


@dataclass(frozen=True, slots=True)
class InsuranceAdapters:
    pass
