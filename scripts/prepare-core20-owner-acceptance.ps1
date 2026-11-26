#requires -Version 7.0

[CmdletBinding()]
param(
    [switch]$RecoverStoppedSource,
    [switch]$RecoverGenerationDiagnostic,
    [switch]$DisposableCloneRemediation
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$private = Join-Path $repo 'work\foundation\test\private'
$workRoot = Join-Path $repo 'work\core20-owner-acceptance'
$stagingRoot = Join-Path $workRoot 'staging'
$lockPath = Join-Path $workRoot 'coordinator.lock'
$failureArchiveRoot = Join-Path $workRoot 'failures'
$dbContainer = 'nestakada-foundation-test-db'
$dbNetwork = 'nestakada-foundation-test-db'
$sourceDatabase = 'estakada_rb5_home_preview'
$previewApp = 'nestakada-rb5-home-app'
$previewIngress = 'nestakada-rb5-home-ingress'
$expectedDbId = '07558e4e011eb12b51e5586728dbf8cd2fc6752b973086e42295224fa843fd8a'
$expectedAppId = '97e4acd16621174049f2b2d62c0ec4d4f90cd8b9e2d6af5208430f75c49e04cd'
$expectedIngressId = '426c369b671ea4461dd67686f7caa57f560e673853a7fe45c72bdf8981d78f4c'
$expectedDbImage = 'sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7'
$expectedAppImage = 'sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986'
$expectedIngressImage = 'sha256:a3b293bbab17bfd78d82d2392240d3d351501fba538ab82de1595b1d28d0d646'
$expectedDiagnosticFailureRun = 'c1daa7f3-3183-4148-8ae4-fbdf9ed81a9b'
$expectedDiagnosticParentRun = 'ff2bbccc-5cf8-4240-8f22-f5bbc872893b'
$expectedDiagnosticGrandparentRun = '52f82993-3046-4844-a449-92d477d771b0'
$expectedCloneParityFailureRun = '900b20e3-f443-428e-8c69-073937f26307'
$expectedCloneIdentityFailureRun = 'daeb6054-14ed-432b-9399-4245c002d382'
$expectedCloneReadinessFailureRun = '7b4b9c8f-22ef-4f85-ba31-95089fdb568b'
$expectedCloneIngressFailureRun = '64740252-d287-457d-85e6-0ae3fbd4a364'
$expectedCloneHostTransportFailureRun = 'd40d43cd-cd66-4b70-bc62-ba4812731443'
$expectedCloneBrowserFailureRun = '32aefdbf-50db-45fe-8086-75d588b99496'
$expectedClonePolicyFailureRun = '8a775d4f-693a-41cf-9627-763e36f52261'
$expectedCloneStoppedDbFailureRun = '3edf38fc-bd3c-4619-9b10-c59f46cd06c9'
$runId = [guid]::NewGuid().ToString('D').ToLowerInvariant()
$runToken = $runId.Replace('-', '')
$staging = Join-Path $stagingRoot $runToken
$preCapture = Join-Path $staging 'pre'
$postCapture = Join-Path $staging 'post'
$sourceGuardPrePath = Join-Path $staging 'source-pre'
$sourceGuardPostPath = Join-Path $staging 'source-post'
$processRoot = Join-Path $staging 'process'
$preCaptureContainer = "nestakada-core20-pre-$runToken"
$postCaptureContainer = "nestakada-core20-post-$runToken"
$sourceGuardPreContainer = "nestakada-core20-source-pre-$runToken"
$sourceGuardPostContainer = "nestakada-core20-source-post-$runToken"
$cloneMigrationContainer = "nestakada-core20-migrate-$runToken"
$cloneDatabase = "estakada_core20_$runToken"
$cloneApp = "nestakada-core20-app-$runToken"
$cloneIngress = "nestakada-core20-ingress-$runToken"
$cloneAppAlias = "core20-app-$runToken"
$previewNetwork = "nestakada-core20-preview-$runToken"
$cloneNginxConfig = Join-Path $staging 'nginx.conf'
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$evidenceParent = [IO.Path]::GetFullPath((Join-Path $tempRoot 'estakada-core20-owner-acceptance'))
$evidence = [IO.Path]::GetFullPath((Join-Path $evidenceParent $runId))
$session = "core20-$runToken"
$lock = $null
$lockOwned = $false
$lockMarkerCommitted = $false
$boundaryAdmitted = $false
$recoveredFailureRun = ''
$recoveryNeedsDbStart = $false
$dbStartedByRecovery = $false
$browserOpened = $false
$appStarted = $false
$ingressStarted = $false
$walkthroughComplete = $false
$evidencePrepared = $false
$evidenceComplete = $false
$failure = $null
$cleanupErrors = [Collections.Generic.List[string]]::new()
$screenshots = [Collections.Generic.List[object]]::new()
$preProjection = $null
$postProjection = $null
$sourceGuardPre = $null
$sourceGuardPost = $null
$cloneDatabaseCreated = $false
$cloneDatabaseOid = ''
$cloneAppStarted = $false
$cloneIngressStarted = $false
$cloneMigrationId = ''
$cloneAppId = ''
$cloneIngressId = ''
$previewNetworkId = ''
$previewNetworkCreated = $false
$previewNetworkStaticSha = ''
$previewNetworkReceiptSha = ''
$dbNetworkId = ''
$appConfigSha = ''
$ingressConfigSha = ''
$postAppConfigSha = ''
$postIngressConfigSha = ''
$cloneAppConfigSha = ''
$cloneIngressConfigSha = ''
$cloneNginxConfigSha = ''
$preNetworkProjectionSha = ''
$postNetworkProjectionSha = ''
$readinessPassed = $false
$preClients = $false
$postClients = $false
$preResourceAudit = $null
$postResourceAudit = $null
$browserDeadline = [long]0
$browserSessionPid = 0
$node = 'C:\Program Files\nodejs\node.exe'
$playwrightCli = 'C:\Users\nname\AppData\Local\npm-cache\_npx\31e32ef8478fbf80\node_modules\@playwright\cli\playwright-cli.js'
$playwrightPackage = 'C:\Users\nname\AppData\Local\npm-cache\_npx\31e32ef8478fbf80\node_modules\@playwright\cli\package.json'
$playwrightLock = 'C:\Users\nname\AppData\Local\npm-cache\_npx\31e32ef8478fbf80\package-lock.json'
$playwrightModulesLock = 'C:\Users\nname\AppData\Local\npm-cache\_npx\31e32ef8478fbf80\node_modules\.package-lock.json'
$processWrapper = Join-Path $repo 'tools\core20_bounded_process.js'
$docker = 'C:\Users\nname\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
$taskkill = 'C:\Windows\System32\taskkill.exe'

function Fail-Core20([string]$Code = 'CORE20_OWNER_ACCEPTANCE_UNAVAILABLE') { throw $Code }

function New-MonotonicDeadline([int]$Milliseconds) {
    return [Diagnostics.Stopwatch]::GetTimestamp() + [long]([double]$Milliseconds * [Diagnostics.Stopwatch]::Frequency / 1000.0)
}

function Get-MonotonicRemainingMilliseconds([long]$Deadline) {
    $ticks = $Deadline - [Diagnostics.Stopwatch]::GetTimestamp()
    if ($ticks -le 0) { return 0 }
    return [int][Math]::Min([int]::MaxValue, [Math]::Floor([double]$ticks * 1000.0 / [Diagnostics.Stopwatch]::Frequency))
}

function Assert-PinnedFile([string]$Path, [string]$Sha256) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $current = $root.TrimEnd('\') + '\'
    foreach ($part in @([IO.Path]::GetDirectoryName($full).Substring($root.Length) -split '\\' | Where-Object { $_ })) {
        $current = Join-Path $current $part
        $directory = Get-Item -Force -LiteralPath $current
        if (!$directory.PSIsContainer -or ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Fail-Core20 'CORE20_TOOL_PROVENANCE_INVALID'
        }
    }
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Sha256) {
        Fail-Core20 'CORE20_TOOL_PROVENANCE_INVALID'
    }
}

function Assert-RegularFile([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-Core20 'CORE20_PATH_INVALID' }
}

function Assert-ExactAsciiFile([string]$Path, [string]$Expected, [string]$Code) {
    if (!(Test-Path -LiteralPath $Path)) { Fail-Core20 $Code }
    Assert-RegularFile $Path
    $expectedBytes = [Text.Encoding]::ASCII.GetBytes($Expected)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($stream.Length -ne $expectedBytes.Length) { Fail-Core20 $Code }
        $actualBytes = [byte[]]::new($expectedBytes.Length)
        $read = $stream.Read($actualBytes, 0, $actualBytes.Length)
        if ($read -ne $actualBytes.Length) { Fail-Core20 $Code }
        for ($index = 0; $index -lt $expectedBytes.Length; $index++) {
            if ($actualBytes[$index] -ne $expectedBytes[$index]) { Fail-Core20 $Code }
        }
    } finally { $stream.Dispose() }
}

function Assert-PinnedTree([string]$Root, [int]$ExpectedFiles, [string]$ExpectedSha256) {
    Assert-PlainDirectory $Root
    $lines = [Collections.Generic.List[string]]::new()
    $descendants = @(Get-ChildItem -Force -Recurse -LiteralPath $Root)
    if (@($descendants | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count -ne 0) {
        Fail-Core20 'CORE20_TOOL_PROVENANCE_INVALID'
    }
    foreach ($item in @($descendants | Where-Object { !$_.PSIsContainer } | Sort-Object FullName)) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail-Core20 'CORE20_TOOL_PROVENANCE_INVALID' }
        $relative = $item.FullName.Substring($Root.Length + 1).Replace('\', '/')
        $sha = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $lines.Add("$relative|$($item.Length)|$sha")
    }
    if ($lines.Count -ne $ExpectedFiles -or (Get-Sha256Text ($lines -join "`n")) -cne $ExpectedSha256) {
        Fail-Core20 'CORE20_TOOL_PROVENANCE_INVALID'
    }
}

function Invoke-BoundedProcess([string]$File, [string[]]$Arguments, [int]$TimeoutMs, [int]$MaxOutputBytes = 1048576) {
    if (!(Test-Path -LiteralPath $processRoot)) { Fail-Core20 'CORE20_PROCESS_ROOT_UNAVAILABLE' }
    $requestId = [guid]::NewGuid().ToString('N')
    $requestPath = Join-Path $processRoot "$requestId.json"
    $request = [ordered]@{
        schema = 'estakada.core20-process-request-v1'; file = $File; args = @($Arguments)
        timeoutMs = $TimeoutMs; maxOutputBytes = $MaxOutputBytes; taskkill = $taskkill
    }
    [IO.File]::WriteAllText($requestPath, ($request | ConvertTo-Json -Depth 5 -Compress), (New-Object Text.UTF8Encoding($false)))
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $node
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.ArgumentList.Add($processWrapper)
    $startInfo.ArgumentList.Add($requestPath)
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (!$process.Start()) { Fail-Core20 'CORE20_PROCESS_START_FAILED' }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (!$process.WaitForExit($TimeoutMs + 15000)) {
            try { $process.Kill($true) } catch {}
            $process.WaitForExit()
            Fail-Core20 'CORE20_PROCESS_WRAPPER_TIMEOUT'
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0 -or $stderr.Length -ne 0 -or [Text.Encoding]::UTF8.GetByteCount($stdout) -gt 3145728) {
            Fail-Core20 'CORE20_PROCESS_WRAPPER_FAILED'
        }
        $result = $stdout | ConvertFrom-Json
        if ($result.schema -cne 'estakada.core20-process-v1' -or $result.timedOut -or $result.overflow -or
            $null -ne $result.spawnError -or $null -eq $result.exitCode) { Fail-Core20 'CORE20_PROCESS_FAILED' }
        return $result
    }
    finally {
        $process.Dispose()
        if (Test-Path -LiteralPath $requestPath) { Remove-Item -LiteralPath $requestPath -Force }
    }
}

function Invoke-Docker([string[]]$Arguments, [int]$TimeoutMs = 60000) {
    $result = Invoke-BoundedProcess $docker $Arguments $TimeoutMs
    if ([int]$result.exitCode -ne 0 -or [string]$result.stderr -ne '') {
        $safeCodes = @([regex]::Matches("$($result.stdout)`n$($result.stderr)", '(?:CORE20|R7)_[A-Z0-9_]+'))
        if ($safeCodes.Count -gt 0) {
            $code = $safeCodes[-1].Value
            if ($code.StartsWith('R7_')) { $code = "CORE20_CAPTURE_$code" }
            Fail-Core20 $code
        }
        Fail-Core20
    }
    return @(([string]$result.stdout -split "`r?`n") | Where-Object { $_ -ne '' })
}

function Read-Container([string]$Name) {
    $items = @(Invoke-Docker @('inspect', $Name) | ConvertFrom-Json)
    if ($items.Count -ne 1) { Fail-Core20 }
    return $items[0]
}

