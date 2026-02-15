from uuid import uuid4

from fastapi.testclient import TestClient

from app import api as semantic_api
from main import app


def test_search_scopes_repo_calls_by_client_id(monkeypatch):
    seen_client_ids = []

    class FakeEmbedder:
        async def embed_query(self, _text):
            return [0.1, 0.2, 0.3]

    class FakeRepo:
        def search_similar(self, client_id, _query_vector, _top_k, _filters):
            seen_client_ids.append(client_id)
            return [
                {
                    "content_id": f"doc-{client_id}",
                    "title": "Scoped Doc",
                    "body_content": "contenido",
                    "metadata": {"client_id": client_id},
                    "similarity": 0.9,
                }
            ]

        def ping(self):
            return True

    monkeypatch.setattr(semantic_api, "embedder", FakeEmbedder())
    monkeypatch.setattr(semantic_api, "repo", FakeRepo())
    client = TestClient(app)

    client_a = str(uuid4())
    client_b = str(uuid4())
    res_a = client.post("/api/v1/search", json={"query_text": "hola", "client_id": client_a, "top_k": 3})
    res_b = client.post("/api/v1/search", json={"query_text": "hola", "client_id": client_b, "top_k": 3})

    assert res_a.status_code == 200
    assert res_b.status_code == 200
    assert seen_client_ids == [client_a, client_b]
    assert res_a.json()["results"][0]["metadata"]["client_id"] == client_a
    assert res_b.json()["results"][0]["metadata"]["client_id"] == client_b
