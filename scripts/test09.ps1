[CmdletBinding()]
param(
    [ValidateSet('preflight')][string]$Package = 'preflight',
    [switch]$StaticTest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$script:AllowedDockerShapes = @(
    'version',
    'info',
    'ps',
    'image inspect'
)

function Test-ExactSha256Id([string]$Value) {
    return $null -ne $Value -and $Value -cmatch '^sha256:[a-f0-9]{64}$'
}

function Assert-OrdinaryDirectory([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if (!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'T09_PATH_BOUNDARY_REJECTED'
    }
}

function Assert-PrerequisiteDirectory([string]$Path) {
    if (!(Test-Path -LiteralPath $Path)) { throw 'T09_EVIDENCE_UNAVAILABLE' }
    Assert-OrdinaryDirectory $Path
}

function Assert-ContainedPath([string]$Parent, [string]$Child) {
    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $childFull = [IO.Path]::GetFullPath($Child)
    if (!$childFull.StartsWith($parentFull + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'T09_PATH_BOUNDARY_REJECTED'
    }
}

function Assert-SafeRepoFile([string]$Repo, [string]$Path) {
    $repoFull = [IO.Path]::GetFullPath($Repo).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $pathFull = [IO.Path]::GetFullPath($Path)
    Assert-ContainedPath $repoFull $pathFull
    if (!(Test-Path -LiteralPath $pathFull -PathType Leaf)) {
        throw 'T09_EVIDENCE_UNAVAILABLE'
    }
    $current = Get-Item -Force -LiteralPath $pathFull
    while ($true) {
        if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'T09_PATH_BOUNDARY_REJECTED'
        }
        if ([string]::Equals(
                $current.FullName.TrimEnd([IO.Path]::DirectorySeparatorChar),
                $repoFull, [StringComparison]::OrdinalIgnoreCase)) { break }
        $current = $current.Parent
        if ($null -eq $current) { throw 'T09_PATH_BOUNDARY_REJECTED' }
    }
}

function Get-DockerShape([string[]]$Arguments) {
    if ($Arguments.Count -eq 0) { throw 'T09_DOCKER_COMMAND_REJECTED' }
    $shape = if ($Arguments.Count -ge 2 -and $Arguments[0] -eq 'image') {
        $Arguments[0] + ' ' + $Arguments[1]
    } else {
        $Arguments[0]
    }
    if ($script:AllowedDockerShapes -cnotcontains $shape) {
        throw 'T09_DOCKER_COMMAND_REJECTED'
    }
    return $shape
}

function Invoke-DockerReadOnly([string[]]$Arguments) {
    Get-DockerShape $Arguments | Out-Null
    $priorErrorAction = $ErrorActionPreference
    try {
        # Windows PowerShell can promote native stderr to a terminating
        # NativeCommandError under the script-wide Stop preference. Capture the
        # process result first, then map every read failure to the closed code.
        $ErrorActionPreference = 'Continue'
        $output = @(& docker.exe @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    } catch {
        throw 'T09_DOCKER_READ_FAILED'
    } finally {
        $ErrorActionPreference = $priorErrorAction
    }
    if ($exitCode -ne 0) { throw 'T09_DOCKER_READ_FAILED' }
    return $output
}

function ConvertFrom-DockerJson([object[]]$Lines) {
    return (($Lines | ForEach-Object { [string]$_ }) -join "`n") | ConvertFrom-Json
}

function Get-ErrorStatus([string]$Code) {
    if ($Code -in @(
        'T09_DOCKER_UNAVAILABLE',
        'T09_DOCKER_READ_FAILED',
        'T09_EVIDENCE_UNAVAILABLE',
        'T09_FOUNDATION_MANIFEST_UNAVAILABLE'
    )) { return 'BLOCKED' }
    return 'FAIL'
}

function New-PreflightResult(
    [ValidateSet('PASS','FAIL','BLOCKED')][string]$Status,
    [string]$Code,
    [System.Collections.IDictionary]$Checks
) {
    return [ordered]@{
        schema = 'test09-preflight-v1'
        package = 'preflight'
        status = $Status
        code = $Code
        readOnly = $true
        checks = $Checks
    }
}

function Assert-Image([string]$Expected) {
    if (!(Test-ExactSha256Id $Expected)) { throw 'T09_IMAGE_ID_INVALID' }
    $raw = @(Invoke-DockerReadOnly @('image','inspect',$Expected))
    $image = @(ConvertFrom-DockerJson $raw)
    if ($image.Count -ne 1 -or $image[0].Id -cne $Expected -or
        $image[0].Os -cne 'linux' -or $image[0].Architecture -cne 'amd64') {
        throw 'T09_IMAGE_IDENTITY_MISMATCH'
    }
}

function Invoke-StaticTests {
    $failures = New-Object Collections.Generic.List[string]
    function Expect([bool]$Condition, [string]$Name) {
        if (!$Condition) { $failures.Add($Name) }
    }

    Expect (Test-ExactSha256Id ('sha256:' + ('a' * 64))) 'valid-image-id'
    Expect (!(Test-ExactSha256Id ('sha256:' + ('A' * 64)))) 'uppercase-image-id-rejected'
    Expect (!(Test-ExactSha256Id 'latest')) 'tag-rejected'
    Expect ((Get-DockerShape @('version','--format','x')) -ceq 'version') 'version-allowed'
    Expect ((Get-DockerShape @('image','inspect',('sha256:' + ('b' * 64)))) -ceq 'image inspect') 'image-inspect-allowed'
    $sample = ConvertFrom-DockerJson @('[', '{"Id":"sha256:test"}', ']')
    Expect (@($sample).Count -eq 1 -and $sample[0].Id -ceq 'sha256:test') 'multiline-json-ps5'
    Expect ((Get-ErrorStatus 'T09_DOCKER_READ_FAILED') -ceq 'BLOCKED') 'prerequisite-is-blocked'
    Expect ((Get-ErrorStatus 'T09_IMAGE_IDENTITY_MISMATCH') -ceq 'FAIL') 'identity-is-fail'
    $orderedResult = New-PreflightResult 'BLOCKED' 'T09_STATIC_SAMPLE' ([ordered]@{ one = 'ok' })
    $orderedJson = $orderedResult | ConvertTo-Json -Depth 4 -Compress
    Expect ($orderedJson -match '"status":"BLOCKED"' -and $orderedJson -match '"one":"ok"') 'ordered-result-json'
    $missingRejected = $false
    $missingPath = Join-Path ([IO.Path]::GetTempPath()) ('test09-absent-' + [guid]::NewGuid().ToString('N'))
    try { Assert-PrerequisiteDirectory $missingPath } catch {
        $missingRejected = $_.Exception.Message -ceq 'T09_EVIDENCE_UNAVAILABLE'
    }
    Expect $missingRejected 'missing-prerequisite-blocked'

    $rejected = $false
    try { Get-DockerShape @('run','--rm','x') | Out-Null } catch {
        $rejected = $_.Exception.Message -ceq 'T09_DOCKER_COMMAND_REJECTED'
    }
    Expect $rejected 'docker-run-rejected'

    $rejected = $false
    try { Get-DockerShape @('volume','create','x') | Out-Null } catch {
        $rejected = $_.Exception.Message -ceq 'T09_DOCKER_COMMAND_REJECTED'
    }
    Expect $rejected 'docker-volume-create-rejected'

    $ast = [Management.Automation.Language.Parser]::ParseFile(
        $PSCommandPath, [ref]$null, [ref]$null)
    $commands = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.CommandAst]
    }, $true) | ForEach-Object { $_.GetCommandName() } | Where-Object { $_ })
    foreach ($forbidden in @('New-Item','Remove-Item','Set-Item','Start-Process','Invoke-WebRequest')) {
        Expect ($commands -cnotcontains $forbidden) ('forbidden-command-' + $forbidden)
    }

    if ($failures.Count -ne 0) {
        throw ('T09_STATIC_TEST_FAILED:' + ($failures -join ','))
    }
    [ordered]@{
        schema = 'test09-preflight-static-v1'
        status = 'PASS'
        assertions = 17
        dockerCalled = $false
    } | ConvertTo-Json -Compress
}

