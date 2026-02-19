# CHANGELOG - Fase 4: Admin Backend v2 (ESTADO: INCOMPLETO)

## Resumen de Estado
La Fase 4 (Admin backend v2) según el RFC requiere backend para scoring dinámico y configuración de modelos, pero NO está completa. Este documento documenta el estado actual y los faltantes.

## Análisis del Estado Actual

### ✅ Implementado (Legacy)
1. **Backend admin existente**: `services/web/admin-console/backend/app/modules/leads/`
2. **Endpoints legacy**: Grid de leads con scoring hardcodeado realtor
3. **Estructura actual**: Usa `lead_scoring_definitions` y columnas fijas:
   - `score_engagement`, `score_finance`, `score_timeline`, `score_match`, `score_info`
   - `eng_def_id`, `fin_def_id`, `timeline_def_id`, `match_def_id`, `info_def_id`
4. **Contrato UI actual**: Columnas fijas con pilares realtor

### ❌ Faltantes para Fase 4 (RFC)
1. **Endpoint de leads con scoring dinámico**:
   - No existe endpoint v2 en admin backend para scoring dinámico
   - El endpoint actual `/leads/me/data` usa SQL legacy

2. **Endpoint de detalle de lead con desglose por `score_items`**:
   - El endpoint actual `/leads/{lead_id}` no consulta `lead_score_items`
   - No integra scoring v2 dinámico

3. **CRUD backend para modelos/criterios/bandas**:
   - No existen endpoints para CRUD de `lead_scoring_models`, `lead_scoring_criteria`, `lead_scoring_bands`

4. **Contratos SDUI para `scoring_schema` y `scoring_values`**:
   - No existe contrato Pydantic para scoring dinámico en admin backend
   - El frontend usa config fija `LEADS_GRID_CONFIG_FULL`

## Arquitectura GAP

### Backend Admin Actual (Legacy)
```
/admin-console/backend/app/modules/leads/
├── router.py          # Endpoints con scoring hardcodeado
└── service.py         # SQL con joins a lead_scoring_definitions
```

### Backend v2 Requerido (RFC)
```
/admin-console/backend/app/modules/leads_v2/
├── router.py          # Endpoints con scoring dinámico
├── service.py         # SQL con joins a lead_scorecards/items
├── models.py          # Contratos SDUI scoring_schema
└── scoring_config/    # CRUD para modelos/criterios/bandas
```

## Dependencias Bloqueantes

### 1. Feature Flags Incompletos
- `scoring_v2_enabled`: ✅ Existe en inference-core-v2
- `admin_dynamic_scoring_ui`: ❌ NO existe
- `legacy_scoring_read_compat`: ❌ NO existe

### 2. Migración de Datos
- Tablas v2 creadas: ✅ (001_initial_scoring_v2.sql)
- Datos migrados: ❌ NO
- Scripts de migración: ❌ NO

### 3. Contratos SDUI
- `scoring_schema`: ❌ NO existe
- `scoring_values`: ❌ NO existe
- Transformación v2→SDUI: ❌ NO implementada

## Riesgos de Progresión sin Fase 4

1. **Fase 5 no puede implementarse**: El frontend dinámico necesita backend v2
2. **Contratos incompatibles**: Frontend espera estructura fija, backend v2 tiene estructura dinámica
3. **Migración imposible**: No hay camino para transición gradual

## Recomendaciones

### Opción A: Implementar Fase 4 primero
1. Crear endpoints admin v2 paralelos a legacy
2. Implementar CRUD de configuración de scoring
3. Crear contratos SDUI dinámicos
4. Activar feature flags faltantes

### Opción B: Adaptar Fase 5 para trabajar con backend actual
1. Modificar frontend para consumir scoring dinámico de inference-core-v2
2. Usar endpoints `/api/v2/scoring/models/active` para obtener schema
3. Mantener compatibilidad con backend legacy temporalmente

### Opción C: Pausar y escalar a Master Architect
- BLOCKED hasta que Fase 4 sea completada
- Documentar dependencias críticas
- Solicitar aprobación para modificar scope

## Gates de Aceptación Fase 4 (RFC)
- [ ] Contract tests SDUI y seguridad/RBAC verdes
- [ ] Endpoints leads con scoring dinámico
- [ ] Endpoints detalle con score_items
- [ ] CRUD backend para configuración
- [ ] Contratos SDUI dinámicos

---

**Estado**: BLOCKED - Fase 4 incompleta según RFC. Fase 5 no puede proceder sin backend admin v2.