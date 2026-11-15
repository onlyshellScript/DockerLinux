# Plan de reportes y KPIs (RF-23, RF-24, RF-25)

## Reportes existentes
- `GET /api/v1/reportes/ordenes` con filtros estado, técnico, zona, fechas, paginación y resumen por estado.

## Exportación (RF-24)
- `formato=xlsx`: genera hoja con columnas ID, Título, Estado, Prioridad, Zona, Técnico, Creado.
- `formato=pdf`: genera tabla básica con ID, Título, Estado, Prioridad.

## KPIs (RF-23/RF-25)
- Reusar `/api/v1/dashboard/summary`, que ya expone KPIs: órdenes activas, completadas, SLA, tiempo medio, técnicos disponibles, alertas de stock.
- KPIs adicionales pendientes de confirmación contra el PDF: tasa de cancelación, tiempo promedio por zona, productividad por técnico.

## Pendientes
- Confirmar lista exacta de KPIs del PDF.
- Añadir gráficos/exportación programada si se requiere.