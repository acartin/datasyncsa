# AI_RUNTIME REFACTOR PLAN 03 — Graph Builder Factory

> **Audiencia**: prompt-plan autoejecutable para un agente de IA sin contexto previo.
> **Owner humano**: acartina@gmail.com
> **Repo**: `/srv/datasyncsa`
> **Branch base esperada**: la branch activa de trabajo (al momento de redacción, `HETZNER-LOCAL-2026-Abril-06`).
> **Fecha de redacción**: 2026-04-15
> **Dependencia**: asume PLAN 01 (decontamination) **ejecutado**. El factory usa el hook `VerticalSpec.policy` y el `VerticalSpec.state_model` que PLAN 01 introdujo. Si PLAN 01 no está mergeado, hacerlo primero.
> **No depende** de PLAN 02.

---

## 0. Por qué este plan existe

Los dos builders actuales duplican el backbone del grafo LangGraph:

- `services/ai_runtime/graph/realtor/graph.py` (187 líneas, ~22 nodos).
- `services/ai_runtime/graph/generic/graph.py` (131 líneas, ~12 nodos).

Ambos repiten la misma topología base:

```
START → analyze_turn
analyze_turn --(after_analyze_turn)--> {ask_clarification, collect_lead_data, capture_memory_entities}
ask_clarification → END
capture_memory_entities --(after_capture_memory)--> {memory_lookup, route_next_intent, lead_advisor, prepare_synthesis}
memory_lookup --(after_memory_lookup)--> {route_next_intent, lead_advisor, END, prepare_synthesis}
collect_lead_data → prepare_synthesis
route_next_intent --(after_route_next_intent ⟵ vertical)--> {<intent-handlers vertical-specific>}
<each intent-handler> → check_queue  (salvo search que tiene subgrafo propio)
check_queue --(after_check_queue)--> {route_next_intent, lead_advisor}
lead_advisor → prepare_synthesis
prepare_synthesis → synthesize
synthesize → END
assign_agent → mensajear
mensajear → check_queue
collect_appointment_data --(vertical)--> {assign_agent, lead_advisor | synthesize}
```

**Lo único que varía entre verticales**:
1. El set de intent-handlers (nodos) y su mapping en `after_route_next_intent`.
2. El router de `collect_appointment_data` (realtor cae a `lead_advisor`, generic cae a `synthesize`).
3. Si existe `search` + subflow `search → render_cards → check_queue` (solo realtor).

Agregar un 5º vertical con intents propios copiaría 100+ líneas de backbone. Este plan mueve el backbone a `_shared/graph_factory.py` y reduce cada `graph.py` vertical a ~30 líneas declarativas.

---

## 1. Estado objetivo

```
services/ai_runtime/graph/
├── _shared/
│   ├── graph_factory.py        ← NUEVO: backbone compartido
│   ├── graph_specs.py          ← NUEVO: IntentHandlerSpec, AppointmentConfig, GraphProfile
│   ├── routers/
│   │   ├── common.py           ← sin cambios
│   │   └── intents.py          ← NUEVO: after_route_next_intent paramétrico
│   ├── nodes/                  ← sin cambios
│   └── tools/mensajear.py      ← sin cambios
├── realtor/
│   ├── graph.py                ← ~30 líneas: construye GraphProfile y delega
│   ├── graph_profile.py        ← NUEVO: declara intent_handlers realtor
│   ├── routers/routes.py       ← deja solo after_search, after_render_cards
│   └── nodes/…                 ← sin cambios
└── generic/
    ├── graph.py                ← ~30 líneas: construye GraphProfile y delega
    ├── graph_profile.py        ← NUEVO: declara intent_handlers generic
    ├── routers/routes.py       ← borrado (todos los routers pasan al factory)
    └── nodes/…                 ← sin cambios
```

### Criterio de done

- `graph/realtor/graph.py` y `graph/generic/graph.py` cada uno ≤50 líneas (imports incluidos).
- `graph/_shared/graph_factory.py` es la única fuente de verdad de la topología común.
- El export de diagramas (`services/ai_runtime/scripts/export_graph_diagrams.py`) sigue generando grafos equivalentes (misma lista de nodos/edges).
- Todos los tests verdes.
- Smoke E2E (si existen) devuelve las mismas respuestas sobre fixtures conocidas.

