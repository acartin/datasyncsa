# Agent Core Prompt Sequence

Secuencia canonica de prompts para implementar de principio a fin la arquitectura nueva con:

- `agent-core`
- `scoring-core`

No existe `routing-core` en el target actual.

## Como usar este archivo

- Ejecuta los prompts en orden.
- Cada prompt es reanudable.
- Si la sesion es nueva o el contexto se compacto, antepone el bloque `COMMON BOOTSTRAP`.
- Cada prompt asume que el anterior ya quedo completado.
- Cada prompt debe terminar con:
  - archivos cambiados
  - decisiones tomadas
  - bloqueos reales
  - id del siguiente prompt sugerido

## COMMON BOOTSTRAP

```text
Trabaja sobre /srv/datasyncsa.

Antes de hacer nada:
1. Lee .agent/RULES.md
2. Lee .agent/PY_EXECUTION_MAP.md
3. Lee .agent/AGENT_CORE_BOOTSTRAP.md
4. Lee docs/AGENT_CORE_INDEX.md

Arquitectura canonica:
- agent-core es el unico decisor conversacional.
- scoring-core es un servicio separado y conserva la BD y logica actual de scoring.
- generic y realtor son verticales del mismo runtime.
- No crear tablas nuevas para policy gate, tool registry o card registry.
- Esos artefactos viven en archivos bajo schemas/.
- Prompts del sistema: ai_system_prompts.
- Prompts por tenant: lead_ai_prompts.
- Prompts de scoring: lead_scoring_prompts.
- No tomar inference-core-v1/v2 como baseline arquitectonico; solo como fuente de extraccion.

Fuentes canonicas:
- docs/AGENT_CORE_RULES.md
- docs/AGENT_CORE_ARCHITECTURE.md
- docs/AGENT_CORE_PROMPT_RUNTIME.md
- docs/SCORING_CORE_BOUNDARY.md
- docs/AGENT_CORE_FILE_MAP.md
- docs/AGENT_CORE_IMPLEMENTATION_PLAN.md
- schemas/agent_core/contracts/*
- schemas/agent_core/runtime/*
- schemas/scoring_core/contracts/*

Reglas de ejecucion:
- No tocar BD de scoring.
- No cambiar logica funcional de scoring al extraerla.
- No mezclar scoring dentro de agent-core.
- No introducir heuristicas hardcodeadas para routing conversacional.
- No crear compatibilidad legacy innecesaria dentro de agent-core.
- Si necesitas compatibilidad de APIs, resuelvela coordinando consumidores del monorepo.

Al terminar:
- resume archivos cambiados
- lista decisiones y supuestos
- propone el siguiente prompt exacto por id
```

## PROMPT 01 - Congelar contratos de borde y mapa de consumidores

```text
Usa COMMON BOOTSTRAP.

Tarea:
Congela el mapa real de consumidores internos del monorepo y los contratos de borde que hoy dependen de inference-core-v1/v2 para que la implementacion de agent-core y scoring-core tenga targets claros.

Objetivos:
- identificar todos los modulos internos que llaman APIs de inference-core-v1/v2
- identificar endpoints realmente usados para chat y scoring
- crear dos documentos nuevos:
  - docs/AGENT_CORE_API_CONTRACT.md
  - docs/SCORING_CORE_API_CONTRACT.md
- actualizar docs/AGENT_CORE_FILE_MAP.md con la lista de consumidores reales

Scope permitido:
- docs/**
- services/** solo para lectura
- tests/** solo para lectura
- .agent/** solo si necesitas agregar referencia documental minima

Reglas:
- no crear codigo de runtime
- no modificar servicios aun
- no inventar consumidores: descubre los reales en el repo
- separa claramente:
  - contrato conversacional de agent-core
  - contrato de scorecards/jobs de scoring-core

Resultado esperado:
- contrato de entrada/salida de agent-core definido
- contrato de entrada/salida de scoring-core definido
- lista exacta de consumidores internos que luego habra que cortar a los nuevos servicios
```

## PROMPT 02 - Extraer scoring-core sin cambiar su logica

