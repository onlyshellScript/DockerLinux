#Requires -Version 5.1
# Contexto comun de SigosWindows.Tests.ps1. Se carga en cada BeforeAll (Pester 3.4 y 5: en Pester 5 el codigo
# fuera de BeforeAll/It solo se ejecuta en la fase de descubrimiento).
$script:winRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:scripts = Join-Path $winRoot 'scripts'
$script:repoRoot = (Resolve-Path (Join-Path $winRoot '..\..')).Path
. (Join-Path $scripts 'common.ps1')
$ErrorActionPreference = 'Continue'
Set-StrictMode -Off

function Assert-True($cond, [string]$msg) { if (-not $cond) { throw "Fallo: $msg" } }

# Todos los .ps1 que se distribuyen o ejecutan en Windows.
function Get-SigosPs1Files {
    @(Get-ChildItem $winRoot -Recurse -Filter *.ps1) + @(Get-ChildItem (Join-Path $repoRoot 'scripts') -Filter 'backup-*.ps1' -ErrorAction SilentlyContinue)
}
