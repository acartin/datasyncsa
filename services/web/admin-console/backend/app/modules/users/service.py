from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import List, Optional
from uuid import UUID
import uuid
from app.modules.users.schemas import UserRow, UserCreate, UserUpdate
from app.dal.database import engine
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from fastapi_users.password import PasswordHelper

password_helper = PasswordHelper()

class UsersService:
    async def list_users(self) -> List[UserRow]:
        query = text("""
            SELECT 
                u.id, u.email, u.name, u.is_active, u.is_superuser, u.contact_id,
                r.name as role_name, r.slug as role_slug, r.id as role_id,
                lc.name as client_name, lc.id as client_id
            FROM auth_users u
            LEFT JOIN auth_client_user acu ON u.id = acu.user_id
            LEFT JOIN auth_roles r ON acu.role_id = r.id
            LEFT JOIN lead_clients lc ON acu.client_id = lc.id
            ORDER BY u.email ASC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.all()
            return [UserRow.model_validate(row) for row in rows]

    async def get_user(self, user_id: UUID) -> Optional[UserRow]:
        query = text("""
            SELECT 
                u.id, u.email, u.name, u.is_active, u.is_superuser, u.contact_id,
                r.name as role_name, r.slug as role_slug, r.id as role_id,
                lc.name as client_name, lc.id as client_id
            FROM auth_users u
            LEFT JOIN auth_client_user acu ON u.id = acu.user_id
            LEFT JOIN auth_roles r ON acu.role_id = r.id
            LEFT JOIN lead_clients lc ON acu.client_id = lc.id
            WHERE u.id = :id
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"id": user_id})
            row = result.fetchone()
            return UserRow.model_validate(row) if row else None

    async def create_user(self, user: UserCreate) -> UserRow:
        hashed_password = password_helper.hash(user.password)
        new_user_id = uuid.uuid4()
        
        async with engine.begin() as conn:
            try:
                # 1. Create User
                await conn.execute(text("""
                    INSERT INTO auth_users (id, email, hashed_password, is_active, is_superuser, is_verified, name, contact_id)
                    VALUES (:id, :email, :password, :active, :superuser, true, :name, :contact_id)
                """), {
                    "id": new_user_id,
                    "email": user.email,
                    "password": hashed_password,
                    "active": user.is_active,
                    "superuser": user.is_superuser,
                    "name": user.name,
                    "contact_id": user.contact_id
                })

                # 2. Link to Client and Role if provided
                if user.client_id and user.role_id:
                    await conn.execute(text("""
                        INSERT INTO auth_client_user (id, user_id, client_id, role_id)
                        VALUES (:id, :user_id, :client_id, :role_id)
                    """), {
                        "id": uuid.uuid4(),
                        "user_id": new_user_id,
                        "client_id": user.client_id,
                        "role_id": user.role_id
                    })
                
                await conn.commit()
            except IntegrityError:
                await conn.rollback()
                
                # Person-Centric Logic: If the user already exists but is associated with the SAME contact, 
                # we can reactivate/update instead of failing.
                async with engine.begin() as conn_retry:
                    existing = await conn_retry.execute(text("SELECT id, contact_id, is_active FROM auth_users WHERE email = :email"), {"email": user.email})
                    row = existing.fetchone()
                    if row and row.contact_id == user.contact_id:
                        # 1. Reactivate and Update password/name
                        await conn_retry.execute(text("""
                            UPDATE auth_users 
                            SET hashed_password = :password, is_active = true, name = :name
                            WHERE id = :id
                        """), {
                            "id": row.id,
                            "password": hashed_password,
                            "name": user.name
                        })

                        # 2. Ensure Client Link exists (or update it)
                        if user.client_id and user.role_id:
                            # Check if link already exists
                            link_check = await conn_retry.execute(text("""
                                SELECT id FROM auth_client_user 
                                WHERE user_id = :uid AND client_id = :cid
                            """), {"uid": row.id, "cid": user.client_id})
                            
                            if not link_check.fetchone():
                                await conn_retry.execute(text("""
                                    INSERT INTO auth_client_user (id, user_id, client_id, role_id)
                                    VALUES (:id, :user_id, :client_id, :role_id)
                                """), {
                                    "id": uuid.uuid4(),
                                    "user_id": row.id,
                                    "client_id": user.client_id,
                                    "role_id": user.role_id
                                })
                            else:
                                await conn_retry.execute(text("""
                                    UPDATE auth_client_user SET role_id = :rid
                                    WHERE user_id = :uid AND client_id = :cid
                                """), {"uid": row.id, "cid": user.client_id, "rid": user.role_id})
                        
                        await conn_retry.commit()
                        return await self.get_user(row.id)
                
                raise HTTPException(status_code=400, detail="User with this email already exists.")
            except Exception as e:
                await conn.rollback()
                raise e

        return await self.get_user(new_user_id)

    async def update_user(self, user_id: UUID, user_update: UserUpdate) -> UserRow:
        updates = []
        params = {"id": user_id}

        if user_update.email is not None:
            updates.append("email = :email")
            params["email"] = user_update.email
        if user_update.name is not None:
            updates.append("name = :name")
            params["name"] = user_update.name
        if user_update.password is not None:
            updates.append("hashed_password = :password")
            params["password"] = password_helper.hash(user_update.password)
        if user_update.is_active is not None:
            updates.append("is_active = :active")
            params["active"] = user_update.is_active
        if user_update.is_superuser is not None:
            updates.append("is_superuser = :superuser")
            params["superuser"] = user_update.is_superuser

        async with engine.begin() as conn:
            if updates:
                await conn.execute(text(f"""
                    UPDATE auth_users SET {", ".join(updates)} WHERE id = :id
                """), params)

            # Update Client/Role link
            if user_update.client_id is not None or user_update.role_id is not None:
                # Check if exists
                res = await conn.execute(text("SELECT id FROM auth_client_user WHERE user_id = :id"), {"id": user_id})
                link_id = res.fetchone()
                
                if link_id:
                    link_updates = []
                    link_params = {"user_id": user_id}
                    if user_update.client_id:
                        link_updates.append("client_id = :cid")
                        link_params["cid"] = user_update.client_id
                    if user_update.role_id:
                        link_updates.append("role_id = :rid")
                        link_params["rid"] = user_update.role_id
                    
                    await conn.execute(text(f"UPDATE auth_client_user SET {', '.join(link_updates)} WHERE user_id = :user_id"), link_params)
                else:
                    if user_update.client_id and user_update.role_id:
                        await conn.execute(text("""
                            INSERT INTO auth_client_user (id, user_id, client_id, role_id)
                            VALUES (:id, :user_id, :client_id, :role_id)
                        """), {
                            "id": uuid.uuid4(),
                            "user_id": user_id,
                            "client_id": user_update.client_id,
                            "role_id": user_update.role_id
                        })
            await conn.commit()

        return await self.get_user(user_id)

    async def delete_user(self, user_id: UUID):
        async with engine.begin() as conn:
            # 1. First cleanup links to avoid constraint violations
            await conn.execute(text("DELETE FROM auth_client_user WHERE user_id = :id"), {"id": user_id})
            
            # 2. Hard delete the user to allow clean re-conversions in Person-Centric model
            await conn.execute(text("DELETE FROM auth_users WHERE id = :id"), {"id": user_id})
            await conn.commit()

    async def list_roles(self):
        query = text("SELECT id, name, slug FROM auth_roles ORDER BY name ASC")
        async with engine.connect() as conn:
            result = await conn.execute(query)
            return [{"id": row.id, "name": row.name, "slug": row.slug} for row in result.all()]

service = UsersService()
