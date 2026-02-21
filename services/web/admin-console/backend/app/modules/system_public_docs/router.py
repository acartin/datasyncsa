import logging
import os
import uuid
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text

from app.contracts.ui_schema import WebIAFirstResponse
from app.dal.database import engine
from app.modules.ai_library.access_policy import SYSTEM_PUBLIC_CLIENT_ALIASES, resolve_datasyncsa_client_id
from app.modules.auth.dependencies import RoleChecker
from app.modules.auth.models import User

# External ETL endpoint is mandatory. No local fallback allowed.
ETL_SERVICE_URL = os.getenv("ETL_SERVICE_URL", "").strip().rstrip("/")
if not ETL_SERVICE_URL:
    raise RuntimeError("ETL_SERVICE_URL is required and must point to the external ETL service.")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system/public-docs", tags=["System Public Documents"])


async def _resolve_superadmin_datasyncsa_client_id() -> Optional[str]:
    # Fallback for superadmin sessions without tenant linkage.
    async with engine.connect() as conn:
        for alias in SYSTEM_PUBLIC_CLIENT_ALIASES:
            row = (
                await conn.execute(
                    text("SELECT id::text AS id FROM lead_clients WHERE lower(name) = :alias LIMIT 1"),
                    {"alias": alias},
                )
            ).fetchone()
            if row and row.id:
                return str(row.id)

        # Last-resort heuristic if aliases are not present verbatim.
        row = (
            await conn.execute(
                text("SELECT id::text AS id FROM lead_clients WHERE lower(name) LIKE :pattern LIMIT 1"),
                {"pattern": "%datasync%"},
            )
        ).fetchone()
        if row and row.id:
            return str(row.id)
    return None


async def _get_datasyncsa_client_id_or_403(user: User) -> str:
    client_id = resolve_datasyncsa_client_id(user)
    if not client_id and user.is_superuser:
        client_id = await _resolve_superadmin_datasyncsa_client_id()
    if not client_id:
        raise HTTPException(
            status_code=403,
            detail="Public documents require datasyncsa tenant context.",
        )
    return client_id


@router.get("", response_model=WebIAFirstResponse)
async def get_public_docs_view(user: User = Depends(RoleChecker(["admin", "system-user"]))):
    await _get_datasyncsa_client_id_or_403(user)
    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "typography",
                "tag": "h2",
                "text": "Documentos Públicos Globales",
                "class": "mb-4",
            },
            {
                "type": "grid-visual",
                "label": "Repositorio Público",
                "properties": {
                    "id": "grid_public_docs",
                    "data_url": "/system/public-docs/data",
                    "enableFilters": True,
                    "filterConfig": {
                        "searchPlaceholder": "Buscar documento...",
                        "searchFields": ["filename"],
                    },
                    "columns": [
                        {"id": "filename", "label": "Nombre del Archivo", "sortable": True},
                        {"id": "category", "label": "Categoría", "sortable": True},
                        {
                            "id": "access_level",
                            "label": "Acceso",
                            "type": "badge",
                            "uppercase": True,
                            "badge_map": {"public": "success"},
                        },
                        {
                            "id": "status",
                            "label": "Estado",
                            "type": "badge",
                            "sortable": True,
                            "badge_map": {
                                "QUEUED": "warning",
                                "STARTED": "info",
                                "SYNCED": "success",
                                "FAILED": "danger",
                            },
                        },
                        {"id": "created_at", "label": "Fecha de Carga", "sortable": True},
                    ],
                    "actions": [
                        {
                            "type": "button",
                            "icon": "ri-delete-bin-line",
                            "label": "Eliminar",
                            "color": "danger",
                            "action": "delete",
                            "action_url": "/system/public-docs/{content_id}",
                            "confirm_message": "¿Eliminar documento público global?",
                        }
                    ],
                    "header_actions": [
                        {
                            "type": "button",
                            "label": "Nuevo Documento Público",
                            "icon": "ri-add-line",
                            "color": "success",
                            "action": "modal-form",
                            "action_url": "/system/public-docs/upload",
                            "modal_title": "Subir Documento Público Global",
                            "schema": [
                                {
                                    "name": "file",
                                    "label": "Archivo PDF",
                                    "type": "file",
                                    "required": True,
                                    "accept": ".pdf",
                                },
                                {
                                    "name": "category",
                                    "label": "Categoría",
                                    "type": "text",
                                    "required": False,
                                    "placeholder": "Ej: Policies, Compliance",
                                },
                            ],
                        }
                    ],
                },
            },
        ],
    }


@router.get("/data", response_model=List[dict])
async def get_public_docs_data(user: User = Depends(RoleChecker(["admin", "system-user"]))):
    client_id = await _get_datasyncsa_client_id_or_403(user)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{ETL_SERVICE_URL}/documents/list/{client_id}")
            if r.status_code != 200:
                return []
            data = r.json()
            docs = data.get("documents", [])
            public_docs = [d for d in docs if (d.get("access_level") or "").lower() == "public"]
            for d in public_docs:
                d["status"] = d.get("sync_status")
            return public_docs
        except Exception as e:
            logger.exception("Public docs list request failed", exc_info=e)
            return []


@router.post("/upload")
async def upload_public_doc(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    user: User = Depends(RoleChecker(["admin", "system-user"])),
):
    client_id = await _get_datasyncsa_client_id_or_403(user)
    content_id = f"public_doc_{uuid.uuid4()}"

    async with httpx.AsyncClient() as client:
        try:
            files = {"file": (file.filename, await file.read(), file.content_type)}
            data = {
                "client_id": client_id,
                "content_id": content_id,
                "category": category or "General",
                "access_level": "public",
                "source": "PDF_UPLOAD",
                "title": file.filename,
            }
            r = await client.post(f"{ETL_SERVICE_URL}/documents/upload", files=files, data=data)
            if r.status_code == 409:
                raise HTTPException(
                    status_code=409,
                    detail=f"El archivo '{file.filename}' ya existe. Renómbrelo o elimine el anterior.",
                )
            r.raise_for_status()
            return r.json()
        except HTTPException as he:
            raise he
        except httpx.HTTPStatusError as e:
            logger.warning("Public docs upload upstream error", extra={"status_code": e.response.status_code})
            raise HTTPException(status_code=e.response.status_code, detail="ETL service upload failed")
        except Exception as e:
            logger.exception("Public docs upload connection failed", exc_info=e)
            raise HTTPException(status_code=500, detail="Connection to ETL failed")


@router.delete("/{content_id}")
async def delete_public_doc(content_id: str, user: User = Depends(RoleChecker(["admin", "system-user"]))):
    client_id = await _get_datasyncsa_client_id_or_403(user)
    async with httpx.AsyncClient() as client:
        try:
            r = await client.delete(f"{ETL_SERVICE_URL}/documents/{client_id}/{content_id}")
            r.raise_for_status()
            return {"status": "success", "message": "Documento público eliminado."}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="ETL service delete failed")
        except Exception as e:
            logger.exception("Public docs delete failed", exc_info=e)
            raise HTTPException(status_code=500, detail="Connection to ETL failed")
