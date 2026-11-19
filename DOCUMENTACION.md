# DOCUMENTACIÓN — SIGOS 2.0

## 1. Descripción general

SIGOS 2.0 es un monorepositorio para la gestión de órdenes de servicio técnico de instalaciones de gas natural. Provee una API REST en Flask (Python) consumida por aplicaciones de escritorio (Electron) y móvil (Flutter), con persistencia en SQL Server y documentación/scripts de operación.

**Stack tecnológico:**
- Backend: Python 3.12, Flask, SQLAlchemy, Alembic/Flask-Migrate, JWT.
- Escritorio: Node.js 20, Electron.
- Móvil: Flutter (Dart).
- Base de datos: SQL Server 2022 (producción/desarrollo), SQLite (tests).
- Infraestructura: Docker, Docker Compose, GitHub Actions.

**Ejecución (resumen):**
- API: `cd services/api && flask --app wsgi db upgrade && flask --app wsgi run --port 5000`
- Tests: `cd services/api && python -m pytest tests/ -v`
- Desktop: `cd apps/desktop && npm install && npm start`
- Móvil: `cd apps/mobile && flutter run`

## 2. Árbol de carpetas

```
SIGOSV/
├── apps/
│   ├── desktop/        # Aplicación de escritorio (Electron)
│   └── mobile/         # Aplicación móvil (Flutter)
├── services/
│   └── api/            # API REST (Flask) + migraciones + tests
├── contracts/          # OpenAPI (openapi.yaml)
├── docs/               # Documentación técnica, auditorías, trazabilidad
├── examples/           # Ejemplos de uso de la API
├── infra/docker/       # Compose de desarrollo y producción
├── scripts/            # Backups, seeds, utilidades
└── .env.example        # Plantilla de variables de entorno
```

## 3. Detalle por carpeta

- **apps/desktop/**: UI de gestión en Electron (JS/HTML/CSS). Se relaciona con `services/api` vía REST.
- **apps/mobile/**: UI móvil en Flutter con sincronización offline. Se relaciona con `services/api`.
- **services/api/**: Backend Flask, modelos, rutas, servicios, migraciones y tests. Se relaciona con SQL Server y clientes.
- **contracts/**: Contrato OpenAPI de la API.
- **docs/**: Documentación técnica, auditorías, trazabilidad y diagramas.
- **examples/**: Ejemplos de consumo de la API.
- **infra/docker/**: Dockerfiles y Compose para desarrollo/producción.
- **scripts/**: Utilidades de backup, seed y migración.

## 4. Detalle por archivo (principales)

- `services/api/app/__init__.py`: Fábrica de la aplicación Flask; registra extensiones y blueprints.
- `services/api/app/config.py`: Configuración por entorno (DB, JWT, rate limit).
- `services/api/app/extensions.py`: Instancias compartidas de SQLAlchemy y Migrate.
- `services/api/app/common/errors.py`: Respuestas de error JSON estandarizadas.
- `services/api/app/common/normalize.py`: Normalización de texto y correo.
- `services/api/app/health/*`: Health check de aplicación y BD.
- `services/api/app/identity/*`: Autenticación JWT, usuarios, roles, tokens, contraseñas.
- `services/api/app/workorders/*`: CRUD, estados, historial, programación, asignación.
- `services/api/app/materials/*`: Catálogo, stock, movimientos, solicitudes, exportación.
- `services/api/app/evidence/*`: Evidencias, revisiones, firmas, checklist.
- `services/api/app/calendar/*`: Programación y validación de agenda.
- `services/api/app/sync/*`: Sincronización offline.
- `services/api/app/notifications/*`: Notificaciones email/WhatsApp.
- `services/api/app/dashboard/*`: Resúmenes.
- `services/api/app/technicians/*`: Perfiles y disponibilidad.
- `services/api/app/catalogs/*`: Catálogos geográficos y de negocio.
- `services/api/app/settings/*`: Configuración del sistema y auditoría.
- `services/api/app/reportes/*`: Reportes y exportación.
- `services/api/app/tecnico/*`: Endpoints específicos de técnicos.
- `apps/desktop/src/**`: Código del cliente de escritorio.
- `apps/mobile/lib/**`: Código del cliente móvil.

## 5. Flujo general

1. El cliente (Electron/Flutter) autentica vía `/api/v1/auth/login` y obtiene JWT.
2. Con el token, consume endpoints de órdenes, materiales, evidencias, calendario, etc.
3. La API valida permisos por rol, ejecuta lógica de negocio y persiste en SQL Server.
4. Las notificaciones se encolan y envían por email/WhatsApp.
5. El cliente móvil sincroniza operaciones offline vía `/api/v1/sync/*`.

## 6. Mapa de agentes

No existen agentes definidos dentro del repositorio; los agentes del flujo de desarrollo son externos al código (orquestador, product-owner, architect, developer, qa, etc.) y se gestionan fuera del repositorio.

---

*Documento generado como parte de la fase de documentación previa obligatoria.*
