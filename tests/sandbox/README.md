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

### `run_realtor_conversation_suite.py`

Uso principal:

- Runner JSON-driven para suites conversacionales contra `ai-runtime`.
- Es la opcion mas clara cuando quieres dejar regresiones reproducibles sin escribir codigo Python nuevo.
- Puede leer `turn-traces` si `INTERNAL_API_TOKEN` esta disponible.
- Sin `--suite`, corre por defecto el pack canonico realtor.

Comandos utiles:

- `python3 tests/sandbox/realtor/run_realtor_conversation_suite.py --list-suites`
- `python3 tests/sandbox/realtor/run_realtor_conversation_suite.py --stop-on-failure`
- `python3 tests/sandbox/realtor/run_realtor_conversation_suite.py --suite tests/sandbox/realtor/manual_suite_01.json`

### `realtor_regression_suite.json`

Uso principal:

- Suite canonica realtor.
- Combina regresiones de busqueda/routing con mapa de momentos de scoring/captura.
- Es el pack que conviene correr cuando quieres validar "que todo siga bien" en el vertical.

### `realtor_generated_suite_01.json`

Uso principal:

- Suite exploratoria amplia para evaluar respuestas del bot sobre casos variados.
- Sirve para QA conversacional, tono, referencias, memoria, FAQ, policy y follow-ups.
- No reemplaza el pack canonico de regresion; es complemento de evaluacion.

### `manual_suite_01.json`

Uso principal:

- Espacio para conversaciones manuales ad hoc.
- Sirve para guardar sesiones de QA que no ameritan entrar todavia en la suite amplia.

### `realtor_conversation_suite.template.json`

Uso principal:

- Plantilla base para crear suites nuevas.
- Reutilizala cuando necesites una bateria JSON sin arrancar desde cero.

### `realtor_conversation_suite.schema.json`

Uso principal:

- Schema del formato JSON de las suites.
- Sirve para validar estructura y evitar suites mal formadas.

### `realtor_conversation_suite_prompt.md`

Uso principal:

- Guia de autoria para pedir o generar nuevas suites conversacionales.
- Util cuando quieras expandir cobertura sin improvisar el formato.

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
- Si quieres una regresion reproducible en JSON contra `ai-runtime`: `run_realtor_conversation_suite.py`.
- Si quieres cobertura funcional integral en realtor: `run_realtor_conversation_suite.py --stop-on-failure`.

Estos scripts no bloquean CI salvo que se agreguen explicitamente a un job.
