from datetime import UTC

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.db import get_connection
from app.core.security import VALID_ROLES, hash_token, new_session_token, session_expiry, verify_password
from app.repositories.auth_repository import AuthRepository


router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=240)


def get_repository() -> AuthRepository:
    return AuthRepository(get_connection)


@router.post("/login")
def login(payload: LoginRequest, repository: AuthRepository = Depends(get_repository)) -> dict[str, object]:
    user = repository.find_user_by_username(payload.username.strip())
    if not user or user["status"] != "active" or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = new_session_token()
    expires_at = session_expiry()
    repository.create_session(
        user_id=int(user["id"]),
        token_hash=hash_token(token),
        expires_at=expires_at.isoformat(),
        active_client_id=None,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at.astimezone(UTC).isoformat(),
    }


class LogoutRequest(BaseModel):
    token: str = Field(min_length=1)


@router.post("/logout")
def logout(payload: LogoutRequest, repository: AuthRepository = Depends(get_repository)) -> dict[str, str]:
    repository.revoke_session(token_hash=hash_token(payload.token))
    return {"status": "ok"}


class SimulateRoleRequest(BaseModel):
    role_id: str = Field(min_length=1, max_length=80)


@router.post("/simulate-role")
def simulate_role(
    payload: SimulateRoleRequest,
    authorization: str | None = Header(default=None),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")

    token_hash = hash_token(authorization.removeprefix("Bearer ").strip())
    if not repository.session_owner_can_simulate_roles(token_hash=token_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System admin role is required")

    role_id = payload.role_id.strip()
    if role_id not in VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    repository.set_session_active_role(
        token_hash=token_hash,
        role_id=None if role_id == "system-admin" else role_id,
    )
    return {"status": "ok", "role_id": role_id}
