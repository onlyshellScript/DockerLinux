# SIGOS — Auditoría de diseño actual

## 1. Alcance y método
- Repositorio auditado: `<raíz del repositorio>`.
- No hay repositorio Git detectado (`git status` falla: not a git repository). No se descartaron ni modificaron cambios preexistentes.
- Referencia visual: `SIGOS ING SW IIIIII-comprimido.pdf` (16 páginas). También se usó `Proyecto SIGOS.pdf` para requerimientos, casos de uso y trazabilidad.
- No se encontró enlace Figma editable operativo en el entorno; el PDF cita un enlace Figma, pero la referencia disponible para esta auditoría es el PDF.
- Fuentes de verdad revisadas: README, manifiestos, código fuente, pruebas, OpenAPI, migraciones, compose y CI.

## 2. Stack verificado
| Capa | Tecnología | Versión verificada |
|---|---|---|
| API | Python | 3.12 |
| API | Flask | 3.0.3 |
| API | Flask-SQLAlchemy | 3.1.1 |
| API | Flask-Migrate | 4.0.7 |
| API | pyodbc | 5.1.0 |
| API | PyJWT | 2.9.0 |
| API | pytest | 8.3.2 |
| DB | Microsoft SQL Server | 2022 (compose) |
| Escritorio | Electron | 33.4.11 |
| Escritorio | electron-builder | 25.0.0 |
| Móvil | Flutter SDK | 3.41.5 (proyecto `^3.11.3`) |
| Móvil | http | 1.2.2 |
| Móvil | sqflite | 2.3.0 |
| Móvil | uuid | 4.4.0 |

## 3. Estado actual de las aplicaciones

### API Flask
- Punto de entrada: `services/api/wsgi.py` → `create_app()`.
- Blueprints registrados: `health`, `auth/identity`, `workorders`, `materials`, `evidence`, `sync`, `notifications` bajo `/api/v1`.
- Base de datos: SQL Server por `DB_URL`; tests usan SQLite en memoria.
- Autenticación: JWT HS256, access 15 min, refresh 7 días.
- Roles semilla: `admin`, `dispatcher`, `technician`.
- Control de acceso por decoradores `require_auth` / `require_role`.
- Estados de orden: `pending`, `assigned`, `in_progress`, `completed`, `closed`, `cancelled` con transiciones controladas.
- Evidencias: foto, documento, observación; almacenamiento local con extensiones y límite de 10 MB.
- Sync offline: push idempotente por `client_operation_id`, pull por `since`.
- Notificaciones: email/WhatsApp, cola con reintentos (máx. 3).

### Escritorio Electron
- Entrada principal: `apps/desktop/src/main/index.js`.
- Ventana única 960x640, `contextIsolation`, `nodeIntegration=false`, `sandbox=true`.
- Seguridad básica correcta: bloqueo de navegación y apertura de ventanas.
- Renderer actual: una sola pantalla de estado de API (`index.html`, `app.js`).
- Comunicación: IPC `sigos:get-health` → `healthClient`.
- Estilo actual: CSS propio, paleta genérica azul/gris, sin sistema de tokens ni componentes reutilizables.

### Móvil Flutter
- Entrada: `main.dart` → `HealthPage`.
- Una sola pantalla de estado de API.
- Cliente HTTP para health.
- Sync/offline implementado a nivel de servicio y base local, pero no expuesto en UI actual.
- Sin tema personalizado ni navegación por roles.

## 4. Endpoints consumibles
- `GET /api/v1/health`
- Auth: `POST /auth/login`, `POST /auth/refresh`
- Usuarios: `GET/POST /users`, `GET/PUT /users/{id}` (admin)
- Órdenes: `GET/POST /work-orders`, `GET/PUT /work-orders/{id}`, `POST /work-orders/{id}/status`, `GET /work-orders/{id}/history`
- Materiales: `GET/POST /materials`, `GET/PUT /materials/{id}`, `POST/GET /materials/{id}/movements`
- Técnicos: `GET/POST /technician-profiles`, `GET/PUT /technician-profiles/{id}`
- Evidencias: `POST/GET /work-orders/{id}/evidences`, `GET /evidences/{id}/download`, `DELETE /evidences/{id}`
- Sync: `POST /sync/push`, `GET /sync/pull`
- Notificaciones: `POST/GET /notifications`, `POST /notifications/process`

## 5. Hallazgos de diseño
- Las tres aplicaciones existen, pero las interfaces actuales son mínimas (health check) y no reflejan el diseño de referencia del PDF.
- No hay design system compartido: no hay tokens, componentes base, layout principal, navegación ni vistas por rol.
- El desktop no consume autenticación, órdenes, materiales ni evidencias en la UI actual.
- El móvil no expone login, órdenes asignadas, evidencias ni sync.
- No hay documentación en `docs/` (directorio vacío al inicio).
- El PDF describe módulos que sí tienen backend: órdenes, técnicos, materiales, evidencias, sync, notificaciones. Reportes/KPI y usuarios tienen base parcial o pendiente en UI.
- El PDF describe funcionalidades fuera del código actual: firma digital, exportación PDF/Excel, reportes avanzados, recuperación de contraseña, panel completo. Deben tratarse como pendientes o fuera de MVP según validación.

## 6. Paleta aproximada extraída del PDF
Análisis de imágenes del PDF (dominantes, aproximación visual, no tokens oficiales de Figma):
- Verde oscuro: `#103020` / `rgb(16,48,32)` (coincide con `0.098 0.42 0.141` del PDF).
- Verde medio: `#207050` / `rgb(32,112,80)` y `#206040` / `rgb(32,96,64)`.
- Fondo beige: `#F0F0E0` / `rgb(240,240,224)`.
- Superficies blancas/grises: `#F0F0F0`, `#E0E0E0`, `#D0D0D0`.
- Alertas: naranja `#F0B050` en vistas de dashboard.

## 7. Verificación ejecutada
- API: `python -m pytest tests/ -v` → 38 passed.
- Desktop: `npm test` → 2 passed.
- Mobile: `flutter test` → 4 passed.
- No se modificó código en esta fase.
