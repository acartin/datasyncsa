from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from app.contracts.ui_schema import WebIAFirstResponse
from app.modules.auth.models import User as AuthUser
from app.modules.auth.dependencies import RoleChecker
from app.modules.shared.sdui import (
    create_modal_action,
    delete_action,
    edit_action,
    encode_schema_b64,
)
from app.modules.users.service import service as users_service
from app.modules.users.schemas import UserCreate
from . import service, schemas, categories

router = APIRouter()
router.include_router(categories.router)


CLIENT_USER_ROLE_ID = UUID("94fb2738-073f-480a-868a-6271e3b362cf")
CONTACTS_ALLOWED_ROLES = ["client-admin", "admin", "system-user", "superadmin"]


def _resolve_target_client_id(current_user: AuthUser, client_id: Optional[UUID] = None) -> Optional[UUID]:
    if current_user.is_superuser:
        return client_id

    if not current_user.tenants:
        return None

    tenant_client_id = current_user.tenants[0].client_id
    if client_id and client_id != tenant_client_id:
        raise HTTPException(status_code=403, detail="Client scope mismatch")
    return tenant_client_id


def _contact_form_schema(include_client_id: bool = False) -> List[dict]:
    fields: List[dict] = [
        {"name": "first_name", "label": "Nombre", "type": "text", "required": True},
        {"name": "last_name", "label": "Apellido", "type": "text", "required": False},
        {"name": "position", "label": "Cargo / Puesto", "type": "text", "required": False},
        {"name": "is_active", "label": "Activo", "type": "switch", "required": False},
        {
            "name": "channels",
            "label": "Canales de Comunicación",
            "type": "repeater",
            "source": "/contacts/categories",
        },
    ]
    if include_client_id:
        fields.append(
            {
                "name": "client_id",
                "label": "Cliente",
                "type": "select",
                "source": "/clients/simple-list",
                "required": True,
            }
        )
    return fields


def _channel_form_schema() -> List[dict]:
    return [
        {
            "name": "category_id",
            "label": "Categoría",
            "type": "select",
            "source": "/contacts/categories",
            "required": True,
        },
        {
            "name": "type",
            "label": "Tipo de Canal",
            "type": "select",
            "source": "/contacts/channel-types",
            "required": True,
        },
        {
            "name": "value",
            "label": "Valor",
            "type": "text",
            "required": True,
            "placeholder": "Ej: contacto@dominio.com",
            "placeholder_source": "type",
            "placeholder_map": {
                "email": "Ej: contacto@dominio.com",
                "phone": "Ej: 2222-3344",
                "mobile": "Ej: +506 8888-9999",
                "whatsapp": "Ej: +506 8888-9999",
                "telegram": "Ej: @usuario",
                "instagram": "Ej: @cuenta",
                "facebook": "Ej: facebook.com/pagina",
                "other": "Ingresa el dato de contacto",
            },
        },
        {"name": "label", "label": "Etiqueta", "type": "text", "required": False},
        {"name": "is_primary", "label": "Principal", "type": "switch", "required": False},
        {"name": "is_verified", "label": "Verificado", "type": "switch", "required": False},
    ]


def _convert_form_schema() -> List[dict]:
    return [
        {"name": "email", "label": "Email de acceso", "type": "text", "required": True},
        {"name": "password", "label": "Contraseña inicial", "type": "password", "required": True},
    ]


def _extract_primary_channel(contact: schemas.ContactRead) -> str:
    channels = contact.channels or []
    if not channels:
        return "-"
    primary = next((c for c in channels if c.is_primary), channels[0])
    return str(primary.value or "-")


def _extract_primary_email(contact: schemas.ContactRead) -> Optional[str]:
    for channel in (contact.channels or []):
        value = (channel.value or "").strip()
        if not value:
            continue
        name = (channel.category_name or "").lower()
        ctype = (channel.type or "").lower()
        if "mail" in name or ctype == "email" or "@" in value:
            return value
    return None


