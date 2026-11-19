# SIGOS {{VERSION}} para Windows — instalación en una máquina nueva

Paquete autónomo: no necesita Git, Docker ni acceso a Internet (las dependencias de Python y WinSW van incluidos).
Documentación completa de administración: [`infra/windows/README.md`](infra/windows/README.md).

## 1. Requisitos de la máquina

| Requisito | Detalle |
|---|---|
| Sistema | Windows 10/11 o Windows Server 2016+ de 64 bits, PowerShell 5.1 (incluido) |
| Permisos | Consola de PowerShell **ejecutada como administrador** |
| Python | **3.12 x64 instalado "para todos los usuarios"** (python.org → *Customize installation* → *Install Python 3.12 for all users*; queda en `C:\Program Files\Python312`) |
| Base de datos | SQL Server 2017+ (Express sirve) con TCP/IP en puerto fijo, **o** SQLite para demostración |
| ODBC (SQL Server) | Microsoft ODBC Driver 18 for SQL Server, 64 bits |
| sqlcmd (SQL Server) | Recomendado: comprobaciones previas, respaldos y restauración |
| Disco | ~1 GB libre en la unidad del sistema |

## 2. Verificar el paquete

Junto al `.zip` se distribuye `SIGOS-Windows-v{{VERSION}}.zip.sha256`. Antes de extraer:

```powershell
(Get-FileHash .\SIGOS-Windows-v{{VERSION}}.zip -Algorithm SHA256).Hash.ToLower()
Get-Content .\SIGOS-Windows-v{{VERSION}}.zip.sha256      # deben coincidir
Unblock-File .\SIGOS-Windows-v{{VERSION}}.zip           # quita la marca "descargado de Internet"
Expand-Archive .\SIGOS-Windows-v{{VERSION}}.zip -DestinationPath C:\SIGOS-setup
```

El instalador vuelve a comprobar el SHA-256 de cada archivo contra `package-manifest.json` y se detiene si falta o
cambió alguno. Para comprobarlo sin instalar: `.\scripts\verify-package.ps1`.

## 3. Instalar

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd C:\SIGOS-setup\SIGOS-Windows-v{{VERSION}}\infra\windows\scripts

# SQL Server local con el usuario de Windows actual como sysadmin:
.\install-windows.ps1 -DbEngine SqlServer -SqlHost localhost -SqlPort 1433 -SqlServiceName 'MSSQL$SQLEXPRESS'

# o SQLite (demostración):
.\install-windows.ps1 -DbEngine SQLite
```

Si la base `sigos` o los logins `sigos_app`/`sigos_migrator` **ya existen** en ese SQL Server, el instalador se detiene
para no migrar una base ajena ni cambiar contraseñas de logins en uso. Elige otros nombres (`-DbName`, `-DbAppUser`,
`-DbMigratorUser`) o confirma la adopción con `-UseExistingDatabase` / `-ReuseExistingLogins`.

El instalador termina con código `0` solo si la API responde `UP` con `database=UP`, el worker escribe su heartbeat y
se generan los logs. Cualquier otro código indica qué falló (ver tabla de códigos en el README).

## 4. Primer acceso

- API: `http://127.0.0.1:5000/api/v1/health`
- Credenciales iniciales: `C:\ProgramData\SIGOS\config\initial-admin.txt` (solo administradores). El sistema exige
  cambiar la contraseña en el primer acceso. **Borra el archivo después.**
- Configura correo/WhatsApp en `C:\ProgramData\SIGOS\config\sigos.env` y ejecuta `.\restart-services.ps1`.

## 5. Comprobar

```powershell
.\status-services.ps1     # SCM, vida y salud por separado; código 0 = sano
.\diagnose-windows.ps1    # .zip de diagnóstico sin secretos para soporte
```

## 6. Después

Conserva esta carpeta: `update-windows.ps1` de un paquete **nuevo** actualiza la instalación (con respaldo y rollback);
`uninstall-windows.ps1` desinstala conservando los datos.
