# SIGOS — Trazabilidad calendario (HU-CAL)

| HU | Endpoint | Vista | Test |
|---|---|---|---|
| HU-CAL-01 | GET /api/v1/calendar/events, /calendar/unassigned | apps/desktop/src/renderer/app.js renderCalendar | apps/desktop/tests/calendarUrl.test.js |
| HU-CAL-02 | POST /api/v1/work-orders/{id}/schedule, PATCH .../schedule | renderCalendar + openScheduleModal | services/api/tests/test_calendar.py |
| HU-CAL-03 | POST /api/v1/calendar/validate | openScheduleModal | services/api/tests/test_calendar.py |
| HU-CAL-04 | POST /api/v1/work-orders/{id}/assignments | panel de acciones | services/api/tests/test_calendar.py |
| HU-CAL-05 | POST /api/v1/work-orders/{id}/transitions, GET .../history | acciones + drawer | services/api/tests/test_workorders.py |
| HU-CAL-06 | GET /api/v1/settings/public, /technicians/{id}/availability | renderCalendar | services/api/tests/test_health.py |
