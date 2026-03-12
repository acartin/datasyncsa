from fastapi import FastAPI


app = FastAPI(title="scoring-core")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "scoring-core"}
