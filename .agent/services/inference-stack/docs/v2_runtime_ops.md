# Inference Stack V2 Runtime Ops

## Objetivo
Referencia rápida para operar servicios v2 en DataSyncSA y evitar ambigüedad en futuras ejecuciones IA.

## Servicios Docker Compose (v2)
- `inference-core-v2` -> contenedor `${ENV_PREFIX}-backend-inference-v2`
- `semantic-adapter-v2` -> contenedor `${ENV_PREFIX}-backend-semantic-v2`
- `generic-bridge-v2` -> contenedor `${ENV_PREFIX}-web-generic-bridge-v2`
- `realtor-bridge-v2` -> contenedor `${ENV_PREFIX}-web-realtor-bridge-v2`

## Puertos esperados (`.env`)
- `INFERENCE_V2_PORT=8091`
- `SEMANTIC_V2_PORT=8092`
- `GENERIC_BRIDGE_V2_PORT=8093`
- `REALTOR_BRIDGE_V2_PORT=8094`

## Levantar servicios v2
```bash
docker compose up -d --build inference-core-v2 semantic-adapter-v2 generic-bridge-v2 realtor-bridge-v2
```

## Verificar estado
```bash
docker compose ps --status running
```

## Ejecutar pruebas de `inference-core-v2` (pytest en contenedor)
`pytest` se instala en la imagen de `inference-core-v2` mediante:
- `services/inference-stack-v2/inference-core-v2/requirements-dev.txt`
- `services/inference-stack-v2/inference-core-v2/Dockerfile`

Comando:
```bash
docker compose exec -T inference-core-v2 env PYTHONPATH=/app pytest -q tests
```

## Mapa oficial de tests (`inference-core-v2`)
Ubicación base:
- `services/inference-stack-v2/inference-core-v2/tests/`

Suites activas actuales (14 tests totales):
- `services/inference-stack-v2/inference-core-v2/tests/integration/test_api_chat_v2.py` (9 tests)
- `services/inference-stack-v2/inference-core-v2/tests/unit/test_scoring_orchestrator.py` (5 tests)

Notas importantes para IAs:
- No existe `tests/smoke/` en `inference-core-v2` al día de hoy.
- El test usado como smoke funcional mínimo está en integración: `test_root_endpoint`.
- Existe carpeta `tests/contract/`, pero actualmente sin casos ejecutables.

Comandos de ejecución por suite:
```bash
# Integración (9)
docker compose exec -T inference-core-v2 env PYTHONPATH=/app pytest -q tests/integration/test_api_chat_v2.py

# Unitarios (5)
docker compose exec -T inference-core-v2 env PYTHONPATH=/app pytest -q tests/unit/test_scoring_orchestrator.py
```

## Notas de integración
- `generic-bridge-v2` y `realtor-bridge-v2` consumen `INFERENCE_V2_URL=http://inference-core-v2:8000`.
- Scoring v2 se resuelve por `vertical_id` (FK `lead_client_verticals.id`) en `lead_scoring_models`.
- El `client_id` solo se usa para resolver el vertical del tenant (`lead_clients.vertical_id`).
