import uuid
from datetime import datetime
from types import SimpleNamespace
import importlib

from app.main import app
from app.modules.auth.config import current_active_user

ai_library_router_module = importlib.import_module("app.modules.ai_library.router")
leads_router_module = importlib.import_module("app.modules.leads.router")


def _set_auth_override(user):
    app.dependency_overrides[current_active_user] = lambda: user


def _clear_auth_override():
    app.dependency_overrides.pop(current_active_user, None)


def _sample_lead(lead_id: uuid.UUID):
    return {
        "id": lead_id,
        "full_name": "Lead QA",
        "email": "lead.qa@example.com",
        "phone": "5551234",
        "score_total": 82,
        "created_at": datetime(2026, 2, 1),
        "status_label": "Nuevo",
    }


def test_leads_me_view_contract(client, monkeypatch):
    user = SimpleNamespace(
        id=uuid.uuid4(),
        is_superuser=False,
        tenants=[SimpleNamespace(client_id=uuid.uuid4())],
    )
    lead_id = uuid.uuid4()

    async def _fake_get_my_leads(_user_id):
        return [_sample_lead(lead_id)]

    monkeypatch.setattr(leads_router_module.lead_service, "get_my_leads", _fake_get_my_leads)
    _set_auth_override(user)
    try:
        response = client.get("/leads/me")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    grid = body["components"][1]["components"][0]
    props = grid["properties"]
    actions = props["actions"]

    assert grid["type"] == "custom-leads-grid"
    assert props["data_url"] == "/leads/me/data"
    assert len(actions) == 2
    assert actions[0]["action_url"] == "/dashboard/leads/{id}"
    assert actions[1]["action_url"] == "/dashboard/leads/{id}/chat"


def test_lead_detail_contract_includes_chat_navigation(client, monkeypatch):
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        is_superuser=False,
        tenants=[SimpleNamespace(client_id=tenant_id)],
    )

    captured = {}

    async def _fake_get_lead_by_id(*, lead_id, user_id, is_superuser, tenant_ids):
        captured["lead_id"] = lead_id
        captured["user_id"] = user_id
        captured["is_superuser"] = is_superuser
        captured["tenant_ids"] = tenant_ids
        return _sample_lead(lead_id)

    monkeypatch.setattr(leads_router_module.lead_service, "get_lead_by_id", _fake_get_lead_by_id)
    _set_auth_override(user)
    try:
        response = client.get(f"/leads/{lead_id}")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    button = body["components"][0]["components"][1]["components"][0]["components"][1]["buttons"][0]

    assert captured["lead_id"] == lead_id
    assert captured["user_id"] == user_id
    assert captured["is_superuser"] is False
    assert captured["tenant_ids"] == [tenant_id]
    assert button["action"] == "navigate"
    assert button["url"] == f"/leads/{lead_id}/chat"


def test_ai_library_view_contract(client):
    user = SimpleNamespace(id=uuid.uuid4(), is_superuser=True, tenants=[SimpleNamespace(client_id=uuid.uuid4())])
    _set_auth_override(user)
    try:
        response = client.get("/ai-library")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    tabs = body["components"][1]
    pdf_props = tabs["items"][0]["content"][0]["properties"]
    url_props = tabs["items"][1]["content"][0]["properties"]

    assert tabs["type"] == "tabs"
    assert pdf_props["data_url"] == "/ai-library/pdfs/data"
    assert pdf_props["header_actions"][0]["action_url"] == "/ai-library/pdfs/upload"
    assert pdf_props["actions"][0]["action_url"] == "/ai-library/pdfs/{content_id}"
    assert url_props["data_url"] == "/ai-library/urls/data"
    assert url_props["header_actions"][0]["action_url"] == "/ai-library/urls/add"


def test_ai_library_pdfs_data_maps_sync_status(client, monkeypatch):
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4(), is_superuser=False, tenants=[SimpleNamespace(client_id=tenant_id)])

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "documents": [
                    {"content_id": "doc-1", "filename": "manual.pdf", "sync_status": "SYNCED"},
                    {"content_id": "doc-2", "filename": "draft.pdf", "sync_status": "QUEUED"},
                ]
            }

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url):
            return _FakeResponse()

    monkeypatch.setattr(ai_library_router_module.httpx, "AsyncClient", _FakeAsyncClient)
    _set_auth_override(user)
    try:
        response = client.get("/ai-library/pdfs/data")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["status"] == "SYNCED"
    assert rows[1]["status"] == "QUEUED"
