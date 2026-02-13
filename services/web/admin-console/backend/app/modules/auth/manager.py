import uuid
from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from app.modules.auth.db import get_user_db
from app.modules.auth.models import User
from app.config.settings import settings
import logging

# Secret for password reset tokens, etc.
SECRET = settings.secret_key
logger = logging.getLogger(__name__)

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User registered", extra={"user_id": str(user.id)})

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Password reset requested", extra={"user_id": str(user.id)})

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Verification requested", extra={"user_id": str(user.id)})

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
