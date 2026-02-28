from fastapi.testclient import TestClient

from main import app
from app import api as semantic_api


def test_search_rejects_invalid_client_id():
    client = TestClient(app)
    res = client.post(
        "/api/v1/search",
        json={"query_text": "casas", "client_id": "bad-id", "top_k": 3},
    )
    assert res.status_code == 422


def test_search_returns_503_when_embedder_missing(monkeypatch):
    monkeypatch.setattr(semantic_api, "embedder", None)
    client = TestClient(app)
    res = client.post(
        "/api/v1/search",
        json={
            "query_text": "casas",
            "client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
            "top_k": 3,
        },
    )
    assert res.status_code == 503
    assert res.json()["detail"] == "Embedder service not configured"


def test_search_returns_503_when_repo_missing(monkeypatch):
    class FakeEmbedder:
        async def embed_query(self, _text):
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(semantic_api, "embedder", FakeEmbedder())
    monkeypatch.setattr(semantic_api, "repo", None)
    client = TestClient(app)
    res = client.post(
        "/api/v1/search",
        json={
            "query_text": "casas",
            "client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
            "top_k": 3,
        },
    )
    assert res.status_code == 503
    assert res.json()["detail"] == "Vector repository is not available"


def test_search_success_response(monkeypatch):
    class FakeEmbedder:
        async def embed_query(self, _text):
            return [0.1, 0.2, 0.3]

    class FakeRepo:
        def search_similar(self, *_args, **_kwargs):
            return [
                {
                    "content_id": "doc-1",
                    "title": "Doc",
                    "body_content": "contenido",
                    "metadata": {"category": "x"},
                    "similarity": 0.99,
                }
            ]

        def ping(self):
            return True

    monkeypatch.setattr(semantic_api, "embedder", FakeEmbedder())
    monkeypatch.setattr(semantic_api, "repo", FakeRepo())

    client = TestClient(app)
    res = client.post(
        "/api/v1/search",
        json={
            "query_text": "casas",
            "client_id": "64f357a0-98eb-44f1-9f41-6e615ed26180",
            "top_k": 3,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["client_id"] == "64f357a0-98eb-44f1-9f41-6e615ed26180"
    assert len(body["results"]) == 1
    assert body["results"][0]["score"] == 0.99