if ($StaticTest) {
    Invoke-StaticTests
    return
}

$checks = [ordered]@{
    workspace = 'unchecked'
    foundation = 'unchecked'
    docker = 'unchecked'
    images = 'unchecked'
    test09Resources = 'unchecked'
    htmlStorage = 'unchecked'
    logStorage = 'unchecked'
}

try {
    $repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    $work = Join-Path $repo 'work'
    $foundation = Join-Path $work 'foundation'
    $foundationTest = Join-Path $foundation 'test'
    $manifestPath = Join-Path $foundationTest 'manifest.json'
    $test09Root = Join-Path $work 'test09'
    $futureRoot = Join-Path $work 'test09/runs'

    Assert-OrdinaryDirectory $repo
    foreach ($path in @($work,$foundation,$foundationTest)) {
        Assert-PrerequisiteDirectory $path
    }
    foreach ($path in @($test09Root,$futureRoot)) {
        if (Test-Path -LiteralPath $path) { Assert-OrdinaryDirectory $path }
    }
    Assert-ContainedPath $work $futureRoot
    $checks.workspace = 'contained-no-reparse'

    if (!(Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw 'T09_FOUNDATION_MANIFEST_UNAVAILABLE'
    }
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($manifest.environment -cne 'test' -or
        $manifest.composeProject -cne 'nestakada-foundation-test') {
        throw 'T09_FOUNDATION_SCOPE_MISMATCH'
    }
    if ($manifest.active -ne $false) {
        $result = New-PreflightResult 'BLOCKED' 'T09_FOUNDATION_ACTIVE' $checks
        $result | ConvertTo-Json -Depth 6 -Compress
        exit 2
    }
    $checks.foundation = 'manifest-stopped'

    if (!(Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) {
        $result = New-PreflightResult 'BLOCKED' 'T09_DOCKER_UNAVAILABLE' $checks
        $result | ConvertTo-Json -Depth 6 -Compress
        exit 2
    }
    $server = (Invoke-DockerReadOnly @('version','--format','{{json .Server}}')) -join '' | ConvertFrom-Json
    $info = (Invoke-DockerReadOnly @('info','--format','{{json .}}')) -join '' | ConvertFrom-Json
    if ($server.Os -cne 'linux' -or $server.Arch -cne 'amd64' -or
        $info.OSType -cne 'linux' -or $info.Architecture -cne 'x86_64') {
        throw 'T09_DOCKER_PLATFORM_MISMATCH'
    }
    $checks.docker = [ordered]@{
        platform = 'linux/amd64'
        driver = [string]$info.Driver
        memoryBytes = [int64]$info.MemTotal
        rootRecorded = -not [string]::IsNullOrWhiteSpace([string]$info.DockerRootDir)
    }

    $running = @(
        Invoke-DockerReadOnly @('ps','--format','{{.ID}}')
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }
    if ($running.Count -ne 0) {
        $result = New-PreflightResult 'BLOCKED' 'T09_RUNNING_CONTAINERS_PRESENT' $checks
        $result | ConvertTo-Json -Depth 6 -Compress
        exit 2
    }
    $checks.test09Resources = 'no-running-containers'

    $lockPath = Join-Path $repo 'environment/foundation/runtime-images.lock.json'
    $editorPath = Join-Path $repo 'environment/editor-package/local-runtime.json'
    $workerPath = Join-Path $repo 'environment/media-worker/candidate-receipt.json'
    foreach ($path in @($lockPath,$editorPath,$workerPath,$manifestPath)) {
        Assert-SafeRepoFile $repo $path
    }
    $lock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json
    $editor = Get-Content -Raw -LiteralPath $editorPath | ConvertFrom-Json
    $worker = Get-Content -Raw -LiteralPath $workerPath | ConvertFrom-Json
    if ($lock.schemaVersion -ne 1 -or $lock.approvedBy -cne 'D-315' -or
        $lock.status -cne 'independently-reviewed-local-artifacts' -or
        ((@($lock.images.component | Sort-Object) -join ',') -cne 'local-ingress,postgres,python-runtime')) {
        throw 'T09_IMAGE_LOCK_MISMATCH'
    }
    $lockPointers = @($lock.requirements)
    foreach ($entry in @($lock.images)) {
        if ($entry.reference -cne $entry.dockerReportedImageId -or
            !(Test-ExactSha256Id $entry.reference)) { throw 'T09_IMAGE_LOCK_MISMATCH' }
        $lockPointers += @($entry.recipe,$entry.inputs,$entry.receipt)
    }
    foreach ($pointer in $lockPointers) {
        $path = [IO.Path]::GetFullPath((Join-Path $repo $pointer.path))
        Assert-SafeRepoFile $repo $path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $pointer.sha256) {
            throw 'T09_LOCK_INPUT_MISMATCH'
        }
    }
    $base = @($lock.images | Where-Object component -eq 'python-runtime')
    $editorHash = (Get-FileHash -LiteralPath $editorPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($editorHash -cne '634b91630fac20a12aba9ce9f243038aab3c91c202bac0383c2db8ee7139d74b' -or
        $editor.schemaVersion -ne 1 -or $editor.status -cne 'verified-local-candidate' -or
        $editor.authorizedBy -cne 'D-330' -or
        $editor.integrationAuthority -cne 'DEV07-NH-RESUME-001') {
        throw 'T09_EDITOR_RECEIPT_MISMATCH'
    }
    foreach ($input in @($editor.inputs)) {
        $path = [IO.Path]::GetFullPath((Join-Path $repo $input.path))
        Assert-SafeRepoFile $repo $path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $input.sha256) {
            throw 'T09_EDITOR_RECEIPT_MISMATCH'
        }
    }
    if ($base.Count -ne 1 -or $manifest.selectedBaseImage -cne $base[0].reference -or
        $manifest.selectedAppImage -cne $editor.appImageId -or
        $editor.baseImageId -cne $base[0].reference) {
        throw 'T09_IMAGE_MANIFEST_MISMATCH'
    }
    $workerHash = (Get-FileHash -LiteralPath $workerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($workerHash -cne '1d34848ab8b676311f4e2dc1d7661f27545a0b61871f605f5e759178d9359149' -or
        $worker.status -cne 'independently-reviewed-for-local-integration' -or
        $worker.authorizedBy -cne 'D-325' -or
        $worker.baseLock -cne 'environment/foundation/runtime-images.lock.json' -or
        $worker.baseDockerReportedImageId -cne $base[0].reference -or
        !(Test-ExactSha256Id $worker.dockerReportedImageId)) {
        throw 'T09_IMAGE_MANIFEST_MISMATCH'
    }
    foreach ($input in @($worker.inputs)) {
        $path = [IO.Path]::GetFullPath((Join-Path $repo $input.path))
        Assert-SafeRepoFile $repo $path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $input.sha256) {
            throw 'T09_WORKER_RECEIPT_MISMATCH'
        }
    }
    foreach ($input in @($worker.workerSource)) {
        $path = [IO.Path]::GetFullPath((Join-Path $repo ('tools/media_worker/' + $input.name)))
        Assert-SafeRepoFile $repo $path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $input.sha256) {
            throw 'T09_WORKER_RECEIPT_MISMATCH'
        }
    }
    $imageIds = @($lock.images | ForEach-Object reference) +
        @($editor.appImageId,$worker.dockerReportedImageId)
    foreach ($imageId in @($imageIds | Sort-Object -Unique)) { Assert-Image $imageId }
    $checks.images = [ordered]@{ pinned = $true; count = @($imageIds | Sort-Object -Unique).Count }

    # Read-only inspection cannot prove a new independently capped mount. No file,
    # volume, container, sparse substitute or Docker/WSL setting is created here.
    $checks.htmlStorage = [ordered]@{
        status = 'BLOCKED'
        code = 'T09_HTML_BUDGET_UNAVAILABLE'
        tmpfsPossible = ($info.OSType -ceq 'linux' -and [int64]$info.MemTotal -gt 0)
        measuredSetBytes = $false
    }
    $checks.logStorage = [ordered]@{
        status = 'BLOCKED'
        code = 'T09_STORAGE_BACKEND_UNAVAILABLE'
        independentlyCappedDiskBackend = $false
    }
    $result = New-PreflightResult 'BLOCKED' 'T09_STORAGE_BACKEND_UNAVAILABLE' $checks
    $result | ConvertTo-Json -Depth 6 -Compress
    exit 2
} catch {
    $code = [string]$_.Exception.Message
    if ($code -notmatch '^T09_[A-Z0-9_]+$') { $code = 'T09_PREFLIGHT_INTERNAL_ERROR' }
    $status = Get-ErrorStatus $code
    $result = New-PreflightResult $status $code $checks
    $result | ConvertTo-Json -Depth 6 -Compress
    if ($status -ceq 'BLOCKED') { exit 2 }
    exit 1
}
