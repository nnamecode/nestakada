[CmdletBinding()]
param(
    [switch]$ServicePageMapping,
    [ValidatePattern('^[0-9a-f]{32}$')][string]$RecoverRunId,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$RecoverContainerId,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$RecoverDbId,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$RecoverAppId,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$RecoverIngressId
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$private = Join-Path $repo 'work\foundation\test\private'
$tool = Join-Path $repo $(if ($ServicePageMapping) { 'tools\rebuild7_service_page_mapping_diagnostic.py' } else { 'tools\rebuild7_owner_payload_diagnostic.py' })
$testTool = Join-Path $repo $(if ($ServicePageMapping) { 'tools\test_rebuild7_service_page_mapping_diagnostic.py' } else { 'tools\test_rebuild7_owner_payload_diagnostic.py' })
$toolTarget = if ($ServicePageMapping) { '/tools/rebuild7_service_page_mapping_diagnostic.py' } else { '/tools/rebuild7_owner_payload_diagnostic.py' }
$testToolTarget = if ($ServicePageMapping) { '/tools/test_rebuild7_service_page_mapping_diagnostic.py' } else { '/tools/test_rebuild7_owner_payload_diagnostic.py' }
$harness = Join-Path $repo 'scripts\rebuild7-owner-payload-diagnostic.ps1'
$workRoot = Join-Path $repo 'work\r7-local-001'
$coordinatorLockPath = Join-Path $workRoot 'coordinator.lock'
$dbContainer = 'nestakada-foundation-test-db'
$dbNetwork = 'nestakada-foundation-test-db'
$sourceDatabase = 'estakada_rb5_home_preview'
$previewApp = 'nestakada-rb5-home-app'
$previewIngress = 'nestakada-rb5-home-ingress'
$recoveryValues = @($RecoverRunId, $RecoverContainerId, $RecoverDbId, $RecoverAppId, $RecoverIngressId)
$recoveryRequested = @($recoveryValues | Where-Object { ![string]::IsNullOrEmpty($_) }).Count -gt 0
if ($recoveryRequested -and @($recoveryValues | Where-Object { [string]::IsNullOrEmpty($_) }).Count -ne 0) {
    throw 'R7_OWNER_PAYLOAD_DIAGNOSTIC_UNAVAILABLE'
}
if ($ServicePageMapping -and $recoveryRequested) { throw 'R7_OWNER_PAYLOAD_DIAGNOSTIC_UNAVAILABLE' }
$runId = if ($recoveryRequested) { $RecoverRunId } else { [guid]::NewGuid().ToString('N') }
$testName = "nestakada-r7-payload-tests-$runId"
$readName = "nestakada-r7-payload-read-$runId"
$testId = ''
$readId = ''
$testMayExist = $false
$readMayExist = $false
$appImage = ''
$resultLine = ''
$failed = $false
$runtimeBoundaryReady = $false
$dbId = ''
$appId = ''
$ingressId = ''
$dbWasRunning = $false
$dbStartMayHaveOccurred = $false
$coordinatorLock = $null
$coordinatorLockOwned = $false
$allowedCodes = @(
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_UNAVAILABLE',
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_TESTS_UNAVAILABLE',
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_CLIENTS_OPEN',
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_DATABASE_NOT_READY',
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_BITMAP_UNCERTAIN',
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED',
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN',
    'R7_OWNER_PAYLOAD_DIAGNOSTIC_CLEANUP_UNCERTAIN'
)

function Fail-Diagnostic([string]$Reason = 'R7_OWNER_PAYLOAD_DIAGNOSTIC_UNAVAILABLE') { throw $Reason }

function Normalize-DiagnosticCode([string]$Value) {
    if ($Value -cin $allowedCodes) { return $Value }
    return 'R7_OWNER_PAYLOAD_DIAGNOSTIC_UNAVAILABLE'
}

function Invoke-Docker([string[]]$Arguments) {
    $bounded = Invoke-DockerBounded $Arguments 30000
    $combined = ([string]$bounded.Output) + "`n" + ([string]$bounded.Error)
    if ($bounded.TimedOut -or $bounded.ExitCode -ne 0) {
        $codes = @([regex]::Matches($combined, 'R7_OWNER_PAYLOAD_DIAGNOSTIC_[A-Z0-9_]+'))
        if ($codes.Count -gt 0) { Fail-Diagnostic (Normalize-DiagnosticCode $codes[-1].Value) }
        Fail-Diagnostic
    }
    if ([string]::IsNullOrEmpty([string]$bounded.Output)) { return @() }
    return @([string]$bounded.Output -split '\r?\n')
}

function Invoke-DockerBounded([string[]]$Arguments, [int]$TimeoutMilliseconds) {
    if ($TimeoutMilliseconds -lt 1000 -or $TimeoutMilliseconds -gt 60000) { Fail-Diagnostic }
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = 'docker.exe'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (!$process.Start()) { Fail-Diagnostic }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (!$process.WaitForExit($TimeoutMilliseconds)) {
            try { $process.Kill($true) } catch {}
            try { $process.WaitForExit(5000) | Out-Null } catch {}
            return [pscustomobject]@{ TimedOut = $true; ExitCode = -1; Output = ''; Error = '' }
        }
        $drained = [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout, $stderr), 5000)
        if (!$drained) {
            return [pscustomobject]@{ TimedOut = $true; ExitCode = -1; Output = ''; Error = '' }
        }
        return [pscustomobject]@{
            TimedOut = $false
            ExitCode = [int]$process.ExitCode
            Output = ([string]$stdout.Result).Trim()
            Error = ([string]$stderr.Result).Trim()
        }
    } finally {
        $process.Dispose()
    }
}

