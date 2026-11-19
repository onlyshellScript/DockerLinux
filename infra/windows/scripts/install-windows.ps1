#Requires -Version 5.1
<#
.SYNOPSIS
  Instala (o reinstala/actualiza) SIGOS como servicios nativos de Windows: SIGOS-API y SIGOS-Worker.

.DESCRIPTION
  Idempotente: si ya existe una instalacion, conserva sigos.env, admin.env, los datos y la base de datos;
  solo actualiza el codigo, el entorno virtual, los servicios y aplica migraciones pendientes (no destructivas).

  Pasos: requisitos -> codigo -> venv -> directorios -> configuracion -> servicios (WinSW, cuentas virtuales)
  -> permisos -> base de datos y migraciones -> arranque -> comprobacion de health.

.PARAMETER DbEngine
  SqlServer (produccion, recomendado) o SQLite (demostracion / un solo equipo).

.PARAMETER SqlAdminAuth
  Como se conecta el instalador a SQL Server para crear la base y los logins:
  Windows (usuario actual, sin contrasena) o Sql (pide credenciales con Get-Credential).
  Esas credenciales solo se usan durante la instalacion y nunca se guardan.

.EXAMPLE
  .\install-windows.ps1 -DbEngine SqlServer -SqlHost localhost -SqlPort 1433 -SqlServiceName 'MSSQL$SQLEXPRESS'

.EXAMPLE
  .\install-windows.ps1 -DbEngine SQLite
#>
[CmdletBinding()]
param(
    [ValidateSet('SqlServer', 'SQLite')][string]$DbEngine,
    [string]$SqlHost,
    [int]$SqlPort,
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]{0,63}$')][string]$DbName,
    [ValidateSet('Windows', 'Sql')][string]$SqlAdminAuth = 'Windows',
    [string]$SqlServiceName,
    [string]$PythonExe,
    [string]$ListenAddress,
    [ValidateRange(1, 65535)][int]$Port,
    [ValidateRange(1, 64)][int]$Threads,
    [string]$WinSWPath,
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]{0,63}$')][string]$DbAppUser,
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]{0,63}$')][string]$DbMigratorUser,
    [switch]$UseExistingDatabase,    # primera instalacion sobre una base que ya existe en el servidor
    [switch]$ReuseExistingLogins,    # primera instalacion con logins que ya existen (se les CAMBIA la contrasena)
    [switch]$OpenFirewall,
    [switch]$SkipStart
)

. "$PSScriptRoot\common.ps1"
Assert-SigosAdmin

# Valores previos (reinstalacion/actualizacion) y valores por defecto; los parametros explicitos ganan.
$prev = $null
if (Test-Path $SigosPaths.InstallCfg) { $prev = Get-Content $SigosPaths.InstallCfg -Raw | ConvertFrom-Json }
function Pick($explicit, $prevName, $default) {
    if ($explicit) { return $explicit }
    if ($prev -and ($prev.PSObject.Properties.Name -contains $prevName) -and $prev.$prevName) { return $prev.$prevName }
    return $default
}
$DbEngine       = Pick $DbEngine 'DbEngine' 'SqlServer'
$SqlHost        = Pick $SqlHost 'SqlHost' 'localhost'
$SqlPort        = [int](Pick $SqlPort 'SqlPort' 1433)
$DbName         = Pick $DbName 'DbName' 'sigos'
$SqlServiceName = Pick $SqlServiceName 'SqlServiceName' ''
$ListenAddress  = Pick $ListenAddress 'ListenAddress' '127.0.0.1'
$Port           = [int](Pick $Port 'Port' 5000)
$Threads        = [int](Pick $Threads 'Threads' 8)
$DbAppUser      = Pick $DbAppUser 'DbAppUser' 'sigos_app'
$DbMigratorUser = Pick $DbMigratorUser 'DbMigratorUser' 'sigos_migrator'
if ($DbAppUser -eq $DbMigratorUser) { Stop-Sigos $EXIT_USAGE '-DbAppUser y -DbMigratorUser deben ser distintos.' }

