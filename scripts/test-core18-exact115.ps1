[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$private = Join-Path $repo 'work\foundation\test\private'
$dbContainer = 'nestakada-foundation-test-db'
$dbNetwork = 'nestakada-foundation-test-db'
$sourceDatabase = 'estakada_rb5_home_preview'
$previewApp = 'nestakada-rb5-home-app'
$previewIngress = 'nestakada-rb5-home-ingress'
$runToken = [guid]::NewGuid().ToString('N')
$scope = "core18-exact115-$runToken"
$appName = "nestakada-core18-exact115-$runToken"
$appId = ''
$databaseId = ''
$databaseWasRunning = $false
$failed = $null

function Fail-Core18([string]$Code) { throw $Code }

function Invoke-Docker([string[]]$Arguments) {
    $output = @(& docker.exe @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        $safeCodes = @([regex]::Matches(($output -join "`n"), '(?:CORE18|R7)_[A-Z0-9_]+'))
        if ($safeCodes.Count -gt 0) { Fail-Core18 $safeCodes[-1].Value }
        Fail-Core18 'CORE18_EXACT115_DOCKER_FAILED'
    }
    return $output
}

function Read-Container([string]$Name) {
    $rows = @(Invoke-Docker @('inspect', $Name) | ConvertFrom-Json)
    if ($rows.Count -ne 1) { Fail-Core18 'CORE18_EXACT115_CONTAINER_AMBIGUOUS' }
    return $rows[0]
}

function Assert-NoOwnedContainer {
    $rows = @(& docker.exe ps -a --filter "label=nestakada.scope=$scope" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0 -or $rows.Count -ne 0) {
        Fail-Core18 'CORE18_EXACT115_CLEANUP_UNCERTAIN'
    }
}

try {
    foreach ($path in @(
        (Join-Path $repo 'src'),
        (Join-Path $repo 'tools\rebuild7_http_smoke.py'),
        (Join-Path $repo 'tools\core18_exact115.py'),
        (Join-Path $repo 'docs\analytics-route-map.csv'),
        (Join-Path $private 'migrator-password'),
        (Join-Path $private 'database-ca')
    )) {
        $item = Get-Item -Force -LiteralPath $path
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Fail-Core18 'CORE18_EXACT115_MOUNT_UNSAFE'
        }
    }

    Assert-NoOwnedContainer
    $database = Read-Container $dbContainer
    if ([string]$database.Name -cne "/$dbContainer") {
        Fail-Core18 'CORE18_EXACT115_DATABASE_IDENTITY_MISMATCH'
    }
    $databaseId = [string]$database.Id
    $databaseWasRunning = [bool]$database.State.Running
    $network = @(Invoke-Docker @('network', 'inspect', $dbNetwork) | ConvertFrom-Json)
    if ($network.Count -ne 1 -or -not [bool]$network[0].Internal) {
        Fail-Core18 'CORE18_EXACT115_NETWORK_NOT_INTERNAL'
    }
    if ($database.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $dbNetwork) {
        Fail-Core18 'CORE18_EXACT115_DATABASE_NETWORK_MISMATCH'
    }

    if (-not $databaseWasRunning) {
        $started = @(Invoke-Docker @('start', $databaseId))
        if ($started.Count -ne 1 -or [string]$started[0] -cne $databaseId) {
            Fail-Core18 'CORE18_EXACT115_DATABASE_START_FAILED'
        }
    }
    $ready = $false
    foreach ($attempt in 1..30) {
        & docker.exe exec --user postgres $databaseId pg_isready -U postgres -d postgres *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { Fail-Core18 'CORE18_EXACT115_DATABASE_NOT_READY' }
    $runningDatabase = Read-Container $databaseId
    if (
        [string]$runningDatabase.Id -cne $databaseId -or
        -not [bool]$runningDatabase.State.Running
    ) { Fail-Core18 'CORE18_EXACT115_DATABASE_IDENTITY_MISMATCH' }

    $preview = Read-Container $previewApp
    $ingress = Read-Container $previewIngress
    if ([bool]$preview.State.Running -or [bool]$ingress.State.Running) {
        Fail-Core18 'CORE18_EXACT115_PREVIEW_MUST_BE_STOPPED'
    }
    $appImage = [string]$preview.Image
    if ($appImage -notmatch '^sha256:[0-9a-f]{64}$') {
        Fail-Core18 'CORE18_EXACT115_IMAGE_NOT_PINNED'
    }

    $arguments = @(
        'run', '-d', '--name', $appName,
        '--label', "nestakada.scope=$scope", '--label', "nestakada.run=$runToken",
        '--network', $dbNetwork, '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app',
        '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore',
        '--env', 'ESTAKADA_LOCAL_RESTORE=1',
        '--env', 'ESTAKADA_DJANGO_SECRET=core18-exact115-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000',
        '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$sourceDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password',
        '--env', 'ESTAKADA_DB_HOST=db', '--env', 'ESTAKADA_DB_PORT=5432',
        '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly",
        '--mount', "type=bind,source=$repo\tools\rebuild7_http_smoke.py,target=/tools/rebuild7_http_smoke.py,readonly",
        '--mount', "type=bind,source=$repo\tools\core18_exact115.py,target=/tools/core18_exact115.py,readonly",
        '--mount', "type=bind,source=$repo\docs\analytics-route-map.csv,target=/authority/analytics-route-map.csv,readonly",
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
        $appImage, 'python', '-B', '/app/manage.py', 'runserver', '0.0.0.0:8000', '--noreload'
    )
    $appIdRows = @(Invoke-Docker $arguments)
    if ($appIdRows.Count -ne 1 -or [string]$appIdRows[0] -notmatch '^[0-9a-f]{64}$') {
        Fail-Core18 'CORE18_EXACT115_CONTAINER_ID_INVALID'
    }
    $appId = [string]$appIdRows[0]

    $ready = $false
    foreach ($attempt in 1..30) {
        & docker.exe exec $appId python -B -c "from urllib.request import Request,urlopen; r=Request('http://localhost:8000/',headers={'X-Estakada-Request-Target':'/'}); assert urlopen(r,timeout=2).status==200" 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { Fail-Core18 'CORE18_EXACT115_APP_NOT_READY' }

    $result = @(Invoke-Docker @('exec', $appId, 'python', '-B', '/tools/core18_exact115.py'))
    if (
        $result.Count -ne 1 -or
        [string]$result[0] -cne 'CORE18_EXACT115_OK routes=115 requests=230 default_off=1 request_rows=0 audit_mutation=0 external_network=0'
    ) { Fail-Core18 'CORE18_EXACT115_RESULT_INVALID' }
    Write-Output $result[0]
}
catch {
    $failed = $_
}
finally {
    $ownedIds = @(& docker.exe ps -a --filter "label=nestakada.scope=$scope" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0 -or $ownedIds.Count -gt 1) {
        $failed = 'CORE18_EXACT115_CLEANUP_UNCERTAIN'
    }
    elseif ($ownedIds.Count -eq 1) {
        $cleanupId = [string]$ownedIds[0]
        $identity = @(& docker.exe inspect --format '{{index .Config.Labels "nestakada.run"}}|{{.Name}}' $cleanupId)
        if (
            $LASTEXITCODE -ne 0 -or
            $identity.Count -ne 1 -or
            [string]$identity[0] -cne "$runToken|/$appName"
        ) {
            $failed = 'CORE18_EXACT115_OWNERSHIP_AMBIGUOUS'
        }
        else {
            & docker.exe rm --force $cleanupId *> $null
            if ($LASTEXITCODE -ne 0) { $failed = 'CORE18_EXACT115_CLEANUP_FAILED' }
        }
    }

    if ($databaseId) {
        $databaseRows = @(& docker.exe inspect $databaseId 2>$null | ConvertFrom-Json)
        if (
            $LASTEXITCODE -ne 0 -or
            $databaseRows.Count -ne 1 -or
            [string]$databaseRows[0].Id -cne $databaseId
        ) {
            $failed = 'CORE18_EXACT115_DATABASE_BITMAP_UNCERTAIN'
        }
        else {
            $databaseRunning = [bool]$databaseRows[0].State.Running
            if (-not $databaseWasRunning -and $databaseRunning) {
                & docker.exe stop --time 10 $databaseId *> $null
                if ($LASTEXITCODE -ne 0) {
                    $failed = 'CORE18_EXACT115_DATABASE_BITMAP_UNCERTAIN'
                }
                $afterStop = @(& docker.exe inspect $databaseId 2>$null | ConvertFrom-Json)
                if (
                    $LASTEXITCODE -ne 0 -or
                    $afterStop.Count -ne 1 -or
                    [string]$afterStop[0].Id -cne $databaseId
                ) {
                    $failed = 'CORE18_EXACT115_DATABASE_BITMAP_UNCERTAIN'
                }
                else {
                    $databaseRunning = [bool]$afterStop[0].State.Running
                }
            }
            if ($databaseRunning -ne $databaseWasRunning) {
                $failed = 'CORE18_EXACT115_DATABASE_BITMAP_UNCERTAIN'
            }
        }
    }
}

Assert-NoOwnedContainer
Write-Output 'CORE18_EXACT115_CLEANUP_OK containers=0 networks_created=0 volumes_created=0 staging=0 database_bitmap=exact'
if ($null -ne $failed) { throw $failed }
