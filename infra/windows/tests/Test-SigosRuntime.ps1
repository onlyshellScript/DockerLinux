#Requires -Version 5.1
<#
.SYNOPSIS
  Prueba de ejecucion SIN administrador: crea un venv temporal con requirements-windows.txt, prepara una base
  SQLite con prepare_db.py y lanza la API (waitress) y el worker con los MISMOS comandos y variables que usan
  los servicios WinSW. Comprueba health, conexion a BD y heartbeat del worker. No registra servicios.
.EXAMPLE
  .\infra\windows\tests\Test-SigosRuntime.ps1 -PythonExe 'C:\Program Files\Python312\python.exe'
#>
[CmdletBinding()] param([string]$PythonExe, [int]$Port = 5099, [switch]$KeepTemp)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$app = Join-Path $repo 'services\api'
if (-not $PythonExe) { $PythonExe = (& py.exe -3.12 -c "import sys; print(sys.executable)") }
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("sigos-runtime-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $tmp, "$tmp\data\uploads", "$tmp\run" | Out-Null
$results = [ordered]@{}
$procs = @()
function Step($name, [scriptblock]$body) {
    try { & $body; $results[$name] = 'PASS'; Write-Host "[PASS] $name" -ForegroundColor Green }
    catch { $results[$name] = "FAIL: $($_.Exception.Message)"; Write-Host "[FAIL] $name -> $($_.Exception.Message)" -ForegroundColor Red }
}
try {
    Step 'venv + requirements-windows.txt' {
        & $PythonExe -m venv "$tmp\venv"; if ($LASTEXITCODE) { throw 'venv' }
        $wheelDir = Join-Path $repo 'wheels'
        if (Test-Path $wheelDir) {
            # Paquete de distribucion: igual que install-windows.ps1, sin conexion y con versiones congeladas.
            Write-Host "      dependencias desde $wheelDir (--no-index)"
            & "$tmp\venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check --no-index --find-links $wheelDir `
                -r (Join-Path $repo 'infra\windows\requirements-windows.lock.txt')
        } else {
            & "$tmp\venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r (Join-Path $repo 'infra\windows\requirements-windows.txt')
        }
        if ($LASTEXITCODE) { throw 'pip install' }
    }
    $py = "$tmp\venv\Scripts\python.exe"
    $fwd = $tmp.Replace('\', '/')
    $envFile = "$tmp\sigos.env"
    @("SIGOS_ENV=production", "JWT_SECRET_KEY=runtime-test-$([guid]::NewGuid())", "DB_URL=sqlite:///$fwd/data/sigos.db",
      "UPLOAD_DIR=$tmp\data\uploads", "PROXY_FIX_HOPS=0", "NOTIFICATION_WORKER_INTERVAL=2", "LOG_FORMAT=json") |
        Set-Content -LiteralPath $envFile -Encoding ASCII
    # Mismas variables que las plantillas WinSW
    $env:SIGOS_ENV = 'production'; $env:SIGOS_ENV_FILE = $envFile; $env:PYTHONDONTWRITEBYTECODE = '1'; $env:PYTHONUNBUFFERED = '1'

    Step 'prepare_db.py (SQLite: migraciones)' {
        & $py (Join-Path $app 'docker\prepare_db.py'); if ($LASTEXITCODE) { throw "codigo $LASTEXITCODE" }
        if (-not (Test-Path "$tmp\data\sigos.db")) { throw 'no se creo sigos.db' }
    }
    Step 'prepare_db.py idempotente (segunda ejecucion)' {
        $before = (Get-Item "$tmp\data\sigos.db").Length
        & $py (Join-Path $app 'docker\prepare_db.py'); if ($LASTEXITCODE) { throw "codigo $LASTEXITCODE" }
        if ((Get-Item "$tmp\data\sigos.db").Length -lt $before) { throw 'la base encogio' }
    }
    Step 'API con waitress responde health UP (database=UP)' {
        $env:ENABLE_NOTIFICATION_WORKER = 'false'
        $p = Start-Process -FilePath $py -ArgumentList @('-m', 'waitress', "--listen=127.0.0.1:$Port", '--threads=8', '--ident=SIGOS', 'wsgi_prod:app') `
            -WorkingDirectory $app -PassThru -WindowStyle Hidden -RedirectStandardOutput "$tmp\api.out.log" -RedirectStandardError "$tmp\api.err.log"
        $script:procs += $p
        $ok = $null
        for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
            Start-Sleep 1
            try { $r = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 3 -UseBasicParsing; if ($r.status -eq 'UP') { $ok = $r } } catch { }
        }
        if (-not $ok) { throw ("sin UP. stderr: " + ((Get-Content "$tmp\api.err.log" -Tail 15) -join ' | ')) }
        if ($ok.checks.database -ne 'UP') { throw "database=$($ok.checks.database)" }
    }
    Step 'Worker escribe heartbeat' {
        $env:WORKER_HEARTBEAT_FILE = "$tmp\run\worker.heartbeat"
        $p = Start-Process -FilePath $py -ArgumentList @("`"$app\docker\worker.py`"") -WorkingDirectory $app -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput "$tmp\worker.out.log" -RedirectStandardError "$tmp\worker.err.log"
        $script:procs += $p
        $seen = $false
        for ($i = 0; $i -lt 20 -and -not $seen; $i++) { Start-Sleep 1; $seen = Test-Path "$tmp\run\worker.heartbeat" }
        if (-not $seen) { throw ("sin heartbeat. " + ((Get-Content "$tmp\worker.out.log", "$tmp\worker.err.log" -ErrorAction SilentlyContinue -Tail 10) -join ' | ')) }
        $t1 = (Get-Item "$tmp\run\worker.heartbeat").LastWriteTime
        Start-Sleep 5
        if ((Get-Item "$tmp\run\worker.heartbeat").LastWriteTime -le $t1) { throw 'el heartbeat no avanza' }
        if ($p.HasExited) { throw "el worker termino (codigo $($p.ExitCode))" }
    }
} finally {
    foreach ($p in $procs) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
    Start-Sleep 1
    if ($KeepTemp) { Write-Host "Temporales en $tmp" } else { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
$failed = @($results.Values | Where-Object { $_ -ne 'PASS' }).Count
Write-Host ("Resultado: {0} PASS, {1} FAIL" -f ($results.Count - $failed), $failed)
exit ([int]($failed -gt 0))
