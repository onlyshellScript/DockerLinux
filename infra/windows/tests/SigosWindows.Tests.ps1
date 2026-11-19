#Requires -Version 5.1
<#
  Pruebas automatizadas SIN privilegios de administrador. Compatibles con Pester 3.4 (incluido en Windows)
  y Pester 5 (runner de GitHub): contexto en BeforeAll, casos con -TestCases, aserciones con throw.
  Ejecutar:  Invoke-Pester .\infra\windows\tests\SigosWindows.Tests.ps1
#>

Describe 'Scripts PowerShell' {
    BeforeAll { . (Join-Path $PSScriptRoot 'TestHelpers.ps1') }

    It 'todos los .ps1 se analizan sin errores en PowerShell 5.1' {
        foreach ($f in Get-SigosPs1Files) {
            $errors = $null
            [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$errors)
            Assert-True (@($errors).Count -eq 0) "$($f.Name): $($errors | ForEach-Object Message)"
        }
    }
    It 'todos los .ps1 tienen BOM UTF-8 (PowerShell 5.1 lee mal los acentos sin BOM)' {
        foreach ($f in Get-SigosPs1Files) {
            $b = [IO.File]::ReadAllBytes($f.FullName)
            Assert-True ($b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) "$($f.Name) sin BOM"
        }
    }
    It 'existen todos los scripts de administracion' {
        foreach ($n in 'install-windows', 'uninstall-windows', 'start-services', 'stop-services', 'restart-services',
                       'status-services', 'logs-services', 'update-windows', 'diagnose-windows', 'restore-database', 'verify-package') {
            Assert-True (Test-Path (Join-Path $scripts "$n.ps1")) "falta $n.ps1"
        }
    }
    It 'ningun script pasa contrasenas por argumentos de linea de comandos' {
        foreach ($f in Get-SigosPs1Files) {
            $t = Get-Content $f.FullName -Raw
            Assert-True ($t -notmatch '-P\s+\$') "$($f.Name) usa sqlcmd -P"
            Assert-True ($t -notmatch 'password=\s*\$') "$($f.Name) pasa password= a sc.exe"
            Assert-True ($t -notmatch '-U\s+\$') "$($f.Name) usa sqlcmd -U (usar -E)"
        }
    }
    It 'los scripts que modifican el sistema exigen administrador' {
        foreach ($n in 'install-windows', 'uninstall-windows', 'start-services', 'stop-services', 'restart-services', 'update-windows', 'restore-database') {
            $t = Get-Content (Join-Path $scripts "$n.ps1") -Raw
            Assert-True ($t -match 'Assert-SigosAdmin') "$n.ps1 no llama a Assert-SigosAdmin"
        }
    }
}

