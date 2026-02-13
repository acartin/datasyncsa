import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from app.modules.countries.service import service
from app.modules.countries.schemas import CountryCreate, CountryUpdate

async def verify_crud():
    print("--- Starting CRUD Verification for Countries ---")
    
    # 1. CREATE
    print("\n1. Testing CREATE...")
    new_country = CountryCreate(name="Testlandia", iso_code="TL")
    created = await service.create_country(new_country)
    print(f"Created: {created}")
    assert created.name == "Testlandia"
    assert created.id is not None

    # 2. READ (List)
    print("\n2. Testing READ (List)...")
    countries = await service.list_countries()
    print(f"Found {len(countries)} countries.")
    found = next((c for c in countries if c.id == created.id), None)
    assert found is not None
    print("New country found in list.")

    # 3. UPDATE
    print("\n3. Testing UPDATE...")
    update_data = CountryUpdate(name="RenamedLand")
    updated = await service.update_country(created.id, update_data)
    print(f"Updated: {updated}")
    assert updated.name == "RenamedLand"
    assert updated.iso_code == "TL" # Should remain unchanged

    # 4. DELETE
    print("\n4. Testing DELETE...")
    deleted = await service.delete_country(created.id)
    print(f"Delete Result: {deleted}")
    assert deleted is True
    
    # Verify deletion
    check = await service.get_country(created.id)
    assert check is None
    print("Country successfully deleted.")

    print("\n--- CRUD VERIFICATION SUCCESSFUL ---")

if __name__ == "__main__":
    asyncio.run(verify_crud())
