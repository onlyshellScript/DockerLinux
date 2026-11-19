# SIGOS 2.0

SIGOS 2.0 es un monorepositorio para la gestión de órdenes de servicio técnico. Provee una API
Flask (servicios) consumida por aplicaciones de escritorio (Electron) y móvil (Flutter), además
de documentación y scripts de operación.

## Estructura del monorepo

```
SIGOSV/
├── apps/
│   ├── desktop/        # Aplicación de escritorio (Electron)
│   └── mobile/         # Aplicación móvil (Flutter)
├── services/
│   └── api/            # API REST (Flask) + migraciones Alembic + tests
├── contracts/          # OpenAPI (openapi.yaml)
├── docs/               # Documentación técnica, auditorías, trazabilidad
├── examples/           # Ejemplos de uso de la API
├── infra/docker/       # Compose de desarrollo y producción
├── scripts/            # Backups, seeds, utilidades
└── .env.example        # Plantilla de variables de entorno
```

## Requisitos

- Python 3.12
- Node.js 20 (para `apps/desktop`)
- Flutter (canal stable) (para `apps/mobile`)
- SQL Server 2022 (producción/desarrollo) o SQLite (solo tests en memoria)
- Docker + Docker Compose (para despliegue containerizado)
- ODBC Driver 18 for SQL Server (en el host o en la imagen)

## Variables de entorno

La plantilla completa está en `.env.example`. Copiarla a `.env` (raíz o `services/api/`) y
reemplazar los valores marcados como `CAMBIAR_ESTE_VALOR`. No versionar `.env`.

Variables mínimas para la API:

- `DB_URL`: cadena de conexión SQLAlchemy (ej. `mssql+pyodbc://...`).
- `JWT_SECRET_KEY`: secreto para firmar tokens JWT.
- `TECH_INITIAL_PASSWORD`: contraseña inicial asignada a técnicos creados desde el panel admin (placeholder `CAMBIAR_ESTE_VALOR`). El técnico debe cambiarla en el primer acceso.

El resto (uploads/evidencias, SMTP, WhatsApp, logging, worker de notificaciones, puertos) está
documentado en `.env.example`.

## Levantar la API (desarrollo)

```bash
cd services/api
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env   # ajustar DB_URL y JWT_SECRET_KEY
flask --app wsgi db upgrade   # ver nota: la cadena de migraciones debe corregirse primero
flask --app wsgi run --port 5000
```

La API queda disponible en `http://localhost:5000` (health: `GET /api/v1/health`).

> **Migraciones (17/11/2026):** `flask db upgrade` falla mientras `migrations/versions/` contenga las migraciones
> antiguas en inglés. Una base existente (p. ej. `SIGOS_DEV`, en `615483f3bc21`) funciona sin migrar.
> Detalle y corrección: `docs/database/esquema-espanol-y-orm.md`.

## Levantar el desktop

```bash
cd apps/desktop
npm install
npm start          # usa SIGOS_API_BASE_URL o http://localhost:5000
```

## Ejecutar los tests

```bash
cd services/api
pip install -r requirements.txt
python -m pytest tests/ -v
```

Las pruebas que requieren SQL Server real se marcan con `@pytest.mark.sqlserver` y se saltan
si no se define `TEST_DB_URL`. Para ejecutarlas:

```bash
TEST_DB_URL="mssql+pyodbc://sa:<password>@localhost:1433/sigos_test?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes" \
DB_URL="mssql+pyodbc://sa:<password>@localhost:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes" \
python -m pytest tests/ -v
```

Suite de referencia (17/11/2026): ver `docs/revision-2026-11-17.md`. Desktop: `cd apps/desktop && npm test`.

## Despliegue con Docker

Desarrollo (solo SQL Server):

```bash
cd infra/docker
docker compose -f compose.yaml up -d
```

Producción (API + SQL Server):

```bash
cd infra/docker
# Crear .env con DB_URL, JWT_SECRET_KEY, MSSQL_SA_PASSWORD, etc.
docker compose -f docker-compose.prod.yaml up -d --build
```

La imagen de la API se construye desde `services/api/Dockerfile` (instala ODBC Driver 18,
crea usuario no-root `sigos`, define `HEALTHCHECK` y arranca con `wsgi_prod:app`).

## Roles

Equivalencia con el documento de requisitos: Administrador = `admin`,
Coordinador = `dispatcher`, Técnico = `technician`. El rol Operador no existe
como rol separado; sus funciones (RF-01, RF-04) las cubren `admin` y
`dispatcher`.

## Documentación

- Documentación completa: `docs/DOCUMENTACION_COMPLETA.md`.
- **Revisión y pendientes (17/11/2026): `docs/revision-2026-11-17.md`.**
- Guía de desarrollo y pruebas: `docs/development/guia-desarrollo-y-pruebas.md`.
- Exportaciones PDF/XLSX: `docs/architecture/exportaciones.md`.
- Usuarios, autenticación y autorización: `docs/architecture/usuarios-y-seguridad.md`.
- Sistema de diseño del desktop: `docs/design/sistema-de-diseno.md`.
- Esquema en español, ORM y migraciones: `docs/database/esquema-espanol-y-orm.md`.
- Trazabilidad: `docs/traceability/design-requirements-matrix.md`.
- Brechas y estado (análisis previo): `docs/analisis-brechas-estado.md`.
- Migraciones (auditoría del 14/11, desactualizada): `docs/architecture/auditoria-migraciones.md`.
