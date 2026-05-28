# Market Watch UI Standards

Documento obligatorio para cualquier trabajo en `services/web/market-watch`.

Este archivo existe para mantener el portal Market Watch consistente mientras el producto crece. No es una guia aspiracional: es un contrato operativo para la IA y para cualquier implementacion futura de interfaz.

## 1. Principio Rector

Market Watch ya tiene una base funcional y visual. No se debe regenerar el portal desde cero, reemplazar el diseno actual ni introducir templates externos.

Orden de decision:

1. Auditar lo existente.
2. Reutilizar componentes existentes.
3. Extender patrones existentes.
4. Crear componentes pequenos solo si falta una pieza reutilizable.
5. Implementar pantalla por pantalla.

Si una instruccion nueva empuja a duplicar patrones, romper arquitectura o reescribir innecesariamente, detenerse y proponer la alternativa correcta antes de implementar.

## 2. Arquitectura Frontend

Estructura esperada:

- `app`: rutas, layouts de Next y composicion de paginas.
- `components/ui`: primitivos reutilizables sin conocimiento de dominio.
- `components/portal`: shell, navegacion, topbar, sidebar y composicion general.
- `components/market-watch`: patrones especificos del producto Market Watch.
- `lib`: tipos, clientes API, helpers, mocks explicitos y utilidades compartidas.

Reglas:

- No mover el producto cliente a `services/price-scrapper/web`.
- No reutilizar `services/web/admin-console` ni `services/web/chat-web-renderer` como base del portal.
- No conectar el frontend directo a Postgres.
- Todo dato debe venir de `services/market-watch-api` o de mocks locales explicitamente marcados como temporales.
- El frontend no debe ejecutar ETL, scraping, queries pesadas ni logica de multitenancy autoritativa.

## 3. Componentes Existentes a Preservar

Estos componentes forman parte del estandar actual y no se deben borrar, reemplazar o duplicar sin una justificacion tecnica clara:

- `components/portal/app-shell.tsx`
- `components/portal/sidebar.tsx`
- `components/portal/topbar.tsx`
- `components/portal/module-view.tsx`
- `components/portal/role-simulator.tsx`
- `components/ui/button.tsx`
- `components/ui/card.tsx`
- `components/ui/badge.tsx`
- `components/ui/modal.tsx`
- `components/ui/alert.tsx`
- `components/ui/tabs.tsx`
- `components/ui/theme-toggle.tsx`
- `components/ui/empty-state.tsx`
- `components/ui/loading-state.tsx`
- `components/market-watch/data-grid.tsx`
- `components/market-watch/filter-bar.tsx`
- `components/market-watch/crud-toolbar.tsx`
- `components/market-watch/kpi-card.tsx`
- `components/market-watch/row-actions.tsx`

Antes de crear un componente nuevo, buscar si una pieza existente cubre el caso.

## 4. Sistema Visual

El look debe ser B2B enterprise: sobrio, denso, profesional y orientado a trabajo operativo.

Permitido:

- Layouts compactos y escaneables.
- Tablas, filtros, evidencia, detalle y acciones explicitas.
- Iconos funcionales dentro de botones.
- Estados claros de error, vacio, carga y confirmacion.
- Light/dark extendiendo variables CSS y Tailwind existentes.

Evitar:

- Hero sections.
- Gradientes decorativos.
- Blobs, fondos ornamentales o recursos visuales de marketing.
- Paletas por pantalla.
- Cards decorativas sin proposito operativo.
- Texto visible explicando como usar la UI cuando el patron debe ser evidente.

Tokens obligatorios:

- `background`
- `foreground`
- `card`
- `muted`
- `primary`
- `secondary`
- `border`
- `input`
- `ring`
- `accent`
- `destructive`

No hardcodear colores por componente salvo casos tecnicos muy justificados. Si falta un color semantico, extender el sistema de tokens, no inventar valores locales.

## 5. Tema Light/Dark

El usuario debe poder escoger tema.

Reglas:

- Usar `ThemeToggle` existente.
- Persistir preferencia de tema con el mecanismo ya implementado en el frontend.
- Evitar flashes visuales al cargar tema.
- Extender `app/globals.css` y `tailwind.config.ts` cuando falte un token.
- No crear variantes dark/light manuales por pantalla si el token resuelve el caso.

## 6. Estandar CRUD

Las pantallas CRUD deben compartir el mismo patron. No crear una barra, tabla, filtros o acciones distintas por cada pantalla.

Componentes obligatorios:

