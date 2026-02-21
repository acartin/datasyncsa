from sqlalchemy import text
from fastapi import HTTPException
from app.dal.database import engine
from .schemas import ClientRow, ClientCreate, ClientUpdate, ClientSimple, ClientStats, DocumentRow
from typing import List, Optional
from uuid import UUID
import uuid

class ClientService:
    async def _validate_scoring_model_scope(self, vertical_id: Optional[int], scoring_model_id: Optional[UUID]) -> None:
        if scoring_model_id is None:
            return
        if vertical_id is None:
            raise HTTPException(status_code=422, detail="vertical_id is required when scoring_model_id is set")

        query = text("""
            SELECT id
            FROM lead_scoring_models
            WHERE id = :model_id
              AND vertical_id = :vertical_id
              AND is_active = true
            LIMIT 1
        """)
        async with engine.connect() as conn:
            row = (await conn.execute(query, {"model_id": scoring_model_id, "vertical_id": vertical_id})).fetchone()
            if not row:
                raise HTTPException(
                    status_code=422,
                    detail="scoring_model_id must reference an active model in the same client vertical",
                )

    async def list_simple(self) -> List[ClientSimple]:
        query = text("SELECT id, name FROM lead_clients ORDER BY name")
        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.all()
            return [ClientSimple(id=row.id, name=row.name) for row in rows]

    async def list_vertical_options(self) -> List[dict]:
        query = text("""
            SELECT id, name
            FROM lead_client_verticals
            ORDER BY name ASC
        """)
        async with engine.connect() as conn:
            rows = (await conn.execute(query)).all()
            return [{"id": row.id, "name": row.name} for row in rows]

    async def list_clients(self) -> List[ClientRow]:
        query = text("""
            SELECT
                c.id,
                c.name,
                c.country_id,
                c.vertical_id,
                c.scoring_model_id,
                lc.name as country_name,
                v.name as vertical_name,
                CASE
                    WHEN m.id IS NULL THEN NULL
                    ELSE (m.name || ' v' || m.version::text)
                END AS scoring_model_name
            FROM lead_clients c
            LEFT JOIN lead_countries lc ON c.country_id = lc.id
            LEFT JOIN lead_client_verticals v ON c.vertical_id = v.id
            LEFT JOIN lead_scoring_models m ON c.scoring_model_id = m.id
            ORDER BY c.name
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.all()
            return [
                ClientRow(
                    id=row.id,
                    name=row.name,
                    country_id=row.country_id or 0,
                    vertical_id=row.vertical_id or 0,
                    scoring_model_id=row.scoring_model_id,
                    country_name=row.country_name,
                    vertical_name=row.vertical_name,
                    scoring_model_name=row.scoring_model_name,
                )
                for row in rows
            ]

    async def get_client(self, client_id: UUID) -> Optional[ClientRow]:
        query = text("""
            SELECT
                c.id,
                c.name,
                c.country_id,
                c.vertical_id,
                c.scoring_model_id,
                c.created_at,
                lc.name as country_name,
                v.name as vertical_name,
                CASE
                    WHEN m.id IS NULL THEN NULL
                    ELSE (m.name || ' v' || m.version::text)
                END AS scoring_model_name
            FROM lead_clients c
            LEFT JOIN lead_countries lc ON c.country_id = lc.id
            LEFT JOIN lead_client_verticals v ON c.vertical_id = v.id
            LEFT JOIN lead_scoring_models m ON c.scoring_model_id = m.id
            WHERE c.id = :id
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"id": client_id})
            row = result.fetchone()
            if row:
                return ClientRow(
                    id=row.id, 
                    name=row.name, 
                    country_id=row.country_id or 0, 
                    vertical_id=row.vertical_id or 0,
                    scoring_model_id=row.scoring_model_id,
                    country_name=row.country_name,
                    vertical_name=row.vertical_name,
                    scoring_model_name=row.scoring_model_name,
                    created_at=row.created_at
                )
            return None

    async def create_client(self, client: ClientCreate) -> ClientRow:
        await self._validate_scoring_model_scope(client.vertical_id, client.scoring_model_id)
        query = text("""
            INSERT INTO lead_clients (id, name, country_id, vertical_id, scoring_model_id)
            VALUES (:id, :name, :country_id, :vertical_id, :scoring_model_id)
            RETURNING id, name, country_id, vertical_id, scoring_model_id
        """)
        new_id = uuid.uuid4()
        async with engine.begin() as conn:
            result = await conn.execute(
                query,
                {
                    "id": new_id,
                    "name": client.name,
                    "country_id": client.country_id,
                    "vertical_id": client.vertical_id,
                    "scoring_model_id": client.scoring_model_id,
                },
            )
            row = result.fetchone()
            return ClientRow(
                id=row.id,
                name=row.name,
                country_id=row.country_id,
                vertical_id=row.vertical_id,
                scoring_model_id=row.scoring_model_id,
            )

    async def update_client(self, client_id: UUID, client: ClientUpdate) -> Optional[ClientRow]:
        updates = []
        params = {"id": client_id}
        
        if client.name:
            updates.append("name = :name")
            params["name"] = client.name
        
        if client.country_id is not None:
             updates.append("country_id = :country_id")
             params["country_id"] = client.country_id
        if client.vertical_id is not None:
            updates.append("vertical_id = :vertical_id")
            params["vertical_id"] = client.vertical_id
        if client.scoring_model_id is not None:
            updates.append("scoring_model_id = :scoring_model_id")
            params["scoring_model_id"] = client.scoring_model_id

        if not updates:
            return await self.get_client(client_id)

        vertical_query = text("SELECT vertical_id, scoring_model_id FROM lead_clients WHERE id = :id")
        async with engine.connect() as conn:
            existing = (await conn.execute(vertical_query, {"id": client_id})).fetchone()
        if not existing:
            return None

        effective_vertical = client.vertical_id if client.vertical_id is not None else existing.vertical_id
        effective_model = client.scoring_model_id if client.scoring_model_id is not None else existing.scoring_model_id
        await self._validate_scoring_model_scope(effective_vertical, effective_model)
            
        query = text(f"""
            UPDATE lead_clients
            SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id, name, country_id, vertical_id, scoring_model_id
        """)
        
        async with engine.begin() as conn:
            result = await conn.execute(query, params)
            row = result.fetchone()
            if row:
                return ClientRow(
                    id=row.id,
                    name=row.name,
                    country_id=row.country_id,
                    vertical_id=row.vertical_id,
                    scoring_model_id=row.scoring_model_id,
                )
            return None

    async def list_scoring_model_options(self, vertical_id: Optional[int]) -> List[dict]:
        if not vertical_id:
            return []

        query = text("""
            SELECT id, (name || ' v' || version::text) AS name
            FROM lead_scoring_models
            WHERE vertical_id = :vertical_id
              AND is_active = true
            ORDER BY version DESC, name ASC
        """)
        async with engine.connect() as conn:
            rows = (await conn.execute(query, {"vertical_id": vertical_id})).all()
            return [{"id": str(row.id), "name": row.name} for row in rows]

    async def delete_client(self, client_id: UUID) -> bool:
        query = text("DELETE FROM lead_clients WHERE id = :id")
        async with engine.begin() as conn:
            await conn.execute(query, {"id": client_id})
            return True

    async def get_client_stats(self, client_id: UUID) -> ClientStats:
        query_leads = text("SELECT COUNT(*) FROM lead_leads WHERE client_id = :id")
        query_props = text("SELECT COUNT(*) FROM lead_properties WHERE client_id = :id")
        
        async with engine.connect() as conn:
            leads = await conn.execute(query_leads, {"id": client_id})
            props = await conn.execute(query_props, {"id": client_id})
            
            return ClientStats(
                total_leads=leads.scalar() or 0,
                total_properties=props.scalar() or 0
            )

    async def get_client_documents(self, client_id: UUID) -> List[DocumentRow]:
        query = text("""
            SELECT id, filename, created_at, sync_status
            FROM lead_knowledge_documents
            WHERE client_id = :id
            ORDER BY created_at DESC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"id": client_id})
            rows = result.fetchall()
            return [DocumentRow(
                id=r.id, 
                filename=r.filename, 
                created_at=r.created_at, 
                sync_status=r.sync_status
            ) for r in rows]

service = ClientService()
