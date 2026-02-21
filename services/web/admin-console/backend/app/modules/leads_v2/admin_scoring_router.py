import base64
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.contracts.ui_schema import WebIAFirstResponse
from app.modules.auth.dependencies import RoleChecker
from app.modules.auth.models import User
from app.modules.shared.sdui import create_modal_action, delete_action, edit_action, encode_schema_b64

from .admin_scoring_schemas import (
    VerticalRow,
    VerticalCreate,
    VerticalUpdate,
    ScoringModelRow,
    ScoringModelCreate,
    ScoringModelUpdate,
    ScoringCriterionRow,
    ScoringCriterionCreate,
    ScoringCriterionUpdate,
    ScoringBandRow,
    ScoringBandCreate,
    ScoringBandUpdate,
    ScoringPromptRow,
    ScoringPromptCreate,
    ScoringPromptUpdate,
)
from .admin_scoring_service import service


router = APIRouter(
    prefix="/system/verticals",
    tags=["System Verticals & Scoring Config"],
    dependencies=[Depends(RoleChecker(["system-user", "admin"]))],
)


def _vertical_form_schema() -> list[dict]:
    return [
        {"name": "name", "label": "Nombre", "type": "text", "required": True, "min_length": 2},
        {"name": "slug", "label": "Slug", "type": "text", "required": True, "min_length": 2},
    ]


def _model_form_schema(vertical_id: Optional[int] = None) -> list[dict]:
    vertical_field: dict[str, Any]
    if vertical_id is not None:
        vertical_field = {"name": "vertical_id", "label": "Vertical", "type": "hidden", "required": True, "value": vertical_id}
    else:
        vertical_field = {"name": "vertical_id", "label": "Vertical", "type": "select", "source": "/system/verticals/lookups/verticals", "required": True}

    return [
        vertical_field,
        {"name": "name", "label": "Nombre Modelo", "type": "text", "required": True},
        {"name": "version", "label": "Versión Modelo", "type": "number", "required": True, "value": 1},
        {"name": "prompt_version", "label": "Versión Prompt", "type": "number", "required": True, "value": 1},
        {"name": "normalization_strategy", "label": "Estrategia", "type": "text", "required": False},
        {"name": "is_active", "label": "Activo", "type": "switch", "value": True},
    ]


def _criterion_form_schema(model_id: Optional[UUID] = None) -> list[dict]:
    model_field: dict[str, Any]
    if model_id is not None:
        model_field = {"name": "model_id", "label": "Modelo", "type": "hidden", "required": True, "value": str(model_id)}
    else:
        model_field = {"name": "model_id", "label": "Modelo", "type": "select", "source": "/system/verticals/lookups/models", "required": True}

    return [
        model_field,
        {"name": "criterion_key", "label": "Criterion Key", "type": "text", "required": True},
        {"name": "label", "label": "Label", "type": "text", "required": True},
        {"name": "weight", "label": "Weight", "type": "number", "required": True, "value": 1},
        {"name": "min_score", "label": "Min Score", "type": "number", "required": True, "value": 0},
        {"name": "max_score", "label": "Max Score", "type": "number", "required": True, "value": 10},
        {"name": "display_order", "label": "Display Order", "type": "number", "required": True, "value": 0},
        {"name": "is_active", "label": "Activo", "type": "switch", "value": True},
    ]


def _band_form_schema(criterion_id: Optional[UUID] = None, force_hidden: bool = False) -> list[dict]:
    criterion_field: dict[str, Any]
    if criterion_id is not None or force_hidden:
        criterion_field = {"name": "criterion_id", "label": "Criterio", "type": "hidden", "required": True, "value": str(criterion_id) if criterion_id is not None else ""}
    else:
        criterion_field = {"name": "criterion_id", "label": "Criterio", "type": "select", "source": "/system/verticals/lookups/criteria", "required": True}

    return [
        criterion_field,
        {"name": "band_key", "label": "Band Key", "type": "text", "required": True},
        {"name": "label", "label": "Label", "type": "text", "required": True},
        {"name": "min_score", "label": "Min Score", "type": "number", "required": True},
        {"name": "max_score", "label": "Max Score", "type": "number", "required": True},
        {"name": "icon", "label": "Icon", "type": "text", "required": False},
        {"name": "color", "label": "Color", "type": "color", "required": False, "value": "#22c55e"},
    ]


