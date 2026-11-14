[CmdletBinding()]
param(
    [ValidateSet('StaticTest','Prepare','Teardown')][string]$Mode = 'StaticTest',
    [string]$RunId = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$foundationRoot = Join-Path $repo 'work/foundation/test'
$manifestPath = Join-Path $foundationRoot 'manifest.json'
$runsRoot = Join-Path $repo 'work/test10/runs'
$utf8 = New-Object Text.UTF8Encoding($false)

function Assert-RunId([string]$Value) {
    if ($Value -cnotmatch '^[a-f0-9]{32}$') { throw 'T10_RUN_ID_REJECTED' }
}
function Assert-Ordinary([string]$Path, [bool]$Directory) {
    $item = Get-Item -Force -LiteralPath $Path
    if (($Directory -and !$item.PSIsContainer) -or (!$Directory -and $item.PSIsContainer) -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'T10_PATH_REJECTED' }
}
function Assert-Contained([string]$Parent, [string]$Child) {
    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $childFull = [IO.Path]::GetFullPath($Child)
    if (!$childFull.StartsWith($parentFull + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) { throw 'T10_PATH_REJECTED' }
}
function Assert-SafeChain([string]$Root, [string]$Path) {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $pathFull = [IO.Path]::GetFullPath($Path)
    if (![string]::Equals($rootFull,$pathFull,[StringComparison]::OrdinalIgnoreCase)) {
        Assert-Contained $rootFull $pathFull
    }
    $current = Get-Item -Force -LiteralPath $pathFull
    while ($true) {
        if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'T10_PATH_REJECTED' }
        if ([string]::Equals($current.FullName.TrimEnd([IO.Path]::DirectorySeparatorChar),
                $rootFull,[StringComparison]::OrdinalIgnoreCase)) { break }
        $current = if ($current -is [IO.DirectoryInfo]) {$current.Parent} else {$current.Directory}
        if ($null -eq $current) { throw 'T10_PATH_REJECTED' }
    }
}
function Write-Receipt([string]$Path, [System.Collections.IDictionary]$Value) {
    $temporary = $Path + '.new'
    if (Test-Path -LiteralPath $temporary) { throw 'T10_RECEIPT_TEMP_EXISTS' }
    [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 8), $utf8)
    if (Test-Path -LiteralPath $Path) {
        [IO.File]::Replace($temporary, $Path, $null)
    } else {
        [IO.File]::Move($temporary, $Path)
    }
}
function Protect-PrivateDirectory([string]$Path) {
    Assert-Ordinary $Path $true
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $directory = [IO.DirectoryInfo]::new($Path)
    $acl = [System.IO.FileSystemAclExtensions]::GetAccessControl(
        $directory,[Security.AccessControl.AccessControlSections]::Access)
    $acl.SetAccessRuleProtection($true,$false)
    $rules = $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])
    foreach ($rule in @($rules)) { $acl.RemoveAccessRuleSpecific($rule) }
    foreach ($sid in @($identity.User,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    [System.IO.FileSystemAclExtensions]::SetAccessControl($directory,$acl)
}
function Docker([string[]]$Arguments) {
    $prior = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& docker.exe @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prior }
    if ($exitCode -ne 0) { throw 'T10_DOCKER_OPERATION_FAILED' }
    return $output
}
function Admin-Arguments($Manifest, [string]$Action, [string]$Id, [string]$SourceHash, [string]$Marker) {
    $private = [IO.Path]::GetFullPath([string]$Manifest.privateDirectory)
    $source = [IO.Path]::GetFullPath([string]$Manifest.sourceDirectory)
    $tool = Join-Path $source 'page_editor/test10_database.py'
    Assert-Ordinary $private $true; Assert-Ordinary $source $true
    foreach ($path in @($tool,(Join-Path $private 'bootstrap-password'),(Join-Path $private 'database-ca'))) {
        Assert-Ordinary $path $false
    }
    return @('run','--rm','--pull=never','--network','nestakada-foundation-test-db',
        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--memory','192m','--memory-swap','192m','--cpus','0.5','--pids-limit','48',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=32m',
        '--mount',"type=bind,source=$source,target=/app,readonly",
        '--mount',"type=bind,source=$private\bootstrap-password,target=/run/secrets/bootstrap-password,readonly",
        '--mount',"type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
        '--workdir','/app',[string]$Manifest.selectedAppImage,'python','-B','page_editor/test10_database.py',
        $Action,$Id,$SourceHash,$Marker)
}
function App-Arguments($Manifest, [string]$Database, [string]$PrivatePath, [string[]]$Command) {
    $source = [IO.Path]::GetFullPath([string]$Manifest.sourceDirectory)
    $foundationPrivate = [IO.Path]::GetFullPath([string]$Manifest.privateDirectory)
    Assert-Ordinary $source $true
    return @('run','--rm','--pull=never','--network','nestakada-foundation-test-db',
        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--user','10001:10001','--memory','768m','--memory-swap','768m','--cpus','1','--pids-limit','128',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=128m',
        '--mount',"type=bind,source=$source,target=/app,readonly",
        '--mount',"type=bind,source=$foundationPrivate\migrator-password,target=/run/secrets/database-password,readonly",
        '--mount',"type=bind,source=$foundationPrivate\django-secret,target=/run/secrets/django-secret,readonly",
        '--mount',"type=bind,source=$foundationPrivate\database-ca,target=/run/secrets/database-ca,readonly",
        '--mount',"type=bind,source=$PrivatePath,target=/run/test10-private",
        '--workdir','/app','--env','DJANGO_SETTINGS_MODULE=estakada.settings.local_http',
        '--env','ESTAKADA_LOCAL_ENV=test','--env',"ESTAKADA_DB_NAME=$Database",
        '--env','ESTAKADA_DB_USER=app_migrator','--env','PYTHONDONTWRITEBYTECODE=1',
        '--env','TEST10_FIXTURE_ADMISSION=D-1040',[string]$Manifest.selectedAppImage,
        'python','-B','manage.py') + $Command
}

