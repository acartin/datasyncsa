from uuid import uuid4

from fastapi.testclient import TestClient

import main


class IsolatedVectorStore:
    def __init__(self, docs_by_client):
        self.docs_by_client = docs_by_client

    def list_documents(self, client_id):
        return list(self.docs_by_client.get(str(client_id), []))

    def delete_document(self, client_id, content_id):
        client_key = str(client_id)
        current = self.docs_by_client.get(client_key, [])
        for i, item in enumerate(current):
            if item["content_id"] == content_id:
                deleted = current.pop(i)
                return deleted["filename"]
        return None


def test_list_documents_is_scoped_by_client_id(monkeypatch):
    client_a = str(uuid4())
    client_b = str(uuid4())
    docs = {
        client_a: [{"filename": "a.pdf", "content_id": "doc_a_1"}],
        client_b: [{"filename": "b.pdf", "content_id": "doc_b_1"}],
    }
    vector_store = IsolatedVectorStore(docs)
    monkeypatch.setattr(main, "VectorStore", lambda: vector_store)

    client = TestClient(main.app)
    res_a = client.get(f"/documents/list/{client_a}")
    res_b = client.get(f"/documents/list/{client_b}")

    assert res_a.status_code == 200
    assert res_b.status_code == 200
    assert [d["content_id"] for d in res_a.json()["documents"]] == ["doc_a_1"]
    assert [d["content_id"] for d in res_b.json()["documents"]] == ["doc_b_1"]


def test_delete_document_does_not_affect_other_client(monkeypatch):
    client_a = str(uuid4())
    client_b = str(uuid4())
    docs = {
        client_a: [{"filename": "a.pdf", "content_id": "doc_a_1"}],
        client_b: [{"filename": "b.pdf", "content_id": "doc_b_1"}],
    }
    vector_store = IsolatedVectorStore(docs)
    monkeypatch.setattr(main, "VectorStore", lambda: vector_store)
    monkeypatch.setattr(main.FileManager, "delete_document", lambda *_: True)

    client = TestClient(main.app)
    res = client.delete(f"/documents/{client_a}/doc_b_1")

    assert res.status_code == 200
    assert [d["content_id"] for d in docs[client_a]] == ["doc_a_1"]
    assert [d["content_id"] for d in docs[client_b]] == ["doc_b_1"]