---

## 2. Contratos nuevos

### 2.1 `services/ai_runtime/graph/_shared/graph_specs.py` (NUEVO)

```python
"""Specs declarativas para el graph factory.

Un GraphProfile describe TODO lo que un vertical aporta al backbone común.
No hay código imperativo acá — solo datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from services.ai_runtime.domain.ports import GraphDependencies

NodeFn = Callable[[dict, GraphDependencies], Any]
RouterFn = Callable[[dict], str]


@dataclass(frozen=True, slots=True)
class NodeChain:
    """Nodo adicional encadenado tras un intent handler.

    Permite modelar el sub-flow realtor: search → render_cards → check_queue.
    """

    name: str
    fn: NodeFn
    router: RouterFn | None = None
    router_mapping: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class IntentHandlerSpec:
    """Handler de intent: nodo(s) + forma de salir.

    Casos soportados:
    1) Handler simple: route_next_intent → node_name → check_queue.
    2) Handler con router condicional (search con loopback).
    3) Handler con chain (search → render_cards).
    """

    intent_type: str
    node_name: str
    fn: NodeFn
    router: RouterFn | None = None
    router_mapping: dict[str, str] | None = None
    chain: tuple[NodeChain, ...] = ()


@dataclass(frozen=True, slots=True)
class AppointmentConfig:
    """Configura el terminal de collect_appointment_data.

    realtor:  {assign_agent → "assign_agent", lead_advisor → "lead_advisor"}
    generic:  {assign_agent → "assign_agent", synthesize → "prepare_synthesis"}
    """

    node_fn: NodeFn
    router: RouterFn
    mapping: dict[str, str]


@dataclass(frozen=True, slots=True)
class GraphProfile:
    """Todo lo que un vertical aporta al backbone compartido."""

    vertical: str
    intent_handlers: tuple[IntentHandlerSpec, ...]
    appointment: AppointmentConfig
    extra_nodes: dict[str, NodeFn] = field(default_factory=dict)
```

### 2.2 `services/ai_runtime/graph/_shared/routers/intents.py` (NUEVO)

```python
"""Router paramétrico para after_route_next_intent."""

from __future__ import annotations

from services.ai_runtime.domain.state import BaseGraphState


def build_after_route_next_intent(mapping: dict[str, str]):
    """Devuelve fn(state) → str usando mapping intent_type → node_name.

    Si no hay active_intent o el tipo no está mapeado, cae a 'lead_advisor'.
    """

    def _router(state: dict[str, object]) -> str:
        graph_state = BaseGraphState.model_validate(state)
        if not graph_state.active_intent:
            return "lead_advisor"
        return mapping.get(graph_state.active_intent.type, "lead_advisor")

    return _router
```

### 2.3 `services/ai_runtime/graph/_shared/graph_factory.py` (NUEVO)

