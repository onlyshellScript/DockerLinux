#Requires -Version 5.1
<#
  Funciones compartidas de los scripts de SIGOS para Windows.
  Se carga con: . "$PSScriptRoot\common.ps1"
  Compatible con Windows PowerShell 5.1 (sin operadores exclusivos de PowerShell 7).
#>

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# --- Rutas y nombres -------------------------------------------------------
$script:SigosInstallDir = Join-Path $env:ProgramFiles 'SIGOS'
$script:SigosDataRoot   = Join-Path $env:ProgramData  'SIGOS'
$script:SigosPaths = @{
    InstallDir = $SigosInstallDir
    AppDir     = Join-Path $SigosInstallDir 'app'
    Venv       = Join-Path $SigosInstallDir 'venv'
    BinDir     = Join-Path $SigosInstallDir 'bin'
    DataRoot   = $SigosDataRoot
    ConfigDir  = Join-Path $SigosDataRoot 'config'
    EnvFile    = Join-Path $SigosDataRoot 'config\sigos.env'
    AdminEnv   = Join-Path $SigosDataRoot 'config\admin.env'
    InstallCfg = Join-Path $SigosDataRoot 'config\install.json'
    DataDir    = Join-Path $SigosDataRoot 'data'
    UploadDir  = Join-Path $SigosDataRoot 'data\uploads'
    LogDir     = Join-Path $SigosDataRoot 'logs'
    InstallLog = Join-Path $SigosDataRoot 'logs\installer'   # install/update/uninstall (solo administradores)
    SystemLog  = Join-Path $SigosDataRoot 'logs\system'      # diagnosticos (solo administradores)
    RunDir     = Join-Path $SigosDataRoot 'run'
    BackupDir  = Join-Path $SigosDataRoot 'backups'
}
$script:SigosServices = @('SIGOS-API', 'SIGOS-Worker')   # orden de arranque
$script:SigosRepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$script:SigosWinRoot  = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# Codigos de salida comunes
$script:EXIT_OK          = 0
$script:EXIT_USAGE       = 1
$script:EXIT_NOT_ADMIN   = 2
$script:EXIT_PREREQ      = 3
$script:EXIT_DB          = 4
$script:EXIT_SERVICE     = 5
$script:EXIT_HEALTH      = 6
$script:EXIT_NOT_INSTALL = 7
$script:EXIT_ROLLED_BACK = 8   # la actualizacion fallo y se restauro la version anterior
$script:EXIT_ROLLBACK_KO = 9   # la actualizacion fallo y el rollback tambien: intervencion manual

