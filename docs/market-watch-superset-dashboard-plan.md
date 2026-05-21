# Market Watch Superset Dashboard Plan

## Dashboard Inicial

```text
MW Product | Pricing | Price Intelligence
```

Este dashboard usa vistas de presentacion `mw_superset_*`. No debe construirse directamente sobre facts, runs, listings ni megavistas semanticas internas.

## Regla Rectora

Antes de proponer o crear cualquier chart, validar:

1. Que pregunta de negocio responde.
2. En que tab vive.
3. Que decision habilita.
4. Por que ese tipo visual es adecuado.
5. Que grano usa.

Si no se puede responder claramente, no crear el chart.

Reglas de clasificacion:

```text
Marca/cadena = indice, ranking y lectura agregada.
SKU = precio absoluto, brecha y evidencia.
Eventos = cambios en el tiempo.
Ejecutivo = senales resumidas y priorizacion.
```

No mezclar precios absolutos de surtidos distintos en vistas marca/cadena, porque puede producir lecturas inconsistentes.

## Tabs

### 1. Executive Signals

Dataset:

```text
mw_superset_senales_ejecutivas
```

Objetivo:

- mostrar cambios relevantes
- priorizar alertas
- dar lectura ejecutiva rapida
- responder que cambio, donde, que tan importante es

Charts iniciales:

```text
MW Product | Executive | Latest Signals
MW Product | Executive | Signals by Severity
```

Grano permitido:

```text
senal/evento ejecutivo
```

Tipos visuales permitidos:

```text
tabla corta
cards/KPIs
barra simple por severidad
```

No usar:

```text
pivots complejas
tablas crudas historicas
precio absoluto por marca/cadena
```

### 2. Brand & Chain Benchmark

Dataset:

```text
mw_superset_benchmark_marca_cadena
```

Objetivo:

- comparar marcas por cadena
- entender posicionamiento de precio
- detectar cadenas agresivas o premium
- responder donde esta posicionada cada marca por cadena

Charts iniciales:

```text
MW Product | Pricing | Brand Chain Price Index Matrix
MW Product | Pricing | Brand Chain Price Index
```

Grano permitido:

```text
fecha/periodo + campana + marca + cadena
```

Metricas permitidas:

```text
indice_precio
diferencia_vs_mercado_pct
ranking_precio
visibilidad_pct
lectura_precio
```

Tipos visuales permitidos:

```text
pivot marca x cadena
barra agrupada marca/cadena
tabla resumen pequena por marca/cadena
```

No usar:

```text
precio_promedio_colones como comparativo principal de marca/cadena
tablas SKU
eventos historicos
```

Razon:

El precio absoluto por marca/cadena mezcla surtidos, presentaciones y cobertura distinta. Para valores en colones usar la tab `SKU Detail`.

### 3. SKU Detail

Dataset:

```text
mw_superset_oportunidades_sku
```

Objetivo:

- revisar productos especificos
- detectar brechas de precio
- priorizar oportunidades comerciales
- responder que SKUs explican el benchmark

Charts iniciales:

```text
MW Product | Pricing | Top SKU Price Opportunities
MW Product | Pricing | SKU Price Gap Table
```

Grano permitido:

```text
fecha/periodo + campana + producto + marca + cadena
```

Metricas permitidas:

```text
precio_promedio
mejor_precio_mercado
brecha_colones
brecha_pct
indice_precio
ranking_precio
lectura_precio
accion_sugerida
```

Tipos visuales permitidos:

```text
tabla ejecutiva
ranking top N
barra horizontal de brecha por SKU
```

No usar:

```text
matrices grandes sin top N
campos tecnicos
promedios de surtido por marca
```

### 4. Events

Dataset:

```text
mw_superset_eventos
```

Objetivo:

- auditar eventos de precio y visibilidad
- alimentar alertas y reportes
- revisar cambios historicos
- responder que cambio, cuando y donde

Charts iniciales:

```text
MW Product | Alerts | Event Timeline
MW Product | Alerts | Event Detail Table
```

Grano permitido:

```text
evento
```

Tipos visuales permitidos:

```text
tabla de eventos
linea/serie temporal de conteo de eventos
barra por tipo_evento o severidad
```

No usar:

```text
benchmarks agregados de marca/cadena
tablas de precio SKU sin cambio detectado
```

## Filtros Globales Recomendados

```text
cliente
campana
marca
cadena
semana_inicio
mes_inicio
fecha
es_ultima_fecha
```

Para charts flexibles, usar filtros globales de `fecha`, `semana_inicio` o `mes_inicio` y no fijar `es_ultima_fecha` dentro del chart. Usar `es_ultima_fecha = true` solo en charts cuyo nombre indique explicitamente `Latest`.

## Regla De Construccion

Cada chart debe responder una pregunta de negocio antes de elegir el tipo visual.

Ejemplos:

```text
Que marca esta mas cara por cadena?
Que productos tienen brecha alta contra el mejor precio?
Que cambios relevantes ocurrieron esta semana?
Donde esta una marca sobre mercado?
```

Evitar charts basados en columnas tecnicas como `run_key`, `date_key`, `listing_key`, `market_min_price_amount` o nombres internos. Si una metrica tecnica es necesaria, debe venir traducida desde una vista `mw_superset_*`.

## Estado Actual

Chart aceptado:

```text
MW Product | Pricing | Brand Chain Price Index Matrix
```

Tab:

```text
Brand & Chain Benchmark
```

Dataset:

```text
mw_superset_benchmark_marca_cadena
```

Pregunta:

```text
Como se posiciona cada marca por cadena en el periodo seleccionado?
```

Decision que habilita:

```text
identificar cadenas donde una marca esta agresiva, alineada, sobre mercado o premium
```

Chart eliminado:

```text
MW Product | Pricing | Brand Chain Average Price Matrix
```

Motivo:

```text
precio promedio absoluto por marca/cadena mezcla surtidos y presentaciones; se presta a lectura inconsistente
```