```python
"""Factory central: construye el grafo compartido inyectando un GraphProfile."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from services.ai_runtime.domain.contracts import TenantConfig
from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.graph_specs import GraphProfile
from services.ai_runtime.graph._shared.nodes import (
    analyze_turn,
    ask_clarification,
    capture_memory_entities,
    check_queue,
    collect_lead_data,
    lead_advisor,
    memory_lookup,
    prepare_synthesis,
    route_next_intent,
    synthesize,
)
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent
from services.ai_runtime.graph._shared.routers.common import (
    after_analyze_turn,
    after_capture_memory,
    after_check_queue,
    after_memory_lookup,
)
from services.ai_runtime.graph._shared.routers.intents import build_after_route_next_intent
from services.ai_runtime.graph._shared.tools.mensajear import mensajear
from services.ai_runtime.runtime.turn_trace import build_traced_node, build_traced_router

# Nombres que registra el factory por sí mismo: los handlers con estos node_name
# NO deben re-registrarse como add_node (solo declaran el mapping de route_next_intent).
_FACTORY_OWNED_NODE_NAMES = {"collect_appointment_data", "mensajear"}


def _mail_node(deps: GraphDependencies, state_model):
    async def _mail_impl(state: dict, runtime_deps: GraphDependencies):
        tenant_config = TenantConfig.model_validate(state["tenant_config"])
        graph_state = state_model.model_validate(state)
        result = await mensajear(
            dependencies=runtime_deps,
            client_id=state["client_id"],
            tipo="appointment_confirmation",
            destinatarios=[],
            datos_cita=state.get("cita", {}),
            tenant_config=tenant_config,
        )
        output = {"type": "mensajear", **result.model_dump(mode="json")}
        return {
            "turn_outputs": [*state.get("turn_outputs", []), output],
            **complete_active_intent(graph_state, output),
        }

    return build_traced_node("mensajear", _mail_impl, deps)


def build_workflow(profile: GraphProfile, deps: GraphDependencies):
    """Ensambla el StateGraph usando el backbone compartido + el perfil del vertical."""

    from services.ai_runtime.verticals import get_vertical_spec
    state_model = get_vertical_spec(profile.vertical).state_model

    workflow = StateGraph(dict)

    # -------------------- Nodos del backbone --------------------
    workflow.add_node("analyze_turn", build_traced_node("analyze_turn", analyze_turn, deps))
    workflow.add_node("ask_clarification", build_traced_node("ask_clarification", ask_clarification, deps))
    workflow.add_node("capture_memory_entities", build_traced_node("capture_memory_entities", capture_memory_entities, deps))
    workflow.add_node("memory_lookup", build_traced_node("memory_lookup", memory_lookup, deps))
    workflow.add_node("route_next_intent", build_traced_node("route_next_intent", route_next_intent, deps))
    workflow.add_node("collect_lead_data", build_traced_node("collect_lead_data", collect_lead_data, deps))
    workflow.add_node("check_queue", build_traced_node("check_queue", check_queue, deps))
    workflow.add_node("lead_advisor", build_traced_node("lead_advisor", lead_advisor, deps))
    workflow.add_node("prepare_synthesis", build_traced_node("prepare_synthesis", prepare_synthesis, deps))
    workflow.add_node("synthesize", build_traced_node("synthesize", synthesize, deps))
    workflow.add_node("mensajear", _mail_node(deps, state_model))

    # -------------------- Handlers del vertical --------------------
    for handler in profile.intent_handlers:
        if handler.node_name in _FACTORY_OWNED_NODE_NAMES:
            # El factory ya lo registra (mensajear) o lo hará la appointment config (collect_appointment_data).
            continue
        workflow.add_node(handler.node_name, build_traced_node(handler.node_name, handler.fn, deps))
        for chain_node in handler.chain:
            workflow.add_node(chain_node.name, build_traced_node(chain_node.name, chain_node.fn, deps))

    # -------------------- Extras del perfil (p.ej. assign_agent) --------------------
    for name, fn in profile.extra_nodes.items():
        workflow.add_node(name, build_traced_node(name, fn, deps))

    # -------------------- Appointment --------------------
    workflow.add_node(
        "collect_appointment_data",
        build_traced_node("collect_appointment_data", profile.appointment.node_fn, deps),
    )

    # -------------------- Edges del backbone --------------------
    workflow.add_edge(START, "analyze_turn")
    workflow.add_conditional_edges(
        "analyze_turn",
        build_traced_router("after_analyze_turn", after_analyze_turn, deps),
        {
            "ask_clarification": "ask_clarification",
            "collect_lead_data": "collect_lead_data",
            "capture_memory_entities": "capture_memory_entities",
        },
    )
    workflow.add_edge("ask_clarification", END)
    workflow.add_conditional_edges(
        "capture_memory_entities",
        build_traced_router("after_capture_memory", after_capture_memory, deps),
        {
            "memory_lookup": "memory_lookup",
            "route_next_intent": "route_next_intent",
            "lead_advisor": "lead_advisor",
            "synthesize": "prepare_synthesis",
        },
    )
    workflow.add_conditional_edges(
        "memory_lookup",
        build_traced_router("after_memory_lookup", after_memory_lookup, deps),
        {
            "route_next_intent": "route_next_intent",
            "lead_advisor": "lead_advisor",
            "end": END,
            "synthesize": "prepare_synthesis",
        },
    )
    workflow.add_edge("collect_lead_data", "prepare_synthesis")

    # -------------------- route_next_intent paramétrico --------------------
    route_mapping = {handler.intent_type: handler.node_name for handler in profile.intent_handlers}
    conditional_destinations = {
        handler.node_name: handler.node_name for handler in profile.intent_handlers
    }
    conditional_destinations["lead_advisor"] = "lead_advisor"
    workflow.add_conditional_edges(
        "route_next_intent",
        build_traced_router(
            "after_route_next_intent",
            build_after_route_next_intent(route_mapping),
            deps,
        ),
        conditional_destinations,
    )

    # -------------------- Salidas de cada handler --------------------
    for handler in profile.intent_handlers:
        if handler.node_name in _FACTORY_OWNED_NODE_NAMES:
            continue  # mensajear/collect_appointment_data ya tienen sus propios edges
        if handler.router is None:
            workflow.add_edge(handler.node_name, "check_queue")
        else:
            assert handler.router_mapping, f"handler {handler.node_name}: router sin mapping"
            workflow.add_conditional_edges(
                handler.node_name,
                build_traced_router(f"after_{handler.node_name}", handler.router, deps),
                handler.router_mapping,
            )
        for chain_node in handler.chain:
            if chain_node.router is None:
                workflow.add_edge(chain_node.name, "check_queue")
            else:
                assert chain_node.router_mapping
                workflow.add_conditional_edges(
                    chain_node.name,
                    build_traced_router(f"after_{chain_node.name}", chain_node.router, deps),
                    chain_node.router_mapping,
                )

    # -------------------- Appointment + assign_agent + mensajear --------------------
    workflow.add_conditional_edges(
        "collect_appointment_data",
        build_traced_router("after_collect_appointment_data", profile.appointment.router, deps),
        profile.appointment.mapping,
    )
    workflow.add_edge("assign_agent", "mensajear")
    workflow.add_edge("mensajear", "check_queue")

    workflow.add_conditional_edges(
        "check_queue",
        build_traced_router("after_check_queue", after_check_queue, deps),
        {"route_next_intent": "route_next_intent", "lead_advisor": "lead_advisor"},
    )
    workflow.add_edge("lead_advisor", "prepare_synthesis")
    workflow.add_edge("prepare_synthesis", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()
```

