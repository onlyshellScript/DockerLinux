#Requires -Version 5.1
<#
.SYNOPSIS
  Prueba REAL contra SQL Server (sin administrador de Windows): aprovisionamiento, migraciones, minimo privilegio,
  cifrado, API (waitress) y worker sobre SQL Server, persistencia, reconexion tras cortar sesiones, indisponibilidad
  controlada, concurrencia del procesamiento de notificaciones y respaldo/restauracion.

.DESCRIPTION
  Requiere: ODBC Driver 18, sqlcmd y que la cuenta de Windows actual sea sysadmin de la instancia.
  AISLADA: crea una base y dos logins con sufijo aleatorio (sigos_wt_<id>, sigos_wt_app_<id>, sigos_wt_mig_<id>)
  y los ELIMINA al terminar. Nunca toca la base 'sigos' ni los logins sigos_app/sigos_migrator existentes.
  Usa los mismos comandos y variables que install-windows.ps1 y las plantillas WinSW.

.EXAMPLE
  .\infra\windows\tests\Test-SigosSqlServer.ps1 -PythonExe 'C:\Program Files\Python312\python.exe'
#>
[CmdletBinding()] param(
    [string]$PythonExe,
    [string]$SqlHost = 'localhost',
    [int]$SqlPort = 1433,
    [int]$Port = 5097,
    [string]$VenvPath,
    [switch]$KeepTemp
)
. (Join-Path $PSScriptRoot '..\scripts\common.ps1')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Off
$repo = $SigosRepoRoot
$app = Join-Path $repo 'services\api'
$probe = Join-Path $PSScriptRoot 'sql_probe.py'
$server = "$SqlHost,$SqlPort"
$rid = [guid]::NewGuid().ToString('N').Substring(0, 6)
$db = "sigos_wt_$rid"; $appUser = "sigos_wt_app_$rid"; $migUser = "sigos_wt_mig_$rid"
$tmp = Join-Path ([IO.Path]::GetTempPath()) "sigos-sql-$rid"
New-Item -ItemType Directory -Path $tmp, "$tmp\data\uploads", "$tmp\run" | Out-Null
# Copia de la app con las MISMAS exclusiones que install-windows.ps1 (sin .env): un services\api\.env de desarrollo
# no debe poder colarse en la configuracion de la prueba (config.py carga .env despues de SIGOS_ENV_FILE).
& robocopy.exe $app "$tmp\app" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD .venv venv tests uploads __pycache__ .pytest_cache versions_backup instance `
    /XF .env .env.* *.bak *.pyc *.log salida_*.txt *.db *.sqlite* | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy fallo ($LASTEXITCODE)" }
$app = "$tmp\app"
foreach ($v in 'DB_URL', 'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_APP_USER', 'DB_APP_PASSWORD', 'DB_ADMIN_URL', 'MSSQL_SA_PASSWORD') { Remove-Item "env:$v" -ErrorAction SilentlyContinue }
$results = [ordered]@{}
$notes = New-Object System.Collections.Generic.List[string]
$procs = New-Object System.Collections.Generic.List[object]
$created = $false
$backupFiles = @()

function Step($name, [scriptblock]$body) {
    try { & $body; $results[$name] = 'PASS'; Write-Host "[PASS] $name" -ForegroundColor Green }
    catch { $results[$name] = "FAIL: $($_.Exception.Message)"; Write-Host "[FAIL] $name -> $($_.Exception.Message)" -ForegroundColor Red }
}
function Sql([string]$q) {
    $r = Invoke-SigosSqlcmd $server $q 60
    if ($r.Code -ne 0) { throw "sqlcmd: $($r.Out)" }
    return ((($r.Out -split "`r?`n") | Where-Object { $_ -notmatch '^Changed database context|^Se cambi. el contexto' }) -join "`n").Trim()
}
function Py([string[]]$a, [hashtable]$extraEnv = @{}) {
    $old = @{}
    foreach ($k in $extraEnv.Keys) { $old[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, $extraEnv[$k]) }
    # PS 5.1: con ErrorActionPreference=Stop, cada linea de stderr de un proceso nativo (los INFO de Alembic) es terminante.
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = & $py @a 2>&1 | ForEach-Object { "$_" }; $code = $LASTEXITCODE }
    finally { $ErrorActionPreference = $eap; foreach ($k in $old.Keys) { [Environment]::SetEnvironmentVariable($k, $old[$k]) } }
    return @{ Code = $code; Out = (($out | Out-String).Trim()) }
}
function Probe([string[]]$a, [string]$envFile = $envFile) {
    $r = Py (@($probe, $app) + $a) @{ SIGOS_ENV_FILE = $envFile }
    if ($r.Code -ne 0) { throw "sql_probe $($a -join ' '): $($r.Out)" }
    return ($r.Out -split "`r?`n")[-1]
}
function Start-Svc([string]$name, [string[]]$a, [string]$envFile) {
    $env:SIGOS_ENV_FILE = $envFile
    $p = Start-Process -FilePath $py -ArgumentList $a -WorkingDirectory $app -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput "$tmp\$name.out.log" -RedirectStandardError "$tmp\$name.err.log"
    $procs.Add($p)
    return $p
}
function Get-Health([int]$p, [string]$path = '/api/v1/health') {
    try { $r = Invoke-WebRequest "http://127.0.0.1:$p$path" -TimeoutSec 5 -UseBasicParsing; return @{ Code = [int]$r.StatusCode; Body = ($r.Content | ConvertFrom-Json) } }
    catch {
        $resp = $null; try { $resp = $_.Exception.Response } catch { }
        if ($resp) { return @{ Code = [int]$resp.StatusCode; Body = $null } }
        return @{ Code = 0; Body = $null }
    }
}
function Wait-Health([int]$p, [int]$code, [int]$sec = 40, [string]$path = '/api/v1/health') {
    $deadline = (Get-Date).AddSeconds($sec)
    do { $h = Get-Health $p $path; if ($h.Code -eq $code) { return $h }; Start-Sleep -Milliseconds 700 } while ((Get-Date) -lt $deadline)
    throw "no se obtuvo HTTP $code en $path (ultimo: $($h.Code))"
}

