#Requires -Version 5.1
<#
.SYNOPSIS
  Construye SIGOS-Windows-vX.Y.Z.zip: paquete de instalacion autonomo (sin Git, Docker ni Internet).

.DESCRIPTION
  Contenido (misma estructura relativa que el repositorio, para que los scripts no dependan de este):
    services/api/        codigo de la API y migraciones (sin tests, .env, bases, uploads, logs, caches ni .bak)
    infra/windows/       instalador, scripts, plantillas WinSW, configuracion de ejemplo, pruebas, README
      bin/WinSW.NET461.exe   verificado contra services/winsw.lock.json
      requirements-windows.lock.txt  versiones exactas de todas las dependencias (incluidas transitivas)
    scripts/             backup-db.ps1, backup-uploads.ps1, backup_sqlite.py
    wheels/              ruedas win_amd64 / cp312 de todas las dependencias (instalacion sin conexion)
    INSTALL.md           guia de instalacion en otra maquina
    package-manifest.json  version, commit, fecha y SHA-256 de cada archivo
    SHA256SUMS.txt       mismo listado en formato sha256sum
  Y fuera del zip: SIGOS-Windows-vX.Y.Z.zip.sha256.

  Antes de comprimir rechaza el paquete si encuentra archivos prohibidos (.env, bases, logs, claves, .git, .bak)
  o patrones de secretos, y lo verifica con Test-SigosPackage.

.PARAMETER PythonExe
  Python 3.12 x64 con el que se descargan las ruedas (por defecto: py -3.12).
.PARAMETER NoWheels
  Paquete sin ruedas: el instalador las descargara de PyPI (requiere Internet en el destino).

.EXAMPLE
  .\infra\windows\package\build-package.ps1
#>
[CmdletBinding()] param(
    [string]$PythonExe,
    [string]$OutDir,
    [string]$WinSWPath,
    [switch]$NoWheels,
    [switch]$Force
)
. (Join-Path $PSScriptRoot '..\scripts\common.ps1')
$repo = $SigosRepoRoot
if (-not $OutDir) { $OutDir = Join-Path $repo 'dist' }

function Invoke-Robo([string]$From, [string]$To, [string[]]$XD = @(), [string[]]$XF = @()) {
    $a = @($From, $To, '/E', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($XD) { $a += '/XD'; $a += $XD }
    if ($XF) { $a += '/XF'; $a += $XF }
    & robocopy.exe @a | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $From fallo ($LASTEXITCODE)" }
}

# --- Version ------------------------------------------------------------------------
$version = Get-SigosSourceVersion
if ($version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z\.-]+)?$') { Stop-Sigos $EXIT_PREREQ "services\api\VERSION invalida: '$version'" }
$name = "SIGOS-Windows-v$version"
$stage = Join-Path $OutDir $name
$zip = Join-Path $OutDir "$name.zip"
Write-SigosStep "Construyendo $name"
if ((Test-Path $stage) -or (Test-Path $zip)) {
    if (-not $Force) { Stop-Sigos $EXIT_USAGE "Ya existe $stage o $zip (usa -Force para regenerarlo)." }
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $zip, "$zip.sha256" -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# --- Archivos -----------------------------------------------------------------------
$xdCommon = @('__pycache__', '.pytest_cache', '.venv', 'venv', 'node_modules', '.git')
$xfCommon = @('.env', '.env.*', '*.bak', '*.pyc', '*.log', '*.db', '*.sqlite', '*.sqlite3', '*.pem', '*.pfx', '*.key')
Invoke-Robo (Join-Path $repo 'services\api') (Join-Path $stage 'services\api') `
    -XD ($xdCommon + @('tests', 'uploads', 'instance', 'versions_backup')) -XF ($xfCommon + @('salida_*.txt', 'requirements-dev.txt'))
Invoke-Robo (Join-Path $repo 'infra\windows') (Join-Path $stage 'infra\windows') -XD ($xdCommon + @('bin', 'package')) -XF $xfCommon
New-Item -ItemType Directory -Force -Path (Join-Path $stage 'scripts'), (Join-Path $stage 'infra\windows\bin') | Out-Null
foreach ($s in 'backup-db.ps1', 'backup-uploads.ps1', 'backup_sqlite.py') {
    $p = Join-Path $repo "scripts\$s"
    if (Test-Path $p) { Copy-Item -LiteralPath $p -Destination (Join-Path $stage 'scripts') }
}
(Get-Content (Join-Path $PSScriptRoot 'INSTALL.md') -Raw).Replace('{{VERSION}}', $version) |
    Set-Content -LiteralPath (Join-Path $stage 'INSTALL.md') -Encoding UTF8
Write-SigosOk 'Codigo, scripts y documentacion copiados'

# --- WinSW -------------------------------------------------------------------------
$lock = Get-Content (Join-Path $SigosWinRoot 'services\winsw.lock.json') -Raw | ConvertFrom-Json
$winsw = Join-Path $stage "infra\windows\bin\$($lock.file)"
if ($WinSWPath) { Copy-Item -LiteralPath $WinSWPath -Destination $winsw }
else {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $lock.url -OutFile $winsw -UseBasicParsing
}
if ((Get-FileHash -LiteralPath $winsw -Algorithm SHA256).Hash.ToLower() -ne $lock.sha256) {
    Remove-Item -LiteralPath $winsw -Force
    Stop-Sigos $EXIT_PREREQ 'SHA-256 de WinSW no coincide con winsw.lock.json.'
}
Write-SigosOk "WinSW $($lock.version) incluido (SHA-256 verificado)"

# --- Dependencias ------------------------------------------------------------------------
$pythonTag = 'cp312-win_amd64'
if (-not $NoWheels) {
    if (-not $PythonExe) { $PythonExe = (& py.exe -3.12 -c "import sys; print(sys.executable)") }
    $wheels = Join-Path $stage 'wheels'
    New-Item -ItemType Directory -Force -Path $wheels | Out-Null
    & $PythonExe -m pip download --disable-pip-version-check -q --only-binary=:all: --platform win_amd64 `
        --python-version 3.12 --implementation cp -d $wheels -r (Join-Path $SigosWinRoot 'requirements-windows.txt')
    if ($LASTEXITCODE -ne 0) { Stop-Sigos $EXIT_PREREQ 'pip download fallo.' }
    $lockLines = @('# Generado por build-package.ps1: versiones exactas incluidas en wheels/ (no editar).')
    foreach ($w in Get-ChildItem -LiteralPath $wheels -Filter *.whl | Sort-Object Name) {
        $parts = $w.BaseName -split '-'
        $lockLines += "$($parts[0])==$($parts[1])"
    }
    $other = @(Get-ChildItem -LiteralPath $wheels -File | Where-Object Extension -ne '.whl')
    if ($other) { Stop-Sigos $EXIT_PREREQ "Hay dependencias sin rueda binaria: $($other.Name -join ', ')" }
    [IO.File]::WriteAllLines((Join-Path $stage 'infra\windows\requirements-windows.lock.txt'), $lockLines, (New-Object Text.UTF8Encoding($false)))
    Write-SigosOk "$($lockLines.Count - 1) ruedas $pythonTag y requirements-windows.lock.txt"
}