### 2.4 Perfil realtor — `services/ai_runtime/graph/realtor/graph_profile.py` (NUEVO)

**Antes de escribir este archivo**: verificar con `ls services/ai_runtime/graph/realtor/nodes/` si `collect_lead_data_node.py` existe. Si no existe, `collect_lead_data` se importa de `_shared`:

```python
from services.ai_runtime.graph._shared.nodes import collect_lead_data
```

```python
"""GraphProfile para el vertical realtor."""

from __future__ import annotations

from services.ai_runtime.graph._shared.graph_specs import (
    AppointmentConfig,
    GraphProfile,
    IntentHandlerSpec,
    NodeChain,
)
from services.ai_runtime.graph.realtor.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.realtor.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.realtor.nodes.compare_properties_node import compare_properties
from services.ai_runtime.graph.realtor.nodes.describe_result_set_node import describe_result_set
from services.ai_runtime.graph.realtor.nodes.focus_property_node import focus_property
from services.ai_runtime.graph.realtor.nodes.llm_recommend_node import llm_recommend
from services.ai_runtime.graph.realtor.nodes.mutate_comparison_set_node import mutate_comparison_set
from services.ai_runtime.graph.realtor.nodes.rag_agencia_node import rag_agencia
from services.ai_runtime.graph.realtor.nodes.rag_documents_node import rag_documents
from services.ai_runtime.graph.realtor.nodes.render_cards_node import render_cards
from services.ai_runtime.graph.realtor.nodes.search_node import search
from services.ai_runtime.graph.realtor.nodes.show_result_cards_node import show_result_cards
from services.ai_runtime.graph._shared.nodes import collect_lead_data  # ajustar si hay versión realtor
from services.ai_runtime.graph.realtor.routers.routes import after_render_cards, after_search
from services.ai_runtime.graph.realtor.tools.financial_calc import financial_calc


def _after_collect_appointment_data_realtor(state):
    from services.ai_runtime.graph.realtor.state.model import RealtorGraphState
    graph_state = RealtorGraphState.model_validate(state)
    return "assign_agent" if getattr(graph_state.cita, "datos_completos", False) else "lead_advisor"


async def _mensajear_placeholder(state, deps):
    # El factory registra el nodo real; este no se usa, pero IntentHandlerSpec requiere una fn.
    return {}


REALTOR_PROFILE = GraphProfile(
    vertical="realtor",
    intent_handlers=(
        IntentHandlerSpec(
            intent_type="buscar",
            node_name="search",
            fn=search,
            router=after_search,
            router_mapping={
                "search": "search",
                "lead_advisor": "lead_advisor",
                "check_queue": "check_queue",
                "render_cards": "render_cards",
            },
            chain=(
                NodeChain(
                    name="render_cards",
                    fn=render_cards,
                    router=after_render_cards,
                    router_mapping={"check_queue": "check_queue"},
                ),
            ),
        ),
        IntentHandlerSpec(intent_type="describe_result_set", node_name="describe_result_set", fn=describe_result_set),
        IntentHandlerSpec(intent_type="show_result_cards", node_name="show_result_cards", fn=show_result_cards),
        IntentHandlerSpec(intent_type="focus_property", node_name="focus_property", fn=focus_property),
        IntentHandlerSpec(intent_type="calcular", node_name="financial_calc", fn=financial_calc),
        IntentHandlerSpec(intent_type="comparar", node_name="compare_properties", fn=compare_properties),
        IntentHandlerSpec(intent_type="mutar_comparacion", node_name="mutate_comparison_set", fn=mutate_comparison_set),
        IntentHandlerSpec(intent_type="agendar", node_name="collect_appointment_data", fn=collect_appointment_data),
        IntentHandlerSpec(intent_type="rag_agencia", node_name="rag_agencia", fn=rag_agencia),
        IntentHandlerSpec(intent_type="rag_docs", node_name="rag_documents", fn=rag_documents),
        IntentHandlerSpec(intent_type="escalar", node_name="collect_lead_data", fn=collect_lead_data),
        IntentHandlerSpec(intent_type="recomendar", node_name="llm_recommend", fn=llm_recommend),
        IntentHandlerSpec(intent_type="mensajear", node_name="mensajear", fn=_mensajear_placeholder),
    ),
    appointment=AppointmentConfig(
        node_fn=collect_appointment_data,
        router=_after_collect_appointment_data_realtor,
        mapping={"assign_agent": "assign_agent", "lead_advisor": "lead_advisor"},
    ),
    extra_nodes={"assign_agent": assign_agent},
)
```

