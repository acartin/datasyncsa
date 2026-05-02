#!/usr/bin/env python3
"""Configuracion local de tiendas, categorias y salidas para price-scrapper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config" / "stores"
SCHEMAS_DIR = SCRIPT_DIR / "schemas"


def normalize_ean(value: Any) -> str | None:
    """Normaliza un EAN/UPC al formato canonico EAN-13.

    Acepta strings, listas (toma el primer no vacio) o None. Si el valor solo
    contiene digitos y mide 11 o 12 caracteres, izquierda-pad con ceros hasta 13
    para resolver el caso UPC-A almacenado sin el cero EAN-13. Largos 8 (UPC-E)
    y 13 se devuelven como llegan; cualquier otro valor (no numerico o longitud
    rara) tambien.
    """
    if value is None:
        return None
    if isinstance(value, list):
        for entry in value:
            normalized = normalize_ean(entry)
            if normalized:
                return normalized
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() and len(text) in (11, 12):
        return text.zfill(13)
    return text


@dataclass(frozen=True)
class StoreDefinition:
    store_id: str
    display_name: str
    short_label: str
    catalog_id: str
    base_url: str
    default_output_dir: Path
    default_enabled_root_slugs: tuple[str, ...] = ("abarrotes",)
    pricing_scope: str = "chain_public_online"
    engine: str = "vtex"
    extras: dict[str, Any] | None = None

    @property
    def category_config_path(self) -> Path:
        return CONFIG_DIR / f"{self.store_id}.json"

    @property
    def default_output_dir_relative(self) -> str:
        return str(self.default_output_dir.relative_to(SCRIPT_DIR))

    @property
    def pricing_context(self) -> dict[str, Any]:
        if self.engine == "instaleap":
            store_reference = (self.extras or {}).get("store_reference")
            return {
                "uses_selected_store": True,
                "uses_postal_code": False,
                "uses_access_control_list": False,
                "store_reference": store_reference,
                "description": (
                    "Consulta publica al endpoint Instaleap (nextgentheadless) con la tienda "
                    f"por defecto {store_reference!r} que el sitio asigna a usuarios anonimos."
                ),
            }
        if self.engine == "vtex":
            extras = self.extras or {}
            sales_channel = extras.get("sales_channel")
            region_id = extras.get("region_id")
            if sales_channel:
                return {
                    "uses_selected_store": True,
                    "uses_postal_code": False,
                    "uses_access_control_list": False,
                    "sales_channel": str(sales_channel),
                    "region_id": region_id,
                    "description": (
                        "Consulta a VTEX productSearchV3 con vtex_segment.channel="
                        f"{sales_channel} y region-id "
                        f"{region_id!r}. Replica el sales channel que el frontend de la "
                        "cadena activa para visitantes CR sin login, asegurando que el "
                        "precio coincida con el que ve el usuario al abrir el producto."
                    ),
                }
        return {
            "uses_selected_store": False,
            "uses_postal_code": False,
            "uses_access_control_list": False,
            "description": (
                "Consulta publica de VTEX productSearchV3 sin seleccionar tienda fisica, "
                "codigo postal ni contexto logistico local."
            ),
        }


STORE_DEFINITIONS = {
    "walmart_cr": StoreDefinition(
        store_id="walmart_cr",
        display_name="Walmart Costa Rica",
        short_label="Walmart",
        catalog_id="walmart_cr_catalog",
        base_url="https://www.walmart.co.cr",
        default_output_dir=SCRIPT_DIR / "output" / "walmart_cr_abarrotes",
    ),
    "maxi_pali_cr": StoreDefinition(
        store_id="maxi_pali_cr",
        display_name="Maxi Palí Costa Rica",
        short_label="Maxi Palí",
        catalog_id="maxi_pali_cr_catalog",
        base_url="https://www.maxipali.co.cr",
        default_output_dir=SCRIPT_DIR / "output" / "maxi_pali_abarrotes",
    ),
    "masxmenos_cr": StoreDefinition(
        store_id="masxmenos_cr",
        display_name="Más x Menos Costa Rica",
        short_label="Más x Menos",
        catalog_id="masxmenos_cr_catalog",
        base_url="https://www.masxmenos.cr",
        default_output_dir=SCRIPT_DIR / "output" / "masxmenos_cr_abarrotes",
    ),
    "megasuper_cr": StoreDefinition(
        store_id="megasuper_cr",
        display_name="Megasuper Costa Rica",
        short_label="Megasuper",
        catalog_id="megasuper_cr_catalog",
        base_url="https://www.megasuper.com",
        default_output_dir=SCRIPT_DIR / "output" / "megasuper_cr_abarrotes",
        default_enabled_root_slugs=("abarrotes",),
        pricing_scope="default_store_online",
        engine="instaleap",
        extras={
            "client_id": "MEGASUPER",
            "store_reference": "M102",
            "store_internal_id": "3645",
            "graphql_endpoint": "https://nextgentheadless.instaleap.io/api/v3",
            "currency": "CRC",
            "locale": "es-CR",
        },
    ),
}


def get_store_definition(store_id: str) -> StoreDefinition:
    try:
        return STORE_DEFINITIONS[store_id]
    except KeyError as exc:
        known = ", ".join(sorted(STORE_DEFINITIONS))
        raise KeyError(f"Tienda desconocida {store_id!r}. Disponibles: {known}") from exc


def iter_store_definitions() -> list[StoreDefinition]:
    return [STORE_DEFINITIONS[key] for key in sorted(STORE_DEFINITIONS)]


def seed_store_config_payload(
    definition: StoreDefinition,
    *,
    categories: list[dict[str, Any]],
    existing_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing_categories = {
        str(category.get("slug") or "").strip(): category
        for category in (existing_payload or {}).get("categories") or []
        if str(category.get("slug") or "").strip()
    }

    payload_categories: list[dict[str, Any]] = []
    for category in categories:
        slug = str(category.get("slug") or "").strip()
        if not slug:
            continue

        existing = existing_categories.get(slug, {})
        enabled = existing.get("enabled")
        if enabled is None:
            enabled = slug in definition.default_enabled_root_slugs

        payload_categories.append(
            {
                "name": category.get("name") or slug,
                "slug": slug,
                "url": category.get("url"),
                "enabled": bool(enabled),
            }
        )

    payload_categories.sort(key=lambda item: str(item["name"]).casefold())

    payload: dict[str, Any] = {
        "schema_version": "store_category_config_v1",
        "store_id": definition.store_id,
        "display_name": definition.display_name,
        "short_label": definition.short_label,
        "catalog_id": definition.catalog_id,
        "base_url": definition.base_url,
        "default_output_dir": definition.default_output_dir_relative,
        "engine": definition.engine,
        "pricing_scope": definition.pricing_scope,
        "pricing_context": definition.pricing_context,
        "categories": payload_categories,
    }
    if definition.extras:
        payload["engine_extras"] = dict(definition.extras)
    return payload


def load_store_config(store_id: str) -> dict[str, Any]:
    definition = get_store_definition(store_id)
    path = definition.category_config_path
    if not path.exists():
        raise FileNotFoundError(
            f"No existe la config de categorias para {store_id!r} en {path}. "
            "Ejecuta refresh_store_categories.py primero."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_store_config(store_id: str, payload: dict[str, Any]) -> Path:
    definition = get_store_definition(store_id)
    path = definition.category_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def enabled_root_categories(payload: dict[str, Any]) -> list[dict[str, Any]]:
    categories = payload.get("categories") or []
    return [category for category in categories if category.get("enabled")]


def resolve_output_dir(payload: dict[str, Any], definition: StoreDefinition) -> Path:
    raw_value = payload.get("default_output_dir") or definition.default_output_dir_relative
    output_dir = Path(str(raw_value))
    if output_dir.is_absolute():
        return output_dir
    return SCRIPT_DIR / output_dir
