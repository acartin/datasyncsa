# AI_RUNTIME REFACTOR PLAN 01 — Domain/Shared Decontamination

> **Audiencia**: este documento es un prompt-plan autoejecutable para un agente de IA (Claude/GPT/otro) que va a tomar el refactor sin contexto previo de la sesión que lo escribió. Leelo completo antes de tocar nada.
>
> **Owner humano**: acartina@gmail.com
> **Repo**: `/srv/datasyncsa`
> **Branch base esperada**: `HETZNER-LOCAL-2026-Abril-06` (o la branch activa de trabajo)
> **Fecha de redacción**: 2026-04-15

---

## 0. Contexto mínimo — leé esto antes de ejecutar

`services/ai_runtime/` es un runtime LangGraph multi-vertical. Verticales soportados: `realtor`, `healthcare`, `legal`, `insurance`. Hoy sólo `realtor` tiene un grafo propio (`graph/realtor/`); los otros 3 comparten `graph/generic/`.

**Un refactor previo declaró** (vía docstrings) que:
- `domain/` debe ser agnóstico de vertical.
- Los contratos/ports/turn-frame realtor viven en `graph/realtor/`.

**La declaración no se ejecutó por completo**. Hay contaminación realtor en `domain/` y en `graph/_shared/`. Este plan la termina.

### Regla de oro

> Al final del refactor, `grep -r "realtor\|Realtor\|Property\|presupuesto\|aprobacion" services/ai_runtime/domain services/ai_runtime/graph/_shared` **no debe arrojar imports ni tipos realtor**. Solo strings de tenant-config o constantes genéricas pueden quedar.

---

## 1. Inventario exacto de contaminación (auditoría 2026-04-15)

### 1.1 `domain/contracts.py`
- Línea 153-154: `LeadExtracted.presupuesto` (float), `LeadExtracted.aprobacion` (str). Campos realtor-only.
- Docstring de cabecera (línea 4) dice que realtor no debe leakear aquí → contradicción interna.

### 1.2 `domain/turn_frame.py`
- Línea 80-81: `LeadSnapshot.presupuesto`, `LeadSnapshot.aprobacion`. Idem realtor-only.

### 1.3 `domain/state.py`
- Líneas 44-50: `SCORING_FIELD_ALIASES` mapea alias a `presupuesto`/`aprobacion`.
- Líneas 306-309: `_field_has_value()` tiene ramas `elif key == "presupuesto"` / `elif key == "aprobacion"`.

### 1.4 `domain/ports.py`
- Línea 25 (bajo `TYPE_CHECKING`): `from services.ai_runtime.graph.realtor.ports import PropertyRepositoryPort`.
- Línea 150: `GraphDependencies.property_repository: "PropertyRepositoryPort"` — port vertical como dependencia obligatoria del contenedor agnóstico.

### 1.5 `graph/_shared/nodes/analyze_turn_node.py`
- Líneas 17-22: imports directos de `Property`, `RealtorGraphState`, `SearchFilters`, `apply_realtor_turn_policies`, `merge_realtor_filters`, `REALTOR_INTERNAL_INTENTS`, `build_realtor_fallback_intent_plan`, `derive_realtor_pending_decision`.
- Línea 152, 158: `if isinstance(graph_state, RealtorGraphState):` + fallback a funciones realtor.
- Línea 257-260: ramificación `RealtorGraphState.model_validate(state) if state["vertical"] == "realtor" else BaseGraphState.model_validate(state)`.
- Línea 336-337: `apply_realtor_turn_policies(graph_state, analysis)`.
- Línea 369-372: rama especial `merge_realtor_filters` para `new_search/refine_search`.

### 1.6 `graph/_shared/nodes/synthesize_node.py`
- Líneas 17-18: imports `RealtorGraphState`, `RealtorTurnFrame`.
- Línea 146-147, 160: `if state.get("vertical") == "realtor":` + `isinstance(graph_state, RealtorGraphState)`.