def _resolve_category_icon(category_name: Optional[str], category_icon: Optional[str]) -> str:
    raw_icon = str(category_icon or "").strip()
    if raw_icon.startswith("ri-"):
        return raw_icon

    normalized = str(category_name or "").strip().lower()
    if "email" in normalized or "mail" in normalized:
        return "ri-mail-line"
    if "telefono" in normalized or "teléfono" in normalized or "phone" in normalized:
        return "ri-phone-line"
    if "whatsapp" in normalized:
        return "ri-whatsapp-line"
    if "telegram" in normalized:
        return "ri-telegram-line"
    if "linkedin" in normalized:
        return "ri-linkedin-line"
    if "chat" in normalized:
        return "ri-chat-1-line"
    if "web" in normalized:
        return "ri-global-line"
    if "social" in normalized or "redes" in normalized:
        return "ri-share-line"
    return "ri-links-line"


def _to_grid_rows(contacts: List[schemas.ContactRead]) -> List[schemas.ContactGridRow]:
    rows: List[schemas.ContactGridRow] = []
    for c in contacts:
        first = (c.first_name or "").strip()
        last = (c.last_name or "").strip()
        rows.append(
            schemas.ContactGridRow(
                id=c.id,
                first_name=first,
                last_name=last or None,
                name=(f"{first} {last}" if last else first).strip(),
                full_name=(f"{first} {last}" if last else first).strip(),
                position=c.position,
                primary_channel=_extract_primary_channel(c),
                primary_email=_extract_primary_email(c),
                channels_count=len(c.channels or []),
                is_active="true" if bool(c.is_active) else "false",
            )
        )
    return rows


def _to_channel_rows(items: List[dict]) -> List[schemas.ContactChannelManageRow]:
    rows: List[schemas.ContactChannelManageRow] = []
    for item in items:
        rows.append(
            schemas.ContactChannelManageRow(
                id=item["id"],
                contact_id=item["contact_id"],
                category_id=item.get("category_id"),
                category_name=item.get("category_name"),
                category_icon=_resolve_category_icon(
                    item.get("category_name"),
                    item.get("category_icon"),
                ),
                type=item.get("type") or "other",
                value=item.get("value") or "",
                label=item.get("label"),
                is_primary="true" if bool(item.get("is_primary")) else "false",
                is_verified="true" if bool(item.get("is_verified")) else "false",
            )
        )
    return rows


def _to_channel_feed_rows(items: List[dict]) -> List[schemas.ContactChannelListRow]:
    rows: List[schemas.ContactChannelListRow] = []
    for item in items:
        rows.append(
            schemas.ContactChannelListRow(
                id=item["id"],
                contact_id=item["contact_id"],
                contact_name=str(item.get("contact_name") or "-").strip() or "-",
                category_icon=_resolve_category_icon(
                    item.get("category_name"),
                    item.get("category_icon"),
                ),
                category_name=item.get("category_name"),
                type=item.get("type") or "other",
                value=item.get("value") or "",
                label=item.get("label"),
                is_primary="true" if bool(item.get("is_primary")) else "false",
                is_verified="true" if bool(item.get("is_verified")) else "false",
            )
        )
    return rows


