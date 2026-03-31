# Sandbox Tests

Scripts manuales y baterias exploratorias que pegan contra servicios ya levantados.

No son la suite de CI principal. Sirven para smoke manual, regresion conversacional y validacion rapida de flujos reales.

## Cuando usar sandbox

- Cuando quieres ver la respuesta real del stack sin montar un test formal de servicio.
- Cuando necesitas reproducir una conversacion multi-turno completa.
- Cuando quieres validar wording, cards, memoria o traces contra el runtime vivo.
- Cuando estas afinando prompts, policies o reglas de vertical y necesitas feedback rapido.

## Estructura

- `tests/sandbox/realtor/`: simuladores y baterias para el vertical realtor.
- `tests/sandbox/dentist/`: simuladores legacy del vertical dentist.
- `tests/sandbox/*.py`: wrappers viejos de compatibilidad.

## Realtor

### `simulate_chat_realtor.py`

Uso principal:

- Smoke manual de una conversacion realtor.
- Sirve para probar un prompt o cambio puntual contra `ai-runtime`.
- Puede correrse con mensaje unico, modo interactivo o con trace completo.

Comandos utiles:

- `python3 tests/sandbox/realtor/simulate_chat_realtor.py`
- `python3 tests/sandbox/realtor/simulate_chat_realtor.py --query "Busco casa en Heredia"`
- `python3 tests/sandbox/realtor/simulate_chat_realtor.py --interactive`
- `python3 tests/sandbox/realtor/simulate_chat_realtor.py --full-trace`

### `simulate_multichat_realtor.py`

Uso principal:

- Ejecuta varios escenarios realtor predefinidos.
- Bueno para regresion manual rapida de cards, follow-ups y continuidad conversacional.

Comando util:

- `python3 tests/sandbox/realtor/simulate_multichat_realtor.py --all`

### `realtor_v3_regression_battery.py`

Uso principal:

- Bateria heuristica mas densa para detectar regresiones de routing, memoria, cards y redaccion.
- Apunta al camino legacy `/api/v3/chat`, asi que sirve mas como referencia historica o comparativa que como gate del runtime nuevo.

Comandos utiles:

- `python3 tests/sandbox/realtor/realtor_v3_regression_battery.py`
- `python3 tests/sandbox/realtor/realtor_v3_regression_battery.py --scenario inventory_active_search`
- `python3 tests/sandbox/realtor/realtor_v3_regression_battery.py --json-out /tmp/realtor_battery.json`

### `run_generated_conversation_suite.py`

Uso principal:

- Runner JSON-driven para suites conversacionales contra `ai-runtime`.
- Es la opcion mas clara cuando quieres dejar regresiones reproducibles sin escribir codigo Python nuevo.
- Puede leer `turn-traces` si `INTERNAL_API_TOKEN` esta disponible.

Comandos utiles:

- `python3 tests/sandbox/realtor/run_generated_conversation_suite.py --suite tests/sandbox/realtor/generated_suite_01.json`
- `python3 tests/sandbox/realtor/run_generated_conversation_suite.py --suite tests/sandbox/realtor/generated_suite_pending_decisions.json`
- `python3 tests/sandbox/realtor/run_generated_conversation_suite.py --suite tests/sandbox/realtor/regression_suite_01.json --stop-on-failure`

### `generated_suite_01.json`

Uso principal:

- Suite amplia de conversaciones generadas.
- Cubre presupuesto, referencias, memoria, FAQ, policy y follow-ups.
- Es buena regresion general despues de cambios en planner, policies o synthesis.

Escenarios representativos:

- `hard_budget_no_exact_curridabat`
- `memory_name_roundtrip`
- `inventory_probe_count`
- `ordinal_focus_second`

### `generated_suite_pending_decisions.json`

Uso principal:

- Regresion puntual nueva para el flujo de `pending_decision`.
- Verifica que, despues de una busqueda sin resultados exactos, un `"Si"` no dispare una pseudo-continuacion vaga ni invente resultados.
- Valida que el runtime pida de forma explicita escoger que flexibilizar: `precio`, `zona` u `otro criterio`.

Escenario cubierto:

- `search_relaxation_choice_after_no_results`

Comando recomendado:

- `python3 tests/sandbox/realtor/run_generated_conversation_suite.py --suite tests/sandbox/realtor/generated_suite_pending_decisions.json`

### `regression_suite_01.json`

Uso principal:

- Suite de regresion curada manualmente.
- Util para mantener escenarios historicos o bugs ya conocidos bajo control.

### `manual_suite_01.json`

Uso principal:

- Espacio para conversaciones manuales ad hoc.
- Sirve para guardar sesiones de QA que no ameritan entrar todavia en la suite amplia.

### `generated_conversation_suite.template.json`

Uso principal:

- Plantilla base para crear suites nuevas.
- Reutilizala cuando necesites una bateria JSON sin arrancar desde cero.

### `generated_conversation_suite.schema.json`

Uso principal:

- Schema del formato JSON de las suites.
- Sirve para validar estructura y evitar suites mal formadas.

### `generated_conversation_suite_prompt.md`

Uso principal:

- Guia de autoria para pedir o generar nuevas suites conversacionales.
- Util cuando quieras expandir cobertura sin improvisar el formato.

### `test_gemini_latency_realtor_contract.py`

Uso principal:

- Benchmark/chequeo puntual de latencia y contrato realtor con Gemini.
- No es el gate funcional principal del runtime.

Comando util:

- `RUN_GEMINI_BENCH=1 python3 -m pytest -q tests/sandbox/realtor/test_gemini_latency_realtor_contract.py -s`

## Dentist

### `simulate_chat_dentist.py`

Uso principal:

- Simulador simple para conversaciones odontologicas en el stack legacy dentist.
- Sirve para revisar scoring y extraccion de datos en un flujo viejo.

Comandos utiles:

- `python3 tests/sandbox/dentist/simulate_chat_dentist.py`
- `python3 tests/sandbox/dentist/simulate_chat_dentist.py --auto`
- `python3 tests/sandbox/dentist/simulate_chat_dentist.py --query "Hola"`

### `simulate_multichat_dentist.py`

Uso principal:

- Ejecuta escenarios odontologicos predefinidos.
- Evalua perfiles de paciente con distintas señales de urgencia, intencion y solvencia.

Comandos utiles:

- `python3 tests/sandbox/dentist/simulate_multichat_dentist.py --list`
- `python3 tests/sandbox/dentist/simulate_multichat_dentist.py --conversation 1`
- `python3 tests/sandbox/dentist/simulate_multichat_dentist.py --all`

## Regla practica

- Si quieres validar una sola conversacion: `simulate_chat_*`.
- Si quieres recorrer varios escenarios manuales: `simulate_multichat_*`.
- Si quieres una regresion reproducible en JSON contra `ai-runtime`: `run_generated_conversation_suite.py`.
- Si quieres cobertura puntual del bug de decisiones pendientes: `generated_suite_pending_decisions.json`.

Estos scripts no bloquean CI salvo que se agreguen explicitamente a un job.
