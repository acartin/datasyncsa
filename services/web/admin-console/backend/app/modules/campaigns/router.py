from fastapi import APIRouter, Depends
from app.contracts.ui_schema import WebIAFirstResponse
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User

router = APIRouter()

@router.get("/", response_model=WebIAFirstResponse)
@router.get("", response_model=WebIAFirstResponse)
async def get_campaigns_view(user: User = Depends(current_active_user)):
    """
    Placeholder Campaigns View to avoid 404.
    """
    return {
        "layout": "dashboard-standard",
        "components": [
            {
                "type": "typography",
                "tag": "h2",
                "text": "Campañas de Marketing",
                "class": "mb-4"
            },
            {
                "type": "card",
                "size": "col-12",
                "components": [
                    {
                        "type": "typography",
                        "tag": "p",
                        "text": "Módulo de Campañas bajo construcción (Próximamente)."
                    }
                ]
            }
        ],
        "permissions_required": ["campaigns.view"]
    }
