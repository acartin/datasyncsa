# CHANGELOG - Fase 2: Inference Core v2

## Resumen Técnico
Implementación del motor de inferencia y scoring configurable v2 (`inference-core-v2`) desacoplado del hardcode realtor, con scoring dinámico por tipo de lead, caché Redis, persistencia atómica de scorecards y versionado completo.

## Archivos Modificados/Creados

### Servicio inference-core-v2
```
/srv/datasyncsa/services/inference-stack-v2/inference-core-v2/
├── app/
│   ├── __init__.py
│   ├── core/
│   │   └── config.py
│   ├── models/
│   │   ├── chat_v2.py          # Contratos Pydantic v2
│   │   └── database.py         # Modelos SQLAlchemy v2
│   ├── repositories/
│   │   └── scoring_repository.py
│   ├── services/
│   │   ├── cache_service.py    # Caché Redis
│   │   └── scoring_orchestrator.py
│   ├── api/
│   │   └── chat_v2.py          # Endpoints API v2
│   ├── dependencies/
│   │   └── database.py         # Configuración DB async
│   └── __init__.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   └── test_scoring_orchestrator.py
│   ├── integration/
│   │   └── test_api_chat_v2.py
│   └── contract/
├── main.py                     # App FastAPI
├── requirements.txt
└── migrations/
    └── v2/001_initial_scoring_v2.sql  # (Pre-existente de Fase 1)
```

### Migración SQL (Fase 1 - Pre-existente)
```
/srv/datasyncsa/services/inference-stack/inference-core/migrations/v2/001_initial_scoring_v2.sql
```

## Implementaciones Clave

### 1. Core de Scoring Configurable
- **Resolución de modelo activo**: Por `(client_id, lead_type, business_domain)`
- **Criterios dinámicos**: Pilares, pesos, rangos y bandas desde DB
- **Cálculo de scores**: Placeholder para integración con motor real
- **Normalización**: Estrategias configurables por modelo

### 2. Caché de Configuración (Redis)
- **TTL configurable**: 60-300s (default 300s)
- **Invalidación explícita**: Endpoint `/api/v2/cache/invalidate`
- **Cache hit/miss**: Logging detallado
- **Fallback a DB**: Si cache no disponible

### 3. Persistencia Atómica
- **Transacción única**: `scorecard + items + lead.current_scorecard_id`
- **Rollback completo**: Si falla cualquier paso
- **Versionado**: `model_version + prompt_version` en scorecard
- **Auditoría**: `raw_payload` JSONB para trazabilidad

### 4. API Endpoints
- **POST /api/v2/chat**: Chat con `lead_type` obligatorio
- **GET /api/v2/leads/{id}/scorecards/latest**: Último scorecard
- **GET /api/v2/leads/{id}/scorecards/{id}**: Scorecard específico
- **GET /api/v2/scoring/models/active**: Modelo activo por scope
- **POST /api/v2/cache/invalidate**: Invalidación cache
- **GET /api/v2/health**: Health check con estado de cache

### 5. Contratos v2
- **ChatV2Request**: `lead_type` obligatorio, `business_domain` opcional
- **ChatV2Response**: Incluye `scorecard_id` y `scorecard` completo
- **ScorecardV2**: Con `score_items` por criterio
- **ActiveModelResponse**: Estructura completa del modelo activo

## Decisiones de Implementación

### 1. Arquitectura Async
- **SQLAlchemy 2.0+**: Con soporte async completo
- **FastAPI con lifespan**: Manejo lifecycle de conexiones
- **Redis async**: `redis.asyncio` para no bloquear event loop

### 2. Caché de Configuración
- **Redis preferido**: Mejor performance y distribución
- **Clave compuesta**: `inference_v2:active_model:{client}:{lead_type}:{domain}`
- **Fallback controlado**: Logging de errores sin falla total