if ($Mode -eq 'StaticTest') {
    $failures = New-Object Collections.Generic.List[string]
    try { Assert-RunId ('a' * 32) } catch { $failures.Add('canonical-run-id') }
    try { Assert-RunId ('A' * 32); $failures.Add('uppercase-accepted') } catch {}
    try { Assert-Contained $repo (Join-Path $runsRoot ('a' * 32)) } catch { $failures.Add('contained-run-root') }
    try { Assert-SafeChain $repo $PSCommandPath } catch { $failures.Add('safe-script-chain') }
    try { Assert-Contained $runsRoot $repo; $failures.Add('outside-accepted') } catch {}
    $ast = [Management.Automation.Language.Parser]::ParseFile(
        $PSCommandPath, [ref]$null, [ref]$null)
    $commands = @($ast.FindAll({param($node) $node -is [Management.Automation.Language.CommandAst]},$true) |
        ForEach-Object {$_.GetCommandName()} | Where-Object {$_})
    if ($commands -contains 'Invoke-Expression') { $failures.Add('invoke-expression') }
    if ($failures.Count) { throw ('T10_STATIC_TEST_FAILED:' + ($failures -join ',')) }
    [ordered]@{schema='test10a-fixture-static-v1';status='PASS';assertions=6;dockerCalled=$false} |
        ConvertTo-Json -Compress
    return
}

