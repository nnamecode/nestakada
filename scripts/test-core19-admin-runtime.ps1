[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runToken = [guid]::NewGuid().ToString('N')
$scope = "core19-admin-$runToken"
$network = "nestakada-core19-net-$runToken"
$volume = "nestakada-core19-pgdata-$runToken"
$databaseName = "nestakada-core19-db-$runToken"
$appName = "nestakada-core19-app-$runToken"
$databaseId = ''
$appId = ''
$networkId = ''
$appImage = 'sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986'
$postgresImage = 'sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$source = $null
$runner = $null
$foundationRequirements = $null
$editorRequirements = $null
$failed = $null

function Fail-Core19([string]$Code) { throw $Code }

function Docker-Output([string[]]$Arguments) {
    $output = @(& docker.exe @Arguments 2>$null)
    if ($LASTEXITCODE -ne 0) { Fail-Core19 'CORE19_DOCKER_COMMAND_FAILED' }
    return $output
}

function Assert-CleanScope {
    $containers = @(Docker-Output @('ps', '-aq', '--filter', "label=nestakada.scope=$scope"))
    $networks = @(Docker-Output @('network', 'ls', '-q', '--filter', "label=nestakada.scope=$scope"))
    $volumes = @(Docker-Output @('volume', 'ls', '-q', '--filter', "label=nestakada.scope=$scope"))
    if (
        $containers.Count -ne 0 -or $networks.Count -ne 0 -or $volumes.Count -ne 0
    ) { Fail-Core19 'CORE19_SCOPE_NOT_CLEAN' }
}

function Container-Identity([string]$Id, [string]$Name) {
    $rows = @(& docker.exe inspect --format '{{.Id}}|{{.Name}}|{{index .Config.Labels "nestakada.run"}}' $Id 2>$null)
    return (
        $LASTEXITCODE -eq 0 -and $rows.Count -eq 1 -and
        [string]$rows[0] -ceq "$Id|/$Name|$runToken"
    )
}

function Read-Container([string]$Id) {
    $rows = @(Docker-Output @('inspect', $Id) | ConvertFrom-Json)
    if ($rows.Count -ne 1 -or [string]$rows[0].Id -cne $Id) {
        Fail-Core19 'CORE19_CONTAINER_INSPECT_INVALID'
    }
    return $rows[0]
}

function Assert-NetworkMembers([string[]]$Expected) {
    $members = @((Docker-Output @(
        'network', 'inspect', '--format',
        '{{range $id, $value := .Containers}}{{$id}}{{"\n"}}{{end}}', $networkId
    )) | Where-Object { $_ })
    if ((@($members | Sort-Object) -join ',') -cne ((@($Expected) | Sort-Object) -join ',')) {
        Fail-Core19 'CORE19_NETWORK_MEMBERSHIP_MISMATCH'
    }
}

function Assert-ContainerBoundary([object]$Item, [bool]$IsDatabase) {
    $networkNames = @($Item.NetworkSettings.Networks.PSObject.Properties.Name)
    $portBindings = @($Item.HostConfig.PortBindings.PSObject.Properties)
    $published = @($Item.NetworkSettings.Ports.PSObject.Properties | Where-Object { $null -ne $_.Value })
    if (
        $networkNames.Count -ne 1 -or $networkNames[0] -cne $network -or
        $portBindings.Count -ne 0 -or $published.Count -ne 0 -or
        -not [bool]$Item.HostConfig.ReadonlyRootfs -or
        @($Item.HostConfig.CapDrop).Count -ne 1 -or [string]$Item.HostConfig.CapDrop[0] -cne 'ALL' -or
        @($Item.HostConfig.SecurityOpt) -notcontains 'no-new-privileges:true'
    ) { Fail-Core19 'CORE19_CONTAINER_BOUNDARY_MISMATCH' }
    $mounts = @($Item.Mounts)
    if ($IsDatabase) {
        $caps = @($Item.HostConfig.CapAdd | Sort-Object)
        if (($caps -join ',') -cne 'CAP_CHOWN,CAP_DAC_OVERRIDE,CAP_FOWNER,CAP_SETGID,CAP_SETUID') {
            Fail-Core19 'CORE19_DATABASE_CAPABILITIES_MISMATCH'
        }
        if (
            [long]$Item.HostConfig.Memory -ne 805306368 -or
            [long]$Item.HostConfig.NanoCpus -ne 750000000 -or
            [long]$Item.HostConfig.PidsLimit -ne 128
        ) { Fail-Core19 'CORE19_DATABASE_RESOURCES_MISMATCH' }
        if (
            $mounts.Count -ne 1 -or [string]$mounts[0].Type -cne 'volume' -or
            [string]$mounts[0].Name -cne $volume -or
            [string]$mounts[0].Destination -cne '/var/lib/postgresql' -or
            -not [bool]$mounts[0].RW
        ) { Fail-Core19 'CORE19_DATABASE_MOUNT_MISMATCH' }
        $tmpfs = $Item.HostConfig.Tmpfs
        if (
            @($tmpfs.PSObject.Properties).Count -ne 2 -or
            [string]$tmpfs.'/var/run/postgresql' -cne 'rw,nosuid,nodev,noexec,size=16m,uid=999,gid=999,mode=3775' -or
            [string]$tmpfs.'/tmp' -cne 'rw,nosuid,nodev,noexec,size=32m,mode=1777'
        ) { Fail-Core19 'CORE19_DATABASE_TMPFS_MISMATCH' }
    }
    else {
        $destinations = @($mounts | ForEach-Object { [string]$_.Destination } | Sort-Object)
        if (@($Item.HostConfig.CapAdd | Where-Object { $null -ne $_ }).Count -ne 0) {
            Fail-Core19 'CORE19_APP_CAPABILITIES_MISMATCH'
        }
        if (
            [long]$Item.HostConfig.Memory -ne 1073741824 -or
            [long]$Item.HostConfig.NanoCpus -ne 1000000000 -or
            [long]$Item.HostConfig.PidsLimit -ne 192
        ) { Fail-Core19 'CORE19_APP_RESOURCES_MISMATCH' }
        if (
            $mounts.Count -ne 4 -or
            ($destinations -join ',') -cne '/project/environment/editor-package/requirements.lock,/project/environment/foundation/requirements.lock,/project/src,/tools/core19_test_runner.py' -or
            @($mounts | Where-Object { [bool]$_.RW }).Count -ne 0
        ) { Fail-Core19 'CORE19_APP_MOUNT_MISMATCH' }
        if (
            [string]$Item.Config.User -cne '10001:10001' -or
            @($Item.HostConfig.Tmpfs.PSObject.Properties).Count -ne 1 -or
            [string]$Item.HostConfig.Tmpfs.'/tmp' -cne 'rw,nosuid,nodev,noexec,size=256m,uid=10001,gid=10001,mode=1777'
        ) { Fail-Core19 'CORE19_APP_TMPFS_OR_USER_MISMATCH' }
        $sources = @($mounts | ForEach-Object { [IO.Path]::GetFullPath([string]$_.Source) } | Sort-Object)
        $expectedSources = @(@($source, $runner, $foundationRequirements, $editorRequirements) | ForEach-Object { [IO.Path]::GetFullPath($_) } | Sort-Object)
        if (($sources -join '|') -cne ($expectedSources -join '|')) {
            Fail-Core19 'CORE19_APP_MOUNT_SOURCE_MISMATCH'
        }
    }
}

function Assert-SafeWorkspacePath([string]$Path, [bool]$Directory) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetFullPath($repo).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not $full.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        Fail-Core19 'CORE19_SOURCE_BOUNDARY_UNSAFE'
    }
    $item = Get-Item -Force -LiteralPath $full
    if ($item.PSIsContainer -ne $Directory -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Fail-Core19 'CORE19_SOURCE_BOUNDARY_UNSAFE'
    }
    $current = if ($Directory) { $full } else { [IO.Path]::GetDirectoryName($full) }
    while (-not [string]::Equals($current, $root, [StringComparison]::OrdinalIgnoreCase)) {
        $parent = Get-Item -Force -LiteralPath $current
        if (-not $parent.PSIsContainer -or ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Fail-Core19 'CORE19_SOURCE_BOUNDARY_UNSAFE'
        }
        $current = [IO.Path]::GetDirectoryName($current)
    }
}