### 2.5 Perfil generic — `services/ai_runtime/graph/generic/graph_profile.py` (NUEVO)

```python
"""GraphProfile para el vertical generic (healthcare, legal, insurance)."""

from __future__ import annotations

from services.ai_runtime.graph._shared.graph_specs import (
    AppointmentConfig,
    GraphProfile,
    IntentHandlerSpec,
)
from services.ai_runtime.graph.generic.nodes.assign_agent_node import assign_agent
from services.ai_runtime.graph.generic.nodes.collect_appointment_data_node import collect_appointment_data
from services.ai_runtime.graph.generic.nodes.rag_agencia_node import rag_agencia
from services.ai_runtime.graph._shared.nodes import collect_lead_data


def _after_collect_appointment_data_generic(state):
    from services.ai_runtime.domain.state import GenericGraphState
    graph_state = GenericGraphState.model_validate(state)
    return "assign_agent" if getattr(graph_state.cita, "datos_completos", False) else "synthesize"


async def _mensajear_placeholder(state, deps):
    return {}


GENERIC_PROFILE = GraphProfile(
    vertical="generic",
    intent_handlers=(
        IntentHandlerSpec(intent_type="rag_agencia", node_name="rag_agencia", fn=rag_agencia),
        IntentHandlerSpec(intent_type="escalar", node_name="collect_lead_data", fn=collect_lead_data),
        IntentHandlerSpec(intent_type="captura_lead", node_name="collect_lead_data", fn=collect_lead_data),
        IntentHandlerSpec(intent_type="agendar", node_name="collect_appointment_data", fn=collect_appointment_data),
        IntentHandlerSpec(intent_type="mensajear", node_name="mensajear", fn=_mensajear_placeholder),
    ),
    appointment=AppointmentConfig(
        node_fn=collect_appointment_data,
        router=_after_collect_appointment_data_generic,
        mapping={"assign_agent": "assign_agent", "synthesize": "prepare_synthesis"},
    ),
    extra_nodes={"assign_agent": assign_agent},
)
```

