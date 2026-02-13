import uuid

from app.modules.leads import router as leads_router


def test_manager_dashboard_requires_auth(client):
    response = client.get("/dashboard/manager")
    assert response.status_code == 401


def test_manager_dashboard_with_auth_returns_ok(client, auth_override, make_user):
    auth_override(make_user())
    response = client.get("/dashboard/manager")
    assert response.status_code == 200
    assert response.json()["layout"] == "dashboard-standard"


def test_contacts_categories_requires_auth(client):
    response = client.get("/contacts/categories")
    assert response.status_code == 401


def test_lead_detail_passes_user_scope(client, auth_override, make_user, monkeypatch):
    tenant_id = uuid.uuid4()
    user = make_user(tenant_ids=[tenant_id])
    auth_override(user)

    captured = {}
    lead_id = uuid.uuid4()

    async def _fake_get_lead_by_id(*, lead_id, user_id, is_superuser, tenant_ids):
        captured["lead_id"] = lead_id
        captured["user_id"] = user_id
        captured["is_superuser"] = is_superuser
        captured["tenant_ids"] = tenant_ids
        return {
            "id": lead_id,
            "full_name": "Lead Test",
            "email": "lead@test.com",
            "phone": "123",
            "score_total": 80,
            "status_label": "New",
        }

    monkeypatch.setattr(leads_router.lead_service, "get_lead_by_id", _fake_get_lead_by_id)

    response = client.get(f"/leads/{lead_id}")
    assert response.status_code == 200
    assert captured["lead_id"] == lead_id
    assert captured["user_id"] == user.id
    assert captured["is_superuser"] is False
    assert captured["tenant_ids"] == [tenant_id]
