from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DBAPIError

from app.dal.database import engine
from .admin_scoring_schemas import (
    VerticalRow,
    VerticalCreate,
    VerticalUpdate,
    ScoringModelRow,
    ScoringModelCreate,
    ScoringModelUpdate,
    ScoringCriterionRow,
    ScoringCriterionCreate,
    ScoringCriterionUpdate,
    ScoringBandRow,
    ScoringBandCreate,
    ScoringBandUpdate,
    ScoringPromptRow,
    ScoringPromptCreate,
    ScoringPromptUpdate,
)


class AdminScoringService:
    @staticmethod
    def _row_to_dict(row: Any) -> Dict[str, Any]:
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        if isinstance(row, dict):
            return row
        return dict(row)

    @classmethod
    def _validate_row(cls, schema: Any, row: Any):
        return schema.model_validate(cls._row_to_dict(row))

    async def list_verticals(self) -> List[VerticalRow]:
        query = text("""
            SELECT id, name, slug
            FROM lead_client_verticals
            ORDER BY name ASC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query)
            return [self._validate_row(VerticalRow, row) for row in result.all()]

    async def get_vertical(self, item_id: int) -> Optional[VerticalRow]:
        query = text("""
            SELECT id, name, slug
            FROM lead_client_verticals
            WHERE id = :id
        """)
        async with engine.connect() as conn:
            row = (await conn.execute(query, {"id": item_id})).fetchone()
            return self._validate_row(VerticalRow, row) if row else None

    async def create_vertical(self, payload: VerticalCreate) -> VerticalRow:
        query = text("""
            INSERT INTO lead_client_verticals (name, slug)
            VALUES (:name, :slug)
            RETURNING id, name, slug
        """)
        async with engine.begin() as conn:
            try:
                row = (await conn.execute(query, payload.model_dump())).fetchone()
                return self._validate_row(VerticalRow, row)
            except IntegrityError:
                raise HTTPException(status_code=409, detail="Vertical with same name or slug already exists")

    async def update_vertical(self, item_id: int, payload: VerticalUpdate) -> Optional[VerticalRow]:
        updates: List[str] = []
        params: Dict[str, Any] = {"id": item_id}
        data = payload.model_dump(exclude_unset=True)
        for key in ("name", "slug"):
            if key in data:
                updates.append(f"{key} = :{key}")
                params[key] = data[key]

        if not updates:
            return await self.get_vertical(item_id)

        query = text(f"""
            UPDATE lead_client_verticals
            SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id, name, slug
        """)
        async with engine.begin() as conn:
            try:
                row = (await conn.execute(query, params)).fetchone()
                return self._validate_row(VerticalRow, row) if row else None
            except IntegrityError:
                raise HTTPException(status_code=409, detail="Vertical with same name or slug already exists")

    async def delete_vertical(self, item_id: int) -> bool:
        query = text("DELETE FROM lead_client_verticals WHERE id = :id")
        async with engine.begin() as conn:
            try:
                result = await conn.execute(query, {"id": item_id})
                return (result.rowcount or 0) > 0
            except IntegrityError:
                raise HTTPException(status_code=409, detail="Cannot delete vertical with active dependencies")

    async def list_scoring_models(self, vertical_id: Optional[int] = None) -> List[ScoringModelRow]:
        where = ""
        params: Dict[str, Any] = {}
        if vertical_id:
            where = "WHERE m.vertical_id = :vertical_id"
            params["vertical_id"] = vertical_id

        query = text(f"""
            SELECT
                m.id,
                m.vertical_id,
                v.name AS vertical_name,
                m.name,
                m.version,
                m.prompt_version,
                m.is_active,
                m.normalization_strategy,
                m.created_at,
                m.updated_at
            FROM lead_scoring_models m
            LEFT JOIN lead_client_verticals v ON v.id = m.vertical_id
            {where}
            ORDER BY v.name ASC, m.version DESC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            return [self._validate_row(ScoringModelRow, row) for row in result.all()]

    async def get_scoring_model(self, item_id: UUID) -> Optional[ScoringModelRow]:
        query = text("""
            SELECT
                m.id,
                m.vertical_id,
                v.name AS vertical_name,
                m.name,
                m.version,
                m.prompt_version,
                m.is_active,
                m.normalization_strategy,
                m.created_at,
                m.updated_at
            FROM lead_scoring_models m
            LEFT JOIN lead_client_verticals v ON v.id = m.vertical_id
            WHERE m.id = :id
        """)
        async with engine.connect() as conn:
            row = (await conn.execute(query, {"id": item_id})).fetchone()
            return self._validate_row(ScoringModelRow, row) if row else None

    async def create_scoring_model(self, payload: ScoringModelCreate) -> ScoringModelRow:
        query = text("""
            INSERT INTO lead_scoring_models (
                vertical_id, name, version, prompt_version, is_active, normalization_strategy
            )
            VALUES (
                :vertical_id, :name, :version, :prompt_version, :is_active, :normalization_strategy
            )
            RETURNING id
        """)
        async with engine.begin() as conn:
            try:
                created = (await conn.execute(query, payload.model_dump())).fetchone()
                if not created:
                    raise HTTPException(status_code=500, detail="Failed to create scoring model")
                item_id = created.id
            except IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Scoring model conflicts with an existing record")

        return await self.get_scoring_model(item_id)

    async def update_scoring_model(self, item_id: UUID, payload: ScoringModelUpdate) -> Optional[ScoringModelRow]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return await self.get_scoring_model(item_id)

        updates: List[str] = []
        params: Dict[str, Any] = {"id": item_id}
        for key, value in data.items():
            updates.append(f"{key} = :{key}")
            params[key] = value

        query = text(f"""
            UPDATE lead_scoring_models
            SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id
        """)
        async with engine.begin() as conn:
            try:
                row = (await conn.execute(query, params)).fetchone()
                if not row:
                    return None
            except IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Scoring model conflicts with an existing record")

        return await self.get_scoring_model(item_id)

    async def delete_scoring_model(self, item_id: UUID) -> bool:
        query = text("DELETE FROM lead_scoring_models WHERE id = :id")
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": item_id})
            return (result.rowcount or 0) > 0

    async def list_scoring_criteria(self, model_id: Optional[UUID] = None) -> List[ScoringCriterionRow]:
        where = ""
        params: Dict[str, Any] = {}
        if model_id:
            where = "WHERE c.model_id = :model_id"
            params["model_id"] = model_id

        query = text(f"""
            SELECT
                c.id,
                c.model_id,
                m.name AS model_name,
                v.name AS vertical_name,
                c.criterion_key,
                c.label,
                c.weight,
                c.min_score,
                c.max_score,
                c.display_order,
                c.is_active
            FROM lead_scoring_criteria c
            JOIN lead_scoring_models m ON m.id = c.model_id
            LEFT JOIN lead_client_verticals v ON v.id = m.vertical_id
            {where}
            ORDER BY v.name ASC, m.name ASC, c.display_order ASC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            return [self._validate_row(ScoringCriterionRow, row) for row in result.all()]

    async def get_scoring_criterion(self, item_id: UUID) -> Optional[ScoringCriterionRow]:
        query = text("""
            SELECT
                c.id,
                c.model_id,
                m.name AS model_name,
                v.name AS vertical_name,
                c.criterion_key,
                c.label,
                c.weight,
                c.min_score,
                c.max_score,
                c.display_order,
                c.is_active
            FROM lead_scoring_criteria c
            JOIN lead_scoring_models m ON m.id = c.model_id
            LEFT JOIN lead_client_verticals v ON v.id = m.vertical_id
            WHERE c.id = :id
        """)
        async with engine.connect() as conn:
            row = (await conn.execute(query, {"id": item_id})).fetchone()
            return self._validate_row(ScoringCriterionRow, row) if row else None

    async def create_scoring_criterion(self, payload: ScoringCriterionCreate) -> ScoringCriterionRow:
        query = text("""
            INSERT INTO lead_scoring_criteria (
                model_id, criterion_key, label, weight, min_score, max_score, display_order, is_active
            )
            VALUES (
                :model_id, :criterion_key, :label, :weight, :min_score, :max_score, :display_order, :is_active
            )
            RETURNING id
        """)
        async with engine.begin() as conn:
            try:
                created = (await conn.execute(query, payload.model_dump())).fetchone()
                if not created:
                    raise HTTPException(status_code=500, detail="Failed to create scoring criterion")
                item_id = created.id
            except IntegrityError:
                raise HTTPException(status_code=409, detail="Criterion key already exists for this model")

        return await self.get_scoring_criterion(item_id)

    async def update_scoring_criterion(self, item_id: UUID, payload: ScoringCriterionUpdate) -> Optional[ScoringCriterionRow]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return await self.get_scoring_criterion(item_id)

        updates: List[str] = []
        params: Dict[str, Any] = {"id": item_id}
        for key, value in data.items():
            updates.append(f"{key} = :{key}")
            params[key] = value

        query = text(f"""
            UPDATE lead_scoring_criteria
            SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id
        """)
        async with engine.begin() as conn:
            try:
                row = (await conn.execute(query, params)).fetchone()
                if not row:
                    return None
            except IntegrityError:
                raise HTTPException(status_code=409, detail="Criterion key already exists for this model")

        return await self.get_scoring_criterion(item_id)

    async def delete_scoring_criterion(self, item_id: UUID) -> bool:
        query = text("DELETE FROM lead_scoring_criteria WHERE id = :id")
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": item_id})
            return (result.rowcount or 0) > 0

    async def list_scoring_bands(self, criterion_id: Optional[UUID] = None) -> List[ScoringBandRow]:
        where = ""
        params: Dict[str, Any] = {}
        if criterion_id:
            where = "WHERE b.criterion_id = :criterion_id"
            params["criterion_id"] = criterion_id

        query = text(f"""
            SELECT
                b.id,
                b.criterion_id,
                c.criterion_key,
                m.name AS model_name,
                b.band_key,
                b.label,
                b.min_score,
                b.max_score,
                b.icon,
                b.color
            FROM lead_scoring_bands b
            JOIN lead_scoring_criteria c ON c.id = b.criterion_id
            JOIN lead_scoring_models m ON m.id = c.model_id
            {where}
            ORDER BY m.name ASC, c.display_order ASC, b.min_score ASC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            return [self._validate_row(ScoringBandRow, row) for row in result.all()]

    async def get_scoring_band(self, item_id: UUID) -> Optional[ScoringBandRow]:
        query = text("""
            SELECT
                b.id,
                b.criterion_id,
                c.criterion_key,
                m.name AS model_name,
                b.band_key,
                b.label,
                b.min_score,
                b.max_score,
                b.icon,
                b.color
            FROM lead_scoring_bands b
            JOIN lead_scoring_criteria c ON c.id = b.criterion_id
            JOIN lead_scoring_models m ON m.id = c.model_id
            WHERE b.id = :id
        """)
        async with engine.connect() as conn:
            row = (await conn.execute(query, {"id": item_id})).fetchone()
            return self._validate_row(ScoringBandRow, row) if row else None

    async def create_scoring_band(self, payload: ScoringBandCreate) -> ScoringBandRow:
        query = text("""
            INSERT INTO lead_scoring_bands (
                criterion_id, band_key, label, min_score, max_score, icon, color
            )
            VALUES (
                :criterion_id, :band_key, :label, :min_score, :max_score, :icon, :color
            )
            RETURNING id
        """)
        async with engine.begin() as conn:
            try:
                created = (await conn.execute(query, payload.model_dump())).fetchone()
                if not created:
                    raise HTTPException(status_code=500, detail="Failed to create scoring band")
                item_id = created.id
            except (IntegrityError, DBAPIError) as exc:
                msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
                if "Overlapping scoring bands" in msg:
                    raise HTTPException(status_code=409, detail="Band range overlaps with an existing band in this criterion")
                raise HTTPException(status_code=409, detail="Band conflicts with existing key/range in this criterion")

        return await self.get_scoring_band(item_id)

    async def update_scoring_band(self, item_id: UUID, payload: ScoringBandUpdate) -> Optional[ScoringBandRow]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return await self.get_scoring_band(item_id)

        updates: List[str] = []
        params: Dict[str, Any] = {"id": item_id}
        for key, value in data.items():
            updates.append(f"{key} = :{key}")
            params[key] = value

        query = text(f"""
            UPDATE lead_scoring_bands
            SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id
        """)
        async with engine.begin() as conn:
            try:
                row = (await conn.execute(query, params)).fetchone()
                if not row:
                    return None
            except (IntegrityError, DBAPIError) as exc:
                msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
                if "Overlapping scoring bands" in msg:
                    raise HTTPException(status_code=409, detail="Band range overlaps with an existing band in this criterion")
                raise HTTPException(status_code=409, detail="Band conflicts with existing key/range in this criterion")

        return await self.get_scoring_band(item_id)

    async def delete_scoring_band(self, item_id: UUID) -> bool:
        query = text("DELETE FROM lead_scoring_bands WHERE id = :id")
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": item_id})
            return (result.rowcount or 0) > 0

    async def list_scoring_prompts(self, model_id: Optional[UUID] = None) -> List[ScoringPromptRow]:
        where = ""
        params: Dict[str, Any] = {}
        if model_id:
            where = "WHERE p.model_id = :model_id"
            params["model_id"] = model_id

        query = text(f"""
            SELECT
                p.id,
                p.model_id,
                m.name AS model_name,
                p.version,
                p.prompt_template,
                p.extraction_schema AS extraction_schema_legacy,
                p.is_active,
                p.created_by,
                p.created_at,
                p.updated_at
            FROM lead_scoring_prompts p
            JOIN lead_scoring_models m ON m.id = p.model_id
            {where}
            ORDER BY m.name ASC, p.version DESC
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, params)
            return [self._validate_row(ScoringPromptRow, row) for row in result.all()]

    async def get_scoring_prompt(self, item_id: UUID) -> Optional[ScoringPromptRow]:
        query = text("""
            SELECT
                p.id,
                p.model_id,
                m.name AS model_name,
                p.version,
                p.prompt_template,
                p.extraction_schema AS extraction_schema_legacy,
                p.is_active,
                p.created_by,
                p.created_at,
                p.updated_at
            FROM lead_scoring_prompts p
            JOIN lead_scoring_models m ON m.id = p.model_id
            WHERE p.id = :id
        """)
        async with engine.connect() as conn:
            row = (await conn.execute(query, {"id": item_id})).fetchone()
            return self._validate_row(ScoringPromptRow, row) if row else None

    async def create_scoring_prompt(self, payload: ScoringPromptCreate, created_by: Optional[UUID]) -> ScoringPromptRow:
        query = text("""
            INSERT INTO lead_scoring_prompts (
                model_id, version, prompt_template, is_active, created_by
            )
            VALUES (
                :model_id, :version, :prompt_template, :is_active, :created_by
            )
            RETURNING id
        """)
        params = payload.model_dump()
        params["created_by"] = created_by

        async with engine.begin() as conn:
            try:
                created = (await conn.execute(query, params)).fetchone()
                if not created:
                    raise HTTPException(status_code=500, detail="Failed to create scoring prompt")
                item_id = created.id
            except IntegrityError as exc:
                msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
                if "lead_scoring_prompts_model_id_version_key" in msg:
                    raise HTTPException(status_code=409, detail="Prompt version already exists for this model")
                if "uq_lead_scoring_prompts_active_model" in msg:
                    raise HTTPException(status_code=409, detail="Only one active prompt is allowed per model")
                raise HTTPException(status_code=409, detail="Scoring prompt conflicts with an existing record")

        return await self.get_scoring_prompt(item_id)

    async def update_scoring_prompt(self, item_id: UUID, payload: ScoringPromptUpdate) -> Optional[ScoringPromptRow]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return await self.get_scoring_prompt(item_id)

        updates: List[str] = []
        params: Dict[str, Any] = {"id": item_id}

        for key, value in data.items():
            updates.append(f"{key} = :{key}")
            params[key] = value

        query = text(f"""
            UPDATE lead_scoring_prompts
            SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id
        """)
        async with engine.begin() as conn:
            try:
                row = (await conn.execute(query, params)).fetchone()
                if not row:
                    return None
            except IntegrityError as exc:
                msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
                if "lead_scoring_prompts_model_id_version_key" in msg:
                    raise HTTPException(status_code=409, detail="Prompt version already exists for this model")
                if "uq_lead_scoring_prompts_active_model" in msg:
                    raise HTTPException(status_code=409, detail="Only one active prompt is allowed per model")
                raise HTTPException(status_code=409, detail="Scoring prompt conflicts with an existing record")

        return await self.get_scoring_prompt(item_id)

    async def delete_scoring_prompt(self, item_id: UUID) -> bool:
        query = text("DELETE FROM lead_scoring_prompts WHERE id = :id")
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": item_id})
            return (result.rowcount or 0) > 0

    async def list_vertical_options(self) -> List[Dict[str, Any]]:
        query = text("SELECT id, name FROM lead_client_verticals ORDER BY name ASC")
        async with engine.connect() as conn:
            rows = (await conn.execute(query)).all()
            return [{"id": row.id, "name": row.name} for row in rows]

    async def list_model_options(self) -> List[Dict[str, Any]]:
        query = text("""
            SELECT m.id, (v.name || ' · ' || m.name || ' v' || m.version::text) AS name
            FROM lead_scoring_models m
            LEFT JOIN lead_client_verticals v ON v.id = m.vertical_id
            ORDER BY v.name ASC, m.name ASC, m.version DESC
        """)
        async with engine.connect() as conn:
            rows = (await conn.execute(query)).all()
            return [{"id": str(row.id), "name": row.name} for row in rows]

    async def list_criterion_options(self) -> List[Dict[str, Any]]:
        query = text("""
            SELECT c.id, (m.name || ' · ' || c.label || ' (' || c.criterion_key || ')') AS name
            FROM lead_scoring_criteria c
            JOIN lead_scoring_models m ON m.id = c.model_id
            ORDER BY m.name ASC, c.display_order ASC
        """)
        async with engine.connect() as conn:
            rows = (await conn.execute(query)).all()
            return [{"id": str(row.id), "name": row.name} for row in rows]


service = AdminScoringService()
