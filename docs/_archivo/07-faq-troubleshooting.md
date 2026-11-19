# FAQ y solución de problemas — SIGOS 2.0

**Proyecto:** SIGOS 2.0
**Versión del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

| # | Síntoma | Causa probable | Solución |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'app'` | Ejecutar comandos fuera de `services/api` o sin `PYTHONPATH` | `cd services/api` y usar `.venv\Scripts\python` |
| 2 | `pyodbc.Error: ... Login failed` | Credenciales/BD incorrectas | Verificar `DB_URL` y que el login `sigos` exista |
| 3 | `flask db upgrade` falla por SQLite | Migraciones usan ALTER no soportado por SQLite | Usar SQL Server (no SQLite) para migraciones |
| 4 | Tests SQL Server se omiten | `TEST_DB_URL` no definido | Definir `TEST_DB_URL` y ejecutar con `-m sqlserver` |
| 5 | Puerto 5000 ocupado | Otro proceso | Cambiar `--port` o liberar puerto |
| 6 | `invalid credentials` en login | Password/usuario incorrecto o seed no ejecutado | Ejecutar `seed.py`; credenciales dev `admin`/`Admin123!` |
| 7 | `missing token` / `token expired` | JWT expirado (15 min) | Refrescar con `/auth/refresh` o volver a login |
| 8 | Evidencias no se guardan | `UPLOAD_DIR` inexistente o sin permisos | Crear directorio y verificar permisos |
| 9 | CORS bloquea llamadas desde navegador | CORS no configurado en backend | [PENDIENTE: implementar CORS o usar proxy] |
| 10 | Migraciones pendientes en producción | No se ejecutó `flask db upgrade` | Ejecutar migraciones antes de arrancar |
| 11 | Desktop no conecta a API | `SIGOS_API_BASE_URL` incorrecto | Definir variable de entorno |
| 12 | Build móvil falla por SDK | Flutter no instalado/versión | Instalar Flutter stable y ejecutar `flutter doctor` |
