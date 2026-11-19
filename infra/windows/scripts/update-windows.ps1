#Requires -Version 5.1
<#
.SYNOPSIS
  Actualiza una instalacion existente con el codigo de este repositorio, con respaldo y rollback.

.DESCRIPTION
  1. Compara la version instalada (C:\Program Files\SIGOS\app\VERSION) con la del repositorio
     (services\api\VERSION). Rechaza bajar de version salvo -AllowDowngrade (las migraciones no se revierten).
  2. SQL Server: con -BackupDatabase ejecuta scripts\backup-db.ps1 antes de migrar (recomendado).
  3. Detiene los servicios y copia a C:\ProgramData\SIGOS\backups\pre-update-<fecha>-<version>:
     configuracion, base SQLite (si aplica), codigo (app), entorno virtual (venv) y XML de WinSW.
  4. Ejecuta install-windows.ps1 con los parametros de install.json: conserva sigos.env, admin.env y datos,
     y aplica solo las migraciones pendientes (alembic upgrade head; nunca destructivo).
  5. Si algo falla (incluida la comprobacion de health/heartbeat), rollback de ARCHIVOS: restaura app, venv, XML e
     install.json, re-registra los servicios, arranca y comprueba. La BASE DE DATOS no se revierte automaticamente
     (ni alembic downgrade ni restauracion): es una decision explicita con restore-database.ps1.

  Codigos: 0 actualizado · 8 fallo y rollback correcto · 9 fallo y rollback fallido · resto: ver common.ps1.

.EXAMPLE
  .\update-windows.ps1 -BackupDatabase
.EXAMPLE
  .\update-windows.ps1 -AllowDowngrade
#>
[CmdletBinding()] param(
    [ValidateSet('Windows', 'Sql')][string]$SqlAdminAuth = 'Windows',
    [switch]$BackupDatabase,
    [string]$DbBackupDir,   # vacio = carpeta de respaldos de la instancia (la cuenta de SQL Server ya puede escribir)
    [switch]$AllowDowngrade,
    [switch]$NoRollback,
    [ValidateRange(1, 50)][int]$KeepBackups = 3
)
. "$PSScriptRoot\common.ps1"
Assert-SigosAdmin
if (-not (Test-SigosInstalled) -or -not (Test-Path $SigosPaths.InstallCfg)) {
    Stop-Sigos $EXIT_NOT_INSTALL 'No hay una instalacion previa: usa install-windows.ps1.'
}

function Invoke-SigosRobocopy([string]$From, [string]$To) {
    & robocopy.exe $From $To /MIR /R:2 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $From -> $To fallo (codigo $LASTEXITCODE)" }
}

