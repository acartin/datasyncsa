from fastapi import APIRouter, HTTPException, Depends
from app.contracts.ui_schema import WebIAFirstResponse
from .schemas import CountryCreate, CountryUpdate, CountryRow
from .service import service
from typing import List
from app.modules.auth.dependencies import RoleChecker

# Lock down the entire module to Admin and System User
router = APIRouter(dependencies=[Depends(RoleChecker(["admin", "system-user"]))])

# --- SERVER DRIVEN UI (SDUI) ---

@router.get("/countries", response_model=WebIAFirstResponse)
async def get_countries_view():
    """
    Returns the UI structure for the Countries Module.
    Defines the Grid Layout and allowed Actions.
    """
    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "grid-visual",
                "label": "Countries Management (Global)",
                "properties": {
                    "data_url": "/countries/data", # Frontend fetches data from here
                    "primary_key": "id",
                    "columns": [
                        {"id": "id", "label": "ID", "type": "text", "sortable": True},
                        {"id": "name", "label": "Country Name", "type": "text", "sortable": True},
                        {"id": "iso_code", "label": "ISO Code", "type": "badge", "color": "info"},
                        {"id": "updated_at", "label": "Last Update", "type": "datetime"}
                    ],
                    "form_schema": [
                        {"name": "name", "label": "Country Name", "type": "text", "required": True, "min_length": 3},
                        {"name": "iso_code", "label": "ISO Code", "type": "text", "required": True, "min_length": 2, "max_length": 2}
                    ],
                    "enableFilters": True,
                    "filterConfig": {
                        "searchFields": ["name", "iso_code"],
                        "filterableColumns": []
                    },
                    "actions": [
                        {
                            "type": "button",
                            "icon": "ri-edit-line",
                            "label": "Editar",
                            "action": "modal-form",
                            "action_url": "/countries/{id}", # Should return GET for pre-fill, PUT for submit
                            "modal_title": "Editar País"
                        },
                        {
                            "type": "button",
                            "icon": "ri-delete-bin-line",
                            "label": "Eliminar",
                            "color": "danger",
                            "action": "api-call",
                            "method": "DELETE",
                            "action_url": "/countries/{id}",
                            "confirm_message": "¿Estás seguro de eliminar este país permanentemente?"
                        }
                    ],
                    "header_actions": [
                        {
                            "type": "button",
                            "icon": "ri-add-line",
                            "label": "Nuevo País",
                            "color": "success",
                            "action": "modal-form",
                            "action_url": "/countries", # Modified to match standard REST POST
                            "modal_title": "Nuevo País"
                        }
                    ]
                }
            }
        ],
        "permissions_required": ["countries.view"]
    }

# --- DATA API (CRUD) ---

@router.get("/countries/data", response_model=List[CountryRow])
async def list_countries_data():
    """Returns raw data for the Grid."""
    return await service.list_countries()

@router.post("/countries", response_model=CountryRow)
async def create_country(country: CountryCreate):
    return await service.create_country(country)

@router.get("/countries/{country_id}", response_model=CountryRow)
async def get_country(country_id: int):
    """Used for populating Edit Modals"""
    item = await service.get_country(country_id)
    if not item:
        raise HTTPException(status_code=404, detail="Country not found")
    return item

@router.put("/countries/{country_id}", response_model=CountryRow)
async def update_country(country_id: int, country: CountryUpdate):
    item = await service.update_country(country_id, country)
    if not item:
        raise HTTPException(status_code=404, detail="Country not found")
    return item

@router.delete("/countries/{country_id}")
async def delete_country(country_id: int):
    success = await service.delete_country(country_id)
    if not success:
        raise HTTPException(status_code=404, detail="Country not found")
    return {"status": "deleted"}
