from sqlalchemy import text
from app.dal.database import engine
from .schemas import CountryCreate, CountryUpdate, CountryRow
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class CountryService:
    """
    Data Access Layer for Global Countries Catalog.
    Uses Explicit SQL. No ORM.
    """

    async def list_countries(self) -> List[CountryRow]:
        query = text("SELECT id, name, iso_code, updated_at FROM lead_countries ORDER BY name ASC")
        async with engine.connect() as conn:
            result = await conn.execute(query)
            # Efficient mapping using Pydantic
            return [CountryRow(id=row.id, name=row.name, iso_code=row.iso_code, updated_at=row.updated_at) for row in result]

    async def get_country(self, country_id: int) -> Optional[CountryRow]:
        query = text("SELECT id, name, iso_code, updated_at FROM lead_countries WHERE id = :id")
        async with engine.connect() as conn:
            result = await conn.execute(query, {"id": country_id})
            row = result.fetchone()
            if row:
                return CountryRow(id=row.id, name=row.name, iso_code=row.iso_code, updated_at=row.updated_at)
            return None

    async def create_country(self, country: CountryCreate) -> CountryRow:
        query = text("""
            INSERT INTO lead_countries (name, iso_code, updated_at)
            VALUES (:name, :iso_code, NOW())
            RETURNING id, name, iso_code, updated_at
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"name": country.name, "iso_code": country.iso_code})
            row = result.fetchone()
            await conn.commit()
            return CountryRow(id=row.id, name=row.name, iso_code=row.iso_code, updated_at=row.updated_at)

    async def update_country(self, country_id: int, country: CountryUpdate) -> Optional[CountryRow]:
        # Dynamic build of SET clause
        updates = []
        params = {"id": country_id}
        
        if country.name:
            updates.append("name = :name")
            params["name"] = country.name
            
        if country.iso_code:
            updates.append("iso_code = :iso_code")
            params["iso_code"] = country.iso_code

        if not updates:
            return await self.get_country(country_id)

        updates.append("updated_at = NOW()")
        
        query_str = f"""
            UPDATE lead_countries
            SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id, name, iso_code, updated_at
        """
        
        async with engine.connect() as conn:
            try:
                result = await conn.execute(text(query_str), params)
                row = result.fetchone()
                await conn.commit()
                if row:
                    return CountryRow(id=row.id, name=row.name, iso_code=row.iso_code, updated_at=row.updated_at)
                return None
            except IntegrityError:
                await conn.rollback()
                raise HTTPException(status_code=409, detail="ISO Code already exists.")
            except Exception as e:
                logger.exception("Country update failed", exc_info=e)
                raise HTTPException(status_code=500, detail="Database update failed")

    async def delete_country(self, country_id: int) -> bool:
        query = text("DELETE FROM lead_countries WHERE id = :id")
        async with engine.connect() as conn:
            result = await conn.execute(query, {"id": country_id})
            await conn.commit()
            return result.rowcount > 0

service = CountryService()
