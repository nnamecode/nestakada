#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('unit','django','config','synthetic','faults','all')]
    [string]$Suite = 'all'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workRoot = Join-Path $repo 'work\r7c-selector'
$authorityPath = Join-Path $workRoot 'authority.json'
$syntheticWorkRoot = Join-Path $repo 'work\r7c-selector-synthetic'
$syntheticAuthorityPath = Join-Path $syntheticWorkRoot 'authority.json'
$composeFile = Join-Path $repo 'environment\rebuild7-cutover\compose.yaml'
$testParent = Join-Path $repo 'work'
$testRoot = Join-Path $testParent ('r7c-selector-test-' + [Guid]::NewGuid().ToString('N'))
$envFile = Join-Path $testRoot 'compose.env'
$secretRoot = Join-Path $testRoot 'secrets'
$utf8 = [Text.UTF8Encoding]::new($false)
$powerShellExecutable = (Get-Process -Id $PID).Path

function Fail-R7CTest([string]$Code) { throw $Code }

function Assert-TestDirectory([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Container)) { Fail-R7CTest 'R7C_TEST_DIRECTORY_INVALID' }
    $item = Get-Item -Force -LiteralPath $Path
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or (Get-Acl -LiteralPath $Path).Owner -cne [Security.Principal.WindowsIdentity]::GetCurrent().Name) { Fail-R7CTest 'R7C_TEST_DIRECTORY_INVALID' }
}

function Initialize-TestPaths {
    if (!(Test-Path -LiteralPath $powerShellExecutable -PathType Leaf) -or [IO.Path]::GetFileName($powerShellExecutable) -cne 'pwsh.exe' -or ((Get-Item -Force -LiteralPath $powerShellExecutable).Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-R7CTest 'R7C_TEST_POWERSHELL_INVALID' }
    if (!(Test-Path -LiteralPath $repo -PathType Container) -or ((Get-Item -Force -LiteralPath $repo).Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail-R7CTest 'R7C_TEST_REPOSITORY_INVALID' }
    if (!(Test-Path -LiteralPath $testParent)) { [void](New-Item -ItemType Directory -Path $testParent) }
    Assert-TestDirectory $testParent
    if (Test-Path -LiteralPath $testRoot) { Fail-R7CTest 'R7C_TEST_DIRECTORY_COLLISION' }
    [void](New-Item -ItemType Directory -Path $testRoot)
    Assert-TestDirectory $testRoot
    [void](New-Item -ItemType Directory -Path $secretRoot)
    Assert-TestDirectory $secretRoot
}

function Write-NewTestFile([string]$Path, [string]$Parent, [string]$Value) {
    if (![string]::Equals([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Path)),[IO.Path]::GetFullPath($Parent),[StringComparison]::OrdinalIgnoreCase)) { Fail-R7CTest 'R7C_TEST_FILE_PATH_INVALID' }
    $stream = [IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $bytes=$utf8.GetBytes($Value);$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true) } finally { $stream.Dispose() }
}

function Remove-TestFile([string]$Path, [string]$Parent) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $full=[IO.Path]::GetFullPath($Path)
    if (![string]::Equals([IO.Path]::GetDirectoryName($full),[IO.Path]::GetFullPath($Parent),[StringComparison]::OrdinalIgnoreCase)) { Fail-R7CTest 'R7C_TEST_FILE_PATH_INVALID' }
    $item=Get-Item -Force -LiteralPath $full
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail-R7CTest 'R7C_TEST_FILE_INVALID' }
    Remove-Item -LiteralPath $full -Force
}

function Invoke-ProcessExact([string]$FileName, [string[]]$Arguments) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $FileName
    $start.UseShellExecute = $false
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::Start($start)
    $process.WaitForExit()
    $exit = $process.ExitCode
    $process.Dispose()
    if ($exit -ne 0) { Fail-R7CTest "R7C_TEST_COMMAND_FAILED_$exit" }
}

function Invoke-ProcessExpectedExit([string]$FileName, [string[]]$Arguments, [int]$ExpectedExit) {
    $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$FileName;$start.UseShellExecute=$false
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    $process=[Diagnostics.Process]::Start($start);$process.WaitForExit();$exit=$process.ExitCode;$process.Dispose()
    if($exit -ne $ExpectedExit){Fail-R7CTest "R7C_TEST_EXPECTED_EXIT_MISMATCH_$exit"}
}

