from fastapi import FastAPI
app = FastAPI()
@app.get("/")
def read_root():
    return {"status": "Admin Console (AiFirst) Backend Running"}