function Read-Container([string]$Reference) {
    $rows = @(Invoke-Docker @('inspect', $Reference) | ConvertFrom-Json)
    if ($rows.Count -ne 1) { Fail-Diagnostic }
    return $rows[0]
}

function Assert-Directory([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if (!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-Diagnostic }
}

function Assert-RegularFile([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-Diagnostic }
}

function Assert-SourceClientsZero {
    $rows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT count(*) FROM pg_stat_activity WHERE datname='$sourceDatabase' AND backend_type='client backend'"
    ))
    if ($rows.Count -ne 1 -or ([string]$rows[0]).Trim() -cne '0') {
        Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_CLIENTS_OPEN'
    }
}

function Get-BaseRunningStateBounded([string]$ExpectedId, [string]$ExpectedName) {
    if ($ExpectedId -notmatch '^[0-9a-f]{64}$') { Fail-Diagnostic }
    $result = Invoke-DockerBounded @('inspect', '--format', '{{.Id}}|{{.Name}}|{{.State.Running}}', $ExpectedId) 10000
    if ($result.TimedOut -or $result.ExitCode -ne 0 -or
        [string]$result.Output -notmatch '^(?<id>[0-9a-f]{64})\|/(?<name>[A-Za-z0-9_.-]+)\|(?<running>true|false)$' -or
        [string]$Matches.id -cne $ExpectedId -or [string]$Matches.name -cne $ExpectedName) {
        Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_BITMAP_UNCERTAIN'
    }
    return ([string]$Matches.running -ceq 'true')
}

function Assert-OriginalBitmap {
    if (
        (Get-BaseRunningStateBounded $dbId $dbContainer) -ne $dbWasRunning -or
        (Get-BaseRunningStateBounded $appId $previewApp) -or
        (Get-BaseRunningStateBounded $ingressId $previewIngress)
    ) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_BITMAP_UNCERTAIN' }
}

function Wait-DatabaseReady {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.ElapsedMilliseconds -lt 60000) {
        $probe = Invoke-DockerBounded @('exec', $dbId, 'pg_isready', '-q', '-U', 'postgres') 2000
        if (!$probe.TimedOut -and $probe.ExitCode -eq 0) { return }
        Start-Sleep -Milliseconds 250
    }
    Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_DATABASE_NOT_READY'
}

