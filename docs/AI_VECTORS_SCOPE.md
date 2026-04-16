# AI Vectors Scope

Fecha de referencia: `2026-04-16`

Este documento resume el estado real de `ai_vectors` consumido hoy por `ai-runtime` y escrito por `etl-docs`.

## Fuente de verdad

- `ai_vectors.client_id` es la frontera tenant principal y obligatoria.
- El runtime filtra por la columna física `client_id`, no por `metadata.client_id`.
- `metadata.client_id` puede existir por trazabilidad, pero no participa en el aislamiento operativo.

## Lectura actual del runtime

El runtime ya está alineado con el schema real de `ai_vectors`:

- el texto del chunk vive en `body_content`
- el título vive en `title`
- la clasificación funcional vive en `metadata.category`
- el alcance lógico vive en `metadata.scope_type`

Esto está implementado en:

- [services/ai_runtime/rag/agency/repository.py](/srv/datasyncsa/services/ai_runtime/rag/agency/repository.py:38)
- [services/ai_runtime/rag/documents/repository.py](/srv/datasyncsa/services/ai_runtime/rag/documents/repository.py:42)

## Filtros vigentes

### FAQ de agencia

El runtime consulta solo chunks con:

- `client_id = tenant`
- `metadata.scope_type = tenant`
- `metadata.category = faq`

### Documentos

El runtime consulta solo chunks con:

- `client_id = tenant`
- `metadata.scope_type = tenant`
- `metadata.category IN ('documentos', 'financial', 'financiero', 'properties', 'propiedades', 'publico', 'public')`

## Metadata tolerada hoy

Campos que el runtime sí usa:

- `category`
- `scope_type`

Campos operativos tolerados:

- `ingested_at`
- `embedding_model`
- `embedding_dimension`
- `source_timestamp`
- `url`
- `client_id` redundante

Campos que el runtime hoy ignora:

- `access_level`
- `vertical_slug`
- cualquier otro extra que llegue en `metadata`

## Estado real del ETL

`etl-docs` sigue serializando `CanonicalMetadata` dentro de `metadata`, y hoy eso incluye `access_level`:

- [services/etl-docs/src/shared/schemas.py](/srv/datasyncsa/services/etl-docs/src/shared/schemas.py:34)
- [services/etl-docs/src/shared/vector_store.py](/srv/datasyncsa/services/etl-docs/src/shared/vector_store.py:146)

Entonces, el estado actual no es “sin `access_level`”, sino:

- el ETL todavía lo escribe
- el runtime no lo consume
- no hay semántica activa en `ai-runtime` basada en `access_level`

## Criterio recomendado

- Mantener `client_id` como única frontera tenant obligatoria.
- Mantener `scope_type = tenant` como único alcance soportado hoy por el runtime.
- Evitar depender de `vertical_slug` o `access_level` en consultas del runtime hasta que exista un contrato formal y transversal.

## Semántica aún no definida

Todavía no debemos inventar reglas de consumo para:

- `scope_type = global`
- precedencia entre contenido tenant y compartido
- semántica operativa de `access_level`
- categorías con comportamiento especial fuera de las listas ya usadas por el runtime