- `CrudToolbar` para acciones superiores.
- `DataGrid` para tablas.
- `FilterBar` para filtros cuando aplique.
- `Modal` para crear, editar, ver detalle o acciones contextuales.
- `Alert` y helpers de `lib/feedback.ts` para errores, warnings y confirmaciones.
- `RowActions` para acciones por fila.

Toolbar estandar:

- Buscar.
- Filtros si aplican.
- Guardar si existe edicion por lote.
- Crear si el usuario tiene permiso.
- Acciones contextuales futuras sin duplicar la barra.

Modal estandar:

- Crear abre modal con los campos editables.
- Editar abre modal con valores actuales.
- Ver abre modal de solo lectura.
- Cancelar cierra sin mutar.
- Guardar llama contrato API y muestra feedback inline.

Acciones por fila:

- Ojo: ver detalle.
- Lapiz: editar.
- Trash: baja logica, desactivar o accion destructiva segun contrato.
- Acciones contextuales adicionales por icono, por ejemplo usuarios o permisos.

No usar doble click como accion primaria de edicion. Puede existir como atajo futuro, pero el estandar visible es el icono de lapiz al final del row.

## 7. DataGrid y TanStack Table

El grid estandar del portal es `components/market-watch/data-grid.tsx`.

Decision arquitectonica:

- Si se incorpora TanStack Table, debe quedar encapsulado dentro de `DataGrid` o de una capa base equivalente.
- Las pantallas no deben usar TanStack Table directamente.
- No crear un grid distinto para cada modulo.

Razon:

- Mantener sorting, filtros, paginacion, seleccion, acciones y estados con una sola API visual.
- Evitar que cada pantalla invente convenciones de columnas.
- Facilitar cambios futuros sin tocar todos los modulos.

## 8. Estados, Errores y Feedback

Nunca mostrar JSON crudo de la API al usuario final.

Usar:

- `Alert` para error, warning, success e info.
- `EmptyState` para ausencia de datos.
- `LoadingState` para carga.
- `lib/feedback.ts` para normalizar mensajes.

Reglas:

- Errores de validacion deben mostrarse de forma humana y cerca del formulario.
- Errores de permisos deben explicar que la accion no esta disponible.
- Errores inesperados deben ser sobrios y no exponer trazas, SQL, tokens ni payloads sensibles.
- Las pantallas deben mantenerse dentro del portal; no navegar a una pagina con JSON crudo por errores de formularios.

## 9. Seguridad, Auth y Multitenancy

La seguridad autoritativa vive en backend y base de datos. El frontend solo refleja permisos y estados.

Reglas:

- Login contra `market-watch-api`.
- Sesion mediante cookie `mw_session` y bearer server-side hacia API.
- Logout siempre por POST/form; no usar `Link` ni GET para acciones con side effects.
- No pasar rol activo o cliente activo por query string como fuente autoritativa.
- El simulador de roles solo debe funcionar para admin y debe llamar contrato API de sesion.
- Las pantallas deben ocultar o deshabilitar acciones sin permiso, pero la API debe validar igualmente.
- Todo dataset devuelto por API debe salir filtrado por `client_id` o tenant equivalente.

## 10. Roles, Usuarios, Clientes y Permisos

Usuarios:

- La asignacion de roles se administra desde Usuarios.
- El cliente principal se elige como `client_id` con dropdown.
- No mostrar etiquetas como "roles actuales" o "clientes actuales" si el control ya expresa el estado.
- `username`, `email` e identificadores unicos deben estar protegidos en edicion salvo contrato explicito.

Roles:

- El modal de rol define metadata del rol: id, etiqueta, scope, descripcion y estado si aplica.
- No asignar usuarios desde el modal principal de rol.
- Ver usuarios de un rol mediante accion contextual con icono de usuario y modal con grid de solo lectura.
- Ver permisos de un rol mediante accion contextual con icono de permisos y modal con grid de solo lectura.
- La edicion de permisos debe esperar contrato API claro.

Clientes:

- El CRUD de clientes debe usar el mismo toolbar, grid, modales y feedback.
- Identificadores como `client_key` deben quedar protegidos si son claves unicas.

Integraciones:

- Mientras no exista contrato backend completo, tratar como placeholder operativo.
- No habilitar acciones destructivas sin contrato.

## 11. Identificadores y Campos Protegidos

No habilitar edicion de:

- PKs.
- IDs tecnicos.
- Claves unicas.
- `username`, `email`, `client_key`, role `id` u otros campos usados como contrato estable.

Si una pantalla necesita cambiar un identificador unico, debe existir un caso de uso y contrato explicito. No improvisarlo desde el formulario.

## 12. Navegacion y Flujos