try {
    $source = (Resolve-Path -LiteralPath (Join-Path $repo 'src')).Path
    $runner = (Resolve-Path -LiteralPath (Join-Path $repo 'tools\core19_test_runner.py')).Path
    $foundationRequirements = (Resolve-Path -LiteralPath (Join-Path $repo 'environment\foundation\requirements.lock')).Path
    $editorRequirements = (Resolve-Path -LiteralPath (Join-Path $repo 'environment\editor-package\requirements.lock')).Path
    Assert-CleanScope
    Assert-SafeWorkspacePath $source $true
    foreach ($path in @($runner, $foundationRequirements, $editorRequirements)) {
        Assert-SafeWorkspacePath $path $false
    }
    $moduleCounts = @(
        'modules/accounts/tests/test_http_auth.py|16',
        'modules/pages/tests/test_http_list.py|9', 'modules/pages/tests/test_http_editor.py|34',
        'modules/pages/tests/test_commands.py|13', 'modules/pages/tests/test_grants.py|10',
        'modules/pages/tests/test_http_grants.py|8', 'modules/pages/tests/test_staff_lifecycle.py|13',
        'modules/pages/tests/test_http_staff.py|8', 'modules/pages/tests/test_publication.py|8',
        'modules/pages/tests/test_http_publication.py|7', 'modules/pages/tests/test_public_read.py|10',
        'modules/pages/tests/test_legacy_plain_projection.py|10', 'modules/pages/tests/test_site_settings.py|4',
        'modules/pages/tests/test_site_settings_commands.py|7', 'modules/pages/tests/test_http_site_settings.py|5',
        'modules/pages/tests/test_rename.py|6', 'modules/pages/tests/test_http_rename.py|4',
        'modules/pages/tests/test_create.py|8', 'modules/pages/tests/test_http_create.py|4',
        'modules/pages/tests/test_reorder.py|8', 'modules/pages/tests/test_http_reorder.py|4',
        'modules/pages/tests/test_delete.py|8', 'modules/pages/tests/test_http_delete.py|4',
        'modules/pages/tests/test_move.py|8', 'modules/pages/tests/test_http_move.py|4',
        'modules/pages/tests/test_url_change.py|8', 'modules/pages/tests/test_http_url_change.py|4',
        'modules/pages/tests/test_contract.py|4', 'modules/audit/tests/test_http.py|4',
        'modules/audit/tests/test_retention.py|5'
    )
    if ($moduleCounts.Count -ne 30) { Fail-Core19 'CORE19_STATIC_AUTHORITY_INVALID' }
    foreach ($entry in $moduleCounts) {
        $parts = $entry.Split('|')
        $path = Join-Path $source $parts[0]
        Assert-SafeWorkspacePath $path $false
        $count = @(Select-String -LiteralPath $path -Pattern '^\s+def test_').Count
        if ($count -ne [int]$parts[1]) { Fail-Core19 'CORE19_STATIC_METHOD_COUNT_MISMATCH' }
    }
    $namedMethods = @(
        'fitness/test_rebuild3_schema.py|test_page_url_authority_field_matches_ordinary_add_field_migration',
        'rebuild3_importer/tests/test_runtime_target.py|test_literal_projection_verifies_before_single_commit',
        'rebuild3_importer/tests/test_runtime_target.py|test_exact_committed_projection_returns_closed_proof_once',
        'rebuild3_importer/tests/test_runtime_target.py|test_any_row_or_count_drift_fails_closed',
        'rebuild3_importer/tests/test_runtime_target.py|test_exact_leaves_generated_alias_and_cleanup'
    )
    foreach ($entry in $namedMethods) {
        $parts = $entry.Split('|')
        $path = Join-Path $source $parts[0]
        Assert-SafeWorkspacePath $path $false
        $matches = @(Select-String -LiteralPath $path -Pattern ("^\s+def " + [regex]::Escape($parts[1]) + '\(self'))
        if ($matches.Count -ne 1) { Fail-Core19 'CORE19_STATIC_NAMED_METHOD_MISMATCH' }
    }
    foreach ($image in @($appImage, $postgresImage)) {
        $actual = @(Docker-Output @('image', 'inspect', '--format', '{{.Id}}', $image))
        if ($actual.Count -ne 1 -or [string]$actual[0] -cne $image) {
            Fail-Core19 'CORE19_IMAGE_MISMATCH'
        }
    }

    $networkRows = @(Docker-Output @(
        'network', 'create', '--internal', '--label', "nestakada.scope=$scope",
        '--label', "nestakada.run=$runToken", $network
    ))
    if ($networkRows.Count -ne 1 -or [string]$networkRows[0] -notmatch '^[0-9a-f]{64}$') {
        Fail-Core19 'CORE19_NETWORK_CREATE_AMBIGUOUS'
    }
    $networkId = [string]$networkRows[0]
    $networkFacts = @(Docker-Output @(
        'network', 'inspect', '--format', '{{.Id}}|{{.Internal}}|{{index .Labels "nestakada.run"}}', $networkId
    ))
    if ($networkFacts.Count -ne 1 -or [string]$networkFacts[0] -cne "$networkId|true|$runToken") {
        Fail-Core19 'CORE19_NETWORK_IDENTITY_MISMATCH'
    }

    $volumeRows = @(Docker-Output @(
        'volume', 'create', '--label', "nestakada.scope=$scope",
        '--label', "nestakada.run=$runToken", $volume
    ))
    if ($volumeRows.Count -ne 1 -or [string]$volumeRows[0] -cne $volume) {
        Fail-Core19 'CORE19_VOLUME_CREATE_AMBIGUOUS'
    }
    $volumeFacts = @(Docker-Output @(
        'volume', 'inspect', '--format', '{{.Name}}|{{.Driver}}|{{index .Labels "nestakada.run"}}', $volume
    ))
    if ($volumeFacts.Count -ne 1 -or [string]$volumeFacts[0] -cne "$volume|local|$runToken") {
        Fail-Core19 'CORE19_VOLUME_IDENTITY_MISMATCH'
    }

    $databaseRows = @(Docker-Output @(
        'run', '--detach', '--name', $databaseName, '--network', $network,
        '--network-alias', 'core19-db', '--label', "nestakada.scope=$scope",
        '--label', "nestakada.run=$runToken", '--read-only', '--cap-drop', 'ALL',
        '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE', '--cap-add', 'FOWNER',
        '--cap-add', 'SETGID', '--cap-add', 'SETUID', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '0.75', '--pids-limit', '128',
        '--mount', "type=volume,source=$volume,target=/var/lib/postgresql",
        '--tmpfs', '/var/run/postgresql:rw,nosuid,nodev,noexec,size=16m,uid=999,gid=999,mode=3775',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=32m,mode=1777',
        '--env', 'POSTGRES_DB=postgres', '--env', 'POSTGRES_USER=postgres',
        '--env', 'POSTGRES_PASSWORD=core19-synthetic-only', $postgresImage,
        'postgres', '-c', 'listen_addresses=*', '-c', 'log_statement=none',
        '-c', 'log_min_error_statement=panic', '-c', 'max_connections=40'
    ))
    if ($databaseRows.Count -ne 1 -or [string]$databaseRows[0] -notmatch '^[0-9a-f]{64}$') {
        Fail-Core19 'CORE19_DATABASE_CREATE_AMBIGUOUS'
    }
    $databaseId = [string]$databaseRows[0]
    if (-not (Container-Identity $databaseId $databaseName)) {
        Fail-Core19 'CORE19_DATABASE_IDENTITY_MISMATCH'
    }
    Assert-ContainerBoundary (Read-Container $databaseId) $true
    $ready = $false
    foreach ($attempt in 1..30) {
        & docker.exe exec $databaseId pg_isready -U postgres -d postgres *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { Fail-Core19 'CORE19_DATABASE_NOT_READY' }
    & docker.exe exec $databaseId /bin/sh -ceu @'
u=$(awk '/^Uid:/{print $2 ":" $3 ":" $4}' /proc/1/status)
g=$(awk '/^Gid:/{print $2 ":" $3 ":" $4}' /proc/1/status)
[ "$u" = "999:999:999" ] && [ "$g" = "999:999:999" ]
'@ *> $null
    if ($LASTEXITCODE -ne 0) { Fail-Core19 'CORE19_DATABASE_PROCESS_IDENTITY_MISMATCH' }

    $appRows = @(Docker-Output @(
        'create', '--name', $appName, '--network', $network,
        '--label', "nestakada.scope=$scope", '--label', "nestakada.run=$runToken",
        '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--user', '10001:10001', '--memory', '1024m', '--cpus', '1.0', '--pids-limit', '192',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=256m,uid=10001,gid=10001,mode=1777',
        '--mount', "type=bind,source=$source,target=/project/src,readonly",
        '--mount', "type=bind,source=$runner,target=/tools/core19_test_runner.py,readonly",
        '--mount', "type=bind,source=$foundationRequirements,target=/project/environment/foundation/requirements.lock,readonly",
        '--mount', "type=bind,source=$editorRequirements,target=/project/environment/editor-package/requirements.lock,readonly",
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'DJANGO_SETTINGS_MODULE=config.settings.core19_runtime',
        '--env', 'ESTAKADA_CORE19_SYNTHETIC_RUNTIME=1', '--env', 'ESTAKADA_TEST_RUNTIME=1',
        '--env', 'ESTAKADA_TEST_DB_NAME=estakada_core19_test', '--env', 'ESTAKADA_TEST_DB_HOST=core19-db',
        '--env', 'ESTAKADA_TEST_DB_USER=postgres', '--env', 'ESTAKADA_DJANGO_SECRET=synthetic-core19-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=testserver,localhost', '--env', 'ESTAKADA_DB_NAME=postgres',
        '--env', 'ESTAKADA_DB_USER=postgres', '--env', 'ESTAKADA_DB_PASSWORD=core19-synthetic-only',
        '--env', 'ESTAKADA_DB_HOST=core19-db', '--env', 'ESTAKADA_DB_PORT=5432',
        '--env', 'ESTAKADA_DB_SSLROOTCERT=/tmp/unused-ca', '--env', 'ESTAKADA_SERVICE_REQUESTS_ENABLED=false',
        '--workdir', '/project/src', $appImage, 'python', '-B', '/tools/core19_test_runner.py'
    ))
    if ($appRows.Count -ne 1 -or [string]$appRows[0] -notmatch '^[0-9a-f]{64}$') {
        Fail-Core19 'CORE19_APP_CREATE_AMBIGUOUS'
    }
    $appId = [string]$appRows[0]
    if (-not (Container-Identity $appId $appName)) { Fail-Core19 'CORE19_APP_IDENTITY_MISMATCH' }
    Assert-ContainerBoundary (Read-Container $appId) $false
    Assert-NetworkMembers @($databaseId)
    $started = @(Docker-Output @('start', $appId))
    if ($started.Count -ne 1 -or [string]$started[0] -cne $appId) { Fail-Core19 'CORE19_APP_START_INVALID' }
    $appFinished = $false
    foreach ($attempt in 1..300) {
        if (-not [bool](Read-Container $appId).State.Running) { $appFinished = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $appFinished) { Fail-Core19 'CORE19_APP_TIMEOUT' }
    $result = @(Docker-Output @('logs', $appId))
    $appExit = if ([int](Read-Container $appId).State.ExitCode -eq 0) { 0 } else { 1 }
    if ($result.Count -ne 1 -or [string]$result[0] -notmatch '^CORE19_[A-Z0-9_= ]+$') {
        Fail-Core19 'CORE19_RESULT_INVALID'
    }
    if ($appExit -ne 0) { Fail-Core19 ([string]$result[0] -split ' ')[0] }
    if ([string]$result[0] -cne 'CORE19_ADMIN_RUNTIME_OK tests=250 failures=0 errors=0 skips=0') {
        Fail-Core19 'CORE19_RESULT_INVALID'
    }
    $appState = Read-Container $appId
    if (
        [bool]$appState.State.Running -or [bool]$appState.State.OOMKilled -or
        [bool]$appState.State.Dead -or [int]$appState.State.ExitCode -ne 0 -or
        [string]$appState.State.Error -cne ''
    ) { Fail-Core19 'CORE19_APP_STATE_INVALID' }
    Assert-NetworkMembers @($databaseId)
    Write-Output $result[0]
}
catch {
    $matches = @([regex]::Matches([string]$_.Exception.Message, 'CORE19_[A-Z0-9_]+'))
    $failed = if ($matches.Count) { $matches[-1].Value } else { 'CORE19_RUNTIME_UNAVAILABLE' }
}
finally {
    $ownedContainers = @(& docker.exe ps -aq --no-trunc --filter "label=nestakada.scope=$scope" 2>$null)
    if ($LASTEXITCODE -ne 0 -or $ownedContainers.Count -gt 2) {
        $failed = 'CORE19_CONTAINER_OWNERSHIP_AMBIGUOUS'
    }
    else {
        foreach ($id in $ownedContainers) {
            $facts = @(& docker.exe inspect --format '{{.Id}}|{{.Name}}|{{index .Config.Labels "nestakada.run"}}' $id 2>$null)
            $expectedId = if ($facts.Count -eq 1 -and $facts[0] -match "\|/$([regex]::Escape($appName))\|") { $appId } else { $databaseId }
            if (
                $LASTEXITCODE -ne 0 -or $facts.Count -ne 1 -or
                [string]$facts[0] -notmatch "^[0-9a-f]{64}\|/($([regex]::Escape($appName))|$([regex]::Escape($databaseName)))\|$runToken`$" -or
                ($expectedId -and [string]$id -cne $expectedId)
            ) { $failed = 'CORE19_CONTAINER_OWNERSHIP_AMBIGUOUS'; continue }
            & docker.exe rm --force $id *> $null
            if ($LASTEXITCODE -ne 0) { $failed = 'CORE19_CONTAINER_CLEANUP_FAILED' }
        }
    }

    $ownedNetworks = @(& docker.exe network ls -q --no-trunc --filter "label=nestakada.scope=$scope" 2>$null)
    if ($LASTEXITCODE -ne 0 -or $ownedNetworks.Count -gt 1) {
        $failed = 'CORE19_NETWORK_OWNERSHIP_AMBIGUOUS'
    }
    elseif ($ownedNetworks.Count -eq 1) {
        $id = [string]$ownedNetworks[0]
        $facts = @(& docker.exe network inspect --format '{{.Id}}|{{.Name}}|{{index .Labels "nestakada.run"}}' $id 2>$null)
        if (
            $LASTEXITCODE -ne 0 -or $facts.Count -ne 1 -or
            [string]$facts[0] -cne "$id|$network|$runToken" -or
            ($networkId -and $id -cne $networkId)
        ) { $failed = 'CORE19_NETWORK_OWNERSHIP_AMBIGUOUS' }
        else {
            & docker.exe network rm $id *> $null
            if ($LASTEXITCODE -ne 0) { $failed = 'CORE19_NETWORK_CLEANUP_FAILED' }
        }
    }

    $ownedVolumes = @(& docker.exe volume ls -q --filter "label=nestakada.scope=$scope" 2>$null)
    if ($LASTEXITCODE -ne 0 -or $ownedVolumes.Count -gt 1) {
        $failed = 'CORE19_VOLUME_OWNERSHIP_AMBIGUOUS'
    }
    elseif ($ownedVolumes.Count -eq 1) {
        $name = [string]$ownedVolumes[0]
        $facts = @(& docker.exe volume inspect --format '{{.Name}}|{{.Driver}}|{{index .Labels "nestakada.run"}}' $name 2>$null)
        if ($LASTEXITCODE -ne 0 -or $facts.Count -ne 1 -or [string]$facts[0] -cne "$volume|local|$runToken") {
            $failed = 'CORE19_VOLUME_OWNERSHIP_AMBIGUOUS'
        }
        else {
            & docker.exe volume rm --force $name *> $null
            if ($LASTEXITCODE -ne 0) { $failed = 'CORE19_VOLUME_CLEANUP_FAILED' }
        }
    }
}

$postAuditClean = $true
try { Assert-CleanScope } catch { $postAuditClean = $false; $failed = 'CORE19_POST_AUDIT_FAILED' }
if ($postAuditClean) {
    Write-Output 'CORE19_ADMIN_CLEANUP_OK containers=0 networks=0 volumes=0 staging=0'
}
if ($null -ne $failed) {
    [Console]::Error.WriteLine("CORE19_RUNTIME_FAILED code=$failed")
    exit 1
}
