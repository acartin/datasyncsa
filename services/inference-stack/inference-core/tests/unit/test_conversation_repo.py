from uuid import uuid4

from app.repositories.conversation_repo import ConversationRepository


class _FakeCursor:
    def __init__(self, fetchone_results):
        self.fetchone_results = list(fetchone_results)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        if not self.fetchone_results:
            return None
        return self.fetchone_results.pop(0)

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_get_or_create_conversation_reuses_only_same_tenant(monkeypatch):
    repo = ConversationRepository()
    client_id = str(uuid4())
    conversation_id = str(uuid4())
    existing = {"id": conversation_id, "messages": [], "lead_id": str(uuid4())}

    fake_cursor = _FakeCursor([existing])
    fake_conn = _FakeConnection(fake_cursor)
    monkeypatch.setattr(repo, "_get_connection", lambda: fake_conn)

    result = repo.get_or_create_conversation(client_id, conversation_id)

    assert result["id"] == conversation_id
    assert len(fake_cursor.executed) == 1
    first_sql, first_params = fake_cursor.executed[0]
    assert "JOIN lead_leads" in first_sql
    assert "ll.client_id = %s" in first_sql
    assert first_params == (conversation_id, client_id)
    assert fake_conn.commits == 0


def test_get_or_create_conversation_creates_new_when_provided_id_not_in_tenant(monkeypatch):
    repo = ConversationRepository()
    client_id = str(uuid4())
    requested_conversation_id = str(uuid4())
    inserted = {"id": str(uuid4()), "messages": [], "lead_id": str(uuid4())}

    # 1st fetchone: no conversation for this tenant
    # 2nd fetchone: RETURNING * from INSERT lead_conversations
    fake_cursor = _FakeCursor([None, inserted])
    fake_conn = _FakeConnection(fake_cursor)
    monkeypatch.setattr(repo, "_get_connection", lambda: fake_conn)

    result = repo.get_or_create_conversation(client_id, requested_conversation_id)

    assert result["id"] == inserted["id"]
    statements = [sql for sql, _ in fake_cursor.executed]
    assert any("INSERT INTO lead_leads" in sql for sql in statements)
    assert any("INSERT INTO lead_conversations" in sql for sql in statements)

    insert_conv_params = next(
        params for sql, params in fake_cursor.executed if "INSERT INTO lead_conversations" in sql
    )
    # Must not reuse a foreign/mismatched requested conversation id.
    assert insert_conv_params[0] != requested_conversation_id
    assert fake_conn.commits == 1
