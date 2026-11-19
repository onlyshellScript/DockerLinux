#Requires -Version 5.1
<#
.SYNOPSIS
  Prueba de integracion REAL de los servicios Windows (requiere PowerShell como administrador).
  Recorre: instalacion limpia -> registro -> API -> worker -> BD -> health -> stop -> start/restart ->
  recuperacion ante fallo (mata el proceso) -> reinstalacion (sin duplicados, secretos conservados) ->
  desinstalacion -> conservacion de datos.

  Por defecto usa SQLite para no tocar SQL Server. Con -DbEngine SqlServer crea la base y los logins indicados.
  El arranque automatico tras reiniciar Windows NO se puede automatizar aqui: ver -RebootPhase.

.PARAMETER Cleanup
  Al terminar, desinstala y borra C:\ProgramData\SIGOS (solo si no habia una instalacion previa).

.PARAMETER RebootPhase
  Prepare: instala y deja todo listo para reiniciar. Verify: tras reiniciar, comprueba que los servicios
  arrancaron solos y que el health responde.

.EXAMPLE
  .\infra\windows\tests\Invoke-SigosIntegration.ps1 -Cleanup
.EXAMPLE
  .\infra\windows\tests\Invoke-SigosIntegration.ps1 -RebootPhase Prepare   # reiniciar Windows y luego:
  .\infra\windows\tests\Invoke-SigosIntegration.ps1 -RebootPhase Verify
#>
[CmdletBinding()] param(
    [ValidateSet('SQLite', 'SqlServer')][string]$DbEngine = 'SQLite',
    [string]$PythonExe,
    [string]$SqlServiceName,
    [ValidateSet('None', 'Prepare', 'Verify')][string]$RebootPhase = 'None',
    [switch]$Cleanup
)
$ErrorActionPreference = 'Stop'
$scripts = (Resolve-Path (Join-Path $PSScriptRoot '..\scripts')).Path
. "$scripts\common.ps1"
$ErrorActionPreference = 'Stop'
Assert-SigosAdmin

$results = [ordered]@{}
function Step([string]$name, [scriptblock]$body) {
    try { & $body; $results[$name] = 'PASS'; Write-Host "[PASS] $name" -ForegroundColor Green }
    catch { $results[$name] = "FAIL: $($_.Exception.Message)"; Write-Host "[FAIL] $name -> $($_.Exception.Message)" -ForegroundColor Red }
}
function Run([string]$script, [string[]]$params = @()) {
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $scripts $script) @params 2>&1
    $code = $LASTEXITCODE
    $out | ForEach-Object { Write-Host "      $_" }
    return $code
}
function Get-SvcPid([string]$name) { (Get-CimInstance Win32_Service -Filter "Name='$name'").ProcessId }
$installArgs = @('-DbEngine', $DbEngine)
if ($PythonExe) { $installArgs += @('-PythonExe', $PythonExe) }
if ($SqlServiceName) { $installArgs += @('-SqlServiceName', $SqlServiceName) }