Describe 'Plantillas WinSW' {
    BeforeAll {
        . (Join-Path $PSScriptRoot 'TestHelpers.ps1')
        $script:tokens = @{
            '{{VENV}}' = 'C:\Program Files\SIGOS\venv'; '{{APP_DIR}}' = 'C:\Program Files\SIGOS\app'
            '{{ENV_FILE}}' = 'C:\ProgramData\SIGOS\config\sigos.env'; '{{LOG_DIR}}' = 'C:\ProgramData\SIGOS\logs'
            '{{RUN_DIR}}' = 'C:\ProgramData\SIGOS\run'; '{{API_LISTEN}}' = '127.0.0.1:5000'; '{{API_THREADS}}' = '8'
            '{{DEPENDS}}' = '  <depend>MSSQL$SQLEXPRESS</depend>'
        }
    }
    It '<t> renderiza XML valido, sin marcadores ni secretos' -TestCases @(@{ t = 'sigos-api' }, @{ t = 'sigos-worker' }) {
        param($t)
        $xml = Get-Content (Join-Path $winRoot "services\$t.xml.template") -Raw
        foreach ($k in $tokens.Keys) { $xml = $xml.Replace($k, $tokens[$k]) }
        Assert-True ($xml -notmatch '\{\{') 'quedan marcadores sin reemplazar'
        $doc = [xml]$xml
        Assert-True ($doc.service.startmode -eq 'Automatic') 'startmode no es Automatic'
        Assert-True ($doc.service.log.mode -eq 'roll-by-size') 'sin rotacion de logs'
        Assert-True (@($doc.service.onfailure).Count -ge 1) 'sin reinicio ante fallos'
        Assert-True ($doc.service.stoptimeout) 'sin stoptimeout'
        $envNames = @($doc.service.env | ForEach-Object { $_.name })
        foreach ($bad in 'JWT_SECRET_KEY', 'DB_URL', 'DB_APP_PASSWORD', 'SMTP_PASS', 'MSSQL_SA_PASSWORD') {
            Assert-True ($envNames -notcontains $bad) "la plantilla define $bad"
        }
    }
    It 'el worker no depende de SIGOS-API (dependencia artificial): solo de SQL Server si se indica' {
        $t = Get-Content (Join-Path $winRoot 'services\sigos-worker.xml.template') -Raw
        Assert-True ($t -notmatch '<depend>SIGOS-API</depend>') 'SIGOS-Worker depende de SIGOS-API'
        Assert-True ($t -match '\{\{DEPENDS\}\}') 'sin marcador de dependencia de SQL Server'
        $empty = [xml]($t.Replace('{{DEPENDS}}', '') -replace '\{\{[A-Z_]+\}\}', 'x')
        Assert-True (@($empty.service.SelectNodes('depend')).Count -eq 0) 'sin -SqlServiceName no debe haber dependencias'
    }
    It 'la API escucha con waitress y desactiva el hilo del worker' {
        $t = Get-Content (Join-Path $winRoot 'services\sigos-api.xml.template') -Raw
        Assert-True ($t -match '-m waitress') 'no usa waitress'
        Assert-True ($t -match 'ENABLE_NOTIFICATION_WORKER" value="false"') 'no desactiva el worker embebido'
    }
    It 'winsw.lock.json fija version, URL de GitHub y SHA-256' {
        $l = Get-Content (Join-Path $winRoot 'services\winsw.lock.json') -Raw | ConvertFrom-Json
        Assert-True ($l.sha256 -match '^[0-9a-f]{64}$') 'sha256 invalido'
        Assert-True ($l.url -like 'https://github.com/winsw/winsw/releases/download/*') 'URL inesperada'
    }
}

