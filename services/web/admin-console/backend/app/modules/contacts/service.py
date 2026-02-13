from typing import List, Optional
from uuid import UUID
import uuid
from sqlalchemy import text
from app.dal.database import engine
from fastapi import HTTPException

from .schemas import ContactCreate, ContactUpdate, ContactRead, ChannelRead

class ContactService:
    async def get_contacts_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> List[ContactRead]:
        query = text("""
            SELECT c.id, c.client_id, c.first_name, c.last_name, c.position, c.is_active, c.created_at, c.updated_at
            FROM lead_contacts c
            WHERE c.client_id = :client_id AND c.deleted_at IS NULL
            ORDER BY c.created_at DESC
            OFFSET :skip LIMIT :limit
        """)
        
        async with engine.connect() as conn:
            result = await conn.execute(query, {"client_id": client_id, "skip": skip, "limit": limit})
            contacts = []
            rows = result.all()
            
            # Optimization: Fetch channels in bulk or lazy?
            # For list view, we usually need basic info.
            # If we need channels (icons), we might need a join or secondary fetch.
            # Let's do a simple loop for now (N+1 but limited by pagination) or just return contacts.
            # The schema Create/Read has channels.
            # Let's fetch channels for these contacts suitable for UI.
            
            contact_ids = [row.id for row in rows]
            channels_map = {}
            if contact_ids:
                # Fetch channels
                ch_query = text("""
                    SELECT cc.id, cc.contact_id, cc.category_id, cc.type, cc.value, cc.label, cc.is_primary, lcc.name as cat_name, lcc.icon as cat_icon
                    FROM lead_contact_channels cc
                    LEFT JOIN lead_channel_categories lcc ON cc.category_id = lcc.id
                    WHERE cc.contact_id = ANY(:ids) AND cc.deleted_at IS NULL
                """)
                ch_res = await conn.execute(ch_query, {"ids": contact_ids})
                for ch in ch_res:
                    if ch.contact_id not in channels_map:
                        channels_map[ch.contact_id] = []
                    channels_map[ch.contact_id].append(ChannelRead(
                        id=ch.id,
                        contact_id=ch.contact_id,
                        category_id=ch.category_id,
                        type=ch.type,
                        value=ch.value,
                        label=ch.label,
                        is_primary=ch.is_primary or False,
                        category_name=ch.cat_name,
                        category_icon=ch.cat_icon
                    ))
            
            for row in rows:
                contacts.append(ContactRead(
                    id=row.id,
                    client_id=row.client_id,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    position=row.position,
                    is_active=row.is_active or False,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    channels=channels_map.get(row.id, [])
                ))
            
            return contacts

    async def get_contact_by_id(self, contact_id: UUID, client_id: Optional[UUID] = None) -> Optional[ContactRead]:
        query_str = """
            SELECT c.id, c.client_id, c.first_name, c.last_name, c.position, c.is_active, c.created_at, c.updated_at
            FROM lead_contacts c
            WHERE c.id = :id AND c.deleted_at IS NULL
        """
        if client_id:
            query_str += " AND c.client_id = :client_id"
        
        query = text(query_str)
        
        async with engine.connect() as conn:
            result = await conn.execute(query, {"id": contact_id, "client_id": client_id})
            row = result.fetchone()
            if not row:
                return None
            
            # Fetch channels
            ch_query = text("""
                SELECT cc.id, cc.contact_id, cc.category_id, cc.type, cc.value, cc.label, cc.is_primary, lcc.name as cat_name, lcc.icon as cat_icon
                FROM lead_contact_channels cc
                LEFT JOIN lead_channel_categories lcc ON cc.category_id = lcc.id
                WHERE cc.contact_id = :id AND cc.deleted_at IS NULL
            """)
            ch_res = await conn.execute(ch_query, {"id": contact_id})
            channels = [
                ChannelRead(
                    id=ch.id,
                    contact_id=ch.contact_id,
                    category_id=ch.category_id,
                    type=ch.type,
                    value=ch.value,
                    label=ch.label,
                    is_primary=ch.is_primary or False,
                    category_name=ch.cat_name,
                    category_icon=ch.cat_icon
                ) for ch in ch_res
            ]
            
            return ContactRead(
                id=row.id,
                client_id=row.client_id,
                first_name=row.first_name,
                last_name=row.last_name,
                position=row.position,
                is_active=row.is_active or False,
                created_at=row.created_at,
                updated_at=row.updated_at,
                channels=channels
            )

    async def create_contact(self, data: ContactCreate, current_user_client_id: Optional[UUID], is_superuser: bool = False) -> ContactRead:
        target_client_id = data.client_id
        if not is_superuser:
            target_client_id = current_user_client_id
        
        if not target_client_id:
            raise HTTPException(status_code=400, detail="Client ID is required")

        new_id = uuid.uuid4()
        
        query = text("""
            INSERT INTO lead_contacts (id, client_id, first_name, last_name, position, is_active)
            VALUES (:id, :client_id, :first_name, :last_name, :position, :is_active)
            RETURNING id, client_id, first_name, last_name, position, is_active, created_at, updated_at
        """)
        
        async with engine.begin() as conn:
            res = await conn.execute(query, {
                "id": new_id,
                "client_id": target_client_id,
                "first_name": data.first_name,
                "last_name": data.last_name,
                "position": data.position,
                "is_active": data.is_active
            })
            row = res.fetchone()
            
            # Channels
            if data.channels:
                 for ch in data.channels:
                     ch_query = text("""
                        INSERT INTO lead_contact_channels (contact_id, category_id, type, value, label, is_primary)
                        VALUES (:cid, :cat_id, :type, :val, :lbl, :is_p)
                     """)
                     await conn.execute(ch_query, {
                         "cid": new_id,
                         "cat_id": ch.category_id,
                         "type": ch.type,
                         "val": ch.value,
                         "lbl": ch.label,
                         "is_p": ch.is_primary
                     })
            
            # Re-fetch with channels to be compliant with Read Schema
            # Or just return empty channels if optimization needed
            # Let's do manual construction to save DB trip if possible, but reading is safer.
        
        # We need to call get_contact_by_id to fetch channels populated
        return await self.get_contact_by_id(new_id, target_client_id)

    async def update_contact(self, contact_id: UUID, data: ContactUpdate, current_user_client_id: Optional[UUID], is_superuser: bool) -> ContactRead:
        # Verify existence and permission
        existing = await self.get_contact_by_id(contact_id, None if is_superuser else current_user_client_id)
        if not existing:
             raise HTTPException(status_code=404, detail="Contact not found")
        
        updates = []
        params = {"id": contact_id}
        
        if data.first_name is not None:
             updates.append("first_name = :first_name")
             params["first_name"] = data.first_name
        if data.last_name is not None:
             updates.append("last_name = :last_name")
             params["last_name"] = data.last_name
        if data.position is not None:
             updates.append("position = :position")
             params["position"] = data.position
        if data.is_active is not None:
             updates.append("is_active = :is_active")
             params["is_active"] = data.is_active
        
        if updates:
            updates.append("updated_at = NOW()")
            query = text(f"""
                UPDATE lead_contacts
                SET {", ".join(updates)}
                WHERE id = :id
            """)
            async with engine.begin() as conn:
                await conn.execute(query, params)
        
        # Channel Sync (Simple version: Delete + Re-insert)
        if data.channels is not None:
            async with engine.begin() as conn:
                # Delete existing
                await conn.execute(
                    text("DELETE FROM lead_contact_channels WHERE contact_id = :id"),
                    {"id": contact_id}
                )
                # Re-insert
                for ch in data.channels:
                    await conn.execute(
                        text("""
                            INSERT INTO lead_contact_channels (contact_id, category_id, type, value, label, is_primary)
                            VALUES (:cid, :cat_id, :type, :val, :lbl, :is_p)
                        """),
                        {
                            "cid": contact_id,
                            "cat_id": ch.category_id,
                            "type": ch.type,
                            "val": ch.value,
                            "lbl": ch.label,
                            "is_p": ch.is_primary
                        }
                    )
        
        return await self.get_contact_by_id(contact_id, None if is_superuser else current_user_client_id)

    async def delete_contact(self, contact_id: UUID, current_user_client_id: Optional[UUID], is_superuser: bool) -> bool:
        # Verify existence and permission
        existing = await self.get_contact_by_id(contact_id, None if is_superuser else current_user_client_id)
        if not existing:
             raise HTTPException(status_code=404, detail="Contact not found")

        async with engine.begin() as conn:
            # Soft delete contact
            await conn.execute(
                text("UPDATE lead_contacts SET deleted_at = NOW() WHERE id = :id"),
                {"id": contact_id}
            )
            # Soft delete channels
            await conn.execute(
                text("UPDATE lead_contact_channels SET deleted_at = NOW() WHERE contact_id = :id"),
                {"id": contact_id}
            )
        return True

service = ContactService()
