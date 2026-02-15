import base64
import json
import uuid
from types import SimpleNamespace

from app.modules.auth.config import current_active_user
from app.modules.clients import router as clients_router
from app.main import app


def _decode_schema(value: str):
    return json.loads(base64.b64decode(value).decode())


def _set_auth_override(user):
    app.dependency_overrides[current_active_user] = lambda: user


def _clear_auth_override():
    app.dependency_overrides.pop(current_active_user, None)


def test_users_ui_schema_contract(client):
    _set_auth_override(SimpleNamespace(is_superuser=True, tenants=[], email="admin@test.local"))
    try:
        response = client.get("/system/users")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    grid = body["components"][0]["properties"]
    create_action = grid["header_actions"][0]
    edit_action = grid["actions"][0]

    assert create_action["action"] == "modal-form"
    assert create_action["action_url"] == "/system/users"
    assert edit_action["action_url"] == "/system/users/{id}"
    assert isinstance(create_action["schema"], str)
    assert isinstance(edit_action["schema"], str)
    assert any(field["name"] == "password" for field in _decode_schema(create_action["schema"]))


def test_roles_ui_schema_contract(client):
    _set_auth_override(SimpleNamespace(is_superuser=True, tenants=[], email="admin@test.local"))
    try:
        response = client.get("/system/roles")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    grid = body["components"][0]["properties"]
    create_action = grid["header_actions"][0]
    edit_action = grid["actions"][0]

    assert create_action["action_url"] == "/system/roles"
    assert edit_action["action_url"] == "/system/roles/{id}"
    assert create_action["schema"] == edit_action["schema"]
    decoded = _decode_schema(create_action["schema"])
    assert [f["name"] for f in decoded] == ["name", "slug"]


def test_prompts_ui_schema_contract_for_admin(client):
    _set_auth_override(SimpleNamespace(is_superuser=True, tenants=[], email="admin@test.local"))
    try:
        response = client.get("/prompts")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    props = body["components"][0]["properties"]
    create_action = props["header_actions"][0]
    delete_action = props["actions"][1]

    assert create_action["action_url"] == "/prompts"
    assert delete_action["action_url"] == "/prompts/{id}"
    assert delete_action["method"] == "DELETE"
    assert any(field["name"] == "client_id" for field in props["form_schema"])


def test_clients_view_superadmin_contract(client):
    _set_auth_override(SimpleNamespace(is_superuser=True, tenants=[], email="admin@test.local"))
    try:
        response = client.get("/clients")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    props = body["components"][0]["properties"]

    assert props["data_url"] == "/clients/data"
    assert props["actions"][0]["action_url"] == "/clients/{id}"
    assert props["actions"][2]["action_url"] == "/clients/{id}/dashboard"
    assert props["header_actions"][0]["action_url"] == "/clients"


def test_clients_view_client_admin_uses_dashboard(monkeypatch, client):
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(
        is_superuser=False,
        email="client-admin@test.local",
        tenants=[SimpleNamespace(client_id=tenant_id, role=SimpleNamespace(slug="client-admin"))],
    )

    captured = {}

    async def _fake_dashboard(client_id, current_user):
        captured["client_id"] = client_id
        captured["email"] = current_user.email
        return {"layout": "dashboard-standard", "components": [{"type": "tabs"}]}

    monkeypatch.setattr(clients_router, "get_client_dashboard", _fake_dashboard)
    _set_auth_override(user)
    try:
        response = client.get("/clients")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    assert captured["client_id"] == tenant_id
    assert captured["email"] == "client-admin@test.local"
    assert response.json()["components"][0]["type"] == "tabs"


def test_system_public_docs_ui_schema_contract(client):
    user = SimpleNamespace(
        is_superuser=False,
        email="admin@datasyncsa.local",
        tenants=[
            SimpleNamespace(
                client_id=uuid.uuid4(),
                client=SimpleNamespace(name="datasyncsa"),
                role=SimpleNamespace(slug="admin"),
            )
        ],
    )
    _set_auth_override(user)
    try:
        response = client.get("/system/public-docs")
    finally:
        _clear_auth_override()

    assert response.status_code == 200
    body = response.json()
    props = body["components"][1]["properties"]
    create_action = props["header_actions"][0]
    delete_action = props["actions"][0]
    access_column = next(col for col in props["columns"] if col["id"] == "access_level")

    assert props["data_url"] == "/system/public-docs/data"
    assert create_action["action_url"] == "/system/public-docs/upload"
    assert delete_action["action_url"] == "/system/public-docs/{content_id}"
    assert access_column["badge_map"] == {"public": "success"}
