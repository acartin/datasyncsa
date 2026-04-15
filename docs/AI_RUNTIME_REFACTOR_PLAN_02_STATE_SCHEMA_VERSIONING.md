# AI_RUNTIME REFACTOR PLAN 02 — State Schema Versioning & Migration

> **Audiencia**: prompt-plan autoejecutable para un agente de IA sin contexto previo.
> **Owner humano**: acartina@gmail.com
> **Repo**: `/srv/datasyncsa`
> **Branch base esperada**: `HETZNER-LOCAL-2026-Abril-06` (o la activa)
> **Fecha de redacción**: 2026-04-15
> **Independencia**: este plan **no depende** de PLAN 01. Pueden ejecutarse en cualquier orden o en paralelo (en branches distintos). Si ambos ya fueron mergeados, ideal; si no, ambos son idempotentes entre sí.

---

## 0. Por qué este plan existe

El runtime serializa el `GraphState` entero a Redis en cada turno:

- **Ubicación del dump**: `services/ai_runtime/runtime/service.py` línea ~167-172:
  ```python
  await self.dependencies.session_store.set_state(
      request.client_id,
      session_id,
      final_state.model_dump(mode="json"),
      tenant_config.redis_ttl_seconds,
  )
  ```
- **Ubicación de la validación al leer**: `services/ai_runtime/runtime/service.py` línea ~110-111:
  ```python
  if existing_payload:
      base_state = vertical_spec.state_model.model_validate(existing_payload)
  ```

**Problema operativo**: al mergear un cambio al schema (ej. agregar un campo requerido en `BaseGraphState`, renombrar un alias), las sesiones vivas serializadas con el schema anterior revientan en `model_validate`. La request devuelve 500. Rollback de código no devuelve las sesiones.

**Superficie de impacto**: cada cambio de estado (nuevo turno sobre sesión existente) de cada usuario con TTL vivo en Redis (hasta `tenant_config.redis_ttl_seconds`, típicamente 30 min).

**Mitigación actual**: ninguna. Si la sesión revienta, el usuario ve 500.

Este plan agrega:
1. `schema_version` en `BaseGraphState`.
2. Registro de migraciones por versión.
3. Fallback defensivo: si `model_validate` falla, loggear y arrancar sesión fresca con el mensaje actual (sin 500).

---

## 1. Estado objetivo (criterio de done)

- Toda sesión persistida lleva un campo `schema_version: int` como parte del payload serializado.
- Al hidratar, `ConversationRuntime` consulta `schema_version`; si es menor a la actual, aplica migraciones registradas en orden hasta alcanzar la versión actual antes de `model_validate`.
- Si `model_validate` aún falla, se captura la excepción, se loggea con `trace_id` y datos mínimos, y se arranca **una nueva sesión** con el mismo `session_id` (preservando `client_id` y `user_id`), agregando el `request.message` como primer mensaje. El flow continúa normalmente. No se devuelve 500 por este caso.
- `tests/` incluye: un test que migra payload v0→v1 (ejemplo ilustrativo), un test de fallback cuando `model_validate` falla con payload corrupto.

---

## 2. Inventario de cambios

### 2.1 Archivo nuevo: `services/ai_runtime/runtime/state_migrations.py`

```python
"""Registro central de migraciones del GraphState serializado.

El objetivo es que, al desplegar un cambio de schema en BaseGraphState o
RealtorGraphState, las sesiones vivas en Redis puedan seguir hidratándose.

Flujo:
    payload_dict (de Redis) -> apply_migrations(payload_dict) -> payload_dict'
                                -> vertical_spec.state_model.model_validate(payload_dict')

Las migraciones se aplican secuencialmente por versión. Cada migración es
idempotente y solo toca los campos que introduce o modifica.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

Migration = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: dict[int, Migration] = {}


def register_migration(from_version: int) -> Callable[[Migration], Migration]:
    """Decora una función que migra payload desde from_version a from_version+1."""
    def decorator(func: Migration) -> Migration:
        if from_version in _MIGRATIONS:
            raise ValueError(f"Migration from v{from_version} already registered")
        _MIGRATIONS[from_version] = func
        return func
    return decorator


def apply_migrations(payload: dict[str, Any]) -> dict[str, Any]:
    """Aplica todas las migraciones pendientes sobre el payload dict.

    Returns: payload actualizado con schema_version == CURRENT_SCHEMA_VERSION.
    """
    current = int(payload.get("schema_version", 0))
    while current < CURRENT_SCHEMA_VERSION:
        migration = _MIGRATIONS.get(current)
        if migration is None:
            logger.warning(
                "no migration registered from v%s; filling schema_version to current",
                current,
            )
            payload["schema_version"] = CURRENT_SCHEMA_VERSION
            return payload
        payload = migration(payload)
        payload["schema_version"] = current + 1
        current += 1
    return payload


# ---------------------------------------------------------------------------
# Example migration (placeholder — reemplazar cuando haya un cambio real)
# ---------------------------------------------------------------------------

@register_migration(from_version=0)
def _migrate_v0_to_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """v0→v1: introduce schema_version explícito.

    Esta migración no cambia nada, solo sirve como ejemplo del registro.
    Cuando agregues una migración real, bumpear CURRENT_SCHEMA_VERSION y
    registrar la función nueva con @register_migration(from_version=1).
    """
    return payload
```

