#Requires -Version 5.1
<#
.SYNOPSIS
  Recopila un diagnostico tecnico de SIGOS en un .zip, SIN secretos.

.DESCRIPTION
  Incluye: sistema y versiones, install.json, paquetes del venv, configuracion de los servicios en el SCM
  (cuenta, inicio, dependencias, acciones ante fallo), vida (/health/live) y salud (/health), heartbeat
  del worker, puerto y firewall, drivers ODBC y conectividad TCP con SQL Server, permisos NTFS, claves de
  sigos.env (los valores sensibles se sustituyen por <definido, N caracteres>), eventos del Service Control
  Manager y las ultimas lineas de cada log.

  Todo el texto pasa por Protect-SigosText y, antes de comprimir, se comprueba que ningun valor secreto de
  sigos.env/admin.env aparezca en los archivos; si aparece, no se genera el .zip.

  Como administrador guarda en C:\ProgramData\SIGOS\logs\system; sin administrador, en %TEMP% (con menos datos).
  Codigos: 0 sin problemas detectados · 6 diagnostico generado con problemas detectados · 5 fallo al generarlo.

.EXAMPLE
  .\diagnose-windows.ps1
.EXAMPLE
  .\diagnose-windows.ps1 -LogLines 500 -OutDir C:\soporte
#>
[CmdletBinding()] param(
    [ValidateRange(10, 5000)][int]$LogLines = 200,
    [string]$OutDir
)
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = 'Continue'   # un fallo parcial no debe impedir el resto del diagnostico

$isAdmin = Test-SigosAdmin
if (-not $OutDir) { if ($isAdmin) { $OutDir = $SigosPaths.SystemLog } else { $OutDir = [IO.Path]::GetTempPath() } }
$stamp = '{0:yyyyMMdd-HHmmss}' -f (Get-Date)
$work = Join-Path $OutDir "diagnose-$stamp"
New-Item -ItemType Directory -Force -Path $work, (Join-Path $work 'logs') | Out-Null

$secrets = Get-SigosSecretValues
$problems = New-Object System.Collections.Generic.List[string]
function Add-Problem([string]$m) { $problems.Add($m); Write-SigosWarn $m }
function Save-Diag([string]$Name, $Content, [switch]$KnownSecretsOnly) {
    $text = ($Content | Out-String -Width 250)
    if ($KnownSecretsOnly) { foreach ($s in $secrets) { if ($s) { $text = $text.Replace($s, '***') } } }
    else { $text = Protect-SigosText $text $secrets }
    [IO.File]::WriteAllText((Join-Path $work $Name), $text, (New-Object Text.UTF8Encoding($false)))
}
function Get-Safe([scriptblock]$Body) { try { & $Body 2>&1 | Out-String -Width 250 } catch { "ERROR: $($_.Exception.Message)" } }

Write-SigosStep "Recopilando diagnostico en $work"
if (-not $isAdmin) { Write-SigosWarn 'Sin administrador: no se leen sigos.env, logs ni heartbeat. Ejecuta como administrador para un diagnostico completo.' }

# --- Sistema y versiones -------------------------------------------------------
$cfg = $null
if (Test-Path $SigosPaths.InstallCfg) { try { $cfg = Get-Content $SigosPaths.InstallCfg -Raw | ConvertFrom-Json } catch { } }
$os = Get-CimInstance Win32_OperatingSystem
$venvPy = Join-Path $SigosPaths.Venv 'Scripts\python.exe'
$summary = [ordered]@{
    Fecha            = (Get-Date).ToString('s')
    Equipo           = $env:COMPUTERNAME
    Sistema          = "$($os.Caption) $($os.Version) (build $($os.BuildNumber))"
    Arquitectura     = $env:PROCESSOR_ARCHITECTURE
    UltimoArranque   = $os.LastBootUpTime
    PowerShell       = $PSVersionTable.PSVersion.ToString()
    Administrador    = $isAdmin
    VersionInstalada = Get-SigosInstalledVersion
    VersionScripts   = Get-SigosSourceVersion
    InstallDir       = (Test-Path $SigosPaths.InstallDir)
    DataRoot         = (Test-Path $SigosPaths.DataRoot)
}
if (Test-Path $venvPy) { $summary['PythonVenv'] = (& $venvPy -c "import sys; print(sys.version.split()[0])" 2>&1 | Out-String).Trim() }
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($env:SystemDrive)'"
if ($disk) { $summary['LibreDiscoSistemaGB'] = [math]::Round($disk.FreeSpace / 1GB, 1) }
Save-Diag 'summary.txt' @(([pscustomobject]$summary | Format-List), '--- install.json ---', ($cfg | Format-List))
if (Test-Path $venvPy) { Save-Diag 'pip-freeze.txt' (Get-Safe { & $venvPy -m pip freeze --disable-pip-version-check }) }
if (-not (Test-Path $SigosPaths.InstallDir)) { Add-Problem "No existe $($SigosPaths.InstallDir): SIGOS no esta instalado." }