def _prompt_form_schema(model_id: Optional[UUID] = None) -> list[dict]:
    model_field: dict[str, Any]
    if model_id is not None:
        model_field = {"name": "model_id", "label": "Modelo", "type": "hidden", "required": True, "value": str(model_id)}
    else:
        model_field = {"name": "model_id", "label": "Modelo", "type": "select", "source": "/system/verticals/lookups/models", "required": True}

    return [
        model_field,
        {"name": "version", "label": "Versión Prompt", "type": "number", "required": True, "value": 1},
        {"name": "prompt_template", "label": "Prompt Template", "type": "textarea", "required": True, "rows": 20},
        {"name": "is_active", "label": "Activo", "type": "switch", "value": True},
    ]


def _prompt_form_schema_force_hidden() -> list[dict]:
    schema = _prompt_form_schema()
    for field in schema:
        if field.get("name") == "model_id":
            field["type"] = "hidden"
            field["value"] = ""
    return schema


def _encode_b64_json(payload: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


@router.get("", response_model=WebIAFirstResponse)
async def get_verticals_scoring_admin_ui(
    vertical_id: Optional[int] = Query(None),
    model_id: Optional[UUID] = Query(None),
    criterion_id: Optional[UUID] = Query(None),
    user: User = Depends(RoleChecker(["system-user", "admin"])),
):
    warnings: List[str] = []

    selected_vertical = await service.get_vertical(vertical_id) if vertical_id is not None else None
    if vertical_id is not None and not selected_vertical:
        warnings.append(f"Vertical {vertical_id} no encontrada. Se limpió el contexto.")
        vertical_id = None

    selected_model = await service.get_scoring_model(model_id) if model_id is not None else None
    if model_id is not None and not selected_model:
        warnings.append(f"Modelo {model_id} no encontrado. Se limpió el contexto.")
        model_id = None

    if selected_model:
        if vertical_id is None and selected_model.vertical_id is not None:
            vertical_id = selected_model.vertical_id
            selected_vertical = await service.get_vertical(vertical_id)
        if selected_vertical and selected_model.vertical_id != selected_vertical.id:
            warnings.append("El modelo seleccionado no pertenece al vertical activo. Se reinició selección de modelo.")
            model_id = None
            selected_model = None
            criterion_id = None

    selected_criterion = await service.get_scoring_criterion(criterion_id) if criterion_id is not None else None
    if criterion_id is not None and not selected_criterion:
        warnings.append(f"Criterio {criterion_id} no encontrado. Se limpió el contexto.")
        criterion_id = None

    if selected_criterion:
        if model_id is None:
            model_id = selected_criterion.model_id
            selected_model = await service.get_scoring_model(model_id)
            if selected_model and vertical_id is None and selected_model.vertical_id is not None:
                vertical_id = selected_model.vertical_id
                selected_vertical = await service.get_vertical(vertical_id)
        elif selected_model and selected_criterion.model_id != selected_model.id:
            warnings.append("El criterio seleccionado no pertenece al modelo activo. Se reinició selección de criterio.")
            criterion_id = None
            selected_criterion = None

    if selected_vertical is None and vertical_id is not None:
        selected_vertical = await service.get_vertical(vertical_id)
    if selected_model is None and model_id is not None:
        selected_model = await service.get_scoring_model(model_id)
    if selected_criterion is None and criterion_id is not None:
        selected_criterion = await service.get_scoring_criterion(criterion_id)

    vertical_schema = _vertical_form_schema()
    model_schema = _model_form_schema()
    criterion_schema = _criterion_form_schema()
    model_create_schema = _model_form_schema(vertical_id=vertical_id) if selected_vertical else model_schema
    criterion_create_schema = _criterion_form_schema(model_id=model_id) if selected_model else criterion_schema

    vertical_schema_b64 = encode_schema_b64(vertical_schema)
    model_schema_b64 = encode_schema_b64(model_schema)
    criterion_schema_b64 = encode_schema_b64(criterion_schema)
    model_create_schema_b64 = encode_schema_b64(model_create_schema)
    criterion_create_schema_b64 = encode_schema_b64(criterion_create_schema)
    prompt_modal_schema = [
        {"name": "model_id", "label": "Modelo", "type": "hidden", "required": True, "value": "{context_model_id}"},
        {"name": "version", "label": "Versión Prompt", "type": "number", "required": True, "value": 1},
        {"name": "prompt_template", "label": "Prompt Template", "type": "textarea", "required": True, "rows": 20},
        {"name": "is_active", "label": "Activo", "type": "switch", "value": True},
    ]
    prompt_modal_schema_b64 = encode_schema_b64(prompt_modal_schema)
    prompt_modal_config_b64 = _encode_b64_json(
        {
            "data_url": "/system/verticals/prompts/data?model_id={context_model_id}",
            "columns": [
                {"id": "version", "label": "Versión", "sortable": True},
                {"id": "is_active", "label": "Activo", "type": "badge", "badge_map": {"true": "success", "false": "secondary"}},
                {"id": "updated_at", "label": "Actualizado", "type": "datetime", "sortable": True},
            ],
            "enableFilters": True,
            "filterConfig": {"searchFields": ["version", "prompt_template"]},
            "actions": [
                edit_action("/system/verticals/prompts/{id}", prompt_modal_schema_b64),
                delete_action("/system/verticals/prompts/{id}"),
            ],
            "header_actions": [
                create_modal_action(
                    action_url="/system/verticals/prompts",
                    schema_b64=prompt_modal_schema_b64,
                    modal_title="Nuevo Prompt",
                    label="Nuevo Prompt",
                    icon="ri-add-line",
                )
            ],
            "schema": prompt_modal_schema,
        }
    )

    breadcrumbs = ["Verticales"]
    if selected_vertical:
        breadcrumbs.append(f"Modelos: {selected_vertical.name}")
    if selected_model:
        breadcrumbs.append(f"Modelo activo: {selected_model.name} v{selected_model.version}")
    if selected_criterion:
        breadcrumbs.append(f"Criterio activo: {selected_criterion.criterion_key}")

    components: List[Dict[str, Any]] = [
        {
            "type": "typography",
            "tag": "h2",
            "text": "Configuración de Verticales y Scoring v2",
            "class": "mb-2",
        },
        {
            "type": "typography",
            "tag": "p",
            "text": " > ".join(breadcrumbs),
            "class": "mb-4 text-muted",
        },
    ]

    for warning in warnings:
        components.append(
            {
                "type": "typography",
                "tag": "p",
                "text": warning,
                "class": "alert alert-warning mb-3",
            }
        )

    components.append(
        {
            "type": "row",
            "class_": "g-3",
            "components": [
                {
                    "type": "col",
                    "class_": "col-xl-4 col-lg-12",
                    "components": [
                        {
                            "type": "card",
                            "title": "1) Verticales",
                            "components": [
                                {
                                    "type": "grid-visual",
                                    "label": "Verticales",
                                    "properties": {
                                        "data_url": "/system/verticals/data",
                                        "columns": [
                                            {"id": "id", "label": "ID", "sortable": True},
                                            {"id": "name", "label": "Nombre", "sortable": True},
                                        ],
                                        "enableFilters": True,
                                        "navigate_on_click": True,
                                        "navigate_url": "/system/verticals?vertical_id={id}",
                                        "filterConfig": {"searchFields": ["name"]},
                                        "actions": [
                                            edit_action("/system/verticals/{id}", vertical_schema_b64),
                                            delete_action("/system/verticals/{id}"),
                                        ],
                                        "header_actions": [
                                            create_modal_action(
                                                action_url="/system/verticals",
                                                schema_b64=vertical_schema_b64,
                                                modal_title="Crear Vertical",
                                                label="Nueva Vertical",
                                                icon="ri-add-line",
                                            )
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                },
                {
                    "type": "col",
                    "class_": "col-xl-8 col-lg-12",
                    "components": [
                        {
                            "type": "card",
                            "title": "2) Modelos del Vertical",
                            "components": (
                                [
                                    {
                                        "type": "typography",
                                        "tag": "p",
                                        "text": f"Vertical activo: {selected_vertical.name} ({selected_vertical.slug})",
                                        "class": "mb-2 text-muted",
                                    },
                                    {
                                        "type": "grid-visual",
                                        "label": "Modelos de Scoring",
                                        "properties": {
                                            "data_url": f"/system/verticals/models/data?vertical_id={selected_vertical.id}",
                                            "columns": [
                                                {"id": "name", "label": "Modelo", "sortable": True},
                                                {"id": "version", "label": "Versión", "sortable": True},
                                                {"id": "prompt_version", "label": "Prompt Ver.", "sortable": True},
                                                {"id": "is_active", "label": "Activo", "type": "badge", "badge_map": {"true": "success", "false": "secondary"}},
                                                {"id": "normalization_strategy", "label": "Estrategia", "sortable": True},
                                            ],
                                            "enableFilters": True,
                                            "navigate_on_click": True,
                                            "navigate_url": f"/system/verticals?vertical_id={selected_vertical.id}&model_id={{id}}",
                                            "filterConfig": {"searchFields": ["name", "normalization_strategy"]},
                                            "actions": [
                                                edit_action("/system/verticals/models/{id}", model_schema_b64),
                                                delete_action("/system/verticals/models/{id}"),
                                                {
                                                    "label": "Prompts",
                                                    "icon": "ri-message-3-line",
                                                    "action": "modal-grid-crud",
                                                    "modal_title": "Prompts de {context_model_name}",
                                                    "config_b64": prompt_modal_config_b64,
                                                },
                                            ],
                                            "header_actions": [
                                                create_modal_action(
                                                    action_url="/system/verticals/models",
                                                    schema_b64=model_create_schema_b64,
                                                    modal_title=f"Crear Modelo para {selected_vertical.name}",
                                                    label="Nuevo Modelo",
                                                    icon="ri-add-line",
                                                )
                                            ],
                                        },
                                    },
                                ]
                                if selected_vertical
                                else [
                                    {
                                        "type": "empty-state",
                                        "properties": {
                                            "title": "Selecciona un vertical",
                                            "message": "Primero elige un vertical en la columna izquierda para habilitar modelos y su CRUD contextual.",
                                            "icon": "ri-arrow-left-circle-line",
                                        },
                                    }
                                ]
                            ),
                        }
                    ],
                },
            ],
        }
    )

    detail_components: List[Dict[str, Any]]
    if selected_model and selected_vertical:
        detail_components = [
            {
                "type": "typography",
                "tag": "h4",
                "text": f"3) Criterios del Modelo: {selected_model.name} v{selected_model.version}",
                "class": "mt-4 mb-2",
            },
            {
                "type": "typography",
                "tag": "p",
                "text": "Acciones por criterio: Editar y Eliminar. Todas se ejecutan desde modal.",
                "class": "mb-3 text-muted",
            },
            {
                "type": "grid-visual",
                "label": "Criterios de Scoring",
                "properties": {
                    "data_url": f"/system/verticals/criteria/data?model_id={selected_model.id}",
                    "columns": [
                        {"id": "criterion_key", "label": "Key", "sortable": True},
                        {"id": "label", "label": "Label", "sortable": True},
                        {"id": "weight", "label": "Weight", "sortable": True},
                        {"id": "display_order", "label": "Order", "sortable": True},
                        {"id": "is_active", "label": "Activo", "type": "badge", "badge_map": {"true": "success", "false": "secondary"}},
                    ],
                    "enableFilters": True,
                    "filterConfig": {"searchFields": ["criterion_key", "label"]},
                    "actions": [
                        edit_action("/system/verticals/criteria/{id}", criterion_schema_b64),
                        delete_action("/system/verticals/criteria/{id}"),
                    ],
                    "header_actions": [
                        create_modal_action(
                            action_url="/system/verticals/criteria",
                            schema_b64=criterion_create_schema_b64,
                            modal_title=f"Crear Criterio para {selected_model.name}",
                            label="Nuevo Criterio",
                            icon="ri-add-line",
                        )
                    ],
                },
            },
        ]
    else:
        detail_components = [
            {
                "type": "typography",
                "tag": "h4",
                "text": "3) Configuración de Modelo",
                "class": "mt-4 mb-2",
            },
            {
                "type": "card",
                "components": [
                    {
                        "type": "empty-state",
                        "properties": {
                            "title": "Selecciona un modelo",
                            "message": "Primero abre un vertical y luego selecciona un modelo para habilitar el CRUD de criterios.",
                            "icon": "ri-cpu-line",
                        },
                    }
                ],
            },
        ]

    components.extend(detail_components)

    return {
        "layout": "dashboard-standard",
        "components": components,
        "permissions_required": ["system.view"],
    }


@router.get("/lookups/verticals")
async def list_vertical_options(user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.list_vertical_options()


@router.get("/lookups/models")
async def list_model_options(user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.list_model_options()


@router.get("/lookups/criteria")
async def list_criterion_options(user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.list_criterion_options()


@router.get("/data", response_model=List[VerticalRow])
async def list_verticals_data(user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.list_verticals()


@router.get("/{item_id:int}", response_model=VerticalRow)
async def get_vertical(item_id: int, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.get_vertical(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vertical not found")
    return item


@router.post("", response_model=VerticalRow)
async def create_vertical(payload: VerticalCreate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.create_vertical(payload)


@router.put("/{item_id:int}", response_model=VerticalRow)
async def update_vertical(item_id: int, payload: VerticalUpdate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.update_vertical(item_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Vertical not found")
    return item


@router.delete("/{item_id:int}")
async def delete_vertical(item_id: int, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    ok = await service.delete_vertical(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Vertical not found")
    return {"status": "deleted"}


@router.get("/models/data", response_model=List[ScoringModelRow])
async def list_models_data(
    vertical_id: Optional[int] = Query(None),
    user: User = Depends(RoleChecker(["system-user", "admin"])),
):
    return await service.list_scoring_models(vertical_id)


@router.get("/models/{item_id}", response_model=ScoringModelRow)
async def get_model(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.get_scoring_model(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring model not found")
    return item


@router.post("/models", response_model=ScoringModelRow)
async def create_model(payload: ScoringModelCreate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.create_scoring_model(payload)


@router.put("/models/{item_id}", response_model=ScoringModelRow)
async def update_model(item_id: UUID, payload: ScoringModelUpdate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.update_scoring_model(item_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring model not found")
    return item


@router.delete("/models/{item_id}")
async def delete_model(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    ok = await service.delete_scoring_model(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scoring model not found")
    return {"status": "deleted"}


@router.get("/criteria/data", response_model=List[ScoringCriterionRow])
async def list_criteria_data(
    model_id: Optional[UUID] = Query(None),
    user: User = Depends(RoleChecker(["system-user", "admin"])),
):
    return await service.list_scoring_criteria(model_id)


@router.get("/criteria/{item_id}", response_model=ScoringCriterionRow)
async def get_criterion(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.get_scoring_criterion(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring criterion not found")
    return item


@router.post("/criteria", response_model=ScoringCriterionRow)
async def create_criterion(payload: ScoringCriterionCreate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.create_scoring_criterion(payload)


@router.put("/criteria/{item_id}", response_model=ScoringCriterionRow)
async def update_criterion(item_id: UUID, payload: ScoringCriterionUpdate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.update_scoring_criterion(item_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring criterion not found")
    return item


@router.delete("/criteria/{item_id}")
async def delete_criterion(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    ok = await service.delete_scoring_criterion(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scoring criterion not found")
    return {"status": "deleted"}


@router.get("/bands/data", response_model=List[ScoringBandRow])
async def list_bands_data(
    criterion_id: Optional[UUID] = Query(None),
    user: User = Depends(RoleChecker(["system-user", "admin"])),
):
    return await service.list_scoring_bands(criterion_id)


@router.get("/bands/{item_id}", response_model=ScoringBandRow)
async def get_band(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.get_scoring_band(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring band not found")
    return item


@router.post("/bands", response_model=ScoringBandRow)
async def create_band(payload: ScoringBandCreate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.create_scoring_band(payload)


@router.put("/bands/{item_id}", response_model=ScoringBandRow)
async def update_band(item_id: UUID, payload: ScoringBandUpdate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.update_scoring_band(item_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring band not found")
    return item


@router.delete("/bands/{item_id}")
async def delete_band(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    ok = await service.delete_scoring_band(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scoring band not found")
    return {"status": "deleted"}


@router.get("/prompts/data", response_model=List[ScoringPromptRow])
async def list_prompts_data(
    model_id: Optional[UUID] = Query(None),
    user: User = Depends(RoleChecker(["system-user", "admin"])),
):
    return await service.list_scoring_prompts(model_id)


@router.get("/prompts/{item_id}", response_model=ScoringPromptRow)
async def get_prompt(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.get_scoring_prompt(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring prompt not found")
    return item


@router.post("/prompts", response_model=ScoringPromptRow)
async def create_prompt(payload: ScoringPromptCreate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    return await service.create_scoring_prompt(payload, created_by=user.id)


@router.put("/prompts/{item_id}", response_model=ScoringPromptRow)
async def update_prompt(item_id: UUID, payload: ScoringPromptUpdate, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    item = await service.update_scoring_prompt(item_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail="Scoring prompt not found")
    return item


@router.delete("/prompts/{item_id}")
async def delete_prompt(item_id: UUID, user: User = Depends(RoleChecker(["system-user", "admin"]))):
    ok = await service.delete_scoring_prompt(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scoring prompt not found")
    return {"status": "deleted"}
