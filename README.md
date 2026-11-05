# SIGOS 2.0

Software empresarial multiplataforma para la gestión de órdenes de servicio. Monorepositorio completo H0-H7: fundación, identidad, órdenes, materiales, evidencias, sync offline, notificaciones y producción.

## Stack

- Backend: Python 3.12+ · Flask · SQLAlchemy · Alembic
- Base de datos: Microsoft SQL Server
- Escritorio: Electron · JavaScript · HTML5 · CSS3
- Móvil: Flutter · Dart (Android)

## Requisitos

- Python 3.12+
- ODBC Driver 18 for SQL Server
- SQL Server 2022+ o SQL Server Express
- Node.js 20+
- Flutter stable

## Base de datos local

Crea la base de datos y el usuario de desarrollo:

```powershell
sqlcmd -S "localhost,1433" -E -C -Q "CREATE DATABASE sigos;"
sqlcmd -S "localhost,1433" -E -C -Q "CREATE LOGIN sigos WITH PASSWORD = 'Sigos_Dev_2026!', CHECK_POLICY = ON;"
sqlcmd -S "localhost,1433" -E -C -Q "USE sigos; CREATE USER sigos FOR LOGIN sigos; ALTER ROLE db_owner ADD MEMBER sigos;"
```

Alternativamente, usa Docker Compose desde `infra/docker/compose.yaml`.



## Base de datos de pruebas (SQL Server)

Crea una base dedicada para los tests contra SQL Server:

`powershell
sqlcmd -S "localhost,1433" -E -C -Q "CREATE DATABASE sigos_test;"
`

Ejecuta el carril SQL Server con:

`powershell
 = "mssql+pyodbc://sigos:Sigos_Dev_2026!@localhost:1433/sigos_test?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
cd services/api
.venv\Scripts\python -m pytest tests/ -m sqlserver -v
`

Si TEST_DB_URL no existe, esos tests se omiten.
## Backend (Flask)

```powershell
cd services/api
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

$env:DB_URL = "mssql+pyodbc://sigos:Sigos_Dev_2026!@localhost:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
$env:FLASK_APP = "wsgi.py"
.venv\Scripts\flask db upgrade
.venv\Scripts\python seed.py
.venv\Scripts\flask run --port 5000
```

Verificación:

```powershell
Invoke-RestMethod http://localhost:5000/api/v1/health
```

Credenciales iniciales (desarrollo): `admin` / `Admin123!`

## Escritorio (Electron)

```powershell
cd apps/desktop
npm install
npm start
```

Variable opcional: `SIGOS_API_BASE_URL`.

## Móvil (Flutter)

```powershell
cd apps/mobile
flutter pub get
flutter run --dart-define=SIGOS_API_BASE_URL=http://10.0.2.2:5000
```

## Pruebas

```powershell
cd services/api
.venv\Scripts\python -m pytest tests/ -v

cd apps/desktop
npm test

cd apps/mobile
flutter test
```

## Estructura

```text
sigos/
+-- apps/desktop/       Electron + JavaScript
+-- apps/mobile/        Flutter + Dart
+-- services/api/       Python + Flask
+-- contracts/          OpenAPI
+-- infra/docker/       Docker Compose para SQL Server
+-- docs/               Arquitectura y decisiones
+-- .env.example        Variables de entorno de ejemplo
```

## Producción

### Docker

```powershell
cd infra/docker
$env:DB_URL = "mssql+pyodbc://sa:YourPassword@sqlserver:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
$env:JWT_SECRET_KEY = "your-secret-key"
$env:MSSQL_SA_PASSWORD = "YourPassword"
docker compose -f docker-compose.prod.yaml up -d
```

### Backups

```powershell
# Backup de base de datos
.\scripts\backup-db.ps1 -Server "localhost,1433" -Database "sigos" -BackupDir "C:\Backups\SIGOS"

# Backup de evidencias
.\scripts\backup-uploads.ps1
```

### Instaladores

```powershell
# Escritorio (Windows)
cd apps/desktop
npm run dist

# Móvil (Android APK)
cd apps/mobile
flutter build apk --release
```

### Variables de entorno de producción

| Variable | Descripción |
|----------|-------------|
| DB_URL | Cadena de conexión SQL Server |
| JWT_SECRET_KEY | Secreto para firmar tokens |
| SMTP_HOST/PORT/USER/PASS | Configuración email |
| WHATSAPP_API_URL/TOKEN | Configuración WhatsApp |
| UPLOAD_DIR | Directorio de evidencias |
| ENABLE_NOTIFICATION_WORKER | "true" para activar worker |
| LOG_LEVEL | DEBUG, INFO, WARNING, ERROR |
| LOG_FORMAT | json o text |

## CI/CD

GitHub Actions en `.github/workflows/ci.yml`:
- Tests automáticos en cada push/PR
- Build de instalador Windows en main
- Build de APK Android en main