**Nota**: `GENERIC_PROFILE.vertical = "generic"` no matchea con los slugs de `_VERTICAL_SPECS` (`healthcare`, `legal`, `insurance`). El `build_workflow` llama `get_vertical_spec(profile.vertical)` para resolver `state_model`. Por eso este perfil **no debe ser llamado con `vertical="generic"`** — el cliente que lo usa (`build_generic_graph`) recibe el `vertical` real del tenant y debe reescribirse para **pasarle al factory el vertical real**, no "generic". Ver arreglo en sección 2.6.

### 2.6 Graph builders colapsados

**`services/ai_runtime/graph/realtor/graph.py`** (reemplazo completo):

```python
"""Builder delgado: delega al factory compartido con el perfil realtor."""
from __future__ import annotations

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.graph_factory import build_workflow
from services.ai_runtime.graph.realtor.graph_profile import REALTOR_PROFILE


def build_realtor_graph(deps: GraphDependencies):
    return build_workflow(REALTOR_PROFILE, deps)
```

**`services/ai_runtime/graph/generic/graph.py`** (reemplazo completo):

```python
"""Builder delgado: delega al factory con el perfil generic.

El vertical real (healthcare/legal/insurance) se resuelve por el caller, que debe
reescribir el profile.vertical antes de delegar al factory. Así el state_model
correcto queda cableado sin un switch en el factory.
"""
from __future__ import annotations

from dataclasses import replace

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.graph._shared.graph_factory import build_workflow
from services.ai_runtime.graph.generic.graph_profile import GENERIC_PROFILE


def build_generic_graph(deps: GraphDependencies, *, vertical: str = "healthcare"):
    profile = replace(GENERIC_PROFILE, vertical=vertical)
    return build_workflow(profile, deps)
```

**Alternativa** si `graph_registry.get_graph(vertical, flow, deps)` pasa siempre el `vertical` real: modificar la firma de `build_generic_graph` y la llamada en `registry.py` para propagar `vertical`. Es preferible a dejar `"healthcare"` como default silencioso.

Revisar `services/ai_runtime/graph/registry.py` y ajustar:

```python
return spec.graph_builder(deps, vertical=spec.slug)
```

Y `VerticalSpec.graph_builder` pasa a ser `Callable[[GraphDependencies, str], Any]` (o `Callable[..., Any]` laxo). `build_realtor_graph` acepta `**kwargs` e ignora `vertical`.

---

## 3. Plan de ejecución — pasos exactos

Cada paso = 1 commit. **No mezclar**.

### PASO 1 — Crear specs (solo tipos)
- Crear `services/ai_runtime/graph/_shared/graph_specs.py`.
- **Commit**: `feat(ai_runtime): add GraphProfile specs for graph factory`

### PASO 2 — Router paramétrico
- Crear `services/ai_runtime/graph/_shared/routers/intents.py`.
- **Commit**: `feat(ai_runtime): add parametric after_route_next_intent router`

### PASO 3 — Factory
- Crear `services/ai_runtime/graph/_shared/graph_factory.py` con `build_workflow` + `_mail_node`.
- Smoke: `python -c "from services.ai_runtime.graph._shared.graph_factory import build_workflow; print('ok')"`.
- **Commit**: `feat(ai_runtime): add shared graph factory`

### PASO 4 — Perfil realtor
- `ls services/ai_runtime/graph/realtor/nodes/ | grep collect_lead` para confirmar de dónde viene `collect_lead_data`.
- Crear `services/ai_runtime/graph/realtor/graph_profile.py`.
- Smoke: `python -c "from services.ai_runtime.graph.realtor.graph_profile import REALTOR_PROFILE; print(len(REALTOR_PROFILE.intent_handlers))"`.
- **Commit**: `feat(ai_runtime): declare REALTOR_PROFILE for graph factory`

### PASO 5 — Perfil generic
- Crear `services/ai_runtime/graph/generic/graph_profile.py`.
- Smoke import.
- **Commit**: `feat(ai_runtime): declare GENERIC_PROFILE for graph factory`