function Assert-OwnedDiagnosticContainer([string]$Reference, [string]$ExpectedId, [string]$Role) {
    if ($Role -notin @('tests', 'read') -or $ExpectedId -notmatch '^[0-9a-f]{64}$') {
        Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN'
    }
    $item = Read-Container $Reference
    $expectedName = if ($Role -ceq 'tests') { $testName } else { $readName }
    $expectedNetwork = if ($Role -ceq 'tests') { 'none' } else { $dbNetwork }
    $expectedCommand = if ($Role -ceq 'tests') {
        @('-B', $testToolTarget)
    } else {
        @('-B', $toolTarget)
    }
    $expectedMounts = if ($Role -ceq 'tests') {
        [ordered]@{
            '/app' = [IO.Path]::GetFullPath((Join-Path $repo 'src'))
            $toolTarget = [IO.Path]::GetFullPath($tool)
            $testToolTarget = [IO.Path]::GetFullPath($testTool)
            '/tools/rebuild7-owner-payload-diagnostic.ps1' = [IO.Path]::GetFullPath($harness)
        }
    } else {
        [ordered]@{
            '/app' = [IO.Path]::GetFullPath((Join-Path $repo 'src'))
            $toolTarget = [IO.Path]::GetFullPath($tool)
            '/run/secrets/db-password' = [IO.Path]::GetFullPath((Join-Path $private 'migrator-password'))
            '/run/secrets/database-ca' = [IO.Path]::GetFullPath((Join-Path $private 'database-ca'))
        }
    }
    $expectedEnvironment = if ($Role -ceq 'tests') {
        @(
            'PYTHONDONTWRITEBYTECODE=1',
            'PYTHONPATH=/tools:/app',
            'R7_OWNER_PAYLOAD_DIAGNOSTIC_HARNESS=/tools/rebuild7-owner-payload-diagnostic.ps1'
        )
    } else {
        @(
            'PYTHONDONTWRITEBYTECODE=1',
            'PYTHONPATH=/app',
            'DJANGO_SETTINGS_MODULE=config.settings.local_restore',
            'ESTAKADA_LOCAL_RESTORE=1',
            'ESTAKADA_DJANGO_SECRET=r7-owner-payload-read-only',
            'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
            'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000',
            'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
            "ESTAKADA_DB_NAME=$sourceDatabase",
            'ESTAKADA_DB_USER=app_migrator',
            'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password',
            'ESTAKADA_DB_HOST=db',
            'ESTAKADA_DB_PORT=5432',
            'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca'
        )
    }
    $baseExpectedLabels = [ordered]@{
        'estakada.scope' = 'r7-owner-payload-diagnostic'
        'estakada.run' = $runId
        'estakada.role' = $Role
    }
    $desktopExpectedLabels = [ordered]@{
        'estakada.scope' = 'r7-owner-payload-diagnostic'
        'estakada.run' = $runId
        'estakada.role' = $Role
        'desktop.docker.io/ports.scheme' = 'v2'
    }
    $mountIndex = 0
    foreach ($destination in $expectedMounts.Keys) {
        $desktopExpectedLabels["desktop.docker.io/mounts/$mountIndex/Source"] = $expectedMounts[$destination]
        $desktopExpectedLabels["desktop.docker.io/mounts/$mountIndex/SourceKind"] = 'hostFile'
        $desktopExpectedLabels["desktop.docker.io/mounts/$mountIndex/Target"] = $destination
        $mountIndex++
    }
    $labels = @($item.Config.Labels.PSObject.Properties)
    $expectedLabels = $null
    foreach ($candidate in @($baseExpectedLabels, $desktopExpectedLabels)) {
        if ($labels.Count -ne $candidate.Count) { continue }
        $candidateMatches = $true
        foreach ($key in $candidate.Keys) {
            $property = $item.Config.Labels.PSObject.Properties[$key]
            if ($null -eq $property) { $candidateMatches = $false; break }
            if ($key -clike 'desktop.docker.io/mounts/*/Source') {
                if (![string]::Equals(
                    [IO.Path]::GetFullPath([string]$property.Value),
                    [IO.Path]::GetFullPath([string]$candidate[$key]),
                    [StringComparison]::OrdinalIgnoreCase
                )) { $candidateMatches = $false; break }
            } elseif ([string]$property.Value -cne [string]$candidate[$key]) {
                $candidateMatches = $false
                break
            }
        }
        if ($candidateMatches) { $expectedLabels = $candidate; break }
    }
    if ($null -eq $expectedLabels) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN' }
    $tmpfs = @($item.HostConfig.Tmpfs.PSObject.Properties)
    $actualNetworks = @($item.NetworkSettings.Networks.PSObject.Properties)
    $expectedNetworkName = if ($Role -ceq 'tests') { 'none' } else { $dbNetwork }
    if (
        [string]$item.Id -cne $ExpectedId -or [string]$item.Name -cne "/$expectedName" -or
        [string]$item.Image -cne $appImage -or
        [string]$item.Config.Labels.'estakada.scope' -cne 'r7-owner-payload-diagnostic' -or
        [string]$item.Config.Labels.'estakada.run' -cne $runId -or
        [string]$item.Config.Labels.'estakada.role' -cne $Role -or
        [string]$item.Config.User -cne '10001:10001' -or
        (@($item.Config.Entrypoint) | ConvertTo-Json -Compress) -cne (@('python') | ConvertTo-Json -Compress) -or
        (@($item.Config.Cmd) | ConvertTo-Json -Compress) -cne ($expectedCommand | ConvertTo-Json -Compress) -or
        [string]$item.HostConfig.NetworkMode -cne $expectedNetwork -or ![bool]$item.HostConfig.ReadonlyRootfs -or
        [bool]$item.HostConfig.AutoRemove -or [string]$item.HostConfig.RestartPolicy.Name -cne 'no' -or
        @($item.HostConfig.CapDrop).Count -ne 1 -or [string]$item.HostConfig.CapDrop[0] -cne 'ALL' -or
        @($item.HostConfig.SecurityOpt).Count -ne 1 -or [string]$item.HostConfig.SecurityOpt[0] -cne 'no-new-privileges:true' -or
        [long]$item.HostConfig.Memory -ne 268435456L -or [long]$item.HostConfig.NanoCpus -ne 500000000L -or
        [long]$item.HostConfig.PidsLimit -ne 64L -or @($item.HostConfig.PortBindings.PSObject.Properties).Count -ne 0 -or
        @($item.Mounts).Count -ne $expectedMounts.Count -or
        $tmpfs.Count -ne 1 -or [string]$tmpfs[0].Name -cne '/tmp' -or
        [string]$tmpfs[0].Value -cne 'rw,nosuid,nodev,noexec,size=32m,uid=10001,gid=10001,mode=1777' -or
        $actualNetworks.Count -ne 1 -or [string]$actualNetworks[0].Name -cne $expectedNetworkName
    ) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN' }
    foreach ($mount in @($item.Mounts)) {
        if (!$expectedMounts.Contains([string]$mount.Destination) -or [string]$mount.Type -cne 'bind' -or [bool]$mount.RW -or
            ![string]::Equals([IO.Path]::GetFullPath([string]$mount.Source), $expectedMounts[[string]$mount.Destination], [StringComparison]::OrdinalIgnoreCase)) {
            Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN'
        }
    }
    foreach ($expected in $expectedEnvironment) {
        $key = $expected.Split('=', 2)[0]
        $matches = @($item.Config.Env | Where-Object { $_ -clike "$key=*" })
        if ($matches.Count -ne 1 -or [string]$matches[0] -cne $expected) {
            Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN'
        }
    }
    $expectedEstakadaCount = @($expectedEnvironment | Where-Object { $_ -clike 'ESTAKADA_*' }).Count
    if (@($item.Config.Env | Where-Object { $_ -clike 'ESTAKADA_*' }).Count -ne $expectedEstakadaCount) {
        Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN'
    }
    return $item
}

