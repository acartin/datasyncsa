import asyncio
import sys
import os

# Add backend directory to sys.path to allow imports from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.dal.database import engine
from sqlalchemy import text

async def _run_connection_check():
    try:
        print(f"Testing connection to: {engine.url}")
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"Connection Successful! Result: {result.scalar()}")
    except Exception as e:
        print(f"Connection Failed: {e}")


def test():
    asyncio.run(_run_connection_check())


if __name__ == "__main__":
    asyncio.run(_run_connection_check())
