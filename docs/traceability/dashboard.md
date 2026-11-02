# Trazabilidad dashboard gerencial

| Requisito | Endpoint | Vista | Tests |
|---|---|---|---|
| KPIs y gráficos | GET /api/v1/dashboard/summary | renderDashboard (apps/desktop/src/renderer/app.js) | tests/i18n-status.test.js |
| Autorización | require_role(admin, dispatcher) | - | services/api tests (403 técnico) |
'''