### 1.7 `graph/_shared/nodes/prepare_synthesis_node.py`
- Línea 14: import `RealtorGraphState`.
- Línea 29-30: rama `if state.get("vertical") == "realtor":`.

### 1.8 `graph/_shared/nodes/lead_advisor_node.py`
- Línea 14: import `RealtorGraphState`.
- Línea 105: `if isinstance(graph_state, RealtorGraphState) and payload.get("presupuesto") is None:` — pull de `search_filters.precio_max` realtor.

### 1.9 `graph/_shared/turn_frame_builder.py`
- Líneas 26-28: imports `Property`, `RealtorGraphState`, `RealtorTurnFrame`.
- Función `_resolve_visible_properties(graph_state: RealtorGraphState)` (línea 72).
- Función `_resolve_search_context(graph_state: RealtorGraphState)` (línea 142).
- Línea 343: `Property.model_validate(prop_data)`.
- Línea 461, 498: chequeo de `isinstance(graph_state, RealtorGraphState)` y firma tipada.

### 1.10 `graph/_shared/scoring_hybrid.py`
- Línea 21: import `RealtorGraphState`.
- Línea 389: `isinstance(graph_state, RealtorGraphState)` y payload realtor-only.

### 1.11 `config/` (contaminación secundaria, no-bloqueante)
- `config/geo_catalog.py`, `config/property_type_catalog.py`: datos realtor en carpeta compartida. **Se mueven al final del plan.**

---

## 2. Arquitectura objetivo

```
services/ai_runtime/
├── domain/
│   ├── contracts.py        ← LeadExtracted / LeadSnapshot base SIN campos realtor
│   ├── state.py            ← _field_has_value delega a policy
│   ├── ports.py            ← GraphDependencies SIN property_repository
│   └── turn_frame.py       ← BaseTurnFrame sin LeadSnapshot realtor
├── graph/
│   ├── _shared/
│   │   └── nodes/          ← CERO imports de graph.realtor.*
│   ├── realtor/
│   │   ├── contracts.py    ← RealtorLeadExtracted extiende LeadExtracted
│   │   ├── turn_frame.py   ← RealtorLeadSnapshot extiende LeadSnapshot
│   │   ├── policies.py     ← NUEVO: VerticalPolicy concreto para realtor
│   │   ├── ports.py        ← PropertyRepositoryPort (ya existe)
│   │   └── state/model.py  ← RealtorGraphState usa RealtorLeadExtracted
│   └── generic/
│       └── policies.py     ← NUEVO: VerticalPolicy null/genérico
└── verticals.py            ← VerticalSpec suma campo `policy: VerticalPolicy`
```

### 2.1 Contrato nuevo `VerticalPolicy` (agnóstico)

Crear **`services/ai_runtime/domain/policies.py`**:

```python
"""Vertical policy protocol: injection hook para comportamiento per-vertical."""
from __future__ import annotations

from typing import Any, Protocol

from services.ai_runtime.domain.contracts import TurnAnalysis
from services.ai_runtime.domain.state import BaseGraphState


class VerticalPolicy(Protocol):
    """Policies inyectadas por VerticalSpec para que _shared no conozca verticales."""

    async def merge_filters(
        self, graph_state: BaseGraphState, analysis: TurnAnalysis, deps: Any
    ) -> dict[str, Any] | None:
        """Devuelve filtros mergeados para new_search/refine_search, o None si no aplica."""
        ...

    def apply_turn_policies(
        self, graph_state: BaseGraphState, analysis: TurnAnalysis
    ) -> tuple[TurnAnalysis, list[str]]:
        """Devuelve (analysis normalizado, compare_target_ids). compare_target_ids vacío si no aplica."""
        ...

    def derive_pending_decision(
        self, graph_state: BaseGraphState, analysis: TurnAnalysis
    ) -> Any | None:
        """Devuelve PendingDecision o None."""
        ...

    def build_fallback_intent_plan(
        self, graph_state: BaseGraphState, analysis: TurnAnalysis
    ) -> list[Any]:
        """Fallback IntentPlanItem list si analysis.intent_plan está vacío."""
        ...

    def internal_intents(self) -> set[str]:
        """Intents internos permitidos además de tenant_config.capabilities."""
        ...

    def field_has_value(self, extracted: Any, field_key: str) -> bool | None:
        """True/False si la policy sabe validar el field, None si delega al shared."""
        ...

    def extra_lead_sync(
        self, graph_state: BaseGraphState, lead_payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Sync extra de campos vertical-specific al lead_extracted. Muta y devuelve."""
        ...


class NullVerticalPolicy:
    """Implementación no-op para verticales sin comportamiento especial (generic)."""

    async def merge_filters(self, graph_state, analysis, deps):
        return None

    def apply_turn_policies(self, graph_state, analysis):
        return analysis, []

    def derive_pending_decision(self, graph_state, analysis):
        return None

    def build_fallback_intent_plan(self, graph_state, analysis):
        return []

    def internal_intents(self):
        return set()

    def field_has_value(self, extracted, field_key):
        return None

    def extra_lead_sync(self, graph_state, lead_payload):
        return lead_payload
```

