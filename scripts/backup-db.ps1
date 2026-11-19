#Requires -Version 5.1
<#
.SYNOPSIS
  Respaldo completo de una base SQL Server de SIGOS con sqlcmd (autenticacion de Windows).

.DESCRIPTION
  - Usa COMPRESSION solo si la edicion la admite (Express no: el respaldo fallaba).
  - sqlcmd -b: un error de SQL devuelve codigo != 0 (antes se informaba "Backup created" aunque fallara).
  - WITH CHECKSUM + RESTORE VERIFYONLY: el archivo se comprueba antes de darlo por bueno.
  - Retencion: borra solo <Database>_*.bak de mas de -RetentionDays dias, y solo tras un respaldo verificado.
  -BackupDir es una ruta del SERVIDOR: la cuenta del servicio de SQL Server debe poder escribir en ella.
  Con -UseInstanceBackupDir se usa la carpeta de respaldos por defecto de la instancia (ya tiene permisos).

  Codigos: 0 respaldo creado y verificado · 1 fallo.
.EXAMPLE
  .\backup-db.ps1 -Server "localhost,1433" -Database sigos -BackupDir C:\Backups\SIGOS
.EXAMPLE
  .\backup-db.ps1 -Database sigos -UseInstanceBackupDir -PassThru
#>
param(
    [string]$Server = "localhost,1433",
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]{0,127}$')][string]$Database = "sigos",
    [string]$BackupDir = "C:\Backups\SIGOS",
    [int]$RetentionDays = 30,
    [switch]$UseInstanceBackupDir,
    [switch]$PassThru
)

function Invoke-Sql([string]$Query) {
    $out = & sqlcmd.exe -S $Server -E -C -b -l 15 -h -1 -W -Q "SET NOCOUNT ON; $Query" 2>&1
    return @{ Code = $LASTEXITCODE; Out = (($out | Out-String).Trim()) }
}

if (-not (Get-Command sqlcmd.exe -ErrorAction SilentlyContinue)) { Write-Host "Backup failed: sqlcmd no esta instalado" -ForegroundColor Red; exit 1 }

$info = Invoke-Sql "SELECT CAST(SERVERPROPERTY('EngineEdition') AS varchar(5)) + '|' + CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS nvarchar(400)) + '|' + CAST(ISNULL(DB_ID(N'$Database'), 0) AS varchar(10))"
if ($info.Code -ne 0) { Write-Host "Backup failed: no se pudo consultar el servidor: $($info.Out)" -ForegroundColor Red; exit 1 }
$edition, $defaultDir, $dbId = $info.Out -split '\|', 3
if ([int]$dbId -eq 0) { Write-Host "Backup failed: la base [$Database] no existe en $Server" -ForegroundColor Red; exit 1 }
if ($UseInstanceBackupDir) { $BackupDir = $defaultDir }

$date = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $BackupDir "${Database}_$date.bak"
# En un servidor local se crea la carpeta; en uno remoto debe existir en el servidor.
try { New-Item -ItemType Directory -Path $BackupDir -Force -ErrorAction Stop | Out-Null } catch { }

$options = 'INIT, FORMAT, CHECKSUM'
if ($edition -ne '4') { $options += ', COMPRESSION' }   # 4 = Express: no admite compresion de respaldos
$file = $backupFile.Replace("'", "''")
$r = Invoke-Sql "BACKUP DATABASE [$Database] TO DISK = N'$file' WITH $options;"
if ($r.Code -ne 0) { Write-Host "Backup failed: $($r.Out)" -ForegroundColor Red; exit 1 }
$v = Invoke-Sql "RESTORE VERIFYONLY FROM DISK = N'$file' WITH CHECKSUM;"
if ($v.Code -ne 0) { Write-Host "Backup failed: el archivo no supera RESTORE VERIFYONLY: $($v.Out)" -ForegroundColor Red; exit 1 }
Write-Host "Backup created: $backupFile (verificado)"

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "${Database}_*.bak" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "Old backups cleaned (retention: $RetentionDays days)"
if ($PassThru) { Write-Output $backupFile }
exit 0