$logFile = Start-SigosScriptLog 'update'
try {
$cfg = Get-Content $SigosPaths.InstallCfg -Raw | ConvertFrom-Json
$dbBackupFile = $null

# --- 1. Versiones y compatibilidad --------------------------------------------
Write-SigosStep 'Comprobando versiones'
$from = Get-SigosInstalledVersion
$to = Get-SigosSourceVersion
if (-not $to) { Stop-Sigos $EXIT_PREREQ "No se encontro services\api\VERSION en $SigosRepoRoot." }
if (-not $from) {
    Write-SigosWarn "No se pudo leer la version instalada: se continua como actualizacion a $to."
    $from = 'desconocida'
} else {
    $cmp = Compare-SigosVersion $to $from
    if ($cmp -lt 0 -and -not $AllowDowngrade) {
        Stop-Sigos $EXIT_USAGE ("La version del repositorio ($to) es anterior a la instalada ($from). Las migraciones no se " +
            'revierten: bajar de version puede dejar la base incompatible. Usa -AllowDowngrade solo si sabes que el esquema es compatible.')
    }
    if ($cmp -eq 0) { Write-SigosInfo "Misma version ($to): se reaplica la instalacion (reparacion)." }
}
Write-SigosOk "Instalada: $from -> repositorio: $to"
if ($cfg.PythonExe -and -not (Test-Path $cfg.PythonExe)) {
    Stop-Sigos $EXIT_PREREQ "El Python registrado en install.json ya no existe ($($cfg.PythonExe)). Reinstala Python 3.12 o usa install-windows.ps1 -PythonExe."
}

# --- 2. Respaldo de la base SQL Server (opcional, antes de parar nada) -------------
if ($cfg.DbEngine -eq 'SqlServer') {
    if ($BackupDatabase) {
        Write-SigosStep "Respaldo de la base [$($cfg.DbName)] (scripts\backup-db.ps1)"
        $ok = $false
        $bkArgs = @{ Server = "$($cfg.SqlHost),$($cfg.SqlPort)"; Database = $cfg.DbName; PassThru = $true }
        if ($DbBackupDir) { $bkArgs['BackupDir'] = $DbBackupDir } else { $bkArgs['UseInstanceBackupDir'] = $true }
        try {
            $dbBackupFile = @(& (Join-Path $SigosRepoRoot 'scripts\backup-db.ps1') @bkArgs)[-1]
            $ok = ($LASTEXITCODE -eq 0)
        } catch { Write-SigosWarn $_.Exception.Message }
        if (-not $ok) { Stop-Sigos $EXIT_DB 'El respaldo de SQL Server fallo: no se actualiza. (Requiere sqlcmd y que la cuenta de SQL Server pueda escribir en -DbBackupDir.)' }
        Write-SigosOk 'Respaldo de SQL Server creado'
    } else {
        Write-SigosWarn 'Sin -BackupDatabase: si una migracion falla en SQL Server, no habra copia de la base para volver atras.'
    }
}

# --- 3. Detener servicios y respaldar la instalacion ------------------------------
& "$PSScriptRoot\stop-services.ps1"
if ($LASTEXITCODE -ne 0) { Stop-Sigos $LASTEXITCODE 'No se pudieron detener los servicios: no se actualiza.' }

$safeFrom = $from -replace '[^0-9A-Za-z\.\-]', '_'
$dest = Join-Path $SigosPaths.BackupDir ('pre-update-{0:yyyyMMdd-HHmmss}-{1}' -f (Get-Date), $safeFrom)
Write-SigosStep "Respaldando la instalacion en $dest"
New-Item -ItemType Directory -Force -Path $dest, (Join-Path $dest 'bin') | Out-Null
Copy-Item -LiteralPath $SigosPaths.ConfigDir -Destination $dest -Recurse
Invoke-SigosRobocopy $SigosPaths.AppDir (Join-Path $dest 'app')
Invoke-SigosRobocopy $SigosPaths.Venv (Join-Path $dest 'venv')
Get-ChildItem -LiteralPath $SigosPaths.BinDir -Filter 'SIGOS-*.xml' | Copy-Item -Destination (Join-Path $dest 'bin')
$sqliteFiles = @()
if ($cfg.DbEngine -eq 'SQLite') {
    # Copia consistente: con los servicios detenidos no hay escrituras en curso.
    $sqliteFiles = @(Get-ChildItem -LiteralPath $SigosPaths.DataDir -Filter *.db -ErrorAction SilentlyContinue)
    New-Item -ItemType Directory -Force -Path (Join-Path $dest 'data') | Out-Null
    $sqliteFiles | Copy-Item -Destination (Join-Path $dest 'data')
}
[ordered]@{ From = $from; To = $to; Date = (Get-Date).ToString('s'); DbEngine = $cfg.DbEngine; Log = $logFile } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dest 'manifest.json') -Encoding UTF8
$what = 'config, app, venv, XML de servicios'
if ($sqliteFiles) { $what += ', base SQLite' }
Write-SigosOk "Respaldo completo ($what)"

# --- 4. Actualizar -------------------------------------------------------------
Write-SigosStep "Actualizando $from -> $to"
& "$PSScriptRoot\install-windows.ps1" -SqlAdminAuth $SqlAdminAuth
$code = $LASTEXITCODE
if ($code -eq 0) {
    # Retencion: las copias de app/venv pesan; se conservan las $KeepBackups ultimas. Config y bases se conservan siempre.
    Get-ChildItem -LiteralPath $SigosPaths.BackupDir -Directory -Filter 'pre-update-*' | Sort-Object Name -Descending |
        Select-Object -Skip $KeepBackups | ForEach-Object {
            foreach ($big in 'app', 'venv') {
                $p = Join-Path $_.FullName $big
                if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
            }
        }
    Write-Host ''
    Write-Host "SIGOS actualizado a $to. Respaldo previo: $dest" -ForegroundColor Green
    exit $EXIT_OK
}