```text
Usa COMMON BOOTSTRAP.

Tarea:
Extrae el motor actual de scoring desde services/inference-stack-v2/inference-core-v2 hacia services/scoring-core, conservando la logica funcional y la BD actual.

Objetivos:
- mover o copiar la implementacion funcional de scoring a scoring-core
- preservar nombres de clases y funciones cuando sea posible
- dejar scoring-core como duenio de:
  - scoring_engine
  - scoring_worker
  - scoring_job_service
  - scoring_repository
  - modelos y endpoints de scorecards/jobs/modelo activo necesarios

Scope permitido:
- services/scoring-core/**
- services/inference-stack-v2/inference-core-v2/** solo para lectura o para quitar acoplamientos minimos si son imprescindibles
- docs/** si necesitas documentar una decision tecnica concreta

Reglas:
- no tocar tablas ni migraciones de scoring
- no cambiar contratos de scorecard/job salvo que el repo ya tenga inconsistencia tecnica real
- no borrar todavia el codigo legacy de inference-core-v2
- si necesitas adaptar imports o config, manten el comportamiento

Resultado esperado:
- scoring-core contiene el motor real de scoring y su worker
- la logica de scoring ya no depende conceptualmente de inference-core-v2 para existir
```

## PROMPT 03 - Cablear scoring-core como servicio ejecutable

```text
Usa COMMON BOOTSTRAP.

Tarea:
Convierte scoring-core en un servicio realmente ejecutable dentro del repo.

Objetivos:
- agregar app FastAPI real en services/scoring-core
- agregar worker funcional en services/scoring-core/worker.py
- crear o adaptar Dockerfile y wiring necesario
- actualizar docker-compose y archivos operativos minimos para levantar:
  - scoring-core
  - scoring-core-worker
- mantener endpoints de lectura de scoring segun docs/SCORING_CORE_API_CONTRACT.md

Scope permitido:
- services/scoring-core/**
- docker-compose.yml
- .env.example si hace falta declarar variables nuevas o mover naming
- .agent/PY_EXECUTION_MAP.md si hace falta ajuste fino
- docs/** solo si debes reflejar un cambio operativo real

Reglas:
- no cambies la BD de scoring
- no redisenes scoring
- no conectes aun consumers nuevos
- limita validacion a lo minimo necesario del servicio

Resultado esperado:
- scoring-core puede compilar/arrancar como servicio propio
- scoring-core-worker puede ejecutar el pipeline async existente
```

## PROMPT 04 - Implementar contratos y loaders base de agent-core

```text
Usa COMMON BOOTSTRAP.

Tarea:
Implementa en codigo el esqueleto real de agent-core a partir de los contratos y runtime config que ya existen en schemas/.

Objetivos:
- crear modelos Pydantic equivalentes a:
  - RouterDecision
  - ToolCall
  - ToolResult
  - SynthesizerInput
  - SynthesizerOutput
  - AnswerEnvelope
- implementar loaders tipados para:
  - policy_gate.v1.json
  - tool_registry.v1.json
  - card_registry.v1.json
  - prompt_runtime.v1.json
- dejar un app skeleton navegable dentro de services/agent-core

Scope permitido:
- services/agent-core/**
- schemas/agent_core/** si encuentras un desajuste estructural real
- docs/** solo si documentas una correccion de contrato

Reglas:
- no implementes aun planner real ni tools reales
- no metas scoring dentro de agent-core
- no introduzcas contratos paralelos distintos a los de schemas

Resultado esperado:
- agent-core tiene tipos y config base listos para construir el runtime
```

## PROMPT 05 - Implementar prompt runtime y planner de agent-core

```text
Usa COMMON BOOTSTRAP.

Tarea:
Implementa la resolucion de prompts y el planner de agent-core siguiendo docs/AGENT_CORE_PROMPT_RUNTIME.md.

Objetivos:
- resolver prompts desde:
  - ai_system_prompts
  - lead_ai_prompts
- implementar normalize_input
- implementar context snapshot minimo y limpio para planner
- implementar planner LLM que devuelva RouterDecision tipado
- implementar salida explicita de clarify como goal legitimo

Scope permitido:
- services/agent-core/**
- docs/** solo si debes documentar una decision de prompt/runtime

Reglas:
- planner no puede ver ToolResult
- planner no puede escribir SQL libre
- planner no puede redactar cards
- si hace falta un nuevo node_slug, documentalo y usalo de forma consistente

Resultado esperado:
- agent-core ya puede recibir un turno y producir RouterDecision valido
```

## PROMPT 06 - Implementar runtime determinista generico

```text
Usa COMMON BOOTSTRAP.

Tarea:
Implementa el runtime determinista de agent-core para el vertical generic.

Objetivos:
- implementar policy gate binario
- implementar answer guardrail binario
- implementar tool execution para:
  - rag
  - workflow si ya hay workflow tipado utilizable
- implementar synthesizer LLM que solo vea SynthesizerInput
- implementar persistencia de AnswerEnvelope

Scope permitido:
- services/agent-core/**
- schemas/agent_core/** solo si hay que ajustar un contrato por bug real

Reglas:
- gate y guardrail solo accept/reject + reason_code
- el synthesizer no puede ver RouterDecision
- si el goal es clarify, el flujo termina antes de tool execution
- cards siguen fuera del synthesizer

Resultado esperado:
- generic funciona de punta a punta en agent-core sin scoring
```

