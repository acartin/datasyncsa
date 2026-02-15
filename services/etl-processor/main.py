from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {
        "status": "DEPRECATED",
        "message": "Use service 'etl-docs' instead of 'etl-processor'."
    }
