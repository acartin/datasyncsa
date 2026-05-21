from fastapi import APIRouter

from app.api.routes import analytics, datasets, health, me, menu, operations, settings


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(menu.router, prefix="/menu", tags=["menu"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(operations.router, prefix="/operations", tags=["operations"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
