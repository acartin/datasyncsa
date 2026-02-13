import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.dal.database import engine
from sqlalchemy import text

async def inspect(table_name):
    query = text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = :table_name
        ORDER BY ordinal_position;
    """)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            rows = result.fetchall()
            if not rows:
                print(f"Table '{table_name}' not found or empty schema info.")
            else:
                print(f"Schema for '{table_name}':")
                for row in rows:
                    print(f"- {row[0]}: {row[1]} (Nullable: {row[2]})")
    except Exception as e:
        print(f"Error inspecting schema: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_schema.py <table_name>")
    else:
        asyncio.run(inspect(sys.argv[1]))