### 3. Modelo de Datos
- **Mapeo 1:1**: Con migración SQL de Fase 1
- **SQLAlchemy ORM**: Para queries complejos con eager loading
- **JSONB fields**: `raw_payload` y `extracted_data` para flexibilidad

### 4. Manejo de Errores
- **Validación Pydantic**: En request/response contracts
- **HTTPExceptions específicas**: 400, 404, 500 con detalles
- **Logging estructurado**: Con contexto de tenant y lead_type

### 5. Seguridad y Aislamiento
- **Tenant isolation**: Filtrado por `client_id` en todas las queries
- **Scope resolution**: Jerarquía client-specific → global
- **Validación de acceso**: Scorecards solo accesibles por lead owner

## Pruebas Implementadas

### Unit Tests
- **Resolución de modelo**: Cache hit/miss
- **Cálculo de scoring**: Lógica de normalización
- **Transacciones**: Rollback en fallos

### Integration Tests
- **Endpoints API**: Happy paths y casos de error
- **Caché**: Invalidación y TTL
- **Validación de contratos**: Request/response shapes

### Contract Tests (Esqueleto)
- **Schemas Pydantic**: Validación de tipos
- **API contracts**: Compatibilidad forward/backward

## Riesgos Abiertos

### 1. Integración con Motor Real de Scoring
- **Riesgo**: Placeholder scoring vs. motor real de LLM
- **Impacto**: Scores no reflejan realidad de negocio
- **Mitigación**: Interface clara para integración futura

### 2. Performance Redis
- **Riesgo**: Latencia en cache misses frecuentes
- **Impacto**: Degradación p95/p99 de chat
- **Mitigación**: TTL optimizado + monitoring cache hit rate

### 3. Migración de Datos Legacy
- **Riesgo**: Scorecards v2 sin datos históricos
- **Impacto**: Panel muestra datos incompletos
- **Mitigación**: Scripts de migración en Fase 6

### 4. Compatibilidad Bridges
- **Riesgo**: Bridges no envían `lead_type` correctamente
- **Impacto**: Fallo en routing de scoring
- **Mitigación**: Validación estricta + fallback a `realtor`

## Rollback de Fase 2

### Pasos para Revertir
1. **Detener servicios v2**:
   ```bash
   # Detener inference-core-v2
   # Detener bridges v2 si están corriendo
   ```

2. **Reconfigurar bridges**:
   - Apuntar bridges legacy a inference-core original
   - Remover parámetros `lead_type` de requests

3. **Mantener datos v2**:
   - No eliminar tablas v2 (preservar para migración futura)
   - Desactivar feature flag `scoring_v2_enabled`

4. **Verificar operación**:
   - Tests legacy pasando
   - Chat funcionando sin scoring v2
   - Panel muestra datos legacy correctamente

### Scripts de Rollback
```sql
-- Desactivar modelos v2 (no eliminar datos)
UPDATE lead_scoring_models SET is_active = false;

-- Remover referencias current_scorecard_id (opcional)
UPDATE lead_leads SET current_scorecard_id = NULL;
```

## Validación Pendiente

### Requiere Master Architect (Codex)
1. ✅ Arquitectura async y patrones de código
2. ✅ Implementación de caché según RFC
3. ✅ Transaccionalidad atómica de scorecards
4. ✅ Contratos API v2 completos
5. ✅ Pruebas unitarias e integración
6. ⏳ Integración con motor real de scoring/LLM
7. ⏳ Performance testing con carga real
8. ⏳ Security audit de tenant isolation

### Gates de Aceptación
- [x] Unit tests + integration tests verdes
- [x] Pruebas de caché y rollback transaccional
- [ ] E2E chat v2 funcionando para 2 tipos de lead
- [ ] Contratos v2 respetados end-to-end

---

**Estado**: Implementación completa de inference-core-v2 según RFC. Listo para integración con bridges v2 (Fase 3) y motor real de scoring.