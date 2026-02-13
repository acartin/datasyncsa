# GUÍA DE AUDITORÍA PARA EL ARQUITECTO

Si la IA entrega código que falla en estos puntos, DEBE ser rechazada inmediatamente:

## 1. Auditoría de Datos (DAL)
- [ ] ¿Hay algún `db.query()` o `session.add()` sin SQL explícito? (FALLO: Capítulo 7/8).
- [ ] ¿Falta el filtro `cliente_id` en alguna query? (FALLO: Capítulo 4).
- [ ] ¿Está usando `OFFSET` en lugar de cursores para paginación? (FALLO: Capítulo 8.6).

## 2. Auditoría de Seguridad e Identidad
- [ ] ¿El frontend intenta leer el `user_id` desde el `localStorage` en lugar del JWT? (FALLO: Capítulo 4.4).
- [ ] ¿Hay lógica de `if/else` basada en roles en los archivos `.js` o `.html`? (FALLO: Capítulo 2.1).

## 3. Auditoría de UI y Contratos
- [ ] ¿La API devuelve HTML en lugar de un JSON estructurado? (FALLO: Capítulo 9).
- [ ] ¿Se están usando colores en hexadecimal (#556ee6) en el código? (FALLO: Capítulo 14).
- [ ] ¿El JSON de respuesta se salta la validación de `ui_schema.py`? (FALLO: Capítulo 11.9).

## 4. Auditoría de Performance
- [ ] ¿El Grid de leads hace múltiples peticiones (N+1) en lugar de una sola vista SQL? (FALLO: Capítulo 6.6).
- [ ] ¿El payload del JSON pesa más de lo necesario por incluir metadata del ORM? (FALLO: Capítulo 8.7).
