param(
    [string]$SourceDir = "C:\Users\braya\Documents\SIGOSV\services\api\uploads",
    [string]$BackupDir = "C:\Backups\SIGOS\uploads"
)

$date = Get-Date -Format "yyyyMMdd"
$backupFile = Join-Path $BackupDir "uploads_$date.zip"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

if (Test-Path $SourceDir) {
    Compress-Archive -Path "$SourceDir\*" -DestinationPath $backupFile -Force
    Write-Host "Uploads backup: $backupFile"
} else {
    Write-Host "No uploads directory found"
}