function Get-Sha256Text([string]$Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([Convert]::ToHexString($sha.ComputeHash($bytes))).ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Assert-PlainDirectory([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if (!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-Core20 'CORE20_PATH_INVALID' }
}

function Assert-Contained([string]$Root, [string]$Target, [bool]$Children = $false) {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $targetFull = [IO.Path]::GetFullPath($Target).TrimEnd('\')
    if (!$targetFull.StartsWith($rootFull + '\', [StringComparison]::OrdinalIgnoreCase)) { Fail-Core20 'CORE20_PATH_INVALID' }
    Assert-PlainDirectory $rootFull
    $current = $rootFull
    foreach ($part in @($targetFull.Substring($rootFull.Length).TrimStart('\') -split '\\' | Where-Object { $_ })) {
        $current = Join-Path $current $part
        Assert-PlainDirectory $current
    }
    if ($Children) {
        foreach ($item in @(Get-ChildItem -Force -Recurse -LiteralPath $targetFull)) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
                ![IO.Path]::GetFullPath($item.FullName).StartsWith($targetFull + '\', [StringComparison]::OrdinalIgnoreCase)) {
                Fail-Core20 'CORE20_PATH_INVALID'
            }
        }
    }
}

function Remove-ExactRunDirectory([string]$Root, [string]$Path, [string]$NamePattern) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    $pathFull = [IO.Path]::GetFullPath($Path)
    if ([IO.Path]::GetDirectoryName($pathFull) -cne $rootFull -or [IO.Path]::GetFileName($pathFull) -notmatch $NamePattern) {
        Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID'
    }
    if (Test-Path -LiteralPath $pathFull) {
        Assert-Contained $rootFull $pathFull $true
        Remove-Item -LiteralPath $pathFull -Recurse -Force
    }
}

function Assert-ZeroClients([string]$Database = $sourceDatabase) {
    if ($Database -cne $sourceDatabase -and $Database -cne $cloneDatabase) { Fail-Core20 'CORE20_DATABASE_SCOPE_INVALID' }
    $rows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-tAc',
        "SELECT count(*) FROM pg_stat_activity WHERE datname='$Database' AND backend_type='client backend'"
    ))
    if ($rows.Count -ne 1 -or ([string]$rows[0]).Trim() -cne '0') { Fail-Core20 'CORE20_DATABASE_CLIENTS_OPEN' }
}

function Wait-ZeroClients([string]$Database = $sourceDatabase, [int]$TimeoutSeconds = 30) {
    $deadline = New-MonotonicDeadline ($TimeoutSeconds * 1000)
    do {
        try { Assert-ZeroClients $Database; return }
        catch {
            if ((Get-MonotonicRemainingMilliseconds $deadline) -le 0) { throw }
            Start-Sleep -Milliseconds 250
        }
    } while ($true)
}

function Get-ResourceAudit {
    $containers = @(
        @(Invoke-Docker @('ps', '-a', '--filter', 'name=nestakada-core20-', '--format', '{{.ID}}')) +
        @(Invoke-Docker @('ps', '-a', '--filter', 'label=estakada.scope=core20-disposable-clone', '--format', '{{.ID}}')) |
        Sort-Object -Unique
    )
    $networks = @(
        @(Invoke-Docker @('network', 'ls', '--filter', 'name=nestakada-core20-', '--format', '{{.ID}}')) +
        @(Invoke-Docker @('network', 'ls', '--filter', 'label=estakada.scope=core20-disposable-clone', '--format', '{{.ID}}')) |
        Sort-Object -Unique
    )
    $volumes = @(Invoke-Docker @('volume', 'ls', '--filter', 'name=nestakada-core20-', '--format', '{{.Name}}'))
    $databases = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT datname FROM pg_database WHERE datname ~ '^estakada_core20_[0-9a-f]{32}$' ORDER BY datname"
    ))
    $databaseOperations = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT count(*) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND query LIKE '%$cloneDatabase%'"
    ))
    if ($databaseOperations.Count -ne 1 -or ([string]$databaseOperations[0]).Trim() -notmatch '^[0-9]+$') { Fail-Core20 'CORE20_RESOURCE_AUDIT_UNAVAILABLE' }
    return [ordered]@{ containers = $containers.Count; networks = $networks.Count; volumes = $volumes.Count; databases = $databases.Count; databaseOperations = [int]([string]$databaseOperations[0]).Trim() }
}

function Assert-ZeroResourceAudit([object]$Audit) {
    if ([int]$Audit.containers -ne 0 -or [int]$Audit.networks -ne 0 -or [int]$Audit.volumes -ne 0 -or [int]$Audit.databases -ne 0 -or [int]$Audit.databaseOperations -ne 0) {
        Fail-Core20 'CORE20_RESOURCE_COLLISION'
    }
}

function Wait-ZeroResourceAuditStable([int]$StableMilliseconds = 10000) {
    $deadline = New-MonotonicDeadline ($StableMilliseconds + 5000)
    $stableSince = [Diagnostics.Stopwatch]::GetTimestamp()
    while ((Get-MonotonicRemainingMilliseconds $deadline) -gt 0) {
        $audit = Get-ResourceAudit
        Assert-ZeroResourceAudit $audit
        $stableElapsed = [long](([Diagnostics.Stopwatch]::GetTimestamp() - $stableSince) * 1000.0 / [Diagnostics.Stopwatch]::Frequency)
        if ($stableElapsed -ge $StableMilliseconds) { return $audit }
        Start-Sleep -Milliseconds 250
    }
    Fail-Core20 'CORE20_RESOURCE_QUIESCENCE_UNCERTAIN'
}

function Get-NetworkProjectionSha {
    $rows = @(Invoke-Docker @('network', 'inspect', $dbNetwork) | ConvertFrom-Json)
    if ($rows.Count -ne 1 -or ![bool]$rows[0].Internal) { Fail-Core20 'CORE20_NETWORK_INVALID' }
    $members = @($rows[0].Containers.PSObject.Properties | ForEach-Object {
        [ordered]@{ id = [string]$_.Name; name = [string]$_.Value.Name }
    } | Sort-Object id)
    return Get-Sha256Text (([ordered]@{ id = [string]$rows[0].Id; internal = [bool]$rows[0].Internal; members = $members } | ConvertTo-Json -Depth 5 -Compress))
}

