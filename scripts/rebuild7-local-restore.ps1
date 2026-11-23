[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$private = Join-Path $repo 'work\foundation\test\private'
$preview = Join-Path $repo 'work\rb5-home-preview'
$mediaSource = Join-Path $preview 'media'
$workRoot = Join-Path $repo 'work\r7-local-001'
$stagingRoot = Join-Path $workRoot 'staging'
$resultsRoot = Join-Path $workRoot 'results'
$dbContainer = 'nestakada-foundation-test-db'
$dbNetwork = 'nestakada-foundation-test-db'
$sourceDatabase = 'estakada_rb5_home_preview'
$previewApp = 'nestakada-rb5-home-app'
$previewIngress = 'nestakada-rb5-home-ingress'
$appImage = ''
$runId = [guid]::NewGuid().ToString('N')
$restoreDatabase = "estakada_r7_$runId"
$restoreApp = "nestakada-r7-app-$runId"
$staging = Join-Path $stagingRoot $runId
$capture = Join-Path $staging 'capture'
$verify = Join-Path $staging 'verify'
$finalCapture = Join-Path $staging 'final'
$restoredMedia = Join-Path $staging 'restored-media'
$phase = 'preflight'
$restoreDatabaseCreated = $false
$restoreAppStarted = $false
$previewAppWasRunning = $false
$previewIngressWasRunning = $false
$previewAppId = ''
$previewIngressId = ''
$postgresImage = ''
$coordinatorLockPath = Join-Path $workRoot 'coordinator.lock'
$coordinatorLock = $null
$coordinatorLockOwned = $false
$runtimeBoundaryReady = $false

function Fail-R7([string]$Reason = 'R7_LOCAL_RESTORE_UNAVAILABLE') { throw $Reason }

function Invoke-Docker([string[]]$Arguments) {
    $result = @(& docker.exe @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        $codes = @([regex]::Matches(($result -join "`n"), 'R7_[A-Z0-9_]+'))
        if ($codes.Count -gt 0) { Fail-R7 $codes[-1].Value }
        Fail-R7
    }
    return $result
}

function Read-Container([string]$Name) {
    $rows = @(Invoke-Docker @('inspect', $Name) | ConvertFrom-Json)
    if ($rows.Count -ne 1) { Fail-R7 }
    return $rows[0]
}

function Assert-ContainerIdentity([string]$Name, [string]$ExpectedId) {
    $item = Read-Container $Name
    if ([string]$item.Id -cne $ExpectedId) { Fail-R7 }
}

function Assert-Directory([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if (!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-R7 }
}

function Assert-ContainedPathChain([string]$Root, [string]$Target, [bool]$InspectChildren = $false) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    $targetFull = [IO.Path]::GetFullPath($Target)
    if (![string]::Equals($rootFull, [IO.Path]::GetPathRoot($rootFull), [StringComparison]::OrdinalIgnoreCase)) {
        $rootFull = $rootFull.TrimEnd([IO.Path]::DirectorySeparatorChar)
    }
    if (![string]::Equals($targetFull, [IO.Path]::GetPathRoot($targetFull), [StringComparison]::OrdinalIgnoreCase)) {
        $targetFull = $targetFull.TrimEnd([IO.Path]::DirectorySeparatorChar)
    }
    $prefix = $rootFull
    if (!$prefix.EndsWith([IO.Path]::DirectorySeparatorChar)) { $prefix += [IO.Path]::DirectorySeparatorChar }
    if (
        ![string]::Equals($targetFull, $rootFull, [StringComparison]::OrdinalIgnoreCase) -and
        !$targetFull.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
    ) { Fail-R7 'R7_STAGING_CONTAINMENT_FAILED' }
    $rootItem = Get-Item -Force -LiteralPath $rootFull
    if (
        !$rootItem.PSIsContainer -or
        ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        ![string]::Equals([IO.Path]::GetFullPath($rootItem.FullName), $rootFull, [StringComparison]::OrdinalIgnoreCase)
    ) { Fail-R7 'R7_STAGING_CONTAINMENT_FAILED' }
    $current = $rootFull
    $relative = $targetFull.Substring($rootFull.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
    foreach ($part in @($relative -split '[\\/]' | Where-Object { $_ })) {
        $current = Join-Path $current $part
        $item = Get-Item -Force -LiteralPath $current
        if (
            !$item.PSIsContainer -or
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            ![string]::Equals([IO.Path]::GetFullPath($item.FullName), [IO.Path]::GetFullPath($current), [StringComparison]::OrdinalIgnoreCase)
        ) { Fail-R7 'R7_STAGING_CONTAINMENT_FAILED' }
    }
    if ($InspectChildren) {
        foreach ($item in @(Get-ChildItem -Force -LiteralPath $targetFull -Recurse)) {
            $itemFull = [IO.Path]::GetFullPath($item.FullName)
            if (
                ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
                !$itemFull.StartsWith($targetFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
            ) { Fail-R7 'R7_STAGING_CONTAINMENT_FAILED' }
        }
    }
}

function Remove-ExactStaging([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $expectedParent = [IO.Path]::GetFullPath($stagingRoot)
    if (
        [IO.Path]::GetDirectoryName($full) -cne $expectedParent -or
        [IO.Path]::GetFileName($full) -notmatch '^[0-9a-f]{32}$'
    ) { Fail-R7 'R7_STAGING_CONTAINMENT_FAILED' }
    if (Test-Path -LiteralPath $full) {
        Assert-ContainedPathChain ([IO.Path]::GetPathRoot($repo)) $repo
        Assert-ContainedPathChain $repo $full $true
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

function Assert-SourceWriterInventory {
    $result = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-tAc',
        "SELECT count(*) FROM pg_stat_activity WHERE datname='$sourceDatabase' AND backend_type='client backend'"
    ))
    if ($result.Count -ne 1 -or ([string]$result[0]).Trim() -cne '0') { Fail-R7 'R7_SOURCE_WRITER_INVENTORY_OPEN' }
}

function Assert-ExactJsonProperties([object]$Value, [string[]]$Expected) {
    $actual = @($Value.PSObject.Properties.Name | Sort-Object)
    $wanted = @($Expected | Sort-Object)
    if ($actual.Count -ne $wanted.Count) { Fail-R7 }
    for ($index = 0; $index -lt $wanted.Count; $index++) {
        if ([string]$actual[$index] -cne [string]$wanted[$index]) { Fail-R7 }
    }
}

function Assert-GenerationManifest {
    $path = Join-Path $capture 'generation-manifest.json'
    $item = Get-Item -Force -LiteralPath $path
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-R7 }
    $manifest = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    Assert-ExactJsonProperties $manifest @('schema', 'generation', 'artifacts')
    if ($manifest.schema -cne 'estakada.r7-local-candidate-v1' -or $manifest.generation -cne $runId) { Fail-R7 }
    $expected = @('capture-facts.json', 'database.dump', 'media-inventory.json', 'media.tar', 'release-manifest.json')
    $artifacts = @($manifest.artifacts)
    if ($artifacts.Count -ne $expected.Count) { Fail-R7 }
    for ($index = 0; $index -lt $expected.Count; $index++) {
        $artifact = $artifacts[$index]
        Assert-ExactJsonProperties $artifact @('name', 'bytes', 'sha256')
        if ($artifact.name -cne $expected[$index] -or [string]$artifact.sha256 -notmatch '^[0-9a-f]{64}$') { Fail-R7 }
        $artifactPath = Join-Path $capture $expected[$index]
        $artifactItem = Get-Item -Force -LiteralPath $artifactPath
        if (
            $artifactItem.PSIsContainer -or
            ($artifactItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            [long]$artifact.bytes -ne [long]$artifactItem.Length -or
            [string]$artifact.sha256 -cne (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
        ) { Fail-R7 }
    }
}

function Assert-RestoreDatabaseName([string]$Name) {
    if ($Name -notmatch '^estakada_r7_[0-9a-f]{32}$') { Fail-R7 }
}

function Invoke-AppHelper(
    [string]$Name,
    [string]$Database,
    [string]$OutputPath,
    [AllowNull()][string]$AuthorityPath,
    [string[]]$Command
) {
    if ($Database -cne $sourceDatabase) {
        Assert-RestoreDatabaseName $Database
        if ($Database -cne $restoreDatabase) { Fail-R7 }
    }
    $args = @(
        'run', '--rm', '--name', $Name, '--network', $dbNetwork,
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app',
        '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore',
        '--env', 'ESTAKADA_LOCAL_RESTORE=1',
        '--env', "ESTAKADA_APP_IMAGE_DIGEST=$appImage",
        '--env', 'ESTAKADA_DJANGO_SECRET=r7-local-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000',
        '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$Database", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password',
        '--env', 'ESTAKADA_DB_HOST=db', '--env', 'ESTAKADA_DB_PORT=5432',
        '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly",
        '--mount', "type=bind,source=$repo,target=/project,readonly",
        '--mount', "type=bind,source=$repo\tools\rebuild7_generation.py,target=/tools/rebuild7_generation.py,readonly",
        '--mount', "type=bind,source=$OutputPath,target=/output",
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly"
    )
    if ($Command[-1] -ceq 'verify') { $args += @('--env', 'ESTAKADA_RESTORE_VERIFY_WRITE=1') }
    if ($AuthorityPath) { $args += @('--mount', "type=bind,source=$AuthorityPath,target=/authority,readonly") }
    $args += @($appImage)
    $args += $Command
    $result = @(Invoke-Docker $args)
    if ($result.Count -ne 1 -or [string]$result[0] -notmatch '^R7_GENERATION_(CAPTURE|RESTORE)_OK ') { Fail-R7 }
    return [string]$result[0]
}

function Invoke-MediaHelper([string]$Mode, [string]$AuthorityPath, [AllowNull()][string]$OutputPath) {
    if ($Mode -notin @('pack', 'check', 'verify')) { Fail-R7 }
    $args = @(
        'run', '--rm', '--name', "nestakada-r7-media-$Mode-$runId", '--network', 'none',
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '64',
        '--env', 'PYTHONDONTWRITEBYTECODE=1',
        '--mount', "type=bind,source=$repo\tools\rebuild7_media.py,target=/tools/rebuild7_media.py,readonly",
        '--mount', "type=bind,source=$AuthorityPath,target=/authority,readonly"
    )
    if ($Mode -in @('pack', 'check')) {
        $args += @('--mount', "type=bind,source=$mediaSource,target=/media-source,readonly")
    }
    if ($Mode -ceq 'pack') { $args += @('--mount', "type=bind,source=$OutputPath,target=/output") }
    if ($Mode -ceq 'verify') { $args += @('--mount', "type=bind,source=$restoredMedia,target=/restore-media") }
    $args += @($appImage, 'python', '-B', '/tools/rebuild7_media.py', $Mode)
    $result = @(Invoke-Docker $args)
    if ($result.Count -ne 1 -or [string]$result[0] -notmatch '^R7_MEDIA_(PACK|CHECK|RESTORE)_OK ') { Fail-R7 }
    return [string]$result[0]
}

function Invoke-PostgresHelper([string]$Mode, [string]$Database) {
    if ($Mode -notin @('dump', 'restore')) { Fail-R7 }
    if ($Database -cne $sourceDatabase) { Assert-RestoreDatabaseName $Database }
    $outputMount = "type=bind,source=$capture,target=/output"
    if ($Mode -ceq 'restore') { $outputMount += ',readonly' }
    $args = @(
        'run', '--rm', '--name', "nestakada-r7-pg-$Mode-$runId", '--network', $dbNetwork,
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=4m,uid=10001,gid=10001,mode=0700',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '512m', '--cpus', '1.0', '--pids-limit', '64',
        '--env', "ESTAKADA_DB_NAME=$Database", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--mount', $outputMount,
        '--mount', "type=bind,source=$repo\tools\rebuild7_pg.sh,target=/tools/rebuild7_pg.sh,readonly",
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
        '--entrypoint', '/bin/sh', $postgresImage, '/tools/rebuild7_pg.sh', $Mode
    )
    $result = @(Invoke-Docker $args)
    if ($result.Count -ne 1 -or [string]$result[0] -cne "R7_POSTGRES_$($Mode.ToUpperInvariant())_OK") { Fail-R7 }
    return [string]$result[0]
}

function Write-GenerationManifest {
    $names = @('capture-facts.json', 'database.dump', 'media-inventory.json', 'media.tar', 'release-manifest.json')
    $artifacts = @()
    foreach ($name in $names) {
        $path = Join-Path $capture $name
        $item = Get-Item -Force -LiteralPath $path
        if ($item.PSIsContainer -or $item.Length -lt 1 -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-R7 }
        $artifacts += [ordered]@{
            name = $name
            bytes = [long]$item.Length
            sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $manifest = [ordered]@{ schema = 'estakada.r7-local-candidate-v1'; generation = $runId; artifacts = $artifacts }
    $path = Join-Path $capture 'generation-manifest.json'
    if (Test-Path -LiteralPath $path) { Fail-R7 }
    [IO.File]::WriteAllText($path, (ConvertTo-Json -Compress -Depth 6 -InputObject $manifest) + "`n", [Text.UTF8Encoding]::new($false))
}

function Assert-FileEqual([string]$First, [string]$Second) {
    $left = (Get-FileHash -LiteralPath $First -Algorithm SHA256).Hash
    $right = (Get-FileHash -LiteralPath $Second -Algorithm SHA256).Hash
    if ($left -cne $right) { Fail-R7 'R7_SOURCE_DRIFT' }
}

try {
    foreach ($path in @($repo, $private, $preview, $mediaSource, (Join-Path $repo 'src'), (Join-Path $repo 'docs\analytics-route-map.csv'))) {
        if (!(Test-Path -LiteralPath $path)) { Fail-R7 }
    }
    foreach ($path in @($repo, $private, $preview, $mediaSource)) { Assert-Directory $path }
    Assert-ContainedPathChain ([IO.Path]::GetPathRoot($repo)) $repo
    New-Item -ItemType Directory -Force -Path $workRoot, $stagingRoot, $resultsRoot | Out-Null
    foreach ($path in @($workRoot, $stagingRoot, $resultsRoot)) { Assert-ContainedPathChain $repo $path }
    if (Test-Path -LiteralPath $coordinatorLockPath) { Fail-R7 'R7_COORDINATOR_LOCKED' }
    try {
        $coordinatorLock = [IO.File]::Open(
            $coordinatorLockPath,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::ReadWrite,
            [IO.FileShare]::None
        )
    } catch { Fail-R7 'R7_COORDINATOR_LOCKED' }
    $coordinatorLockOwned = $true
    $lockBytes = [Text.Encoding]::ASCII.GetBytes("$runId`n")
    $coordinatorLock.Write($lockBytes, 0, $lockBytes.Length)
    $coordinatorLock.Flush($true)
    if (!(Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) { Fail-R7 }
    Assert-RestoreDatabaseName $restoreDatabase

    $db = Read-Container $dbContainer
    if (![bool]$db.State.Running -or [string]$db.Name -cne "/$dbContainer") { Fail-R7 }
    $postgresImage = [string]$db.Image
    if ($postgresImage -notmatch '^sha256:[0-9a-f]{64}$') { Fail-R7 }
    $networks = @(Invoke-Docker @('network', 'inspect', $dbNetwork) | ConvertFrom-Json)
    if ($networks.Count -ne 1 -or ![bool]$networks[0].Internal) { Fail-R7 'R7_NETWORK_NOT_INTERNAL' }
    if ($db.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $dbNetwork) { Fail-R7 }
    $app = Read-Container $previewApp
    $ingress = Read-Container $previewIngress
    $appImage = [string]$app.Image
    if ($appImage -notmatch '^sha256:[0-9a-f]{64}$') { Fail-R7 'R7_APP_IMAGE_NOT_PINNED' }
    if ($app.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $dbNetwork) { Fail-R7 }
    $previewAppId = [string]$app.Id
    $previewIngressId = [string]$ingress.Id
    $previewAppWasRunning = [bool]$app.State.Running
    $previewIngressWasRunning = [bool]$ingress.State.Running
    if ($previewIngressWasRunning -and !$previewAppWasRunning) { Fail-R7 }
    $existingTemp = @(Invoke-Docker @('ps', '-a', '--filter', 'name=nestakada-r7-', '--format', '{{.Names}}'))
    if ($existingTemp.Count -ne 0) { Fail-R7 }
    $existingDb = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-tAc', "SELECT datname FROM pg_database WHERE datname ~ '^estakada_r7_[0-9a-f]{32}$' ORDER BY datname"))
    if ($existingDb.Count -ne 0) { Fail-R7 }
    $runtimeBoundaryReady = $true

    New-Item -ItemType Directory -Path $staging, $capture, $verify, $finalCapture, $restoredMedia | Out-Null
    foreach ($path in @($staging, $capture, $verify, $finalCapture, $restoredMedia)) { Assert-ContainedPathChain $repo $path }

    $phase = 'maintenance'
    if ($previewIngressWasRunning) { Invoke-Docker @('stop', '--time', '10', $previewIngress) | Out-Null }
    if ($previewAppWasRunning) { Invoke-Docker @('stop', '--time', '10', $previewApp) | Out-Null }
    Assert-ContainerIdentity $previewApp $previewAppId
    Assert-ContainerIdentity $previewIngress $previewIngressId
    Assert-SourceWriterInventory

    $phase = 'capture'
    $captureLine = Invoke-AppHelper "nestakada-r7-capture-$runId" $sourceDatabase $capture $null @('python', '-B', '/tools/rebuild7_generation.py', 'capture')
    Assert-SourceWriterInventory
    $dumpLine = Invoke-PostgresHelper 'dump' $sourceDatabase
    Assert-SourceWriterInventory
    $mediaLine = Invoke-MediaHelper 'pack' $capture $capture
    Assert-SourceWriterInventory
    Write-GenerationManifest
    Assert-GenerationManifest

    $phase = 'restore-database'
    Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'createdb', '--owner=app_migrator', $restoreDatabase) | Out-Null
    $restoreDatabaseCreated = $true
    Assert-GenerationManifest
    $restoreLine = Invoke-PostgresHelper 'restore' $restoreDatabase

    $phase = 'restore-verify'
    Assert-GenerationManifest
    $phase = 'restore-verify-media'
    $mediaRestoreLine = Invoke-MediaHelper 'verify' $capture $null
    $phase = 'restore-verify-database'
    $verifyLine = Invoke-AppHelper "nestakada-r7-verify-$runId" $restoreDatabase $verify $capture @('python', '-B', '/tools/rebuild7_generation.py', 'verify')

    $phase = 'http'
    $httpArgs = @(
        'run', '-d', '--name', $restoreApp, '--network', $dbNetwork,
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app',
        '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore', '--env', 'ESTAKADA_LOCAL_RESTORE=1',
        '--env', 'ESTAKADA_DJANGO_SECRET=r7-local-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000', '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$restoreDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password', '--env', 'ESTAKADA_DB_HOST=db',
        '--env', 'ESTAKADA_DB_PORT=5432', '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly",
        '--mount', "type=bind,source=$repo\tools\rebuild7_http_smoke.py,target=/tools/rebuild7_http_smoke.py,readonly",
        '--mount', "type=bind,source=$repo\docs\analytics-route-map.csv,target=/authority/analytics-route-map.csv,readonly",
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
        $appImage, 'python', '-B', '/app/manage.py', 'runserver', '0.0.0.0:8000', '--noreload'
    )
    Invoke-Docker $httpArgs | Out-Null
    $restoreAppStarted = $true
    $ready = $false
    for ($index = 0; $index -lt 30; $index++) {
        & docker.exe exec $restoreApp python -B -c "from urllib.request import Request,urlopen; r=Request('http://localhost:8000/',headers={'X-Estakada-Request-Target':'/'}); assert urlopen(r,timeout=2).status==200" 2>$null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (!$ready) { Fail-R7 }
    $httpResult = @(Invoke-Docker @('exec', $restoreApp, 'python', '-B', '/tools/rebuild7_http_smoke.py'))
    if ($httpResult.Count -ne 1 -or [string]$httpResult[0] -notmatch '^R7_HTTP_SMOKE_OK ') { Fail-R7 }
    Invoke-Docker @('rm', '-f', $restoreApp) | Out-Null
    $restoreAppStarted = $false

    $phase = 'source-post-audit'
    Assert-SourceWriterInventory
    $finalLine = Invoke-AppHelper "nestakada-r7-final-$runId" $sourceDatabase $finalCapture $null @('python', '-B', '/tools/rebuild7_generation.py', 'capture')
    Assert-SourceWriterInventory
    foreach ($name in @('release-manifest.json', 'capture-facts.json', 'media-inventory.json')) {
        Assert-FileEqual (Join-Path $capture $name) (Join-Path $finalCapture $name)
    }
    $mediaFinalLine = Invoke-MediaHelper 'check' $capture $null
    Assert-SourceWriterInventory

    $phase = 'result'
    $restoreResult = Get-Content -Raw -LiteralPath (Join-Path $verify 'restore-result.json') | ConvertFrom-Json
    $generationHash = (Get-FileHash -LiteralPath (Join-Path $capture 'generation-manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    $safeResult = [ordered]@{
        schema = 'estakada.r7-local-result-v1'
        run = $runId
        generationManifestSha256 = $generationHash
        releaseSha256 = [string]$restoreResult.releaseSha256
        rawTableCountsSha256 = [string]$restoreResult.rawTableCountsSha256
        rawTableContentSha256 = [string]$restoreResult.rawTableContentSha256
        mediaInventorySha256 = [string]$restoreResult.mediaInventorySha256
        mediaFiles = [int]$restoreResult.mediaFiles
        mediaBytes = [long]$restoreResult.mediaBytes
        sessionsDeleted = [int]$restoreResult.sessionsDeleted
        staffGenerationsBumped = [int]$restoreResult.staffGenerationsBumped
        exact115 = 'PASS'
        privateDenial = 'PASS'
        networkInternal = 'PASS'
        sourcePostAudit = 'PASS'
    }
    $resultPath = Join-Path $resultsRoot "$runId.json"
    if (Test-Path -LiteralPath $resultPath) { Fail-R7 }
}
catch {
    $reason = [string]$_.Exception.Message
    if ($reason -notmatch '^R7_[A-Z0-9_]+$') { $reason = 'R7_LOCAL_RESTORE_UNAVAILABLE' }
    Write-Error "R7_LOCAL_RESTORE_UNAVAILABLE phase=$phase reason=$reason" -ErrorAction Continue
    exit 1
}
finally {
    if ($coordinatorLockOwned) {
        if ($runtimeBoundaryReady) {
            if ($restoreAppStarted -or (& docker.exe ps -a --filter "name=^/$restoreApp$" --format '{{.Names}}')) {
                & docker.exe rm -f $restoreApp 2>$null | Out-Null
            }
            if ($restoreDatabaseCreated) {
                Assert-RestoreDatabaseName $restoreDatabase
                & docker.exe exec --user postgres $dbContainer psql -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$restoreDatabase' AND pid <> pg_backend_pid()" 2>$null | Out-Null
                & docker.exe exec --user postgres $dbContainer dropdb --if-exists $restoreDatabase 2>$null | Out-Null
            }
            if (Test-Path -LiteralPath $staging) { Remove-ExactStaging $staging }

            $leftovers = @(Invoke-Docker @('ps', '-a', '--filter', 'name=nestakada-r7-', '--format', '{{.Names}}'))
            $database = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-tAc', "SELECT datname FROM pg_database WHERE datname ~ '^estakada_r7_[0-9a-f]{32}$' ORDER BY datname"))
            if ($leftovers.Count -ne 0 -or $database.Count -ne 0 -or (Test-Path -LiteralPath $staging)) {
                Fail-R7 'R7_LOCAL_RESTORE_CLEANUP_UNCERTAIN'
            }

            Assert-ContainerIdentity $previewApp $previewAppId
            Assert-ContainerIdentity $previewIngress $previewIngressId
            if (!$previewIngressWasRunning -and [bool](Read-Container $previewIngress).State.Running) {
                Invoke-Docker @('stop', '--time', '10', $previewIngress) | Out-Null
            }
            if (!$previewAppWasRunning -and [bool](Read-Container $previewApp).State.Running) {
                Invoke-Docker @('stop', '--time', '10', $previewApp) | Out-Null
            }
            if ($previewAppWasRunning -and ![bool](Read-Container $previewApp).State.Running) {
                Invoke-Docker @('start', $previewApp) | Out-Null
            }
            if ($previewIngressWasRunning -and ![bool](Read-Container $previewIngress).State.Running) {
                Invoke-Docker @('start', $previewIngress) | Out-Null
            }
            Assert-ContainerIdentity $previewApp $previewAppId
            Assert-ContainerIdentity $previewIngress $previewIngressId
            if (
                [bool](Read-Container $previewApp).State.Running -ne $previewAppWasRunning -or
                [bool](Read-Container $previewIngress).State.Running -ne $previewIngressWasRunning
            ) { Fail-R7 'R7_PREVIEW_BITMAP_UNCERTAIN' }

            Write-Output 'R7_LOCAL_RESTORE_CLEANUP_PASS containers=0 database=0 staging=0 bitmap=exact'
        }
        $coordinatorLock.Dispose()
        $coordinatorLock = $null
        $lockItem = Get-Item -Force -LiteralPath $coordinatorLockPath
        if (
            $lockItem.PSIsContainer -or
            ($lockItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            ![string]::Equals([IO.Path]::GetDirectoryName($lockItem.FullName), [IO.Path]::GetFullPath($workRoot), [StringComparison]::OrdinalIgnoreCase)
        ) { Fail-R7 'R7_COORDINATOR_LOCK_UNCERTAIN' }
        Remove-Item -Force -LiteralPath $coordinatorLockPath
        $coordinatorLockOwned = $false
    }
}

[IO.File]::WriteAllText($resultPath, (ConvertTo-Json -Compress -InputObject $safeResult) + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "R7_LOCAL_RESTORE_PASS run=$runId media_files=$($safeResult.mediaFiles) media_bytes=$($safeResult.mediaBytes) exact115=PASS"
