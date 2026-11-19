#Requires -Version 5.1
<# .SYNOPSIS Reinicia los servicios SIGOS (stop + start con comprobacion de health). #>
[CmdletBinding()] param()
. "$PSScriptRoot\common.ps1"
Assert-SigosAdmin
& "$PSScriptRoot\stop-services.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& "$PSScriptRoot\start-services.ps1"
exit $LASTEXITCODE
