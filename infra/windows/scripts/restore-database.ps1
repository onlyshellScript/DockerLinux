#Requires -Version 5.1
<#
.SYNOPSIS
  Restaura la base de datos de SIGOS desde un respaldo. Operacion DESTRUCTIVA y separada del rollback de archivos.

.DESCRIPTION
  update-windows.ps1 revierte automaticamente el CODIGO (app, venv, servicios) pero nunca la base de datos.
  Usa este script cuando la version anterior no funcione con el esquema migrado, o para recuperar datos.

  1. Comprueba el respaldo (SQL Server: RESTORE VERIFYONLY; SQLite: cabecera del archivo).
  2. Pide escribir "RESTAURAR <base>" (salvo -Force).
  3. Detiene SIGOS-Worker y SIGOS-API.
  4. Respaldo de seguridad del estado ACTUAL antes de sustituirlo (no se pierde nada):
     SQL Server -> carpeta de respaldos de la instancia; SQLite -> backups\pre-restore-<fecha>\.
  5. Restaura (SQL Server: RESTORE ... WITH REPLACE sobre la misma base; SQLite: sustituye el .db).
  6. Arranca los servicios y comprueba health.

  SQL Server: requiere sqlcmd y que el administrador que lo ejecuta sea sysadmin (autenticacion de Windows).
  Solo restaura sobre la misma base y servidor de install.json (los usuarios sigos_app/sigos_migrator conservan su SID).

  Codigos: 0 restaurado y sano · 1 uso/cancelado · 4 fallo de BD · 5/6 servicios o health tras restaurar.
.EXAMPLE
  .\restore-database.ps1 -BackupFile 'C:\Program Files\Microsoft SQL Server\MSSQL17.SQLEXPRESS\MSSQL\Backup\sigos_20261119_120000.bak'
.EXAMPLE
  .\restore-database.ps1 -BackupFile C:\ProgramData\SIGOS\backups\pre-update-20261119-120000-1.0.0\data\sigos.db
#>
[CmdletBinding()] param(
    [Parameter(Mandatory)][string]$BackupFile,
    [switch]$Force,
    [switch]$SkipStart
)
. "$PSScriptRoot\common.ps1"
Assert-SigosAdmin
if (-not (Test-Path $SigosPaths.InstallCfg)) { Stop-Sigos $EXIT_NOT_INSTALL 'No hay install.json: SIGOS no esta instalado.' }
$cfg = Get-Content $SigosPaths.InstallCfg -Raw | ConvertFrom-Json
$logFile = Start-SigosScriptLog 'restore'
try {
$server = "$($cfg.SqlHost),$($cfg.SqlPort)"

# --- 1. Comprobar el respaldo ---------------------------------------------------
Write-SigosStep "Comprobando el respaldo $BackupFile"
if ($cfg.DbEngine -eq 'SqlServer') {
    if (-not (Get-Command sqlcmd.exe -ErrorAction SilentlyContinue)) { Stop-Sigos $EXIT_PREREQ 'Falta sqlcmd (Microsoft SQL Server command line utilities).' }
    $f = $BackupFile.Replace("'", "''")
    $v = Invoke-SigosSqlcmd $server "RESTORE VERIFYONLY FROM DISK = N'$f' WITH CHECKSUM;" 60
    if ($v.Code -ne 0) { Stop-Sigos $EXIT_DB "El respaldo no es valido o el servidor no puede leerlo (la ruta es del servidor): $($v.Out)" }
    $target = $cfg.DbName
} else {
    if (-not (Test-SigosSqliteFile $BackupFile)) { Stop-Sigos $EXIT_USAGE "$BackupFile no es una base SQLite." }
    $envMap = Read-SigosEnvFile $SigosPaths.EnvFile
    if (-not ($envMap.Contains('DB_URL') -and $envMap['DB_URL'] -like 'sqlite:///*')) { Stop-Sigos $EXIT_USAGE 'sigos.env no define DB_URL de SQLite.' }
    $target = ($envMap['DB_URL'] -replace '^sqlite:///', '').Replace('/', '\')
    if ([IO.Path]::GetFullPath($target) -eq [IO.Path]::GetFullPath($BackupFile)) { Stop-Sigos $EXIT_USAGE 'El respaldo es la propia base en uso.' }
}
Write-SigosOk "Respaldo valido. Destino: $target"

# --- 2. Confirmacion ---------------------------------------------------------------
if (-not $Force) {
    $name = Split-Path $target -Leaf
    $answer = Read-Host "Se SUSTITUIRA el contenido de '$name' por el del respaldo (antes se guarda una copia). Escribe RESTAURAR $name para confirmar"
    if ($answer -ne "RESTAURAR $name") { Write-SigosWarn 'Restauracion cancelada.'; exit $EXIT_USAGE }
}

# --- 3. Detener servicios --------------------------------------------------------------
if (Test-SigosInstalled) {
    & "$PSScriptRoot\stop-services.ps1"
    if ($LASTEXITCODE -ne 0) { Stop-Sigos $LASTEXITCODE 'No se pudieron detener los servicios: no se restaura.' }
}

# --- 4-5. Copia de seguridad del estado actual y restauracion ----------------------------
if ($cfg.DbEngine -eq 'SqlServer') {
    Write-SigosStep 'Respaldo de seguridad del estado actual'
    $safety = & (Join-Path $SigosRepoRoot 'scripts\backup-db.ps1') -Server $server -Database $target -UseInstanceBackupDir -RetentionDays 36500 -PassThru
    if ($LASTEXITCODE -ne 0) { Stop-Sigos $EXIT_DB 'No se pudo respaldar el estado actual: no se restaura. Los servicios quedan detenidos.' }
    Write-SigosOk "Estado actual guardado en $(@($safety)[-1])"
    Write-SigosStep "Restaurando [$target]"
    $r = Restore-SigosSqlServerDb -Server $server -Database $target -BackupFile $BackupFile
    if ($r.Code -ne 0) { Stop-Sigos $EXIT_DB "RESTORE fallo: $($r.Out). Copia del estado previo: $(@($safety)[-1])" }
} else {
    $safetyDir = Join-Path $SigosPaths.BackupDir ('pre-restore-{0:yyyyMMdd-HHmmss}' -f (Get-Date))
    New-Item -ItemType Directory -Force -Path $safetyDir | Out-Null
    if (Test-Path $target) { Copy-Item -LiteralPath $target -Destination $safetyDir }
    Write-SigosOk "Estado actual guardado en $safetyDir"
    Copy-Item -LiteralPath $BackupFile -Destination $target -Force
    Set-SigosAcl -Path $SigosPaths.DataDir -Modify ($SigosServices | ForEach-Object { "NT SERVICE\$_" })
}
Write-SigosOk 'Base restaurada'
Write-SigosWarn 'Si el respaldo es de una version anterior, la version instalada puede necesitar migraciones: update-windows.ps1 las aplica.'

# --- 6. Arranque ---------------------------------------------------------------------
if ($SkipStart -or -not (Test-SigosInstalled)) { exit $EXIT_OK }
& "$PSScriptRoot\start-services.ps1"
exit $LASTEXITCODE
} finally {
    Stop-Transcript | Out-Null
}
