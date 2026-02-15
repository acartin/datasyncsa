from uuid import uuid4

from fastapi.testclient import TestClient

import main


class DummyJob:
    def __init__(self, job_id: str):
        self.id = job_id


class DummyQueue:
    def __init__(self):
        self.count = 1

    def enqueue(self, _fn, *_args, job_id=None, **_kwargs):
        return DummyJob(job_id or "job_test")


class DummyVectorStore:
    def __init__(self):
        self.registered = []

    def register_document_in_db(self, **kwargs):
        self.registered.append(kwargs)

    def list_documents(self, _client_id):
        return [
            {
                "id": 1,
                "filename": "sample.pdf",
                "sync_status": "PENDING",
                "content_id": "doc_test",
            }
        ]


def test_upload_document_queues_job(monkeypatch):
    vector_store = DummyVectorStore()
    monkeypatch.setattr(main, "queue", DummyQueue())
    monkeypatch.setattr(main, "VectorStore", lambda: vector_store)
    monkeypatch.setattr(main.FileManager, "check_file_exists", lambda *_: False)
    monkeypatch.setattr(
        main.FileManager,
        "save_upload",
        lambda _bytes, _filename, _client_id: "/app/data/storage/documents/file.pdf",
    )

    client = TestClient(main.app)
    response = client.post(
        "/documents/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={
            "client_id": str(uuid4()),
            "content_id": "doc_test",
            "access_level": "private",
            "category": "knowledge_base",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["job_id"] == "job_doc_test"
    assert body["content_id"] == "doc_test"
    assert vector_store.registered


def test_upload_rejects_non_pdf():
    client = TestClient(main.app)
    response = client.post(
        "/documents/upload",
        files={"file": ("sample.txt", b"text", "text/plain")},
        data={"client_id": str(uuid4())},
    )
    assert response.status_code == 400
    assert "Only application/pdf" in response.text


def test_list_documents(monkeypatch):
    monkeypatch.setattr(main, "VectorStore", DummyVectorStore)
    client = TestClient(main.app)

    response = client.get(f"/documents/list/{uuid4()}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["count"] == 1


def test_delete_document_triggers_memory_reset(monkeypatch):
    calls = {}

    class DeleteVectorStore:
        def delete_document(self, _client_id, _content_id):
            return "sample.pdf"

    monkeypatch.setattr(main, "VectorStore", DeleteVectorStore)
    monkeypatch.setattr(main.FileManager, "delete_document", lambda *_: True)
    monkeypatch.setattr(main, "reset_client_memory", lambda client_id, reason=None: calls.update({"client_id": client_id, "reason": reason}) or True)

    client_id = str(uuid4())
    client = TestClient(main.app)
    res = client.delete(f"/documents/{client_id}/doc_1")

    assert res.status_code == 200
    assert calls["client_id"] == client_id
    assert calls["reason"] == "document_deleted"
