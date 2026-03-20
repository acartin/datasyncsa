from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models.contracts import (
    RealtorSearchSlots,
    RAGQuery,
    RAGResult,
    RealtorSQLResult,
    ToolCall,
    ToolName,
    ToolResult,
)
from app.runtime.runtime_registry import get_tool_registry_config
from app.tools.canonical_property_contract import canonical_feature_keys
from app.tools.rag_client import rag_client
from app.tools.sql_translator import slots_to_sql
from app.tools.workflow_executor import workflow_executor


class ToolExecutor:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = _to_asyncpg_url(database_url or settings.database_url)
        self._engine = create_async_engine(self.database_url, pool_pre_ping=True)

    async def execute(self, *, tenant_id: str, vertical: str, call: ToolCall) -> ToolResult:
        try:
            registry = get_tool_registry_config()
        except Exception:
            return ToolResult(
                tool_name=call.tool_name,
                status="error",
                error_code="tool_registry_unavailable",
                error="tool registry unavailable",
            )

        if call.tool_name not in registry.tool_specs:
            return ToolResult(
                tool_name=call.tool_name,
                status="error",
                error_code="tool_not_registered",
                error="tool not registered in runtime registry",
            )

        vertical_key = vertical.lower().strip() if vertical else "generic"
        vertical_config = registry.verticals.get(vertical_key) or registry.verticals.get("generic")
        if vertical_config is None or call.tool_name not in vertical_config.enabled_tools:
            return ToolResult(
                tool_name=call.tool_name,
                status="error",
                error_code="tool_not_enabled_for_vertical",
                error="tool not enabled for vertical",
            )

        if call.tool_name == ToolName.rag:
            return await self._run_rag(tenant_id, call.rag)
        if call.tool_name == ToolName.realtor_sql:
            return await self._run_realtor_sql(tenant_id, call.realtor_slots)
        if call.tool_name == ToolName.workflow:
            return await self._run_workflow(tenant_id, call.workflow)
        return ToolResult(
            tool_name=call.tool_name,
            status="error",
            error_code="unsupported_tool",
            error="Unsupported tool",
        )

    async def execute_all(self, tenant_id: str, vertical: str, calls: list[ToolCall]) -> list[ToolResult]:
        results: list[ToolResult] = []
        for call in calls:
            results.append(await self.execute(tenant_id=tenant_id, vertical=vertical, call=call))
        return results

    async def _run_rag(self, tenant_id: str, payload: RAGQuery | None) -> ToolResult:
        if not payload:
            return ToolResult(
                tool_name=ToolName.rag,
                status="error",
                error="missing_rag_payload",
                error_code="missing_payload",
            )
        try:
            result = await rag_client.search(tenant_id=tenant_id, query=payload)
            return ToolResult(tool_name=ToolName.rag, status="ok", rag=result)
        except Exception as exc:
            return ToolResult(
                tool_name=ToolName.rag,
                status="error",
                error_code="rag_tool_failed",
                error=str(exc),
            )

    async def _run_realtor_sql(self, tenant_id: str, payload: RealtorSearchSlots | None) -> ToolResult:
        if not payload:
            return ToolResult(
                tool_name=ToolName.realtor_sql,
                status="error",
                error="missing_realtor_slots",
                error_code="missing_payload",
            )
        try:
            sql, params = slots_to_sql.compile(tenant_id=tenant_id, slots=payload.model_dump())
            rows = []
            total = 0
            async with self._engine.connect() as connection:
                rows_raw = (await connection.execute(text(sql), params)).mappings().all()
                total = len(rows_raw)
                for row in rows_raw:
                    rows.append(
                        self._normalize_row(
                            dict(row),
                            requested_property_type=payload.property_type,
                        )
                    )
            result = RealtorSQLResult(
                listings=rows,
                total_found=total,
                sql_executed=sql,
                slots_used=payload,
            )
            return ToolResult(tool_name=ToolName.realtor_sql, status="ok", realtor=result)
        except Exception as exc:
            return ToolResult(
                tool_name=ToolName.realtor_sql,
                status="error",
                error_code="realtor_sql_failed",
                error=str(exc),
            )

    async def _run_workflow(self, tenant_id: str, payload: Any) -> ToolResult:
        if payload is None:
            return ToolResult(
                tool_name=ToolName.workflow,
                status="error",
                error="missing_workflow_payload",
                error_code="missing_payload",
            )
        try:
            workflow_result = await workflow_executor.execute(tenant_id=tenant_id, workflow=payload)
            return ToolResult(
                tool_name=ToolName.workflow,
                status="ok" if workflow_result.success else "error",
                error_code=None if workflow_result.success else "workflow_failed",
                workflow=workflow_result,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=ToolName.workflow,
                status="error",
                error_code="workflow_execution_failed",
                error=str(exc),
            )

    def _normalize_row(self, row: dict[str, Any], requested_property_type: str | None = None) -> dict[str, Any]:
        feature_keys = canonical_feature_keys()
        features_payload = _parse_json_object(row.get("features_json") or row.get("features"))
        address = str(row.get("address_street") or "") or str(features_payload.get(feature_keys["address"]) or "")

        listing_id = str(row.get("listing_id") or row.get("id") or "")
        title = str(row.get("title") or "")
        city = address
        neighborhood = None
        price = _coerce_int(row.get("price"))
        currency = str(row.get("currency") or "USD")
        rooms = _coerce_int(features_payload.get(feature_keys["bedrooms_clean"]))
        area_m2 = _coerce_float(features_payload.get(feature_keys["sqm_clean"]))
        property_type = str(
            features_payload.get("property_type")
            or requested_property_type
            or "generic"
        )
        raw_features = features_payload.get(feature_keys["amenities"]) or []
        raw_images = row.get("image_urls") or []
        listing_url = row.get("listing_url")

        return {
            "listing_id": listing_id,
            "title": title,
            "city": city,
            "neighborhood": neighborhood if neighborhood is not None else None,
            "price": price,
            "currency": currency,
            "rooms": rooms,
            "area_m2": area_m2,
            "property_type": property_type,
            "features": _parse_list(raw_features),
            "image_urls": _parse_list(raw_images),
            "listing_url": str(listing_url) if listing_url is not None else None,
        }


def _coerce_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, Decimal):
            return int(value)

        cleaned = str(value).replace(",", "").strip()
        if not cleaned:
            return 0

        try:
            return int(cleaned)
        except ValueError:
            return int(Decimal(cleaned))
    except (InvalidOperation, ValueError, TypeError):
        return 0
    except Exception:
        return 0


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def _parse_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except Exception:
            pass
    return []


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _to_asyncpg_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url[len("postgresql://") :]
    if database_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + database_url[len("postgres://") :]
    return database_url


tool_executor = ToolExecutor()
