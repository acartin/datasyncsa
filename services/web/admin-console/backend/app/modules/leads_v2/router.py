from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Tuple
from uuid import UUID
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User
from app.modules.leads_v2.service import service as lead_v2_service
from app.contracts.ui_schema import WebIAFirstResponse
from app.contracts.scoring_schema import (
    ScoringSchemaV2, 
    ScoringValuesV2,
    DynamicGridConfig,
    DynamicLeadGridColumn
)
from app.config.settings import settings


router = APIRouter()


def _get_tenant_ids(user: User) -> List[UUID]:
    """Extract tenant IDs from user."""
    if not user.tenants:
        return []
    return [tenant.client_id for tenant in user.tenants if getattr(tenant, "client_id", None)]


def _get_primary_client_id(user: User) -> Optional[UUID]:
    """
    Resolve a primary tenant client_id for vertical-aware scoring config.
    """
    tenant_ids = _get_tenant_ids(user)
    if tenant_ids:
        return tenant_ids[0]
    return getattr(user, "client_id", None)


async def _resolve_vertical_schema_for_user(user: User) -> Tuple[Optional[ScoringSchemaV2], str, str]:
    """
    Returns (schema, vertical_slug, vertical_name) for current tenant context.
    """
    client_id = _get_primary_client_id(user)
    if not client_id:
        return None, "generic", "Generic"

    vertical_ctx = await lead_v2_service.get_client_vertical_context(client_id)
    if not vertical_ctx or not vertical_ctx.get("vertical_id"):
        return None, "generic", "Generic"

    schema = await lead_v2_service.get_scoring_schema_for_vertical(
        int(vertical_ctx["vertical_id"]),
        vertical_ctx.get("scoring_model_id"),
    )
    vertical_slug = (vertical_ctx.get("vertical_slug") or "generic").strip()
    vertical_name = (vertical_ctx.get("vertical_name") or vertical_slug or "Generic").strip()
    return schema, vertical_slug, vertical_name


def _grid_props_to_renderer_config(config: DynamicGridConfig) -> dict:
    """
    Adapt backend snake_case contract to the custom grid renderer contract.
    """
    payload = config.model_dump()
    payload["enableFilters"] = payload.pop("enable_filters", False)
    payload["filterConfig"] = payload.pop("filter_config", {})
    return payload


@router.get("", response_model=WebIAFirstResponse)
@router.get("/", response_model=WebIAFirstResponse)
async def get_leads_grid_v2(
    user: User = Depends(current_active_user),
):
    """
    Returns the dynamic leads grid for v2 scoring.
    Uses dynamic scoring schema based on tenant context (vertical + scoring_model_id).
    """
    leads = await lead_v2_service.get_my_leads_with_scoring_v2(
        user_id=user.id,
        is_superuser=user.is_superuser,
        tenant_ids=_get_tenant_ids(user),
    )
    schema, vertical_slug, vertical_name = await _resolve_vertical_schema_for_user(user)
    grid_config = _build_dynamic_grid_config(schema, vertical_slug)
    
    # Transform leads to grid rows
    rows = _transform_leads_to_dynamic_rows(leads, schema)
    
    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "typography",
                "tag": "h2",
                "text": f"Leads - {vertical_name}",
                "class": "mb-4"
            },
            {
                "type": "card",
                "size": "col-12",
                "components": [
                    {
                        "type": "custom-leads-grid",
                        "label": "Panel de Leads (v2)",
                        "properties": _grid_props_to_renderer_config(grid_config)
                    }
                ]
            }
        ],
        "permissions_required": ["leads.view"],
        "metadata": {
            "scoring_schema": schema.model_dump() if schema else None,
            "dynamic_ui_enabled": True
        }
    }


@router.get("/data", response_model=List[dict])
async def list_leads_data_v2(
    user: User = Depends(current_active_user),
):
    """
    Returns raw data for leads with v2 scoring.
    """
    leads = await lead_v2_service.get_my_leads_with_scoring_v2(
        user_id=user.id,
        is_superuser=user.is_superuser,
        tenant_ids=_get_tenant_ids(user),
    )
    schema, _, _ = await _resolve_vertical_schema_for_user(user)

    return _transform_leads_to_dynamic_rows(leads, schema)


