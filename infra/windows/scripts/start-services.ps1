#Requires -Version 5.1
<# .SYNOPSIS Inicia SIGOS-API y SIGOS-Worker y comprueba el health. #>
[CmdletBinding()] param([int]$TimeoutSec = 60)
. "$PSScriptRoot\common.ps1"
Assert-SigosAdmin
if (-not (Test-SigosInstalled)) { Stop-Sigos $EXIT_NOT_INSTALL 'SIGOS no esta instalado (.\install-windows.ps1).' }
foreach ($s in $SigosServices) {
    if ((Get-SigosService $s).Status -ne 'Running') { Start-Service -Name $s }
    if (-not (Wait-SigosServiceStatus $s 'Running' $TimeoutSec)) {
        Stop-Sigos $EXIT_SERVICE "$s no arranco. Diagnostico: .\logs-services.ps1 -Service $($s.Split('-')[1].ToLower()) -Events"
    }
    Write-SigosOk "$s en ejecucion"
}
$h = Invoke-SigosHealth $TimeoutSec
if (-not $h) { Stop-Sigos $EXIT_HEALTH "La API no responde UP en $(Get-SigosHealthUrl)." }
Write-SigosOk "Health UP (database=$($h.checks.database))"
exit $EXIT_OK