## PROMPT 07 - Implementar vertical realtor en agent-core

```text
Usa COMMON BOOTSTRAP.

Tarea:
Implementa el vertical realtor dentro del mismo runtime de agent-core, sin crear una arquitectura paralela.

Objetivos:
- implementar contratos de slots realtor
- implementar realtor_sql como:
  - slots -> AST -> SQL
  - allowlist de tablas/columnas
  - linter + row-limit
- implementar card_renderer determinista para resultados realtor
- conectar prompts y policies especificas del vertical

Scope permitido:
- services/agent-core/**
- schemas/agent_core/**
- schemas/canonical_property.json
- schemas/property_card_expanded.v1.json

Reglas:
- no meter SQL libre en prompts ni planner
- cards salen solo de ToolResult
- generic y realtor deben compartir el mismo runtime base
- cualquier diferencia por vertical debe vivir en config, contracts o tools, no en dos pipelines distintos

Resultado esperado:
- realtor funciona dentro de agent-core como vertical del mismo sistema
```

## PROMPT 08 - Conectar agent-core con scoring-core

```text
Usa COMMON BOOTSTRAP.

Tarea:
Conecta agent-core con scoring-core usando el contrato minimo definido, sin reintroducir scoring en agent-core.

Objetivos:
- despues de persistir la conversacion final, disparar side effect de scoring
- usar solo:
  - client_id
  - lead_id
  - conversation_id
- implementar cliente interno o llamada interna a scoring-core
- asegurar que agent-core no resuelva:
  - scoring_model_id
  - prompt_id de scoring
  - prompt snapshot de scoring

Scope permitido:
- services/agent-core/**
- services/scoring-core/**
- schemas/scoring_core/contracts/*
- docs/** solo si se documenta el borde definitivo

Reglas:
- agent-core no ejecuta scoring
- agent-core no calcula scorecards
- scoring-core es duenio completo del dominio de scoring

Resultado esperado:
- agent-core dispara scoring sin conocer detalles internos del dominio de scoring
```

## PROMPT 09 - Cortar consumidores internos al nuevo stack

```text
Usa COMMON BOOTSTRAP.

Tarea:
Migra los consumidores internos del monorepo para que dejen de depender del camino activo de inference-core-v1/v2 y usen agent-core y scoring-core.

Objetivos:
- actualizar los modulos detectados en docs/AGENT_CORE_FILE_MAP.md y docs/AGENT_CORE_API_CONTRACT.md
- cortar llamadas directas a inference-core-v1/v2 para chat
- cortar llamadas directas a inference-core-v1/v2 para scorecards/jobs cuando ya existan equivalentes en scoring-core
- mantener coordinados los contratos de borde de los consumidores del monorepo

Scope permitido:
- consumers reales identificados en el paso 01
- services/agent-core/**
- services/scoring-core/**
- docs/** si el cambio altera borde operativo

Reglas:
- no meter adaptacion de compatibilidad dentro de agent-core
- si un consumer necesita mapping, resolverlo en ese consumer o su adapter local
- no reabrir inference-core-v1/v2 como baseline

Resultado esperado:
- el camino principal del monorepo deja de usar inference-core-v1/v2 para las rutas activas
```

## PROMPT 10 - Limpieza final y congelamiento canónico

```text
Usa COMMON BOOTSTRAP.

Tarea:
Haz la limpieza final para que cualquier IA o desarrollador vea una sola arquitectura vigente en el repo.

Objetivos:
- marcar inference-core-v1/v2 como legacy fuera del camino principal
- actualizar docs y bootstrap operativos si cambiaron rutas reales
- regenerar contexto si aplica segun .agent/RULES.md
- dejar AGENT_CORE_INDEX como puerta de entrada correcta
- eliminar o archivar documentos que contradigan la arquitectura nueva

Scope permitido:
- docs/**
- .agent/**
- servicios legacy solo para quitar referencias activas si ya no son usadas

Reglas:
- no borrar algo que aun este en uso por consumidores reales
- no dejar dos documentos vivos describiendo arquitecturas distintas
- el resultado debe ser navegable por una IA sin ambiguedad

Resultado esperado:
- el repo tiene una sola verdad canonica para chat y scoring
- inference-core-v1/v2 quedan explicitamente fuera del camino principal
```

