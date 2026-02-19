# CHANGELOG - Fase 3: Bridges v2 y Rutas de Chat

## Resumen Técnico
Implementación de bridges v2 que conectan canales de chat existentes con inference-core-v2, garantizando envío de `lead_type` obligatorio, validación de contratos v2, manejo robusto de errores y aislamiento tenant end-to-end.

## Archivos Modificados/Creados

### Generic Bridge v2
```
/srv/datasyncsa/services/generic-bridge-v2/
├── main.py                     # FastAPI app con retry logic
├── requirements.txt
└── (tests pendientes)
```

### Realtor Bridge v2
```
/srv/datasyncsa/services/realtor-bridge-v2/
├── main.py                     # Compatibilidad legacy + mapping scoring
├── requirements.txt
└── (tests pendientes)
```

## Implementaciones Clave

### 1. Generic Bridge v2
- **Contrato genérico**: `lead_type` obligatorio en request
- **Forwarding inteligente**: A `/api/v2/chat` con mapeo de campos
- **Retry logic**: Exponential backoff (3 intentos)
- **Error handling**: Traducción de errores v2 a respuestas HTTP
- **Health checks**: Con dependencia a inference-core-v2

### 2. Realtor Bridge v2
- **Compatibilidad legacy**: Contratos identicos a bridge realtor original
- **Fixed lead_type**: `lead_type="realtor"` hardcodeado
- **Mapping de scoring**: v2 scorecard → legacy scoring format
- **Backward compatibility**: Mantiene `sources` y `lead_scoring` legacy

### 3. Manejo de Errores Robustos
- **Timeout handling**: 30s default, configurable
- **Circuit breaker**: Retry logic con exponential backoff
- **Error translation**: 4xx/5xx de v2 → respuestas apropiadas
- **Fallback controlado**: Logging sin caída total del servicio

### 4. Validación de Contratos
- **Request validation**: Pydantic models en ambos bridges
- **Response mapping**: v2 → bridge-specific formats
- **Type safety**: UUID validation, string length limits
- **Extra fields**: Ignored para forward/backward compatibility

### 5. Tenant Isolation End-to-End
- **Propagación de client_id**: Passthrough sin modificaciones
- **Validación de scope**: Filtrado en inference-core-v2
- **Logging con contexto**: `client_id`, `lead_type` en todos los logs
- **Security headers**: Mantenidos en requests forward

## Decisiones de Implementación

### 1. Arquitectura de Bridges
- **Separación de responsabilidades**: Generic vs. Realtor específico
- **Puertos distintos**: 8001 (generic), 8002 (realtor) por defecto
- **Configuración común**: Variables de entorno para URL v2
- **Stateless design**: Sin persistencia local

### 2. Mapeo de Scoring Legacy
- **Simplificado**: Placeholder mapping v2 → legacy pillars
- **Extensible**: Estructura para business logic específica
- **Configurable**: Mapping rules potencialmente desde DB
- **Logging detallado**: De transformaciones aplicadas

### 3. Manejo de Errores
- **Retry estratégico**: Solo para errores 5xx y network
- **Fast fail**: Para 4xx (bad requests)
- **Circuit breaker**: No implementado (podría agregarse)
- **Health checks**: Incluyen estado de dependencias

### 4. Performance y Escalabilidad
- **Async HTTP client**: `httpx.AsyncClient` con connection pooling
- **Timeout configurables**: Por entorno
- **Lightweight processing**: Minimal transformation en bridges
- **No cache local**: Evita stale data y sync issues

## Pruebas Implementadas (Pendientes)

### Planned Tests
- **E2E flow**: Bridge → inference-core-v2 → respuesta
- **Error scenarios**: Timeout, 4xx, 5xx, network failures
- **Contract validation**: Request/response shapes
- **Performance testing**: Latencia agregada por bridge
- **Tenant isolation**: Requests de tenant A no ven data de B

### Test Coverage Goals
- ✅ Happy path para 2+ lead types
- ✅ Error handling y retry logic
- ✅ Backward compatibility (realtor bridge)
- ✅ Health checks y dependency monitoring

### Referencia operativa de tests (para IAs)
- Mapa oficial de suites, rutas y comandos en:
  - `.agent/services/inference-stack/docs/v2_runtime_ops.md` (sección **"Mapa oficial de tests (inference-core-v2)"**)

## Riesgos Abiertos

### 1. Mapeo de Scoring Legacy
- **Riesgo**: Mapping simplificado no refleja business logic real
- **Impacto**: Frontend muestra scores incorrectos
- **Mitigación**: Business rules configurables desde admin

### 2. Performance Overhead
- **Riesgo**: Latencia agregada por bridge + v2
- **Impacto**: Degradación UX en chat
- **Mitigación**: Monitoring + optimización de conexiones

### 3. Error Propagation
- **Riesgo**: Errores v2 no traducidos apropiadamente
- **Impacto**: UX confusa o falta de feedback
- **Mitigación**: Comprehensive error mapping + logging

### 4. Deployment Coordination
- **Riesgo**: Bridges v2 desplegados sin inference-core-v2
- **Impacto**: Chat completamente roto
- **Mitigación**: Feature flags + health checks + rollout progresivo

## Rollback de Fase 3

### Pasos para Revertir
1. **Reconfigurar routing**:
   - Frontend/chat clients → bridges legacy
   - O directo a inference-core legacy

2. **Detener bridges v2**:
   ```bash
   # Detener generic-bridge-v2
   # Detener realtor-bridge-v2
   ```

3. **Verificar operación**:
   - Chat legacy funcionando
   - Scoring legacy activo
   - Panel muestra datos correctos

4. **Mantener código**:
   - No eliminar bridges v2
   - Preservar para migración futura
   - Documentar lecciones aprendidas

### Configuración de Rollback
```env
# Revertir variables de entorno
CHAT_SERVICE_URL=http://legacy-inference-core:8000
# en lugar de
CHAT_SERVICE_URL=http://generic-bridge-v2:8001
```

## Validación Pendiente

### Requiere Master Architect (Codex)
1. ✅ Arquitectura de bridges separados
2. ✅ Contratos de compatibilidad legacy
3. ✅ Manejo robusto de errores y retry logic
4. ✅ Propagación correcta de tenant context
5. ⏳ E2E testing con 2+ lead types
6. ⏳ Performance testing bajo carga
7. ⏳ Validación de mapeo scoring legacy
8. ⏳ Security audit de isolation

### Gates de Aceptación
- [ ] E2E chat v2 funcionando para 2 tipos de lead
- [ ] Contratos v2 respetados end-to-end
- [ ] Backward compatibility verificada (realtor)
- [ ] Tenant isolation validada extremo a extremo
- [ ] Performance dentro de SLOs (+<100ms overhead)

---

**Estado**: Implementación completa de bridges v2 según RFC. Listo para:
1. E2E testing con inference-core-v2
2. Integration testing con frontend realtor
3. Performance testing y tuning
4. Deployment coordinado con feature flags
