from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import List, Optional
import httpx
import uuid
from app.contracts.ui_schema import WebIAFirstResponse
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User

import os
import logging

# Use internal docker alias or external env var
ETL_SERVICE_URL = os.getenv("ETL_SERVICE_URL", "http://etl-processor:8000")
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=WebIAFirstResponse)
@router.get("", response_model=WebIAFirstResponse)
async def get_ai_library_view(user: User = Depends(current_active_user)):
    """
    Biblioteca de IA: Gestión de conocimiento y base documental.
    """
    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "typography",
                "tag": "h2",
                "text": "Biblioteca de IA",
                "class": "mb-4"
            },
            {
                "type": "tabs",
                "items": [
                    {
                        "id": "tab-pdfs",
                        "label": "Pdfs",
                        "icon": "ri-file-pdf-line",
                        "active": True,
                        "content": [
                            {
                                "type": "grid-visual",
                                "label": "Listado de Pdfs",
                                "properties": {
                                    "id": "grid_pdfs",
                                    "data_url": "/ai-library/pdfs/data",
                                    "enableFilters": True,
                                    "filterConfig": {
                                        "searchPlaceholder": "Buscar PDF...",
                                        "searchFields": ["filename"]
                                    },
                                    "columns": [
                                        {"id": "filename", "label": "Nombre del Archivo", "sortable": True},
                                        {"id": "category", "label": "Categoría", "sortable": True},
                                        {
                                            "id": "access_level", 
                                            "label": "Acceso", 
                                            "type": "badge",
                                            "uppercase": True,
                                            "badge_map": {
                                                "private": "danger",
                                                "shared": "warning",
                                                "public": "success"
                                            }
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
                                                "FAILED": "danger"
                                            }
                                        },
                                        {"id": "created_at", "label": "Fecha de Carga", "sortable": True}
                                    ],
                                    "actions": [
                                        {
                                            "type": "button",
                                            "icon": "ri-delete-bin-line",
                                            "label": "Eliminar",
                                            "color": "danger",
                                            "action": "delete",
                                            "action_url": "/ai-library/pdfs/{content_id}",
                                            "confirm_message": "¿Estás seguro de que deseas eliminar este conocimiento?"
                                        }
                                    ],
                                    "header_actions": [
                                        {
                                            "type": "button",
                                            "label": "Nuevo PDF",
                                            "icon": "ri-add-line",
                                            "color": "success",
                                            "action": "modal-form",
                                            "action_url": "/ai-library/pdfs/upload",
                                            "modal_title": "Subir Nuevo PDF",
                                            "schema": [
                                                {"name": "file", "label": "Archivo PDF", "type": "file", "required": True, "accept": ".pdf"},
                                                {"name": "category", "label": "Categoría", "type": "text", "required": False, "placeholder": "Ej: Ventas, RRHH"},
                                                {
                                                    "name": "access_level", 
                                                    "label": "Nivel de Acceso", 
                                                    "type": "select", 
                                                    "required": True,
                                                    "options": [
                                                        {"label": "Privado (Solo yo)", "value": "private"},
                                                        {"label": "Compartido (Empresa)", "value": "shared"},
                                                        {"label": "Público (Global)", "value": "public"}
                                                    ],
                                                    "value": "shared"
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {
                        "id": "tab-urls",
                        "label": "Sitios Web",
                        "icon": "ri-global-line",
                        "content": [
                            {
                                "type": "grid-visual",
                                "label": "Fuentes Web (URLs)",
                                "properties": {
                                    "id": "grid_urls",
                                    "data_url": "/ai-library/urls/data",
                                    "enableFilters": True,
                                    "filterConfig": {
                                        "searchPlaceholder": "Buscar URL...",
                                        "searchFields": ["url"]
                                    },
                                    "columns": [
                                        {"id": "url", "label": "URL", "sortable": True},
                                        {
                                            "id": "status", 
                                            "label": "Estado", 
                                            "type": "badge", 
                                            "sortable": True,
                                            "badge_map": {
                                                "Pendiente": "warning",
                                                "Rastreando": "info",
                                                "Indexado": "success",
                                                "Error": "danger"
                                            }
                                        },
                                        {"id": "last_sync", "label": "Última Sincro", "sortable": True}
                                    ],
                                    "header_actions": [
                                        {
                                            "type": "button",
                                            "label": "Nueva URL",
                                            "icon": "ri-add-line",
                                            "color": "success",
                                            "action": "modal-form",
                                            "action_url": "/ai-library/urls/add",
                                            "modal_title": "Agregar Nueva URL",
                                            "schema": [
                                                {"name": "url", "label": "URL del Sitio", "type": "text", "required": True, "placeholder": "https://tusitio.com/documentacion"},
                                                {"name": "category", "label": "Categoría", "type": "text", "required": False, "placeholder": "Ej: Blog, Knowledge Base"},
                                                {"name": "max_depth", "label": "Profundidad de Rastreo", "type": "select", "options": [
                                                    {"label": "Solo esta página", "value": "0"},
                                                    {"label": "Nivel 1 (Subpáginas)", "value": "1"},
                                                    {"label": "Nivel 2 (Profundo)", "value": "2"}
                                                ], "value": "1"}
                                            ]
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {
                        "id": "tab-status",
                        "label": "Monitor",
                        "icon": "ri-cpu-line",
                        "content": [
                            {
                                "type": "row",
                                "class": "row",
                                "components": [
                                    {
                                        "type": "col", "class": "col-md-4",
                                        "components": [
                                            {
                                                "type": "card-metric",
                                                "properties": {
                                                    "title": "Vectores Indexados", "value": "0", "icon": "ri-node-tree", "color": "info"
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        "type": "col", "class": "col-md-4",
                                        "components": [
                                            {
                                                "type": "card-metric",
                                                "properties": {
                                                    "title": "Salud del Índice", "value": "Óptimo", "icon": "ri-shield-check-line", "color": "success"
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        "type": "col", "class": "col-md-4",
                                        "components": [
                                            {
                                                "type": "card-metric",
                                                "properties": {
                                                    "title": "Última Sincro", "value": "Nunca", "icon": "ri-time-line", "color": "warning"
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ],
        "permissions_required": ["ai_library.view"]
    }

@router.get("/pdfs/data", response_model=List[dict])
async def get_pdfs_data(user: User = Depends(current_active_user)):
    """
    Retorna los documentos del cliente actual consultando el servicio ETL.
    """
    if not user.tenants:
        return []
    
    client_id = str(user.tenants[0].client_id)
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{ETL_SERVICE_URL}/documents/list/{client_id}")
            if r.status_code == 200:
                data = r.json()
                # El servicio devuelve {status, client_id, count, documents: []}
                docs = data.get("documents", [])
                # Mapping simple para asegurar que el grid vea 'status'
                for d in docs:
                    d['status'] = d.get('sync_status')
                return docs
            return []
        except Exception as e:
            logger.exception("ETL list request failed", exc_info=e)
            return []

@router.post("/pdfs/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    access_level: str = Form("shared"),
    user: User = Depends(current_active_user)
):
    """
    Proxy para subir el PDF al servicio ETL con soporte de AccessLevel.
    """
    if not user.tenants:
        raise HTTPException(status_code=403, detail="No client context.")

    client_id = str(user.tenants[0].client_id)
    content_id = f"doc_{uuid.uuid4()}"


    async with httpx.AsyncClient() as client:
        try:
            # Preparamos el archivo para el reenvío
            files = {'file': (file.filename, await file.read(), file.content_type)}
            
            # Ajustamos la data siguiendo el esquema de metadata de canonical_document.json y AccessLevel
            data = {
                'client_id': client_id,
                'content_id': content_id,
                'category': category or "General",
                'access_level': access_level,
                'source': "PDF_UPLOAD",
                'title': file.filename
            }
            
            r = await client.post(f"{ETL_SERVICE_URL}/documents/upload", files=files, data=data)
            
            if r.status_code == 409:
                raise HTTPException(status_code=409, detail=f"El archivo '{file.filename}' ya existe. Por favor renombrelo o elimine el anterior.")
            
            r.raise_for_status()
            return r.json()
        except HTTPException as he:
            raise he
        except httpx.HTTPStatusError as e:
            logger.warning("ETL upload upstream error", extra={"status_code": e.response.status_code})
            raise HTTPException(status_code=e.response.status_code, detail="ETL service upload failed")
        except Exception as e:
            logger.exception("ETL upload connection failed", exc_info=e)
            raise HTTPException(status_code=500, detail="Connection to ETL failed")

@router.get("/pdfs/jobs/{job_id}")
async def get_job_status(job_id: str, user: User = Depends(current_active_user)):
    """
    Consulta el estado de una tarea de procesamiento.
    """
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{ETL_SERVICE_URL}/documents/jobs/{job_id}")
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="ETL service job lookup failed")
        except Exception as e:
            logger.exception("ETL job lookup failed", exc_info=e)
            raise HTTPException(status_code=500, detail="Connection to ETL failed")

@router.delete("/pdfs/{content_id}")
async def delete_pdf(content_id: str, user: User = Depends(current_active_user)):
    """
    Elimina un documento específico.
    """
    if not user.tenants:
        raise HTTPException(status_code=403, detail="No client context.")

    client_id = str(user.tenants[0].client_id)
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.delete(f"{ETL_SERVICE_URL}/documents/{client_id}/{content_id}")
            r.raise_for_status()
            return {"status": "success", "message": "Documento eliminado."}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="ETL service delete failed")
        except Exception as e:
            logger.exception("ETL delete failed", exc_info=e)
            raise HTTPException(status_code=500, detail="Connection to ETL failed")

@router.get("/urls/data", response_model=List[dict])
async def get_urls_data(user: User = Depends(current_active_user)):
    """Retorna lista vacía de URLs por ahora."""
    return []