if ($RebootPhase -eq 'Verify') {
    Step '9. Inicio automatico tras reiniciar Windows' {
        foreach ($s in $SigosServices) {
            $w = Get-CimInstance Win32_Service -Filter "Name='$s'"
            if ($w.StartMode -ne 'Auto') { throw "$s StartMode=$($w.StartMode)" }
            if (-not (Wait-SigosServiceStatus $s 'Running' 180)) { throw "$s no esta en Running tras el reinicio" }
        }
        if (-not (Invoke-SigosHealth 120)) { throw 'health no UP tras el reinicio' }
        $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
        Write-Host "      Ultimo arranque de Windows: $boot"
    }
} else {
    $preexisting = Test-SigosInstalled
    if ($preexisting -and $RebootPhase -eq 'None') {
        throw 'Ya hay una instalacion de SIGOS: esta prueba hace instalacion limpia y desinstalacion. Desinstala antes o usa otra maquina.'
    }

    Step '1. Instalacion limpia' { if ((Run 'install-windows.ps1' $installArgs) -ne 0) { throw 'install-windows.ps1 fallo' } }
    Step '2. Registro de servicios (cuenta virtual, inicio automatico retrasado)' {
        foreach ($s in $SigosServices) {
            $w = Get-CimInstance Win32_Service -Filter "Name='$s'"
            if (-not $w) { throw "$s no existe" }
            if ($w.StartName -ne "NT SERVICE\$s") { throw "$s corre como $($w.StartName)" }
            if ($w.StartMode -ne 'Auto' -or -not $w.DelayedAutoStart) { throw "$s StartMode=$($w.StartMode) Delayed=$($w.DelayedAutoStart)" }
        }
    }
    Step '3. Inicio de la API' { if ((Get-SigosService 'SIGOS-API').Status -ne 'Running') { throw 'SIGOS-API no esta Running' } }
    Step '4. Inicio del worker (heartbeat reciente)' {
        if ((Get-SigosService 'SIGOS-Worker').Status -ne 'Running') { throw 'SIGOS-Worker no esta Running' }
        Start-Sleep 5
        $age = Get-SigosHeartbeatAge
        if ($null -eq $age -or $age -gt 90) { throw "heartbeat=$age" }
    }
    Step '5-6. Health UP y comunicacion con la base de datos' {
        $h = Invoke-SigosHealth 30
        if (-not $h) { throw 'health no UP' }
        if ($h.checks.database -ne 'UP') { throw "database=$($h.checks.database)" }
    }
    Step 'Seguridad: ACL de sigos.env y admin.env' {
        $acl = (Get-Acl $SigosPaths.EnvFile).Access | ForEach-Object { $_.IdentityReference.Value }
        if ($acl -match 'Users|Usuarios|Everyone|Todos') { throw "sigos.env accesible por: $($acl -join ', ')" }
        if (Test-Path $SigosPaths.AdminEnv) {
            $a = (Get-Acl $SigosPaths.AdminEnv).Access | ForEach-Object { $_.IdentityReference.Value }
            if ($a -match 'NT SERVICE') { throw 'admin.env legible por los servicios' }
        }
    }
    if ($RebootPhase -eq 'Prepare') {
        Write-Host "`nListo. Reinicia Windows y ejecuta: .\Invoke-SigosIntegration.ps1 -RebootPhase Verify" -ForegroundColor Yellow
    } else {
        Step '7. Detencion de servicios' {
            if ((Run 'stop-services.ps1') -ne 0) { throw 'stop-services.ps1 fallo' }
            foreach ($s in $SigosServices) { if ((Get-SigosService $s).Status -ne 'Stopped') { throw "$s no se detuvo" } }
            $wrap = Join-Path $SigosPaths.LogDir 'worker\SIGOS-Worker.wrapper.log'
            if (Test-Path $wrap) { Write-Host ('      wrapper worker: ' + ((Get-Content $wrap -Tail 3) -join ' | ')) }
        }
        Step '8. Inicio y reinicio' {
            if ((Run 'start-services.ps1') -ne 0) { throw 'start-services.ps1 fallo' }
            $before = Get-SvcPid 'SIGOS-API'
            if ((Run 'restart-services.ps1') -ne 0) { throw 'restart-services.ps1 fallo' }
            if ((Get-SvcPid 'SIGOS-API') -eq $before) { throw 'el PID no cambio tras reiniciar' }
        }
        Step '10. Recuperacion ante fallos (se mata el proceso de python de la API)' {
            $wrapperPid = Get-SvcPid 'SIGOS-API'
            $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$wrapperPid" | Where-Object { $_.Name -eq 'python.exe' } | Select-Object -First 1
            if (-not $child) { throw 'no se encontro el proceso python hijo de WinSW' }
            Stop-Process -Id $child.ProcessId -Force
            Start-Sleep 15
            if (-not (Invoke-SigosHealth 90)) { throw 'la API no se recupero (onfailure)' }
            if ((Get-SigosService 'SIGOS-API').Status -ne 'Running') { throw 'SIGOS-API no esta Running' }
        }
        $jwtBefore = (Read-SigosEnvFile $SigosPaths.EnvFile)['JWT_SECRET_KEY']
        Step '11. Reinstalacion (sin duplicados, secretos conservados)' {
            if ((Run 'install-windows.ps1' $installArgs) -ne 0) { throw 'reinstalacion fallo' }
            $n = @(Get-Service | Where-Object { $_.Name -like 'SIGOS-*' }).Count
            if ($n -ne 2) { throw "hay $n servicios SIGOS-*" }
            if ((Read-SigosEnvFile $SigosPaths.EnvFile)['JWT_SECRET_KEY'] -ne $jwtBefore) { throw 'JWT_SECRET_KEY cambio' }
            if (-not (Invoke-SigosHealth 60)) { throw 'health no UP tras reinstalar' }
        }
        Step '11b. Sin dependencias artificiales: detener la API no detiene el worker' {
            $deps = (& sc.exe qc 'SIGOS-Worker' | Out-String)
            if ($deps -match 'SIGOS-API') { throw 'SIGOS-Worker depende de SIGOS-API' }
            Stop-Service 'SIGOS-API' -Force
            [void](Wait-SigosServiceStatus 'SIGOS-API' 'Stopped' 60)
            Start-Sleep 3
            if ((Get-SigosService 'SIGOS-Worker').Status -ne 'Running') { throw 'el worker se detuvo con la API' }
            Start-Service 'SIGOS-API'
            if (-not (Invoke-SigosHealth 60)) { throw 'la API no volvio' }
        }
        Step '11c. Estado: SCM, vida y salud por separado' {
            if ((Run 'status-services.ps1') -ne 0) { throw 'status-services.ps1 no devolvio 0' }
            if (-not (Invoke-SigosLiveness 10)) { throw '/health/live no responde' }
        }
        Step '11d. Diagnostico sin secretos' {
            $code = Run 'diagnose-windows.ps1'
            if ($code -ne 0) { throw "diagnose-windows.ps1 devolvio $code" }
            $zip = Get-ChildItem $SigosPaths.SystemLog -Filter 'diagnose-*.zip' | Sort-Object LastWriteTime | Select-Object -Last 1
            if (-not $zip) { throw 'no se genero el .zip' }
            $x = Join-Path ([IO.Path]::GetTempPath()) ('sigos-diag-' + [guid]::NewGuid().ToString('N'))
            Expand-Archive $zip.FullName -DestinationPath $x
            try {
                $all = (Get-ChildItem $x -Recurse -File | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
                foreach ($s in (Get-SigosSecretValues)) { if ($all.Contains($s)) { throw 'el diagnostico contiene un secreto' } }
            } finally { Remove-Item $x -Recurse -Force }
        }
        Step '11e. Actualizacion (misma version = reparacion): respaldo, datos y secretos conservados' {
            $markerU = Join-Path $SigosPaths.UploadDir 'update-marker.txt'
            Set-Content -LiteralPath $markerU -Value 'x'
            if ((Run 'update-windows.ps1') -ne 0) { throw 'update-windows.ps1 fallo' }
            $b = Get-ChildItem $SigosPaths.BackupDir -Directory -Filter 'pre-update-*' | Sort-Object Name | Select-Object -Last 1
            foreach ($sub in 'app', 'venv', 'config', 'bin') { if (-not (Test-Path (Join-Path $b.FullName $sub))) { throw "el respaldo no contiene $sub" } }
            if (-not (Test-Path $markerU)) { throw 'la actualizacion borro uploads' }
            if ((Read-SigosEnvFile $SigosPaths.EnvFile)['JWT_SECRET_KEY'] -ne $jwtBefore) { throw 'JWT_SECRET_KEY cambio' }
            if ((Get-Content $SigosPaths.InstallCfg -Raw | ConvertFrom-Json).Version -ne (Get-SigosSourceVersion)) { throw 'install.json sin Version' }
        }
        # Marca en los datos para comprobar que sobreviven a la desinstalacion
        $marker = Join-Path $SigosPaths.UploadDir 'integration-marker.txt'
        Set-Content -LiteralPath $marker -Value (Get-Date -Format o)
        Step '12. Desinstalacion' {
            if ((Run 'uninstall-windows.ps1') -ne 0) { throw 'uninstall-windows.ps1 fallo' }
            foreach ($s in $SigosServices) { if (Get-SigosService $s) { throw "$s sigue registrado" } }
            if (Test-Path $SigosPaths.InstallDir) { throw 'Program Files\SIGOS sigue existiendo' }
        }
        Step '13. Conservacion de datos tras desinstalar' {
            if (-not (Test-Path $SigosPaths.EnvFile)) { throw 'sigos.env eliminado' }
            if (-not (Test-Path $marker)) { throw 'uploads eliminados' }
            if ($DbEngine -eq 'SQLite' -and -not (Get-ChildItem $SigosPaths.DataDir -Filter *.db)) { throw 'base SQLite eliminada' }
            if ((Read-SigosEnvFile $SigosPaths.EnvFile)['JWT_SECRET_KEY'] -ne $jwtBefore) { throw 'JWT_SECRET_KEY cambio' }
        }
        if ($Cleanup -and -not $preexisting) {
            Run 'uninstall-windows.ps1' @('-PurgeData', '-Force') | Out-Null
            Write-Host '      Limpieza: datos de prueba eliminados.'
        }
    }
}
$failed = @($results.Values | Where-Object { $_ -ne 'PASS' }).Count
Write-Host ''
$results.GetEnumerator() | ForEach-Object { Write-Host ("{0,-70} {1}" -f $_.Key, $_.Value) }
Write-Host ("Resultado: {0} PASS, {1} FAIL" -f ($results.Count - $failed), $failed)
exit ([int]($failed -gt 0))
