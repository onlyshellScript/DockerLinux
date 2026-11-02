# Dashboard gerencial (Administrador)

- Endpoint: `GET /api/v1/dashboard/summary?range=7|14|30&zone=&technician_id=`
- Autorizado para admin y dispatcher; técnico recibe 403.
- KPIs: activas, completadas, SLA, tiempo medio, técnicos disp., alertas stock.
- Gráficos: Chart.js UMD local (`apps/desktop/src/renderer/chart.js`).
- Mapeo de estados/prioridades en `apps/desktop/src/renderer/i18n-status.js`.
- SLA supuesto: órdenes completadas dentro de 7 días (created_at → completed_at/updated_at).
- Campos nuevos en work_orders: zone, installation_type, scheduled_at, completed_at (migración 012be9890960).
'''