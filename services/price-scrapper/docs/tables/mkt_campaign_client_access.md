# `mkt_campaign_client_access`

## Qué es
Relación autorizativa entre campañas de monitoreo y clientes del portal.

Cada fila indica que un `auth_clients.id` puede ver o administrar una campaña específica.

## Qué script correr
No tiene scraper propio.

Se mantiene por seed o carga administrativa desde el portal Market Watch.

## Qué hace
- vincula `campaign_id` con `client_id` de `auth_clients`
- define `access_role` como `viewer`, `owner` o `admin`
- permite marcar una campaña como default para un cliente
- permite vigencia con `valid_from` y `valid_to`
- permite activar/desactivar acceso sin borrar la campaña

## Tipo de actualización
`manual / upsert administrativo`

## Frecuencia recomendada
Baja o media.

Cada vez que se habilita, deshabilita o cambia el acceso de un cliente a una campaña.

## Notas
- es la fuente oficial de multitenancy para campañas/canastas
- reemplaza cualquier intento de guardar cliente propietario en `mkt_dim_campaign` o `mkt_run`
- una campaña puede tener varios clientes autorizados
- los facts y runs no guardan `client_id`; se publican por cliente a través de esta tabla
