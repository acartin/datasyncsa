import asyncio
import os
from sqlalchemy import text
from app.dal.database import engine
from fastapi_users.password import PasswordHelper

async def restore_password():
    print("Restoring password for cocacola-admin@cocacola.com to 'holalola'...")
    ph = PasswordHelper()
    hashed = ph.hash("holalola")
    
    async with engine.begin() as conn:
        await conn.execute(text("""
            UPDATE auth_users 
            SET hashed_password = :pwd 
            WHERE email = 'cocacola-admin@cocacola.com'
        """), {"pwd": hashed})
        print("Password restored.")

if __name__ == "__main__":
    asyncio.run(restore_password())
