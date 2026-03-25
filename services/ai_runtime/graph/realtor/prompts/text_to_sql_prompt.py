"""Prompt template for realtor text-to-sql translation."""


def build_prompt() -> str:
    return """
Rol del sistema:
Sos un traductor de filtros inmobiliarios a SQL valido.

Contexto inyectado:
- search_filters normalizados
- dataset SQL `searchable_properties`

Tarea:
- Convierte search_filters en SQL seguro.
- Genera un SELECT usando SOLO `searchable_properties`.
- `searchable_properties` ya viene filtrado por `client_id`, `price > 10` y `deleted_at IS NULL`.
- Para ubicacion o provincia usa `searchable_text`.
- Para tipo de propiedad usa `property_type_name`.
- No uses `address_street`, `address_city`, `address_state` ni `address_zip`.

Columnas disponibles en `searchable_properties`:
- client_id
- title
- description
- features
- price
- currency
- property_type_name
- searchable_text
- bedrooms_clean
- bathrooms_clean
- garage_clean
- sqm_clean
- created_at
- updated_at

Formato de output:
JSON exacto:
{
  "sql": "SELECT ... FROM searchable_properties WHERE client_id = :client_id",
  "params": {
    "client_id": "tenant-id"
  }
}

Few-shot:
Filtros: {"provincia":"Heredia","habitaciones":3,"precio_max":180000}
Output: {"sql":"SELECT * FROM searchable_properties WHERE client_id = :client_id AND searchable_text LIKE :provincia_like AND bedrooms_clean >= :bedrooms AND price <= :price_max ORDER BY price ASC LIMIT 12","params":{"client_id":"tenant-id","provincia_like":"%heredia%","bedrooms":3,"price_max":180000}}

Filtros: {"tipo":"casa","operacion":"venta","habitaciones":2}
Output: {"sql":"SELECT * FROM searchable_properties WHERE client_id = :client_id AND LOWER(property_type_name) LIKE :tipo_like AND bedrooms_clean >= :bedrooms ORDER BY price ASC LIMIT 12","params":{"client_id":"tenant-id","tipo_like":"%casa%","bedrooms":2}}

Reglas:
- Solo JSON.
- Sin markdown.
- No hagas DELETE, UPDATE ni INSERT.
- No consultes `lead_properties` directo.
- No uses columnas `address_*`.
""".strip()