Write-Host "    [ERROR] La actualizacion fallo (codigo $code)." -ForegroundColor Red
if ($NoRollback) {
    Write-SigosWarn "Sin rollback (-NoRollback). Respaldo para restaurar a mano: $dest"
    exit $code
}

# --- 5. Rollback ---------------------------------------------------------------
Write-SigosStep "Rollback a $from"
try {
    foreach ($s in ($SigosServices[($SigosServices.Count - 1)..0])) {
        $svc = Get-SigosService $s
        if ($svc -and $svc.Status -ne 'Stopped') {
            Stop-Service -Name $s -Force -ErrorAction SilentlyContinue
            [void](Wait-SigosServiceStatus $s 'Stopped' 90)
        }
    }
    Invoke-SigosRobocopy (Join-Path $dest 'app') $SigosPaths.AppDir
    Invoke-SigosRobocopy (Join-Path $dest 'venv') $SigosPaths.Venv
    Copy-Item -LiteralPath (Join-Path $dest 'config\install.json') -Destination $SigosPaths.InstallCfg -Force
    Write-SigosOk 'Codigo, entorno virtual e install.json restaurados (sigos.env y admin.env no se tocan)'

    # La base de datos NO se toca aqui (rollback de archivos y de datos van separados): si la version anterior no
    # funciona con el esquema migrado, el administrador decide restaurar con restore-database.ps1.

    foreach ($s in $SigosServices) {
        $exe = Join-Path $SigosPaths.BinDir "$s.exe"
        $xmlBackup = Join-Path $dest "bin\$s.xml"
        if (-not (Test-Path $exe) -or -not (Test-Path $xmlBackup)) { throw "falta $exe o $xmlBackup" }
        Copy-Item -LiteralPath $xmlBackup -Destination (Join-Path $SigosPaths.BinDir "$s.xml") -Force
        if (Get-SigosService $s) { $rc = Invoke-SigosWinSW $s 'refresh' } else { $rc = Invoke-SigosWinSW $s 'install' }
        if ($rc -ne 0 -or -not (Get-SigosService $s)) { throw "WinSW no pudo registrar $s" }
        & sc.exe config $s obj= "NT SERVICE\$s" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "no se pudo asignar NT SERVICE\$s" }
    }
    Write-SigosOk 'Servicios registrados con la configuracion anterior'

    & "$PSScriptRoot\start-services.ps1"
    if ($LASTEXITCODE -ne 0) { throw "la version $from no arranco sana (codigo $LASTEXITCODE)" }
} catch {
    Write-Host "    [ERROR] Rollback fallido: $($_.Exception.Message)" -ForegroundColor Red
    Write-SigosWarn "Respaldo de archivos: $dest. Diagnostico: .\diagnose-windows.ps1"
    Write-SigosWarn 'Si la actualizacion llego a migrar la base, la version anterior puede no ser compatible con el esquema nuevo.'
    if ($sqliteFiles) {
        Write-SigosWarn "Restaurar la base previa: .\restore-database.ps1 -BackupFile '$dest\data\$($sqliteFiles[0].Name)'"
    } else {
        if ($dbBackupFile) { Write-SigosWarn "Restaurar la base previa: .\restore-database.ps1 -BackupFile '$dbBackupFile'" }
        else { Write-SigosWarn 'No hay respaldo de la base de esta actualizacion (no se uso -BackupDatabase).' }
    }
    exit $EXIT_ROLLBACK_KO
}
Write-SigosWarn "Actualizacion revertida: SIGOS $from esta funcionando. Revisa el registro: $logFile"
Write-SigosWarn 'La base de datos no se revirtio: las migraciones aplicadas siguen aplicadas (son aditivas). Si necesitas el estado previo, usa restore-database.ps1.'
exit $EXIT_ROLLED_BACK

} finally {
    Stop-Transcript | Out-Null
}