Describe 'Funciones de common.ps1' {
    BeforeAll { . (Join-Path $PSScriptRoot 'TestHelpers.ps1') }

    It 'New-SigosSecret genera valores distintos, largos y sin caracteres problematicos' {
        $a = New-SigosSecret 24; $b = New-SigosSecret 24
        Assert-True ($a -ne $b) 'secretos repetidos'
        Assert-True ($a.Length -ge 32) 'secreto corto'
        Assert-True ($a -match '^[A-Za-z0-9_-]+$') "caracteres no permitidos: $a"
        Assert-True ($a -cmatch '[A-Z]' -and $a -cmatch '[a-z]' -and $a -match '[0-9]') 'no cumple complejidad de SQL Server'
    }
    It 'Read/Write-SigosEnvFile conserva claves y valores con = y espacios' {
        $tmp = [IO.Path]::GetTempFileName()
        try {
            $m = [ordered]@{ A = '1'; B = 'x=y z'; C = '' }
            Write-SigosEnvFile $tmp $m '# cabecera'
            $r = Read-SigosEnvFile $tmp
            Assert-True ($r['B'] -eq 'x=y z' -and $r['C'] -eq '' -and $r.Count -eq 3) 'ida y vuelta incorrecta'
            Assert-True ([IO.File]::ReadAllBytes($tmp)[0] -ne 0xEF) 'el .env no debe llevar BOM (python-dotenv)'
        } finally { Remove-Item $tmp -Force }
    }
    It 'Get-SigosHealthUrl usa 127.0.0.1 por defecto' {
        Assert-True ((Get-SigosHealthUrl) -match '^http://127\.0\.0\.1:\d+/api/v1/health$') (Get-SigosHealthUrl)
    }
    It 'las rutas de instalacion no dependen del usuario' {
        Assert-True ($SigosPaths.InstallDir -like "$env:ProgramFiles*") 'InstallDir fuera de Program Files'
        Assert-True ($SigosPaths.DataRoot -like "$env:ProgramData*") 'DataRoot fuera de ProgramData'
        Assert-True ($SigosPaths.InstallLog -eq (Join-Path $SigosPaths.LogDir 'installer')) 'logs\installer'
        Assert-True ($SigosPaths.SystemLog -eq (Join-Path $SigosPaths.LogDir 'system')) 'logs\system'
    }
    It 'Compare-SigosVersion(<a>, <b>) = <r>' -TestCases @(
        @{ a = '1.0.0'; b = '1.0.0'; r = 0 }, @{ a = '1.0.1'; b = '1.0.0'; r = 1 }, @{ a = '1.0.0'; b = '1.1.0'; r = -1 },
        @{ a = '2.0'; b = '1.9.9'; r = 1 }, @{ a = '1.0.0'; b = '1.0.0-rc.1'; r = 1 }, @{ a = '1.0.0-rc.1'; b = '1.0.0'; r = -1 },
        @{ a = '1.0.0-rc.2'; b = '1.0.0-rc.1'; r = 1 }, @{ a = '1.0.10'; b = '1.0.9'; r = 1 }) {
        param($a, $b, $r)
        $got = Compare-SigosVersion $a $b
        Assert-True ($got -eq $r) "obtenido $got"
    }
    It 'la version del repositorio es legible' {
        Assert-True ((Get-SigosSourceVersion) -match '^\d+\.\d+\.\d+') "VERSION = $(Get-SigosSourceVersion)"
    }
    It 'Protect-SigosText oculta credenciales en URL, ODBC, Bearer y pares clave=valor' {
        $in = @(
            # Credenciales ficticias montadas en tiempo de ejecucion (el detector de secretos del paquete no debe verlas como reales).
            ('mssql+pyodbc://sigos_app:' + 'S3cr3t%40x' + '@db:1433/sigos?driver=ODBC'),
            ('DRIVER={ODBC Driver 18};SERVER=db,1433;UID=sa;' + 'PWD={p4ss;w0rd};Trust=yes'),
            'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def',
            'SMTP_PASS=hunter22 JWT_SECRET_KEY: k3y-val WHATSAPP_API_TOKEN="tok123"'
        ) -join "`n"
        $out = Protect-SigosText $in @()
        foreach ($leak in 'S3cr3t', 'p4ss', 'w0rd', 'eyJhbGci', 'hunter22', 'k3y-val', 'tok123') {
            Assert-True ($out -notmatch [regex]::Escape($leak)) "queda '$leak' en: $out"
        }
        Assert-True ($out -match 'sigos_app:\*\*\*@db') 'debe conservar usuario y host'
        Assert-True ($out -match 'SERVER=db,1433') 'no debe tocar datos no sensibles'
    }
    It 'Protect-SigosText elimina valores secretos conocidos aunque no tengan nombre de clave' {
        $out = Protect-SigosText 'error: login fallido con abcDEF123456 en servidor' @('abcDEF123456')
        Assert-True ($out -eq 'error: login fallido con *** en servidor') $out
        Assert-True ((Protect-SigosText 'Serving on http://127.0.0.1:5000' @()) -eq 'Serving on http://127.0.0.1:5000') 'altera texto benigno'
    }
    It 'Get-SigosSecretValues toma solo los valores sensibles de sigos.env y admin.env' {
        $tmpEnv = [IO.Path]::GetTempFileName(); $tmpAdmin = [IO.Path]::GetTempFileName()
        $saved = $SigosPaths.EnvFile, $SigosPaths.AdminEnv
        try {
            Write-SigosEnvFile $tmpEnv ([ordered]@{ JWT_SECRET_KEY = 'fake-jwt-value'; DB_HOST = 'localhost'; SMTP_PASS = 'fake-smtp-value'; SMTP_PORT = '587' }) ''
            Write-SigosEnvFile $tmpAdmin ([ordered]@{ DB_MIGRATOR_USER = 'sigos_migrator'; DB_MIGRATOR_PASSWORD = 'fake-migrator-value' }) ''
            $SigosPaths.EnvFile = $tmpEnv; $SigosPaths.AdminEnv = $tmpAdmin
            $v = Get-SigosSecretValues
            foreach ($s in 'fake-jwt-value', 'fake-smtp-value', 'fake-migrator-value') { Assert-True ($v -contains $s) "falta $s" }
            foreach ($s in 'localhost', '587', 'sigos_migrator') { Assert-True ($v -notcontains $s) "$s no es secreto" }
        } finally {
            $SigosPaths.EnvFile = $saved[0]; $SigosPaths.AdminEnv = $saved[1]
            Remove-Item $tmpEnv, $tmpAdmin -Force
        }
    }
    It 'Test-SigosSqliteFile reconoce una base SQLite y rechaza otros archivos' {
        $tmp = [IO.Path]::GetTempFileName()
        try {
            [IO.File]::WriteAllBytes($tmp, [byte[]]([Text.Encoding]::ASCII.GetBytes('SQLite format 3') + @(0) + (New-Object byte[] 84)))
            Assert-True (Test-SigosSqliteFile $tmp) 'no reconoce la cabecera'
            [IO.File]::WriteAllText($tmp, 'no soy sqlite')
            Assert-True (-not (Test-SigosSqliteFile $tmp)) 'acepta un archivo cualquiera'
        } finally { Remove-Item $tmp -Force }
    }
}