# --- Mensajes ----------------------------------------------------------------
function Write-SigosStep([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-SigosInfo([string]$Message) { Write-Host "    $Message" }
function Write-SigosOk([string]$Message)   { Write-Host "    [OK] $Message" -ForegroundColor Green }
function Write-SigosWarn([string]$Message) { Write-Host "    [AVISO] $Message" -ForegroundColor Yellow }
function Stop-Sigos([int]$Code, [string]$Message) {
    Write-Host "    [ERROR] $Message" -ForegroundColor Red
    exit $Code
}

# --- Comprobaciones ----------------------------------------------------------
function Test-SigosAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-SigosAdmin {
    if (-not (Test-SigosAdmin)) {
        Stop-Sigos $EXIT_NOT_ADMIN 'Este script requiere una consola de PowerShell ejecutada como administrador.'
    }
}

function Get-SigosService([string]$Name) {
    return Get-Service -Name $Name -ErrorAction SilentlyContinue
}

function Test-SigosInstalled {
    foreach ($s in $SigosServices) { if (-not (Get-SigosService $s)) { return $false } }
    return $true
}

function Wait-SigosServiceStatus([string]$Name, [string]$Status, [int]$TimeoutSec = 60) {
    $svc = Get-SigosService $Name
    if (-not $svc) { return $false }
    try {
        $svc.WaitForStatus($Status, [TimeSpan]::FromSeconds($TimeoutSec))
        return $true
    } catch {
        return $false
    }
}

function Get-SigosListen {
    # Lee la direccion de escucha guardada por el instalador (sin secretos).
    if (Test-Path $SigosPaths.InstallCfg) {
        $cfg = Get-Content $SigosPaths.InstallCfg -Raw | ConvertFrom-Json
        return @{ Address = $cfg.ListenAddress; Port = [int]$cfg.Port }
    }
    return @{ Address = '127.0.0.1'; Port = 5000 }
}

function Get-SigosHealthUrl {
    $l = Get-SigosListen
    $addr = $l.Address
    if ($addr -eq '0.0.0.0') { $addr = '127.0.0.1' }
    return "http://${addr}:$($l.Port)/api/v1/health"
}

function Invoke-SigosHealth([int]$TimeoutSec = 60) {
    # Devuelve el objeto de health o $null si no responde UP dentro del plazo.
    $url = Get-SigosHealthUrl
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        try {
            $r = Invoke-RestMethod -Uri $url -TimeoutSec 5 -UseBasicParsing
            if ($r.status -eq 'UP') { return $r }
        } catch { }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    return $null
}

function Get-SigosLiveUrl { return ((Get-SigosHealthUrl) + '/live') }

function Invoke-SigosLiveness([int]$TimeoutSec = 5) {
    # Vida del proceso (no consulta la BD): distingue "proceso colgado" de "BD caida".
    try { $r = Invoke-RestMethod -Uri (Get-SigosLiveUrl) -TimeoutSec $TimeoutSec -UseBasicParsing; if ($r.status -eq 'UP') { return $r } } catch { }
    return $null
}

function Get-SigosWorkerInterval {
    $interval = 30
    try {
        $m = Read-SigosEnvFile $SigosPaths.EnvFile
        if ($m.Contains('NOTIFICATION_WORKER_INTERVAL') -and $m['NOTIFICATION_WORKER_INTERVAL'] -match '^\d+$') {
            $interval = [int]$m['NOTIFICATION_WORKER_INTERVAL']
        }
    } catch { }
    return [Math]::Max(1, $interval)
}

function Wait-SigosHeartbeat([datetime]$Since, [int]$TimeoutSec = 90) {
    # $true cuando el worker toca el heartbeat despues de $Since (prueba de que el bucle de procesamiento corre).
    $hb = Join-Path $SigosPaths.RunDir 'worker.heartbeat'
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        if ((Test-Path $hb) -and (Get-Item $hb).LastWriteTime -gt $Since) { return $true }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    return $false
}

# --- Versiones -----------------------------------------------------------------
function Get-SigosSourceVersion {
    $f = Join-Path $SigosRepoRoot 'services\api\VERSION'
    if (Test-Path $f) { return (Get-Content -LiteralPath $f -Raw).Trim() }
    return $null
}

function Get-SigosInstalledVersion {
    $f = Join-Path $SigosPaths.AppDir 'VERSION'
    if (Test-Path $f) { return (Get-Content -LiteralPath $f -Raw).Trim() }
    return $null
}

function Compare-SigosVersion([string]$A, [string]$B) {
    <# -1 si A < B, 0 si iguales, 1 si A > B. Formato MAYOR.MENOR.PARCHE[-pre]; una pre-version es menor que la final. #>
    $pa = $A.Trim() -split '-', 2; $pb = $B.Trim() -split '-', 2
    $core = { param($s) $n = @($s -split '\.' | Select-Object -First 3); while ($n.Count -lt 3) { $n += '0' }; [version]($n -join '.') }
    $va = & $core $pa[0]
    $vb = & $core $pb[0]
    $c = $va.CompareTo($vb)
    if ($c -ne 0) { return [Math]::Sign($c) }
    $ra = if ($pa.Count -gt 1) { $pa[1] } else { $null }
    $rb = if ($pb.Count -gt 1) { $pb[1] } else { $null }
    if ($ra -eq $rb) { return 0 }
    if ($null -eq $ra) { return 1 }
    if ($null -eq $rb) { return -1 }
    return [Math]::Sign([string]::CompareOrdinal($ra, $rb))
}

# --- Logs de scripts ------------------------------------------------------------
function Start-SigosScriptLog([string]$Prefix, [int]$Keep = 30) {
    <# Abre una transcripcion en logs\installer y conserva solo las $Keep mas recientes de ese prefijo. #>
    New-Item -ItemType Directory -Force -Path $SigosPaths.InstallLog | Out-Null
    Get-ChildItem -LiteralPath $SigosPaths.InstallLog -Filter "$Prefix-*.log" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep | Remove-Item -Force -ErrorAction SilentlyContinue
    $file = Join-Path $SigosPaths.InstallLog ("{0}-{1:yyyyMMdd-HHmmss}.log" -f $Prefix, (Get-Date))
    Start-Transcript -LiteralPath $file | Out-Null
    return $file
}

# --- Paquete de distribucion -------------------------------------------------------
function Test-SigosPackage([string]$Root = $SigosRepoRoot) {
    <#
      Si $Root contiene package-manifest.json (paquete SIGOS-Windows-vX.Y.Z), comprueba el SHA-256 de cada archivo listado.
      Devuelve @{ IsPackage; Ok; Version; Files; Problems }. Un repositorio git (sin manifiesto) devuelve IsPackage=$false.
    #>
    $manifestPath = Join-Path $Root 'package-manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { return @{ IsPackage = $false; Ok = $true; Problems = @() } }
    $man = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $problems = New-Object System.Collections.Generic.List[string]
    foreach ($f in $man.files) {
        $p = Join-Path $Root ($f.path -replace '/', '\')
        if (-not (Test-Path -LiteralPath $p)) { $problems.Add("falta: $($f.path)"); continue }
        $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower()
        if ($h -ne $f.sha256) { $problems.Add("modificado: $($f.path)") }
    }
    $src = Join-Path $Root 'services\api\VERSION'
    if ((Test-Path $src) -and ((Get-Content $src -Raw).Trim() -ne $man.version)) { $problems.Add("VERSION no coincide con el manifiesto ($($man.version))") }
    return @{ IsPackage = $true; Ok = ($problems.Count -eq 0); Version = $man.version; Files = @($man.files).Count; Problems = $problems.ToArray() }
}

function Find-SigosSecretLeaks([string]$Root) {
    <#
      Busca secretos en los archivos de texto bajo $Root (paquete o CI). Devuelve "ruta: inicio del hallazgo" (recortado).
      Todo archivo: claves privadas, URL mssql con contrasena, PWD=/Password= de ODBC.
      Configuracion (.env, .example, .json, ...): KEY=valor para claves sensibles (salvo el marcador GENERADO_POR_EL_INSTALADOR).
      Codigo (.py, .ps1, .sh): literales de 8+ caracteres asignados a nombres *password*/*secret*/*token*/*api_key*.
    #>
    $anyPatterns = @(
        '-----BEGIN [A-Z ]*PRIVATE KEY-----',
        'mssql\+pyodbc://[^:/\s]+:[^@\s\$\{\}]{6,}@',
        '(?i)\b(PWD|Password)=\{?[^;\s\{\}\$]{6,}\}?;'
    )
    $envKeys = 'JWT_SECRET_KEY|DB_APP_PASSWORD|DB_MIGRATOR_PASSWORD|MSSQL_SA_PASSWORD|SMTP_PASS|WHATSAPP_API_TOKEN|ADMIN_PASSWORD|DB_URL'
    $configPattern = "(?im)^[ \t]*($envKeys)[ \t]*=[ \t]*(?!GENERADO_POR_EL_INSTALADOR[ \t]*\r?$)(?!sqlite:)[^\s#]{6,}"
    $codePattern = '(?i)\b\w*(password|passwd|secret|token|api_key)\w*[ \t]*[:=][ \t]*["''][^"''\s\$\{\}]{8,}["'']'
    $textExt = @('.py', '.ps1', '.txt', '.md', '.json', '.xml', '.example', '.ini', '.cfg', '.yaml', '.yml', '.template', '.sh', '.env', '')
    foreach ($f in Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Where-Object { $_.Extension -in $textExt -and $_.Length -lt 5MB }) {
        $t = [IO.File]::ReadAllText($f.FullName)
        $patterns = @($anyPatterns)
        if ($f.Extension -in @('.py', '.ps1', '.sh')) { $patterns += $codePattern } else { $patterns += $configPattern }
        foreach ($p in $patterns) {
            # Valores ficticios declarados (p. ej. TestingConfig.JWT_SECRET_KEY = "test-secret") no cuentan.
            $m = @([regex]::Matches($t, $p) | Where-Object { $_.Value -notmatch '(?i)(test|example|dummy|fake|ficticio)' }) | Select-Object -First 1
            if ($m) { "$($f.FullName.Substring($Root.TrimEnd('\').Length + 1)): '$($m.Value.Substring(0, [Math]::Min(12, $m.Value.Length)))...'" }
        }
    }
}

# --- SQL Server (sqlcmd con autenticacion de Windows: ninguna contrasena en argumentos) ---
function Invoke-SigosSqlcmd([string]$Server, [string]$Query, [int]$TimeoutSec = 15) {
    $out = & sqlcmd.exe -S $Server -E -C -b -l $TimeoutSec -h -1 -W -Q "SET NOCOUNT ON; $Query" 2>&1
    return @{ Code = $LASTEXITCODE; Out = (($out | Out-String).Trim()) }
}

function Test-SigosSqlIdent([string]$Name) { return ($Name -match '^[A-Za-z_][A-Za-z0-9_]{0,127}$') }

function Restore-SigosSqlServerDb {
    <#
      RESTORE DATABASE ... WITH REPLACE sobre la MISMA base y el MISMO servidor (los usuarios conservan el SID de
      sus logins). Verifica el archivo antes; cierra conexiones (SINGLE_USER) y siempre deja la base en MULTI_USER.
      DESTRUCTIVO: sustituye el contenido actual. Lo llaman restore-database.ps1 (con confirmacion) y las pruebas.
    #>
    param([string]$Server, [string]$Database, [string]$BackupFile)
    if (-not (Test-SigosSqlIdent $Database)) { return @{ Code = 1; Out = "Nombre de base invalido: $Database" } }
    $f = $BackupFile.Replace("'", "''")
    $v = Invoke-SigosSqlcmd $Server "RESTORE VERIFYONLY FROM DISK = N'$f' WITH CHECKSUM;" 60
    if ($v.Code -ne 0) { return @{ Code = $v.Code; Out = "El respaldo no supera RESTORE VERIFYONLY: $($v.Out)" } }
    $r = Invoke-SigosSqlcmd $Server ("USE master; IF DB_ID(N'$Database') IS NOT NULL ALTER DATABASE [$Database] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; " +
        "RESTORE DATABASE [$Database] FROM DISK = N'$f' WITH REPLACE, CHECKSUM;") 300
    $m = Invoke-SigosSqlcmd $Server "USE master; IF DB_ID(N'$Database') IS NOT NULL ALTER DATABASE [$Database] SET MULTI_USER;"
    if ($r.Code -ne 0) { return @{ Code = $r.Code; Out = $r.Out } }
    if ($m.Code -ne 0) { return @{ Code = $m.Code; Out = "Restaurada, pero no se pudo volver a MULTI_USER: $($m.Out)" } }
    return @{ Code = 0; Out = $r.Out }
}

function Test-SigosSqliteFile([string]$Path) {
    # Cabecera "SQLite format 3\0" (16 bytes)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $fs = [IO.File]::OpenRead($Path)
    try { $b = New-Object byte[] 16; [void]$fs.Read($b, 0, 16) } finally { $fs.Dispose() }
    return ([Text.Encoding]::ASCII.GetString($b, 0, 15) -eq 'SQLite format 3' -and $b[15] -eq 0)
}

# --- Redaccion de secretos -----------------------------------------------------
$script:SigosSecretKeyPattern = '(?i)(PASS|PWD|SECRET|TOKEN|KEY|_URL$|^DB_URL)'

function Get-SigosSecretValues {
    # Valores secretos de sigos.env / admin.env, para eliminarlos literalmente de cualquier texto recopilado.
    $values = New-Object System.Collections.Generic.List[string]
    foreach ($f in @($SigosPaths.EnvFile, $SigosPaths.AdminEnv)) {
        try {
            $m = Read-SigosEnvFile $f
            foreach ($k in $m.Keys) {
                $v = [string]$m[$k]
                if ($k -match $SigosSecretKeyPattern -and $v.Length -ge 6) { $values.Add($v) }
            }
        } catch { }
    }
    return ,$values.ToArray()
}

function Protect-SigosText([string]$Text, [string[]]$SecretValues = @()) {
    <# Oculta secretos: valores conocidos, user:pass@ en URLs, Bearer, y pares clave=valor con nombres sensibles. #>
    if (-not $Text) { return $Text }
    foreach ($s in ($SecretValues | Sort-Object Length -Descending)) { if ($s) { $Text = $Text.Replace($s, '***') } }
    $Text = [regex]::Replace($Text, '(?i)(://[^:/@\s]+:)[^@\s]+@', '$1***@')
    $Text = [regex]::Replace($Text, '(?i)(Bearer\s+)[A-Za-z0-9\-\._~\+/]+=*', '$1***')
    $Text = [regex]::Replace($Text, '(?i)\b([A-Z0-9_]*(PASSWORD|PASSWD|PASS|PWD|SECRET|TOKEN|API_KEY|SECRET_KEY)[A-Z0-9_]*)(\s*[=:]\s*"?)(\{(?:[^}]|\}\})*\}|[^\s;&",}]+)', '$1$3***')
    return $Text
}

function Get-SigosHeartbeatAge {
    $hb = Join-Path $SigosPaths.RunDir 'worker.heartbeat'
    if (-not (Test-Path $hb)) { return $null }
    return [int]((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
}

# --- Secretos y archivos de entorno -----------------------------------------
function New-SigosSecret([int]$Bytes = 32) {
    # Aleatorio criptografico, base64url. Sufijo que garantiza la complejidad que exige SQL Server.
    $buf = New-Object byte[] $Bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buf) } finally { $rng.Dispose() }
    $b64 = [Convert]::ToBase64String($buf).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    return "${b64}Aa1-"
}

function Read-SigosEnvFile([string]$Path) {
    $map = [ordered]@{}
    if (Test-Path $Path) {
        foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
            if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
            $k, $v = $line -split '=', 2
            $map[$k.Trim()] = $v
        }
    }
    return $map
}

function Write-SigosEnvFile([string]$Path, $Map, [string]$Header) {
    $lines = New-Object System.Collections.Generic.List[string]
    if ($Header) { $lines.Add($Header) }
    foreach ($k in $Map.Keys) { $lines.Add("$k=$($Map[$k])") }
    # UTF-8 sin BOM: python-dotenv no espera BOM.
    [IO.File]::WriteAllLines($Path, $lines, (New-Object Text.UTF8Encoding($false)))
}

# --- ACL ---------------------------------------------------------------------
function Set-SigosAcl {
    <#
      Reemplaza la ACL de $Path (sin herencia): Administradores y SYSTEM control total,
      y las identidades de $Read / $Modify con esos derechos.
    #>
    param([string]$Path, [string[]]$Read = @(), [string[]]$Modify = @())
    $isDir = (Get-Item -LiteralPath $Path).PSIsContainer
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    if (-not $isDir) { $acl = New-Object System.Security.AccessControl.FileSecurity }
    $acl.SetAccessRuleProtection($true, $false)
    $inherit = [System.Security.AccessControl.InheritanceFlags]::None
    if ($isDir) { $inherit = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit' }
    $prop = [System.Security.AccessControl.PropagationFlags]::None
    $allow = [System.Security.AccessControl.AccessControlType]::Allow
    $add = {
        param($who, $rights)
        $sidOrName = $who
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sidOrName, $rights, $inherit, $prop, $allow)
        $acl.AddAccessRule($rule)
    }
    # S-1-5-32-544 = Administradores, S-1-5-18 = SYSTEM (independiente del idioma de Windows)
    & $add (New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')) 'FullControl'
    & $add (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')) 'FullControl'
    foreach ($r in $Read)   { & $add (New-Object Security.Principal.NTAccount($r)) 'ReadAndExecute' }
    foreach ($m in $Modify) { & $add (New-Object Security.Principal.NTAccount($m)) 'Modify' }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

# --- Procesos ----------------------------------------------------------------
function Invoke-SigosProcess {
    <#
      Ejecuta un proceso con variables de entorno propias (los secretos nunca van en argumentos).
      Devuelve el codigo de salida; la salida se muestra y se agrega a $LogFile.
    #>
    param([string]$FilePath, [string[]]$Arguments, [hashtable]$Environment = @{}, [string]$WorkingDirectory, [string]$LogFile)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = ($Arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }
    foreach ($k in $Environment.Keys) { $psi.EnvironmentVariables[$k] = [string]$Environment[$k] }
    $p = [System.Diagnostics.Process]::Start($psi)
    $errTask = $p.StandardError.ReadToEndAsync()
    $out = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()
    $err = $errTask.Result
    $text = ($out + $err).TrimEnd()
    if ($text) {
        $text -split "`r?`n" | ForEach-Object { Write-SigosInfo $_ }
        if ($LogFile) { Add-Content -LiteralPath $LogFile -Value $text -Encoding UTF8 }
    }
    return $p.ExitCode
}

function Invoke-SigosWinSW([string]$Service, [string]$Command) {
    $exe = Join-Path $SigosPaths.BinDir "$Service.exe"
    if (-not (Test-Path $exe)) { return 1 }
    & $exe $Command | ForEach-Object { Write-SigosInfo $_ }
    return $LASTEXITCODE
}