### PASO 6 — Ajustar registry para pasar `vertical` al builder
- Editar `services/ai_runtime/graph/registry.py`: `spec.graph_builder(deps, vertical=spec.slug)`.
- Editar `verticals.py`: el type `GraphBuilder = Callable[..., Any]` (laxo) para aceptar kwarg opcional.
- Smoke: `python -c "from services.ai_runtime.graph.registry import GraphRegistry; print('ok')"`.
- **Commit**: `refactor(ai_runtime): pass vertical slug to graph builders`

### PASO 7 — Cutover realtor
- Reemplazar `services/ai_runtime/graph/realtor/graph.py` por la versión delgada (sección 2.6). `build_realtor_graph` acepta `**_: Any` y lo ignora, o `vertical: str = "realtor"`.
- Correr `pytest services/ai_runtime/tests/ -k realtor -x --tb=short`.
- Correr smoke E2E realtor si existe.
- **Commit**: `refactor(ai_runtime): realtor graph delegates to shared factory`

### PASO 8 — Cutover generic
- Reemplazar `services/ai_runtime/graph/generic/graph.py` por la versión delgada.
- `pytest services/ai_runtime/tests/ -x --tb=short`.
- Smoke E2E para al menos un vertical generic (healthcare).
- **Commit**: `refactor(ai_runtime): generic graph delegates to shared factory`

### PASO 9 — Limpieza de routers muertos
- Editar `services/ai_runtime/graph/realtor/routers/routes.py`: borrar `after_route_next_intent` y `after_collect_appointment_data`. Deben quedar solo `after_search` y `after_render_cards`.
- Borrar `services/ai_runtime/graph/generic/routers/routes.py`. Si `__init__.py` queda vacío, borrar `routers/` entero. Ajustar cualquier import roto.
- `grep -rn "after_route_next_intent\|after_collect_appointment_data" services/` → no debe mostrar imports externos al `_shared` ni al `graph_profile`.
- **Commit**: `refactor(ai_runtime): remove obsolete router functions after factory adoption`

### PASO 10 — Verificar export de diagramas
- Correr `python services/ai_runtime/scripts/export_graph_diagrams.py` (o el comando habitual del repo).
- Comparar los diagramas generados contra los commiteados antes del refactor (si hay PNGs/SVGs versionados). Deben ser equivalentes en nodos y edges. Orden puede variar.
- Si el script importa `build_generic_graph(deps)` sin el kwarg `vertical`, ajustar para pasarlo (línea ~366-367 del script según auditoría).
- **Commit**: `chore(ai_runtime): update graph diagram export for factory` (solo si hubo cambios).

---

## 4. Criterio de done (ejecutable)

```bash
cd /srv/datasyncsa

# 1. Imports OK
python -c "from services.ai_runtime.graph._shared.graph_factory import build_workflow"
python -c "from services.ai_runtime.graph.realtor.graph_profile import REALTOR_PROFILE"
python -c "from services.ai_runtime.graph.generic.graph_profile import GENERIC_PROFILE"

# 2. Graph builders compilan
python -c "
from unittest.mock import MagicMock
from services.ai_runtime.graph.realtor.graph import build_realtor_graph
from services.ai_runtime.graph.generic.graph import build_generic_graph
deps = MagicMock()
assert build_realtor_graph(deps) is not None
assert build_generic_graph(deps, vertical='healthcare') is not None
print('ok')
"

# 3. graph.py colapsados
test $(wc -l < services/ai_runtime/graph/realtor/graph.py) -le 50 || echo "FAIL: realtor graph too long"
test $(wc -l < services/ai_runtime/graph/generic/graph.py) -le 50 || echo "FAIL: generic graph too long"

# 4. Routers muertos eliminados
grep -rn "from services.ai_runtime.graph.generic.routers" services/ && echo "FAIL" || echo "clean"
grep -rn "realtor.routers.routes import.*after_route_next_intent" services/ && echo "FAIL" || echo "clean"

# 5. Tests verdes
pytest services/ai_runtime/tests/ -x --tb=short
```

Manual: lanzar servicio local, ejecutar conversación realtor completa (búsqueda → fichas → agendar) y un flow generic (saludo → appointment). Ambas deben responder idéntico al baseline.