try {
    Step '1. ODBC Driver 18, sqlcmd y permisos sysadmin (Windows)' {
        if (-not (Get-OdbcDriver -Name 'ODBC Driver 18 for SQL Server' -Platform '64-bit' -ErrorAction SilentlyContinue)) { throw 'falta ODBC Driver 18 (64-bit)' }
        if (-not (Get-Command sqlcmd.exe -ErrorAction SilentlyContinue)) { throw 'falta sqlcmd' }
        $info = Sql "SELECT CAST(SERVERPROPERTY('ProductVersion') AS varchar(30)) + '|' + CAST(SERVERPROPERTY('Edition') AS varchar(80)) + '|' + CAST(IS_SRVROLEMEMBER('sysadmin') AS varchar)"
        $v, $ed, $sa = $info -split '\|'
        if ($sa -ne '1') { throw 'la cuenta actual no es sysadmin' }
        $notes.Add("SQL Server $v ($ed)")
    }
    if ($VenvPath) { $py = Join-Path $VenvPath 'Scripts\python.exe' } else {
        Step '2. venv con requirements-windows.txt' {
            if (-not $PythonExe) { $PythonExe = (& py.exe -3.12 -c "import sys; print(sys.executable)") }
            & $PythonExe -m venv "$tmp\venv"; if ($LASTEXITCODE) { throw 'venv' }
            & "$tmp\venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r (Join-Path $SigosWinRoot 'requirements-windows.txt')
            if ($LASTEXITCODE) { throw 'pip install' }
        }
        $py = "$tmp\venv\Scripts\python.exe"
    }
    $env:SIGOS_ENV = 'production'; $env:PYTHONDONTWRITEBYTECODE = '1'; $env:PYTHONUNBUFFERED = '1'; $env:ENABLE_NOTIFICATION_WORKER = 'false'

    # Configuracion identica a la que genera install-windows.ps1
    $appPwd = New-SigosSecret 24; $migPwd = New-SigosSecret 24
    $base = [ordered]@{
        SIGOS_ENV = 'production'; JWT_SECRET_KEY = (New-SigosSecret 48); LOG_LEVEL = 'INFO'; LOG_FORMAT = 'json'
        UPLOAD_DIR = "$tmp\data\uploads"; PROXY_FIX_HOPS = '0'; NOTIFICATION_WORKER_INTERVAL = '2'
        DB_HOST = $SqlHost; DB_PORT = "$SqlPort"; DB_NAME = $db; DB_APP_USER = $appUser; DB_APP_PASSWORD = $appPwd
    }
    $envFile = "$tmp\sigos.env"; Write-SigosEnvFile $envFile $base ''
    $badEnv = "$tmp\sigos-down.env"; $b2 = [ordered]@{}; foreach ($k in $base.Keys) { $b2[$k] = $base[$k] }; $b2['DB_PORT'] = '1'; Write-SigosEnvFile $badEnv $b2 ''
    $prepEnv = @{
        SIGOS_ENV_FILE = $envFile; DB_WAIT_RETRIES = '5'; DB_WAIT_DELAY = '2'; DB_MIGRATOR_USER = $migUser; DB_MIGRATOR_PASSWORD = $migPwd
        DB_ADMIN_URL = "mssql+pyodbc://@${SqlHost}:$SqlPort/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&trusted_connection=yes"
    }

    Step '3. prepare_db.py: crea base, logins (migrador DDL / app DML) y aplica migraciones como migrador' {
        $script:created = $true
        $r = Py @((Join-Path $app 'docker\prepare_db.py')) $prepEnv
        if ($r.Code -ne 0) { throw "codigo $($r.Code): $(Protect-SigosText $r.Out @($appPwd, $migPwd))" }
        if ($r.Out -match [regex]::Escape($appPwd) -or $r.Out -match [regex]::Escape($migPwd)) { throw 'prepare_db imprime una contrasena' }
        $script:rev1 = Sql "SELECT version_num FROM [$db].dbo.alembic_version"
        $tables = [int](Sql "SELECT COUNT(*) FROM [$db].sys.tables")
        if ($tables -lt 20) { throw "solo $tables tablas" }
        $notes.Add("Migraciones: revision $rev1, $tables tablas")
    }
    Step '4. prepare_db.py idempotente: segunda ejecucion sin cambios de revision ni de datos' {
        $r = Py @((Join-Path $app 'docker\prepare_db.py')) $prepEnv
        if ($r.Code -ne 0) { throw "codigo $($r.Code)" }
        if ((Sql "SELECT version_num FROM [$db].dbo.alembic_version") -ne $rev1) { throw 'la revision cambio' }
    }
    Step '5. Minimo privilegio: la cuenta de la app no es owner/ddladmin y no puede crear tablas' {
        $roles = Sql "USE [$db]; SELECT CAST(IS_ROLEMEMBER('db_owner', N'$appUser') AS varchar) + '|' + CAST(IS_ROLEMEMBER('db_ddladmin', N'$appUser') AS varchar) + '|' + CAST(IS_SRVROLEMEMBER('sysadmin', N'$appUser') AS varchar) + '|' + CAST(IS_ROLEMEMBER('db_ddladmin', N'$migUser') AS varchar)"
        if ($roles -ne '0|0|0|1') { throw "roles owner|ddladmin|sysadmin|migrador-ddl = $roles" }
        Probe @('ddl-denied') | Out-Null
        Probe @('seed-user') | Out-Null   # la app SI puede escribir datos (DML)
    }
    Step '7. Certificado: con TrustServerCertificate=no se rechaza un certificado no confiable' {
        $r = Py @('-c', "import os,sys,pyodbc; from sqlalchemy.engine import make_url; sys.path.insert(0, r'$app'); from app.config import database_url; u = make_url(database_url()); cs = 'DRIVER={ODBC Driver 18 for SQL Server};SERVER=%s,%s;DATABASE=%s;UID=%s;PWD={%s};Encrypt=yes;TrustServerCertificate=no' % (u.host, u.port, u.database, u.username, u.password.replace('}','}}')); pyodbc.connect(cs, timeout=5); print('CONFIABLE')") @{ SIGOS_ENV_FILE = $envFile }
        if ($r.Code -eq 0) { $notes.Add('Certificado del servidor confiable: DB_TRUST_SERVER_CERTIFICATE=no es viable') }
        elseif ($r.Out -match 'certificate|certificado|SSL') { $notes.Add('Certificado autofirmado: con DB_TRUST_SERVER_CERTIFICATE=no la conexion se rechaza (esperado); produccion: certificado de una CA o TrustServerCertificate=yes en red de confianza') }
        else { throw "error inesperado: $(Protect-SigosText $r.Out @($appPwd))" }
    }
    Step '8. API (waitress, mismo comando que SIGOS-API) sobre SQL Server: health UP, database=UP y conexion cifrada' {
        $script:api = Start-Svc 'api' @('-m', 'waitress', "--listen=127.0.0.1:$Port", '--threads=8', '--ident=SIGOS', 'wsgi_prod:app') $envFile
        $h = Wait-Health $Port 200 60
        if ($h.Body.checks.database -ne 'UP') { throw "database=$($h.Body.checks.database)" }
        $enc = Sql "SELECT TOP 1 c.encrypt_option FROM sys.dm_exec_connections c JOIN sys.dm_exec_sessions s ON s.session_id = c.session_id WHERE s.login_name = N'$appUser'"
        if ($enc -ne 'TRUE') { throw "conexion de la API sin cifrar (encrypt_option=$enc)" }
        $notes.Add("API: latencia BD $($h.Body.latency_ms.database) ms; conexion cifrada")
    }
    Step '9. Persistencia: lo escrito por un proceso lo lee otro y SQL Server lo confirma' {
        Probe @('marker', 'put', "persist-$rid") | Out-Null
        if ((Probe @('marker', 'count', "persist-$rid")) -ne '1') { throw 'no se lee el marcador' }
        if ((Sql "SELECT COUNT(*) FROM [$db].dbo.Notificaciones WHERE Asunto = N'persist-$rid'") -ne '1') { throw 'no esta en SQL Server' }
    }
    Step '10. Worker (mismo comando que SIGOS-Worker) procesa la cola en SQL Server y escribe heartbeat' {
        Probe @('enqueue', '3') | Out-Null
        $env:WORKER_HEARTBEAT_FILE = "$tmp\run\worker.heartbeat"
        $script:worker = Start-Svc 'worker' @("`"$app\docker\worker.py`"") $envFile
        $deadline = (Get-Date).AddSeconds(40); $ok = $false
        do {
            Start-Sleep 2
            $s = Probe @('stats') | ConvertFrom-Json
            # Sin SMTP configurado el envio falla: el worker debe registrar el intento (reintento) sin perder la notificacion.
            if ($s.pending -and $s.pending.sum_retries -ge 3) { $ok = $true }
        } while (-not $ok -and (Get-Date) -lt $deadline)
        if (-not $ok) { throw ("el worker no proceso la cola: " + (Get-Content "$tmp\worker.out.log", "$tmp\worker.err.log" -Tail 5 -ErrorAction SilentlyContinue) -join ' | ') }
        if (-not (Test-Path "$tmp\run\worker.heartbeat")) { throw 'sin heartbeat' }
        if ($worker.HasExited) { throw 'el worker termino' }
    }
    Step '11. Reconexion: tras cortar (KILL) las sesiones de la app, la API vuelve a UP sin reiniciar' {
        $spids = @((Sql "SELECT session_id FROM sys.dm_exec_sessions WHERE login_name = N'$appUser'") -split "`r?`n" | Where-Object { $_ -match '^\d+$' })
        if (-not $spids) { throw 'no hay sesiones de la app que cortar' }
        foreach ($s in $spids) { Sql "KILL $s" | Out-Null }
        $first = Get-Health $Port
        $h = Wait-Health $Port 200 30
        if ($api.HasExited -or $worker.HasExited) { throw 'un proceso termino tras el corte' }
        $notes.Add("Reconexion: $($spids.Count) sesiones cortadas; primera peticion HTTP $($first.Code), despues UP")
    }
    Step '12. BD inaccesible: /health/live 200, /health 503, sin credenciales en la respuesta y sin caer' {
        $p2 = $Port + 1
        $down = Start-Svc 'api-down' @('-m', 'waitress', "--listen=127.0.0.1:$p2", '--threads=4', 'wsgi_prod:app') $badEnv
        Wait-Health $p2 200 60 '/api/v1/health/live' | Out-Null
        $deadline = (Get-Date).AddSeconds(60)
        do {
            $code = 0; $body = ''
            try { $resp = Invoke-WebRequest "http://127.0.0.1:$p2/api/v1/health" -TimeoutSec 40 -UseBasicParsing; $code = [int]$resp.StatusCode; $body = $resp.Content }
            catch { try { $code = [int]$_.Exception.Response.StatusCode; $body = (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() } catch { } }
        } while ($code -ne 503 -and (Get-Date) -lt $deadline)
        if ($code -ne 503) { throw "health=$code" }
        if ($body -match [regex]::Escape($appPwd) -or $body -match 'PWD|UID=') { throw 'la respuesta expone la conexion' }
        if ($down.HasExited) { throw 'la API termino con la BD caida' }
        $logs = (Get-Content "$tmp\api-down.out.log", "$tmp\api-down.err.log" -Raw -ErrorAction SilentlyContinue) -join ''
        if ($logs -match [regex]::Escape($appPwd)) { throw 'el log contiene la contrasena' }
        $env:WORKER_HEARTBEAT_FILE = "$tmp\run\worker-down.heartbeat"
        $wd = Start-Svc 'worker-down' @("`"$app\docker\worker.py`"") $badEnv
        Start-Sleep 25
        if ($wd.HasExited) { throw "el worker termino con la BD caida (codigo $($wd.ExitCode))" }
        $age = ((Get-Date) - (Get-Item "$tmp\run\worker-down.heartbeat").LastWriteTime).TotalSeconds
        if ($age -gt 20) { throw "heartbeat del worker detenido con la BD caida ($([int]$age) s)" }
        $notes.Add('BD caida: API viva (live 200 / health 503) y worker vivo con heartbeat; sin secretos en respuesta ni logs')
    }
    Step '13. Concurrencia: dos procesadores simultaneos no procesan dos veces la misma notificacion' {
        if ($worker -and -not $worker.HasExited) { Stop-Process -Id $worker.Id -Force }
        Sql "UPDATE [$db].dbo.Notificaciones SET Estado = 'failed' WHERE Estado <> 'sent'" | Out-Null
        Probe @('enqueue', '30', 'cc') | Out-Null
        $env:SIGOS_ENV_FILE = $envFile
        $env:PROBE_SEND_LOG = "$tmp\sends.log"
        $startAt = [string]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000 + 8)   # ambos arrancan a la vez
        $jobs = foreach ($i in 1..2) {
            Start-Process -FilePath $py -ArgumentList @("`"$probe`"", "`"$app`"", 'process-once', '0.05', $startAt) -WorkingDirectory $app -PassThru -WindowStyle Hidden `
                -RedirectStandardOutput "$tmp\proc$i.out.log" -RedirectStandardError "$tmp\proc$i.err.log"
        }
        foreach ($j in $jobs) { $j.WaitForExit(120000) | Out-Null }
        $env:PROBE_SEND_LOG = $null
        $sends = @(Get-Content "$tmp\sends.log" -ErrorAction SilentlyContinue | ForEach-Object { ($_ -split "`t")[1] } | Where-Object { $_ -like 'cc-*' })
        $byProc = @(Get-Content "$tmp\sends.log" -ErrorAction SilentlyContinue | ForEach-Object { ($_ -split "`t")[0] } | Group-Object | ForEach-Object { "$($_.Name)=$($_.Count)" })
        $dups = @($sends | Group-Object | Where-Object Count -gt 1)
        $missing = 30 - @($sends | Sort-Object -Unique).Count
        $retries = Sql "SELECT CAST(SUM(Intentos) AS varchar) + '|' + CAST(MAX(Intentos) AS varchar) FROM [$db].dbo.Notificaciones WHERE Asunto LIKE N'cc-%'"
        $notes.Add("Concurrencia: 30 notificaciones, 2 procesos (envios por proceso: $($byProc -join ', ')) -> $($sends.Count) intentos de envio, " +
            "$($dups.Count) notificaciones enviadas mas de una vez, $missing sin intentar; Intentos en BD (suma|max) = $retries")
        if ($dups.Count) { throw "$($dups.Count) notificaciones se enviaron dos veces (duplicado)" }
        if ($missing) { throw "$missing notificaciones no se intentaron" }
    }
    Step '14. Respaldo verificado (backup-db.ps1) y restauracion (Restore-SigosSqlServerDb) sobre la misma base' {
        Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
        # Carpeta propia en la que la cuenta del servicio de SQL Server puede escribir (y que esta prueba puede borrar).
        $bkDir = Join-Path $tmp 'bk'; New-Item -ItemType Directory -Path $bkDir | Out-Null
        $svcAcct = Sql "SELECT TOP 1 service_account FROM sys.dm_server_services WHERE servicename LIKE N'SQL Server (%'"
        & icacls.exe $bkDir /grant "${svcAcct}:(OI)(CI)M" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "no se pudo dar permiso a $svcAcct sobre $bkDir" }
        $bk = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'scripts\backup-db.ps1') -Server $server -Database $db -BackupDir $bkDir -RetentionDays 36500 -PassThru)
        if ($LASTEXITCODE -ne 0) { throw "backup-db.ps1 fallo: $($bk -join ' ')" }
        $file = $bk[-1].Trim(); $script:backupFiles += $file
        Probe @('marker', 'put', "after-backup-$rid") | Out-Null
        $r = Restore-SigosSqlServerDb -Server $server -Database $db -BackupFile $file
        if ($r.Code -ne 0) { throw "restore: $($r.Out)" }
        if ((Probe @('marker', 'count', "after-backup-$rid")) -ne '0') { throw 'la restauracion no devolvio el estado del respaldo' }
        if ((Probe @('marker', 'count', "persist-$rid")) -ne '1') { throw 'falta un dato anterior al respaldo' }
        if ((Sql "SELECT version_num FROM [$db].dbo.alembic_version") -ne $rev1) { throw 'revision distinta tras restaurar' }
        $notes.Add('Restauracion: dato posterior al respaldo eliminado, dato anterior presente, login de la app sigue funcionando')
    }
} finally {
    foreach ($p in $procs) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
    Start-Sleep 1
    if ($created) {
        $clean = Invoke-SigosSqlcmd $server ("USE master; IF DB_ID(N'$db') IS NOT NULL BEGIN ALTER DATABASE [$db] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [$db]; END; " +
            "IF SUSER_ID(N'$appUser') IS NOT NULL DROP LOGIN [$appUser]; IF SUSER_ID(N'$migUser') IS NOT NULL DROP LOGIN [$migUser];") 120
        if ($clean.Code -eq 0) { Write-Host "Limpieza: base $db y logins $appUser / $migUser eliminados" } else { Write-Host "AVISO: limpieza incompleta: $($clean.Out)" -ForegroundColor Yellow }
    }
    $env:SIGOS_ENV_FILE = $null; $env:WORKER_HEARTBEAT_FILE = $null
    if ($KeepTemp) { Write-Host "Temporales en $tmp" } else { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
Write-Host ''
$notes | ForEach-Object { Write-Host "  - $_" }
$failed = @($results.Values | Where-Object { $_ -ne 'PASS' }).Count
Write-Host ("Resultado: {0} PASS, {1} FAIL" -f ($results.Count - $failed), $failed)
exit ([int]($failed -gt 0))