function Remove-OwnedDiagnosticContainer([string]$Role) {
    $mayExist = if ($Role -ceq 'tests') { $testMayExist } else { $readMayExist }
    if (!$mayExist) { return }
    $name = if ($Role -ceq 'tests') { $testName } else { $readName }
    $id = if ($Role -ceq 'tests') { $testId } else { $readId }
    if ($id -notmatch '^[0-9a-f]{64}$') {
        $names = @(Invoke-Docker @('ps', '-a', '--filter', "name=^/$name$", '--format', '{{.Names}}'))
        if ($names.Count -eq 0) {
            if ($Role -ceq 'tests') { $script:testMayExist = $false } else { $script:readMayExist = $false }
            return
        }
        if ($names.Count -ne 1 -or [string]$names[0] -cne $name) {
            Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN'
        }
        $id = [string](Read-Container $name).Id
    }
    Assert-OwnedDiagnosticContainer $id $id $Role | Out-Null
    Invoke-Docker @('rm', '-f', $id) | Out-Null
    if (@(Invoke-Docker @('ps', '-a', '--no-trunc', '--filter', "id=$id", '--format', '{{.ID}}')).Count -ne 0) {
        Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_CLEANUP_UNCERTAIN'
    }
    if ($Role -ceq 'tests') {
        $script:testId = ''
        $script:testMayExist = $false
    } else {
        $script:readId = ''
        $script:readMayExist = $false
    }
}

