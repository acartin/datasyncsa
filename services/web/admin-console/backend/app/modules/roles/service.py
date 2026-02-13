from sqlalchemy import text
from typing import List, Optional
from uuid import UUID
from app.dal.database import engine
from .schemas import RoleRow, RoleCreate, RoleUpdate

class RolesService:
    async def list_roles(self) -> List[RoleRow]:
        query = text("SELECT id, name, slug FROM auth_roles ORDER BY name ASC")
        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.all()
            return [RoleRow(id=row.id, name=row.name, slug=row.slug) for row in rows]

    async def get_role(self, role_id: UUID) -> Optional[RoleRow]:
        query = text("SELECT id, name, slug FROM auth_roles WHERE id = :id")
        async with engine.connect() as conn:
            result = await conn.execute(query, {"id": role_id})
            row = result.fetchone()
            if row:
                return RoleRow(id=row.id, name=row.name, slug=row.slug)
            return None

    async def create_role(self, data: RoleCreate) -> RoleRow:
        query = text("""
            INSERT INTO auth_roles (id, name, slug)
            VALUES (:id, :name, :slug)
            RETURNING id, name, slug
        """)
        import uuid
        payload = data.model_dump()
        payload["id"] = uuid.uuid4()

        async with engine.begin() as conn:
            result = await conn.execute(query, payload)
            row = result.fetchone()
            return RoleRow(id=row.id, name=row.name, slug=row.slug)

    async def update_role(self, role_id: UUID, data: RoleUpdate) -> Optional[RoleRow]:
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_role(role_id)

        set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
        query = text(f"""
            UPDATE auth_roles
            SET {set_clause}
            WHERE id = :rol_id
            RETURNING id, name, slug
        """)
        params = {**update_data, "rol_id": role_id}
        
        async with engine.begin() as conn:
            result = await conn.execute(query, params)
            row = result.fetchone()
            if row:
                return RoleRow(id=row.id, name=row.name, slug=row.slug)
            return None

    async def delete_role(self, role_id: UUID) -> bool:
        query = text("DELETE FROM auth_roles WHERE id = :id")
        async with engine.begin() as conn:
            await conn.execute(query, {"id": role_id})
            return True

service = RolesService()
