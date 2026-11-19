# SIGOS — Análisis de brechas y estado

Documento de seguimiento del estado de los hallazgos críticos identificados en las revisiones de
seguridad, calidad e infraestructura. Los IDs referencian el informe de hallazgos (seguridad `S*`,
funcionales `F*`); la evidencia se cita contra el código actual.

Suite de regresión de referencia (Fase 2): **257 passed, 10 skipped, 0 failed**.

## Estado de hallazgos críticos

| ID | Área | Descripción (inferida del informe) | Estado | Evidencia / Motivo |
|---|---|---|---|---|
| S5 | Secretos / Config | Credenciales por defecto en `Config` (dev) (`services/api/app/config.py:11-13`) | Cerrado | `config.py` ahora lee `DB_URL` y `JWT_SECRET_KEY` desde entorno sin fallback; `create_app` valida su presencia fuera de TESTING. |
| S6 | Secretos / Config | `.env.example` incompleto y con secretos débiles/expuestos | Cerrado | `.env.example` actualizado con todas las variables usadas (uploads, evidencias, SMTP, WhatsApp, logging, worker, DB de desarrollo) y placeholders `CAMBIAR_ESTE_VALOR`; `.gitignore` ignora `.env.local`. |
| S7 | Autorización | Reglas de acceso en cambio de estado / mutaciones (RF-12) | Cerrado | Decoradores `require_role` y pruebas `test_rnf05_access_rules`, `test_admin_cannot_create_work_order` en verde. |
| S20 | Infraestructura / Docker | Empaquetado y arranque del contenedor de producción (ODBC, usuario no-root, healthcheck) | Cerrado | `services/api/Dockerfile` instala ODBC Driver 18, crea usuario `sigos`, define `HEALTHCHECK` y arranca con `wsgi_prod:app`. |
| F3 | Materiales / Stock (RF-16) | Descuento de stock y registro de movimiento | Cerrado | `tests/test_rf15_rf16_materiales.py::test_rf16_descuenta_stock_y_movimiento` en verde. |
| F4 | Órdenes / Cancelación (RF-04) | Cancelación exige motivo y transición de estado | Cerrado | `tests/test_rf04_rf13_rf14.py::test_rf04_cancelar_exige_motivo` en verde. |
| S19 | Materiales / Stock (RF-16) | Defecto de concurrencia/stock en movimientos | Parcial | Pruebas de concurrencia existen (`test_materials_concurrency.py`); 10 skipped corresponden a pruebas `sqlserver` sin `TEST_DB_URL`. Validar en SQL Server real antes de cerrar. |
| F13 / F10 / F14 | Historial / Timeline / Calendario (RF-10, RF-13, RF-14) | Filtrado, rango de calendario, historial y timeline cronológico | Cerrado | `test_work_orders_list_filters_and_pagination`, `test_work_orders_calendar_range_and_empty_technician`, `test_rf13_historial_por_transicion`, `test_rf14_timeline_cronologico` en verde. |
| F5 | Filtrado / Paginación (RF-03, RF-10) | Filtros y paginación del listado de órdenes | Cerrado | `tests/test_workorders.py::test_work_orders_list_filters_and_pagination` en verde. |
| Secretos / Config | Configuración por entorno | Fallback con credenciales hardcodeadas y JWT secret débil (H9) | Cerrado | `Config` y `ProductionConfig` exigen `DB_URL`/`JWT_SECRET_KEY` por entorno; no hay defaults inseguros en código. |
| Migraciones | Esquema / Alembic | Cadena activa vs. linaje histórico en inglés (`versions_backup`) | Parcial | Cadena activa `ef3ab0606ef4 → 3a374aacae1f → 615483f3bc21` coherente con modelos; `versions_backup` queda como histórico no ejecutable. Entornos legacy requieren migración de datos one-shot (ver `docs/architecture/auditoria-migraciones.md`). |
| Docker | Despliegue / CI | Contenedores de producción y pipeline | Cerrado | Entrypoint (`services/api/docker/entrypoint.sh`) espera SQL Server, crea la BD y aplica migraciones; worker de notificaciones como servicio aparte; compose prod sin puerto 1433 publicado y con `infra/docker/.env.prod.example`. CI con secreto y build de imagen (H16/H17 cerrados). Verificado 2026-11-18: `up --build` desde cero aplica 4 migraciones, health `UP` (app y BD), worker activo, reinicio sin re-migrar. |

## Notas

- Los hallazgos marcados "Cerrado" se verifican contra el código actual; los hashes de commit no están disponibles en el entorno de documentación, por lo que no se cita commit específico.
- Los 10 tests saltados corresponden a pruebas que requieren SQL Server real (`TEST_DB_URL`); no constituyen fallos.
- Para cerrar S19 y los hallazgos de migraciones/Docker pendientes se requiere ejecución en entorno con SQL Server y Docker daemon.
