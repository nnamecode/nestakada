[CmdletBinding()]
param(
    [switch]$OwnerInteractivePreview
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$private = Join-Path $repo 'work\foundation\test\private'
$preview = Join-Path $repo 'work\rb5-home-preview'
$mediaSource = Join-Path $preview 'media'
$serviceMediaSource = Join-Path $repo 'media\design-concepts\services-v4'
$ownerProjectionTool = Join-Path $repo 'tools\rebuild7_owner_preview_projection.py'
$ownerProjectionTestTool = Join-Path $repo 'tools\test_rebuild7_owner_preview_projection.py'
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
$captureCloneDatabase = "estakada_r7_capture_$runId"
$captureCloneMarker = "estakada.r7-owner-capture:$runId"
$captureDatabase = $sourceDatabase
$captureMigrationContainer = "nestakada-r7-capture-migrate-$runId"
$restoreApp = "nestakada-r7-app-$runId"
$restoreAppAlias = "r7-app-$runId"
$restoreIngress = "nestakada-r7-ingress-$runId"
$previewNetwork = "nestakada-r7-preview-$runId"
$staging = Join-Path $stagingRoot $runId
$capture = Join-Path $staging 'capture'
$verify = Join-Path $staging 'verify'
$finalCapture = Join-Path $staging 'final'
$sourceGuardBefore = Join-Path $staging 'source-guard-before'
$sourceGuardAfter = Join-Path $staging 'source-guard-after'
$restoredMedia = Join-Path $staging 'restored-media'
$ownerProjectionAuthority = Join-Path $staging 'owner-projection-authority'
$ownerProjectionProbeAuthority = Join-Path $staging 'owner-projection-probe-authority'
$phase = 'preflight'
$restoreDatabaseCreated = $false
$restoreAppStarted = $false
$restoreIngressStarted = $false
$previewNetworkCreated = $false
$restoreDatabaseOid = ''
$restoreDatabaseMarker = "estakada.r7-local-restore:$runId"
$restoreDatabaseMarkerApplied = $false
$captureCloneMayExist = $false
$captureCloneCreated = $false
$captureCloneOid = ''
$captureMigrationMayExist = $false
$captureMigrationId = ''
$sourceGuardBeforeComplete = $false
$sourceGuardAfterAttempted = $false
$sourceGuardAfterComplete = $false
$restoreAppId = ''
$restoreIngressId = ''
$previewNetworkId = ''
$previewAppWasRunning = $false
$previewIngressWasRunning = $false
$previewAppId = ''
$previewIngressId = ''
$postgresImage = ''
$ingressImage = ''
$coordinatorLockPath = Join-Path $workRoot 'coordinator.lock'
$coordinatorLock = $null
$coordinatorLockOwned = $false
$runtimeBoundaryReady = $false
$ownerProjectionMediaFiles = 0
$ownerProjectionMediaBytes = 0
$ownerProjectionMediaSha256 = ''

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

function Assert-OwnedRestoreContainer([string]$Id, [string]$Name, [string]$Role, [string]$Image) {
    if ($Id -notmatch '^[0-9a-f]{64}$' -or $Role -notin @('app', 'ingress')) { Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN' }
    $item = Read-Container $Id
    $labels = @($item.Config.Labels.PSObject.Properties)
    $expectedLabelCount = if ($Role -ceq 'ingress') { 4 } else { 3 }
    if (
        [string]$item.Id -cne $Id -or [string]$item.Name -cne "/$Name" -or [string]$item.Image -cne $Image -or
        $labels.Count -ne $expectedLabelCount -or [string]$item.Config.Labels.'estakada.scope' -cne 'r7-local-restore' -or
        [string]$item.Config.Labels.'estakada.run' -cne $runId -or [string]$item.Config.Labels.'estakada.role' -cne $Role -or
        ![bool]$item.HostConfig.ReadonlyRootfs -or [string]$item.HostConfig.RestartPolicy.Name -cne 'no' -or
        @($item.HostConfig.CapDrop).Count -ne 1 -or [string]$item.HostConfig.CapDrop[0] -cne 'ALL' -or
        @($item.HostConfig.SecurityOpt).Count -ne 1 -or [string]$item.HostConfig.SecurityOpt[0] -cne 'no-new-privileges:true'
    ) { Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN' }
    if ($Role -ceq 'ingress' -and [string]$item.Config.Labels.maintainer -cne 'NGINX Docker Maintainers <docker-maint@nginx.com>') {
        Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN'
    }
    return $item
}

function Assert-OwnedPreviewNetwork([int]$ExpectedMembers) {
    if ($previewNetworkId -notmatch '^[0-9a-f]{64}$') { Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN' }
    $rows = @(Invoke-Docker @('network', 'inspect', $previewNetworkId) | ConvertFrom-Json)
    if ($rows.Count -ne 1) { Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN' }
    $item = $rows[0]
    $labels = @($item.Labels.PSObject.Properties)
    if (
        [string]$item.Id -cne $previewNetworkId -or [string]$item.Name -cne $previewNetwork -or
        [string]$item.Driver -cne 'bridge' -or [bool]$item.Internal -or [bool]$item.Attachable -or [bool]$item.Ingress -or
        $labels.Count -ne 2 -or [string]$item.Labels.'estakada.scope' -cne 'r7-owner-preview' -or
        [string]$item.Labels.'estakada.run' -cne $runId -or @($item.Options.PSObject.Properties).Count -ne 0 -or
        @($item.Containers.PSObject.Properties).Count -ne $ExpectedMembers
    ) { Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN' }
    return $item
}

function Assert-OwnedRestoreDatabase {
    if ($restoreDatabaseOid -notmatch '^[1-9][0-9]*$') { Fail-R7 'R7_RESTORE_DATABASE_OWNERSHIP_UNCERTAIN' }
    $sql = "SELECT d.oid::text || '|' || pg_get_userbyid(d.datdba) || '|' || COALESCE(array_to_string(d.datacl, ','),'') || '|' || COALESCE(shobj_description(d.oid,'pg_database'),'') FROM pg_database d WHERE d.datname='$restoreDatabase';"
    $rows = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c', $sql))
    $expectedMarker = if ($restoreDatabaseMarkerApplied) { $restoreDatabaseMarker } else { '' }
    if ($rows.Count -ne 1 -or [string]$rows[0] -cne "$restoreDatabaseOid|app_migrator||$expectedMarker") {
        Fail-R7 'R7_RESTORE_DATABASE_OWNERSHIP_UNCERTAIN'
    }
}

function Assert-CaptureCloneName {
    if (!$OwnerInteractivePreview -or $captureCloneDatabase -notmatch '^estakada_r7_capture_[0-9a-f]{32}$') {
        Fail-R7 'R7_OWNER_CAPTURE_CLONE_SCOPE_INVALID'
    }
}

function Get-CaptureCloneCount {
    Assert-CaptureCloneName
    $rows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT count(*) FROM pg_database WHERE datname='$captureCloneDatabase'"
    ))
    if ($rows.Count -ne 1 -or ([string]$rows[0]).Trim() -notmatch '^[01]$') {
        Fail-R7 'R7_OWNER_CAPTURE_CLONE_UNCERTAIN'
    }
    return [int]([string]$rows[0]).Trim()
}

function Assert-CaptureCloneOwned {
    Assert-CaptureCloneName
    if ($captureCloneOid -notmatch '^[1-9][0-9]*$') { Fail-R7 'R7_OWNER_CAPTURE_CLONE_OWNERSHIP_UNCERTAIN' }
    $sql = "SELECT d.oid::text || '|' || pg_get_userbyid(d.datdba) || '|' || COALESCE(shobj_description(d.oid,'pg_database'),'') FROM pg_database d WHERE d.datname='$captureCloneDatabase'"
    $rows = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c', $sql))
    if ($rows.Count -ne 1 -or [string]$rows[0] -cne "$captureCloneOid|app_migrator|$captureCloneMarker") {
        Fail-R7 'R7_OWNER_CAPTURE_CLONE_OWNERSHIP_UNCERTAIN'
    }
    $acl = "WITH acl AS (SELECT x.* FROM pg_database d CROSS JOIN LATERAL aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) x WHERE d.datname='$captureCloneDatabase') SELECT count(*)::text || '|' || count(*) FILTER (WHERE grantee=(SELECT oid FROM pg_roles WHERE rolname='app_migrator'))::text || '|' || count(*) FILTER (WHERE grantee<>(SELECT oid FROM pg_roles WHERE rolname='app_migrator'))::text || '|' || string_agg(privilege_type,',' ORDER BY privilege_type) || '|' || count(*) FILTER (WHERE NOT is_grantable)::text FROM acl"
    $aclRows = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c', $acl))
    if ($aclRows.Count -ne 1 -or [string]$aclRows[0] -cne '3|3|0|CONNECT,CREATE,TEMPORARY|3') {
        Fail-R7 'R7_OWNER_CAPTURE_CLONE_OWNERSHIP_UNCERTAIN'
    }
}

function Wait-CaptureCloneZeroClients {
    Assert-CaptureCloneName
    for ($index = 0; $index -lt 60; $index++) {
        $rows = @(Invoke-Docker @(
            'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
            "SELECT count(*) FROM pg_stat_activity WHERE datname='$captureCloneDatabase' AND backend_type='client backend'"
        ))
        if ($rows.Count -eq 1 -and ([string]$rows[0]).Trim() -ceq '0') { return }
        Start-Sleep -Milliseconds 250
    }
    Fail-R7 'R7_OWNER_CAPTURE_CLONE_CLIENTS_OPEN'
}

function New-CaptureCloneDatabase {
    Assert-CaptureCloneName
    Assert-SourceWriterInventory
    if ((Get-CaptureCloneCount) -ne 0) { Fail-R7 'R7_OWNER_CAPTURE_CLONE_COLLISION' }
    $script:captureCloneMayExist = $true
    Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'createdb', '--owner=app_migrator',
        "--template=$sourceDatabase", $captureCloneDatabase
    ) | Out-Null
    Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-AtX', '-c',
        "COMMENT ON DATABASE $captureCloneDatabase IS '$captureCloneMarker'; REVOKE CONNECT,TEMPORARY ON DATABASE $captureCloneDatabase FROM PUBLIC; GRANT CONNECT,TEMPORARY ON DATABASE $captureCloneDatabase TO app_migrator"
    ) | Out-Null
    $rows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT oid::text FROM pg_database WHERE datname='$captureCloneDatabase'"
    ))
    if ($rows.Count -ne 1 -or ([string]$rows[0]).Trim() -notmatch '^[1-9][0-9]*$') {
        Fail-R7 'R7_OWNER_CAPTURE_CLONE_OWNERSHIP_UNCERTAIN'
    }
    $script:captureCloneOid = ([string]$rows[0]).Trim()
    $script:captureCloneCreated = $true
    Assert-CaptureCloneOwned
    Assert-SourceWriterInventory
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

function Assert-RestoreClientInventory {
    Assert-RestoreDatabaseName $restoreDatabase
    $result = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-tAc',
        "SELECT count(*) FROM pg_stat_activity WHERE datname='$restoreDatabase' AND backend_type='client backend'"
    ))
    if ($result.Count -ne 1 -or ([string]$result[0]).Trim() -cne '0') { Fail-R7 'R7_OWNER_PROJECTION_CLIENTS_OPEN' }
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