La navegacion principal debe preservar `AppShell`, `Sidebar` y `Topbar`.

Reglas:

- La ruta senal -> detalle -> evidencia debe ser explicita y controlada.
- No esconder flujos centrales detras de acciones ambiguas.
- No crear landings de marketing dentro del portal autenticado.
- Mantener densidad profesional: tablas, filtros, detalle y evidencia son el centro del producto.

## 13. Formularios

Reglas:

- Usar modales para create/edit/view en CRUD administrativo.
- Validacion basica en frontend cuando sea clara, por ejemplo longitud minima de password.
- La API sigue siendo la fuente final de validacion.
- No duplicar textos obvios como "campos protegidos" si el control deshabilitado ya lo comunica.
- Botones de formulario: Guardar/Crear/Actualizar y Cancelar segun contexto.
- Mantener labels claros, sin microcopy excesivo.

## 14. Organizacion de Nuevos Componentes

Crear en `components/ui` si:

- Es un primitivo reusable sin dominio: modal, alert, tabs, button, input futuro, select futuro.

Crear en `components/portal` si:

- Pertenece al shell, navegacion, sesion, topbar, sidebar o composicion general del portal.

Crear en `components/market-watch` si:

- Representa un patron de producto: grid, toolbar CRUD, filtros, tabla de senales, panel de detalle, tarjetas KPI.

Crear en `lib` si:

- Es cliente API, normalizador de errores, helper de URLs, tipos o mocks temporales.

No crear archivos enormes. Si un componente crece demasiado, dividir por responsabilidad, no por capricho visual.

## 15. Dependencias UI

No instalar librerias visuales grandes sin justificar.

Permitido con criterio:

- Librerias funcionales pequenas si resuelven un problema real.
- TanStack Table para grids controlados, encapsulado dentro del `DataGrid`.
- Iconos ya presentes o libreria de iconos existente en el proyecto.

No permitido:

- Templates UI externos.
- Kits completos que reemplacen el sistema actual.
- Dependencias que impongan una estetica ajena al portal.

## 16. Mocks y Contratos API

Mientras una API no este completa:

- El mock debe estar marcado explicitamente como temporal.
- No mezclar mocks silenciosos con datos reales sin indicarlo en codigo.
- Preferir contratos simples y estables.
- Al activar un contrato real, retirar o aislar el mock para evitar confusion.

Para PATCH/UPDATE:

- Crear contrato backend antes de habilitar edicion real.
- No simular exito si la API no persiste.
- Mostrar acciones deshabilitadas o feedback claro cuando falte contrato.

## 17. Validacion Minima

Si se cambia `services/web/market-watch`:

- Revisar `package.json` local.
- Ejecutar build, lint o smoke HTTP segun disponibilidad.
- Si corre en compose, usar el servicio `market-watch-web`.

Si se cambia `services/market-watch-api`:

- Usar contenedor `market-watch-api` cuando exista.
- Hacer rebuild si el codigo se copia a imagen.
- Compilar Python dentro del contenedor segun `.agent/PY_EXECUTION_MAP.md`.

Si se cambia `docker-compose.yml`:

- Ejecutar `docker compose config`.

Si se cambia `.agent`:

- Revisar diff.
- No requiere Python salvo scripts shell.

## 18. Checklist Antes de Implementar UI

Antes de tocar UI:

1. Leer `AGENTS.md`, `.agent/RULES.md`, `.agent/PY_EXECUTION_MAP.md` y este documento.
2. Revisar componentes existentes.
3. Confirmar si la pantalla es CRUD, dashboard, detalle, evidencia o configuracion.
4. Elegir el patron existente correspondiente.
5. Confirmar fuente de datos: API o mock explicito.
6. Confirmar permisos esperados.
7. Implementar cambios pequenos.
8. Validar minimamente.
9. Reportar que se reutilizo, que se creo y por que.

## 19. Checklist de Rechazo

Rechazar o detenerse antes de implementar si el cambio propone:

- Reescribir el portal completo.
- Reemplazar AppShell, Sidebar, Topbar, Button, Card, Badge, DataGrid o CrudToolbar sin justificacion.
- Crear un grid nuevo por pantalla.
- Conectar frontend a Postgres.
- Saltarse API para datos cliente.
- Hardcodear colores fuera del sistema de tokens.
- Mostrar JSON crudo de errores.
- Usar GET/Link para logout o mutaciones.
- Exponer seleccion de tenant/rol como autoridad de seguridad en frontend.
- Meter estetica marketing en pantallas operativas.
- Habilitar edicion o delete sin contrato backend.