# --- Servicios (SCM) -------------------------------------------------------------
$svcText = foreach ($s in $SigosServices) {
    "===== $s ====="
    $w = Get-CimInstance Win32_Service -Filter "Name='$s'"
    if (-not $w) { "(no registrado)"; Add-Problem "$s no esta registrado."; continue }
    $w | Select-Object Name, DisplayName, State, Status, StartMode, DelayedAutoStart, StartName, ProcessId, ExitCode, PathName | Format-List
    if ($w.State -ne 'Running') { Add-Problem "$s esta en estado $($w.State)." }
    if ($w.StartName -ne "NT SERVICE\$s") { Add-Problem "$s corre como '$($w.StartName)' (esperado NT SERVICE\$s)." }
    Get-Safe { & sc.exe qc $s }
    Get-Safe { & sc.exe qfailure $s }
    Get-Safe { & sc.exe enumdepend $s }
}
$sqlSvcName = ''
if ($cfg -and $cfg.PSObject.Properties.Name -contains 'SqlServiceName') { $sqlSvcName = [string]$cfg.SqlServiceName }
if ($sqlSvcName) {
    $sq = Get-SigosService $sqlSvcName
    $svcText += "===== $sqlSvcName (SQL Server) ====="
    if ($sq) { $svcText += ($sq | Format-List Name, Status, StartType | Out-String); if ($sq.Status -ne 'Running') { Add-Problem "SQL Server ($sqlSvcName) esta $($sq.Status)." } }
    else { Add-Problem "No existe el servicio de SQL Server '$sqlSvcName'." }
}
Save-Diag 'services.txt' $svcText

# --- Vida y salud ----------------------------------------------------------------
$live = Invoke-SigosLiveness 5
$health = $null
try { $health = Invoke-RestMethod -Uri (Get-SigosHealthUrl) -TimeoutSec 10 -UseBasicParsing } catch {
    # 503 (BD caida) llega como excepcion: se conserva el cuerpo.
    try { $health = (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() } catch { $health = "ERROR: $($_.Exception.Message)" }
}
$interval = Get-SigosWorkerInterval
$age = $null; try { $age = Get-SigosHeartbeatAge } catch { }
Save-Diag 'health.txt' @(
    "live   $(Get-SigosLiveUrl)", ($live | ConvertTo-Json -Depth 5),
    "health $(Get-SigosHealthUrl)", $(if ($health -is [string]) { $health } else { $health | ConvertTo-Json -Depth 5 }),
    "heartbeat del worker: $(if ($null -eq $age) { 'sin datos' } else { "$age s" }) (intervalo $interval s)")
if (-not $live) { Add-Problem 'La API no responde en /health/live (proceso caido, arrancando o puerto ocupado).' }
elseif (-not ($health -and $health -isnot [string] -and $health.status -eq 'UP')) { Add-Problem 'La API esta viva pero /health no esta UP: revisa la base de datos.' }
if ($isAdmin) {
    if ($null -eq $age) { Add-Problem 'El worker no ha escrito nunca el heartbeat.' }
    elseif ($age -gt 3 * $interval) { Add-Problem "Heartbeat del worker antiguo ($age s > 3 x $interval s)." }
}

# --- Red, firewall y base de datos -------------------------------------------------
$listen = Get-SigosListen
$net = @("Escucha configurada: $($listen.Address):$($listen.Port)")
$conns = @(Get-NetTCPConnection -LocalPort $listen.Port -State Listen -ErrorAction SilentlyContinue)
foreach ($c in $conns) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue
    $net += "  $($c.LocalAddress):$($c.LocalPort) PID $($c.OwningProcess) $(if ($proc) { $proc.Name })"
}
if (-not $conns) { $net += '  (nadie escucha en el puerto)' }
$fw = Get-NetFirewallRule -Name 'SIGOS-API-In' -ErrorAction SilentlyContinue
$net += "Regla de firewall SIGOS-API-In: $(if ($fw) { "habilitada=$($fw.Enabled) perfiles=$($fw.Profile)" } else { 'no existe' })"
if ($listen.Address -eq '0.0.0.0') { $net += 'AVISO: la API escucha en todas las interfaces.' }
$net += '--- Drivers ODBC (64 bits) ---'
$net += (Get-OdbcDriver -Platform '64-bit' -ErrorAction SilentlyContinue | Where-Object Name -like '*SQL Server*' | ForEach-Object Name)
if ($cfg -and $cfg.DbEngine -eq 'SqlServer') {
    $tcp = New-Object Net.Sockets.TcpClient
    try { $ok = $tcp.ConnectAsync([string]$cfg.SqlHost, [int]$cfg.SqlPort).Wait(5000) } catch { $ok = $false } finally { $tcp.Dispose() }
    $net += "TCP a SQL Server $($cfg.SqlHost):$($cfg.SqlPort): $(if ($ok) { 'OK' } else { 'SIN CONEXION' })"
    if (-not $ok) { Add-Problem "Sin conexion TCP con SQL Server en $($cfg.SqlHost):$($cfg.SqlPort)." }
}
Save-Diag 'network.txt' $net