### 2.2 `VerticalSpec` con campo `policy`

Editar **`services/ai_runtime/verticals.py`**:
- Agregar `policy: VerticalPolicy = field(default_factory=NullVerticalPolicy)` al dataclass.
- En el spec `"realtor"` setear `policy=RealtorPolicy()`.
- En `"healthcare"`, `"legal"`, `"insurance"` dejar `NullVerticalPolicy()` (default).

---

## 3. Plan de ejecución — pasos exactos

Cada paso es un commit. No agrupar. Verificar tests después de cada paso.

### PASO 1 — Extender contratos realtor

**Archivo**: `services/ai_runtime/graph/realtor/contracts.py`
**Cambio**:
1. Agregar clase `RealtorLeadExtracted(LeadExtracted)` con los campos realtor:
   ```python
   from services.ai_runtime.domain.contracts import LeadExtracted

   class RealtorLeadExtracted(LeadExtracted):
       presupuesto: float | None = None
       aprobacion: str | None = None
   ```
2. Exportar `RealtorLeadExtracted` vía `__all__` o import-star.

**Archivo**: `services/ai_runtime/graph/realtor/turn_frame.py`
**Cambio**:
1. Crear `RealtorLeadSnapshot(LeadSnapshot)` con `presupuesto: float | None` y `aprobacion: str | None`.
2. Cambiar `RealtorTurnFrame.lead_snapshot` (o el campo equivalente) para usar `RealtorLeadSnapshot`.

**Verificación**: `python -c "from services.ai_runtime.graph.realtor.contracts import RealtorLeadExtracted"` debe funcionar.

---

### PASO 2 — Limpiar `domain/contracts.py` y `domain/turn_frame.py`

**Archivo**: `services/ai_runtime/domain/contracts.py`
**Cambio**: borrar líneas 153-154 (`presupuesto`, `aprobacion` de `LeadExtracted`).

**Archivo**: `services/ai_runtime/domain/turn_frame.py`
**Cambio**: borrar líneas 80-81 (`presupuesto`, `aprobacion` de `LeadSnapshot`).

**Archivo**: `services/ai_runtime/graph/realtor/state/model.py`
**Cambio**:
- Localizar donde `LeadAdvisorState.lead_extracted: LeadExtracted` se usa dentro de `RealtorGraphState`. Reemplazar con `RealtorLeadExtracted`.
- Si `RealtorGraphState` no override-a el campo, agregar override tipado: `lead_extracted: RealtorLeadExtracted = Field(default_factory=RealtorLeadExtracted)`.

**Verificación**:
- `grep -n "presupuesto\|aprobacion" services/ai_runtime/domain/` debe devolver 0 matches.
- `pytest services/ai_runtime/tests/ -x` debe pasar.

---

### PASO 3 — Mover helpers de `_field_has_value` realtor a la policy

**Archivo**: `services/ai_runtime/domain/state.py`
**Cambio en `_field_has_value` (línea ~296-319)**:
Eliminar ramas `presupuesto` y `aprobacion`. Después la función queda:

```python
def _field_has_value(extracted: LeadExtracted, field_key: str, policy=None) -> bool:
    key = _normalize_field_key(field_key)
    if policy is not None:
        policy_result = policy.field_has_value(extracted, key)
        if policy_result is not None:
            return policy_result
    if key == "contacto":
        return has_valid_lead_contact(extracted)
    # ... resto sin ramas realtor
```

**Archivo nuevo**: `services/ai_runtime/graph/realtor/policies.py`
**Cambio**: crear `RealtorPolicy` que implementa `VerticalPolicy`. Su `field_has_value` retorna:

```python
def field_has_value(self, extracted, field_key):
    if field_key == "presupuesto":
        return getattr(extracted, "presupuesto", None) is not None
    if field_key == "aprobacion":
        return bool(getattr(extracted, "aprobacion", None))
    return None
```

**Verificación**: tests que tocan lead-advisor con realtor siguen verdes.

---

### PASO 4 — Mover `SCORING_FIELD_ALIASES` alias realtor a la policy

**Archivo**: `services/ai_runtime/domain/state.py`
**Cambio**: borrar entradas realtor-específicas de `SCORING_FIELD_ALIASES` (presupuesto, extracted_approval, extracted_budget, budget, timeline para presupuesto, etc.).

**Archivo**: `services/ai_runtime/graph/realtor/policies.py`
**Cambio**: exponer `RealtorPolicy.scoring_field_aliases: dict[str, str]` con los alias realtor. El lead-advisor shared debe pedirle los alias a la policy y fusionar con los del domain.

**Atención**: los alias genéricos (`name → nombre`, `email`, `phone → telefono`) se quedan en `domain/state.py`. Sólo lo específicamente realtor se va.

---

### PASO 5 — Sacar `PropertyRepositoryPort` de `GraphDependencies`

**Archivo**: `services/ai_runtime/domain/ports.py`
**Cambio**:
1. Eliminar líneas 24-25 (el `TYPE_CHECKING` import de `PropertyRepositoryPort`).
2. Eliminar línea 150 (`property_repository: "PropertyRepositoryPort"`).
3. Agregar `vertical_extras: dict[str, Any] = field(default_factory=dict)` al dataclass `GraphDependencies`.

**Archivo**: `services/ai_runtime/runtime/bootstrap.py`
**Cambio**: en vez de pasar `property_repository=...` al `GraphDependencies`, armar:
```python
vertical_extras = {
    "realtor": {"property_repository": PropertyRepositoryAdapter(...)},
}
GraphDependencies(..., vertical_extras=vertical_extras)
```

**Archivo**: todos los consumidores de `deps.property_repository` dentro de `graph/realtor/`
**Cambio**: reemplazar `deps.property_repository` por `deps.vertical_extras["realtor"]["property_repository"]`. Crear helper `_get_property_repo(deps)` en `graph/realtor/` para centralizar la lookup.

**Ubicaciones típicas a actualizar** (verificar con grep antes):
- `graph/realtor/nodes/search_node.py`
- `graph/realtor/nodes/focus_property_node.py`
- `graph/realtor/nodes/compare_properties_node.py`
- cualquier otro nodo realtor que accede properties.

**Verificación**:
- `grep -r "property_repository" services/ai_runtime/domain/` → 0 matches.
- `grep -r "deps\.property_repository" services/ai_runtime/graph/_shared/` → 0 matches.
- Integration test realtor sigue verde.

---

### PASO 6 — Refactorizar `analyze_turn_node.py` para usar policy

**Archivo**: `services/ai_runtime/graph/_shared/nodes/analyze_turn_node.py`

**Cambios**:

1. **Imports**: borrar las líneas 17-22 (`Property`, `RealtorGraphState`, `SearchFilters`, `apply_realtor_turn_policies`, `merge_realtor_filters`, `REALTOR_INTERNAL_INTENTS`, `build_realtor_fallback_intent_plan`, `derive_realtor_pending_decision`).

