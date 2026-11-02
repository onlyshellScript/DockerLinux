param(
    [string]$Server = "localhost,1433",
    [string]$Database = "sigos",
    [string]$BackupDir = "C:\Backups\SIGOS",
    [int]$RetentionDays = 30
)

$date = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $BackupDir "sigos_$date.bak"

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

sqlcmd -S $Server -E -C -Q "BACKUP DATABASE [$Database] TO DISK = N'$backupFile' WITH INIT, FORMAT, COMPRESSION;"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Backup created: $backupFile"
} else {
    Write-Error "Backup failed"
    exit 1
}

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "sigos_*.bak" | Where-Object { $_.LastWriteTime -lt $cutoff } | Remove-Item -Force
Write-Host "Old backups cleaned (retention: $RetentionDays days)"
