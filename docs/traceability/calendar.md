# SIGOS — Trazabilidad calendario (HU-CAL)

| HU | Endpoint | Vista | Test |
|---|---|---|---|
| HU-CAL-03 | GET /api/v1/calendar/events, /calendar/unassigned | apps/desktop/src/renderer/app.js renderCalendar | apps/desktop/tests/calendarUrl.test.js |
| HU-CAL-04 | POST/PATCH /api/v1/work-orders/{id}/schedule, POST /api/v1/calendar/validate | renderCalendar + openScheduleModal | services/api/tests (pendiente) |
| HU-CAL-05 | POST /api/v1/work-orders/{id}/transitions, GET /work-orders/{id}/history | renderCalendar actions/history | services/api/tests/test_workorders.py |
| HU-CAL-06 | GET /api/v1/settings/public, /technicians/{id}/availability | renderCalendar | services/api/tests/test_health.py |