2. **Resolver policy**: al inicio de `analyze_turn()`, después de validar state:
   ```python
   from services.ai_runtime.verticals import get_vertical_spec
   spec = get_vertical_spec(graph_state.vertical)
   policy = spec.policy
   ```

3. **`_internal_intents_for_state`** (línea 157-160): reemplazar el `isinstance(RealtorGraphState)` por:
   ```python
   def _internal_intents_for_state(graph_state: BaseGraphState, policy) -> set[str]:
       return policy.internal_intents()
   ```

4. **`_fallback_intent_plan`** (línea 131-154): último return `if isinstance(graph_state, RealtorGraphState): return build_realtor_fallback_intent_plan(...)` → reemplazar por `return policy.build_fallback_intent_plan(graph_state, analysis)`.

5. **Validación del state** (líneas 256-260): ya no se ramifica por vertical. Reemplazar por:
   ```python
   graph_state = spec.state_model.model_validate(state)
   ```
   Usar el `state_model` del VerticalSpec en lugar de hard-code realtor.

6. **`apply_realtor_turn_policies`** (líneas 336-337): reemplazar por `analysis, compare_target_ids = policy.apply_turn_policies(graph_state, analysis)`.

7. **`derive_realtor_pending_decision`** (línea 338): reemplazar por `pending_decision = policy.derive_pending_decision(graph_state, analysis)`.

8. **`merge_realtor_filters`** (línea 369-372): reemplazar por:
   ```python
   if analysis.dialogue_act in {"new_search", "refine_search"}:
       merged = await policy.merge_filters(graph_state, analysis, deps)
       if merged is not None:
           updates["search_filters"] = merged
           if any(intent.get("type") == "buscar" for intent in updates["intent_queue"]):
               updates["search_attempts"] = 0
   ```

9. **`_visible_reference_items`** y cualquier uso de `Property.model_validate`: estos helpers usan `Property` para resolver referencias. **No mover `Property`** — delegar a la policy vía un método `resolve_reference(graph_state, decision) -> list[dict]`. Agregar ese método al protocol `VerticalPolicy` y a `RealtorPolicy` (que sí importa `Property`). El `NullVerticalPolicy` devuelve `[]`.

   El bloque 86-128 (`_resolve_reference` + `_select_reference_candidate` + `_visible_reference_items`) se mueve a `graph/realtor/policies.py`.

**Verificación**:
- `grep -n "realtor\|Realtor\|Property" services/ai_runtime/graph/_shared/nodes/analyze_turn_node.py` → 0 matches.
- `pytest -k analyze_turn` verde.

---

### PASO 7 — Refactorizar `synthesize_node.py`

**Archivo**: `services/ai_runtime/graph/_shared/nodes/synthesize_node.py`

**Cambios**:
1. Borrar imports de `RealtorGraphState`, `RealtorTurnFrame` (líneas 17-18).
2. Línea 146-147 y 160: reemplazar el switch por el `state_model` del `VerticalSpec`:
   ```python
   spec = get_vertical_spec(state.get("vertical"))
   graph_state = spec.state_model.model_validate(state)
   ```
3. Si el nodo necesitaba construir `RealtorTurnFrame` — ese turn-frame concreto lo arma `prepare_synthesis` (no `synthesize`). Acá sólo se lee. Si lee `turn_frame` desde `state["turn_frame"]`, validar con el TypedFrame correspondiente vía policy: `policy.turn_frame_model` o usar `BaseTurnFrame` polimorficamente.

**Regla**: el `synthesize` no debe saber si es realtor. Recibe `turn_frame` ya construido como `dict` + vertical; la deserialización la hace la policy si necesita campos específicos.

---

### PASO 8 — Refactorizar `prepare_synthesis_node.py`

**Archivo**: `services/ai_runtime/graph/_shared/nodes/prepare_synthesis_node.py`