$logFile = Start-SigosScriptLog 'install'
try {
Write-SigosInfo "Registro de la instalacion: $logFile"
$sourceVersion = Get-SigosSourceVersion
if (-not $sourceVersion) { Stop-Sigos $EXIT_PREREQ "No se encontro services\api\VERSION en $SigosRepoRoot." }
Write-SigosInfo "Version a instalar: $sourceVersion"
$pkg = Test-SigosPackage
if ($pkg.IsPackage) {
    if (-not $pkg.Ok) {
        $pkg.Problems | Select-Object -First 20 | ForEach-Object { Write-SigosInfo $_ }
        Stop-Sigos $EXIT_PREREQ "El paquete esta incompleto o alterado ($($pkg.Problems.Count) problema(s)). Vuelve a descargarlo y verifica su .sha256."
    }
    Write-SigosOk "Integridad del paquete $($pkg.Version): $($pkg.Files) archivos verificados (SHA-256)"
}

# --- 1. Requisitos -----------------------------------------------------------
Write-SigosStep 'Comprobando requisitos'
$os = Get-CimInstance Win32_OperatingSystem
Write-SigosInfo "Sistema: $($os.Caption) $($os.Version) ($env:PROCESSOR_ARCHITECTURE)"
if ([Environment]::Is64BitOperatingSystem -eq $false) { Stop-Sigos $EXIT_PREREQ 'Se requiere Windows de 64 bits.' }

if (-not $PythonExe) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) { $PythonExe = (& py.exe -3.12 -c "import sys; print(sys.executable)" 2>$null) }
}
if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Stop-Sigos $EXIT_PREREQ 'No se encontro Python 3.12. Instalalo "para todos los usuarios" (python.org) o indica -PythonExe.'
}
$pyInfo = (& $PythonExe -c "import sys, json; print(json.dumps({'v': '%d.%d.%d' % sys.version_info[:3], 'base': sys.base_prefix, 'bits': 64 if sys.maxsize > 2**32 else 32}))") | ConvertFrom-Json
if (-not $pyInfo.v.StartsWith('3.12.')) { Stop-Sigos $EXIT_PREREQ "Se requiere Python 3.12.x (encontrado $($pyInfo.v) en $PythonExe)." }
if ($pyInfo.bits -ne 64) { Stop-Sigos $EXIT_PREREQ 'Se requiere Python de 64 bits.' }
$profilesDir = [Environment]::ExpandEnvironmentVariables((Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList').ProfilesDirectory)
if ($pyInfo.base.StartsWith($profilesDir, [StringComparison]::OrdinalIgnoreCase)) {
    Stop-Sigos $EXIT_PREREQ ("Python esta instalado en un perfil de usuario ($($pyInfo.base)); las cuentas de servicio no pueden leerlo. " +
        'Reinstala Python 3.12 marcando "Install for all users" (queda en C:\Program Files\Python312) o indica -PythonExe.')
}
Write-SigosOk "Python $($pyInfo.v) en $($pyInfo.base)"

if ($DbEngine -eq 'SqlServer') {
    if (-not (Get-OdbcDriver -Name 'ODBC Driver 18 for SQL Server' -Platform '64-bit' -ErrorAction SilentlyContinue)) {
        Stop-Sigos $EXIT_PREREQ 'Falta "Microsoft ODBC Driver 18 for SQL Server" (64-bit). Instalalo desde https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server'
    }
    Write-SigosOk 'ODBC Driver 18 for SQL Server'
    $tcp = New-Object Net.Sockets.TcpClient
    try {
        $ok = $tcp.ConnectAsync($SqlHost, $SqlPort).Wait(5000)
    } catch { $ok = $false } finally { $tcp.Dispose() }
    if (-not $ok) {
        Stop-Sigos $EXIT_DB ("No hay conexion TCP con SQL Server en ${SqlHost}:$SqlPort. " +
            'Habilita TCP/IP y un puerto fijo en SQL Server Configuration Manager y reinicia el servicio de SQL Server.')
    }
    Write-SigosOk "SQL Server accesible en ${SqlHost}:$SqlPort"
    if ($SqlServiceName -and -not (Get-SigosService $SqlServiceName)) {
        Stop-Sigos $EXIT_USAGE "No existe el servicio '$SqlServiceName' indicado en -SqlServiceName."
    }
}

$lock = Get-Content (Join-Path $SigosWinRoot 'services\winsw.lock.json') -Raw | ConvertFrom-Json

# --- 2. Detener servicios existentes (reinstalacion) --------------------------
$reinstall = Test-SigosInstalled
if ($reinstall) {
    Write-SigosStep 'Instalacion existente detectada: se detienen los servicios (los datos se conservan)'
    foreach ($s in ($SigosServices[($SigosServices.Count - 1)..0])) {
        $svc = Get-SigosService $s
        if ($svc -and $svc.Status -ne 'Stopped') {
            Stop-Service -Name $s -Force
            if (-not (Wait-SigosServiceStatus $s 'Stopped' 60)) { Stop-Sigos $EXIT_SERVICE "No se pudo detener $s." }
        }
    }
}

# --- 3. Codigo de la aplicacion ----------------------------------------------
Write-SigosStep "Copiando la aplicacion a $($SigosPaths.AppDir)"
New-Item -ItemType Directory -Force -Path $SigosPaths.InstallDir, $SigosPaths.BinDir | Out-Null
$src = Join-Path $SigosRepoRoot 'services\api'
& robocopy.exe $src $SigosPaths.AppDir /MIR /R:2 /W:2 /NFL /NDL /NJH /NJS /NP `
    /XD .venv venv tests uploads __pycache__ .pytest_cache versions_backup instance `
    /XF .env .env.* *.bak *.pyc *.log salida_*.txt *.db *.sqlite* | Out-Null
if ($LASTEXITCODE -ge 8) { Stop-Sigos $EXIT_PREREQ "robocopy fallo (codigo $LASTEXITCODE)." }
Write-SigosOk 'Codigo copiado (sin .env, tests, uploads ni cachés)'

# --- 4. Entorno virtual --------------------------------------------------------
Write-SigosStep 'Preparando el entorno virtual'
$venvPy = Join-Path $SigosPaths.Venv 'Scripts\python.exe'
$cfgFile = Join-Path $SigosPaths.Venv 'pyvenv.cfg'
$recreate = -not (Test-Path $venvPy)
if (-not $recreate -and (Test-Path $cfgFile)) {
    $venvHome = (Get-Content $cfgFile | Where-Object { $_ -match '^home\s*=' }) -replace '^home\s*=\s*', ''
    if ($venvHome.TrimEnd('\') -ne $pyInfo.base.TrimEnd('\')) { $recreate = $true }
}
if ($recreate) {
    if (Test-Path $SigosPaths.Venv) { Remove-Item -LiteralPath $SigosPaths.Venv -Recurse -Force }
    & $PythonExe -m venv $SigosPaths.Venv
    if ($LASTEXITCODE -ne 0) { Stop-Sigos $EXIT_PREREQ 'No se pudo crear el entorno virtual.' }
}
$wheelDir = Join-Path $SigosRepoRoot 'wheels'
$lockReq = Join-Path $SigosWinRoot 'requirements-windows.lock.txt'
if (Test-Path $wheelDir) {
    # Paquete de distribucion: dependencias congeladas y sin acceso a Internet (reproducible).
    $req = $(if (Test-Path $lockReq) { $lockReq } else { Join-Path $SigosWinRoot 'requirements-windows.txt' })
    Write-SigosInfo "Dependencias desde $wheelDir (sin conexion)"
    & $venvPy -m pip install --disable-pip-version-check --no-input -q --no-index --find-links $wheelDir -r $req
} else {
    & $venvPy -m pip install --disable-pip-version-check --no-input -q --upgrade pip
    & $venvPy -m pip install --disable-pip-version-check --no-input -q -r (Join-Path $SigosWinRoot 'requirements-windows.txt')
}
if ($LASTEXITCODE -ne 0) { Stop-Sigos $EXIT_PREREQ 'Fallo la instalacion de dependencias (pip).' }
& $venvPy -m compileall -q $SigosPaths.AppDir | Out-Null
Write-SigosOk 'Dependencias instaladas (incluye waitress)'

# --- 5. Directorios de datos ---------------------------------------------------
Write-SigosStep "Preparando $($SigosPaths.DataRoot)"
foreach ($d in @($SigosPaths.ConfigDir, $SigosPaths.DataDir, $SigosPaths.UploadDir, $SigosPaths.RunDir, $SigosPaths.BackupDir,
                 (Join-Path $SigosPaths.LogDir 'api'), (Join-Path $SigosPaths.LogDir 'worker'),
                 $SigosPaths.InstallLog, $SigosPaths.SystemLog)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

# --- 6. Configuracion (sin sobrescribir la existente) --------------------------
Write-SigosStep 'Configuracion'
$envMap = Read-SigosEnvFile $SigosPaths.EnvFile
$adminMap = Read-SigosEnvFile $SigosPaths.AdminEnv
$firstInstall = -not $envMap.Contains('JWT_SECRET_KEY')

# Primera instalacion contra SQL Server: no adoptar en silencio una base o unos logins que ya existen.
# prepare_db.py migraria esa base y haria ALTER LOGIN ... PASSWORD, rompiendo cualquier otra aplicacion que los use.
if ($DbEngine -eq 'SqlServer' -and $firstInstall) {
    if ($SqlAdminAuth -eq 'Windows' -and (Get-Command sqlcmd.exe -ErrorAction SilentlyContinue)) {
        $srv = "$SqlHost,$SqlPort"
        $q = Invoke-SigosSqlcmd $srv ("SELECT CAST(ISNULL(DB_ID(N'$DbName'),0) AS varchar) + '|' + CAST(ISNULL(SUSER_ID(N'$DbAppUser'),0) AS varchar)" +
            " + '|' + CAST(ISNULL(SUSER_ID(N'$DbMigratorUser'),0) AS varchar)")
        if ($q.Code -ne 0) { Stop-Sigos $EXIT_DB "No se pudo consultar SQL Server con la cuenta de Windows actual: $($q.Out)" }
        $dbId, $appId, $migId = $q.Out -split '\|'
        if ([int]$dbId -ne 0 -and -not $UseExistingDatabase) {
            Stop-Sigos $EXIT_DB ("La base [$DbName] ya existe en $srv y esta es una instalacion nueva. Usa otro -DbName o, si es la base " +
                'de SIGOS que quieres adoptar (se le aplicaran las migraciones pendientes), -UseExistingDatabase.')
        }
        $existing = @()
        if ([int]$appId -ne 0) { $existing += $DbAppUser }
        if ([int]$migId -ne 0) { $existing += $DbMigratorUser }
        if ($existing -and -not $ReuseExistingLogins) {
            Stop-Sigos $EXIT_DB ("Ya existen los logins $($existing -join ', ') en $srv. El instalador les cambiaria la contrasena y cualquier " +
                'otra aplicacion que los use dejaria de conectar. Usa -DbAppUser/-DbMigratorUser con otros nombres o -ReuseExistingLogins.')
        }
        Write-SigosOk 'Base y logins: sin conflictos con objetos existentes'
    } else {
        Write-SigosWarn 'No se puede comprobar si la base o los logins ya existen (requiere -SqlAdminAuth Windows y sqlcmd).'
    }
}
$fwd = $SigosPaths.DataRoot.Replace('\', '/')
$defaults = [ordered]@{
    SIGOS_ENV                    = 'production'
    JWT_SECRET_KEY               = (New-SigosSecret 48)
    LOG_LEVEL                    = 'INFO'
    LOG_FORMAT                   = 'json'
    UPLOAD_DIR                   = $SigosPaths.UploadDir
    EVIDENCE_UPLOAD_DIR          = (Join-Path $SigosPaths.UploadDir 'evidences')
    PROXY_FIX_HOPS               = '0'
    NOTIFICATION_WORKER_INTERVAL = '30'
    SMTP_HOST = ''; SMTP_PORT = '587'; SMTP_USER = ''; SMTP_PASS = ''; SMTP_FROM = ''
    WHATSAPP_API_URL = ''; WHATSAPP_API_TOKEN = ''; WHATSAPP_PHONE_NUMBER_ID = ''
}
if ($DbEngine -eq 'SqlServer') {
    $defaults['DB_HOST'] = $SqlHost
    $defaults['DB_PORT'] = "$SqlPort"
    $defaults['DB_NAME'] = $DbName
    $defaults['DB_APP_USER'] = $DbAppUser
    $defaults['DB_APP_PASSWORD'] = (New-SigosSecret 24)
    if (-not $adminMap.Contains('DB_MIGRATOR_USER'))     { $adminMap['DB_MIGRATOR_USER'] = $DbMigratorUser }
    if (-not $adminMap.Contains('DB_MIGRATOR_PASSWORD')) { $adminMap['DB_MIGRATOR_PASSWORD'] = (New-SigosSecret 24) }
} else {
    $defaults['DB_URL'] = "sqlite:///$fwd/data/$DbName.db"
}
$added = @()
foreach ($k in $defaults.Keys) { if (-not $envMap.Contains($k)) { $envMap[$k] = $defaults[$k]; $added += $k } }
Write-SigosEnvFile $SigosPaths.EnvFile $envMap '# SIGOS - configuracion de los servicios Windows. Generado por install-windows.ps1; editable. NO compartir.'
if ($adminMap.Count -gt 0) {
    Write-SigosEnvFile $SigosPaths.AdminEnv $adminMap '# Credenciales solo para migraciones (lectura: Administradores). NO compartir.'
}
if ($added.Count -gt 0) { Write-SigosOk ("Claves nuevas: " + ($added -join ', ')) } else { Write-SigosOk 'sigos.env existente conservado' }
if ($envMap.Contains('DB_URL') -and $DbEngine -eq 'SqlServer' -and $envMap['DB_URL'] -like 'sqlite*') {
    Write-SigosWarn 'sigos.env define DB_URL de SQLite y se pidio SqlServer: se respeta DB_URL. Editalo si quieres migrar de motor.'
}

$installCfg = [ordered]@{
    DbEngine = $DbEngine; SqlHost = $SqlHost; SqlPort = $SqlPort; DbName = $DbName; SqlServiceName = $SqlServiceName
    DbAppUser = $DbAppUser; DbMigratorUser = $DbMigratorUser
    ListenAddress = $ListenAddress; Port = $Port; Threads = $Threads; PythonExe = $PythonExe
    WinSW = $lock.version; InstalledAt = (Get-Date).ToString('s'); Source = $SigosRepoRoot; Version = $sourceVersion
}
$installCfg | ConvertTo-Json | Set-Content -LiteralPath $SigosPaths.InstallCfg -Encoding UTF8

# --- 7. Servicios (WinSW) ------------------------------------------------------
Write-SigosStep 'Registrando servicios'
$winswCache = Join-Path $SigosPaths.BinDir $lock.file
$bundled = Join-Path $SigosWinRoot "bin\$($lock.file)"
if (-not $WinSWPath -and (Test-Path $bundled)) { $WinSWPath = $bundled }   # incluido en el paquete de distribucion
if ($WinSWPath) { Copy-Item -LiteralPath $WinSWPath -Destination $winswCache -Force }
if (-not (Test-Path $winswCache)) {
    Write-SigosInfo "Descargando WinSW $($lock.version)"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $lock.url -OutFile $winswCache -UseBasicParsing
}
$hash = (Get-FileHash -LiteralPath $winswCache -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $lock.sha256) {
    Remove-Item -LiteralPath $winswCache -Force
    Stop-Sigos $EXIT_PREREQ "SHA-256 de WinSW no coincide (esperado $($lock.sha256), obtenido $hash). Archivo descartado."
}
Write-SigosOk "WinSW $($lock.version) verificado (SHA-256)"

$tokens = @{
    '{{VENV}}' = $SigosPaths.Venv; '{{APP_DIR}}' = $SigosPaths.AppDir; '{{ENV_FILE}}' = $SigosPaths.EnvFile
    '{{LOG_DIR}}' = $SigosPaths.LogDir; '{{RUN_DIR}}' = $SigosPaths.RunDir
    '{{API_LISTEN}}' = "${ListenAddress}:$Port"; '{{API_THREADS}}' = "$Threads"
    '{{DEPENDS}}' = $(if ($SqlServiceName -and $DbEngine -eq 'SqlServer') { "  <depend>$([Security.SecurityElement]::Escape($SqlServiceName))</depend>" } else { '' })
}
$templates = @{ 'SIGOS-API' = 'sigos-api.xml.template'; 'SIGOS-Worker' = 'sigos-worker.xml.template' }

foreach ($s in $SigosServices) {
    $xml = Get-Content (Join-Path $SigosWinRoot "services\$($templates[$s])") -Raw
    foreach ($t in $tokens.Keys) { $xml = $xml.Replace($t, $tokens[$t]) }
    $null = [xml]$xml   # valida que el XML resultante sea correcto
    $exe = Join-Path $SigosPaths.BinDir "$s.exe"
    $xmlPath = Join-Path $SigosPaths.BinDir "$s.xml"

    if (Get-SigosService $s) {
        # Reinstalacion: se elimina el registro anterior para aplicar el XML nuevo (sin duplicados).
        Invoke-SigosWinSW $s 'uninstall' | Out-Null
        $deadline = (Get-Date).AddSeconds(30)
        while ((Get-SigosService $s) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
        if (Get-SigosService $s) { Stop-Sigos $EXIT_SERVICE "$s quedo marcado para eliminacion. Cierra services.msc / el Visor de eventos y vuelve a ejecutar." }
    }
    Copy-Item -LiteralPath $winswCache -Destination $exe -Force
    [IO.File]::WriteAllText($xmlPath, $xml, (New-Object Text.UTF8Encoding($false)))
    if ((Invoke-SigosWinSW $s 'install') -ne 0 -or -not (Get-SigosService $s)) { Stop-Sigos $EXIT_SERVICE "WinSW no pudo registrar $s." }
    # Cuenta virtual con minimo privilegio (sin contrasena, no SYSTEM).
    & sc.exe config $s obj= "NT SERVICE\$s" | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-Sigos $EXIT_SERVICE "No se pudo asignar la cuenta NT SERVICE\$s." }
    Write-SigosOk "$s registrado (cuenta NT SERVICE\$s, inicio automatico retrasado)"
}

# --- 8. Permisos ---------------------------------------------------------------
Write-SigosStep 'Aplicando permisos'
$svcAccounts = $SigosServices | ForEach-Object { "NT SERVICE\$_" }
Set-SigosAcl -Path $SigosPaths.InstallDir -Read $svcAccounts
Set-SigosAcl -Path $SigosPaths.DataRoot -Read $svcAccounts
Set-SigosAcl -Path $SigosPaths.ConfigDir -Read $svcAccounts
Set-SigosAcl -Path $SigosPaths.EnvFile -Read $svcAccounts
if (Test-Path $SigosPaths.AdminEnv) { Set-SigosAcl -Path $SigosPaths.AdminEnv }
Set-SigosAcl -Path $SigosPaths.DataDir -Modify $svcAccounts
Set-SigosAcl -Path $SigosPaths.LogDir -Modify $svcAccounts
# Registros de instalacion y diagnosticos: solo administradores (despues de LogDir, que propaga a sus hijos).
Set-SigosAcl -Path $SigosPaths.InstallLog
Set-SigosAcl -Path $SigosPaths.SystemLog
Set-SigosAcl -Path $SigosPaths.RunDir -Modify 'NT SERVICE\SIGOS-Worker'
Set-SigosAcl -Path $SigosPaths.BackupDir
Write-SigosOk 'config: lectura servicios / admin.env: solo administradores / data, logs\{api,worker}: modificacion servicios / logs\{installer,system}, backups: solo administradores'

# --- 9. Base de datos ---------------------------------------------------------
Write-SigosStep "Base de datos ($DbEngine) y migraciones"
$dbEnv = @{
    SIGOS_ENV = 'production'; SIGOS_ENV_FILE = $SigosPaths.EnvFile; PYTHONDONTWRITEBYTECODE = '1'
    DB_WAIT_RETRIES = '5'; DB_WAIT_DELAY = '2'
}
if ($DbEngine -eq 'SqlServer' -and -not ($envMap.Contains('DB_URL') -and $envMap['DB_URL'] -like 'sqlite*')) {
    $drv = 'ODBC+Driver+18+for+SQL+Server'
    if ($SqlAdminAuth -eq 'Windows') {
        $dbEnv['DB_ADMIN_URL'] = "mssql+pyodbc://@${SqlHost}:$SqlPort/master?driver=$drv&TrustServerCertificate=yes&trusted_connection=yes"
    } else {
        $cred = Get-Credential -Message 'Credenciales de administrador de SQL Server (solo para crear la base y los logins; no se guardan)'
        if (-not $cred) { Stop-Sigos $EXIT_USAGE 'Instalacion cancelada: no se dieron credenciales.' }
        $u = [Uri]::EscapeDataString($cred.UserName)
        $p = [Uri]::EscapeDataString($cred.GetNetworkCredential().Password)
        $dbEnv['DB_ADMIN_URL'] = "mssql+pyodbc://${u}:$p@${SqlHost}:$SqlPort/master?driver=$drv&TrustServerCertificate=yes"
    }
    $dbEnv['DB_MIGRATOR_USER'] = $adminMap['DB_MIGRATOR_USER']
    $dbEnv['DB_MIGRATOR_PASSWORD'] = $adminMap['DB_MIGRATOR_PASSWORD']
}
$code = Invoke-SigosProcess -FilePath $venvPy -Arguments @((Join-Path $SigosPaths.AppDir 'docker\prepare_db.py')) `
    -Environment $dbEnv -WorkingDirectory $SigosPaths.AppDir
$dbEnv.Clear()
if ($code -ne 0) { Stop-Sigos $EXIT_DB "La preparacion de la base de datos fallo (codigo $code). Los servicios quedan registrados pero detenidos." }
if ($DbEngine -eq 'SQLite') {
    # La base la creo el administrador: los servicios necesitan modificarla.
    Set-SigosAcl -Path $SigosPaths.DataDir -Modify $svcAccounts
}
Write-SigosOk 'Base de datos lista y migraciones aplicadas'

# Datos iniciales (roles y usuario admin). seed.py es idempotente: solo crea si no hay roles/usuarios.
$adminPwd = New-SigosSecret 12
$seedOut = Join-Path ([IO.Path]::GetTempPath()) ("sigos-seed-" + [guid]::NewGuid().ToString('N') + '.log')
$seedEnv = @{ SIGOS_ENV = 'production'; SIGOS_ENV_FILE = $SigosPaths.EnvFile; PYTHONDONTWRITEBYTECODE = '1'; ADMIN_PASSWORD = $adminPwd }
$code = Invoke-SigosProcess -FilePath $venvPy -Arguments @((Join-Path $SigosPaths.AppDir 'seed.py')) `
    -Environment $seedEnv -WorkingDirectory $SigosPaths.AppDir -LogFile $seedOut
$seedEnv.Clear()
$seedText = ''
if (Test-Path $seedOut) { $seedText = Get-Content -LiteralPath $seedOut -Raw; Remove-Item -LiteralPath $seedOut -Force }
if ($code -ne 0) { Stop-Sigos $EXIT_DB "seed.py fallo (codigo $code): no se pudieron crear los roles/usuario inicial." }
if ($seedText -match 'Usuario admin creado') {
    $initial = Join-Path $SigosPaths.ConfigDir 'initial-admin.txt'
    [IO.File]::WriteAllLines($initial, @(
        'SIGOS - credenciales iniciales (generadas por install-windows.ps1).',
        'usuario: admin', "contrasena: $adminPwd",
        'Se exige cambiarla en el primer acceso. BORRA este archivo despues de usarla.'), (New-Object Text.UTF8Encoding($false)))
    Set-SigosAcl -Path $initial
    Write-SigosOk "Usuario 'admin' creado. Contrasena inicial en $initial (solo administradores; borrala tras el primer acceso)"
} else {
    Write-SigosOk 'Roles y usuarios ya existentes: no se crea el usuario inicial'
}
$adminPwd = $null

# --- 10. Firewall (opcional) ---------------------------------------------------
if ($OpenFirewall) {
    if ($ListenAddress -eq '127.0.0.1') {
        Write-SigosWarn 'La API escucha solo en 127.0.0.1: no se abre el firewall.'
    } elseif (-not (Get-NetFirewallRule -Name 'SIGOS-API-In' -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -Name 'SIGOS-API-In' -DisplayName 'SIGOS API (TCP)' -Direction Inbound -Protocol TCP `
            -LocalPort $Port -Action Allow -Profile Domain, Private | Out-Null
        Write-SigosOk "Regla de firewall SIGOS-API-In (TCP $Port, perfiles Dominio y Privado)"
    }
}

# --- 11. Arranque y comprobacion ----------------------------------------------
if ($SkipStart) {
    Write-SigosWarn 'Instalacion terminada sin arrancar los servicios (-SkipStart).'
    exit $EXIT_OK
}
Write-SigosStep 'Arrancando servicios'
$startedAt = Get-Date
foreach ($s in $SigosServices) {
    Start-Service -Name $s
    if (-not (Wait-SigosServiceStatus $s 'Running' 60)) { Stop-Sigos $EXIT_SERVICE "$s no llego a Running. Revisa .\logs-services.ps1 -Service $($s.Split('-')[1].ToLower())" }
    Write-SigosOk "$s en ejecucion"
}
$health = Invoke-SigosHealth 90
if (-not $health) {
    Get-ChildItem (Join-Path $SigosPaths.LogDir 'api') -Filter *.err.log -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -Last 1 | ForEach-Object { Get-Content $_.FullName -Tail 30 }
    Stop-Sigos $EXIT_HEALTH "La API no respondio UP en $(Get-SigosHealthUrl)."
}
Write-SigosOk "Health UP: application=$($health.checks.application) database=$($health.checks.database) version=$($health.version)"
if ($health.version -and $health.version -ne $sourceVersion) {
    Stop-Sigos $EXIT_HEALTH "La API responde con la version $($health.version) pero se instalo ${sourceVersion}. Hay otro proceso en el puerto ${Port}?"
}

# El servicio en Running no basta: el bucle del worker debe tocar el heartbeat tras el arranque.
$hbTimeout = [Math]::Max(60, 2 * (Get-SigosWorkerInterval) + 30)
if (-not (Wait-SigosHeartbeat $startedAt $hbTimeout)) {
    Get-ChildItem (Join-Path $SigosPaths.LogDir 'worker') -Filter *.err.log -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -Last 1 | ForEach-Object { Get-Content $_.FullName -Tail 30 }
    Stop-Sigos $EXIT_HEALTH "SIGOS-Worker esta en Running pero no actualizo su heartbeat en $hbTimeout s. Revisa .\logs-services.ps1 -Service worker"
}
Write-SigosOk 'Worker activo (heartbeat actualizado tras el arranque)'

foreach ($svcLogDir in @('api', 'worker')) {
    $d = Join-Path $SigosPaths.LogDir $svcLogDir
    $fresh = Get-ChildItem -LiteralPath $d -Filter *.log -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $startedAt.AddSeconds(-5) }
    if (-not $fresh) { Stop-Sigos $EXIT_SERVICE "No se escribio ningun log en $d tras el arranque. Revisa los permisos de $($SigosPaths.LogDir)." }
}
Write-SigosOk 'Logs de servicio generandose en logs\api y logs\worker'
Write-Host ''
Write-Host "SIGOS instalado. API: http://${ListenAddress}:$Port  Config: $($SigosPaths.EnvFile)  Logs: $($SigosPaths.LogDir)" -ForegroundColor Green
exit $EXIT_OK

} finally {
    Stop-Transcript | Out-Null
}
