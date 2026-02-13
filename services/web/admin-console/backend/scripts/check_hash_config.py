import asyncio
from fastapi_users.password import PasswordHelper
from passlib.context import CryptContext

def check_hashing():
    ph = PasswordHelper()
    print("Start context schemes:", ph.context.schemes())
    print("Default scheme:", ph.context.default_scheme())
    
    # Test a dummy hash verify
    # Argon2
    argon_hash = "$argon2id$v=19$m=65536,t=3,p=4$Z2s6LizMmechVudW9a6n/A$WYaOo8gttG3RBU3L4Czn3Tr7v6SlIaRjhsBKmYIXoVA"
    try:
        # Note: PasswordHelper.verify takes (plain, hash)
        # We don't know the plain for this hash, but we can check if it recognizes the scheme
        print(f"Argon2 hash identified? {ph.context.identify(argon_hash)}")
    except Exception as e:
        print(f"Argon2 check error: {e}")

    # Bcrypt (Common legacy)
    bcrypt_hash = "$2b$12$GwF.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F.F"
    try:
         print(f"Bcrypt hash identified? {ph.context.identify(bcrypt_hash)}")
    except Exception as e:
         print(f"Bcrypt check error: {e}")

if __name__ == "__main__":
    check_hashing()