@router.get("/{lead_id}", response_model=WebIAFirstResponse)
async def get_lead_detail_v2(
    lead_id: UUID, 
    user: User = Depends(current_active_user)
):
    """
    Returns detailed view for a single lead with v2 scoring.
    """
    # Fetch lead data with v2 scoring
    lead = await lead_v2_service.get_lead_detail_with_scoring_v2(
        lead_id=lead_id,
        user_id=user.id,
        is_superuser=user.is_superuser,
        tenant_ids=_get_tenant_ids(user),
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found or not assigned.")
    
    # Get scoring values
    scoring_values = lead_v2_service.transform_to_scoring_values(lead)
    
    schema = None
    if lead.get("client_id"):
        vertical_ctx = await lead_v2_service.get_client_vertical_context(lead["client_id"])
        if vertical_ctx and vertical_ctx.get("vertical_id"):
            schema = await lead_v2_service.get_scoring_schema_for_vertical(
                int(vertical_ctx["vertical_id"]),
                vertical_ctx.get("scoring_model_id"),
            )
    if not schema:
        schema, _, _ = await _resolve_vertical_schema_for_user(user)
    
    # Build detail components with dynamic scoring
    components = _build_lead_detail_components(lead, scoring_values, schema)
    
    return {
        "layout": "dashboard-standard",
        "components": components,
        "permissions_required": ["leads.view"],
        "metadata": {
            "scoring_values": scoring_values.model_dump(),
            "scoring_schema": schema.model_dump() if schema else None,
            "dynamic_ui_enabled": settings.admin_dynamic_scoring_ui
        }
    }


@router.get("/{lead_id}/scoring", response_model=ScoringValuesV2)
async def get_lead_scoring_values(
    lead_id: UUID,
    user: User = Depends(current_active_user)
):
    """
    Returns scoring values for a specific lead.
    """
    lead = await lead_v2_service.get_lead_detail_with_scoring_v2(
        lead_id=lead_id,
        user_id=user.id,
        is_superuser=user.is_superuser,
        tenant_ids=_get_tenant_ids(user),
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    
    return lead_v2_service.transform_to_scoring_values(lead)


@router.get("/schema/current", response_model=ScoringSchemaV2)
async def get_scoring_schema(
    user: User = Depends(current_active_user)
):
    """
    Returns scoring schema for current tenant context (vertical + scoring_model_id).
    """
    schema, _, _ = await _resolve_vertical_schema_for_user(user)
    
    if not schema:
        raise HTTPException(
            status_code=404, 
            detail="No active scoring schema found for current tenant context"
        )
    
    return schema


def _build_dynamic_grid_config(
    schema: Optional[ScoringSchemaV2],
    vertical_slug: str,
) -> DynamicGridConfig:
    """
    Build dynamic grid configuration based on scoring schema.
    """
    columns = []
    
    # Always include identity column
    columns.append(DynamicLeadGridColumn(
        id="identity",
        label="Lead / Calificación",
        type="gauge-identity",
        sortable=True,
        width="250px",
        icon="ri-shield-user-line"
    ))
    
    # Add dynamic scoring columns if schema exists
    if schema and schema.criteria:
        for criterion in sorted(schema.criteria, key=lambda c: c.display_order):
            columns.append(DynamicLeadGridColumn(
                id=f"scoring_{criterion.criterion_key}",
                label=criterion.label,
                type="scoring-pillar",
                sortable=True,
                icon=criterion.icon or "ri-star-line",
                criterion_key=criterion.criterion_key
            ))
    
    # Add static contact columns
    columns.extend([
        DynamicLeadGridColumn(
            id="email",
            label="Email",
            type="text",
            sortable=True,
            icon="ri-mail-line"
        ),
        DynamicLeadGridColumn(
            id="phone",
            label="Teléfono",
            type="text",
            sortable=True,
            icon="ri-phone-line"
        ),
        DynamicLeadGridColumn(
            id="created",
            label="Fecha",
            type="date",
            sortable=True,
            icon="ri-calendar-line"
        )
    ])
    
    return DynamicGridConfig(
        grid_id=f"leads-v2-{vertical_slug}",
        data_url="/leads_v2/data",
        enable_filters=True,
        columns=columns,
        filter_config={
            "searchFields": ["full_name", "email"],
            "filterableColumns": [
                {"id": "identity", "label": "Lead", "icon": "ri-shield-user-line"}
            ] + ([
                {
                    "id": f"scoring_{c.criterion_key}",
                    "label": c.label,
                    "icon": c.icon or "ri-star-line",
                }
                for c in (schema.criteria if schema else [])
            ] if schema else [])
        },
        actions=[
            {"label": "Ver Detalle", "icon": "ri-eye-line", "action": "navigate", "action_url": "/dashboard/leads_v2/{id}"},
            {"label": "Chat", "icon": "ri-chat-3-line", "action": "navigate", "action_url": "/dashboard/leads/{id}/chat"}
        ]
    )


def _transform_leads_to_dynamic_rows(leads: List[dict], schema: Optional[ScoringSchemaV2]) -> List[dict]:
    """
    Transform leads data to dynamic grid rows based on scoring schema.
    """
    rows = []
    
    for lead in leads:
        score_total = float(lead.get('score_total') or 0)

        # Derive identity color: use prio_color from DB only if present (legacy path).
        # For v2 leads (no prio_color column), send empty string so JS falls through
        # to resolveScoreTierColor(score) which uses ac-score-high/medium/low tokens
        # (teal / yellow / blue-purple — correct for lead quality visualization).
        prio_color = lead.get('prio_color') or ""

        row = {
            "id": str(lead['id']),
            "identity": {
                "name": lead['full_name'] or "",
                "score": score_total,
                "color": prio_color,
            },
            "full_name": lead['full_name'] or "",
            "email": lead['email'] or "-",
            "phone": lead['phone'] or "-",
            "created": lead['created_at'].strftime("%Y-%m-%d") if lead['created_at'] else "-"
        }

        # Add dynamic scoring columns.
        # score_items comes from json_agg — may arrive as a list or a JSON string
        # depending on the asyncpg codec. Normalise to a list of dicts before use.
        raw_score_items = lead.get('score_items')
        if isinstance(raw_score_items, str):
            import json as _json
            try:
                raw_score_items = _json.loads(raw_score_items)
            except Exception:
                raw_score_items = []

        if schema and schema.criteria and raw_score_items:
            score_items_dict = {
                item.get('criterion_key'): item
                for item in (raw_score_items or [])
                if isinstance(item, dict)
            }

            for criterion in schema.criteria:
                item_data = score_items_dict.get(criterion.criterion_key, {})
                score = float(item_data.get('score', 0.0))

                # Find matching band by score range
                band_info: dict = {}
                epsilon = 0.001
                for band in criterion.bands:
                    is_last_band = band is criterion.bands[-1]
                    in_range = (
                        band.min_score - epsilon <= score <= band.max_score + epsilon
                        if is_last_band
                        else band.min_score - epsilon <= score < band.max_score
                    )
                    if in_range:
                        band_info = {
                            "label": band.label,
                            "icon": band.icon,
                            "color": band.color,
                        }
                        break

                row[f"scoring_{criterion.criterion_key}"] = {
                    "score": score,
                    "totalScore": score_total,
                    "label": band_info.get("label", "-"),
                    "icon": band_info.get("icon", "ri-question-line"),
                    "color": band_info.get("color", "thermal-none"),
                }

        rows.append(row)
    
    return rows


def _build_lead_detail_components(
    lead: dict, 
    scoring_values: ScoringValuesV2, 
    schema: Optional[ScoringSchemaV2]
) -> List[dict]:
    """
    Build lead detail components with dynamic scoring visualization.
    """
    components = [
        {
            "type": "layout-row",
            "components": [
                {
                    "type": "layout-col",
                    "size": "col-xl-4",
                    "components": [
                        {
                            "type": "card",
                            "title": "Información del Lead",
                            "components": [
                                {"type": "typography", "tag": "h4", "text": lead['full_name'], "class": "mb-1"},
                                {"type": "typography", "tag": "p", "text": f"Vertical: {(schema.vertical_slug if schema else 'generic').capitalize()}", "class": "text-muted mb-1"},
                                {"type": "typography", "tag": "p", "text": f"Status: {lead.get('status_label') or 'Nuevo'}", "class": "text-muted mb-3"},
                                {"type": "typography", "tag": "p", "text": f"Email: {lead['email'] or '-'}"},
                                {"type": "typography", "tag": "p", "text": f"Tel: {lead['phone'] or '-'}"}
                            ]
                        },
                        {
                            "type": "card-metric",
                            "title": "Score Total",
                            "value": str(scoring_values.score_total),
                            "icon": "ri-star-fill",
                            "color": "warning",
                            "label": scoring_values.priority_label or "Basado en scoring dinámico"
                        }
                    ]
                },
                {
                    "type": "layout-col",
                    "size": "col-xl-8",
                    "components": [
                        {
                            "type": "card",
                            "title": "Scoring Dinámico",
                            "components": _build_scoring_detail_components(scoring_values, schema)
                        }
                    ]
                }
            ]
        }
    ]
    
    return components


def _build_scoring_detail_components(scoring_values: ScoringValuesV2, schema: Optional[ScoringSchemaV2]) -> List[dict]:
    """
    Build scoring detail components with visual bands.
    """
    components = []
    
    if not scoring_values.score_items:
        components.append({
            "type": "typography",
            "tag": "p",
            "text": "No hay datos de scoring disponibles para este lead.",
            "class": "text-muted"
        })
        return components
    
    # Add reasoning if available
    if scoring_values.reasoning:
        components.append({
            "type": "typography",
            "tag": "p",
            "text": scoring_values.reasoning,
            "class": "mb-3"
        })
    
    # Add scoring items as progress bars or metrics
    for item in scoring_values.score_items:
        # Find criterion details from schema
        criterion_label = item.criterion_key
        if schema:
            for criterion in schema.criteria:
                if criterion.criterion_key == item.criterion_key:
                    criterion_label = criterion.label
                    break
        
        components.append({
            "type": "progress-metric",
            "label": criterion_label,
            "value": item.score,
            "maxValue": 100.0,  # Normalized to 0-100
            "color": item.band_color or "primary",
            "icon": item.band_icon or "ri-star-line",
            "subtext": item.explanation or f"Band: {item.band_label or 'N/A'}"
        })
    
    # Add metadata
    if scoring_values.scorecard_id:
        components.append({
            "type": "typography",
            "tag": "p",
            "text": f"Scorecard ID: {scoring_values.scorecard_id}",
            "class": "text-muted small mt-3"
        })
    
    return components