Describe 'Deteccion de secretos y paquete' {
    BeforeAll {
        . (Join-Path $PSScriptRoot 'TestHelpers.ps1')
        $script:tmpRoot = Join-Path ([IO.Path]::GetTempPath()) ('sigos-pkgtest-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tmpRoot | Out-Null
    }
    AfterAll { Remove-Item -LiteralPath $tmpRoot -Recurse -Force -ErrorAction SilentlyContinue }

    It 'Find-SigosSecretLeaks detecta secretos reales en configuracion y codigo' {
        $d = Join-Path $tmpRoot 'leaky'; New-Item -ItemType Directory $d | Out-Null
        Set-Content (Join-Path $d 'prod.example') ('JWT_SECRET_KEY=' + 'q8Zr4Lw1Xv9Pm2Kt')
        Set-Content (Join-Path $d 'svc.py') ('smtp_password = "' + 'Wq8rT5yZpL3m' + '"')
        Set-Content (Join-Path $d 'url.txt') ('mssql+pyodbc://sa:' + 'Zx9Wq8rT5y' + '@srv:1433/sigos')
        $hits = @(Find-SigosSecretLeaks $d)
        Assert-True ($hits.Count -eq 3) "esperados 3 hallazgos, obtenidos $($hits.Count): $($hits -join ' | ')"
        Assert-True (($hits -join ' ') -notmatch 'q8Zr4Lw1Xv9P') 'el informe no debe repetir el secreto completo'
    }
    It 'Find-SigosSecretLeaks ignora marcadores, claves vacias, codigo y valores ficticios' {
        $d = Join-Path $tmpRoot 'clean'; New-Item -ItemType Directory $d | Out-Null
        Set-Content (Join-Path $d 'sigos.env.example') "JWT_SECRET_KEY=GENERADO_POR_EL_INSTALADOR`r`nSMTP_PASS=`r`nSMTP_FROM=alguien@example.com`r`nDB_URL=sqlite:///C:/x.db"
        Set-Content (Join-Path $d 'cfg.py') ('JWT_SECRET_KEY = _Env(env_secret, "JWT_SECRET_KEY")' + "`n" + 'JWT_SECRET_KEY = "test-secret"')
        $hits = @(Find-SigosSecretLeaks $d)
        Assert-True ($hits.Count -eq 0) "falsos positivos: $($hits -join ' | ')"
    }
    It 'el codigo fuente y la infraestructura Windows no contienen secretos' {
        $hits = @(Find-SigosSecretLeaks $winRoot) + @(Find-SigosSecretLeaks (Join-Path $repoRoot 'services\api\app'))
        Assert-True ($hits.Count -eq 0) ($hits -join ' | ')
    }
    It 'Test-SigosPackage valida un manifiesto y detecta archivos alterados o ausentes' {
        $p = Join-Path $tmpRoot 'pkg'; New-Item -ItemType Directory (Join-Path $p 'services\api') -Force | Out-Null
        Set-Content (Join-Path $p 'services\api\VERSION') '9.9.9' -NoNewline
        Set-Content (Join-Path $p 'a.txt') 'hola'
        $files = foreach ($rel in 'a.txt', 'services/api/VERSION') {
            @{ path = $rel; sha256 = (Get-FileHash (Join-Path $p $rel) -Algorithm SHA256).Hash.ToLower() }
        }
        @{ version = '9.9.9'; files = @($files) } | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $p 'package-manifest.json')
        $ok = Test-SigosPackage $p
        Assert-True ($ok.IsPackage -and $ok.Ok -and $ok.Files -eq 2) "paquete integro rechazado: $($ok.Problems -join ', ')"
        Add-Content (Join-Path $p 'a.txt') 'x'
        $bad = Test-SigosPackage $p
        Assert-True (-not $bad.Ok -and ($bad.Problems -join ' ') -match 'modificado: a\.txt') 'no detecta la modificacion'
        Assert-True (-not (Test-SigosPackage $tmpRoot).IsPackage) 'un directorio sin manifiesto no es un paquete'
    }
    # El empaquetador no viaja dentro del paquete: se omite al ejecutar las pruebas desde un paquete extraido.
    It 'build-package excluye .env, bases, logs, tests de la API y verifica WinSW y secretos' -Skip:(-not (Test-Path (Join-Path $PSScriptRoot '..\package\build-package.ps1'))) {
        $t = Get-Content (Join-Path $winRoot 'package\build-package.ps1') -Raw
        foreach ($p in "'\.env'", "'\*\.db'", "'\*\.log'", "'tests'", 'versions_backup', 'Find-SigosSecretLeaks', 'winsw.lock.json', 'Test-SigosPackage', '--only-binary=:all:') {
            Assert-True ($t -match $p) "build-package.ps1 no contempla $p"
        }
    }
}