function New-DiagnosticContainer([string]$Role) {
    $name = if ($Role -ceq 'tests') { $testName } else { $readName }
    $args = @(
        'create', '--name', $name,
        '--label', 'estakada.scope=r7-owner-payload-diagnostic', '--label', "estakada.run=$runId", '--label', "estakada.role=$Role",
        '--network', $(if ($Role -ceq 'tests') { 'none' } else { $dbNetwork }),
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=32m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '256m', '--cpus', '0.5', '--pids-limit', '64',
        '--env', 'PYTHONDONTWRITEBYTECODE=1'
    )
    if ($Role -ceq 'tests') {
        $args += @(
            '--env', 'PYTHONPATH=/tools:/app',
            '--env', 'R7_OWNER_PAYLOAD_DIAGNOSTIC_HARNESS=/tools/rebuild7-owner-payload-diagnostic.ps1',
            '--mount', "type=bind,source=$repo\src,target=/app,readonly",
            '--mount', "type=bind,source=$tool,target=$toolTarget,readonly",
            '--mount', "type=bind,source=$testTool,target=$testToolTarget,readonly",
            '--mount', "type=bind,source=$harness,target=/tools/rebuild7-owner-payload-diagnostic.ps1,readonly",
            '--entrypoint', 'python', $appImage, '-B', $testToolTarget
        )
        $script:testMayExist = $true
    } else {
        $args += @(
            '--env', 'PYTHONPATH=/app', '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore',
            '--env', 'ESTAKADA_LOCAL_RESTORE=1', '--env', 'ESTAKADA_DJANGO_SECRET=r7-owner-payload-read-only',
            '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
            '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000', '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
            '--env', "ESTAKADA_DB_NAME=$sourceDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator',
            '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password', '--env', 'ESTAKADA_DB_HOST=db',
            '--env', 'ESTAKADA_DB_PORT=5432', '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
            '--mount', "type=bind,source=$repo\src,target=/app,readonly",
            '--mount', "type=bind,source=$tool,target=$toolTarget,readonly",
            '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
            '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
            '--entrypoint', 'python', $appImage, '-B', $toolTarget
        )
        $script:readMayExist = $true
    }
    $ids = @(Invoke-Docker $args)
    if ($ids.Count -ne 1 -or [string]$ids[0] -notmatch '^[0-9a-f]{64}$') { Fail-Diagnostic }
    if ($Role -ceq 'tests') { $script:testId = [string]$ids[0] } else { $script:readId = [string]$ids[0] }
    Assert-OwnedDiagnosticContainer ([string]$ids[0]) ([string]$ids[0]) $Role | Out-Null
}