function Assert-OwnedCaptureMigrationContainer([string]$Reference, [string]$ExpectedId) {
    if (!$OwnerInteractivePreview -or $ExpectedId -notmatch '^[0-9a-f]{64}$') {
        Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_OWNERSHIP_UNCERTAIN'
    }
    $item = Read-Container $Reference
    $expectedCommand = @('-B', '/app/manage.py', 'migrate', 'service_requests', '0001_initial', '--noinput')
    $expectedMounts = [ordered]@{
        '/app' = [IO.Path]::GetFullPath((Join-Path $repo 'src'))
        '/run/secrets/db-password' = [IO.Path]::GetFullPath((Join-Path $private 'migrator-password'))
        '/run/secrets/database-ca' = [IO.Path]::GetFullPath((Join-Path $private 'database-ca'))
    }
    $labels = @($item.Config.Labels.PSObject.Properties)
    $ports = @($item.HostConfig.PortBindings.PSObject.Properties)
    if (
        [string]$item.Id -cne $ExpectedId -or [string]$item.Name -cne "/$captureMigrationContainer" -or
        [string]$item.Image -cne $appImage -or $labels.Count -ne 3 -or
        [string]$item.Config.Labels.'estakada.scope' -cne 'r7-owner-capture-clone' -or
        [string]$item.Config.Labels.'estakada.run' -cne $runId -or
        [string]$item.Config.Labels.'estakada.role' -cne 'migrate' -or
        [string]$item.Config.User -cne '10001:10001' -or
        (@($item.Config.Entrypoint) | ConvertTo-Json -Compress) -cne (@('python') | ConvertTo-Json -Compress) -or
        (@($item.Config.Cmd) | ConvertTo-Json -Compress) -cne ($expectedCommand | ConvertTo-Json -Compress) -or
        [string]$item.HostConfig.NetworkMode -cne $dbNetwork -or ![bool]$item.HostConfig.ReadonlyRootfs -or
        [string]$item.HostConfig.RestartPolicy.Name -cne 'no' -or
        @($item.HostConfig.CapDrop).Count -ne 1 -or [string]$item.HostConfig.CapDrop[0] -cne 'ALL' -or
        @($item.HostConfig.SecurityOpt).Count -ne 1 -or [string]$item.HostConfig.SecurityOpt[0] -cne 'no-new-privileges:true' -or
        [long]$item.HostConfig.Memory -ne 805306368L -or [long]$item.HostConfig.NanoCpus -ne 1000000000L -or
        [long]$item.HostConfig.PidsLimit -ne 128L -or $ports.Count -ne 0 -or
        @($item.Mounts).Count -ne $expectedMounts.Count -or
        @($item.Config.Env | Where-Object { $_ -ceq "ESTAKADA_DB_NAME=$captureCloneDatabase" }).Count -ne 1 -or
        @($item.Config.Env | Where-Object { $_ -ceq 'ESTAKADA_RESTORE_VERIFY_WRITE=1' }).Count -ne 1
    ) { Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_OWNERSHIP_UNCERTAIN' }
    foreach ($mount in @($item.Mounts)) {
        if (!$expectedMounts.Contains([string]$mount.Destination) -or [string]$mount.Type -cne 'bind' -or [bool]$mount.RW -or
            ![string]::Equals([IO.Path]::GetFullPath([string]$mount.Source), $expectedMounts[[string]$mount.Destination], [StringComparison]::OrdinalIgnoreCase)) {
            Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_OWNERSHIP_UNCERTAIN'
        }
    }
    return $item
}

function Remove-CaptureMigrationContainer {
    if (!$captureMigrationMayExist) { return }
    $id = $captureMigrationId
    if ($id -notmatch '^[0-9a-f]{64}$') {
        $names = @(Invoke-Docker @('ps', '-a', '--filter', "name=^/$captureMigrationContainer$", '--format', '{{.Names}}'))
        if ($names.Count -eq 0) {
            $script:captureMigrationMayExist = $false
            return
        }
        if ($names.Count -ne 1 -or [string]$names[0] -cne $captureMigrationContainer) {
            Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_OWNERSHIP_UNCERTAIN'
        }
        $candidate = Read-Container $captureMigrationContainer
        $id = [string]$candidate.Id
    }
    Assert-OwnedCaptureMigrationContainer $id $id | Out-Null
    Invoke-Docker @('rm', '-f', $id) | Out-Null
    $remaining = @(Invoke-Docker @('ps', '-a', '--no-trunc', '--filter', "id=$id", '--format', '{{.ID}}'))
    if ($remaining.Count -ne 0) { Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_CLEANUP_UNCERTAIN' }
    $script:captureMigrationId = ''
    $script:captureMigrationMayExist = $false
}

function Invoke-CaptureCloneMigration {
    Assert-CaptureCloneOwned
    $args = @(
        'create', '--name', $captureMigrationContainer,
        '--label', 'estakada.scope=r7-owner-capture-clone', '--label', "estakada.run=$runId", '--label', 'estakada.role=migrate',
        '--network', $dbNetwork, '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app',
        '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore', '--env', 'ESTAKADA_LOCAL_RESTORE=1',
        '--env', 'ESTAKADA_RESTORE_VERIFY_WRITE=1', '--env', 'ESTAKADA_DJANGO_SECRET=r7-owner-capture-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000', '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$captureCloneDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password', '--env', 'ESTAKADA_DB_HOST=db',
        '--env', 'ESTAKADA_DB_PORT=5432', '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly",
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
        '--entrypoint', 'python', $appImage,
        '-B', '/app/manage.py', 'migrate', 'service_requests', '0001_initial', '--noinput'
    )
    $script:captureMigrationMayExist = $true
    $ids = @(Invoke-Docker $args)
    if ($ids.Count -ne 1 -or [string]$ids[0] -notmatch '^[0-9a-f]{64}$') {
        Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_CREATE_FAILED'
    }
    $script:captureMigrationId = [string]$ids[0]
    Assert-OwnedCaptureMigrationContainer $captureMigrationId $captureMigrationId | Out-Null
    Invoke-Docker @('start', '--attach', $captureMigrationId) | Out-Null
    $after = Assert-OwnedCaptureMigrationContainer $captureMigrationId $captureMigrationId
    if ([bool]$after.State.Running -or [int]$after.State.ExitCode -ne 0) {
        Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_FAILED'
    }
    Remove-CaptureMigrationContainer
}

function Assert-CaptureCloneMigrationState {
    Assert-CaptureCloneOwned
    $sql = "SELECT (SELECT count(*) FROM app.django_migrations WHERE app='service_requests' AND name='0001_initial')::text || '|' || (to_regclass('app.service_requests_servicerequest') IS NOT NULL)::int::text || '|' || (to_regclass('app.service_requests_servicerequestdeletionprojection') IS NOT NULL)::int::text || '|' || (SELECT count(*) FROM app.service_requests_servicerequest)::text || '|' || (SELECT count(*) FROM app.service_requests_servicerequestdeletionprojection)::text"
    $rows = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', $captureCloneDatabase, '-AtX', '-c', $sql))
    if ($rows.Count -ne 1 -or [string]$rows[0] -cne '1|1|1|0|0') {
        Fail-R7 'R7_OWNER_CAPTURE_MIGRATION_INVALID'
    }
}

function Remove-CaptureCloneDatabase {
    if (!$captureCloneMayExist) { return }
    Assert-CaptureCloneOwned
    Wait-CaptureCloneZeroClients
    Assert-CaptureCloneOwned
    Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'dropdb', '--if-exists', $captureCloneDatabase) | Out-Null
    if ((Get-CaptureCloneCount) -ne 0) { Fail-R7 'R7_OWNER_CAPTURE_CLONE_CLEANUP_UNCERTAIN' }
    $script:captureCloneCreated = $false
    $script:captureCloneMayExist = $false
    $script:captureCloneOid = ''
}

function Complete-OwnerSourceGuardAfter {
    if (!$OwnerInteractivePreview -or !$sourceGuardBeforeComplete -or $sourceGuardAfterComplete -or $sourceGuardAfterAttempted) {
        Fail-R7 'R7_OWNER_CAPTURE_SOURCE_GUARD_UNAVAILABLE'
    }
    $script:sourceGuardAfterAttempted = $true
    Invoke-AppHelper "nestakada-r7-source-guard-after-$runId" $sourceDatabase $sourceGuardAfter $null @('python', '-B', '/tools/rebuild7_generation.py', 'source-guard') | Out-Null
    Assert-SourceWriterInventory
    Assert-FileEqual (Join-Path $sourceGuardBefore 'source-guard.json') (Join-Path $sourceGuardAfter 'source-guard.json')
    $script:sourceGuardAfterComplete = $true
}

function Invoke-AppHelper(
    [string]$Name,
    [string]$Database,
    [string]$OutputPath,
    [AllowNull()][string]$AuthorityPath,
    [string[]]$Command
) {
    if ($Database -cne $sourceDatabase) {
        if ($Database -ceq $restoreDatabase) {
            Assert-RestoreDatabaseName $Database
        } elseif ($OwnerInteractivePreview -and $Database -ceq $captureCloneDatabase) {
            Assert-CaptureCloneName
            Assert-CaptureCloneOwned
        } else {
            Fail-R7
        }
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
    $expected = switch ($Command[-1]) {
        'capture' { '^R7_GENERATION_CAPTURE_OK ' }
        'verify' { '^R7_GENERATION_RESTORE_OK ' }
        'source-guard' { '^R7_GENERATION_SOURCE_GUARD_OK$' }
        default { '^$' }
    }
    if ($result.Count -ne 1 -or [string]$result[0] -notmatch $expected) { Fail-R7 }
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

function Invoke-OwnerProjectionHelper([string]$Mode) {
    if (!$OwnerInteractivePreview -or $Mode -notin @('apply', 'verify', 'probe')) { Fail-R7 'R7_OWNER_PROJECTION_UNAVAILABLE' }
    $restoredMediaMount = "type=bind,source=$restoredMedia,target=/restore-media"
    $projectionAuthoritySource = if ($Mode -ceq 'probe') { $ownerProjectionProbeAuthority } else { $ownerProjectionAuthority }
    $projectionAuthorityMount = "type=bind,source=$projectionAuthoritySource,target=/projection-authority"
    if ($Mode -ceq 'verify') {
        $restoredMediaMount += ',readonly'
        $projectionAuthorityMount += ',readonly'
    }
    $args = @(
        'run', '--rm', '--name', "nestakada-r7-owner-projection-$Mode-$runId", '--network', $dbNetwork,
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app',
        '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore', '--env', 'ESTAKADA_LOCAL_RESTORE=1',
        '--env', 'ESTAKADA_DJANGO_SECRET=r7-owner-projection-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://127.0.0.1:18085', '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$restoreDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password', '--env', 'ESTAKADA_DB_HOST=db',
        '--env', 'ESTAKADA_DB_PORT=5432', '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly",
        '--mount', "type=bind,source=$serviceMediaSource,target=/source-authority/media/design-concepts/services-v4,readonly",
        '--mount', "type=bind,source=$ownerProjectionTool,target=/tools/rebuild7_owner_preview_projection.py,readonly",
        '--mount', "type=bind,source=$capture,target=/base-authority,readonly",
        '--mount', $projectionAuthorityMount,
        '--mount', $restoredMediaMount,
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly"
    )
    if ($Mode -in @('apply', 'probe')) { $args += @('--env', 'ESTAKADA_RESTORE_VERIFY_WRITE=1') }
    $args += @($appImage, 'python', '-B', '/tools/rebuild7_owner_preview_projection.py', $Mode)
    $result = @(Invoke-Docker $args)
    if ($Mode -ceq 'probe') {
        if ($result.Count -ne 1 -or [string]$result[0] -cne 'R7_OWNER_PROJECTION_PROBE_OK cases=transaction-map019-history-rollback') {
            Fail-R7 'R7_OWNER_PROJECTION_UNAVAILABLE'
        }
        return [ordered]@{ probe = 'PASS' }
    }
    $pattern = "^R7_OWNER_PROJECTION_$($Mode.ToUpperInvariant())_OK assets=23 files=23 usages=23 media_files=(?<files>[1-9][0-9]*) media_bytes=(?<bytes>[1-9][0-9]*) media_sha256=(?<sha>[0-9a-f]{64})$"
    $match = if ($result.Count -eq 1) { [regex]::Match([string]$result[0], $pattern) } else { $null }
    if ($null -eq $match -or !$match.Success) {
        Fail-R7 'R7_OWNER_PROJECTION_UNAVAILABLE'
    }
    $projection = [ordered]@{
        files = [int]$match.Groups['files'].Value
        bytes = [long]$match.Groups['bytes'].Value
        sha256 = [string]$match.Groups['sha'].Value
    }
    if ($projection.files -ne 288 -or $projection.bytes -ne 52751698) { Fail-R7 'R7_OWNER_PROJECTION_UNAVAILABLE' }
    return $projection
}

function Invoke-OwnerProjectionSourceTests {
    if (!$OwnerInteractivePreview) { Fail-R7 'R7_OWNER_PROJECTION_TESTS_UNAVAILABLE' }
    $args = @(
        'run', '--rm', '--name', "nestakada-r7-owner-projection-tests-$runId", '--network', 'none',
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '256m', '--cpus', '0.5', '--pids-limit', '64',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/tools',
        '--env', 'R7_OWNER_PROJECTION_HARNESS=/tools/rebuild7-local-restore.ps1',
        '--mount', "type=bind,source=$ownerProjectionTool,target=/tools/rebuild7_owner_preview_projection.py,readonly",
        '--mount', "type=bind,source=$ownerProjectionTestTool,target=/tools/test_rebuild7_owner_preview_projection.py,readonly",
        '--mount', "type=bind,source=$repo\scripts\rebuild7-local-restore.ps1,target=/tools/rebuild7-local-restore.ps1,readonly",
        '--entrypoint', 'python', $appImage, '-B', '/tools/test_rebuild7_owner_preview_projection.py'
    )
    $result = @(Invoke-Docker $args)
    if ($result.Count -ne 1 -or [string]$result[0] -cne 'R7_OWNER_PROJECTION_TESTS_OK cases=7') {
        Fail-R7 'R7_OWNER_PROJECTION_TESTS_UNAVAILABLE'
    }
}

function Invoke-PostgresHelper([string]$Mode, [string]$Database) {
    if ($Mode -notin @('dump', 'restore')) { Fail-R7 }
    if ($Database -cne $sourceDatabase) {
        if ($Database -ceq $restoreDatabase) {
            Assert-RestoreDatabaseName $Database
        } elseif ($OwnerInteractivePreview -and $Database -ceq $captureCloneDatabase) {
            Assert-CaptureCloneName
            Assert-CaptureCloneOwned
        } else {
            Fail-R7
        }
    }
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
    foreach ($path in @($repo, $private, $preview, $mediaSource, $serviceMediaSource, $ownerProjectionTool, $ownerProjectionTestTool, (Join-Path $repo 'src'), (Join-Path $repo 'docs\analytics-route-map.csv'))) {
        if (!(Test-Path -LiteralPath $path)) { Fail-R7 }
    }
    foreach ($path in @($repo, $private, $preview, $mediaSource, $serviceMediaSource)) { Assert-Directory $path }
    Assert-ContainedPathChain ([IO.Path]::GetPathRoot($repo)) $repo
    Assert-ContainedPathChain $repo $serviceMediaSource $true
    foreach ($path in @($ownerProjectionTool, $ownerProjectionTestTool)) {
        $projectionToolItem = Get-Item -Force -LiteralPath $path
        if ($projectionToolItem.PSIsContainer -or ($projectionToolItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-R7 'R7_OWNER_PROJECTION_UNAVAILABLE' }
    }
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
    $ingressImage = [string]$ingress.Image
    if ($ingressImage -notmatch '^sha256:[0-9a-f]{64}$') { Fail-R7 'R7_INGRESS_IMAGE_NOT_PINNED' }
    $previewAppWasRunning = [bool]$app.State.Running
    $previewIngressWasRunning = [bool]$ingress.State.Running
    if ($previewIngressWasRunning -and !$previewAppWasRunning) { Fail-R7 }
    $existingTemp = @(Invoke-Docker @('ps', '-a', '--filter', 'name=nestakada-r7-', '--format', '{{.Names}}'))
    if ($existingTemp.Count -ne 0) { Fail-R7 }
    $existingNetworks = @(Invoke-Docker @('network', 'ls', '--filter', 'name=^nestakada-r7-preview-', '--format', '{{.Name}}'))
    if ($existingNetworks.Count -ne 0) { Fail-R7 }
    $existingDb = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-tAc', "SELECT datname FROM pg_database WHERE datname ~ '^estakada_r7_([0-9a-f]{32}|capture_[0-9a-f]{32})$' ORDER BY datname"))
    if ($existingDb.Count -ne 0) { Fail-R7 }
    if ($OwnerInteractivePreview) {
        $listener = $null
        try {
            $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 18085)
            $listener.Start()
        } catch { Fail-R7 'R7_OWNER_PREVIEW_PORT_BUSY' }
        finally { if ($null -ne $listener) { $listener.Stop() } }
    }
    $runtimeBoundaryReady = $true

    if ($OwnerInteractivePreview) {
        $phase = 'owner-projection-source-tests'
        Invoke-OwnerProjectionSourceTests
    }

    $stagingDirectories = @($staging, $capture, $verify, $finalCapture, $restoredMedia, $ownerProjectionAuthority, $ownerProjectionProbeAuthority)
    if ($OwnerInteractivePreview) { $stagingDirectories += @($sourceGuardBefore, $sourceGuardAfter) }
    New-Item -ItemType Directory -Path $stagingDirectories | Out-Null
    foreach ($path in $stagingDirectories) { Assert-ContainedPathChain $repo $path }

    $phase = 'maintenance'
    if ($previewIngressWasRunning) { Invoke-Docker @('stop', '--time', '10', $previewIngress) | Out-Null }
    if ($previewAppWasRunning) { Invoke-Docker @('stop', '--time', '10', $previewApp) | Out-Null }
    Assert-ContainerIdentity $previewApp $previewAppId
    Assert-ContainerIdentity $previewIngress $previewIngressId
    Assert-SourceWriterInventory

    if ($OwnerInteractivePreview) {
        $phase = 'owner-capture-source-guard-before'
        Invoke-AppHelper "nestakada-r7-source-guard-before-$runId" $sourceDatabase $sourceGuardBefore $null @('python', '-B', '/tools/rebuild7_generation.py', 'source-guard') | Out-Null
        Assert-SourceWriterInventory
        $sourceGuardBeforeComplete = $true
        $phase = 'owner-capture-clone-create'
        New-CaptureCloneDatabase
        $phase = 'owner-capture-clone-migrate'
        Invoke-CaptureCloneMigration
        $phase = 'owner-capture-clone-verify'
        Assert-CaptureCloneMigrationState
        Wait-CaptureCloneZeroClients
        $captureDatabase = $captureCloneDatabase
    }

    $phase = 'capture'
    $captureLine = Invoke-AppHelper "nestakada-r7-capture-$runId" $captureDatabase $capture $null @('python', '-B', '/tools/rebuild7_generation.py', 'capture')
    Assert-SourceWriterInventory
    $dumpLine = Invoke-PostgresHelper 'dump' $captureDatabase
    Assert-SourceWriterInventory
    $mediaLine = Invoke-MediaHelper 'pack' $capture $capture
    Assert-SourceWriterInventory
    Write-GenerationManifest
    Assert-GenerationManifest

    $phase = 'restore-database'
    Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'createdb', '--owner=app_migrator', $restoreDatabase) | Out-Null
    $databaseRows = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c', "SELECT d.oid::text || '|' || pg_get_userbyid(d.datdba) || '|' || COALESCE(array_to_string(d.datacl, ','),'') || '|' || COALESCE(shobj_description(d.oid,'pg_database'),'') FROM pg_database d WHERE d.datname='$restoreDatabase'"))
    $databaseMatch = if ($databaseRows.Count -eq 1) { [regex]::Match([string]$databaseRows[0], '^(?<oid>[1-9][0-9]*)\|app_migrator\|\|$') } else { $null }
    if ($null -eq $databaseMatch -or !$databaseMatch.Success) { Fail-R7 'R7_RESTORE_DATABASE_OWNERSHIP_UNCERTAIN' }
    $restoreDatabaseOid = [string]$databaseMatch.Groups['oid'].Value
    $restoreDatabaseCreated = $true
    Assert-OwnedRestoreDatabase
    Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-c', "COMMENT ON DATABASE $restoreDatabase IS '$restoreDatabaseMarker'") | Out-Null
    $restoreDatabaseMarkerApplied = $true
    Assert-OwnedRestoreDatabase
    Assert-GenerationManifest
    $restoreLine = Invoke-PostgresHelper 'restore' $restoreDatabase

    $phase = 'restore-verify'
    Assert-GenerationManifest
    $phase = 'restore-verify-media'
    $mediaRestoreLine = Invoke-MediaHelper 'verify' $capture $null
    $phase = 'restore-verify-database'
    $verifyLine = Invoke-AppHelper "nestakada-r7-verify-$runId" $restoreDatabase $verify $capture @('python', '-B', '/tools/rebuild7_generation.py', 'verify')
    if ($OwnerInteractivePreview) {
        $phase = 'owner-projection-probe'
        Invoke-OwnerProjectionHelper 'probe' | Out-Null
        $phase = 'owner-projection-apply'
        $projectionApply = Invoke-OwnerProjectionHelper 'apply'
        $ownerProjectionMediaFiles = [int]$projectionApply.files
        $ownerProjectionMediaBytes = [long]$projectionApply.bytes
        $ownerProjectionMediaSha256 = [string]$projectionApply.sha256
        $phase = 'owner-projection-verify'
        $projectionVerify = Invoke-OwnerProjectionHelper 'verify'
        if (
            [int]$projectionVerify.files -ne $ownerProjectionMediaFiles -or
            [long]$projectionVerify.bytes -ne $ownerProjectionMediaBytes -or
            [string]$projectionVerify.sha256 -cne $ownerProjectionMediaSha256
        ) { Fail-R7 'R7_OWNER_PROJECTION_UNAVAILABLE' }
    }

    $phase = 'http'
    $publicOrigin = if ($OwnerInteractivePreview) { 'http://127.0.0.1:18085' } else { 'http://localhost:8000' }
    $httpArgs = @(
        'run', '-d', '--name', $restoreApp,
        '--label', 'estakada.scope=r7-local-restore', '--label', "estakada.run=$runId", '--label', 'estakada.role=app',
        '--network', $dbNetwork, '--network-alias', $restoreAppAlias,
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app',
        '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore', '--env', 'ESTAKADA_LOCAL_RESTORE=1',
        '--env', 'ESTAKADA_DJANGO_SECRET=r7-local-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', "ESTAKADA_PUBLIC_ORIGIN=$publicOrigin", '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
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
    $appIds = @(Invoke-Docker $httpArgs)
    if ($appIds.Count -ne 1 -or [string]$appIds[0] -notmatch '^[0-9a-f]{64}$') { Fail-R7 'R7_RESTORE_APP_CREATE_FAILED' }
    $restoreAppId = [string]$appIds[0]
    Assert-OwnedRestoreContainer $restoreAppId $restoreApp 'app' $appImage | Out-Null
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

    if ($OwnerInteractivePreview) {
        $phase = 'owner-preview'
        $canonicalNginx = Join-Path $repo 'environment\rebuild5-preview\nginx.conf'
        $staticSource = Join-Path $repo 'src\modules\pages\static'
        foreach ($path in @($canonicalNginx, $staticSource)) {
            if (!(Test-Path -LiteralPath $path)) { Fail-R7 'R7_OWNER_PREVIEW_SOURCE_INVALID' }
        }
        $nginxItem = Get-Item -Force -LiteralPath $canonicalNginx
        if ($nginxItem.PSIsContainer -or ($nginxItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Fail-R7 'R7_OWNER_PREVIEW_SOURCE_INVALID'
        }
        Assert-ContainedPathChain $repo $staticSource $true
        $nginxConfig = Join-Path $staging 'owner-preview-nginx.conf'
        $nginxText = [IO.File]::ReadAllText($canonicalNginx, [Text.Encoding]::UTF8)
        $needle = 'proxy_pass http://app:8000;'
        if ([regex]::Matches($nginxText, [regex]::Escape($needle)).Count -ne 1) { Fail-R7 'R7_OWNER_PREVIEW_CONFIG_INVALID' }
        $nginxText = $nginxText.Replace($needle, "proxy_pass http://$restoreAppAlias`:8000;")
        [IO.File]::WriteAllText($nginxConfig, $nginxText, [Text.UTF8Encoding]::new($false))

        $networkIds = @(Invoke-Docker @(
            'network', 'create', '--driver', 'bridge',
            '--label', 'estakada.scope=r7-owner-preview', '--label', "estakada.run=$runId", $previewNetwork
        ))
        if ($networkIds.Count -ne 1 -or [string]$networkIds[0] -notmatch '^[0-9a-f]{64}$') { Fail-R7 'R7_OWNER_PREVIEW_NETWORK_FAILED' }
        $previewNetworkId = [string]$networkIds[0]
        $previewNetworkCreated = $true
        Assert-OwnedPreviewNetwork 0 | Out-Null

        $ingressArgs = @(
            'create', '--name', $restoreIngress,
            '--label', 'estakada.scope=r7-local-restore', '--label', "estakada.run=$runId", '--label', 'estakada.role=ingress',
            '--network', $previewNetwork,
            '--read-only', '--user', '101:101',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=32m,uid=101,gid=101,mode=1777',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--memory', '256m', '--cpus', '0.5', '--pids-limit', '64',
            '--publish', '127.0.0.1:18085:8080',
            '--mount', "type=bind,source=$nginxConfig,target=/etc/nginx/nginx.conf,readonly",
            '--mount', "type=bind,source=$restoredMedia,target=/srv/public-media,readonly",
            '--mount', "type=bind,source=$staticSource,target=/srv/static,readonly",
            '--entrypoint', 'nginx', $ingressImage, '-g', 'daemon off;'
        )
        $ingressIds = @(Invoke-Docker $ingressArgs)
        if ($ingressIds.Count -ne 1 -or [string]$ingressIds[0] -notmatch '^[0-9a-f]{64}$') {
            Fail-R7 'R7_OWNER_PREVIEW_INGRESS_CREATE_FAILED'
        }
        $restoreIngressId = [string]$ingressIds[0]
        Invoke-Docker @('network', 'connect', $dbNetwork, $restoreIngress) | Out-Null
        Invoke-Docker @('start', $restoreIngress) | Out-Null
        $restoreIngressStarted = $true
        $ingressProjection = Assert-OwnedRestoreContainer $restoreIngressId $restoreIngress 'ingress' $ingressImage
        if (@($ingressProjection.NetworkSettings.Networks.PSObject.Properties).Count -ne 2 -or
            $ingressProjection.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $dbNetwork -or
            $ingressProjection.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $previewNetwork) {
            Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN'
        }
        $portProperties = @($ingressProjection.HostConfig.PortBindings.PSObject.Properties)
        $bindings = @($portProperties | ForEach-Object { @($_.Value) } | Where-Object { $null -ne $_ })
        if ($portProperties.Count -ne 1 -or [string]$portProperties[0].Name -cne '8080/tcp' -or
            $bindings.Count -ne 1 -or [string]$bindings[0].HostIp -cne '127.0.0.1' -or [string]$bindings[0].HostPort -cne '18085') {
            Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN'
        }
        $expectedMounts = [ordered]@{
            '/etc/nginx/nginx.conf' = [IO.Path]::GetFullPath($nginxConfig)
            '/srv/public-media' = [IO.Path]::GetFullPath($restoredMedia)
            '/srv/static' = [IO.Path]::GetFullPath($staticSource)
        }
        if (@($ingressProjection.Mounts).Count -ne $expectedMounts.Count) { Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN' }
        foreach ($destination in $expectedMounts.Keys) {
            $mount = @($ingressProjection.Mounts | Where-Object { [string]$_.Destination -ceq $destination })
            if ($mount.Count -ne 1 -or [bool]$mount[0].RW -or
                [IO.Path]::GetFullPath([string]$mount[0].Source) -cne $expectedMounts[$destination]) {
                Fail-R7 'R7_OWNER_PREVIEW_OWNERSHIP_UNCERTAIN'
            }
        }
        Assert-OwnedPreviewNetwork 1 | Out-Null

        $previewReady = $false
        for ($index = 0; $index -lt 180; $index++) {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -NoProxy -SkipHttpErrorCheck -MaximumRedirection 0 -ConnectionTimeoutSeconds 2 -OperationTimeoutSeconds 2 -Uri 'http://127.0.0.1:18085/'
                if ([int]$response.StatusCode -eq 200) { $previewReady = $true; break }
            } catch {}
            Start-Sleep -Milliseconds 500
        }
        if (!$previewReady) { Fail-R7 'R7_OWNER_PREVIEW_READINESS_FAILED' }
        Write-Output 'R7_OWNER_PREVIEW_READY url=http://127.0.0.1:18085 timeoutMinutes=30 stopToken=STOP'
        [Console]::Out.Flush()
        $stopTask = [Console]::In.ReadLineAsync()
        if (!$stopTask.Wait([TimeSpan]::FromMinutes(30))) { Fail-R7 'R7_OWNER_PREVIEW_TIMEOUT' }
        if ([string]$stopTask.Result -cne 'STOP') { Fail-R7 'R7_OWNER_PREVIEW_STOP_INVALID' }

        Assert-OwnedRestoreContainer $restoreIngressId $restoreIngress 'ingress' $ingressImage | Out-Null
        Invoke-Docker @('rm', '-f', $restoreIngressId) | Out-Null
        $restoreIngressStarted = $false
        $restoreIngressId = ''
        Assert-OwnedPreviewNetwork 0 | Out-Null
        Invoke-Docker @('network', 'rm', $previewNetworkId) | Out-Null
        $previewNetworkCreated = $false
        $previewNetworkId = ''
        Assert-OwnedRestoreContainer $restoreAppId $restoreApp 'app' $appImage | Out-Null
        Invoke-Docker @('rm', '-f', $restoreAppId) | Out-Null
        $restoreAppStarted = $false
        $restoreAppId = ''
        Assert-RestoreClientInventory

        $phase = 'owner-projection-post-verify'
        $projectionPost = Invoke-OwnerProjectionHelper 'verify'
        Assert-RestoreClientInventory
        if (
            [int]$projectionPost.files -ne $ownerProjectionMediaFiles -or
            [long]$projectionPost.bytes -ne $ownerProjectionMediaBytes -or
            [string]$projectionPost.sha256 -cne $ownerProjectionMediaSha256
        ) { Fail-R7 'R7_OWNER_PROJECTION_UNAVAILABLE' }
    }
    if ($restoreAppId -match '^[0-9a-f]{64}$') {
        Assert-OwnedRestoreContainer $restoreAppId $restoreApp 'app' $appImage | Out-Null
        Invoke-Docker @('rm', '-f', $restoreAppId) | Out-Null
        $restoreAppStarted = $false
        $restoreAppId = ''
    }

    $phase = 'source-post-audit'
    Assert-SourceWriterInventory
    $finalLine = Invoke-AppHelper "nestakada-r7-final-$runId" $captureDatabase $finalCapture $null @('python', '-B', '/tools/rebuild7_generation.py', 'capture')
    Assert-SourceWriterInventory
    foreach ($name in @('release-manifest.json', 'capture-facts.json', 'media-inventory.json')) {
        Assert-FileEqual (Join-Path $capture $name) (Join-Path $finalCapture $name)
    }
    $mediaFinalLine = Invoke-MediaHelper 'check' $capture $null
    Assert-SourceWriterInventory
    if ($OwnerInteractivePreview) {
        Wait-CaptureCloneZeroClients
        $phase = 'owner-capture-source-guard-after'
        Complete-OwnerSourceGuardAfter
        $phase = 'owner-capture-clone-drop'
        Remove-CaptureCloneDatabase
    }

    $phase = 'result'
    $restoreResult = Get-Content -Raw -LiteralPath (Join-Path $verify 'restore-result.json') | ConvertFrom-Json
    $generationHash = (Get-FileHash -LiteralPath (Join-Path $capture 'generation-manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($OwnerInteractivePreview) {
        $safeResult = [ordered]@{
            schema = 'estakada.r7-owner-preview-result-v1'
            run = $runId
            generationManifestSha256 = $generationHash
            releaseSha256 = [string]$restoreResult.releaseSha256
            rawTableCountsSha256 = [string]$restoreResult.rawTableCountsSha256
            rawTableContentSha256 = [string]$restoreResult.rawTableContentSha256
            mediaInventorySha256 = [string]$restoreResult.mediaInventorySha256
            baseMediaFiles = [int]$restoreResult.mediaFiles
            baseMediaBytes = [long]$restoreResult.mediaBytes
            projectedMediaFiles = $ownerProjectionMediaFiles
            projectedMediaBytes = $ownerProjectionMediaBytes
            projectedMediaInventorySha256 = $ownerProjectionMediaSha256
            sessionsDeleted = [int]$restoreResult.sessionsDeleted
            staffGenerationsBumped = [int]$restoreResult.staffGenerationsBumped
            exact115 = 'PASS'
            privateDenial = 'PASS'
            databaseNetworkInternal = 'PASS'
            ownerPreviewLoopbackOnly = 'PASS'
            ownerPreviewBridgeInternal = 'NO'
            ownerPreviewProjection = 'exact23-assets-files-usages'
            sourcePostAudit = 'PASS'
        }
    } else {
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
        $cleanupFailures = [Collections.Generic.List[string]]::new()
        if ($runtimeBoundaryReady) {
            if ($captureMigrationMayExist) {
                try { Remove-CaptureMigrationContainer }
                catch { $cleanupFailures.Add('capture-migration') }
            }
            if ($restoreIngressId -match '^[0-9a-f]{64}$') {
                try {
                    Assert-OwnedRestoreContainer $restoreIngressId $restoreIngress 'ingress' $ingressImage | Out-Null
                    & docker.exe rm -f $restoreIngressId 2>$null | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'ingress' }
                } catch { $cleanupFailures.Add('ingress') }
            }
            if ($restoreAppId -match '^[0-9a-f]{64}$') {
                try {
                    Assert-OwnedRestoreContainer $restoreAppId $restoreApp 'app' $appImage | Out-Null
                    & docker.exe rm -f $restoreAppId 2>$null | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'app' }
                } catch { $cleanupFailures.Add('app') }
            }
            if ($previewNetworkId -match '^[0-9a-f]{64}$') {
                try {
                    Assert-OwnedPreviewNetwork 0 | Out-Null
                    & docker.exe network rm $previewNetworkId 2>$null | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'network' }
                } catch { $cleanupFailures.Add('network') }
            }
            if ($restoreDatabaseCreated) {
                try {
                    Assert-RestoreDatabaseName $restoreDatabase
                    Assert-OwnedRestoreDatabase
                    & docker.exe exec --user postgres $dbContainer psql -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$restoreDatabase' AND pid <> pg_backend_pid()" 2>$null | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'database-clients' }
                    & docker.exe exec --user postgres $dbContainer dropdb --if-exists $restoreDatabase 2>$null | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw 'database-drop' }
                    $databaseAfterDrop = @(& docker.exe exec --user postgres $dbContainer psql -d postgres -AtX -c "SELECT oid::text FROM pg_database WHERE datname='$restoreDatabase'" 2>$null)
                    if ($LASTEXITCODE -ne 0 -or $databaseAfterDrop.Count -ne 0) { throw 'database-audit' }
                } catch { $cleanupFailures.Add('database') }
            }
            if ($OwnerInteractivePreview -and $sourceGuardBeforeComplete -and !$sourceGuardAfterComplete) {
                try { Complete-OwnerSourceGuardAfter }
                catch { $cleanupFailures.Add('source-guard') }
            }
            if ($captureCloneMayExist) {
                try { Remove-CaptureCloneDatabase }
                catch { $cleanupFailures.Add('capture-clone') }
            }
            try {
                if (Test-Path -LiteralPath $staging) { Remove-ExactStaging $staging }
            } catch { $cleanupFailures.Add('staging') }

            try {
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
                ) { throw 'bitmap' }
            } catch { $cleanupFailures.Add('bitmap') }

            try {
                $leftovers = @(Invoke-Docker @('ps', '-a', '--filter', 'name=nestakada-r7-', '--format', '{{.Names}}'))
                $networkLeftovers = @(Invoke-Docker @('network', 'ls', '--filter', 'name=^nestakada-r7-preview-', '--format', '{{.Name}}'))
                $database = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-tAc', "SELECT datname FROM pg_database WHERE datname ~ '^estakada_r7_([0-9a-f]{32}|capture_[0-9a-f]{32})$' ORDER BY datname"))
                if ($leftovers.Count -ne 0 -or $networkLeftovers.Count -ne 0 -or $database.Count -ne 0 -or (Test-Path -LiteralPath $staging)) {
                    throw 'post-audit'
                }
            } catch { $cleanupFailures.Add('post-audit') }
        }

        try {
            $coordinatorLock.Dispose()
            $coordinatorLock = $null
        } catch { $cleanupFailures.Add('lock-handle') }

        if ($cleanupFailures.Count -eq 0) {
            try {
                $lockItem = Get-Item -Force -LiteralPath $coordinatorLockPath
                if (
                    $lockItem.PSIsContainer -or
                    ($lockItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
                    ![string]::Equals([IO.Path]::GetDirectoryName($lockItem.FullName), [IO.Path]::GetFullPath($workRoot), [StringComparison]::OrdinalIgnoreCase)
                ) { throw 'lock-path' }
                Remove-Item -Force -LiteralPath $coordinatorLockPath
                $coordinatorLockOwned = $false
            } catch { $cleanupFailures.Add('lock-path') }
        }

        if ($cleanupFailures.Count -eq 0 -and $runtimeBoundaryReady) {
            if ($OwnerInteractivePreview) {
                Write-Output 'R7_OWNER_PREVIEW_CLEANUP_PASS containers=0 networks=0 database=0 staging=0 bitmap=exact'
            } else {
                Write-Output 'R7_LOCAL_RESTORE_CLEANUP_PASS containers=0 database=0 staging=0 bitmap=exact'
            }
        }
        if ($cleanupFailures.Count -ne 0) { throw 'R7_LOCAL_RESTORE_CLEANUP_UNCERTAIN' }
    }
}

[IO.File]::WriteAllText($resultPath, (ConvertTo-Json -Compress -InputObject $safeResult) + "`n", [Text.UTF8Encoding]::new($false))
if ($OwnerInteractivePreview) {
    Write-Output "R7_OWNER_PREVIEW_PASS run=$runId media_files=$($safeResult.projectedMediaFiles) media_bytes=$($safeResult.projectedMediaBytes) exact115=PASS"
} else {
    Write-Output "R7_LOCAL_RESTORE_PASS run=$runId media_files=$($safeResult.mediaFiles) media_bytes=$($safeResult.mediaBytes) exact115=PASS"
}
