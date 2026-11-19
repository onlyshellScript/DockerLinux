#Requires -Version 5.1
<#
.SYNOPSIS
  Comprueba la integridad de un paquete SIGOS-Windows extraido: SHA-256 de cada archivo contra package-manifest.json.
  No requiere administrador ni modifica nada. Codigos: 0 integro · 3 incompleto/alterado · 1 no es un paquete.
.EXAMPLE
  .\verify-package.ps1
#>
[CmdletBinding()] param()
. "$PSScriptRoot\common.ps1"
$r = Test-SigosPackage
if (-not $r.IsPackage) { Write-SigosWarn "$SigosRepoRoot no contiene package-manifest.json (no es un paquete de distribucion)."; exit $EXIT_USAGE }
if (-not $r.Ok) {
    $r.Problems | ForEach-Object { Write-SigosInfo $_ }
    Stop-Sigos $EXIT_PREREQ "Paquete $($r.Version) incompleto o alterado: $($r.Problems.Count) problema(s)."
}
Write-SigosOk "Paquete SIGOS $($r.Version): $($r.Files) archivos integros (SHA-256)"
exit $EXIT_OK