function Read-TestAuthority([string]$Path = $authorityPath) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { Fail-R7CTest 'R7C_TEST_AUTHORITY_MISSING' }
    $authority = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
    if ([string]$authority.schema -cne 'estakada.r7c-authority-v1' -or [string]$authority.appImage -cnotmatch '^sha256:[0-9a-f]{64}$' -or [string]$authority.ingressImage -cnotmatch '^sha256:[0-9a-f]{64}$') { Fail-R7CTest 'R7C_TEST_AUTHORITY_INVALID' }
    return $authority
}

function New-StaticAuthority {
    $runtime = Get-Content -Raw -LiteralPath (Join-Path $repo 'environment\foundation\runtime-images.lock.json') | ConvertFrom-Json
    $editor = Get-Content -Raw -LiteralPath (Join-Path $repo 'environment\editor-package\local-runtime.json') | ConvertFrom-Json
    $project='nestakada-r7c-rehearsal-'+('0'*32)
    $target = { param($role) [pscustomobject]@{generationSha256=('a'*64);storageBindingSha256=('b'*64);dbName="r7c_$role";dbUser="r7c_$($role)_runtime";dbContainer="$project-$role-db";dbImage=[string]($runtime.images|Where-Object component -ceq 'postgres').dockerReportedImageId;dbNetwork="$project-$role-dbnet";sourceVolume="$project-$role-source";mediaVolume="$project-$role-media";secretsVolume="$project-$role-secrets";authorityVolume="$project-$role-authority"} }
    return [pscustomobject]@{schema='estakada.r7c-authority-v1';scope=('rehearsal:'+('0'*32));runId=('0'*32);project=$project;prefix=$project;loopbackPort=18086;appImage=[string]$editor.appImageId;ingressImage=[string]($runtime.images|Where-Object component -ceq 'local-ingress').dockerReportedImageId;selectorVolume="$project-selector";old=(&$target 'old');new=(&$target 'new');durableLocal=[pscustomobject]@{selectorVolume="$project-sentinel-selector";ingressName="$project-sentinel-ingress";ingressId='ABSENT';selectorSha256='ABSENT'}}
}

