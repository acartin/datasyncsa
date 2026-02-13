import base64
import json

from app.modules.shared.sdui import create_modal_action, delete_action, edit_action, encode_schema_b64


def test_encode_schema_b64_roundtrip():
    schema = [
        {"name": "name", "label": "Nombre", "type": "text", "required": True},
        {"name": "active", "label": "Activo", "type": "checkbox", "required": False},
    ]

    encoded = encode_schema_b64(schema)
    decoded = json.loads(base64.b64decode(encoded).decode())

    assert decoded == schema


def test_edit_action_contract_shape():
    action = edit_action("/system/users/{id}", "Zm9v")

    assert action["action"] == "edit"
    assert action["action_url"] == "/system/users/{id}"
    assert action["schema"] == "Zm9v"
    assert action["label"] == "Editar"
    assert action["icon"] == "ri-pencil-line"


def test_delete_action_contract_shape():
    action = delete_action("/system/users/{id}")

    assert action["action"] == "delete"
    assert action["action_url"] == "/system/users/{id}"
    assert action["label"] == "Eliminar"
    assert action["icon"] == "ri-delete-bin-line"
    assert action["color"] == "danger"


def test_create_modal_action_contract_shape():
    action = create_modal_action(
        action_url="/system/users",
        schema_b64="YmFy",
        modal_title="Crear Usuario",
        label="Nuevo Usuario",
        icon="ri-user-add-line",
    )

    assert action["action"] == "modal-form"
    assert action["action_url"] == "/system/users"
    assert action["schema"] == "YmFy"
    assert action["modal_title"] == "Crear Usuario"
    assert action["label"] == "Nuevo Usuario"
    assert action["color"] == "success"
    assert action["icon"] == "ri-user-add-line"