# --- Controles de seguridad ----------------------------------------------------------------
$forbidden = Get-ChildItem -LiteralPath $stage -Recurse -Force | Where-Object {
    ($_.PSIsContainer -and $_.Name -in @('.git', '__pycache__', 'uploads', 'tests') -and $_.FullName -notlike '*\infra\windows\tests') -or
    (-not $_.PSIsContainer -and ($_.Name -eq '.env' -or $_.Name -like '.env.*' -or $_.Extension -in @('.db', '.sqlite', '.sqlite3', '.bak', '.log', '.pem', '.pfx', '.key', '.pyc')))
}
if ($forbidden) { $forbidden | ForEach-Object { Write-SigosInfo $_.FullName }; Stop-Sigos $EXIT_PREREQ 'El paquete contiene archivos prohibidos.' }
$hits = @(Find-SigosSecretLeaks $stage)
# Rutas de un perfil concreto (p. ej. C:\Users\<persona>\...): el paquete no debe depender de la maquina que lo construye.
$hits += @(Get-ChildItem -LiteralPath $stage -Recurse -File | Where-Object Extension -in @('.py', '.ps1', '.json', '.txt', '.xml', '.template', '.example') |
    Select-String -Pattern '[A-Za-z]:\\Users\\(?!\.\.\.)[A-Za-z0-9_.-]+\\' -List | ForEach-Object { "$($_.Path.Substring($stage.Length + 1)): ruta de usuario" })
if ($hits) { $hits | ForEach-Object { Write-SigosInfo $_ }; Stop-Sigos $EXIT_PREREQ 'Posibles secretos en el paquete.' }
Write-SigosOk 'Sin archivos prohibidos ni secretos'

# --- Manifiesto ----------------------------------------------------------------------------
$commit = $null; $dirty = $null
try {
    $commit = (& git -C $repo rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -eq 0) { $dirty = [bool](& git -C $repo status --porcelain 2>$null) } else { $commit = $null }
} catch { }
$files = foreach ($f in Get-ChildItem -LiteralPath $stage -Recurse -File | Sort-Object FullName) {
    [ordered]@{
        path   = $f.FullName.Substring($stage.Length + 1).Replace('\', '/')
        sha256 = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
        size   = $f.Length
    }
}
$manifest = [ordered]@{
    name = 'SIGOS-Windows'; version = $version; builtAt = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
    commit = $commit; workingTreeDirty = $dirty; python = '3.12 x64'; wheels = (-not $NoWheels); winsw = $lock.version
    files = @($files)
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'package-manifest.json') -Encoding UTF8
[IO.File]::WriteAllLines((Join-Path $stage 'SHA256SUMS.txt'), @($files | ForEach-Object { "$($_.sha256)  $($_.path)" }), (New-Object Text.UTF8Encoding($false)))

$check = Test-SigosPackage $stage
if (-not $check.Ok) { $check.Problems | ForEach-Object { Write-SigosInfo $_ }; Stop-Sigos $EXIT_PREREQ 'El paquete no supera su propia verificacion.' }
Write-SigosOk "Manifiesto: $($check.Files) archivos con SHA-256"
if ($dirty) { Write-SigosWarn "Construido con cambios sin commitear (commit base $commit): queda registrado en el manifiesto." }

# --- Zip --------------------------------------------------------------------------------------
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($stage, $zip, [IO.Compression.CompressionLevel]::Optimal, $true)
$zipHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
[IO.File]::WriteAllText("$zip.sha256", "$zipHash  $name.zip`n", (New-Object Text.UTF8Encoding($false)))
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host ''
Write-Host "Paquete: $zip ($mb MB)" -ForegroundColor Green
Write-Host "SHA-256: $zipHash  ($zip.sha256)" -ForegroundColor Green
exit $EXIT_OK
