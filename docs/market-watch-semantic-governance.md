# Market Watch Semantic Governance

## Objetivo

Evitar que la capa semantica crezca sin control. Cada dataset debe tener grano,
consumidor, estado y regla de promocion claros antes de convertirse en contrato
de producto.

## Capas y Prefijos

| Prefijo | Proposito | Estabilidad | Regla |
|---|---|---|---|
| `mw_core_*` | Hechos limpios y agregados con grano tecnico claro. | Alta | Base reutilizable; no contiene narrativa ni filtros de UI. |
| `mw_signal_*` | Contratos estables para Signal Engine. | Alta | Puede alimentar senales; no debe depender de BI ni portal. |
| `mw_bi_*` | Datasets de presentacion para API, portal, Superset o Metabase. | Alta | Debe tener consumidor explicito y filtro por cliente antes de salir por API. |
| `mw_exp_*` | Experimentos, prototipos y analisis de validacion. | Baja | Debe tener fecha de revision; no se promete como contrato estable. |
| `mw_deprecated_*` | Compatibilidad temporal antes de eliminar. | Temporal | Debe indicar reemplazo y fecha objetivo de borrado. |

## Estados

| Estado | Significado |
|---|---|
| `active` | En uso por API, portal, Signal Engine o BI. |
| `experimental` | En validacion; puede cambiar sin compatibilidad. |
| `candidate` | Listo para promoverse si un consumidor lo adopta. |
| `deprecated` | No usar en trabajo nuevo. |
| `retired` | Eliminado o pendiente de eliminar en el siguiente corte. |

## Reglas de Creacion

1. Toda vista nueva nace como `mw_exp_*` salvo que ya exista un consumidor claro.
2. Toda vista `mw_bi_*` debe estar documentada con consumidor, grano y filtros.
3. Toda vista experimental debe tener fecha de revision maxima de 30 dias.
4. No crear una vista por pantalla si una vista parametrizable cubre el caso.
5. Las vistas publicadas deben incluir `comment on view` en SQL.
6. El portal nunca consume `mw_core_*` directo; consume API sobre `mw_bi_*` o `mw_exp_*` autorizado.
7. Signal Engine consume `mw_signal_*`, no vistas de BI ni vistas experimentales.

## Catalogo Actual

| Dataset | Capa | Grano | Consumidor | Estado | Notas |
|---|---|---|---|---|---|
| `mw_core_sku_store_observation` | core | SKU/tienda/captura | vistas semanticas | active | Base con precio efectivo, promo, disponibilidad, URL y timestamp. |
| `mw_core_sku_chain_day` | core | SKU/cadena/dia | signal/BI | active | Agrega observaciones por cadena y calcula mejor precio de mercado. |
| `mw_core_brand_chain_day` | core | marca/cadena/dia | signal/BI | active | Resume posicionamiento de marca por cadena. |
| `mw_core_price_change_day` | core | SKU/cadena/dia contra dia previo | signal/BI | active | Detecta cambios diarios de precio. |
| `mw_core_promo_daily` | core | SKU/cadena/dia contra dia previo | signal/BI | active | Detecta entrada, salida o intensidad de promo diaria. |
| `mw_signal_brand_chain_daily` | signal | marca/cadena/dia | Retail Signal Engine | active | Lectura de posicion de precio y visibilidad. |
| `mw_signal_sku_chain_daily` | signal | SKU/cadena/dia | Retail Signal Engine | active | Gap, indice, mejor cadena y accion sugerida. |
| `mw_signal_sku_store_observation` | signal | SKU/tienda/captura | evidencia | active | Evidencia verificable por tienda. |
| `mw_signal_price_change_daily` | signal | evento diario de precio | BI/API | active | Publica cambios de precio diarios. |
| `mw_signal_promo_daily` | signal | evento diario de promo | BI/API | active | Publica eventos de promo diarios. |
| `mw_bi_brand_chain_price_index` | BI | marca/cadena/dia/cliente autorizado | Superset/API futuro | active | Contexto de posicionamiento. |
| `mw_bi_sku_price_drivers` | BI | SKU/cadena/dia/cliente autorizado | Portal/API | active | Drivers y comparacion contra mejor precio observado. |
| `mw_bi_sku_store_price_evidence` | BI | SKU/tienda/captura/cliente autorizado | Portal/API | active | Evidencia de precio, promo y URL. |
| `mw_bi_price_events` | BI | evento precio/promo diario | Superset/API futuro | active | Eventos diarios consolidados. |
| `mw_bi_executive_signal_feed` | BI | senal/cliente/dia | Portal/API | active | Feed ejecutivo desde `mkt_client_signal`. |
| `mw_fact_comparative_listing_snapshot` | legado/fact | listing/captura | transicion | candidate | Existe en BD; no debe ser fuente primaria para producto nuevo. |

## Experimentos Intradia

| Dataset | Capa | Grano | Consumidor | Estado | Revision |
|---|---|---|---|---|---|
| `mw_exp_intraday_sku_chain_capture` | exp | SKU/cadena/run | Portal/API experimental | experimental | 2026-06-27 |
| `mw_exp_intraday_price_movement` | exp | cambio de precio SKU/cadena/run | Portal/API experimental | experimental | 2026-06-27 |
| `mw_exp_intraday_promo_movement` | exp | cambio de promo SKU/cadena/run | Portal/API experimental | experimental | 2026-06-27 |
| `mw_exp_intraday_radar_events` | exp | evento intradia unificado | Portal/API experimental | experimental | 2026-06-27 |

## Promocion de Experimentos

Un `mw_exp_*` puede promoverse a `mw_signal_*` o `mw_bi_*` solo si:

- tiene consumidor real;
- el grano no cambia entre ejecuciones;
- tiene filtro por `client_id` o se consume solo internamente;
- hay una narrativa de negocio clara;
- se documentan umbrales y campos;
- se valida con datos de al menos una campana real.