# --- Configuracion (sin valores sensibles) --------------------------------------
if ($isAdmin) {
    $cfgText = @('--- sigos.env ---')
    $m = Read-SigosEnvFile $SigosPaths.EnvFile
    foreach ($k in $m.Keys) {
        $v = [string]$m[$k]
        if ($k -match $SigosSecretKeyPattern) { $v = $(if ($v) { "<definido, $($v.Length) caracteres>" } else { '<vacio>' }) }
        $cfgText += "$k=$v"
    }
    foreach ($req in 'JWT_SECRET_KEY', 'SIGOS_ENV') { if (-not ($m.Contains($req) -and $m[$req])) { Add-Problem "sigos.env no define $req." } }
    $cfgText += '--- admin.env (solo claves) ---'
    $cfgText += (Read-SigosEnvFile $SigosPaths.AdminEnv).Keys
    Save-Diag 'config.txt' $cfgText -KnownSecretsOnly   # los valores sensibles ya se sustituyeron arriba
}

# --- Permisos ----------------------------------------------------------------------
$aclText = foreach ($p in @($SigosPaths.InstallDir, $SigosPaths.ConfigDir, $SigosPaths.EnvFile, $SigosPaths.AdminEnv,
                            $SigosPaths.DataDir, $SigosPaths.LogDir, $SigosPaths.InstallLog, $SigosPaths.RunDir, $SigosPaths.BackupDir)) {
    if (Test-Path $p) { Get-Safe { & icacls.exe $p } }
}
Save-Diag 'acl.txt' $aclText
if ($isAdmin -and (Test-Path $SigosPaths.EnvFile)) {
    $ids = (Get-Acl $SigosPaths.EnvFile).Access | ForEach-Object { $_.IdentityReference.Value }
    if ($ids -match '\\(Users|Usuarios|Everyone|Todos|Authenticated Users|Usuarios autentificados)$') { Add-Problem 'sigos.env es legible por usuarios no administradores.' }
}

# --- Eventos y logs ---------------------------------------------------------------
$ev = Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Service Control Manager'; StartTime = (Get-Date).AddDays(-7) } -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -like '*SIGOS*' } | Select-Object -First 200 TimeCreated, Id, LevelDisplayName, Message
Save-Diag 'events-scm.txt' ($ev | Format-Table -Wrap -AutoSize)

if ($isAdmin) {
    $logSets = @(
        @{ Dir = (Join-Path $SigosPaths.LogDir 'api'); Take = 10 },
        @{ Dir = (Join-Path $SigosPaths.LogDir 'worker'); Take = 10 },
        @{ Dir = $SigosPaths.InstallLog; Take = 3 }
    )
    foreach ($set in $logSets) {
        if (-not (Test-Path $set.Dir)) { continue }
        $leaf = Split-Path $set.Dir -Leaf
        Get-ChildItem -LiteralPath $set.Dir -Filter *.log -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending |
            Select-Object -First $set.Take | ForEach-Object {
                Save-Diag ("logs\{0}-{1}" -f $leaf, $_.Name) (Get-Content -LiteralPath $_.FullName -Tail $LogLines -ErrorAction SilentlyContinue)
            }
    }
}

# --- Problemas, verificacion de secretos y empaquetado ---------------------------
Save-Diag 'problems.txt' $(if ($problems.Count) { $problems } else { 'Sin problemas detectados.' })
$leaks = @()
foreach ($f in Get-ChildItem -LiteralPath $work -Recurse -File) {
    $t = [IO.File]::ReadAllText($f.FullName)
    foreach ($s in $secrets) { if ($s -and $t.Contains($s)) { $leaks += $f.Name; break } }
}
if ($leaks) {
    Remove-Item -LiteralPath $work -Recurse -Force
    Write-Host "    [ERROR] Se detecto un secreto en: $($leaks -join ', '). Diagnostico descartado." -ForegroundColor Red
    exit $EXIT_SERVICE
}
$zip = "$work.zip"
try {
    Compress-Archive -Path (Join-Path $work '*') -DestinationPath $zip -Force -ErrorAction Stop
    Remove-Item -LiteralPath $work -Recurse -Force
} catch {
    Write-SigosWarn "No se pudo comprimir ($($_.Exception.Message)); queda la carpeta $work"
    $zip = $work
}
# Retencion: 20 diagnosticos en logs\system
if ($OutDir -eq $SigosPaths.SystemLog) {
    Get-ChildItem -LiteralPath $OutDir -Filter 'diagnose-*.zip' | Sort-Object Name -Descending | Select-Object -Skip 20 | Remove-Item -Force
}

Write-Host ''
if ($problems.Count) {
    Write-Host "Diagnostico: $zip ($($problems.Count) problema(s) detectado(s))" -ForegroundColor Yellow
    exit $EXIT_HEALTH
}
Write-Host "Diagnostico: $zip (sin problemas detectados)" -ForegroundColor Green
exit $EXIT_OK
