"""Minimal FastAPI entrypoint for the multitenant AI runtime."""

from fastapi import FastAPI

from services.ai_runtime.api import router
from services.ai_runtime.runtime.settings import settings

app = FastAPI(title=settings.app_name)
app.include_router(router, prefix=settings.api_prefix)
