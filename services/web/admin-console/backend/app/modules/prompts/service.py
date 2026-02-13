from sqlalchemy import text
from app.dal.database import engine
from .schemas import PromptCreate, PromptUpdate, PromptRow
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

class PromptService:
    """
    Data Access Layer for AI Prompts.
    Tenant-Scoped: All operations require client_id.
    """

    async def list_prompts(self, client_id: Optional[str] = None) -> List[PromptRow]:
        # Filter by client_id if provided (Tenant View), else ALL (Admin View)
        # Assuming lead_clients exists and has 'name', we JOIN to get it.
        
        where_clause = "WHERE p.deleted_at IS NULL"
        params = {}
        
        if client_id:
            where_clause += " AND p.client_id = :cid"
            params["cid"] = client_id
            
        query = text(f"""
            SELECT p.id, p.client_id, p.slug, p.prompt_text, p.is_active, p.updated_at, c.name as client_name
            FROM lead_ai_prompts p
            LEFT JOIN lead_clients c ON p.client_id = c.id
            {where_clause}
            ORDER BY c.name ASC, p.slug ASC
        """)
        
        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            return [
                PromptRow(
                    id=row.id, 
                    client_id=row.client_id,
                    slug=row.slug, 
                    prompt_text=row.prompt_text, 
                    is_active=row.is_active, 
                    updated_at=row.updated_at,
                    client_name=row.client_name
                ) for row in result
            ]

    async def get_prompt(self, client_id: Optional[str], prompt_id: UUID) -> Optional[PromptRow]:
        where_clause = "WHERE id = :id AND deleted_at IS NULL"
        params = {"id": prompt_id}
        if client_id:
            where_clause += " AND client_id = :cid"
            params["cid"] = client_id
            
        query = text(f"""
            SELECT id, client_id, slug, prompt_text, is_active, updated_at 
            FROM lead_ai_prompts 
            {where_clause}
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            row = result.fetchone()
            if row:
                return PromptRow(
                    id=row.id, 
                    client_id=row.client_id,
                    slug=row.slug, 
                    prompt_text=row.prompt_text, 
                    is_active=row.is_active, 
                    updated_at=row.updated_at
                )
            return None

    async def create_prompt(self, client_id: str, prompt: PromptCreate) -> PromptRow:
        query = text("""
            INSERT INTO lead_ai_prompts (client_id, slug, prompt_text, is_active, created_at, updated_at)
            VALUES (:cid, :slug, :text, :active, NOW(), NOW())
            RETURNING id, client_id, slug, prompt_text, is_active, updated_at
        """)
        params = {
            "cid": client_id,
            "slug": prompt.slug,
            "text": prompt.prompt_text,
            "active": prompt.is_active
        }
        
        async with engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                row = result.fetchone()
                await conn.commit()
                return PromptRow(
                    id=row.id, 
                    client_id=row.client_id,
                    slug=row.slug, 
                    prompt_text=row.prompt_text, 
                    is_active=row.is_active, 
                    updated_at=row.updated_at
                )
            except IntegrityError:
                await conn.rollback()
                raise HTTPException(status_code=409, detail="A prompt with this slug already exists.")
            except Exception as e:
                logger.exception("Prompt create failed", exc_info=e)
                raise HTTPException(status_code=500, detail="Prompt create failed")

    async def update_prompt(self, client_id: Optional[str], prompt_id: UUID, prompt: PromptUpdate) -> Optional[PromptRow]:
        updates = []
        params = {"id": prompt_id}

        if prompt.slug:
            updates.append("slug = :slug")
            params["slug"] = prompt.slug
        if prompt.prompt_text:
            updates.append("prompt_text = :text")
            params["text"] = prompt.prompt_text
        if prompt.is_active is not None:
            updates.append("is_active = :active")
            params["active"] = prompt.is_active
        if prompt.client_id:
            updates.append("client_id = :new_cid")
            params["new_cid"] = str(prompt.client_id)

        if not updates:
            return await self.get_prompt(client_id, prompt_id)

        updates.append("updated_at = NOW()")
        
        where_clause = "WHERE id = :id AND deleted_at IS NULL"
        if client_id:
            where_clause += " AND client_id = :cid"
            params["cid"] = client_id

        query_str = f"""
            UPDATE lead_ai_prompts
            SET {", ".join(updates)}
            {where_clause}
            RETURNING id, client_id, slug, prompt_text, is_active, updated_at
        """
        
        async with engine.connect() as conn:
            try:
                result = await conn.execute(text(query_str), params)
                row = result.fetchone()
                await conn.commit()
                if row:
                    return PromptRow(
                        id=row.id, 
                        client_id=row.client_id,
                        slug=row.slug, 
                        prompt_text=row.prompt_text, 
                        is_active=row.is_active, 
                        updated_at=row.updated_at
                    )
                return None
            except IntegrityError:
                await conn.rollback()
                raise HTTPException(status_code=409, detail="A prompt with this slug already exists.")
            except Exception as e:
                logger.exception("Prompt update failed", exc_info=e)
                raise HTTPException(status_code=500, detail="Prompt update failed")

    async def delete_prompt(self, client_id: Optional[str], prompt_id: UUID) -> bool:
        # Soft Delete
        where_clause = "WHERE id = :id"
        params = {"id": prompt_id}
        if client_id:
            where_clause += " AND client_id = :cid"
            params["cid"] = client_id

        query = text(f"""
            UPDATE lead_ai_prompts 
            SET deleted_at = NOW() 
            {where_clause}
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            await conn.commit()
            return result.rowcount > 0

service = PromptService()
