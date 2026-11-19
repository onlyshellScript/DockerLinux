#Requires -Version 5.1
<#
.SYNOPSIS Desinstala los servicios SIGOS y borra C:\Program Files\SIGOS.
.DESCRIPTION
  Por defecto CONSERVA C:\ProgramData\SIGOS (configuracion, secretos, SQLite, uploads, logs, respaldos)
  y la base de SQL Server: una reinstalacion posterior los reutiliza.
  -PurgeData borra tambien C:\ProgramData\SIGOS (pide confirmacion salvo -Force). Nunca borra la base de SQL Server.
#>
[CmdletBinding()] param([switch]$PurgeData, [switch]$Force)
. "$PSScriptRoot\common.ps1"
Assert-SigosAdmin

foreach ($s in ($SigosServices[($SigosServices.Count - 1)..0])) {
    $svc = Get-SigosService $s
    if (-not $svc) { continue }
    if ($svc.Status -ne 'Stopped') {
        Stop-Service -Name $s -Force
        if (-not (Wait-SigosServiceStatus $s 'Stopped' 90)) { Stop-Sigos $EXIT_SERVICE "No se pudo detener $s." }
    }
    if ((Invoke-SigosWinSW $s 'uninstall') -ne 0) { & sc.exe delete $s | Out-Null }
    Write-SigosOk "$s eliminado"
}
if (Get-NetFirewallRule -Name 'SIGOS-API-In' -ErrorAction SilentlyContinue) {
    Remove-NetFirewallRule -Name 'SIGOS-API-In'
    Write-SigosOk 'Regla de firewall eliminada'
}
if (Test-Path $SigosPaths.InstallDir) {
    Remove-Item -LiteralPath $SigosPaths.InstallDir -Recurse -Force
    Write-SigosOk "$($SigosPaths.InstallDir) eliminado"
}
if ($PurgeData) {
    if (-not $Force) {
        $answer = Read-Host "Se borrara $($SigosPaths.DataRoot) (config, secretos, SQLite, uploads, respaldos). Escribe BORRAR para confirmar"
        if ($answer -ne 'BORRAR') { Write-SigosWarn 'Datos conservados.'; exit $EXIT_OK }
    }
    if (Test-Path $SigosPaths.DataRoot) { Remove-Item -LiteralPath $SigosPaths.DataRoot -Recurse -Force }
    Write-SigosOk "$($SigosPaths.DataRoot) eliminado (la base de SQL Server, si existe, no se toca)"
} else {
    Write-SigosInfo "Datos conservados en $($SigosPaths.DataRoot)"
}
exit $EXIT_OK