function Read-PreviewNetwork {
    $rows = @(Invoke-Docker @('network', 'inspect', $previewNetwork) | ConvertFrom-Json)
    if ($rows.Count -ne 1) { Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID' }
    return $rows[0]
}

function Get-PreviewNetworkStaticSha([object]$Network) {
    $options = [ordered]@{}
    foreach ($property in @($Network.Options.PSObject.Properties | Sort-Object Name)) {
        if ($property.Name -notin @('com.docker.network.bridge.host_binding_ipv4','com.docker.network.enable_ipv4','com.docker.network.enable_ipv6')) {
            Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID'
        }
        $options[$property.Name] = [string]$property.Value
    }
    $labels = [ordered]@{}
    foreach ($property in @($Network.Labels.PSObject.Properties | Sort-Object Name)) { $labels[$property.Name] = [string]$property.Value }
    return Get-Sha256Text (([ordered]@{
        id = [string]$Network.Id; name = [string]$Network.Name; driver = [string]$Network.Driver; scope = [string]$Network.Scope
        internal = [bool]$Network.Internal; attachable = [bool]$Network.Attachable; ingress = [bool]$Network.Ingress
        configOnly = [bool]$Network.ConfigOnly; configFromNetwork = [string]$Network.ConfigFrom.Network
        enableIPv4 = [bool]$Network.EnableIPv4; enableIPv6 = [bool]$Network.EnableIPv6
        ipamDriver = [string]$Network.IPAM.Driver; ipamConfig = @($Network.IPAM.Config)
        options = $options; labels = $labels
    } | ConvertTo-Json -Depth 8 -Compress))
}

function Assert-PreviewNetwork([int]$ExpectedMembers) {
    if ($previewNetworkId -notmatch '^[0-9a-f]{64}$' -or $previewNetwork -notmatch '^nestakada-core20-preview-[0-9a-f]{32}$') {
        Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID'
    }
    $network = Read-PreviewNetwork
    if ([string]$network.Id -cne $previewNetworkId -or [string]$network.Name -cne $previewNetwork -or
        [string]$network.Driver -cne 'bridge' -or [string]$network.Scope -cne 'local' -or
        [bool]$network.Internal -or [bool]$network.Attachable -or [bool]$network.Ingress -or [bool]$network.ConfigOnly -or
        @($network.ConfigFrom.PSObject.Properties | Where-Object { $_.Name -cne 'Network' }).Count -ne 0 -or
        [string]$network.ConfigFrom.Network -cne '' -or
        ![bool]$network.EnableIPv4 -or [bool]$network.EnableIPv6 -or [string]$network.IPAM.Driver -cne 'default' -or
        [string]$network.Options.'com.docker.network.bridge.host_binding_ipv4' -cne '127.0.0.1' -or
        @($network.Labels.PSObject.Properties).Count -ne 3 -or
        [string]$network.Labels.'estakada.scope' -cne 'core20-disposable-clone' -or
        [string]$network.Labels.'estakada.run' -cne $runToken -or [string]$network.Labels.'estakada.role' -cne 'preview-network' -or
        @($network.Containers.PSObject.Properties).Count -ne $ExpectedMembers) {
        Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID'
    }
    $staticSha = Get-PreviewNetworkStaticSha $network
    if ($previewNetworkStaticSha -ne '' -and $staticSha -cne $previewNetworkStaticSha) { Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID' }
    return $network
}

function New-PreviewNetwork {
    if ($previewNetwork -notmatch '^nestakada-core20-preview-[0-9a-f]{32}$') { Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID' }
    $ids = @(Invoke-Docker @(
        'network','create','--driver','bridge','--opt','com.docker.network.bridge.host_binding_ipv4=127.0.0.1',
        '--label','estakada.scope=core20-disposable-clone','--label',"estakada.run=$runToken",'--label','estakada.role=preview-network',
        $previewNetwork
    ) 60000)
    if ($ids.Count -ne 1 -or [string]$ids[0] -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_PREVIEW_NETWORK_CREATE_FAILED' }
    $script:previewNetworkId = [string]$ids[0]
    $script:previewNetworkCreated = $true
    $network = Assert-PreviewNetwork 0
    $script:previewNetworkStaticSha = Get-PreviewNetworkStaticSha $network
    $script:previewNetworkReceiptSha = $previewNetworkStaticSha
    Assert-PreviewNetwork 0 | Out-Null
}

function Remove-PreviewNetwork {
    $matches = @(Invoke-Docker @('network','ls','--filter',"name=^$previewNetwork$",'--format','{{.Name}}'))
    if ($matches.Count -eq 0) {
        $script:previewNetworkCreated = $false
        $script:previewNetworkId = ''
        $script:previewNetworkStaticSha = ''
        return
    }
    if ($matches.Count -ne 1 -or [string]$matches[0] -cne $previewNetwork) { Fail-Core20 'CORE20_PREVIEW_NETWORK_CLEANUP_UNCERTAIN' }
    if (!$previewNetworkCreated -or $previewNetworkId -eq '') {
        $network = Read-PreviewNetwork
        $candidateId = [string]$network.Id
        if ($candidateId -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID' }
        $script:previewNetworkId = $candidateId
        $script:previewNetworkCreated = $true
        Assert-PreviewNetwork 0 | Out-Null
        $script:previewNetworkStaticSha = Get-PreviewNetworkStaticSha $network
    }
    Assert-PreviewNetwork 0 | Out-Null
    Invoke-Docker @('network','rm',$previewNetworkId) 30000 | Out-Null
    $remaining = @(Invoke-Docker @('network','ls','--filter',"name=^$previewNetwork$",'--format','{{.Name}}'))
    if ($remaining.Count -ne 0) { Fail-Core20 'CORE20_PREVIEW_NETWORK_CLEANUP_UNCERTAIN' }
    $script:previewNetworkCreated = $false
    $script:previewNetworkId = ''
    $script:previewNetworkStaticSha = ''
}

function Get-ContainerStaticProjection([object]$Item) {
    $mounts = @($Item.Mounts | Sort-Object Destination | ForEach-Object {
        [ordered]@{ destination = [string]$_.Destination; mode = [string]$_.Mode; rw = [bool]$_.RW; type = [string]$_.Type }
    })
    $networkNames = @($Item.NetworkSettings.Networks.PSObject.Properties.Name | Sort-Object)
    $portBindings = @()
    foreach ($property in @($Item.HostConfig.PortBindings.PSObject.Properties | Sort-Object Name)) {
        foreach ($binding in @($property.Value)) {
            $portBindings += [ordered]@{ container = [string]$property.Name; hostIp = [string]$binding.HostIp; hostPort = [string]$binding.HostPort }
        }
    }
    $projection = [ordered]@{
        id = [string]$Item.Id
        image = [string]$Item.Image
        readonlyRootfs = [bool]$Item.HostConfig.ReadonlyRootfs
        restart = [string]$Item.HostConfig.RestartPolicy.Name
        capDrop = @($Item.HostConfig.CapDrop | Sort-Object)
        securityOpt = @($Item.HostConfig.SecurityOpt | Sort-Object)
        networks = $networkNames
        ports = $portBindings
        mounts = $mounts
        configHash = Get-Sha256Text (([ordered]@{
            image = [string]$Item.Config.Image
            cmd = @($Item.Config.Cmd)
            entrypoint = @($Item.Config.Entrypoint)
            env = @($Item.Config.Env | Sort-Object)
            labels = @($Item.Config.Labels.PSObject.Properties | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" })
        } | ConvertTo-Json -Depth 8 -Compress))
    }
    return $projection
}

function Assert-PreviewBoundary([bool]$RequireStopped) {
    $db = Read-Container $dbContainer
    $app = Read-Container $previewApp
    $ingress = Read-Container $previewIngress
    if ([string]$db.Id -cne $expectedDbId -or [string]$db.Image -cne $expectedDbImage) { Fail-Core20 'CORE20_SOURCE_DB_IDENTITY_INVALID' }
    if (![bool]$db.State.Running) { Fail-Core20 'CORE20_SOURCE_DB_NOT_RUNNING' }
    if ([string]$app.Id -cne $expectedAppId -or [string]$app.Image -cne $expectedAppImage) { Fail-Core20 }
    if ([string]$ingress.Id -cne $expectedIngressId -or [string]$ingress.Image -cne $expectedIngressImage) { Fail-Core20 }
    if ($RequireStopped -and ([bool]$app.State.Running -or [bool]$ingress.State.Running)) { Fail-Core20 'CORE20_PREVIEW_BITMAP_INVALID' }
    foreach ($item in @($app, $ingress)) {
        if (![bool]$item.HostConfig.ReadonlyRootfs -or [string]$item.HostConfig.RestartPolicy.Name -cne 'no') { Fail-Core20 }
    }
    $appBindings = @($app.HostConfig.PortBindings.PSObject.Properties | ForEach-Object { @($_.Value) } | Where-Object { $null -ne $_ })
    if ($appBindings.Count -ne 0) { Fail-Core20 }
    $ingressBindings = @($ingress.HostConfig.PortBindings.PSObject.Properties | ForEach-Object { @($_.Value) } | Where-Object { $null -ne $_ })
    if ($ingressBindings.Count -ne 1 -or [string]$ingressBindings[0].HostIp -cne '127.0.0.1' -or [string]$ingressBindings[0].HostPort -cne '18085') { Fail-Core20 }
    $previewMount = @($app.Mounts | Where-Object { [string]$_.Destination -ceq '/preview' })
    $publicMount = @($ingress.Mounts | Where-Object { [string]$_.Destination -ceq '/srv/public-media' })
    if ($previewMount.Count -ne 1 -or [bool]$previewMount[0].RW -or $publicMount.Count -ne 1 -or [bool]$publicMount[0].RW) { Fail-Core20 }
    return [ordered]@{
        app = Get-ContainerStaticProjection $app
        ingress = Get-ContainerStaticProjection $ingress
    }
}

function Stop-ExactPreviewContainer([string]$Name, [string]$ExpectedId) {
    $item = Read-Container $Name
    if ([string]$item.Id -cne $ExpectedId) { Fail-Core20 'CORE20_PREVIEW_IDENTITY_DRIFT' }
    if ([bool]$item.State.Running) { Invoke-Docker @('stop', '--time', '10', $Name) 30000 | Out-Null }
    $after = Read-Container $Name
    if ([string]$after.Id -cne $ExpectedId -or [bool]$after.State.Running) { Fail-Core20 'CORE20_PREVIEW_BITMAP_UNCERTAIN' }
}

function Remove-OwnedCaptureContainer([string]$Name) {
    if ($Name -notmatch "^nestakada-core20-(pre|post)-$runToken$") { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    $rows = @(Invoke-Docker @('ps', '-a', '--filter', "name=^/$Name$", '--format', '{{.Names}}'))
    if ($rows.Count -eq 0) { return }
    if ($rows.Count -ne 1 -or [string]$rows[0] -cne $Name) { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    $item = Read-Container $Name
    $command = @($item.Config.Cmd)
    if ([string]$item.Name -cne "/$Name" -or [string]$item.Image -cne $expectedAppImage -or
        ![bool]$item.HostConfig.AutoRemove -or $command -notcontains '/tools/rebuild7_generation.py' -or $command[-1] -cne 'capture') {
        Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID'
    }
    $exactId = [string]$item.Id
    if ($exactId -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    Invoke-Docker @('rm', '-f', $exactId) 30000 | Out-Null
    $remainingByName = @(Invoke-Docker @('ps', '-a', '--filter', "name=^/$Name$", '--format', '{{.Names}}'))
    $remainingById = @(Invoke-Docker @('ps', '-a', '--no-trunc', '--filter', "id=$exactId", '--format', '{{.ID}}'))
    if ($remainingByName.Count -ne 0 -or $remainingById.Count -ne 0) { Fail-Core20 'CORE20_CLEANUP_UNCERTAIN' }
}

function Remove-OwnedSourceGuardContainer([string]$Name) {
    if ($Name -cne $sourceGuardPreContainer -and $Name -cne $sourceGuardPostContainer) { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    if ($Name -notmatch '^nestakada-core20-source-(pre|post)-[0-9a-f]{32}$') { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    $rows = @(Invoke-Docker @('ps', '-a', '--filter', "name=^/$Name$", '--format', '{{.Names}}'))
    if ($rows.Count -eq 0) { return }
    if ($rows.Count -ne 1 -or [string]$rows[0] -cne $Name) { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    $item = Read-Container $Name
    $command = @($item.Config.Cmd)
    if ([string]$item.Name -cne "/$Name" -or [string]$item.Image -cne $expectedAppImage -or
        ![bool]$item.HostConfig.AutoRemove -or $command -notcontains '/tools/rebuild7_generation.py' -or $command[-1] -cne 'source-guard') {
        Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID'
    }
    $exactId = [string]$item.Id
    if ($exactId -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    Invoke-Docker @('rm', '-f', $exactId) 30000 | Out-Null
}

function Assert-OwnedCloneContainer([string]$Name, [string]$Role, [string]$Image, [string]$ExpectedId, [bool]$RequireExactName = $true) {
    $expectedNames = @{
        migrate = $cloneMigrationContainer; app = $cloneApp; ingress = $cloneIngress
    }
    if (!$expectedNames.ContainsKey($Role) -or $Name -cne $expectedNames[$Role] -or $ExpectedId -notmatch '^[0-9a-f]{64}$' -or
        $Name -notmatch '^nestakada-core20-(migrate|app|ingress)-[0-9a-f]{32}$') {
        Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID'
    }
    $item = Read-Container $(if ($RequireExactName) { $Name } else { $ExpectedId })
    $expectedUser = if ($Role -eq 'ingress') { '101:101' } else { '10001:10001' }
    $expectedMemory = if ($Role -eq 'ingress') { 268435456L } else { 805306368L }
    $expectedNanoCpus = if ($Role -eq 'ingress') { 500000000L } else { 1000000000L }
    $expectedPids = if ($Role -eq 'ingress') { 64L } else { 128L }
    $expectedNetworkMode = if ($Role -eq 'ingress') { $previewNetwork } else { $dbNetwork }
    $expectedEntrypoint = if ($Role -eq 'ingress') { @('nginx') } else { @('python') }
    $expectedCommand = switch ($Role) {
        migrate { @('-B','/app/manage.py','migrate','service_requests','0001_initial','--noinput') }
        app { @('-B','/app/manage.py','runserver','0.0.0.0:8000','--noreload') }
        ingress { @('-g','daemon off;') }
    }
    $expectedMounts = switch ($Role) {
        migrate { @{ '/app' = (Join-Path $repo 'src'); '/run/secrets/db-password' = (Join-Path $private 'migrator-password'); '/run/secrets/database-ca' = (Join-Path $private 'database-ca') } }
        app { @{ '/app' = (Join-Path $repo 'src'); '/run/secrets/db-password' = (Join-Path $private 'migrator-password'); '/run/secrets/database-ca' = (Join-Path $private 'database-ca') } }
        ingress { @{ '/etc/nginx/nginx.conf' = $cloneNginxConfig; '/srv/public-media' = (Join-Path $repo 'work\rb5-home-preview\media') } }
    }
    if ([string]$item.Id -cne $ExpectedId -or ($RequireExactName -and [string]$item.Name -cne "/$Name") -or [string]$item.Image -cne $Image -or
        [string]$item.Config.Labels.'estakada.scope' -cne 'core20-disposable-clone' -or
        [string]$item.Config.Labels.'estakada.run' -cne $runToken -or
        [string]$item.Config.Labels.'estakada.role' -cne $Role -or [string]$item.Config.User -cne $expectedUser -or
        (@($item.Config.Entrypoint) | ConvertTo-Json -Compress) -cne ($expectedEntrypoint | ConvertTo-Json -Compress) -or
        (@($item.Config.Cmd) | ConvertTo-Json -Compress) -cne ($expectedCommand | ConvertTo-Json -Compress) -or
        [string]$item.HostConfig.NetworkMode -cne $expectedNetworkMode -or ![bool]$item.HostConfig.ReadonlyRootfs -or
        [string]$item.HostConfig.RestartPolicy.Name -cne 'no' -or @($item.HostConfig.CapDrop).Count -ne 1 -or
        [string]$item.HostConfig.CapDrop[0] -cne 'ALL' -or @($item.HostConfig.SecurityOpt).Count -ne 1 -or
        [string]$item.HostConfig.SecurityOpt[0] -cne 'no-new-privileges:true' -or [long]$item.HostConfig.Memory -ne $expectedMemory -or
        [long]$item.HostConfig.NanoCpus -ne $expectedNanoCpus -or [long]$item.HostConfig.PidsLimit -ne $expectedPids -or
        @($item.Mounts).Count -ne $expectedMounts.Count) {
        Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID'
    }
    foreach ($mount in @($item.Mounts)) {
        if (!$expectedMounts.ContainsKey([string]$mount.Destination) -or [bool]$mount.RW -or [string]$mount.Type -cne 'bind' -or
            ![string]::Equals([IO.Path]::GetFullPath([string]$mount.Source), [IO.Path]::GetFullPath([string]$expectedMounts[[string]$mount.Destination]), [StringComparison]::OrdinalIgnoreCase)) {
            Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID'
        }
    }
    $ports = @($item.HostConfig.PortBindings.PSObject.Properties)
    if (($Role -eq 'ingress' -and ($ports.Count -ne 1 -or $ports[0].Name -cne '8080/tcp' -or @($ports[0].Value).Count -ne 1 -or
        [string]$ports[0].Value[0].HostIp -cne '127.0.0.1' -or [string]$ports[0].Value[0].HostPort -cne '18085')) -or
        ($Role -ne 'ingress' -and $ports.Count -ne 0)) { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    return $item
}

function Remove-OwnedCloneContainer([string]$Name, [string]$Role, [string]$Image, [string]$ExpectedId) {
    if ($ExpectedId -ne '') {
        $idRows = @(Invoke-Docker @('ps', '-a', '--no-trunc', '--filter', "id=$ExpectedId", '--format', '{{.ID}}'))
        if ($idRows.Count -eq 0) {
            if (@(Invoke-Docker @('ps', '-a', '--filter', "name=^/$Name$", '--format', '{{.Names}}')).Count -ne 0) {
                Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID'
            }
            return
        }
        if ($idRows.Count -ne 1 -or [string]$idRows[0] -cne $ExpectedId) { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
        Assert-OwnedCloneContainer $Name $Role $Image $ExpectedId $false | Out-Null
    } else {
        $rows = @(Invoke-Docker @('ps', '-a', '--filter', "name=^/$Name$", '--format', '{{.Names}}'))
        if ($rows.Count -eq 0) { return }
        if ($rows.Count -ne 1 -or [string]$rows[0] -cne $Name) { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
        $candidate = Read-Container $Name
        $ExpectedId = [string]$candidate.Id
        if ($ExpectedId -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
        Assert-OwnedCloneContainer $Name $Role $Image $ExpectedId | Out-Null
    }
    Invoke-Docker @('rm', '-f', $ExpectedId) 30000 | Out-Null
    $remainingByName = @(Invoke-Docker @('ps', '-a', '--filter', "name=^/$Name$", '--format', '{{.Names}}'))
    $remainingById = @(Invoke-Docker @('ps', '-a', '--no-trunc', '--filter', "id=$ExpectedId", '--format', '{{.ID}}'))
    if ($remainingByName.Count -ne 0 -or $remainingById.Count -ne 0) {
        Fail-Core20 'CORE20_CLEANUP_UNCERTAIN'
    }
}

function Invoke-Capture([string]$Name, [string]$OutputPath, [string]$Database = $sourceDatabase) {
    if ($Database -cne $sourceDatabase -and $Database -cne $cloneDatabase) { Fail-Core20 'CORE20_DATABASE_SCOPE_INVALID' }
    $args = @(
        'run', '--rm', '--name', $Name, '--network', $dbNetwork,
        '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app',
        '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore', '--env', 'ESTAKADA_LOCAL_RESTORE=1',
        '--env', "ESTAKADA_APP_IMAGE_DIGEST=$expectedAppImage", '--env', 'ESTAKADA_DJANGO_SECRET=core20-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000', '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$Database", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password', '--env', 'ESTAKADA_DB_HOST=db',
        '--env', 'ESTAKADA_DB_PORT=5432', '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly",
        '--mount', "type=bind,source=$repo,target=/project,readonly",
        '--mount', "type=bind,source=$repo\tools\rebuild7_generation.py,target=/tools/rebuild7_generation.py,readonly",
        '--mount', "type=bind,source=$OutputPath,target=/output",
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
        $expectedAppImage, 'python', '-B', '/tools/rebuild7_generation.py', 'capture'
    )
    $lines = @(Invoke-Docker $args 300000)
    if ($lines.Count -ne 1 -or [string]$lines[0] -notmatch '^R7_GENERATION_CAPTURE_OK ') { Fail-Core20 'CORE20_PROJECTION_FAILED' }
    $projection = [ordered]@{}
    foreach ($filename in @('release-manifest.json', 'capture-facts.json', 'media-inventory.json')) {
        $path = Join-Path $OutputPath $filename
        $item = Get-Item -Force -LiteralPath $path
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-Core20 }
        $projection[$filename] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $projection
}

function Invoke-SourceGuard([string]$Name, [string]$OutputPath) {
    $args = @(
        'run', '--rm', '--name', $Name, '--network', $dbNetwork,
        '--read-only', '--user', '10001:10001', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app', '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore',
        '--env', 'ESTAKADA_LOCAL_RESTORE=1', '--env', "ESTAKADA_APP_IMAGE_DIGEST=$expectedAppImage",
        '--env', 'ESTAKADA_DJANGO_SECRET=core20-ephemeral-only', '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000', '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$sourceDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator', '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password',
        '--env', 'ESTAKADA_DB_HOST=db', '--env', 'ESTAKADA_DB_PORT=5432', '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly", '--mount', "type=bind,source=$repo,target=/project,readonly",
        '--mount', "type=bind,source=$repo\tools\rebuild7_generation.py,target=/tools/rebuild7_generation.py,readonly",
        '--mount', "type=bind,source=$OutputPath,target=/output", '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
        $expectedAppImage, 'python', '-B', '/tools/rebuild7_generation.py', 'source-guard'
    )
    $lines = @(Invoke-Docker $args 300000)
    if ($lines.Count -ne 1 -or [string]$lines[0] -cne 'R7_GENERATION_SOURCE_GUARD_OK') { Fail-Core20 'CORE20_SOURCE_GUARD_FAILED' }
    $path = Join-Path $OutputPath 'source-guard.json'
    Assert-RegularFile $path
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-CloneDatabaseCount {
    $rows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT count(*) FROM pg_database WHERE datname='$cloneDatabase'"
    ))
    if ($rows.Count -ne 1 -or ([string]$rows[0]).Trim() -notmatch '^[01]$') { Fail-Core20 'CORE20_CLONE_DATABASE_UNCERTAIN' }
    return [int]([string]$rows[0]).Trim()
}

function Assert-CloneDatabaseAbsent {
    if ((Get-CloneDatabaseCount) -ne 0) { Fail-Core20 'CORE20_CLONE_DATABASE_COLLISION' }
}

function Assert-CloneDatabaseOwned {
    $identityRows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT oid::text || '|' || pg_get_userbyid(datdba) || '|' || COALESCE(shobj_description(oid,'pg_database'),'') FROM pg_database WHERE datname='$cloneDatabase'"
    ))
    if ($identityRows.Count -ne 1 -or [string]$identityRows[0] -notmatch '^(?<oid>[1-9][0-9]*)\|app_migrator\|estakada-core20-disposable-clone:[0-9a-f]{32}$' -or
        [string]$identityRows[0] -cne "$cloneDatabaseOid|app_migrator|estakada-core20-disposable-clone:$runToken") {
        Fail-Core20 'CORE20_CLONE_DATABASE_IDENTITY_INVALID'
    }
}

function Assert-CloneDatabaseAcl {
    $sql = "WITH acl AS (SELECT x.* FROM pg_database d CROSS JOIN LATERAL aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) x WHERE d.datname='$cloneDatabase') SELECT count(*)::text || '|' || count(*) FILTER (WHERE grantee=(SELECT oid FROM pg_roles WHERE rolname='app_migrator'))::text || '|' || count(*) FILTER (WHERE grantee<>(SELECT oid FROM pg_roles WHERE rolname='app_migrator'))::text || '|' || string_agg(privilege_type,',' ORDER BY privilege_type) || '|' || count(*) FILTER (WHERE NOT is_grantable)::text FROM acl;"
    $rows = @(Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c', $sql))
    if ($rows.Count -ne 1 -or [string]$rows[0] -cne '3|3|0|CONNECT,CREATE,TEMPORARY|3') { Fail-Core20 'CORE20_CLONE_DATABASE_ACL_INVALID' }
}

function Remove-DisposableCloneDatabase {
    if (!$cloneDatabaseCreated) { return }
    if ($cloneDatabase -notmatch '^estakada_core20_[0-9a-f]{32}$') { Fail-Core20 'CORE20_CLEANUP_SCOPE_INVALID' }
    Wait-ZeroClients $cloneDatabase
    Assert-CloneDatabaseOwned
    Assert-CloneDatabaseAcl
    Invoke-Docker @('exec', '--user', 'postgres', $dbContainer, 'dropdb', '--if-exists', $cloneDatabase) 60000 | Out-Null
    Assert-CloneDatabaseAbsent
    $script:cloneDatabaseCreated = $false
    $script:cloneDatabaseOid = ''
}

function New-DisposableCloneDatabase {
    if (!$DisposableCloneRemediation -or $cloneDatabase -notmatch '^estakada_core20_[0-9a-f]{32}$') { Fail-Core20 'CORE20_DATABASE_SCOPE_INVALID' }
    Assert-ZeroClients $sourceDatabase
    Assert-CloneDatabaseAbsent
    Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'createdb', '--owner=app_migrator',
        "--template=$sourceDatabase", $cloneDatabase
    ) 300000 | Out-Null
    $script:cloneDatabaseCreated = $true
    Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-AtX', '-c',
        "COMMENT ON DATABASE $cloneDatabase IS 'estakada-core20-disposable-clone:$runToken'; REVOKE CONNECT,TEMPORARY ON DATABASE $cloneDatabase FROM PUBLIC; GRANT CONNECT,TEMPORARY ON DATABASE $cloneDatabase TO app_migrator"
    ) 30000 | Out-Null
    $identityRows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', 'postgres', '-AtX', '-c',
        "SELECT oid::text || '|' || pg_get_userbyid(datdba) || '|' || COALESCE(shobj_description(oid,'pg_database'),'') FROM pg_database WHERE datname='$cloneDatabase'"
    ))
    if ($identityRows.Count -ne 1 -or [string]$identityRows[0] -notmatch '^(?<oid>[1-9][0-9]*)\|app_migrator\|estakada-core20-disposable-clone:[0-9a-f]{32}$') {
        Fail-Core20 'CORE20_CLONE_DATABASE_IDENTITY_INVALID'
    }
    $script:cloneDatabaseOid = $Matches.oid
    Assert-CloneDatabaseOwned
    Assert-CloneDatabaseAcl
}

function Invoke-CloneMigration {
    $args = @(
        'create', '--name', $cloneMigrationContainer,
        '--label', 'estakada.scope=core20-disposable-clone', '--label', "estakada.run=$runToken", '--label', 'estakada.role=migrate',
        '--network', $dbNetwork, '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges:true', '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app', '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore',
        '--env', 'ESTAKADA_LOCAL_RESTORE=1', '--env', 'ESTAKADA_RESTORE_VERIFY_WRITE=1',
        '--env', 'ESTAKADA_DJANGO_SECRET=core20-ephemeral-only', '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver',
        '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://localhost:8000', '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all',
        '--env', "ESTAKADA_DB_NAME=$cloneDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator', '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password',
        '--env', 'ESTAKADA_DB_HOST=db', '--env', 'ESTAKADA_DB_PORT=5432', '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--mount', "type=bind,source=$repo\src,target=/app,readonly", '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly", '--entrypoint', 'python',
        $expectedAppImage, '-B', '/app/manage.py', 'migrate', 'service_requests', '0001_initial', '--noinput'
    )
    $ids = @(Invoke-Docker $args 60000)
    if ($ids.Count -ne 1 -or [string]$ids[0] -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_CLONE_CONTAINER_CREATE_FAILED' }
    $script:cloneMigrationId = [string]$ids[0]
    Assert-OwnedCloneContainer $cloneMigrationContainer 'migrate' $expectedAppImage $cloneMigrationId | Out-Null
    Invoke-Docker @('start', '--attach', $cloneMigrationId) 300000 | Out-Null
    $after = Assert-OwnedCloneContainer $cloneMigrationContainer 'migrate' $expectedAppImage $cloneMigrationId
    if ([int]$after.State.ExitCode -ne 0 -or [bool]$after.State.Running) { Fail-Core20 'CORE20_CLONE_MIGRATION_FAILED' }
    Remove-OwnedCloneContainer $cloneMigrationContainer 'migrate' $expectedAppImage $cloneMigrationId
    $script:cloneMigrationId = ''
}

function Assert-CloneMigrationState {
    $sql = "SELECT (SELECT count(*) FROM app.django_migrations WHERE app='service_requests' AND name='0001_initial')::text || '|' || (to_regclass('app.service_requests_servicerequest') IS NOT NULL)::int::text || '|' || (to_regclass('app.service_requests_servicerequestdeletionprojection') IS NOT NULL)::int::text || '|' || (SELECT count(*) FROM app.service_requests_servicerequest)::text || '|' || (SELECT count(*) FROM app.service_requests_servicerequestdeletionprojection)::text;"
    $rows = @(Invoke-Docker @(
        'exec', '--user', 'postgres', $dbContainer, 'psql', '-d', $cloneDatabase, '-AtX', '-c', $sql
    ))
    if ($rows.Count -ne 1 -or [string]$rows[0] -cne '1|1|1|0|0') {
        Fail-Core20 'CORE20_CLONE_MIGRATION_INVALID'
    }
}

function Wait-CloneAppReadiness([int]$TimeoutSeconds = 90) {
    $probeCode = @'
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None
status = 0
try:
    response = build_opener(NoRedirect).open(Request("http://127.0.0.1:8000/", headers={"X-Estakada-Request-Target": "/"}), timeout=2)
    status = int(response.status)
except HTTPError as error:
    status = int(error.code)
except Exception:
    status = 0
print(f"CORE20_APP_STATUS_{status:03d}")
'@
    $deadline = New-MonotonicDeadline ($TimeoutSeconds * 1000)
    $lastStatus = '000'
    while ((Get-MonotonicRemainingMilliseconds $deadline) -gt 0) {
        try {
            $lines = @(Invoke-Docker @('exec', $cloneAppId, 'python', '-B', '-c', $probeCode) 5000)
            if ($lines.Count -eq 1 -and [string]$lines[0] -match '^CORE20_APP_STATUS_(?<status>(?:000|[1-5][0-9]{2}))$') {
                $lastStatus = $Matches.status
                if ($lastStatus -ceq '200') { return }
            }
        } catch { $lastStatus = '000' }
        $remainingMs = Get-MonotonicRemainingMilliseconds $deadline
        if ($remainingMs -gt 0) { Start-Sleep -Milliseconds ([Math]::Min(250, $remainingMs)) }
    }
    Fail-Core20 "CORE20_APP_READINESS_STATUS_$lastStatus"
}

function Start-ClonePreview {
    $canonicalNginx = Join-Path $repo 'environment\rebuild5-preview\nginx.conf'
    Assert-PinnedFile $canonicalNginx 'eb12141e24120c19d869850fef4c656a5abee3a48390fa924bcced19686b29ad'
    $nginxText = [IO.File]::ReadAllText($canonicalNginx, [Text.Encoding]::UTF8)
    $needle = 'proxy_pass http://app:8000;'
    if ([regex]::Matches($nginxText, [regex]::Escape($needle)).Count -ne 1) { Fail-Core20 'CORE20_INGRESS_CONFIG_INVALID' }
    $nginxText = $nginxText.Replace($needle, "proxy_pass http://$cloneAppAlias`:8000;")
    if (Test-Path -LiteralPath $cloneNginxConfig) { Fail-Core20 'CORE20_INGRESS_CONFIG_INVALID' }
    [IO.File]::WriteAllText($cloneNginxConfig, $nginxText, [Text.UTF8Encoding]::new($false))
    Assert-RegularFile $cloneNginxConfig
    $script:cloneNginxConfigSha = (Get-FileHash -LiteralPath $cloneNginxConfig -Algorithm SHA256).Hash.ToLowerInvariant()

    $appArgs = @(
        'create', '--name', $cloneApp,
        '--label', 'estakada.scope=core20-disposable-clone', '--label', "estakada.run=$runToken", '--label', 'estakada.role=app',
        '--network', $dbNetwork, '--network-alias', $cloneAppAlias, '--read-only', '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges:true', '--memory', '768m', '--cpus', '1.0', '--pids-limit', '128',
        '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/app', '--env', 'DJANGO_SETTINGS_MODULE=config.settings.local_restore',
        '--env', 'ESTAKADA_LOCAL_RESTORE=1', '--env', 'ESTAKADA_DJANGO_SECRET=core20-ephemeral-only',
        '--env', 'ESTAKADA_ALLOWED_HOSTS=localhost,127.0.0.1,testserver', '--env', 'ESTAKADA_PUBLIC_ORIGIN=http://127.0.0.1:18085',
        '--env', 'ESTAKADA_SEO_ROBOTS_PROFILE=deny-all', '--env', "ESTAKADA_DB_NAME=$cloneDatabase", '--env', 'ESTAKADA_DB_USER=app_migrator',
        '--env', 'ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password', '--env', 'ESTAKADA_DB_HOST=db', '--env', 'ESTAKADA_DB_PORT=5432',
        '--env', 'ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca', '--mount', "type=bind,source=$repo\src,target=/app,readonly",
        '--mount', "type=bind,source=$private\migrator-password,target=/run/secrets/db-password,readonly",
        '--mount', "type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly", '--entrypoint', 'python',
        $expectedAppImage, '-B', '/app/manage.py', 'runserver', '0.0.0.0:8000', '--noreload'
    )
    $appIds = @(Invoke-Docker $appArgs 60000)
    if ($appIds.Count -ne 1 -or [string]$appIds[0] -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_CLONE_CONTAINER_CREATE_FAILED' }
    $script:cloneAppId = [string]$appIds[0]
    Assert-OwnedCloneContainer $cloneApp 'app' $expectedAppImage $cloneAppId | Out-Null
    Invoke-Docker @('start', $cloneAppId) 30000 | Out-Null
    $script:cloneAppStarted = $true
    Wait-CloneAppReadiness
    New-PreviewNetwork

    $mediaSource = Join-Path $repo 'work\rb5-home-preview\media'
    Assert-Contained $repo $mediaSource $true
    $ingressArgs = @(
        'create', '--name', $cloneIngress,
        '--label', 'estakada.scope=core20-disposable-clone', '--label', "estakada.run=$runToken", '--label', 'estakada.role=ingress',
        '--network', $previewNetwork, '--read-only', '--user', '101:101', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=32m,uid=101,gid=101,mode=1777',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--memory', '256m', '--cpus', '0.5', '--pids-limit', '64',
        '--publish', '127.0.0.1:18085:8080', '--mount', "type=bind,source=$cloneNginxConfig,target=/etc/nginx/nginx.conf,readonly",
        '--mount', "type=bind,source=$mediaSource,target=/srv/public-media,readonly", '--entrypoint', 'nginx',
        $expectedIngressImage, '-g', 'daemon off;'
    )
    $ingressIds = @(Invoke-Docker $ingressArgs 60000)
    if ($ingressIds.Count -ne 1 -or [string]$ingressIds[0] -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_CLONE_CONTAINER_CREATE_FAILED' }
    $script:cloneIngressId = [string]$ingressIds[0]
    Assert-OwnedCloneContainer $cloneIngress 'ingress' $expectedIngressImage $cloneIngressId | Out-Null
    if ($dbNetworkId -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_NETWORK_INVALID' }
    Invoke-Docker @('network','connect',$dbNetworkId,$cloneIngressId) 30000 | Out-Null
    Invoke-Docker @('start', $cloneIngressId) 30000 | Out-Null
    $script:cloneIngressStarted = $true
}

function Assert-ClonePreviewBoundary {
    $app = Assert-OwnedCloneContainer $cloneApp 'app' $expectedAppImage $cloneAppId
    $ingress = Assert-OwnedCloneContainer $cloneIngress 'ingress' $expectedIngressImage $cloneIngressId
    if ((Get-FileHash -LiteralPath $cloneNginxConfig -Algorithm SHA256).Hash.ToLowerInvariant() -cne $cloneNginxConfigSha) {
        Fail-Core20 'CORE20_INGRESS_CONFIG_INVALID'
    }
    foreach ($tuple in @(@($app, $cloneApp, $expectedAppImage, 'app'), @($ingress, $cloneIngress, $expectedIngressImage, 'ingress'))) {
        $item = $tuple[0]
        if ([string]$item.Name -cne "/$($tuple[1])" -or [string]$item.Image -cne $tuple[2] -or ![bool]$item.State.Running -or
            ![bool]$item.HostConfig.ReadonlyRootfs -or [string]$item.HostConfig.RestartPolicy.Name -cne 'no' -or
            @($item.HostConfig.CapDrop).Count -ne 1 -or [string]$item.HostConfig.CapDrop[0] -cne 'ALL' -or
            @($item.HostConfig.SecurityOpt).Count -ne 1 -or [string]$item.HostConfig.SecurityOpt[0] -cne 'no-new-privileges:true' -or
            [string]$item.Config.Labels.'estakada.scope' -cne 'core20-disposable-clone' -or
            [string]$item.Config.Labels.'estakada.run' -cne $runToken -or [string]$item.Config.Labels.'estakada.role' -cne $tuple[3] -or
            $item.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $dbNetwork) {
            Fail-Core20 'CORE20_CLONE_PREVIEW_INVALID'
        }
    }
    if (@($app.NetworkSettings.Networks.PSObject.Properties).Count -ne 1 -or
        @($ingress.NetworkSettings.Networks.PSObject.Properties).Count -ne 2 -or
        $ingress.NetworkSettings.Networks.PSObject.Properties.Name -notcontains $previewNetwork) {
        Fail-Core20 'CORE20_CLONE_PREVIEW_INVALID'
    }
    $appNetwork = $app.NetworkSettings.Networks.PSObject.Properties[$dbNetwork].Value
    if (@($appNetwork.Aliases | Where-Object { [string]$_ -ceq $cloneAppAlias }).Count -ne 1) { Fail-Core20 'CORE20_CLONE_PREVIEW_INVALID' }
    $network = Assert-PreviewNetwork 1
    $member = @($network.Containers.PSObject.Properties)[0]
    if ([string]$member.Name -cne $cloneIngressId -or [string]$member.Value.Name -cne $cloneIngress) { Fail-Core20 'CORE20_PREVIEW_NETWORK_INVALID' }
    if (@($app.HostConfig.PortBindings.PSObject.Properties).Count -ne 0 -or
        @($app.Config.Env | Where-Object { $_ -ceq "ESTAKADA_DB_NAME=$cloneDatabase" }).Count -ne 1) {
        Fail-Core20 'CORE20_CLONE_PREVIEW_INVALID'
    }
    $bindings = @($ingress.HostConfig.PortBindings.PSObject.Properties | ForEach-Object { @($_.Value) } | Where-Object { $null -ne $_ })
    if ($bindings.Count -ne 1 -or [string]$bindings[0].HostIp -cne '127.0.0.1' -or [string]$bindings[0].HostPort -cne '18085') {
        Fail-Core20 'CORE20_CLONE_PREVIEW_INVALID'
    }
    $appSource = @($app.Mounts | Where-Object { [string]$_.Destination -ceq '/app' })
    $media = @($ingress.Mounts | Where-Object { [string]$_.Destination -ceq '/srv/public-media' })
    $config = @($ingress.Mounts | Where-Object { [string]$_.Destination -ceq '/etc/nginx/nginx.conf' })
    if ($appSource.Count -ne 1 -or [bool]$appSource[0].RW -or $media.Count -ne 1 -or [bool]$media[0].RW -or
        $config.Count -ne 1 -or [bool]$config[0].RW) { Fail-Core20 'CORE20_CLONE_PREVIEW_INVALID' }
    return [ordered]@{ app = Get-ContainerStaticProjection $app; ingress = Get-ContainerStaticProjection $ingress }
}

function Invoke-Playwright(
    [string[]]$Arguments,
    [bool]$Raw = $false,
    [bool]$Cleanup = $false,
    [string]$FailureCode = 'CORE20_BROWSER_FAILED'
) {
    if ($FailureCode -notmatch '^CORE20_BROWSER_(?:OPEN|POLICY|PID|RESIZE|NAVIGATION|SCREENSHOT|EXTERNAL)_FAILED$' -and
        $FailureCode -cne 'CORE20_BROWSER_FAILED') { Fail-Core20 'CORE20_BROWSER_DIAGNOSTIC_INVALID' }
    $args = @("-s=$session")
    if ($Raw) { $args += '--raw' }
    $args += $Arguments
    $timeout = 30000
    if (!$Cleanup) {
        $remaining = Get-MonotonicRemainingMilliseconds $browserDeadline
        if ($remaining -lt 1000) { Fail-Core20 'CORE20_BROWSER_TIMEOUT' }
        $timeout = [Math]::Min(60000, $remaining)
    }
    try { $result = Invoke-BoundedProcess $node (@($playwrightCli) + $args) $timeout }
    catch { Fail-Core20 $FailureCode }
    if ([int]$result.exitCode -ne 0 -or [string]$result.stderr -ne '') { Fail-Core20 $FailureCode }
    return @(([string]$result.stdout -split "`r?`n") | Where-Object { $_ -ne '' })
}

function Test-PlaywrightSessionPresent {
    $result = Invoke-BoundedProcess $node @($playwrightCli, 'list', '--all') 30000
    if ([int]$result.exitCode -ne 0 -or [string]$result.stderr -ne '') { Fail-Core20 'CORE20_BROWSER_AUDIT_FAILED' }
    return [bool]([string]$result.stdout -match "(?m)(^|\s)$([regex]::Escape($session))(\s|$)")
}

function Assert-ExactPlaywrightSessionPid([int]$Value) {
    if ($Value -le 0) { Fail-Core20 'CORE20_BROWSER_PID_UNAVAILABLE' }
    $process = [Diagnostics.Process]::GetProcessById($value)
    try {
        if ($process.ProcessName -cne 'node' -or [IO.Path]::GetFullPath($process.MainModule.FileName) -cne [IO.Path]::GetFullPath($node)) {
            Fail-Core20 'CORE20_BROWSER_PID_INVALID'
        }
    } finally { $process.Dispose() }
    return $Value
}

function Close-ExactPlaywrightSession {
    if (!(Test-PlaywrightSessionPresent)) { return }
    if ($browserSessionPid -le 0) { Fail-Core20 'CORE20_BROWSER_PID_UNAVAILABLE' }
    Assert-ExactPlaywrightSessionPid $browserSessionPid | Out-Null
    try { Invoke-Playwright @('close') $false $true | Out-Null } catch {}
    if (Test-PlaywrightSessionPresent) {
        $process = [Diagnostics.Process]::GetProcessById($browserSessionPid)
        try {
            if ($process.ProcessName -cne 'node' -or [IO.Path]::GetFullPath($process.MainModule.FileName) -cne [IO.Path]::GetFullPath($node)) {
                Fail-Core20 'CORE20_BROWSER_PID_INVALID'
            }
            $process.Kill($true)
            if (!$process.WaitForExit(10000)) { Fail-Core20 'CORE20_BROWSER_CLEANUP_FAILED' }
        } finally { $process.Dispose() }
    }
    if (Test-PlaywrightSessionPresent) { Fail-Core20 'CORE20_BROWSER_CLEANUP_FAILED' }
}

function Invoke-BrowserState([string]$Url) {
    $escaped = $Url.Replace("'", "\'")
    $code = @"
async page => {
page.__core20Console = [];
page.__core20PageErrors = [];
page.on('console', message => { if (message.type() === 'error') page.__core20Console.push(message.text()); });
page.on('pageerror', error => page.__core20PageErrors.push(error.name));
const response = await page.goto('$escaped', { waitUntil: 'networkidle', timeout: 20000 });
await page.evaluate(async () => {
  const pending = Array.from(document.images).filter(image => !image.complete).map(image => new Promise(resolve => {
    const done = () => resolve(); image.addEventListener('load', done, { once: true }); image.addEventListener('error', done, { once: true });
  }));
  await Promise.race([Promise.all(pending), new Promise(resolve => setTimeout(resolve, 10000))]);
});
const state = await page.evaluate(() => ({
  brokenImages: Array.from(document.images).filter(image => !image.complete || image.naturalWidth === 0).length,
  overflow: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0) > window.innerWidth
}));
return JSON.stringify({ status: response ? response.status() : 0, brokenImages: state.brokenImages, overflow: state.overflow,
  consoleErrors: page.__core20Console.length, pageErrors: page.__core20PageErrors.length });
}
"@
    $output = @(Invoke-Playwright @('run-code', $code) $true $false 'CORE20_BROWSER_NAVIGATION_FAILED')
    $jsonLine = @($output | Where-Object { [string]$_ -match '^\{.*\}$' })
    if ($jsonLine.Count -ne 1) { Fail-Core20 'CORE20_BROWSER_RESULT_INVALID' }
    $state = [string]$jsonLine[0] | ConvertFrom-Json
    if ([int]$state.status -ne 200 -or [int]$state.brokenImages -ne 0 -or [bool]$state.overflow -or
        [int]$state.consoleErrors -ne 0 -or [int]$state.pageErrors -ne 0) { Fail-Core20 'CORE20_BROWSER_ASSERTION_FAILED' }
    return $state
}

function Get-PngDimensions([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    $signature = [byte[]](137, 80, 78, 71, 13, 10, 26, 10)
    if ($bytes.Length -lt 24) { Fail-Core20 'CORE20_EVIDENCE_INVALID' }
    for ($index = 0; $index -lt $signature.Length; $index++) {
        if ($bytes[$index] -ne $signature[$index]) { Fail-Core20 'CORE20_EVIDENCE_INVALID' }
    }
    $width = [int](
        ([uint32]$bytes[16] -shl 24) -bor ([uint32]$bytes[17] -shl 16) -bor
        ([uint32]$bytes[18] -shl 8) -bor [uint32]$bytes[19]
    )
    $height = [int](
        ([uint32]$bytes[20] -shl 24) -bor ([uint32]$bytes[21] -shl 16) -bor
        ([uint32]$bytes[22] -shl 8) -bor [uint32]$bytes[23]
    )
    return [pscustomobject]@{ width = $width; height = $height }
}

function Add-Screenshot([string]$Map, [string]$Path, [string]$Viewport, [int]$Width, [int]$Height) {
    Invoke-Playwright @('resize', [string]$Width, [string]$Height) $false $false 'CORE20_BROWSER_RESIZE_FAILED' | Out-Null
    $url = "http://127.0.0.1:18085$Path"
    $state = Invoke-BrowserState $url
    $filename = "$Map-$Viewport.png"
    $destination = Join-Path $evidence $filename
    Invoke-Playwright @('screenshot', '--filename', $destination) $false $false 'CORE20_BROWSER_SCREENSHOT_FAILED' | Out-Null
    $item = Get-Item -Force -LiteralPath $destination
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -le 0 -or $item.Length -gt 20MB) {
        Fail-Core20 'CORE20_EVIDENCE_INVALID'
    }
    $dimensions = Get-PngDimensions $destination
    if ($dimensions.width -ne $Width -or $dimensions.height -ne $Height) { Fail-Core20 'CORE20_EVIDENCE_INVALID' }
    $screenshots.Add([ordered]@{
        map = $Map; path = $Path; viewport = $Viewport; width = $Width; height = $Height
        filename = $filename; bytes = [long]$item.Length
        sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        status = [int]$state.status; consoleErrors = 0; pageErrors = 0; brokenImages = 0; overflow = $false
    })
}

try {
    $requestedModes = @($RecoverStoppedSource, $RecoverGenerationDiagnostic, $DisposableCloneRemediation)
    if (@($requestedModes | Where-Object { $_ }).Count -gt 1) { Fail-Core20 'CORE20_RECOVERY_MODE_INVALID' }
    $recoveryRequested = $RecoverStoppedSource -or $RecoverGenerationDiagnostic -or $DisposableCloneRemediation
    $workParent = Join-Path $repo 'work'
    foreach ($path in @($repo, $workParent, $private, (Join-Path $repo 'src'))) {
        if (!(Test-Path -LiteralPath $path)) { Fail-Core20 'CORE20_PATH_INVALID' }
        Assert-PlainDirectory $path
    }
    foreach ($path in @(
        (Join-Path $repo 'tools\rebuild7_generation.py'), $processWrapper,
        (Join-Path $private 'migrator-password'), (Join-Path $private 'database-ca')
    )) {
        if (!(Test-Path -LiteralPath $path)) { Fail-Core20 'CORE20_PATH_INVALID' }
        Assert-RegularFile $path
    }
    Assert-PinnedFile $docker '17cbf2f5f5f7693bbeda46e35dc930050b40aff06f41f9f5a69e4e2dd7fc12aa'
    Assert-PinnedFile $node 'f5109dc868ec38703ad8f305e0aceece717cb60d4889873f434017af4e96cccb'
    Assert-PinnedFile $taskkill '56f8cc2c1790c389394733b84c3fb55e10977e9f0fe0c08110ac11f0fe47f05e'
    Assert-PinnedFile $playwrightCli 'a174d071b97fd0480e9ff25625d7bc2880f8a795152236360a6808e74ccaf614'
    Assert-PinnedFile $playwrightPackage '885d03334c4da8dcc0c725d247691da717c1c32a80bc694b060a5a2cf81cf31d'
    Assert-PinnedFile $playwrightLock '860307fabc62b83b8b4d8f1a3a189a59e900675e345f3a9f8aac817469f5fc7c'
    Assert-PinnedFile $playwrightModulesLock '175cec80f2291b07c7a20bd32b701b446dd205799c649a2456b4e66cca806aad'
    Assert-PinnedFile $processWrapper '9e080d2663c71e808db96fe566f0a083de9bcaf4aa025ad89187246e12ae328b'
    Assert-PinnedTree 'C:\Users\nname\AppData\Local\npm-cache\_npx\31e32ef8478fbf80\node_modules' 202 'ccb9e1e10f0cc43996878b10cea243be39c9dd77d6fe7e9f93ec05e8d7f8c246'

    if (!(Test-Path -LiteralPath $workRoot)) { New-Item -ItemType Directory -Path $workRoot | Out-Null }
    Assert-Contained $repo $workRoot
    if (!(Test-Path -LiteralPath $stagingRoot)) { New-Item -ItemType Directory -Path $stagingRoot | Out-Null }
    Assert-Contained $repo $stagingRoot
    if ($recoveryRequested) {
        if (!(Test-Path -LiteralPath $lockPath)) { Fail-Core20 'CORE20_RECOVERY_LOCK_MISSING' }
        Assert-RegularFile $lockPath
        $lock = [IO.File]::Open($lockPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        $lockOwned = $true
        if ($lock.Length -le 0 -or $lock.Length -gt 512) { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
        if ($RecoverGenerationDiagnostic -and $lock.Length -ne 153) { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
        $lock.Position = 0
        $reader = New-Object IO.StreamReader($lock, [Text.Encoding]::ASCII, $false, 1024, $true)
        try { $previousFailure = $reader.ReadToEnd() } finally { $reader.Dispose() }
        if ($DisposableCloneRemediation) {
            if (!(Test-Path -LiteralPath $failureArchiveRoot)) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_MISSING' }
            Assert-Contained $workRoot $failureArchiveRoot
        }
        $stoppedMatch = [regex]::Match($previousFailure, '^(?<run>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\r?\nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=clients,clients-post,bitmap\r?\n?$')
        $captureMatch = [regex]::Match($previousFailure, '^(?<run>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\r?\nrecovered-from=(?<parent>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\r?\nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=\r?\n?$')
        $diagnosticMatch = [regex]::Match($previousFailure, '^(?<run>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\r?\nrecovered-from=(?<parent>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\r?\nfailure=CORE20_CAPTURE_R7_LOCAL_GENERATION_UNAVAILABLE cleanup=\r?\n?$')
        $cloneMatch = [regex]::Match($previousFailure, '^(?<run>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\nrecovered-from=(?<parent>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\nfailure=CORE20_RECOVERY_BITMAP_INVALID cleanup=\n$')
        if ($DisposableCloneRemediation) {
            if (!$cloneMatch.Success -or $cloneMatch.Groups['run'].Value -cne $expectedCloneStoppedDbFailureRun -or
                $cloneMatch.Groups['parent'].Value -cne $expectedClonePolicyFailureRun) {
                Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID'
            }
            $recoveredFailureRun = $cloneMatch.Groups['run'].Value
            $recoveryNeedsDbStart = $true
            $expectedCloneBytes = [Text.Encoding]::ASCII.GetBytes("$expectedCloneStoppedDbFailureRun`nrecovered-from=$expectedClonePolicyFailureRun`nfailure=CORE20_RECOVERY_BITMAP_INVALID cleanup=`n")
            $actualCloneBytes = [Text.Encoding]::ASCII.GetBytes($previousFailure)
            if ($actualCloneBytes.Length -ne $expectedCloneBytes.Length) { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
            for ($index = 0; $index -lt $expectedCloneBytes.Length; $index++) {
                if ($actualCloneBytes[$index] -ne $expectedCloneBytes[$index]) { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
            }
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedClonePolicyFailureRun.lock") "$expectedClonePolicyFailureRun`nrecovered-from=$expectedCloneBrowserFailureRun`nfailure=CORE20_BROWSER_POLICY_FAILED cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedCloneBrowserFailureRun.lock") "$expectedCloneBrowserFailureRun`nrecovered-from=$expectedCloneHostTransportFailureRun`nfailure=CORE20_BROWSER_FAILED cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedCloneHostTransportFailureRun.lock") "$expectedCloneHostTransportFailureRun`nrecovered-from=$expectedCloneIngressFailureRun`nfailure=CORE20_INGRESS_READINESS_STATUS_000 cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedCloneIngressFailureRun.lock") "$expectedCloneIngressFailureRun`nrecovered-from=$expectedCloneReadinessFailureRun`nfailure=CORE20_INGRESS_READINESS_STATUS_000 cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedCloneReadinessFailureRun.lock") "$expectedCloneReadinessFailureRun`nrecovered-from=$expectedCloneIdentityFailureRun`nfailure=CORE20_READINESS_FAILED cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedCloneIdentityFailureRun.lock") "$expectedCloneIdentityFailureRun`nrecovered-from=$expectedCloneParityFailureRun`nfailure=CORE20_CLONE_DATABASE_IDENTITY_INVALID cleanup=clone-nginx-config,clone-database,resources`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedCloneParityFailureRun.lock") "$expectedCloneParityFailureRun`nrecovered-from=$expectedDiagnosticFailureRun`nfailure=CORE20_CAPTURE_R7_GENERATION_MIGRATION_PARITY_UNAVAILABLE cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedDiagnosticFailureRun.lock") "$expectedDiagnosticFailureRun`nrecovered-from=$expectedDiagnosticParentRun`nfailure=CORE20_CAPTURE_R7_LOCAL_GENERATION_UNAVAILABLE cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedDiagnosticParentRun.lock") "$expectedDiagnosticParentRun`nrecovered-from=$expectedDiagnosticGrandparentRun`nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
            Assert-ExactAsciiFile (Join-Path $failureArchiveRoot "$expectedDiagnosticGrandparentRun.lock") "$expectedDiagnosticGrandparentRun`nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=clients,clients-post,bitmap`n" 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID'
        } elseif ($RecoverGenerationDiagnostic) {
            if (!$diagnosticMatch.Success) { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
            $recoveredFailureRun = $diagnosticMatch.Groups['run'].Value
            if ($recoveredFailureRun -cne $expectedDiagnosticFailureRun -or
                $diagnosticMatch.Groups['parent'].Value -cne $expectedDiagnosticParentRun) {
                Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID'
            }
            $recoveryNeedsDbStart = $false
            $expectedDiagnosticBytes = [Text.Encoding]::ASCII.GetBytes("$recoveredFailureRun`nrecovered-from=$($diagnosticMatch.Groups['parent'].Value)`nfailure=CORE20_CAPTURE_R7_LOCAL_GENERATION_UNAVAILABLE cleanup=`n")
            $actualDiagnosticBytes = [Text.Encoding]::ASCII.GetBytes($previousFailure)
            if ($actualDiagnosticBytes.Length -ne $expectedDiagnosticBytes.Length) { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
            for ($index = 0; $index -lt $expectedDiagnosticBytes.Length; $index++) {
                if ($actualDiagnosticBytes[$index] -ne $expectedDiagnosticBytes[$index]) { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
            }
        } elseif ($stoppedMatch.Success) {
            $recoveredFailureRun = $stoppedMatch.Groups['run'].Value
            $recoveryNeedsDbStart = $true
        } elseif ($captureMatch.Success) {
            $recoveredFailureRun = $captureMatch.Groups['run'].Value
            $recoveryNeedsDbStart = $false
        } else { Fail-Core20 'CORE20_RECOVERY_LOCK_INVALID' }
        if (!(Test-Path -LiteralPath $failureArchiveRoot)) { New-Item -ItemType Directory -Path $failureArchiveRoot | Out-Null }
        Assert-Contained $workRoot $failureArchiveRoot
        if ($captureMatch.Success) {
            $parentRun = $captureMatch.Groups['parent'].Value
            $parentArchive = Join-Path $failureArchiveRoot "$parentRun.lock"
            if (!(Test-Path -LiteralPath $parentArchive)) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_MISSING' }
            Assert-RegularFile $parentArchive
            $expectedParentBytes = [Text.Encoding]::ASCII.GetBytes("$parentRun`nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=clients,clients-post,bitmap`n")
            $parentStream = [IO.File]::Open($parentArchive, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
            try {
                if ($parentStream.Length -ne $expectedParentBytes.Length) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
                $actualParentBytes = [byte[]]::new($expectedParentBytes.Length)
                $read = $parentStream.Read($actualParentBytes, 0, $actualParentBytes.Length)
                if ($read -ne $actualParentBytes.Length) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
                for ($index = 0; $index -lt $expectedParentBytes.Length; $index++) {
                    if ($actualParentBytes[$index] -ne $expectedParentBytes[$index]) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
                }
            } finally { $parentStream.Dispose() }
        }
        if ($diagnosticMatch.Success) {
            $parentRun = $diagnosticMatch.Groups['parent'].Value
            $parentArchive = Join-Path $failureArchiveRoot "$parentRun.lock"
            if (!(Test-Path -LiteralPath $parentArchive)) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_MISSING' }
            Assert-RegularFile $parentArchive
            $parentStream = [IO.File]::Open($parentArchive, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
            try {
                if ($parentStream.Length -le 0 -or $parentStream.Length -gt 512) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
                $parentBytes = [byte[]]::new([int]$parentStream.Length)
                $read = $parentStream.Read($parentBytes, 0, $parentBytes.Length)
                if ($read -ne $parentBytes.Length) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
            } finally { $parentStream.Dispose() }
            $parentFailure = [Text.Encoding]::ASCII.GetString($parentBytes)
            $parentMatch = [regex]::Match($parentFailure, '^(?<run>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\nrecovered-from=(?<grandparent>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=\n$')
            if (!$parentMatch.Success -or $parentMatch.Groups['run'].Value -cne $parentRun) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
            $grandparentRun = $parentMatch.Groups['grandparent'].Value
            if ($parentRun -cne $expectedDiagnosticParentRun -or $grandparentRun -cne $expectedDiagnosticGrandparentRun) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
            if ($recoveredFailureRun -ceq $parentRun -or $parentRun -ceq $grandparentRun -or $recoveredFailureRun -ceq $grandparentRun) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
            $expectedParentBytes = [Text.Encoding]::ASCII.GetBytes("$parentRun`nrecovered-from=$grandparentRun`nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=`n")
            if ($parentBytes.Length -ne $expectedParentBytes.Length) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
            for ($index = 0; $index -lt $expectedParentBytes.Length; $index++) {
                if ($parentBytes[$index] -ne $expectedParentBytes[$index]) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
            }
            $grandparentArchive = Join-Path $failureArchiveRoot "$grandparentRun.lock"
            if (!(Test-Path -LiteralPath $grandparentArchive)) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_MISSING' }
            Assert-RegularFile $grandparentArchive
            $expectedGrandparentBytes = [Text.Encoding]::ASCII.GetBytes("$grandparentRun`nfailure=CORE20_OWNER_ACCEPTANCE_UNAVAILABLE cleanup=clients,clients-post,bitmap`n")
            $grandparentStream = [IO.File]::Open($grandparentArchive, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
            try {
                if ($grandparentStream.Length -ne $expectedGrandparentBytes.Length) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
                $actualGrandparentBytes = [byte[]]::new($expectedGrandparentBytes.Length)
                $read = $grandparentStream.Read($actualGrandparentBytes, 0, $actualGrandparentBytes.Length)
                if ($read -ne $actualGrandparentBytes.Length) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
                for ($index = 0; $index -lt $expectedGrandparentBytes.Length; $index++) {
                    if ($actualGrandparentBytes[$index] -ne $expectedGrandparentBytes[$index]) { Fail-Core20 'CORE20_RECOVERY_PARENT_ARCHIVE_INVALID' }
                }
            } finally { $grandparentStream.Dispose() }
        }
        $archivePath = Join-Path $failureArchiveRoot "$recoveredFailureRun.lock"
        if (Test-Path -LiteralPath $archivePath) { Fail-Core20 'CORE20_RECOVERY_ARCHIVE_EXISTS' }
        $archive = [IO.File]::Open($archivePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $archiveBytes = [Text.Encoding]::ASCII.GetBytes($previousFailure)
            $archive.Write($archiveBytes, 0, $archiveBytes.Length)
            $archive.Flush($true)
        } finally { $archive.Dispose() }
        Assert-RegularFile $archivePath
        try {
            $lock.SetLength(0)
            $lock.Position = 0
            $lockBytes = [Text.Encoding]::ASCII.GetBytes("$runId`nrecovered-from=$recoveredFailureRun`n")
            $lock.Write($lockBytes, 0, $lockBytes.Length)
            $lock.Flush($true)
            $lockMarkerCommitted = $true
        } catch {
            try {
                $lock.SetLength(0)
                $lock.Position = 0
                $originalBytes = [Text.Encoding]::ASCII.GetBytes($previousFailure)
                $lock.Write($originalBytes, 0, $originalBytes.Length)
                $lock.Flush($true)
            } catch {}
            throw
        }
    } else {
        if (Test-Path -LiteralPath $lockPath) { Fail-Core20 'CORE20_COORDINATOR_LOCKED' }
        $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        $lockOwned = $true
        $lockBytes = [Text.Encoding]::ASCII.GetBytes("$runId`n")
        $lock.Write($lockBytes, 0, $lockBytes.Length)
        $lock.Flush($true)
        $lockMarkerCommitted = $true
    }

    New-Item -ItemType Directory -Path $staging | Out-Null
    Assert-Contained $stagingRoot $staging
    foreach ($path in @($preCapture, $postCapture, $sourceGuardPrePath, $sourceGuardPostPath, $processRoot)) { New-Item -ItemType Directory -Path $path | Out-Null; Assert-Contained $staging $path }

    if ($recoveryRequested) {
        $dbBefore = Read-Container $dbContainer
        $appBefore = Read-Container $previewApp
        $ingressBefore = Read-Container $previewIngress
        if ([string]$dbBefore.Id -cne $expectedDbId -or [string]$dbBefore.Image -cne $expectedDbImage -or
            [string]$appBefore.Id -cne $expectedAppId -or [bool]$appBefore.State.Running -or
            [string]$ingressBefore.Id -cne $expectedIngressId -or [bool]$ingressBefore.State.Running) {
            Fail-Core20 'CORE20_RECOVERY_BITMAP_INVALID'
        }
        if ($recoveryNeedsDbStart -and [bool]$dbBefore.State.Running) { Fail-Core20 'CORE20_RECOVERY_BITMAP_INVALID' }
        if (!$recoveryNeedsDbStart -and ![bool]$dbBefore.State.Running) { Fail-Core20 'CORE20_RECOVERY_BITMAP_INVALID' }
        if ($recoveryNeedsDbStart) {
            try { Invoke-Docker @('start', $expectedDbId) 30000 | Out-Null } catch {}
        }
        $dbAfter = Read-Container $dbContainer
        if ([string]$dbAfter.Id -cne $expectedDbId -or [string]$dbAfter.Image -cne $expectedDbImage -or ![bool]$dbAfter.State.Running) {
            Fail-Core20 'CORE20_SOURCE_DB_START_FAILED'
        }
        $dbStartedByRecovery = $recoveryNeedsDbStart
        $pgDeadline = New-MonotonicDeadline 60000
        $pgReady = $false
        while ((Get-MonotonicRemainingMilliseconds $pgDeadline) -gt 0) {
            try {
                Invoke-Docker @('exec', $expectedDbId, 'pg_isready', '-h', '127.0.0.1', '-p', '5432', '-U', 'postgres', '-d', 'postgres') 5000 | Out-Null
                $pgReady = $true
                break
            } catch {}
            Start-Sleep -Milliseconds 250
        }
        if (!$pgReady) { Fail-Core20 'CORE20_SOURCE_DB_READINESS_FAILED' }
    }

    Assert-PlainDirectory $tempRoot
    if (!(Test-Path -LiteralPath $evidenceParent)) { New-Item -ItemType Directory -Path $evidenceParent | Out-Null }
    Assert-Contained $tempRoot $evidenceParent
    $currentOwner = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $parentAcl = Get-Acl -LiteralPath $evidenceParent
    if ($parentAcl.Owner -cne $currentOwner -or !$parentAcl.AreAccessRulesCanonical) { Fail-Core20 'CORE20_EVIDENCE_OWNER_INVALID' }
    if (Test-Path -LiteralPath $evidence) { Fail-Core20 'CORE20_EVIDENCE_EXISTS' }
    New-Item -ItemType Directory -Path $evidence | Out-Null
    Assert-Contained $evidenceParent $evidence
    $evidenceAcl = Get-Acl -LiteralPath $evidence
    if ($evidenceAcl.Owner -cne $currentOwner -or !$evidenceAcl.AreAccessRulesCanonical) { Fail-Core20 'CORE20_EVIDENCE_OWNER_INVALID' }

    $boundary = Assert-PreviewBoundary $true
    $appConfigSha = Get-Sha256Text ($boundary.app | ConvertTo-Json -Depth 12 -Compress)
    $ingressConfigSha = Get-Sha256Text ($boundary.ingress | ConvertTo-Json -Depth 12 -Compress)
    $network = @(Invoke-Docker @('network', 'inspect', $dbNetwork) | ConvertFrom-Json)
    if ($network.Count -ne 1 -or ![bool]$network[0].Internal) { Fail-Core20 'CORE20_NETWORK_INVALID' }
    $dbNetworkRows = @(Invoke-Docker @('network', 'inspect', $dbNetwork) | ConvertFrom-Json)
    if ($dbNetworkRows.Count -ne 1 -or [string]$dbNetworkRows[0].Id -notmatch '^[0-9a-f]{64}$') { Fail-Core20 'CORE20_NETWORK_INVALID' }
    $dbNetworkId = [string]$dbNetworkRows[0].Id
    $preNetworkProjectionSha = Get-NetworkProjectionSha
    $preResourceAudit = Wait-ZeroResourceAuditStable 3000
    $listener = $null
    try { $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 18085); $listener.Start() }
    catch { Fail-Core20 'CORE20_PORT_BUSY' }
    finally { if ($null -ne $listener) { $listener.Stop() } }
    Assert-ZeroClients
    $preClients = $true
    $boundaryAdmitted = $true

    if ($DisposableCloneRemediation) {
        $sourceGuardPre = Invoke-SourceGuard $sourceGuardPreContainer $sourceGuardPrePath
        Assert-ZeroClients $sourceDatabase
        New-DisposableCloneDatabase
        Invoke-CloneMigration
        Assert-CloneMigrationState
        Wait-ZeroClients $cloneDatabase
        $preProjection = Invoke-Capture $preCaptureContainer $preCapture $cloneDatabase
        Wait-ZeroClients $cloneDatabase
        Start-ClonePreview
        $cloneBoundary = Assert-ClonePreviewBoundary
        $cloneAppConfigSha = Get-Sha256Text ($cloneBoundary.app | ConvertTo-Json -Depth 12 -Compress)
        $cloneIngressConfigSha = Get-Sha256Text ($cloneBoundary.ingress | ConvertTo-Json -Depth 12 -Compress)
    } else {
        $preProjection = Invoke-Capture $preCaptureContainer $preCapture
        Assert-ZeroClients
        Invoke-Docker @('start', $previewApp) | Out-Null
        $appStarted = $true
        Invoke-Docker @('start', $previewIngress) | Out-Null
        $ingressStarted = $true
    }
    $ready = $false
    $lastIngressStatus = '000'
    $readinessDeadline = New-MonotonicDeadline 90000
    while ((Get-MonotonicRemainingMilliseconds $readinessDeadline) -gt 0) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -NoProxy -SkipHttpErrorCheck -MaximumRedirection 0 -ConnectionTimeoutSeconds 2 -OperationTimeoutSeconds 2 -Uri 'http://127.0.0.1:18085/'
            $statusCode = [int]$response.StatusCode
            $lastIngressStatus = if ($statusCode -ge 100 -and $statusCode -le 599) { $statusCode.ToString('D3') } else { '000' }
            if ($lastIngressStatus -ceq '200') { $ready = $true; break }
        } catch { $lastIngressStatus = '000' }
        $remainingMs = Get-MonotonicRemainingMilliseconds $readinessDeadline
        if ($remainingMs -gt 0) { Start-Sleep -Milliseconds ([Math]::Min(250, $remainingMs)) }
    }
    if (!$ready) { Fail-Core20 "CORE20_INGRESS_READINESS_STATUS_$lastIngressStatus" }
    $readinessPassed = $true

    $browserDeadline = New-MonotonicDeadline 600000
    if (Test-PlaywrightSessionPresent) { Fail-Core20 'CORE20_BROWSER_SESSION_COLLISION' }
    $openOutput = @(Invoke-Playwright @('open', 'about:blank', '--browser', 'chrome', '--idle-timeout', '650000') $false $false 'CORE20_BROWSER_OPEN_FAILED')
    $openPattern = "^### Browser ``$([regex]::Escape($session))`` opened with pid (?<pid>[1-9][0-9]*)\.$"
    $openPidLines = @($openOutput | Where-Object { [string]$_ -match $openPattern })
    if ($openPidLines.Count -ne 1) { Fail-Core20 'CORE20_BROWSER_PID_UNAVAILABLE' }
    $openPidMatch = [regex]::Match([string]$openPidLines[0], $openPattern)
    $browserSessionPid = [int]$openPidMatch.Groups['pid'].Value
    Assert-ExactPlaywrightSessionPid $browserSessionPid | Out-Null
    $browserOpened = $true
    $policyCode = @"
async page => {
page.__core20External = [];
await page.context().route('**/*', async route => {
  const url = new URL(route.request().url());
  if (url.protocol === 'http:' && url.hostname === '127.0.0.1' && url.port === '18085') await route.continue();
  else { page.__core20External.push(route.request().url()); await route.abort('blockedbyclient'); }
});
return JSON.stringify({ ready: 'CORE20_BROWSER_POLICY_READY' });
}
"@
    $policy = @(Invoke-Playwright @('run-code', $policyCode) $true $false 'CORE20_BROWSER_POLICY_FAILED')
    $policyLine = @($policy | Where-Object { [string]$_ -match '^\{.*\}$' })
    if ($policyLine.Count -ne 1) { Fail-Core20 'CORE20_BROWSER_POLICY_FAILED' }
    $policyResult = [string]$policyLine[0] | ConvertFrom-Json
    if ([string]$policyResult.ready -cne 'CORE20_BROWSER_POLICY_READY') { Fail-Core20 'CORE20_BROWSER_POLICY_FAILED' }
    Assert-ExactPlaywrightSessionPid $browserSessionPid | Out-Null

    $desktop = @(
        @('MAP-001', '/'), @('MAP-002', '/services/'), @('MAP-015', '/services/drugie-uslugi/shinomontazh/'),
        @('MAP-008', '/gallery-of-works/'), @('MAP-036', '/gallery-of-works/ford-mondeo'),
        @('MAP-007', '/contacts'), @('MAP-003', '/partners')
    )
    foreach ($target in $desktop) { Add-Screenshot $target[0] $target[1] 'desktop' 1440 900 }
    $mobile = @(
        @('MAP-001', '/'), @('MAP-002', '/services/'), @('MAP-008', '/gallery-of-works/'), @('MAP-007', '/contacts')
    )
    foreach ($target in $mobile) { Add-Screenshot $target[0] $target[1] 'mobile' 390 844 }
    if ($screenshots.Count -ne 11) { Fail-Core20 'CORE20_EVIDENCE_INVALID' }
    $externalCode = "async page => JSON.stringify(page.__core20External || [])"
    $external = @(Invoke-Playwright @('run-code', $externalCode) $true $false 'CORE20_BROWSER_EXTERNAL_FAILED')
    if (@($external | Where-Object { [string]$_ -ceq '[]' }).Count -ne 1) { Fail-Core20 'CORE20_EXTERNAL_REQUEST_DETECTED' }
    Close-ExactPlaywrightSession
    $browserOpened = $false
    $walkthroughComplete = $true
}
catch {
    $failure = [string]$_.Exception.Message
    if ($failure -notmatch '^CORE20_[A-Z0-9_]+$') { $failure = 'CORE20_OWNER_ACCEPTANCE_UNAVAILABLE' }
}
finally {
    if ($lockOwned) {
        if ($boundaryAdmitted) {
            try { Close-ExactPlaywrightSession; $browserOpened = $false }
            catch { $cleanupErrors.Add('browser') }
            if ($DisposableCloneRemediation) {
                try {
                    if ($cloneNginxConfigSha -ne '') {
                        if (!(Test-Path -LiteralPath $cloneNginxConfig) -or
                            (Get-FileHash -LiteralPath $cloneNginxConfig -Algorithm SHA256).Hash.ToLowerInvariant() -cne $cloneNginxConfigSha) {
                            Fail-Core20 'CORE20_INGRESS_CONFIG_INVALID'
                        }
                    } elseif (Test-Path -LiteralPath $cloneNginxConfig) { Fail-Core20 'CORE20_INGRESS_CONFIG_INVALID' }
                } catch { $cleanupErrors.Add('clone-nginx-config') }
                try { Remove-OwnedCloneContainer $cloneIngress 'ingress' $expectedIngressImage $cloneIngressId; $cloneIngressStarted = $false; $cloneIngressId = '' }
                catch { $cleanupErrors.Add('clone-ingress') }
                try { Remove-PreviewNetwork }
                catch { $cleanupErrors.Add('preview-network') }
                try { Remove-OwnedCloneContainer $cloneApp 'app' $expectedAppImage $cloneAppId; $cloneAppStarted = $false; $cloneAppId = '' }
                catch { $cleanupErrors.Add('clone-app') }
                try { Remove-OwnedCloneContainer $cloneMigrationContainer 'migrate' $expectedAppImage $cloneMigrationId; $cloneMigrationId = '' }
                catch { $cleanupErrors.Add('clone-migrate') }
            } else {
                try { Stop-ExactPreviewContainer $previewIngress $expectedIngressId; $ingressStarted = $false }
                catch { $cleanupErrors.Add('ingress') }
                try { Stop-ExactPreviewContainer $previewApp $expectedAppId; $appStarted = $false }
                catch { $cleanupErrors.Add('app') }
            }
            try { Remove-OwnedCaptureContainer $preCaptureContainer }
            catch { $cleanupErrors.Add('pre-container') }
            try {
                if ($DisposableCloneRemediation -and $cloneDatabaseCreated) { Wait-ZeroClients $cloneDatabase }
                Wait-ZeroClients $sourceDatabase
                $postClients = $true
            } catch { $cleanupErrors.Add('clients') }
            try {
                if ($null -ne $preProjection) {
                    $projectionDatabase = if ($DisposableCloneRemediation) { $cloneDatabase } else { $sourceDatabase }
                    $postProjection = Invoke-Capture $postCaptureContainer $postCapture $projectionDatabase
                    Wait-ZeroClients $projectionDatabase
                    foreach ($name in @('release-manifest.json', 'capture-facts.json', 'media-inventory.json')) {
                        if ([string]$preProjection[$name] -cne [string]$postProjection[$name]) { Fail-Core20 'CORE20_SOURCE_DRIFT' }
                    }
                }
            } catch { $cleanupErrors.Add('projection') }
            try { Remove-OwnedCaptureContainer $postCaptureContainer }
            catch { $cleanupErrors.Add('post-container') }
            if ($DisposableCloneRemediation) {
                try { Remove-DisposableCloneDatabase }
                catch { $cleanupErrors.Add('clone-database') }
                try { Remove-OwnedSourceGuardContainer $sourceGuardPreContainer }
                catch { $cleanupErrors.Add('source-pre-container') }
                try {
                    if ($null -ne $sourceGuardPre) {
                        $sourceGuardPost = Invoke-SourceGuard $sourceGuardPostContainer $sourceGuardPostPath
                        if ([string]$sourceGuardPre -cne [string]$sourceGuardPost) { Fail-Core20 'CORE20_SOURCE_DRIFT' }
                    }
                } catch { $cleanupErrors.Add('source-guard') }
                try { Remove-OwnedSourceGuardContainer $sourceGuardPostContainer }
                catch { $cleanupErrors.Add('source-post-container') }
            }
            try { Wait-ZeroClients $sourceDatabase; $postClients = $true }
            catch { $cleanupErrors.Add('clients-post') }
            try {
                $postBoundary = Assert-PreviewBoundary $true
                $postAppConfigSha = Get-Sha256Text ($postBoundary.app | ConvertTo-Json -Depth 12 -Compress)
                $postIngressConfigSha = Get-Sha256Text ($postBoundary.ingress | ConvertTo-Json -Depth 12 -Compress)
                if ($postAppConfigSha -cne $appConfigSha -or $postIngressConfigSha -cne $ingressConfigSha) {
                    Fail-Core20 'CORE20_PREVIEW_IDENTITY_DRIFT'
                }
            } catch { $cleanupErrors.Add('bitmap') }
            try {
                $postResourceAudit = Wait-ZeroResourceAuditStable 10000
                $postNetworkProjectionSha = Get-NetworkProjectionSha
                if ($postNetworkProjectionSha -cne $preNetworkProjectionSha) { Fail-Core20 'CORE20_NETWORK_DRIFT' }
            } catch { $cleanupErrors.Add('resources') }
        }

        try { Remove-ExactRunDirectory $stagingRoot $staging '^[0-9a-f]{32}$' }
        catch { $cleanupErrors.Add('staging') }
        if (Test-Path -LiteralPath $staging) { $cleanupErrors.Add('staging-present') }

        if ($walkthroughComplete -and $cleanupErrors.Count -eq 0 -and $null -eq $failure) {
            try {
                $manifest = [ordered]@{
                    schema = 'estakada.core20-owner-evidence-v1'; runId = $runId
                    recovery = [ordered]@{ sourceDbStarted = $dbStartedByRecovery; archivedFailureRun = $recoveredFailureRun; disposableClone = [bool]$DisposableCloneRemediation }
                    readiness = [ordered]@{ path = '/'; status = 200; timeoutSeconds = 90; passed = $readinessPassed }
                    browser = [ordered]@{ externalRequests = 0; session = 'fresh'; loopbackOnly = $true }
                    acceptanceProjection = [ordered]@{ before = $preProjection; after = $postProjection; equal = $true }
                    sourceGuard = [ordered]@{ before = $sourceGuardPre; after = $sourceGuardPost; equal = if ($DisposableCloneRemediation) { $sourceGuardPre -ceq $sourceGuardPost } else { $true } }
                    sourceClients = [ordered]@{ before = if ($preClients) { 0 } else { -1 }; after = if ($postClients) { 0 } else { -1 } }
                    preview = [ordered]@{
                        before = [ordered]@{ db = 'running'; app = 'stopped'; ingress = 'stopped'; appProjectionSha256 = $appConfigSha; ingressProjectionSha256 = $ingressConfigSha }
                        after = [ordered]@{ db = 'running'; app = 'stopped'; ingress = 'stopped'; appProjectionSha256 = $postAppConfigSha; ingressProjectionSha256 = $postIngressConfigSha }
                        disposable = [ordered]@{ appProjectionSha256 = $cloneAppConfigSha; ingressProjectionSha256 = $cloneIngressConfigSha; nginxConfigSha256 = $cloneNginxConfigSha; databaseRemoved = [bool]$DisposableCloneRemediation }
                    }
                    resources = [ordered]@{ before = $preResourceAudit; after = $postResourceAudit; networkBeforeSha256 = $preNetworkProjectionSha; networkAfterSha256 = $postNetworkProjectionSha; previewNetworkSha256 = $previewNetworkReceiptSha; staging = 0; lock = 'held-until-evidence-commit' }
                    screenshots = @($screenshots)
                }
                $manifestPath = Join-Path $evidence 'manifest.json'
                [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 10), (New-Object Text.UTF8Encoding($false)))
                $files = @(Get-ChildItem -Force -File -LiteralPath $evidence)
                $directories = @(Get-ChildItem -Force -Directory -LiteralPath $evidence)
                $bytes = [long](($files | Measure-Object -Property Length -Sum).Sum)
                $expectedFiles = @(
                    'MAP-001-desktop.png','MAP-002-desktop.png','MAP-015-desktop.png','MAP-008-desktop.png',
                    'MAP-036-desktop.png','MAP-007-desktop.png','MAP-003-desktop.png','MAP-001-mobile.png',
                    'MAP-002-mobile.png','MAP-008-mobile.png','MAP-007-mobile.png','manifest.json'
                ) | Sort-Object
                $actualFiles = @($files.Name | Sort-Object)
                if ($files.Count -ne 12 -or (Compare-Object -CaseSensitive $expectedFiles $actualFiles) -or
                    $directories.Count -ne 0 -or $bytes -gt 128MB -or
                    @($files | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count -ne 0) {
                    Fail-Core20 'CORE20_EVIDENCE_INVALID'
                }
                $evidencePrepared = $true
            } catch { $cleanupErrors.Add('evidence') }
        }

        if (!$evidencePrepared -or $cleanupErrors.Count -ne 0 -or $null -ne $failure) {
            try { Remove-ExactRunDirectory $evidenceParent $evidence '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' }
            catch { $cleanupErrors.Add('owner-evidence') }
        }
        if ($evidencePrepared -and $cleanupErrors.Count -eq 0 -and $null -eq $failure) {
            try {
                $commitMarker = [Text.Encoding]::ASCII.GetBytes("commit-pending=$runId`n")
                $lock.Write($commitMarker, 0, $commitMarker.Length)
                $lock.Flush($true)
                $lock.Dispose()
                $lock = $null
                Remove-Item -LiteralPath $lockPath -Force
                if (Test-Path -LiteralPath $lockPath) { Fail-Core20 'CORE20_LOCK_CLEANUP_FAILED' }
                $lockOwned = $false
                $evidenceComplete = $true
            } catch {
                $cleanupErrors.Add('lock')
                try { Remove-ExactRunDirectory $evidenceParent $evidence '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' }
                catch { $cleanupErrors.Add('owner-evidence') }
            }
        } else {
            if ($lockMarkerCommitted) {
                try {
                    $marker = [Text.Encoding]::ASCII.GetBytes("failure=$($failure ?? 'CORE20_CLEANUP_UNCERTAIN') cleanup=$($cleanupErrors -join ',')`n")
                    $lock.Write($marker, 0, $marker.Length)
                    $lock.Flush($true)
                } catch { $cleanupErrors.Add('failure-marker') }
            }
            try { $lock.Dispose(); $lock = $null } catch { $cleanupErrors.Add('lock-dispose') }
        }
    }
}

if ($null -ne $failure -or $cleanupErrors.Count -ne 0 -or !$evidenceComplete) {
    $reason = if ($null -ne $failure) { $failure } else { 'CORE20_CLEANUP_UNCERTAIN' }
    Write-Error "CORE20_OWNER_ACCEPTANCE_FAILED reason=$reason cleanup=$($cleanupErrors -join ',')" -ErrorAction Continue
    exit 1
}

$evidenceBytes = [long]((Get-ChildItem -Force -File -LiteralPath $evidence | Measure-Object -Property Length -Sum).Sum)
Write-Output "CORE20_OWNER_CAPTURE_OK run=$runId owner_evidence=screenshots11,manifest1,files12,bytes=$evidenceBytes"
Write-Output 'CORE20_OWNER_CLEANUP_OK containers=0 networks=0 volumes=0 staging=0 lock=0 bitmap=exact'
Write-Output "CORE20_OWNER_EVIDENCE_PATH=$evidence"
