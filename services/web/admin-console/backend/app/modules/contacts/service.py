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

    async def list_channels_by_contact(
        self,
        contact_id: UUID,
        client_id: Optional[UUID] = None,
    ) -> List[dict]:
        query_str = """
            SELECT
                cc.id,
                cc.contact_id,
                cc.category_id,
                lcc.name AS category_name,
                lcc.icon AS category_icon,
                cc.type,
                cc.value,
                cc.label,
                COALESCE(cc.is_primary, false) AS is_primary,
                COALESCE(cc.is_verified, false) AS is_verified,
                cc.updated_at
            FROM lead_contact_channels cc
            JOIN lead_contacts c ON c.id = cc.contact_id
            LEFT JOIN lead_channel_categories lcc ON lcc.id = cc.category_id
            WHERE cc.contact_id = :contact_id
              AND cc.deleted_at IS NULL
              AND c.deleted_at IS NULL
        """
        params = {"contact_id": contact_id}
        if client_id:
            query_str += " AND c.client_id = :client_id"
            params["client_id"] = client_id
        query_str += " ORDER BY cc.is_primary DESC, cc.created_at ASC"

        async with engine.connect() as conn:
            result = await conn.execute(text(query_str), params)
            return [dict(row._mapping) for row in result]

    async def get_channel_by_id(
        self,
        contact_id: UUID,
        channel_id: UUID,
        client_id: Optional[UUID] = None,
    ) -> Optional[dict]:
        query_str = """
            SELECT
                cc.id,
                cc.contact_id,
                cc.category_id,
                lcc.name AS category_name,
                lcc.icon AS category_icon,
                cc.type,
                cc.value,
                cc.label,
                COALESCE(cc.is_primary, false) AS is_primary,
                COALESCE(cc.is_verified, false) AS is_verified,
                cc.updated_at
            FROM lead_contact_channels cc
            JOIN lead_contacts c ON c.id = cc.contact_id
            LEFT JOIN lead_channel_categories lcc ON lcc.id = cc.category_id
            WHERE cc.id = :channel_id
              AND cc.contact_id = :contact_id
              AND cc.deleted_at IS NULL
              AND c.deleted_at IS NULL
        """
        params = {"channel_id": channel_id, "contact_id": contact_id}
        if client_id:
            query_str += " AND c.client_id = :client_id"
            params["client_id"] = client_id

        async with engine.connect() as conn:
            result = await conn.execute(text(query_str), params)
            row = result.mappings().first()
            return dict(row) if row else None

    async def create_channel(
        self,
        contact_id: UUID,
        payload: dict,
        current_user_client_id: Optional[UUID],
        is_superuser: bool,
    ) -> dict:
        existing_contact = await self.get_contact_by_id(
            contact_id,
            None if is_superuser else current_user_client_id,
        )
        if not existing_contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        query = text(
            """
            INSERT INTO lead_contact_channels (
                contact_id, category_id, type, value, label, is_primary, is_verified
            )
            VALUES (
                :contact_id, :category_id, :type, :value, :label, :is_primary, :is_verified
            )
            RETURNING id
            """
        )
        params = {
            "contact_id": contact_id,
            "category_id": payload.get("category_id"),
            "type": payload.get("type") or "other",
            "value": payload.get("value"),
            "label": payload.get("label"),
            "is_primary": bool(payload.get("is_primary", False)),
            "is_verified": bool(payload.get("is_verified", False)),
        }
        async with engine.begin() as conn:
            row = (await conn.execute(query, params)).mappings().first()
            channel_id = row["id"]

        created = await self.get_channel_by_id(
            contact_id=contact_id,
            channel_id=channel_id,
            client_id=None if is_superuser else current_user_client_id,
        )
        if not created:
            raise HTTPException(status_code=500, detail="Unable to read created channel")
        return created

    async def update_channel(
        self,
        contact_id: UUID,
        channel_id: UUID,
        payload: dict,
        current_user_client_id: Optional[UUID],
        is_superuser: bool,
    ) -> dict:
        existing = await self.get_channel_by_id(
            contact_id=contact_id,
            channel_id=channel_id,
            client_id=None if is_superuser else current_user_client_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Channel not found")

        updates = []
        params = {"channel_id": channel_id, "contact_id": contact_id}
        allowed_fields = (
            "category_id",
            "type",
            "value",
            "label",
            "is_primary",
            "is_verified",
        )
        for key in allowed_fields:
            if key in payload and payload[key] is not None:
                updates.append(f"{key} = :{key}")
                params[key] = payload[key]

        if updates:
            updates.append("updated_at = NOW()")
            query = text(
                f"""
                UPDATE lead_contact_channels
                SET {", ".join(updates)}
                WHERE id = :channel_id
                  AND contact_id = :contact_id
                  AND deleted_at IS NULL
                """
            )
            async with engine.begin() as conn:
                await conn.execute(query, params)

        updated = await self.get_channel_by_id(
            contact_id=contact_id,
            channel_id=channel_id,
            client_id=None if is_superuser else current_user_client_id,
        )
        if not updated:
            raise HTTPException(status_code=500, detail="Unable to read updated channel")
        return updated

    async def delete_channel(
        self,
        contact_id: UUID,
        channel_id: UUID,
        current_user_client_id: Optional[UUID],
        is_superuser: bool,
    ) -> bool:
        existing = await self.get_channel_by_id(
            contact_id=contact_id,
            channel_id=channel_id,
            client_id=None if is_superuser else current_user_client_id,
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Channel not found")

        query = text(
            """
            UPDATE lead_contact_channels
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE id = :channel_id
              AND contact_id = :contact_id
              AND deleted_at IS NULL
            """
        )
        async with engine.begin() as conn:
            await conn.execute(query, {"channel_id": channel_id, "contact_id": contact_id})
        return True

    async def list_channel_type_options(self) -> List[dict]:
        defaults = [
            {"id": "phone", "name": "Teléfono"},
            {"id": "mobile", "name": "Celular"},
            {"id": "whatsapp", "name": "WhatsApp"},
            {"id": "email", "name": "Email"},
            {"id": "telegram", "name": "Telegram"},
            {"id": "instagram", "name": "Instagram"},
            {"id": "facebook", "name": "Facebook"},
            {"id": "other", "name": "Otro"},
        ]
        existing_map = {item["id"]: item["name"] for item in defaults}

        query = text(
            """
            SELECT DISTINCT lower(trim(type)) AS type_key
            FROM lead_contact_channels
            WHERE deleted_at IS NULL
              AND type IS NOT NULL
              AND trim(type) <> ''
            ORDER BY 1
            """
        )
        async with engine.connect() as conn:
            result = await conn.execute(query)
            for row in result:
                type_key = str(row.type_key or "").strip().lower()
                if not type_key:
                    continue
                if type_key not in existing_map:
                    existing_map[type_key] = type_key.replace("_", " ").title()

        return [{"id": k, "name": v} for k, v in existing_map.items()]

    async def list_channels_feed(
        self,
        client_id: UUID,
        skip: int = 0,
        limit: int = 200,
    ) -> List[dict]:
        query = text(
            """
            SELECT
                cc.id,
                cc.contact_id,
                trim(
                    concat(
                        coalesce(c.first_name, ''),
                        ' ',
                        coalesce(c.last_name, '')
                    )
                ) AS contact_name,
                cc.category_id,
                lcc.name AS category_name,
                lcc.icon AS category_icon,
                cc.type,
                cc.value,
                cc.label,
                COALESCE(cc.is_primary, false) AS is_primary,
                COALESCE(cc.is_verified, false) AS is_verified,
                cc.updated_at
            FROM lead_contact_channels cc
            JOIN lead_contacts c ON c.id = cc.contact_id
            LEFT JOIN lead_channel_categories lcc ON lcc.id = cc.category_id
            WHERE c.client_id = :client_id
              AND c.deleted_at IS NULL
              AND cc.deleted_at IS NULL
            ORDER BY cc.is_primary DESC, cc.updated_at DESC NULLS LAST, cc.created_at DESC
            OFFSET :skip LIMIT :limit
            """
        )
        async with engine.connect() as conn:
            result = await conn.execute(
                query,
                {"client_id": client_id, "skip": skip, "limit": limit},
            )
            return [dict(row._mapping) for row in result]

service = ContactService()
