# SIGOS — Contratos frontend-backend

## 1. Base URL
- Desarrollo: `http://localhost:5000`
- Desktop: `SIGOS_API_BASE_URL`
- Mobile: `--dart-define=SIGOS_API_BASE_URL=...`

## 2. Autenticación
- `POST /api/v1/auth/login` body: `{username, password}`.
- Respuesta: `{access_token, refresh_token, token_type, user}`.
- `POST /api/v1/auth/refresh` body: `{refresh_token}`.
- Header: `Authorization: Bearer <access_token>`.
- JWT access: 15 min; refresh: 7 días.

## 3. Roles
- `admin`: gestión de usuarios, materiales, notificaciones, reportes.
- `dispatcher`: órdenes, asignaciones, materiales, notificaciones.
- `technician`: órdenes asignadas, estados, evidencias, sync.

## 4. Endpoints principales
Ver `contracts/openapi.yaml` y código en `services/api/app/*/routes.py`. Resumen:
- Health: `GET /api/v1/health`
- Usuarios: `/api/v1/users`
- Órdenes: `/api/v1/work-orders`, `/status`, `/history`
- Materiales: `/api/v1/materials`, `/movements`
- Técnicos: `/api/v1/technician-profiles`
- Evidencias: `/api/v1/work-orders/{id}/evidences`, `/api/v1/evidences/{id}/download`
- Sync: `/api/v1/sync/push`, `/api/v1/sync/pull`
- Notificaciones: `/api/v1/notifications`, `/process`

## 5. Reglas de consumo
- No alterar contratos sin actualizar consumidores y pruebas.
- Desktop/mobile deben manejar 401/403/404/400 y estados de red.
- Sync push es idempotente por `client_operation_id`.
- Pull usa `since` ISO-8601.