Assert-RunId $RunId
if (!(Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'T10_FOUNDATION_MANIFEST_REQUIRED' }
Assert-Ordinary $manifestPath $false
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if ($manifest.environment -cne 'test' -or $manifest.composeProject -cne 'nestakada-foundation-test' -or
    $manifest.active -ne $true -or [string]$manifest.selectedAppImage -cnotmatch '^sha256:[a-f0-9]{64}$') {
    throw 'T10_FOUNDATION_IDENTITY_REJECTED'
}
$expectedPrivate = [IO.Path]::GetFullPath((Join-Path $foundationRoot 'private'))
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $foundationRoot 'sources'))
$source = [IO.Path]::GetFullPath([string]$manifest.sourceDirectory)
if ([IO.Path]::GetFullPath([string]$manifest.privateDirectory) -cne $expectedPrivate) {
    throw 'T10_FOUNDATION_PRIVATE_IDENTITY_REJECTED'
}
Assert-SafeChain $repo $foundationRoot
Assert-SafeChain $foundationRoot $expectedPrivate
Assert-SafeChain $foundationRoot $sourceRoot
Assert-SafeChain $sourceRoot $source
$sourceManifest = [IO.Path]::GetFullPath([string]$manifest.sourceManifest)
Assert-SafeChain $foundationRoot $sourceManifest
if ((Get-FileHash -LiteralPath $sourceManifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne
    [string]$manifest.sourceSha256) { throw 'T10_SOURCE_MANIFEST_DRIFT' }
$sourceRows = @(Get-Content -Raw -LiteralPath $sourceManifest | ConvertFrom-Json)
if ($sourceRows.Count -eq 0) { throw 'T10_SOURCE_MANIFEST_EMPTY' }
foreach ($row in $sourceRows) {
    $sourcePath = [IO.Path]::GetFullPath((Join-Path $source ([string]$row.path)))
    Assert-SafeChain $source $sourcePath
    if ([string]$row.sha256 -cnotmatch '^[a-f0-9]{64}$' -or
        (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$row.sha256) {
        throw 'T10_FROZEN_SOURCE_DRIFT'
    }
}
$image = @(Docker @('image','inspect',[string]$manifest.selectedAppImage) | ConvertFrom-Json)
if ($image.Count -ne 1 -or $image[0].Id -cne [string]$manifest.selectedAppImage -or
    $image[0].Os -cne 'linux' -or $image[0].Architecture -cne 'amd64') {
    throw 'T10_APP_IMAGE_IDENTITY_REJECTED'
}
if (!(Test-Path -LiteralPath $runsRoot)) {
    $test10Root = Join-Path $repo 'work/test10'
    if (!(Test-Path -LiteralPath $test10Root)) { New-Item -ItemType Directory -Path $test10Root | Out-Null }
    Assert-Ordinary $test10Root $true
    New-Item -ItemType Directory -Path $runsRoot | Out-Null
}
Assert-Ordinary $runsRoot $true
Assert-SafeChain $repo $runsRoot
$runRoot = Join-Path $runsRoot $RunId
Assert-Contained $runsRoot $runRoot
$privateRoot = Join-Path $runRoot 'private'
$receiptPath = Join-Path $runRoot 'fixture-receipt.json'
$database = 'estakada_test10_' + $RunId

if ($Mode -eq 'Prepare') {
    if (Test-Path -LiteralPath $runRoot) { throw 'T10_RUN_ALREADY_EXISTS' }
    New-Item -ItemType Directory -Path $runRoot,$privateRoot | Out-Null
    Assert-Ordinary $runRoot $true; Assert-Ordinary $privateRoot $true
    Assert-SafeChain $runsRoot $runRoot; Assert-SafeChain $runRoot $privateRoot
    Protect-PrivateDirectory $privateRoot
    $markerBytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {$rng.GetBytes($markerBytes)} finally {$rng.Dispose()}
    $marker = [BitConverter]::ToString($markerBytes).Replace('-','').ToLowerInvariant()
    $receipt = [ordered]@{schema='test10a-fixture-receipt-v1';runId=$RunId;database=$database;
        sourceSha256=[string]$manifest.sourceSha256;appImage=[string]$manifest.selectedAppImage;
        marker=$marker;privateRelative='private/actors.json';evidenceRootRelative='.';status='database_pending'}
    Write-Receipt $receiptPath $receipt
    Assert-SafeChain $runRoot $receiptPath
    Docker (Admin-Arguments $manifest 'prepare' $RunId $receipt.sourceSha256 $receipt.marker) | Out-Null
    $receipt.status='database_created'; Write-Receipt $receiptPath $receipt
    Docker (App-Arguments $manifest $database $privateRoot @('migrate','--noinput')) | Out-Null
    $output = @(Docker (App-Arguments $manifest $database $privateRoot @('test10_fixture','--prepare')))
    $summary = ($output | Select-Object -Last 1) | ConvertFrom-Json
    if ($summary.schema -cne 'test10a-fixture-v1' -or $summary.containsSecrets -ne $false -or
        [string]$summary.fixtureHash -cnotmatch '^[a-f0-9]{64}$') { throw 'T10_FIXTURE_SUMMARY_REJECTED' }
    Assert-Ordinary (Join-Path $privateRoot 'actors.json') $false
    $receipt.status='prepared';$receipt.fixtureHash=[string]$summary.fixtureHash
    $receipt.identifiers=$summary.identifiers;Write-Receipt $receiptPath $receipt
    $summary | ConvertTo-Json -Depth 8 -Compress
    return
}

if (!(Test-Path -LiteralPath $receiptPath -PathType Leaf)) { throw 'T10_RECEIPT_REQUIRED' }
Assert-Ordinary $runRoot $true; Assert-Ordinary $privateRoot $true; Assert-Ordinary $receiptPath $false
Assert-SafeChain $runsRoot $runRoot; Assert-SafeChain $runRoot $privateRoot; Assert-SafeChain $runRoot $receiptPath
$receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
if ($receipt.schema -cne 'test10a-fixture-receipt-v1' -or $receipt.runId -cne $RunId -or
    $receipt.database -cne $database -or $receipt.privateRelative -cne 'private/actors.json' -or
    $receipt.sourceSha256 -cne [string]$manifest.sourceSha256 -or
    $receipt.appImage -cne [string]$manifest.selectedAppImage -or
    [string]$receipt.sourceSha256 -cnotmatch '^[a-f0-9]{64}$' -or
    [string]$receipt.marker -cnotmatch '^[a-f0-9]{64}$' -or
    $receipt.status -cnotin @('database_pending','database_created','prepared','prepare_failed','database_removed','secrets_removed')) { throw 'T10_RECEIPT_IDENTITY_REJECTED' }
if ($receipt.status -cnotin @('database_removed','secrets_removed')) {
    Docker (Admin-Arguments $manifest 'teardown' $RunId $receipt.sourceSha256 $receipt.marker) | Out-Null
    $receipt.status='database_removed';$receipt.databaseRemovedAt=[DateTimeOffset]::UtcNow.ToString('o')
    Write-Receipt $receiptPath $receipt
}
$actors = Join-Path $privateRoot 'actors.json'
if ($receipt.status -ne 'secrets_removed') {
    if (Test-Path -LiteralPath $actors) {
        Assert-SafeChain $privateRoot $actors
        Assert-Ordinary $actors $false
        Remove-Item -LiteralPath $actors
    }
    $receipt.status='secrets_removed';$receipt.secretsRemovedAt=[DateTimeOffset]::UtcNow.ToString('o')
    Write-Receipt $receiptPath $receipt
}
$receipt.status='removed';$receipt.removedAt=[DateTimeOffset]::UtcNow.ToString('o')
Write-Receipt $receiptPath $receipt
[ordered]@{schema='test10a-fixture-teardown-v1';status='PASS';runId=$RunId;databaseRemoved=$true;
    privateSecretsRemoved=!(Test-Path -LiteralPath $actors);evidenceRetained=$true} | ConvertTo-Json -Compress
