import base64
import json
from typing import Any, Dict


def encode_schema_b64(schema: list[dict]) -> str:
    return base64.b64encode(json.dumps(schema).encode()).decode()


def edit_action(action_url: str, schema_b64: str, label: str = "Editar") -> Dict[str, Any]:
    return {
        "label": label,
        "icon": "ri-pencil-line",
        "action": "edit",
        "action_url": action_url,
        "schema": schema_b64,
    }


def delete_action(action_url: str, label: str = "Eliminar") -> Dict[str, Any]:
    return {
        "label": label,
        "icon": "ri-delete-bin-line",
        "action": "delete",
        "action_url": action_url,
        "color": "danger",
    }


def create_modal_action(
    action_url: str,
    schema_b64: str,
    modal_title: str,
    label: str,
    icon: str = "ri-add-line",
) -> Dict[str, Any]:
    return {
        "label": label,
        "action": "modal-form",
        "action_url": action_url,
        "modal_title": modal_title,
        "color": "success",
        "icon": icon,
        "schema": schema_b64,
    }