@router.get("/contacts", response_model=WebIAFirstResponse)
async def get_contacts_view(current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES))):
    include_client_id = bool(current_user.is_superuser)
    create_schema_b64 = encode_schema_b64(_contact_form_schema(include_client_id=include_client_id))
    edit_schema_b64 = encode_schema_b64(_contact_form_schema(include_client_id=False))
    convert_schema_b64 = encode_schema_b64(_convert_form_schema())
    channel_schema_b64 = encode_schema_b64(_channel_form_schema())
    channels_feed_properties = {
        "title": "Canales de Comunicación",
        "id": "contacts_channels_feed",
        "data_url": "/contacts/channels/data",
        "data_url_template": "/contacts/{master_id}/channels/data",
        "master_grid_id": "contacts_grid",
        "master_row_field": "id",
        "master_url_token": "{master_id}",
        "empty_until_master": True,
        "columns": [
            {"id": "category_icon", "label": "", "type": "icon", "icon_only": True},
            {"id": "category_name", "label": "Canal", "sortable": True},
            {"id": "value", "label": "Detalle", "sortable": True},
            {"id": "is_primary", "label": "Principal", "type": "badge", "badge_map": {"true": "success", "false": "secondary"}},
            {"id": "is_verified", "label": "Verificado", "type": "badge", "badge_map": {"true": "info", "false": "secondary"}},
        ],
        "enableFilters": False,
        "filterConfig": {
            "searchFields": ["category_name", "type", "value", "label"],
        },
        "actions": [
            edit_action("/contacts/{contact_id}/channels/{id}", channel_schema_b64),
            delete_action("/contacts/{contact_id}/channels/{id}"),
        ],
        "header_actions": [
            {
                "label": "Nuevo Canal",
                "icon": "ri-add-line",
                "action": "modal-form-create",
                "action_url": "/contacts/{master_id}/channels",
                "schema": channel_schema_b64,
                "modal_title": "Agregar canal",
                "color": "success",
                "requires_master": True,
                "show_disabled_when_locked": True,
                "locked_label": "Seleccione contacto",
            }
        ],
    }

    return {
        "layout": "dashboard-standard",
        "title": "Gestión de Contactos",
        "components": [
            {
                "type": "row",
                "class_": "g-4",
                "components": [
                    {
                        "type": "col",
                        "class_": "col-12 col-xl-7",
                        "components": [
                            {
                                "type": "grid-visual",
                                "label": "Directorio de Contactos",
                                "properties": {
                                    "title": "Directorio de Contactos",
                                    "id": "contacts_grid",
                                    "data_url": "/contacts/data",
                                    "auto_select_first_row": True,
                                    "columns": [
                                        {"id": "full_name", "label": "Nombre", "sortable": True},
                                        {"id": "position", "label": "Posición", "sortable": True},
                                        {
                                            "id": "is_active",
                                            "label": "Activo",
                                            "type": "badge",
                                            "badge_map": {"true": "success", "false": "secondary"},
                                        },
                                    ],
                                    "enableFilters": False,
                                    "filterConfig": {
                                        "searchFields": ["full_name", "position"],
                                        "filterableColumns": [
                                            {"id": "is_active", "label": "Activo", "icon": "ri-toggle-line"},
                                            {"id": "position", "label": "Posición", "icon": "ri-briefcase-4-line"},
                                        ],
                                    },
                                    "actions": [
                                        edit_action("/contacts/{id}", edit_schema_b64),
                                        {
                                            "label": "Convertir a Usuario",
                                            "icon": "ri-user-add-line",
                                            "action": "modal-form-create",
                                            "action_url": "/contacts/{id}/convert",
                                            "schema": convert_schema_b64,
                                            "modal_title": "Crear acceso para contacto",
                                            "prefill": {"email": "{primary_email}"},
                                            "color": "primary",
                                        },
                                        delete_action("/contacts/{id}"),
                                    ],
                                    "header_actions": [
                                        create_modal_action(
                                            action_url="/contacts",
                                            schema_b64=create_schema_b64,
                                            modal_title="Crear Contacto",
                                            label="Nuevo Contacto",
                                            icon="ri-user-add-line",
                                        )
                                    ],
                                },
                            }
                        ],
                    },
                    {
                        "type": "col",
                        "class_": "col-12 col-xl-5",
                        "components": [
                            {
                                "type": "grid-visual",
                                "label": "Todos los Canales",
                                "properties": channels_feed_properties,
                            }
                        ],
                    },
                ],
            }
        ],
        "permissions_required": ["contacts.view"],
    }


@router.get("/contacts/data", response_model=List[schemas.ContactGridRow])
async def read_contacts_data(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[UUID] = Query(None, description="Filter by Client ID (admin only)"),
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user, client_id)

    if not target_client_id and not current_user.is_superuser:
        return []

    if not target_client_id:
        return []

    contacts = await service.service.get_contacts_by_client(target_client_id, skip=skip, limit=limit)
    return _to_grid_rows(contacts)


@router.get("/contacts/channels/data", response_model=List[schemas.ContactChannelListRow])
async def read_channels_feed_data(
    skip: int = 0,
    limit: int = 200,
    client_id: Optional[UUID] = Query(None, description="Filter by Client ID (admin only)"),
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user, client_id)

    if not target_client_id and not current_user.is_superuser:
        return []

    if not target_client_id:
        return []

    channels = await service.service.list_channels_feed(target_client_id, skip=skip, limit=limit)
    return _to_channel_feed_rows(channels)


@router.get("/contacts/channel-types")
async def list_channel_types(current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES))):
    return await service.service.list_channel_type_options()