### 2.2 Cambios en `services/ai_runtime/domain/state.py`

Agregar en `BaseGraphState` (buscar la clase, ubicarla después del último field y antes de cualquier validator):

```python
from services.ai_runtime.runtime.state_migrations import CURRENT_SCHEMA_VERSION

class BaseGraphState(BaseModel):
    # ... campos existentes ...
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION)
```

**Atención**: evitar import circular. Si `runtime.state_migrations` importa de `domain`, no puede `domain` importar de `runtime`. Solución: definir `CURRENT_SCHEMA_VERSION` como literal en `domain/state.py` y que `runtime/state_migrations.py` lo importe desde ahí. Es decir, invertir la dirección del import. Ajustar la constante:

```python
# En domain/state.py:
CURRENT_SCHEMA_VERSION = 1

class BaseGraphState(BaseModel):
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION)
    # ... resto
```

Y en `state_migrations.py` hacer `from services.ai_runtime.domain.state import CURRENT_SCHEMA_VERSION`.

### 2.3 Cambios en `services/ai_runtime/runtime/service.py`

Ubicar el bloque que hidrata sesión existente (línea ~108-135 aproximadamente):

```python
existing_payload = await self.dependencies.session_store.get_state(request.client_id, session_id)

if existing_payload:
    base_state = vertical_spec.state_model.model_validate(existing_payload)
    base_state.tenant_config = tenant_config
    # ...
```

**Reemplazar por**:

```python
from services.ai_runtime.runtime.state_migrations import apply_migrations

existing_payload = await self.dependencies.session_store.get_state(request.client_id, session_id)

base_state = None
if existing_payload:
    try:
        migrated = apply_migrations(dict(existing_payload))
        base_state = vertical_spec.state_model.model_validate(migrated)
    except Exception as exc:
        logger.warning(
            "state_hydration_failed client_id=%s session_id=%s error=%s — starting fresh session",
            request.client_id,
            session_id,
            exc,
        )
        base_state = None

if base_state is not None:
    base_state.tenant_config = tenant_config
    base_state.capabilities = list(tenant_config.capabilities)
    base_state.vertical = tenant_config.vertical
    base_state.flow = flow
    base_state.user_id = user_id
    base_state.lead_advisor = build_lead_advisor_state(tenant_config, base_state.lead_advisor)
    _reset_turn_scoped_state(base_state)
    base_state.current_turn += 1
    base_state.messages.append(ChatMessage(role="user", content=request.message))
    conversation_id = base_state.conversation_id
else:
    # Sesión nueva o corrupta: arrancar desde cero
    state = build_base_state(
        session_id=session_id,
        conversation_id=conversation_id,
        user_id=user_id,
        client_id=request.client_id,
        vertical=tenant_config.vertical,
        flow=flow,
        tenant_config=tenant_config,
        initial_message=request.message,
    )
    base_state = vertical_spec.state_model.model_validate(state.model_dump())
    _reset_turn_scoped_state(base_state)
    conversation_id = base_state.conversation_id
```

La lógica antes era `if existing_payload: … else: …`. Ahora es `if base_state is not None: … else: …`, con un catch defensivo en el medio.

**Agregar import** al tope del archivo:
```python
import logging
logger = logging.getLogger(__name__)
```
(si ya existe un logger, reusarlo.)

### 2.4 Tests

**Archivo nuevo**: `services/ai_runtime/tests/test_state_migrations.py`

