#Requires -Version 5.1
<#
.SYNOPSIS
  Comprime las evidencias/firmas subidas (uploads) en <BackupDir>\uploads_<fecha>.zip.
.DESCRIPTION
  Sin -SourceDir: usa C:\ProgramData\SIGOS\data\uploads (instalacion nativa de Windows) si existe y,
  si no, services\api\uploads relativo a este repositorio (desarrollo). Codigos: 0 creado · 1 fallo.
#>
param(
    [string]$SourceDir,
    [string]$BackupDir = "C:\Backups\SIGOS\uploads"
)

if (-not $SourceDir) {
    $native = Join-Path $env:ProgramData 'SIGOS\data\uploads'
    $SourceDir = $(if (Test-Path $native) { $native } else { Join-Path $PSScriptRoot '..\services\api\uploads' })
}

$date = Get-Date -Format "yyyyMMdd"
$backupFile = Join-Path $BackupDir "uploads_$date.zip"

if (-not (Test-Path $SourceDir)) {
    Write-Host "No uploads directory found: $SourceDir" -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
if (-not (Get-ChildItem -LiteralPath $SourceDir -Force | Select-Object -First 1)) {
    Write-Host "Uploads directory is empty: $SourceDir (nothing to back up)"
    exit 0
}
Compress-Archive -Path (Join-Path $SourceDir '*') -DestinationPath $backupFile -Force
Write-Host "Uploads backup: $backupFile"
exit 0