---

## 5. Qué NO hacer

1. **No renombrar nodos**. `search`, `check_queue`, `mensajear`, `analyze_turn`, etc. deben preservar el nombre exacto — dashboards, trazas y tests indexan por nombre.
2. **No cambiar `StateGraph(dict)` por tipado**. Es otro plan (PLAN 06 futuro).
3. **No editar el body de los nodos** (`search_node.py`, etc.).
4. **No inventar plugin discovery**. Los profiles se importan estáticamente.
5. **No colapsar verticales en runtime**. Cada uno compila su propio workflow.
6. **No unificar `collect_appointment_data` entre realtor y generic**. Son implementaciones distintas del mismo intent; el factory las trata igual, los profiles las suministran distintas. Unificarlas es otro refactor (probablemente una policy en `VerticalSpec`).
7. **No acumular pasos en un commit**.
8. **No "mejorar" prompts, estado o side-effects** durante este refactor. Mover, no rediseñar.

---

## 6. Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| Doble registro de `collect_appointment_data` o `mensajear` | Set `_FACTORY_OWNED_NODE_NAMES` en el factory + `continue` en el loop de handlers. |
| `collect_lead_data` no existe en `graph/realtor/nodes/` (solo en `_shared`) | Paso 4: `ls` antes de escribir el profile y ajustar import. |
| `build_generic_graph` no sabe qué `state_model` usar porque el "generic" profile tiene vertical="generic" que no está en `_VERTICAL_SPECS` | Paso 6: registry pasa `vertical=spec.slug` al builder, y el builder hace `replace(GENERIC_PROFILE, vertical=<slug real>)` antes de llamar al factory. |
| Tests que comparan hashes del grafo compilado fallan por orden distinto de edges | Ajustar test (no refactor). La topología equivalente es el contrato, no el orden interno. |
| `IntentHandlerSpec` para `mensajear`/`collect_appointment_data` requiere una `fn` aunque el factory la ignora | Usar `_mensajear_placeholder` async no-op. Feo pero preserva el tipo; alternativa es `fn: NodeFn \| None` pero aumenta el ruido. |
| Un 5º vertical sin intents propios | `GraphProfile(intent_handlers=(), ...)` es válido. El router cae siempre a `lead_advisor`. |
| `extra_nodes` tiene colisión de nombre con un handler o con el backbone | Agregar al inicio del factory una aserción: `assert len(extra_nodes) == len(set(extra_nodes))` + `assert all(name not in BACKBONE_NODE_NAMES for name in extra_nodes)`. |

---

## 7. Estado al terminar

- Cada `graph.py` vertical ≤50 líneas.
- Backbone en `_shared/graph_factory.py` es la única fuente de topología común.
- Agregar un intent nuevo a realtor = 1 entrada de `IntentHandlerSpec` en `REALTOR_PROFILE`. Sin tocar factory.
- Agregar un 5º vertical con intents propios = crear `graph_profile.py` + registrar spec en `verticals.py`. Cero líneas nuevas en backbone.

### Deuda remanente (no bloqueante, para planes futuros)

- **PLAN 04 — Prompt composer tenant override**: mover `compose()` if-chain por vertical a `VerticalSpec.prompt_pack` + hook de override por tenant.
- **PLAN 05 — Outbox de side-effects**: reliability de `mensajear`.
- **PLAN 06 — StateGraph tipado**: `StateGraph(state_model)` en lugar de `dict`.
- **PLAN 07 — Plugin discovery** (opcional).

---

## 8. Mensaje para la próxima IA ejecutora

> Este plan es refactor de topología — **comportamiento, prompts, estado y side-effects no cambian**. Si un test E2E falla tras el paso 7/8, el refactor introdujo un bug: no ajustes el test, encontrá el edge faltante o el nombre de nodo que cambió. Los nombres de nodo son contract público con dashboards y trazas — preservalos byte-exact. Si un import de nodo no existe donde el plan lo indica (ej. `collect_lead_data` en realtor), ajustá el import del `graph_profile` — no inventes un nodo nuevo. Si un paso no aplica porque el código ya divergió, documentá el delta al final de este archivo y pedí confirmación humana antes de seguir.