function Invoke-RetainedRecovery {
    try {
        $workParent = Join-Path $repo 'work'
        foreach ($path in @($repo, $workParent, $workRoot)) { Assert-Directory $path }
        $repoFull = [IO.Path]::GetFullPath($repo).TrimEnd([IO.Path]::DirectorySeparatorChar)
        $workParentFull = [IO.Path]::GetFullPath($workParent)
        $workRootFull = [IO.Path]::GetFullPath($workRoot)
        $lockFull = [IO.Path]::GetFullPath($coordinatorLockPath)
        if (
            !$workParentFull.StartsWith($repoFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
            !$workRootFull.StartsWith($workParentFull.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
            ![string]::Equals([IO.Path]::GetDirectoryName($lockFull), $workRootFull, [StringComparison]::OrdinalIgnoreCase)
        ) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED' }
        $lockItem = Get-Item -Force -LiteralPath $coordinatorLockPath
        if (
            $lockItem.PSIsContainer -or
            ($lockItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            [IO.Path]::GetFullPath([string]$lockItem.DirectoryName) -cne [IO.Path]::GetFullPath($workRoot) -or
            [long]$lockItem.Length -ne 33
        ) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED' }
        try {
            $script:coordinatorLock = [IO.File]::Open(
                $coordinatorLockPath,
                [IO.FileMode]::Open,
                [IO.FileAccess]::ReadWrite,
                [IO.FileShare]::None
            )
        } catch { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED' }
        $script:coordinatorLockOwned = $true
        $buffer = [byte[]]::new(33)
        $offset = 0
        while ($offset -lt $buffer.Length) {
            $read = $coordinatorLock.Read($buffer, $offset, $buffer.Length - $offset)
            if ($read -lt 1) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED' }
            $offset += $read
        }
        if ([Text.Encoding]::ASCII.GetString($buffer) -cne "$runId`n" -or $coordinatorLock.ReadByte() -ne -1) {
            Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED'
        }

        $db = Read-Container $dbContainer
        $app = Read-Container $previewApp
        $ingress = Read-Container $previewIngress
        $script:dbId = [string]$db.Id
        $script:appId = [string]$app.Id
        $script:ingressId = [string]$ingress.Id
        $script:appImage = [string]$app.Image
        $script:dbWasRunning = $false
        if (
            $dbId -cne $RecoverDbId -or [string]$db.Name -cne "/$dbContainer" -or [bool]$db.State.Running -or
            $appId -cne $RecoverAppId -or [string]$app.Name -cne "/$previewApp" -or [bool]$app.State.Running -or
            $ingressId -cne $RecoverIngressId -or [string]$ingress.Name -cne "/$previewIngress" -or [bool]$ingress.State.Running -or
            $appImage -notmatch '^sha256:[0-9a-f]{64}$'
        ) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_BITMAP_UNCERTAIN' }

        if (@(Invoke-Docker @('ps', '-a', '--filter', "name=^/$readName$", '--format', '{{.Names}}')).Count -ne 0) {
            Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN'
        }
        $script:testId = $RecoverContainerId
        $script:testMayExist = $true
        $retained = Assert-OwnedDiagnosticContainer $testId $testId 'tests'
        if ([bool]$retained.State.Running -or [string]$retained.State.Status -cne 'created') {
            Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_OWNERSHIP_UNCERTAIN'
        }
        Remove-OwnedDiagnosticContainer 'tests'
        $leftovers = @(Invoke-Docker @(
            'ps', '-a', '--filter', "label=estakada.scope=r7-owner-payload-diagnostic",
            '--filter', "label=estakada.run=$runId", '--format', '{{.ID}}'
        ))
        if ($leftovers.Count -ne 0) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_CLEANUP_UNCERTAIN' }
        Assert-OriginalBitmap

        $coordinatorLock.Dispose()
        $script:coordinatorLock = $null
        $postLock = Get-Item -Force -LiteralPath $coordinatorLockPath
        if (
            $postLock.PSIsContainer -or
            ($postLock.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            [IO.Path]::GetFullPath([string]$postLock.DirectoryName) -cne [IO.Path]::GetFullPath($workRoot) -or
            [IO.File]::ReadAllText($coordinatorLockPath, [Text.Encoding]::ASCII) -cne "$runId`n"
        ) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED' }
        Remove-Item -Force -LiteralPath $coordinatorLockPath
        $script:coordinatorLockOwned = $false
        Write-Output 'R7_OWNER_PAYLOAD_DIAGNOSTIC_RECOVERY_PASS container=0 lock=0 bitmap=exact query=0'
    } catch {
        if ($null -ne $coordinatorLock) {
            try { $coordinatorLock.Dispose() } catch {}
            $script:coordinatorLock = $null
        }
        throw (Normalize-DiagnosticCode ([string]$_.Exception.Message))
    }
}

if ($recoveryRequested) {
    Invoke-RetainedRecovery
    exit 0
}

try {
    foreach ($path in @($repo, $private, $workRoot, (Join-Path $repo 'src'))) { Assert-Directory $path }
    foreach ($path in @($tool, $testTool, $harness, (Join-Path $private 'migrator-password'), (Join-Path $private 'database-ca'))) { Assert-RegularFile $path }
    if (!(Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) { Fail-Diagnostic }
    if (Test-Path -LiteralPath $coordinatorLockPath) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED' }
    try {
        $coordinatorLock = [IO.File]::Open(
            $coordinatorLockPath,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::ReadWrite,
            [IO.FileShare]::None
        )
    } catch { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_COORDINATOR_LOCKED' }
    $coordinatorLockOwned = $true
    $lockBytes = [Text.Encoding]::ASCII.GetBytes("$runId`n")
    $coordinatorLock.Write($lockBytes, 0, $lockBytes.Length)
    $coordinatorLock.Flush($true)
    $db = Read-Container $dbContainer
    $dbId = [string]$db.Id
    $dbWasRunning = [bool]$db.State.Running
    if ($dbId -notmatch '^[0-9a-f]{64}$' -or $dbWasRunning -or [string]$db.Name -cne "/$dbContainer" -or
        $db.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $dbNetwork) { Fail-Diagnostic }
    $networks = @(Invoke-Docker @('network', 'inspect', $dbNetwork) | ConvertFrom-Json)
    if ($networks.Count -ne 1 -or ![bool]$networks[0].Internal) { Fail-Diagnostic }
    $app = Read-Container $previewApp
    $appId = [string]$app.Id
    $appImage = [string]$app.Image
    if ($appId -notmatch '^[0-9a-f]{64}$' -or [string]$app.Name -cne "/$previewApp" -or
        [bool]$app.State.Running -or $appImage -notmatch '^sha256:[0-9a-f]{64}$' -or
        $app.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $dbNetwork) { Fail-Diagnostic }
    $ingress = Read-Container $previewIngress
    $ingressId = [string]$ingress.Id
    if ($ingressId -notmatch '^[0-9a-f]{64}$' -or [string]$ingress.Name -cne "/$previewIngress" -or
        [bool]$ingress.State.Running) { Fail-Diagnostic }
    foreach ($name in @($testName, $readName)) {
        if (@(Invoke-Docker @('ps', '-a', '--filter', "name=^/$name$", '--format', '{{.Names}}')).Count -ne 0) { Fail-Diagnostic }
    }
    $runtimeBoundaryReady = $true
    $dbStartMayHaveOccurred = $true
    $startResult = Invoke-DockerBounded @('start', $dbId) 30000
    if ($startResult.TimedOut -or $startResult.ExitCode -ne 0) {
        if (!(Get-BaseRunningStateBounded $dbId $dbContainer)) {
            Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_DATABASE_NOT_READY'
        }
    }
    Wait-DatabaseReady
    if (!(Get-BaseRunningStateBounded $dbId $dbContainer)) { Fail-Diagnostic 'R7_OWNER_PAYLOAD_DIAGNOSTIC_DATABASE_NOT_READY' }
    Assert-SourceClientsZero

    New-DiagnosticContainer 'tests'
    $testOutput = @(Invoke-Docker @('start', '--attach', $testId))
    $testState = Assert-OwnedDiagnosticContainer $testId $testId 'tests'
    $expectedTestOutput = if ($ServicePageMapping) {
        'R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_TESTS_OK cases=5'
    } else {
        'R7_OWNER_PAYLOAD_DIAGNOSTIC_TESTS_OK cases=6'
    }
    if ([bool]$testState.State.Running -or [int]$testState.State.ExitCode -ne 0 -or $testOutput.Count -ne 1 -or
        [string]$testOutput[0] -cne $expectedTestOutput) { Fail-Diagnostic }
    Remove-OwnedDiagnosticContainer 'tests'
    Assert-SourceClientsZero

    New-DiagnosticContainer 'read'
    $output = @(Invoke-Docker @('start', '--attach', $readId))
    $readState = Assert-OwnedDiagnosticContainer $readId $readId 'read'
    if ([bool]$readState.State.Running -or [int]$readState.State.ExitCode -ne 0 -or $output.Count -ne 1) { Fail-Diagnostic }
    if ($ServicePageMapping) {
        if ([string]$output[0] -notmatch '^\{.*\}$') { Fail-Diagnostic }
        $safe = [string]$output[0] | ConvertFrom-Json
        if (@($safe.PSObject.Properties).Count -ne 2 -or $safe.schema -cne 'estakada.r7-service-page-mapping-diagnostic-v1') { Fail-Diagnostic }
        $allowedMaps = @('MAP-010','MAP-011','MAP-013','MAP-015','MAP-016','MAP-019','MAP-020','MAP-021','MAP-022','MAP-023','MAP-024','MAP-025','MAP-026','MAP-027','MAP-028','MAP-029','MAP-030','MAP-032','MAP-034','MAP-035','MAP-038','MAP-040','MAP-041','MAP-042','MAP-046','MAP-047','MAP-050','MAP-051','MAP-052','MAP-054','MAP-055','MAP-058','MAP-059','MAP-060','MAP-062','MAP-063','MAP-064','MAP-066','MAP-067','MAP-068','MAP-069','MAP-073','MAP-074','MAP-075','MAP-079','MAP-080','MAP-083','MAP-084','MAP-085','MAP-089','MAP-091','MAP-094','MAP-095','MAP-098','MAP-101','MAP-104','MAP-107','MAP-115')
        $mappings = @($safe.mappings)
        if ($mappings.Count -ne 58) { Fail-Diagnostic }
        $seenMaps = @{}
        $seenPages = @{}
        foreach ($mapping in $mappings) {
            if (@($mapping.PSObject.Properties).Count -ne 2 -or $mapping.map -notin $allowedMaps -or
                [string]$mapping.page_id -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' -or
                $seenMaps.ContainsKey([string]$mapping.map) -or $seenPages.ContainsKey([string]$mapping.page_id)) { Fail-Diagnostic }
            $seenMaps[[string]$mapping.map] = $true
            $seenPages[[string]$mapping.page_id] = $true
        }
        if (@($allowedMaps | Where-Object { !$seenMaps.ContainsKey($_) }).Count -ne 0) { Fail-Diagnostic }
        $resultLine = "R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_OK $([string]$output[0])"
    } else {
        if ([string]$output[0] -notmatch '^R7_OWNER_PAYLOAD_DIAGNOSTIC_OK (?<json>\{.*\})$') { Fail-Diagnostic }
        $safe = $Matches.json | ConvertFrom-Json
        if (@($safe.PSObject.Properties).Count -ne 2 -or $safe.schema -cne 'estakada.r7-owner-payload-diagnostic-v1') { Fail-Diagnostic }
        $allowedMaps = @('MAP-010','MAP-011','MAP-013','MAP-015','MAP-016','MAP-019','MAP-020','MAP-021','MAP-022','MAP-023','MAP-024','MAP-025','MAP-026','MAP-027','MAP-028','MAP-029','MAP-030','MAP-032','MAP-034','MAP-035','MAP-038','MAP-040','MAP-041','MAP-042','MAP-046','MAP-047','MAP-050','MAP-051','MAP-052','MAP-054','MAP-055','MAP-058','MAP-059','MAP-060','MAP-062','MAP-063','MAP-064','MAP-066','MAP-067','MAP-068','MAP-069','MAP-073','MAP-074','MAP-075','MAP-079','MAP-080','MAP-083','MAP-084','MAP-085','MAP-089','MAP-091','MAP-094','MAP-095','MAP-098','MAP-101','MAP-104','MAP-107','MAP-115')
        $allowedCategories = @('PAYLOAD_SHAPE','HERO_TARGET','HERO_OTHER','MAP019_HERO_NULL','MAP019_HERO_TARGET','MAP019_HERO_OTHER','MAP019_BODY_NONEMPTY')
        $mismatches = @($safe.mismatches)
        if ($mismatches.Count -lt 1 -or $mismatches.Count -gt 58) { Fail-Diagnostic }
        $seen = @{}
        foreach ($mismatch in $mismatches) {
            if (@($mismatch.PSObject.Properties).Count -ne 2 -or $mismatch.map -notin $allowedMaps -or
                $mismatch.category -notin $allowedCategories -or $seen.ContainsKey([string]$mismatch.map)) { Fail-Diagnostic }
            $seen[[string]$mismatch.map] = $true
        }
        $resultLine = [string]$output[0]
    }
    Remove-OwnedDiagnosticContainer 'read'
    Assert-SourceClientsZero
}
catch {
    $failed = $true
    $reason = Normalize-DiagnosticCode ([string]$_.Exception.Message)
    Write-Error $reason -ErrorAction Continue
}
finally {
    $cleanupFailures = [Collections.Generic.List[string]]::new()
    if ($runtimeBoundaryReady) {
        if ($testMayExist) { try { Remove-OwnedDiagnosticContainer 'tests' } catch { $cleanupFailures.Add('tests') } }
        if ($readMayExist) { try { Remove-OwnedDiagnosticContainer 'read' } catch { $cleanupFailures.Add('read') } }
        try { Assert-SourceClientsZero } catch { $cleanupFailures.Add('clients') }
        if ($dbStartMayHaveOccurred) {
            try {
                if (Get-BaseRunningStateBounded $dbId $dbContainer) {
                    $stopResult = Invoke-DockerBounded @('stop', '--time', '10', $dbId) 30000
                    if (($stopResult.TimedOut -or $stopResult.ExitCode -ne 0) -and
                        (Get-BaseRunningStateBounded $dbId $dbContainer)) {
                        throw 'database-stop'
                    }
                }
                if (Get-BaseRunningStateBounded $dbId $dbContainer) { throw 'database-running' }
                $dbStartMayHaveOccurred = $false
            } catch { $cleanupFailures.Add('database') }
        }
        try { Assert-OriginalBitmap } catch { $cleanupFailures.Add('bitmap') }
        try {
            $leftovers = @(Invoke-Docker @('ps', '-a', '--filter', "label=estakada.scope=r7-owner-payload-diagnostic", '--filter', "label=estakada.run=$runId", '--format', '{{.Names}}'))
            if ($leftovers.Count -ne 0) { throw 'leftovers' }
        } catch { $cleanupFailures.Add('post-audit') }
    }
    if ($coordinatorLockOwned) {
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
                    [IO.Path]::GetFullPath([string]$lockItem.DirectoryName) -cne [IO.Path]::GetFullPath($workRoot) -or
                    [IO.File]::ReadAllText($coordinatorLockPath, [Text.Encoding]::ASCII) -cne "$runId`n"
                ) { throw 'lock-path' }
                Remove-Item -Force -LiteralPath $coordinatorLockPath
                $coordinatorLockOwned = $false
            } catch { $cleanupFailures.Add('lock-path') }
        }
    }
    if ($cleanupFailures.Count -eq 0 -and $runtimeBoundaryReady) {
        if ($ServicePageMapping) {
            Write-Output 'R7_SERVICE_PAGE_MAPPING_DIAGNOSTIC_CLEANUP_PASS containers=0 clients=0 bitmap=exact'
        } else {
            Write-Output 'R7_OWNER_PAYLOAD_DIAGNOSTIC_CLEANUP_PASS containers=0 clients=0 bitmap=exact'
        }
    }
    if ($cleanupFailures.Count -ne 0) { throw 'R7_OWNER_PAYLOAD_DIAGNOSTIC_CLEANUP_UNCERTAIN' }
}

if ($failed) { exit 1 }
Write-Output $resultLine