@router.get("/contacts/{contact_id}", response_model=schemas.ContactRead)
async def read_contact(
    contact_id: UUID,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user)
    contact = await service.service.get_contact_by_id(contact_id, target_client_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("/contacts/{contact_id}/channels/data", response_model=List[schemas.ContactChannelManageRow])
async def read_contact_channels_data(
    contact_id: UUID,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user)
    channels = await service.service.list_channels_by_contact(
        contact_id=contact_id,
        client_id=None if current_user.is_superuser else target_client_id,
    )
    return _to_channel_rows(channels)


@router.get("/contacts/{contact_id}/channels/{channel_id}", response_model=schemas.ContactChannelManageRow)
async def get_contact_channel(
    contact_id: UUID,
    channel_id: UUID,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user)
    channel = await service.service.get_channel_by_id(
        contact_id=contact_id,
        channel_id=channel_id,
        client_id=None if current_user.is_superuser else target_client_id,
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _to_channel_rows([channel])[0]


@router.post("/contacts", response_model=schemas.ContactRead)
async def create_contact(
    contact: schemas.ContactCreate,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user, contact.client_id)
    return await service.service.create_contact(
        data=contact,
        current_user_client_id=target_client_id,
        is_superuser=current_user.is_superuser,
    )


@router.post("/contacts/{contact_id}/channels", response_model=schemas.ContactChannelManageRow)
async def create_contact_channel(
    contact_id: UUID,
    payload: schemas.ContactChannelManageCreate,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user)
    created = await service.service.create_channel(
        contact_id=contact_id,
        payload=payload.model_dump(),
        current_user_client_id=target_client_id,
        is_superuser=current_user.is_superuser,
    )
    return _to_channel_rows([created])[0]


@router.put("/contacts/{contact_id}", response_model=schemas.ContactRead)
async def update_contact(
    contact_id: UUID,
    contact: schemas.ContactUpdate,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    current_client_id = _resolve_target_client_id(current_user)

    return await service.service.update_contact(
        contact_id=contact_id,
        data=contact,
        current_user_client_id=current_client_id,
        is_superuser=current_user.is_superuser,
    )


@router.put("/contacts/{contact_id}/channels/{channel_id}", response_model=schemas.ContactChannelManageRow)
async def update_contact_channel(
    contact_id: UUID,
    channel_id: UUID,
    payload: schemas.ContactChannelManageUpdate,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user)
    updated = await service.service.update_channel(
        contact_id=contact_id,
        channel_id=channel_id,
        payload={k: v for k, v in payload.model_dump().items() if v is not None},
        current_user_client_id=target_client_id,
        is_superuser=current_user.is_superuser,
    )
    return _to_channel_rows([updated])[0]


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: UUID,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    current_client_id = _resolve_target_client_id(current_user)

    await service.service.delete_contact(
        contact_id=contact_id,
        current_user_client_id=current_client_id,
        is_superuser=current_user.is_superuser,
    )
    return {"status": "success", "message": "Contact deleted"}


@router.delete("/contacts/{contact_id}/channels/{channel_id}")
async def delete_contact_channel(
    contact_id: UUID,
    channel_id: UUID,
    current_user: AuthUser = Depends(RoleChecker(CONTACTS_ALLOWED_ROLES)),
):
    target_client_id = _resolve_target_client_id(current_user)
    await service.service.delete_channel(
        contact_id=contact_id,
        channel_id=channel_id,
        current_user_client_id=target_client_id,
        is_superuser=current_user.is_superuser,
    )
    return {"status": "success", "message": "Channel deleted"}


@router.post("/contacts/{contact_id}/convert")
async def convert_contact_to_user(
    contact_id: UUID,
    data: schemas.ContactConvert,
    current_user: AuthUser = Depends(RoleChecker(["client-admin", "admin", "superadmin"])),
):
    client_id = _resolve_target_client_id(current_user)
    if not client_id:
        raise HTTPException(status_code=403, detail="User has no client context")

    contact = await service.service.get_contact_by_id(contact_id, client_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found or access denied")

    user_create = UserCreate(
        email=data.email,
        password=data.password,
        name=f"{contact.first_name} {contact.last_name or ''}".strip(),
        is_active=True,
        client_id=client_id,
        role_id=CLIENT_USER_ROLE_ID,
        contact_id=contact_id,
    )

    try:
        new_user = await users_service.create_user(user_create)
        return {"status": "success", "message": "User created and linked", "user_id": new_user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