**Cambios**:
1. Borrar import de `RealtorGraphState` (línea 14).
2. Usar `spec.state_model.model_validate(state)` en vez del `if vertical == "realtor"`.
3. `build_turn_frame(graph_state)` en el shared builder ya debería ser polimórfico tras PASO 9.

---

### PASO 9 — Refactorizar `turn_frame_builder.py`

**Archivo**: `services/ai_runtime/graph/_shared/turn_frame_builder.py`

**Cambios**:
1. Borrar imports de `Property`, `RealtorGraphState`, `RealtorTurnFrame` (líneas 26-28).
2. Las funciones `_resolve_visible_properties` y `_resolve_search_context` son realtor-puras → moverlas **enteras** a `graph/realtor/turn_frame_builder.py` (archivo nuevo).
3. En `graph/realtor/policies.py` agregar método `build_turn_frame_extras(graph_state) -> dict[str, Any]` que invoca los helpers movidos y devuelve los campos realtor (`visible_properties`, `search_context`, `seen_properties`).
4. El `build_turn_frame` shared termina así:
   ```python
   def build_turn_frame(graph_state: BaseGraphState) -> BaseTurnFrame:
       base_data = {...}  # campos agnósticos
       spec = get_vertical_spec(graph_state.vertical)
       extras = spec.policy.build_turn_frame_extras(graph_state)
       frame_model = spec.turn_frame_model or BaseTurnFrame
       return frame_model.model_validate({**base_data, **extras})
   ```
5. Agregar `turn_frame_model: type[BaseTurnFrame] = BaseTurnFrame` al `VerticalSpec`. Realtor setea `turn_frame_model=RealtorTurnFrame`.

**Verificación**: `grep -n "Property\|RealtorGraphState" services/ai_runtime/graph/_shared/turn_frame_builder.py` → 0 matches.

---

### PASO 10 — Refactorizar `lead_advisor_node.py`

**Archivo**: `services/ai_runtime/graph/_shared/nodes/lead_advisor_node.py`

**Cambios**:
1. Borrar import de `RealtorGraphState` (línea 14).
2. Línea 105-108: el bloque `if isinstance(graph_state, RealtorGraphState) and payload.get("presupuesto") is None:` que lee `search_filters.precio_max` → mover a `RealtorPolicy.extra_lead_sync(graph_state, payload)`. El shared llama `policy.extra_lead_sync(graph_state, payload)` y obtiene payload actualizado.

---

### PASO 11 — Refactorizar `scoring_hybrid.py`

**Archivo**: `services/ai_runtime/graph/_shared/scoring_hybrid.py`

**Cambios**:
1. Borrar import de `RealtorGraphState` (línea 21).
2. Línea 389 y contexto: el payload que se arma con campos realtor-específicos se delega a `policy.build_scoring_payload(graph_state) -> dict[str, Any]`. Agregar ese método al protocol y a realtor policy.

---

### PASO 12 — Mover catálogos `config/`

**Archivo**: `services/ai_runtime/config/geo_catalog.py`, `services/ai_runtime/config/property_type_catalog.py`
**Cambio**: moverlos a `services/ai_runtime/graph/realtor/catalogs/`. Actualizar todos los imports (ripgrep `from services.ai_runtime.config.geo_catalog` / `property_type_catalog`).

**Excepción**: si estos catálogos son usados por `prompt_composer.py` de forma agnóstica (por ejemplo, para rellenar un prompt generic), hay que verificarlo. Hoy todos los callsites que encontré son realtor.

---

## 4. Criterio de done (ejecutable)

Ejecutar estos comandos desde `/srv/datasyncsa`. **Todos deben devolver 0 matches o estar vacíos**:

```bash
# Ninguna referencia realtor en domain/
grep -rn "realtor\|Realtor\|Property\|presupuesto\|aprobacion" services/ai_runtime/domain/ | grep -v "# "

# Ninguna importación de realtor en _shared/
grep -rn "from services.ai_runtime.graph.realtor" services/ai_runtime/graph/_shared/

# Ningún isinstance de RealtorGraphState en _shared/
grep -rn "isinstance.*RealtorGraphState" services/ai_runtime/graph/_shared/

# property_repository fuera del contenedor agnóstico
grep -n "property_repository" services/ai_runtime/domain/ports.py
```

