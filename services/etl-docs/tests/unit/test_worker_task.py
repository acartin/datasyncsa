from uuid import uuid4

from src.ETL_DOCS import worker_task


def test_worker_task_calls_processor(monkeypatch):
    called = {}

    class DummyProcessor:
        def process_document(self, **kwargs):
            called.update(kwargs)
            return {"status": "SYNCED", "content_id": kwargs["content_id"]}

    monkeypatch.setattr(worker_task, "DocumentProcessor", DummyProcessor)

    client_id = uuid4()
    result = worker_task.process_document_task(
        "/tmp/doc.pdf",
        client_id,
        "doc_test_1",
        "doc.pdf",
        "private",
        "knowledge_base",
    )

    assert result["status"] == "SYNCED"
    assert called["file_path"] == "/tmp/doc.pdf"
    assert called["client_id"] == client_id
    assert called["content_id"] == "doc_test_1"
