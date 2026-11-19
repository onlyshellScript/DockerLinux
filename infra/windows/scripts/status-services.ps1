#Requires -Version 5.1
<#
.SYNOPSIS
  Estado de SIGOS en tres capas, que se diagnostican por separado:
    1. Service Control Manager: estado, inicio, cuenta, PID de cada servicio.
    2. Vida del proceso:   GET /api/v1/health/live  (responde aunque la BD este caida).
    3. Salud funcional:    GET /api/v1/health (BD)  y heartbeat del worker.
  No requiere administrador (sin admin no puede leer sigos.env ni el heartbeat: se avisa).
  Codigo 0 si todo esta sano, 6 si algo falla, 7 si no esta instalado.
#>
[CmdletBinding()] param()
. "$PSScriptRoot\common.ps1"
if (-not (Test-SigosInstalled)) { Write-SigosWarn 'SIGOS no esta instalado.'; exit $EXIT_NOT_INSTALL }
$healthy = $true

$installed = Get-SigosInstalledVersion
if ($installed) { Write-SigosInfo "Version instalada: $installed" }

Write-SigosStep '1. Service Control Manager'
$rows = foreach ($s in $SigosServices) {
    $w = Get-CimInstance Win32_Service -Filter "Name='$s'"
    if ($w.State -ne 'Running') { $healthy = $false }
    [pscustomobject]@{ Servicio = $s; Estado = $w.State; Inicio = $w.StartMode; Retrasado = $w.DelayedAutoStart; Cuenta = $w.StartName; PID = $w.ProcessId }
}
$rows | Format-Table -AutoSize | Out-String | Write-Host

Write-SigosStep '2. Vida del proceso de la API'
$live = Invoke-SigosLiveness 5
if ($live) { Write-SigosOk "$(Get-SigosLiveUrl): UP (version=$($live.version))" }
else { Write-SigosWarn "$(Get-SigosLiveUrl): sin respuesta (proceso caido, arrancando o puerto ocupado)"; $healthy = $false }

Write-SigosStep '3. Salud funcional'
$h = Invoke-SigosHealth 5
if ($h) {
    $lat = ''
    if ($h.PSObject.Properties.Name -contains 'latency_ms') { $lat = ", latencia BD=$($h.latency_ms.database) ms" }
    Write-SigosOk "API $(Get-SigosHealthUrl): $($h.status) (database=$($h.checks.database)$lat)"
} elseif ($live) {
    Write-SigosWarn "API viva pero $(Get-SigosHealthUrl) no responde UP: la base de datos no esta disponible (ver logs\api\*.err.log)"
    $healthy = $false
} else {
    Write-SigosWarn "API $(Get-SigosHealthUrl): sin respuesta UP"
    $healthy = $false
}

# El heartbeat lo escribe el worker en cada ciclo; sin admin el intervalo cae al valor por defecto (30 s).
$interval = Get-SigosWorkerInterval
$age = $null
try { $age = Get-SigosHeartbeatAge } catch { }
if ($null -eq $age) { Write-SigosWarn 'Worker: sin heartbeat (o sin permiso para leerlo; ejecuta como administrador)'; $healthy = $false }
elseif ($age -gt 3 * $interval) { Write-SigosWarn "Worker: heartbeat de hace $age s (> 3 x $interval s): el bucle esta detenido o bloqueado"; $healthy = $false }
else { Write-SigosOk "Worker: heartbeat hace $age s" }

if ($healthy) { exit $EXIT_OK } else { exit $EXIT_HEALTH }