Describe 'Instalacion, actualizacion, restauracion y diagnostico' {
    BeforeAll {
        . (Join-Path $PSScriptRoot 'TestHelpers.ps1')
        $script:install = Get-Content (Join-Path $scripts 'install-windows.ps1') -Raw
        $script:update = Get-Content (Join-Path $scripts 'update-windows.ps1') -Raw
        $script:restore = Get-Content (Join-Path $scripts 'restore-database.ps1') -Raw
        $script:diag = Get-Content (Join-Path $scripts 'diagnose-windows.ps1') -Raw
        $script:backup = Get-Content (Join-Path $repoRoot 'scripts\backup-db.ps1') -Raw
    }
    It 'install-windows no adopta en silencio una base o logins existentes en la primera instalacion' {
        Assert-True ($install -match 'UseExistingDatabase' -and $install -match 'ReuseExistingLogins') 'faltan los conmutadores de adopcion'
        Assert-True ($install -match 'SUSER_ID' -and $install -match 'DB_ID') 'no consulta logins/base existentes'
    }
    It 'install-windows crea el usuario inicial sin exponer la contrasena' {
        Assert-True ($install -match 'seed\.py') 'no ejecuta seed.py'
        Assert-True ($install -match 'ADMIN_PASSWORD = \$adminPwd') 'la contrasena debe ir por variable de entorno'
        Assert-True ($install -match 'Set-SigosAcl -Path \$initial') 'initial-admin.txt sin ACL restringida'
    }
    It 'install-windows verifica el paquete y usa las ruedas incluidas sin conexion' {
        Assert-True ($install -match 'Test-SigosPackage') 'no verifica la integridad del paquete'
        Assert-True ($install -match '--no-index --find-links') 'no instala desde wheels/ sin conexion'
    }
    It 'update-windows comprueba versiones y rechaza bajar de version sin -AllowDowngrade' {
        Assert-True ($update -match 'Compare-SigosVersion') 'no compara versiones'
        Assert-True ($update -match '\$cmp -lt 0 -and -not \$AllowDowngrade') 'no protege contra downgrade'
    }
    It 'update-windows separa el rollback de archivos del de base de datos' {
        foreach ($p in "'app'", "'venv'", 'ConfigDir', '\.db', 'Rollback', 'EXIT_ROLLED_BACK', 'EXIT_ROLLBACK_KO', 'restore-database\.ps1') {
            Assert-True ($update -match $p) "falta $p"
        }
        $rollback = $update.Substring($update.IndexOf('# --- 5. Rollback'))
        Assert-True ($rollback -notmatch 'Restore-SigosSqlServerDb|Copy-Item[^\r\n]*\.db') 'el rollback automatico no debe tocar la base de datos'
        Assert-True ($update -notmatch '(?i)(downgrade\(|db downgrade|alembic\S* downgrade\s+-)') 'no debe ejecutar alembic downgrade'
    }
    It 'restore-database pide confirmacion explicita y guarda el estado actual antes de restaurar' {
        Assert-True ($restore -match 'RESTAURAR \$name') 'sin confirmacion escrita'
        Assert-True ($restore -match 'backup-db\.ps1' -and $restore -match 'pre-restore-') 'sin copia de seguridad previa'
        Assert-True ($restore -match 'RESTORE VERIFYONLY') 'no verifica el respaldo'
    }
    It 'backup-db usa sqlcmd -b, verifica el archivo y solo comprime si la edicion lo admite' {
        Assert-True ($backup -match "sqlcmd\.exe -S \`$Server -E -C -b") 'sin -b un error de SQL devuelve 0'
        Assert-True ($backup -match "edition -ne '4'") 'COMPRESSION falla en Express'
        Assert-True ($backup -match 'RESTORE VERIFYONLY') 'no verifica el respaldo'
    }
    It 'diagnose-windows redacta y verifica que no se filtren secretos antes de comprimir' {
        Assert-True ($diag -match 'Protect-SigosText') 'no redacta'
        Assert-True ($diag -match 'Get-SigosSecretValues') 'no carga los secretos a verificar'
        Assert-True ($diag -match 'Se detecto un secreto') 'no verifica fugas'
    }
}

Describe 'Configuracion de ejemplo' {
    BeforeAll { . (Join-Path $PSScriptRoot 'TestHelpers.ps1') }
    It 'sigos.env.example no contiene secretos reales' {
        $t = Get-Content (Join-Path $winRoot 'config\sigos.env.example') -Raw
        Assert-True ($t -match 'JWT_SECRET_KEY=GENERADO_POR_EL_INSTALADOR') 'JWT con valor real'
        Assert-True ($t -match 'DB_APP_PASSWORD=GENERADO_POR_EL_INSTALADOR') 'password con valor real'
    }
    It 'requirements-windows.txt reutiliza las dependencias de la API y fija waitress' {
        $t = Get-Content (Join-Path $winRoot 'requirements-windows.txt') -Raw
        Assert-True ($t -match '-r \.\./\.\./services/api/requirements\.txt') 'no reutiliza requirements.txt'
        Assert-True ($t -match 'waitress==\d+\.\d+\.\d+') 'waitress sin version fija'
    }
}
