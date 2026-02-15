import pytest

from app.vector_repo import VectorRepository


def test_vector_repo_rejects_invalid_table_name(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("TABLE_VECTORS", "bad-table;drop")
    with pytest.raises(ValueError):
        VectorRepository()


def test_search_similar_does_not_treat_shared_as_global(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    repo = VectorRepository()
    captured = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = params

        def fetchall(self):
            return []

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self, cursor_factory=None):
            return FakeCursor()

    monkeypatch.setattr(repo, "_ensure_initialized", lambda: None)
    monkeypatch.setattr(repo, "_get_connection", lambda: FakeConn())

    repo.search_similar(client_id="client-a", query_vector=[0.1, 0.2], top_k=3, filters={})

    query = captured["query"]
    assert "metadata->>'access_level' = 'public'" in query
    assert "'shared'" not in query