Y estos tests deben pasar:

```bash
cd /srv/datasyncsa
pytest services/ai_runtime/tests/ -x --tb=short
```

Si hay smoke tests E2E (por ejemplo `tests/smoke_realtor.py`), también.

---

## 5. Qué NO hacer (guardrails)

1. **No borrar `RealtorGraphState`** — sigue siendo el state model concreto del grafo realtor. Solo se deja de importar desde `_shared/`.
2. **No mergear pasos**. Cada paso es un commit separado para que un rollback quirúrgico sea posible.
3. **No agregar feature flags ni modo legacy** — el refactor es in-place. Lo que estaba en `domain/` como realtor desaparece.
4. **No tocar los prompts** (`graph/*/prompts/`). Su refactor es otro plan (ver `AI_RUNTIME_REFACTOR_PLAN_PROMPTS` si existe).
5. **No tocar el state schema** (agregar `schema_version`, etc.). Ese es PLAN 02.
6. **No refactorizar `build_realtor_graph` / `build_generic_graph`** (boilerplate de grafos). Ese es otro plan.
7. **No cambiar firmas de nodos** ni la forma en que LangGraph los llama. El refactor es interno al cuerpo de los nodos.
8. **No introducir dependencias circulares**: `graph/realtor/policies.py` puede importar de `domain/*` y de `graph/realtor/*`, pero `domain/*` **no** puede importar de `graph/realtor/*` (ni siquiera bajo `TYPE_CHECKING`).

---

## 6. Orden sugerido de commits

```
1. feat(ai_runtime): add RealtorLeadExtracted and RealtorLeadSnapshot
2. refactor(ai_runtime): remove realtor fields from LeadExtracted / LeadSnapshot
3. feat(ai_runtime): add VerticalPolicy protocol and NullVerticalPolicy
4. feat(ai_runtime): wire VerticalSpec.policy and RealtorPolicy skeleton
5. refactor(ai_runtime): move _field_has_value realtor branches to policy
6. refactor(ai_runtime): move SCORING_FIELD_ALIASES realtor keys to policy
7. refactor(ai_runtime): move property_repository to vertical_extras
8. refactor(ai_runtime): analyze_turn_node uses policy instead of realtor imports
9. refactor(ai_runtime): synthesize_node uses VerticalSpec.state_model
10. refactor(ai_runtime): prepare_synthesis_node uses VerticalSpec.state_model
11. refactor(ai_runtime): turn_frame_builder delegates to policy.build_turn_frame_extras
12. refactor(ai_runtime): lead_advisor_node uses policy.extra_lead_sync
13. refactor(ai_runtime): scoring_hybrid uses policy.build_scoring_payload
14. refactor(ai_runtime): move geo/property_type catalogs to graph/realtor/catalogs/
```

---

## 7. Estado al terminar este plan

- `domain/` y `graph/_shared/` no saben que existe realtor.
- Agregar un 5º vertical es: crear `graph/<nuevo>/policies.py` implementando `VerticalPolicy` + registrar en `verticals.py`. No se toca nada en `_shared/` ni en `domain/`.
- La deuda que **queda pendiente** (no forma parte de este plan):
  - Boilerplate duplicado entre `build_realtor_graph` y `build_generic_graph` (PLAN separado).
  - Prompt composer con if-chain por vertical (PLAN separado).
  - State schema sin versionado (PLAN 02).
  - Outbox de side-effects (PLAN separado).

---

## 8. Mensaje para la próxima IA ejecutora

> Leé este documento entero antes de empezar. Es autocontenido. No necesitás memoria ni sesión previa. El orden de los 14 pasos es deliberado: romperlo puede causar imports circulares o tests rojos que tape el verdadero bug. Si algún paso no cierra porque el código ya divergió, no improvises: pará, documentá el delta en un comentario al final de este archivo, y pedí confirmación humana antes de seguir.
