import asyncio
import uuid
from app.modules.users.service import service
from app.modules.users.schemas import UserCreate, UserUpdate
from fastapi_users.password import PasswordHelper
from app.dal.database import engine
from sqlalchemy import text

async def test_update_flow():
    email = f"test_update_{uuid.uuid4()}@example.com"
    pwd_initial = "initial123"
    pwd_new = "changed456"
    
    print(f"1. Creating user {email} with password '{pwd_initial}'")
    user_in = UserCreate(
        email=email,
        password=pwd_initial,
        is_active=True,
        is_superuser=False,
        is_verified=True,
        name="Test Update"
    )
    
    user = await service.create_user(user_in)
    print(f"   User created: {user.id}")
    
    # Verify initial password
    ph = PasswordHelper()
    async with engine.connect() as conn:
        row = await conn.execute(text("SELECT hashed_password FROM auth_users WHERE id = :id"), {"id": user.id})
        hashed = row.scalar()
        valid = ph.verify(pwd_initial, hashed)
        print(f"   Initial password verify: {valid}")
        if not valid:
            print("   ERROR: Initial password hashing failed.")
            return

    # 2. Updating password using service
    print(f"2. Updating password to '{pwd_new}' via service...")
    update_in = UserUpdate(password=pwd_new) 
    # Note: access other fields to ensure pydantic model is populated similarly to request?
    # UserUpdate has optional fields.
    
    await service.update_user(user.id, update_in)
    print("   Update called.")
    
    # 3. Verify new password
    async with engine.connect() as conn:
        row = await conn.execute(text("SELECT hashed_password FROM auth_users WHERE id = :id"), {"id": user.id})
        hashed_new = row.scalar()
        
        # Check if hash changed
        if hashed == hashed_new:
             print("   ERROR: Hash did NOT change in DB!")
        else:
             print("   Hash changed in DB.")
             
        valid_new = ph.verify(pwd_new, hashed_new)
        print(f"   New password verify: {valid_new}")
        
        valid_old = ph.verify(pwd_initial, hashed_new)
        print(f"   Old password verify (should be False): {valid_old}")

        if valid_new:
            print("SUCCESS: Password update logic is working.")
        else:
            print("FAILURE: New password is not valid.")

    # Cleanup
    await service.delete_user(user.id)
    print("Test user deleted.")

if __name__ == "__main__":
    asyncio.run(test_update_flow())