function Write-TestComposeEnvironment([object]$Authority) {
    $lines = [ordered]@{
        R7C_PROJECT=[string]$Authority.project; R7C_PREFIX=[string]$Authority.prefix; R7C_SCOPE=[string]$Authority.scope
        R7C_SYNTHETIC=$(if([string]$Authority.scope -cmatch '^rehearsal:'){'1'}else{'0'})
        R7C_LOOPBACK_PORT=[string]$Authority.loopbackPort; R7C_APP_IMAGE=[string]$Authority.appImage; R7C_INGRESS_IMAGE=[string]$Authority.ingressImage
        R7C_SELECTOR_VOLUME=[string]$Authority.selectorVolume
        R7C_OLD_DB_NAME=[string]$Authority.old.dbName; R7C_OLD_DB_USER=[string]$Authority.old.dbUser; R7C_OLD_DB_NETWORK=[string]$Authority.old.dbNetwork
        R7C_OLD_GENERATION=[string]$Authority.old.generationSha256; R7C_OLD_STORAGE_BINDING=[string]$Authority.old.storageBindingSha256
        R7C_OLD_SOURCE_VOLUME=[string]$Authority.old.sourceVolume; R7C_OLD_MEDIA_VOLUME=[string]$Authority.old.mediaVolume
        R7C_OLD_SECRETS_VOLUME=[string]$Authority.old.secretsVolume; R7C_OLD_AUTHORITY_VOLUME=[string]$Authority.old.authorityVolume
        R7C_NEW_DB_NAME=[string]$Authority.new.dbName; R7C_NEW_DB_USER=[string]$Authority.new.dbUser; R7C_NEW_DB_NETWORK=[string]$Authority.new.dbNetwork
        R7C_NEW_GENERATION=[string]$Authority.new.generationSha256; R7C_NEW_STORAGE_BINDING=[string]$Authority.new.storageBindingSha256
        R7C_NEW_SOURCE_VOLUME=[string]$Authority.new.sourceVolume; R7C_NEW_MEDIA_VOLUME=[string]$Authority.new.mediaVolume
        R7C_NEW_SECRETS_VOLUME=[string]$Authority.new.secretsVolume; R7C_NEW_AUTHORITY_VOLUME=[string]$Authority.new.authorityVolume
    }
    Write-NewTestFile $envFile $testRoot ((($lines.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "`n") + "`n")
}

function Invoke-Unit([object]$Authority) {
    Invoke-ProcessExact 'docker' @('run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--mount',"type=bind,src=$repo,dst=/project,readonly",'--workdir','/project/tools',[string]$Authority.appImage,'python','-B','-m','unittest','-v','test_rebuild7_selector.py')
}

function Invoke-Generation([object]$Authority) {
    Invoke-ProcessExact 'docker' @('run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--mount',"type=bind,src=$repo,dst=/project,readonly",'--workdir','/project/tools',[string]$Authority.appImage,'python','-B','-m','unittest','-v','test_rebuild7_generation_diagnostic.py')
}

function Invoke-Django([object]$Authority) {
    Write-NewTestFile (Join-Path $secretRoot 'db-password') $secretRoot "r7c-test-only`n"
    Invoke-ProcessExact 'docker' @(
        'run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--mount',"type=bind,src=$(Join-Path $repo 'src'),dst=/app,readonly",'--mount',"type=bind,src=$secretRoot,dst=/run/secrets,readonly",'--workdir','/app',
        '--env','PYTHONDONTWRITEBYTECODE=1','--env','DJANGO_SETTINGS_MODULE=config.settings.local_cutover','--env','ESTAKADA_LOCAL_RESTORE=1',
        '--env','ESTAKADA_DJANGO_SECRET=r7c-test-only','--env','ESTAKADA_ALLOWED_HOSTS=localhost,r7c-probe.invalid','--env','ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password',
        '--env','ESTAKADA_DB_NAME=r7c_test','--env','ESTAKADA_DB_USER=r7c_test','--env','ESTAKADA_DB_HOST=127.0.0.1','--env','ESTAKADA_DB_PORT=5432','--env','ESTAKADA_DB_SSLROOTCERT=/run/secrets/db-password',
        '--env','ESTAKADA_R7C_ROLE=old','--env',('ESTAKADA_R7C_GENERATION_SHA256=' + ('a' * 64)),'--env',('ESTAKADA_R7C_STORAGE_BINDING_SHA256=' + ('b' * 64)),
        [string]$Authority.appImage,'python','-B','manage.py','test','config.tests','--verbosity','2'
    )
}

function Invoke-Config([object]$Authority) {
    Write-TestComposeEnvironment $Authority
    Invoke-ProcessExact 'docker' @('compose','--env-file',$envFile,'--project-name',[string]$Authority.project,'--file',$composeFile,'config','--quiet')
}

function Invoke-Synthetic {
    if (!(Test-Path -LiteralPath $syntheticAuthorityPath -PathType Leaf)) { Fail-R7CTest 'R7C_SYNTHETIC_AUTHORITY_MISSING' }
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Bootstrap
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Switch -TargetRole new
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Switch -TargetRole old
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action QuiesceRehearsal
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action DisposeRehearsal
}

function Invoke-ExpectedCoordinatorFailure(
    [ValidateSet('Bootstrap','Switch')][string]$Action,
    [ValidateSet('old','new')][string]$TargetRole = 'new',
    [ValidateSet('none','after-prepared','after-ingress-stopped','after-selector-committed','after-ingress-started','after-observed','implementation-pre-cas','implementation-post-start')][string]$TestFault = 'none',
    [ValidateNotNullOrEmpty()][string]$Pattern
) {
    $failed=$false
    try { & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action $Action -TargetRole $TargetRole -TestFault $TestFault } catch { if($_.Exception.Message -notmatch $Pattern){throw};$failed=$true }
    if(!$failed){Fail-R7CTest "R7C_EXPECTED_FAILURE_MISSING_$Pattern"}
}

function Invoke-Faults([object]$Authority) {
    Invoke-ProcessExact 'docker' @('run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--env','ESTAKADA_R7C_TESTING=1','--mount',"type=bind,src=$repo,dst=/project,readonly",'--workdir','/project/tools',[string]$Authority.appImage,'python','-B','-m','unittest','-v','test_rebuild7_selector.SelectorFilesystemTests')
    foreach ($stage in @('after-prepared','after-ingress-stopped','after-selector-committed','after-ingress-started','after-observed','implementation-pre-cas','implementation-post-start')) {
        & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Cleanup
        & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Setup
        & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Bootstrap
        $pattern = if($stage -cmatch '^implementation-'){'R7C_IMPLEMENTATION_DRIFT'}else{[regex]::Escape("R7C_INJECTED_$stage")}
        Invoke-ExpectedCoordinatorFailure -Action Switch -TargetRole new -TestFault $stage -Pattern $pattern
        & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Status
        if ($stage -in @('after-selector-committed','after-ingress-started','after-observed')) {
            & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action QuiesceRehearsal
            & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action DisposeRehearsal
        }
    }
    foreach($boundary in @('crash-after-ingress-stopped','crash-after-selector-committed')){
        & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Cleanup
        & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Setup
        & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Bootstrap
        Invoke-ProcessExpectedExit -FileName $powerShellExecutable -Arguments @('-NoLogo','-NoProfile','-File',(Join-Path $PSScriptRoot 'rebuild7-selector.ps1'),'-AuthoritySet','synthetic','-Action','Switch','-TargetRole','new','-TestFault',$boundary) -ExpectedExit 86
        & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Recover
        & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action QuiesceRehearsal
        & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action DisposeRehearsal
    }
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Cleanup
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Setup
    $portBlocker=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse('127.0.0.1'),18086)
    try {
        $portBlocker.Start()
        Invoke-ExpectedCoordinatorFailure -Action Bootstrap -Pattern 'R7C_LOOPBACK_PORT_IN_USE'
    } finally {
        $portBlocker.Stop()
    }
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Cleanup
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Setup
    $caseAuthority=Read-TestAuthority $syntheticAuthorityPath;$caseAuthority.old.storageBindingSha256='c'*64
    [IO.File]::WriteAllText($syntheticAuthorityPath,(ConvertTo-Json $caseAuthority -Depth 12 -Compress)+"`n",$utf8)
    Invoke-ExpectedCoordinatorFailure -Action Bootstrap -Pattern 'R7C_STORAGE_BINDING_MISMATCH'
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Cleanup
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Setup
    $caseAuthority=Read-TestAuthority $syntheticAuthorityPath
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Bootstrap
    Invoke-ProcessExact 'docker' @('stop','--time','1',[string]$caseAuthority.old.dbContainer.Replace('-db','-app'))
    Invoke-ProcessExact 'docker' @('rm',[string]$caseAuthority.old.dbContainer.Replace('-db','-app'))
    Invoke-ProcessExact 'docker' @('create','--name',"$($caseAuthority.project)-old-app",'--label',"estakada.r7c.scope=$($caseAuthority.scope)",'--label','estakada.r7c.synthetic=1',[string]$caseAuthority.appImage,'python','-B','-c','raise SystemExit(0)')
    Invoke-ExpectedCoordinatorFailure -Action Switch -TargetRole new -Pattern 'R7C_TARGET_REPLACED'
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Cleanup
    & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Setup
    $caseAuthority=Read-TestAuthority $syntheticAuthorityPath
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action Bootstrap
    $duplicate="$($caseAuthority.project)-alias-duplicate"
    try {
        Invoke-ProcessExact 'docker' @('run','-d','--name',$duplicate,'--label',"estakada.r7c.scope=$($caseAuthority.scope)",'--label','estakada.r7c.synthetic=1','--network',"$($caseAuthority.project)-old-web",'--network-alias','r7c-old-app',[string]$caseAuthority.appImage,'python','-B','-c','import time;time.sleep(300)')
        Invoke-ExpectedCoordinatorFailure -Action Switch -TargetRole new -Pattern 'R7C_APP_ALIAS_MISMATCH'
    } finally {
        try{Invoke-ProcessExact 'docker' @('stop','--time','1',$duplicate)}catch{}
        try{Invoke-ProcessExact 'docker' @('rm',$duplicate)}catch{}
    }
}

