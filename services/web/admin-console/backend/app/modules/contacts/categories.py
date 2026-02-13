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

@router.get("/contacts/categories", response_model=List[CategoryRead])
async def list_categories(user: User = Depends(current_active_user)):
    query = text("SELECT id, name, icon FROM lead_channel_categories ORDER BY name")
    async with engine.connect() as conn:
        result = await conn.execute(query)
        return [CategoryRead(id=row.id, name=row.name, icon=row.icon) for row in result]
