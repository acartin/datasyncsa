**AI Vectors Scope**

Fecha de referencia: `2026-03-25`

Este documento resume el criterio vigente para `ai_vectors` mientras estabilizamos el runtime y antes de ajustar el ETL que produce embeddings.

**Fuente de verdad**

- `ai_vectors.client_id` es la frontera tenant principal y obligatoria.
- El runtime debe filtrar por la columna fisica `client_id`, no por `metadata.client_id`.
- `metadata.client_id` puede existir como dato redundante para trazabilidad, pero no es la fuente de verdad para aislamiento.

**Metadata vigente**

Los chunks de `ai_vectors.metadata` deben usar este criterio:

- `category`: clasificacion funcional del contenido.
  Ejemplos: `faq`, `financial`, `properties`, `publico`.
- `scope_type`: alcance logico del chunk.
  Valor soportado hoy: `tenant`.
- `ingested_at`, `embedding_model`, `embedding_dimension`, `source_timestamp`, `url`:
  metadatos operativos permitidos.

**Criterios acordados**

- No usar `vertical_slug` en `metadata`.
  Motivo: agrega riesgo de inconsistencias derivables desde el tenant y el pipeline.
- No usar `access_level` por ahora.
  Quedaba ambiguo y mezclaba semanticas distintas.
- Para los datos actuales de prueba, todos los vectores existentes quedan con:
  - `scope_type = tenant`
  - `category = faq`

**Semantica actual**

- `scope_type = tenant`
  significa que el chunk solo aplica al tenant identificado por la columna `client_id`.

**Semantica aun no definida**

Todavia no debemos inventar reglas de consumo para estos casos hasta acordarlas formalmente:

- `scope_type = global`
- categorias nuevas con comportamiento especial
- reutilizacion transversal entre tenants

Si en el futuro aparece contenido comun para multiples tenants, debemos definir primero:

- valores permitidos de `scope_type`
- reglas exactas de query
- precedencia entre contenido tenant y contenido compartido

**Impacto para ETL**

Cuando se ajuste el ETL que genera `ai_vectors`, debe cumplir este contrato:

- escribir `client_id` en la columna fisica
- escribir `category` en `metadata`
- escribir `scope_type` en `metadata`
- no escribir `vertical_slug`
- no escribir `access_level`

**Nota operativa**

El runtime conversacional actual todavia necesita ser alineado al schema real de `ai_vectors`:

- el texto del chunk vive en `body_content`
- el titulo vive en `title`
- la clasificacion funcional vive en `metadata.category`

Ese ajuste del runtime y del ETL queda como siguiente paso.