$ownsFixture = $false
$ownsTestRoot = $false
try {
    Initialize-TestPaths
    $ownsTestRoot = $true
    $authority = New-StaticAuthority
    if ($Suite -in @('all','synthetic','faults')) {
        Invoke-Unit $authority
        Invoke-Generation $authority
        Invoke-Django $authority
        Invoke-Config $authority
        $ownsFixture = $true
        & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Setup
        $authority = Read-TestAuthority $syntheticAuthorityPath
        if ($Suite -in @('all','synthetic')) { Invoke-Synthetic }
        if ($Suite -in @('all','faults')) { Invoke-Faults $authority }
    } elseif ($Suite -ceq 'unit') {
        Invoke-Unit $authority
    } elseif ($Suite -ceq 'django') {
        Invoke-Django $authority
    } else {
        Invoke-Config $authority
    }
    Write-Output "R7C_TEST_SUITE_PASS suite=$Suite"
} finally {
    if ($ownsFixture) { & (Join-Path $PSScriptRoot 'setup-rebuild7-selector-synthetic.ps1') -Action Cleanup }
    if ($ownsTestRoot) {
        Assert-TestDirectory $testRoot
        Assert-TestDirectory $secretRoot
        Remove-TestFile $envFile $testRoot
        $secretFile = Join-Path $secretRoot 'db-password'
        Remove-TestFile $secretFile $secretRoot
        Remove-Item -LiteralPath $secretRoot -Force
        Remove-Item -LiteralPath $testRoot -Force
    }
}
