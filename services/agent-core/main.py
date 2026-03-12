from fastapi import FastAPI


app = FastAPI(title="agent-core")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "agent-core"}
