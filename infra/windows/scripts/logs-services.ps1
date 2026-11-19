#Requires -Version 5.1
<#
.SYNOPSIS Muestra los logs de SIGOS-API o SIGOS-Worker.
.EXAMPLE .\logs-services.ps1 -Service api -Tail 100
.EXAMPLE .\logs-services.ps1 -Service worker -Stream out -Follow
.EXAMPLE .\logs-services.ps1 -Service api -Events     # errores del Service Control Manager (servicio que no arranca)
#>
[CmdletBinding()] param(
    [ValidateSet('api', 'worker')][string]$Service = 'api',
    [int]$Tail = 50,
    [ValidateSet('out', 'err', 'wrapper', 'all')][string]$Stream = 'all',
    [switch]$Follow,
    [switch]$Events
)
. "$PSScriptRoot\common.ps1"
$name = @{ api = 'SIGOS-API'; worker = 'SIGOS-Worker' }[$Service]

if ($Events) {
    $ev = Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Service Control Manager'; StartTime = (Get-Date).AddDays(-7) } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -like "*$name*" } | Select-Object -First $Tail
    if (-not $ev) { Write-SigosInfo "Sin eventos de $name en el Service Control Manager (ultimos 7 dias)." }
    $ev | Format-Table TimeCreated, Id, LevelDisplayName, Message -Wrap | Out-String | Write-Host
    exit $EXIT_OK
}

$dir = Join-Path $SigosPaths.LogDir $Service
if (-not (Test-Path $dir)) { Stop-Sigos $EXIT_NOT_INSTALL "No existe $dir." }
$files = @{ out = "$name.out.log"; err = "$name.err.log"; wrapper = "$name.wrapper.log" }
$keys = @($Stream)
if ($Stream -eq 'all') { $keys = @('wrapper', 'err', 'out') }
if ($Follow -and $keys.Count -gt 1) { Stop-Sigos $EXIT_USAGE 'Usa -Follow junto con -Stream out|err|wrapper.' }
foreach ($k in $keys) {
    $f = Join-Path $dir $files[$k]
    if (-not (Test-Path $f)) { continue }
    Write-SigosStep $f
    if ($Follow) { Get-Content -LiteralPath $f -Tail $Tail -Wait } else { Get-Content -LiteralPath $f -Tail $Tail }
}
exit $EXIT_OK
