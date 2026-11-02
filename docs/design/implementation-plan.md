# SIGOS — Plan de implementación

## Fase A — Tokens y componentes base
1. Crear archivo de tokens en desktop (`styles.css` o `tokens.css`) y tema Flutter.
2. Implementar componentes base compartidos por criterio (botones, inputs, cards, badges).
3. No cambiar contratos de API.

## Fase B — Layout principal y acceso por roles
1. Desktop: shell con sidebar/topbar, login, rutas por rol.
2. Mobile: login, navegación por tabs/drawer, sesión persistida.

## Fase C — Dashboard y órdenes
1. Dashboard con KPIs disponibles y alertas.
2. Lista/filtro/detalle de órdenes.
3. Crear/editar/cancelar orden.
4. Cambio de estado con historial.

## Fase D — Técnicos, calendario, inventario
1. Perfiles y disponibilidad.
2. Calendario de visitas.
3. Materiales y movimientos de stock.

## Fase E — Evidencias y reportes
1. Carga/descarga de evidencias.
2. Observaciones.
3. Reportes básicos y exportación (si entra en MVP).

## Fase F — Móvil técnico
1. Órdenes asignadas.
2. Actualización de estado.
3. Registro de materiales y evidencias.
4. Sync offline push/pull con UI.

## Fase G — Validación
1. Pruebas funcionales por módulo.
2. Pruebas de accesibilidad/responsive.
3. Regresión API/desktop/mobile.
4. Documentar diferencias contra PDF.
