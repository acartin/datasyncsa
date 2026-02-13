import pytest

from app.vector_repo import VectorRepository


def test_vector_repo_rejects_invalid_table_name(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("TABLE_VECTORS", "bad-table;drop")
    with pytest.raises(ValueError):
        VectorRepository()
