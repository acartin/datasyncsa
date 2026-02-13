from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from app.modules.auth.manager import get_user_manager
from app.modules.auth.config import auth_backend
from app.modules.auth.models import User
from app.modules.auth.schemas import UserRead, UserCreate, UserUpdate
import uuid

# Initialize FastAPI Users logic
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

router = APIRouter()

# 1. Auth Routes (Login/Logout)
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# 2. Register Routes
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# 3. User Management Routes (Me, Update)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
