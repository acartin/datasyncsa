import logging
import os
import uuid
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from redis import Redis
from rq import Queue
from rq.job import Job

from src.ETL_DOCS.worker_task import process_document_task
from src.shared.file_manager import FileManager
from src.shared.memory_reset import reset_client_memory
from src.shared.vector_store import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ETL Docs API", version="1.0.0")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DOCS_QUEUE = os.getenv("DOCS_QUEUE_NAME", "docs")

redis_conn = Redis.from_url(REDIS_URL)
queue = Queue(DOCS_QUEUE, connection=redis_conn)


@app.get("/")
def root():
    return {"status": "ETL Docs API Running"}


@app.post("/documents/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    content_id: str | None = Form(None),
    access_level: str = Form("private"),
    category: str = Form("knowledge_base"),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only application/pdf is accepted")

    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    generated_content_id = content_id or f"doc_{uuid.uuid4()}"

    if FileManager.check_file_exists(client_uuid, file.filename):
        raise HTTPException(status_code=409, detail=f"File '{file.filename}' already exists")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_path = FileManager.save_upload(file_bytes, file.filename, client_uuid)

    vector_store = VectorStore()
    vector_store.register_document_in_db(
        client_id=client_uuid,
        filename=file.filename,
        storage_path=file_path,
        content_id=generated_content_id,
        access_level=access_level,
        category=category,
    )

    job = queue.enqueue(
        process_document_task,
        file_path,
        client_uuid,
        generated_content_id,
        file.filename,
        access_level,
        category,
        job_id=f"job_{generated_content_id}",
    )

    return {
        "status": "QUEUED",
        "job_id": job.id,
        "content_id": generated_content_id,
        "filename": file.filename,
        "queue_position": max(queue.count, 1),
    }


@app.get("/documents/list/{client_id}")
def list_documents(client_id: str):
    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    vector_store = VectorStore()
    docs = vector_store.list_documents(client_uuid)
    return {
        "status": "success",
        "client_id": client_id,
        "count": len(docs),
        "documents": docs,
    }


@app.get("/documents/jobs/{job_id}")
def get_job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "status": job.get_status(refresh=True),
        "result": job.result if job.is_finished else None,
    }


@app.delete("/documents/{client_id}/{content_id}")
def delete_document(client_id: str, content_id: str):
    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    vector_store = VectorStore()
    filename = vector_store.delete_document(client_uuid, content_id)
    if filename:
        FileManager.delete_document(client_uuid, filename)
    reset_client_memory(str(client_uuid), reason="document_deleted")

    return {"status": "success", "content_id": content_id}


@app.delete("/documents/client/{client_id}")
def delete_client_documents(client_id: str):
    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_id UUID") from exc

    vector_store = VectorStore()
    vector_store.delete_client(client_uuid)
    FileManager.delete_client_folder(client_uuid)
    reset_client_memory(str(client_uuid), reason="client_knowledge_purged")
    return {"status": "success", "client_id": client_id}
