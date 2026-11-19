#Requires -Version 5.1
<# .SYNOPSIS Detiene SIGOS-Worker y SIGOS-API (orden inverso, apagado ordenado). #>
[CmdletBinding()] param([int]$TimeoutSec = 90)
. "$PSScriptRoot\common.ps1"
Assert-SigosAdmin
if (-not (Test-SigosInstalled)) { Stop-Sigos $EXIT_NOT_INSTALL 'SIGOS no esta instalado.' }
foreach ($s in ($SigosServices[($SigosServices.Count - 1)..0])) {
    if ((Get-SigosService $s).Status -ne 'Stopped') { Stop-Service -Name $s -Force }
    if (-not (Wait-SigosServiceStatus $s 'Stopped' $TimeoutSec)) { Stop-Sigos $EXIT_SERVICE "$s no se detuvo en $TimeoutSec s." }
    Write-SigosOk "$s detenido"
}
exit $EXIT_OK
