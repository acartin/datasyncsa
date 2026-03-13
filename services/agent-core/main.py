from fastapi import FastAPI

from app.api import api_router

app = FastAPI(title="agent-core")
app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "agent-core"}