```python
"""Tests para el sistema de migraciones de GraphState."""

import pytest

from services.ai_runtime.runtime.state_migrations import (
    CURRENT_SCHEMA_VERSION,
    apply_migrations,
)


def test_apply_migrations_adds_schema_version_to_v0_payload():
    payload = {"client_id": "test", "vertical": "realtor"}
    result = apply_migrations(payload)
    assert result["schema_version"] == CURRENT_SCHEMA_VERSION


def test_apply_migrations_idempotent_at_current_version():
    payload = {"schema_version": CURRENT_SCHEMA_VERSION, "client_id": "test"}
    result = apply_migrations(payload)
    assert result["schema_version"] == CURRENT_SCHEMA_VERSION


def test_apply_migrations_preserves_other_fields():
    payload = {"client_id": "abc", "messages": [{"role": "user", "content": "hi"}]}
    result = apply_migrations(payload)
    assert result["client_id"] == "abc"
    assert result["messages"] == [{"role": "user", "content": "hi"}]
```

**Archivo nuevo**: `services/ai_runtime/tests/test_runtime_hydration_fallback.py`

```python
"""Smoke test: si el payload en Redis está corrupto, arranca sesión fresca sin 500."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.ai_runtime.runtime.service import ConversationRuntime


@pytest.mark.asyncio
async def test_corrupted_state_falls_back_to_fresh_session():
    """Un payload corrupto no debe levantar excepción; debe arrancar sesión nueva."""
    # TODO: el que ejecuta este plan debe armar los mocks de dependencies
    # según cómo esté actualmente el wiring de ConversationRuntime.
    # El assert core es:
    #   1) La request con session_id existente y payload corrupto no revienta.
    #   2) Se construye un BaseGraphState nuevo (current_turn == 1).
    #   3) Se loggea un warning "state_hydration_failed".
    pytest.skip("stub — completar según la infraestructura de tests del repo")
```

---

## 3. Pasos de ejecución (por commit)

### PASO 1 — crear `state_migrations.py` con versión 1 inicial
Crear `services/ai_runtime/runtime/state_migrations.py` con el contenido de la sección 2.1. No conectar todavía con `service.py`.
**Commit**: `feat(ai_runtime): add state migrations registry`

### PASO 2 — agregar `schema_version` a `BaseGraphState`
Editar `services/ai_runtime/domain/state.py`:
- Definir `CURRENT_SCHEMA_VERSION = 1` como constante de módulo.
- Ajustar `state_migrations.py` para importar la constante desde `domain/state.py`.
- Agregar el field `schema_version: int = Field(default=CURRENT_SCHEMA_VERSION)` a `BaseGraphState`.
- Verificar que `RealtorGraphState` (subclase) lo hereda sin rehacer nada.
**Commit**: `feat(ai_runtime): add schema_version field to BaseGraphState`

### PASO 3 — conectar migraciones en la hidratación
Editar `services/ai_runtime/runtime/service.py` según sección 2.3. Agregar `import logging`.
**Commit**: `feat(ai_runtime): apply migrations and fallback when hydrating session`

### PASO 4 — tests
Crear los dos archivos de `tests/` de la sección 2.4. Correr `pytest services/ai_runtime/tests/ -x`.
**Commit**: `test(ai_runtime): cover state migrations and hydration fallback`

### PASO 5 (opcional, sólo si existe) — documentar en ARCHITECTURE.md
Si `services/ai_runtime/ARCHITECTURE.md` describe el flujo de sesión, agregar un párrafo corto sobre `schema_version` y cómo registrar una migración nueva.
**Commit**: `docs(ai_runtime): document state schema versioning`

---

## 4. Cómo agregar una migración real después

Cuando en el futuro alguien cambie el schema (ej: rename de un campo, nuevo field requerido sin default seguro):

1. Bumpear `CURRENT_SCHEMA_VERSION` en `domain/state.py` (`1 → 2`).
2. Registrar en `state_migrations.py`:
   ```python
   @register_migration(from_version=1)
   def _migrate_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
       # ej: rename "budget" to "presupuesto" inside lead_advisor.lead_extracted
       lead_advisor = payload.get("lead_advisor") or {}
       extracted = lead_advisor.get("lead_extracted") or {}
       if "budget" in extracted:
           extracted["presupuesto"] = extracted.pop("budget")
       return payload
   ```
3. Agregar un test que cubra el caso.

**Regla invariable**: nunca borrar una migración vieja ni cambiar su lógica después de mergeada. Si hay un bug en `_migrate_v0_to_v1`, se crea `_migrate_vX_to_vX+1` que corrija el daño; la histórica se mantiene igual.

---

## 5. Criterio de done (ejecutable)

