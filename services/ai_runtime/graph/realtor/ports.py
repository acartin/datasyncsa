"""Realtor-specific integration ports."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from services.ai_runtime.graph.realtor.contracts import Property


class PropertyRepositoryPort(Protocol):
    async def load_property_types(self) -> list[str]: ...

    async def run_text_to_sql_query(
        self,
        *,
        client_id: str,
        sql: str,
        params: dict[str, Any],
    ) -> list[Property]: ...

    async def load_properties_by_ids(
        self,
        *,
        client_id: str,
        property_ids: Sequence[str],
    ) -> list[Property]: ...
