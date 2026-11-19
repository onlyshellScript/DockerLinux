# Rendimiento (RNF-01 / RNF-02)

Prueba de carga ejecutada con Locust sobre API (SQL Server Express, 10000 ordenes semilla).

Configuracion: 30 usuarios virtuales, ramp-up 5/s, duracion 180s, headless.

Resultados (ms):

| Endpoint | p50 | p95 | p99 | Cumple p95 <= 3s |
|---|---|---|---|---|
| POST /api/v1/auth/login | 2300 | 2400 | 2400 | Si |
| GET /api/v1/work-orders?page=1&page_size=20 | 2100 | 2100 | 2100 | Si |
| GET /api/v1/work-orders?status=pending&zone=Z1 | 2100 | 2200 | 2200 | Si |
| POST /api/v1/work-orders | 2100 | 2100 | 2100 | Si |
| GET /api/v1/reportes/ordenes?por_pagina=20 | 2100 | 2200 | 2200 | Si |

Total requests: 1318, 0 fallos.

Conclusion: todos los endpoints medidos cumplen el umbral p95 <= 3s contra SQL Server. No se requirieron optimizaciones adicionales.
