# AGENTS

## Bootstrap obligatorio por sesion
1. Leer en este orden (base minima):
   - `.agent/RULES.md`
   - `.agent/PY_EXECUTION_MAP.md`
2. Regenerar contexto (`bash .agent/regenerar_contexto.sh`) solo si aplica:
   - faltan `.agent/BRAIN_MAP.md` o `.agent/AI_CONTEXT_PACK.md`
   - cambio de commit vs `BRAIN_MAP.md`
   - solicitud explicita del usuario
3. Leer `BRAIN_MAP.md` y `AI_CONTEXT_PACK.md` solo por secciones necesarias (no carga masiva).

No iniciar implementacion/debug/review sin los pasos anteriores.

## Fuente operativa para ejecutar Python
Usar siempre `.agent/PY_EXECUTION_MAP.md` para decidir:
- host vs contenedor
- comandos base por servicio
- necesidad de rebuild/restart antes de pruebas

Regla de ejecucion:
- No correr `pytest` en host, salvo que el usuario lo pida explicitamente.
- Si la tarea es reorganizacion/documentacion de tests, validar solo con `--help`/`--list` y `python3 -m py_compile`.
- Para pruebas funcionales/reales, usar el contenedor del servicio correspondiente.

## Estructura de pruebas (resumen)
- Service-local: `services/*/tests/...`
- Cross-service: `tests/system`, `tests/smoke-stack`
- Sandbox manual: `tests/sandbox/realtor`, `tests/sandbox/dentist`