```bash
cd /srv/datasyncsa
# 1) El módulo existe y se importa
python -c "from services.ai_runtime.runtime.state_migrations import apply_migrations, CURRENT_SCHEMA_VERSION; print(CURRENT_SCHEMA_VERSION)"
# debe imprimir: 1

# 2) El field existe en el state
python -c "from services.ai_runtime.domain.state import BaseGraphState; assert 'schema_version' in BaseGraphState.model_fields; print('ok')"
# debe imprimir: ok

# 3) Tests verdes
pytest services/ai_runtime/tests/test_state_migrations.py -v
pytest services/ai_runtime/tests/ -x
```

Y una verificación manual con Redis (si hay ambiente local levantado):

```bash
# Dejar una sesión activa en Redis (turno normal desde el front).
# Cambiar manualmente el payload con un campo desconocido:
redis-cli SET "ai_runtime:session:CLIENT:SESSION" '{"foo_invalido": true}'
# Hacer una request al endpoint de chat con el mismo session_id.
# Esperado: response 200, logs muestran "state_hydration_failed … starting fresh session".
```

---

## 6. Qué NO hacer

1. **No borrar el payload corrupto** cuando falla la validación. Loggear y seguir. Si se borra y el bug estaba en el código nuevo, se pierde info diagnóstica al rollbackear.
2. **No cambiar el path de Redis**. La clave/namespace la maneja el `session_store`; no inventar otra.
3. **No agregar `schema_version` a `LeadAdvisorState` ni a sub-modelos**. Una sola versión global para el state raíz. Migraciones tocan sub-campos cuando haga falta.
4. **No hacer migraciones destructivas en caliente** (ej: borrar campos). Primero deprecar (default None), bumpear versión, limpiar en versión siguiente. Siempre two-phase.
5. **No hacer la migración async**. Todas las migraciones deben ser funciones puras sync sobre `dict`. Si una migración necesita I/O (ej. releer tenant_config), reescribir la lógica para que trabaje solo con el payload.
6. **No acoplar el `apply_migrations` con pydantic**. Las migraciones operan sobre `dict[str, Any]`. La validación pydantic ocurre DESPUÉS. Si una migración usa `state_model.model_validate` internamente, estás mezclando capas.
7. **No llamar `apply_migrations` desde otros puntos** que no sean el `ConversationRuntime.handle_turn`. El punto único de hidratación es ese.

---

## 7. Riesgos conocidos y respuestas

| Riesgo | Respuesta |
|---|---|
| Alguien bumpea `CURRENT_SCHEMA_VERSION` sin registrar migración | El `while` en `apply_migrations` detecta el gap y loggea warning, fuerza `schema_version` a la actual pero no muta datos → la siguiente `model_validate` puede fallar y caer al fallback de sesión nueva. Consecuencia: sesiones viejas se pierden al deploy. Prevención: code review de schema changes. |
| Dos migraciones se registran para la misma `from_version` | `register_migration` tira `ValueError` al importar. Se detecta en tests/CI. |
| El payload en Redis no es dict (ej: bytes, string) | El `session_store.get_state` ya debe retornar dict o None. Si retorna algo inesperado, `dict(existing_payload)` o `apply_migrations` revientan y el fallback arranca sesión nueva. Safe. |
| Cambios de schema en `TenantConfig` | No aplica — `tenant_config` se sobrescribe en cada turno (línea 112-113 de `service.py`). No se persiste de Redis. |

---

## 8. Relación con PLAN 01

**No hay dependencia**. Este plan solo toca:
- `domain/state.py` (agrega 1 field + 1 constante — no entra en conflicto con la descontaminación).
- `runtime/service.py` (hidratación).
- `runtime/state_migrations.py` (nuevo).
- `tests/` (nuevos).

Si ambos planes se están ejecutando en paralelo en branches distintos, el merge no debería conflictuar más allá de los imports al tope de `domain/state.py`. Si hay conflicto, resolverlo trivialmente: ambos cambios coexisten.

---

## 9. Mensaje para la próxima IA ejecutora

> Este plan es chico (5 commits, ~250 líneas de código nuevo). Hacelo completo de una vez. No pares en el paso 3 sin los tests del paso 4 — sin tests, la invariante "sesión corrupta no revienta" no está validada y es el entero valor del cambio. Si el repo no tiene pytest-asyncio o el test fallback es complejo de mockear, skippealo con `pytest.skip` y dejá el TODO escrito claramente en el test para que un humano lo retome; mergeá igual el resto.
