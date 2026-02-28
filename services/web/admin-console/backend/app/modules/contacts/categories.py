from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.dal.database import engine
from pydantic import BaseModel
from app.modules.auth.config import current_active_user
from app.modules.auth.models import User

router = APIRouter()

class CategoryRead(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None


def _resolve_category_icon(name: str, icon: Optional[str]) -> str:
    raw_icon = str(icon or "").strip()
    if raw_icon.startswith("ri-"):
        return raw_icon

    normalized = str(name or "").strip().lower()
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


@router.get("/contacts/categories", response_model=List[CategoryRead])
async def list_categories(user: User = Depends(current_active_user)):
    query = text("SELECT id, name, icon FROM lead_channel_categories ORDER BY name")
    async with engine.connect() as conn:
        result = await conn.execute(query)
        return [
            CategoryRead(
                id=row.id,
                name=row.name,
                icon=_resolve_category_icon(row.name, row.icon),
            )
            for row in result
        ]
