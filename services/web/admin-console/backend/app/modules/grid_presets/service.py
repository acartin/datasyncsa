import json
from uuid import UUID
from sqlalchemy import text
from app.dal.database import engine
from .schemas import GridPresetCreate, GridPresetUpdate

class GridPresetsService:
    @staticmethod
    async def create_preset(user_id: UUID, client_id: UUID, preset: GridPresetCreate):
        query = text("""
            INSERT INTO lead_grid_presets (user_id, client_id, grid_id, name, icon, config, is_default)
            VALUES (:user_id, :client_id, :grid_id, :name, :icon, :config, :is_default)
            RETURNING id, user_id, client_id, grid_id, name, icon, config, is_default, created_at, updated_at
        """)
        
        # If this is set as default, we might want to unset other defaults for this user/grid
        if preset.is_default:
            async with engine.begin() as conn:
                await conn.execute(text("""
                    UPDATE lead_grid_presets 
                    SET is_default = false 
                    WHERE user_id = :user_id AND grid_id = :grid_id AND client_id = :client_id
                """), {"user_id": user_id, "grid_id": preset.grid_id, "client_id": client_id})
                
                result = await conn.execute(query, {
                    "user_id": user_id,
                    "client_id": client_id,
                    "grid_id": preset.grid_id,
                    "name": preset.name,
                    "icon": preset.icon,
                    "config": json.dumps(preset.config),
                    "is_default": preset.is_default
                })
                return result.mappings().first()
        else:
            async with engine.begin() as conn:
                result = await conn.execute(query, {
                    "user_id": user_id,
                    "client_id": client_id,
                    "grid_id": preset.grid_id,
                    "name": preset.name,
                    "icon": preset.icon,
                    "config": json.dumps(preset.config),
                    "is_default": preset.is_default
                })
                return result.mappings().first()

    @staticmethod
    async def get_user_presets(user_id: UUID, client_id: UUID, grid_id: str):
        query = text("""
            SELECT id, user_id, client_id, grid_id, name, icon, config, is_default, created_at, updated_at
            FROM lead_grid_presets
            WHERE user_id = :user_id 
            AND client_id = :client_id
            AND grid_id = :grid_id
            AND deleted_at IS NULL
            ORDER BY is_default DESC, created_at DESC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {
                "user_id": user_id,
                "client_id": client_id,
                "grid_id": grid_id
            })
            return result.mappings().all()

    @staticmethod
    async def delete_preset(user_id: UUID, client_id: UUID, preset_id: UUID):
        # Soft delete
        query = text("""
            UPDATE lead_grid_presets 
            SET deleted_at = NOW()
            WHERE id = :id AND user_id = :user_id AND client_id = :client_id
            RETURNING id
        """)
        async with engine.begin() as conn:
            result = await conn.execute(query, {
                "id": preset_id,
                "user_id": user_id,
                "client_id": client_id
            })
            return result.mappings().first()

    @staticmethod
    async def set_default_preset(user_id: UUID, client_id: UUID, grid_id: str, preset_id: UUID):
        async with engine.begin() as conn:
            # Unset all defaults for this user/grid
            await conn.execute(text("""
                UPDATE lead_grid_presets 
                SET is_default = false 
                WHERE user_id = :user_id AND grid_id = :grid_id AND client_id = :client_id
            """), {"user_id": user_id, "grid_id": grid_id, "client_id": client_id})
            
            # Set new default
            query = text("""
                UPDATE lead_grid_presets 
                SET is_default = true 
                WHERE id = :id AND user_id = :user_id AND client_id = :client_id
                RETURNING id
            """)
            result = await conn.execute(query, {
                "id": preset_id,
                "user_id": user_id,
                "client_id": client_id
            })
            return result.mappings().first()
