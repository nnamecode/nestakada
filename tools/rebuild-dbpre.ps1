$script:Contract = 'rb1-dbpre-v1'

function Stop-DbpreFailure([string]$Code = 'DBPRE_FAILED') {
    $allowed = @(
        'DBPRE_FAILED','DBPRE_FAILED_PRECHECK','DBPRE_FAILED_START',
        'DBPRE_FAILED_ROLE','DBPRE_FAILED_READ',
        'DBPRE_FAILED_READ_SQL','DBPRE_FAILED_READ_ENVELOPE',
        'DBPRE_FAILED_READ_CONTRACT','DBPRE_FAILED_READ_OUTPUT',
        'DBPRE_FAILED_READ_CONTRACT_COUNTS','DBPRE_FAILED_READ_CONTRACT_BINDING',
        'DBPRE_FAILED_READ_CONTRACT_USAGE','DBPRE_FAILED_READ_CONTRACT_RECON',
        'DBPRE_FAILED_MEDIA_SOURCE_SESSION','DBPRE_FAILED_MEDIA_SOURCE_DESCRIPTOR',
        'DBPRE_FAILED_MEDIA_SOURCE_IMAGE','DBPRE_FAILED_MEDIA_SOURCE_VOLUME',
        'DBPRE_FAILED_MEDIA_SOURCE_CREATE','DBPRE_FAILED_MEDIA_SOURCE_IDENTITY',
        'DBPRE_FAILED_MEDIA_SOURCE_VERIFY','DBPRE_FAILED_MEDIA_SOURCE_CLEANUP',
        'DBPRE_FAILED_MEDIA_SOURCE_UNKNOWN_ISOLATED',
        'DBPRE_FAILED_CLEANUP_ROLE','DBPRE_FAILED_CLEANUP_CONTAINER_FILES',
        'DBPRE_FAILED_CLEANUP_HOST_SECRET','DBPRE_FAILED_CLEANUP_COMPOSE',
        'DBPRE_FAILED_CLEANUP_ROLE_IDENTITY','DBPRE_FAILED_CLEANUP_ROLE_ROLE_FLAGS',
        'DBPRE_FAILED_CLEANUP_ROLE_VALID_UNTIL','DBPRE_FAILED_CLEANUP_ROLE_SETTINGS',
        'DBPRE_FAILED_CLEANUP_ROLE_SESSIONS',
        'DBPRE_FAILED_CLEANUP_ROLE_RELATIONS','DBPRE_FAILED_CLEANUP_ROLE_PRIVILEGES',
        'DBPRE_FAILED_CLEANUP_ROLE_REVOKE_DROP'
    )
    if ($Code -cnotin $allowed) { $Code = 'DBPRE_FAILED' }
    [Console]::Error.WriteLine(
        ('{{"contract":"{0}","status":"FAIL","code":"{1}"}}' -f $script:Contract,$Code))
    exit 1
}

trap {
    Stop-DbpreFailure
}

if ($args.Count -ne 2 -or $args[0] -cne '-ApprovedGate' -or
    $args[1] -cnotin @('RB1-READ-Q001','RB1-MEDIA-BIND-Q001','RB1-MEDIA-SOURCE-Q001')) {
    Stop-DbpreFailure
}
$ApprovedGate = [string]$args[1]
$mediaBinding = $ApprovedGate -ceq 'RB1-MEDIA-BIND-Q001'
$mediaSource = $ApprovedGate -ceq 'RB1-MEDIA-SOURCE-Q001'
$mediaScoped = $mediaBinding -or $mediaSource
if ($mediaBinding) { $script:Contract = 'rb1-media-db-bind-v4' }
if ($mediaSource) { $script:Contract = 'rb1-media-source-v1' }

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work = Join-Path $repo 'work/foundation/dev'
$private = Join-Path $work 'private'
$manifestPath = Join-Path $work 'manifest.json'
$envFile = Join-Path $work 'compose.env'
$composeFile = Join-Path $repo 'environment/foundation/compose.yaml'
$project = 'nestakada-foundation-dev'
$container = 'nestakada-foundation-dev-db'
$database = 'estakada_foundation'
$role = 'estakada_rebuild_reader'
$hostSecret = Join-Path $private 'rebuild-reader-password'
$containerSecret = '/var/run/postgresql/rebuild-reader-password'
$containerPassfile = '/var/run/postgresql/rebuild-reader.pgpass'
$dbpreTables = @(
    'accounts_pagegrant',
    'accounts_userprofile',
    'auth_user',
    'content_page',
    'content_route',
    'media_library_asset',
    'media_library_assetfile',
    'media_library_assetusage',
    'media_library_mediafolder',
    'media_library_pagemediahome',
    'page_versions_pagecontentstate',
    'page_versions_pagerevision',
    'shared_content_sharedblock',
    'shared_content_sharedrevision'
)
$mediaBindingTables = @(
    'content_page',
    'media_library_asset',
    'media_library_assetfile',
    'media_library_assetusage',
    'page_versions_pagecontentstate',
    'page_versions_pagerevision',
    'shared_content_sharedblock',
    'shared_content_sharedrevision'
)
$expectedTables = if ($mediaScoped) { $mediaBindingTables } else { $dbpreTables }
$grantSqlTables = if ($mediaScoped) {
    'app.content_page,app.media_library_asset,app.media_library_assetfile,app.media_library_assetusage,app.page_versions_pagecontentstate,app.page_versions_pagerevision,app.shared_content_sharedblock,app.shared_content_sharedrevision'
} else {
    'app.accounts_pagegrant,app.accounts_userprofile,app.auth_user,app.content_page,app.content_route,app.media_library_asset,app.media_library_assetfile,app.media_library_assetusage,app.media_library_mediafolder,app.media_library_pagemediahome,app.page_versions_pagecontentstate,app.page_versions_pagerevision,app.shared_content_sharedblock,app.shared_content_sharedrevision'
}
$allowlistSqlNames = (($expectedTables | ForEach-Object { "'$_'" }) -join ',')
$expectedTableCount = $expectedTables.Count
$evidencePath = Join-Path $repo 'docs/analytics-media-evidence.csv'
$mediaSourceSqlPath = Join-Path $repo 'tools/rebuild-media-source.sql'
$verifierCidPath = Join-Path $private 'rebuild-media-verifier.cid'
$verifierLabel = 'nestakada.rebuild.media-source'
$stateVolumeName = "$project-state"

$composeTouched = $false
$roleCreated = $false
$roleOid = $null
$roleValidUntilMicros = $null
$safeResult = $null
$failureCode = 'DBPRE_FAILED_PRECHECK'
$cleanupFailureCode = $null
$verifierEvidence = $null
$verifierName = $null
$dbContainerId = $null
$dbImageId = $null
$stateVolumeIdentity = $null
$unknownIsolated = $false

function Assert-RegularNoLink([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'DBPRE_PATH_REJECTED'
    }
}

function Assert-ExactPrivateAcl([string]$Path) {
    $acl = [System.IO.FileSystemAclExtensions]::GetAccessControl(
        [IO.DirectoryInfo]::new($Path),
        [Security.AccessControl.AccessControlSections]'Access, Owner')
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $systemSid = 'S-1-5-18'
    $ownerSid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if (!$acl.AreAccessRulesProtected -or $ownerSid -ne $currentSid) {
        throw 'DBPRE_PRIVATE_ACL_REJECTED'
    }
    $rules = @($acl.GetAccessRules($true,$false,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2) { throw 'DBPRE_PRIVATE_ACL_REJECTED' }
    $seen = @{}
    $expectedInheritance = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    foreach ($rule in $rules) {
        $sid = $rule.IdentityReference.Value
        if ($seen.ContainsKey($sid) -or
            $rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $rule.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
            $rule.InheritanceFlags -ne $expectedInheritance -or
            $rule.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
            $rule.IsInherited -or
            ($sid -ne $currentSid -and $sid -ne $systemSid)) {
            throw 'DBPRE_PRIVATE_ACL_REJECTED'
        }
        $seen[$sid] = $true
    }
    if (!$seen.ContainsKey($currentSid) -or !$seen.ContainsKey($systemSid)) {
        throw 'DBPRE_PRIVATE_ACL_REJECTED'
    }
}

function Invoke-Docker([string[]]$Arguments) {
    $output = @(& docker.exe @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw 'DBPRE_DOCKER_FAILED' }
    return $output
}

function Invoke-DockerInputExact([string[]]$Arguments,[string]$Payload) {
    if ($Payload -cnotmatch '^[0-9a-f]{96}$') { throw 'DBPRE_DOCKER_INPUT_REJECTED' }
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = (Get-Command docker.exe -CommandType Application -ErrorAction Stop).Source
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardInputEncoding = [Text.UTF8Encoding]::new($false)
    foreach ($argument in $Arguments) { [void]$psi.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $started = $false
    try {
        $started = $process.Start()
        if (!$started) { throw 'DBPRE_DOCKER_INPUT_START_FAILED' }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.Write($Payload)
        $process.StandardInput.Close()
        if (!$process.WaitForExit(10000)) {
            try { $process.Kill($true) } catch { }
            throw 'DBPRE_DOCKER_INPUT_TIMEOUT'
        }
        [void]$stdoutTask.GetAwaiter().GetResult()
        [void]$stderrTask.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw 'DBPRE_DOCKER_INPUT_FAILED' }
    } finally {
        try {
            if ($started) {
                try { if (!$process.HasExited) { $process.Kill($true) } } catch { }
            }
        } finally {
            $process.Dispose()
        }
    }
}

function Invoke-Compose([string[]]$Arguments) {
    return Invoke-Docker (@('compose','--env-file',$envFile,'--project-name',$project,
        '--file',$composeFile) + $Arguments)
}

function Invoke-BootstrapSql([string]$Sql) {
    $arguments = @('exec','-i',$container,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
        '-U','postgres','-d',$database)
    $output = @($Sql | & docker.exe @arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        $cleanupStage = $null
        foreach ($line in $output) {
            foreach ($candidate in @('IDENTITY','ROLE_FLAGS','VALID_UNTIL','SETTINGS','SESSIONS','RELATIONS','PRIVILEGES','REVOKE_DROP')) {
                if ([string]$line -match ("DBPRE_CLEANUP_PROOF_{0}(?:\s|$)" -f $candidate)) {
                    $cleanupStage = $candidate
                }
            }
        }
        if ($cleanupStage) { throw "DBPRE_CLEANUP_PROOF_FAILED_$cleanupStage" }
        throw 'DBPRE_BOOTSTRAP_SQL_FAILED'
    }
    return $output
}

function Invoke-ReaderSql([string]$Sql) {
    $arguments = @('exec','-i','-e',"PGPASSFILE=$containerPassfile",
        '-e','PGSSLMODE=verify-full','-e','PGSSLROOTCERT=/run/secrets/database-ca',
        '-e','PGCONNECT_TIMEOUT=5',$container,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
        '-h','db','-U',$role,'-d',$database)
    $output = @($Sql | & docker.exe @arguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw 'DBPRE_READER_SQL_FAILED' }
    return $output
}

function Remove-ExactSecret {
    if (Test-Path -LiteralPath $hostSecret) {
        $full = [IO.Path]::GetFullPath($hostSecret)
        $root = [IO.Path]::GetFullPath($private) + [IO.Path]::DirectorySeparatorChar
        if (!$full.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) {
            throw 'DBPRE_SECRET_SCOPE_REJECTED'
        }
        Assert-RegularNoLink $hostSecret
        Remove-Item -LiteralPath $hostSecret -Force
    }
}

function New-ExactSecret {
    if (Test-Path -LiteralPath $hostSecret) { throw 'DBPRE_SECRET_PREEXISTS' }
    $bytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $value = [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
    [IO.File]::WriteAllText($hostSecret,$value,(New-Object Text.UTF8Encoding($false)))
    Assert-RegularNoLink $hostSecret
    if ((Get-Item -LiteralPath $hostSecret).Length -ne 96) { throw 'DBPRE_SECRET_FORMAT_REJECTED' }
}

function New-MediaBindingSql([string]$TemplateName = 'rebuild-media-binding.sql') {
    Assert-RegularNoLink $evidencePath
    $expectedDigest = '52823a26c535f6bcbb45601fccad630278d59d421ab5f87b25bb1390d28867ca'
    $bytes = [IO.File]::ReadAllBytes($evidencePath)
    if ($bytes.Length -le 0 -or $bytes.Length -gt 1048576) { throw 'DBPRE_MEDIA_EVIDENCE_SIZE_REJECTED' }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $digest = [Convert]::ToHexString($sha.ComputeHash($bytes)).ToLowerInvariant() }
    finally { $sha.Dispose() }
    if ($digest -cne $expectedDigest) { throw 'DBPRE_MEDIA_EVIDENCE_DIGEST_REJECTED' }
    $csvText = [Text.UTF8Encoding]::new($false,$true).GetString($bytes)
    $roles = @('gallery-original','new_design_asset','trusted_design_svg_not_user_upload','illustration-or-layout')
    $rows = @($csvText | ConvertFrom-Csv | Where-Object {
        $_.role -cin $roles -and $_.local_exists -ceq 'true' -and $_.archive_status -cne 'error_http404'
    })
    $csvText = $null
    $bytes = $null
    if ($rows.Count -ne 301) { throw 'DBPRE_MEDIA_SCOPE_COUNT_REJECTED' }
    $pairs = @{}
    $values = foreach ($row in ($rows | Sort-Object sha256,bytes)) {
        [uint64]$size = 0
        if ($row.sha256 -cnotmatch '^[0-9a-f]{64}$' -or
            ![uint64]::TryParse($row.bytes,[ref]$size)) { throw 'DBPRE_MEDIA_DESCRIPTOR_REJECTED' }
        $pair = '{0}|{1}' -f $row.sha256,$size
        if ($pairs.ContainsKey($pair)) { throw 'DBPRE_MEDIA_PAIR_DUPLICATE' }
        $pairs[$pair] = $true
        $cohort = if ($row.role -ceq 'gallery-original') { 'gallery' } else { 'ordinary' }
        "('$($row.sha256)',$size,'$cohort')"
    }
    if ($pairs.Count -ne 301) { throw 'DBPRE_MEDIA_PAIR_COUNT_REJECTED' }
    if ($TemplateName -cnotin @('rebuild-media-binding.sql','rebuild-media-source.sql')) {
        throw 'DBPRE_MEDIA_SQL_TEMPLATE_REJECTED'
    }
    $sqlPath = Join-Path $repo "tools/$TemplateName"
    Assert-RegularNoLink $sqlPath
    $template = [IO.File]::ReadAllText($sqlPath,[Text.Encoding]::UTF8)
    if (($template.Split('__CANDIDATE_VALUES__').Count - 1) -ne 1) {
        throw 'DBPRE_MEDIA_SQL_TEMPLATE_REJECTED'
    }
    return $template.Replace('__CANDIDATE_VALUES__',($values -join ",`n    "))
}

function Assert-ExactCidFile {
    $privateFull = [IO.Path]::GetFullPath($private)
    $cidFull = [IO.Path]::GetFullPath($verifierCidPath)
    if ([IO.Path]::GetDirectoryName($cidFull) -cne $privateFull) { throw 'DBPRE_CID_SCOPE_REJECTED' }
    Assert-ExactPrivateAcl $private
    Assert-RegularNoLink $verifierCidPath
    $item = Get-Item -Force -LiteralPath $verifierCidPath
    if ($item.Length -cnotin @(64,65,66)) { throw 'DBPRE_CID_SIZE_REJECTED' }
    $acl = [System.IO.FileSystemAclExtensions]::GetAccessControl(
        [IO.FileInfo]::new($cidFull),
        [Security.AccessControl.AccessControlSections]'Access, Owner')
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $systemSid = 'S-1-5-18'
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $currentSid) {
        throw 'DBPRE_CID_ACL_REJECTED'
    }
    $rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2) { throw 'DBPRE_CID_ACL_REJECTED' }
    $seen = @{}
    foreach ($rule in $rules) {
        $sid = $rule.IdentityReference.Value
        if ($seen.ContainsKey($sid) -or !$rule.IsInherited -or
            $rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $rule.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
            ($sid -ne $currentSid -and $sid -ne $systemSid)) {
            throw 'DBPRE_CID_ACL_REJECTED'
        }
        $seen[$sid] = $true
    }
    if (!$seen.ContainsKey($currentSid) -or !$seen.ContainsKey($systemSid)) {
        throw 'DBPRE_CID_ACL_REJECTED'
    }
    $bytes = [IO.File]::ReadAllBytes($cidFull)
    if ($bytes.Length -notin @(64,65,66)) { throw 'DBPRE_CID_SIZE_REJECTED' }
    if (($bytes | Where-Object { $_ -gt 127 }).Count -ne 0) { throw 'DBPRE_CID_FORMAT_REJECTED' }
    if (($bytes.Length -eq 65 -and $bytes[64] -ne 10) -or
        ($bytes.Length -eq 66 -and ($bytes[64] -ne 13 -or $bytes[65] -ne 10))) {
        throw 'DBPRE_CID_FORMAT_REJECTED'
    }
    $id = [Text.Encoding]::ASCII.GetString($bytes,0,64)
    if ($id -cnotmatch '^[0-9a-f]{64}$') { throw 'DBPRE_CID_FORMAT_REJECTED' }
    return $id
}

function Test-ApprovedMediaKey([string]$Key) {
    if ($Key.Length -gt 1024 -or
        $Key -cnotmatch '^img/[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$') {
        return $false
    }
    $device = '^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)'
    foreach ($segment in $Key.Split('/')[1..($Key.Split('/').Count - 1)]) {
        if ($segment.EndsWith('.',[StringComparison]::Ordinal) -or $segment -match $device) { return $false }
    }
    return $true
}

function Test-ExactVerifierIdentity(
    [string]$Id,[string]$Name,[string]$Evidence,[string]$ImageId,[string]$ExpectedCode) {
    $raw = @(Invoke-Docker @('inspect',$Id)) -join "`n"
    $info = @($raw | ConvertFrom-Json)
    if ($info.Count -ne 1) { throw 'DBPRE_VERIFIER_INSPECT_REJECTED' }
    $c = $info[0]
    $security = @($c.HostConfig.SecurityOpt)
    $capDrop = @($c.HostConfig.CapDrop)
    $capAdd = @()
    if ($null -ne $c.HostConfig.CapAdd) { $capAdd = @($c.HostConfig.CapAdd) }
    $mounts = @($c.Mounts)
    $entrypoint = @($c.Config.Entrypoint)
    $cmd = @($c.Config.Cmd)
    if ($c.Id -cne $Id -or $c.Name -cne "/$Name" -or $c.Image -cne $ImageId -or
        $c.Config.Labels.$verifierLabel -cne $Evidence -or
        $c.Config.User -cne '10001:10001' -or
        $c.HostConfig.NetworkMode -cne 'none' -or !$c.HostConfig.ReadonlyRootfs -or
        $c.HostConfig.LogConfig.Type -cne 'none' -or $c.HostConfig.Memory -ne 134217728 -or
        $c.HostConfig.MemorySwap -ne 134217728 -or
        $c.HostConfig.NanoCpus -ne 250000000 -or $c.HostConfig.PidsLimit -ne 16 -or
        $capDrop.Count -ne 1 -or $capDrop[0] -cne 'ALL' -or
        $capAdd.Count -ne 0 -or $c.HostConfig.Privileged -or $c.HostConfig.AutoRemove -or
        $c.HostConfig.RestartPolicy.Name -cne 'no' -or
        $security.Count -ne 1 -or $security[0] -cne 'no-new-privileges' -or
        $entrypoint.Count -ne 1 -or $entrypoint[0] -cne '/usr/local/bin/python' -or
        $cmd.Count -ne 4 -or $cmd[0] -cne '-I' -or $cmd[1] -cne '-S' -or
        $cmd[2] -cne '-c' -or $cmd[3] -cne $ExpectedCode -or
        $mounts.Count -ne 1 -or $mounts[0].Type -cne 'volume' -or
        $mounts[0].Name -cne $stateVolumeName -or $mounts[0].Destination -cne '/state' -or $mounts[0].RW) {
        throw 'DBPRE_VERIFIER_IDENTITY_REJECTED'
    }
    $tmpfs = $c.HostConfig.Tmpfs.'/tmp'
    if ($tmpfs -cne 'rw,nosuid,nodev,noexec,size=16m,uid=10001,gid=10001,mode=1777') {
        throw 'DBPRE_VERIFIER_TMPFS_REJECTED'
    }
}

function Test-ExactVerifierCleanupIdentity(
    [string]$Id,[string]$Name,[string]$Evidence,[string]$ImageId) {
    if ($Id -cnotmatch '^[0-9a-f]{64}$') { throw 'DBPRE_VERIFIER_CLEANUP_ID_REJECTED' }
    $raw = @(Invoke-Docker @('inspect',$Id)) -join "`n"
    $info = @($raw | ConvertFrom-Json)
    if ($info.Count -ne 1 -or $info[0].Id -cne $Id -or $info[0].Name -cne "/$Name" -or
        $info[0].Config.Labels.$verifierLabel -cne $Evidence -or $info[0].Image -cne $ImageId) {
        throw 'DBPRE_VERIFIER_CLEANUP_IDENTITY_REJECTED'
    }
}

function Assert-DbOnlyScope {
    if ($dbContainerId -cnotmatch '^[0-9a-f]{64}$' -or $dbImageId -cnotmatch '^sha256:[0-9a-f]{64}$') {
        throw 'DBPRE_DATABASE_IDENTITY_REJECTED'
    }
    $ids = @(Invoke-Docker @('ps','-aq','--no-trunc','--filter',"label=com.docker.compose.project=$project"))
    if ($ids.Count -ne 1 -or $ids[0] -cne $dbContainerId) { throw 'DBPRE_DATABASE_IDENTITY_REJECTED' }
    $db = @((@(Invoke-Docker @('inspect',$dbContainerId)) -join "`n") | ConvertFrom-Json)
    if ($db.Count -ne 1 -or $db[0].Id -cne $dbContainerId -or $db[0].Image -cne $dbImageId -or
        $db[0].Name -cne "/$container" -or !$db[0].State.Running -or
        $db[0].Config.Labels.'com.docker.compose.project' -cne $project -or
        $db[0].Config.Labels.'com.docker.compose.service' -cne 'db' -or
        $db[0].Config.Labels.'com.docker.compose.oneoff' -cne 'False') {
        throw 'DBPRE_DATABASE_IDENTITY_REJECTED'
    }
}

function Invoke-BoundedProcess([string]$File,[string[]]$Arguments,[string]$Payload,[int]$TimeoutMs) {
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $File
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardInputEncoding = [Text.UTF8Encoding]::new($false)
    foreach ($argument in $Arguments) { [void]$psi.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $started = $false
    try {
        $started = $process.Start()
        if (!$started) { throw 'DBPRE_PROCESS_START_FAILED' }
        $process.StandardInput.Write($Payload)
        $process.StandardInput.Close()
        $stdout = [IO.MemoryStream]::new()
        $stderr = [IO.MemoryStream]::new()
        $outBuffer = New-Object byte[] 257
        $errBuffer = New-Object byte[] 257
        $outTask = $process.StandardOutput.BaseStream.ReadAsync($outBuffer,0,$outBuffer.Length)
        $errTask = $process.StandardError.BaseStream.ReadAsync($errBuffer,0,$errBuffer.Length)
        $outDone = $false
        $errDone = $false
        $watch = [Diagnostics.Stopwatch]::StartNew()
        while (!$outDone -or !$errDone -or !$process.HasExited) {
            if ($watch.ElapsedMilliseconds -gt $TimeoutMs) { throw 'DBPRE_PROCESS_TIMEOUT' }
            if (!$outDone -and $outTask.IsCompleted) {
                $count = $outTask.GetAwaiter().GetResult()
                if ($count -eq 0) { $outDone = $true }
                else {
                    if ($stdout.Length + $count -gt 256) { throw 'DBPRE_PROCESS_OUTPUT_CAP' }
                    $stdout.Write($outBuffer,0,$count)
                    $outBuffer = New-Object byte[] 257
                    $outTask = $process.StandardOutput.BaseStream.ReadAsync($outBuffer,0,$outBuffer.Length)
                }
            }
            if (!$errDone -and $errTask.IsCompleted) {
                $count = $errTask.GetAwaiter().GetResult()
                if ($count -eq 0) { $errDone = $true }
                else {
                    if ($stderr.Length + $count -gt 256) { throw 'DBPRE_PROCESS_OUTPUT_CAP' }
                    $stderr.Write($errBuffer,0,$count)
                    $errBuffer = New-Object byte[] 257
                    $errTask = $process.StandardError.BaseStream.ReadAsync($errBuffer,0,$errBuffer.Length)
                }
            }
            if (!$outDone -or !$errDone -or !$process.HasExited) { Start-Sleep -Milliseconds 2 }
        }
        $watch.Stop()
        $utf8 = [Text.UTF8Encoding]::new($false,$true)
        $stdoutText = $utf8.GetString($stdout.ToArray())
        $stderrText = $utf8.GetString($stderr.ToArray())
        return [ordered]@{ ExitCode=$process.ExitCode; Stdout=$stdoutText; Stderr=$stderrText }
    } finally {
        try { if ($started -and !$process.HasExited) { $process.Kill($true) } } catch { }
        $process.Dispose()
    }
}

function Invoke-MediaVerifier([string]$DescriptorJson,[string]$ImageId) {
    if (Test-Path -LiteralPath $verifierCidPath) { throw 'DBPRE_CID_PREEXISTS' }
    Assert-ExactPrivateAcl $private
    $evidence = $verifierEvidence
    $name = $verifierName
    if ($evidence -cnotmatch '^[0-9a-f]{32}$' -or $name -cne "nestakada-media-source-$evidence") {
        throw 'DBPRE_VERIFIER_IDENTITY_REJECTED'
    }
    $python = @'
import hashlib,json,os,re,stat,sys
fds=[]
try:
    raw=sys.stdin.buffer.read(2049)
    if not raw or len(raw)>2048: raise ValueError()
    obj=json.loads(raw.decode('utf-8','strict'))
    if type(obj) is not dict or set(obj)!={'key','sha256','byteSize'}: raise ValueError()
    key=obj['key']; digest=obj['sha256']; size=obj['byteSize']
    if type(key) is not str or type(digest) is not str or type(size) is not int: raise ValueError()
    if len(key)>1024 or not re.fullmatch(r'img/[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*',key): raise ValueError()
    for segment in key.split('/')[1:]:
        if segment.endswith('.') or re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',segment): raise ValueError()
    if not re.fullmatch(r'[0-9a-f]{64}',digest) or size<0 or size>9223372036854775807: raise ValueError()
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
    fd=os.open('/state/media',flags); fds.append(fd)
    parts=key.split('/')[1:]
    for part in parts[:-1]:
        fd=os.open(part,flags,dir_fd=fd); fds.append(fd)
    final=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd); fds.append(final)
    before=os.fstat(final)
    if not stat.S_ISREG(before.st_mode) or before.st_size!=size: raise ValueError()
    h=hashlib.sha256()
    while True:
        block=os.read(final,1048576)
        if not block: break
        h.update(block)
    after=os.fstat(final)
    if (before.st_dev,before.st_ino,before.st_size)!=(after.st_dev,after.st_ino,after.st_size): raise ValueError()
    if h.hexdigest()!=digest: raise ValueError()
    os.write(1,b'RB1SRC_OK\n')
except BaseException:
    os.write(1,b'RB1SRC_FAIL\n')
    sys.exit(1)
finally:
    for fd in reversed(fds):
        try: os.close(fd)
        except OSError: pass
'@
    $created = $false
    $startAttempted = $false
    $knownFailureClean = $false
    $cleanIdentity = $false
    $id = $null
    try {
        Assert-DbOnlyScope
        $nameCollisions = @(Invoke-Docker @('ps','-aq','--filter',"name=^/$name$"))
        $labelCollisions = @(Invoke-Docker @('ps','-aq','--filter',"label=$verifierLabel"))
        if ($nameCollisions.Count -ne 0 -or $labelCollisions.Count -ne 0) { throw 'DBPRE_VERIFIER_COLLISION' }
        Invoke-Docker @('create','--cidfile',$verifierCidPath,'--name',$name,
            '--label',"$verifierLabel=$evidence",'--network','none','--read-only','--log-driver','none',
            '--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--memory','128m','--memory-swap','128m','--cpus','0.25','--pids-limit','16',
            '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=16m,uid=10001,gid=10001,mode=1777',
            '--mount',"type=volume,source=$stateVolumeName,target=/state,readonly",
            '--entrypoint','/usr/local/bin/python',$ImageId,'-I','-S','-c',$python) | Out-Null
        $created = $true
        $id = Assert-ExactCidFile
        Test-ExactVerifierIdentity $id $name $evidence $ImageId $python
        $cleanIdentity = $true
        $startAttempted = $true
        $docker = (Get-Command docker.exe -CommandType Application -ErrorAction Stop).Source
        $result = Invoke-BoundedProcess $docker @('start','-a','-i',$id) $DescriptorJson 15000
        if ($result.ExitCode -ne 0 -or $result.Stdout -cne "RB1SRC_OK`n" -or $result.Stderr -cne '') {
            Test-ExactVerifierIdentity $id $name $evidence $ImageId $python
            Invoke-Docker @('rm',$id) | Out-Null
            $created = $false
            if (@(Invoke-Docker @('ps','-aq','--filter',"id=$id")).Count -ne 0 -or
                @(Invoke-Docker @('ps','-aq','--filter',"name=^/$name$")).Count -ne 0 -or
                @(Invoke-Docker @('ps','-aq','--filter',"label=$verifierLabel=$evidence")).Count -ne 0) {
                throw 'DBPRE_VERIFIER_ABSENCE_REJECTED'
            }
            [void](Assert-ExactCidFile)
            Remove-Item -LiteralPath $verifierCidPath -Force
            $knownFailureClean = $true
            throw 'DBPRE_VERIFIER_RESULT_REJECTED'
        }
        Test-ExactVerifierIdentity $id $name $evidence $ImageId $python
        Invoke-Docker @('rm',$id) | Out-Null
        $created = $false
        if (@(Invoke-Docker @('ps','-aq','--filter',"id=$id")).Count -ne 0 -or
            @(Invoke-Docker @('ps','-aq','--filter',"name=^/$name$")).Count -ne 0 -or
            @(Invoke-Docker @('ps','-aq','--filter',"label=$verifierLabel=$evidence")).Count -ne 0) {
            throw 'DBPRE_VERIFIER_ABSENCE_REJECTED'
        }
        [void](Assert-ExactCidFile)
        Remove-Item -LiteralPath $verifierCidPath -Force
        return $true
    } catch {
        $originalError = $_.Exception.Message
        if ($startAttempted -and !$knownFailureClean) { throw 'DBPRE_MEDIA_SOURCE_UNKNOWN_ISOLATED' }
        if ($created) {
            if (!$cleanIdentity -or !$id) {
                if (!$id) { throw 'DBPRE_VERIFIER_CLEANUP_REQUIRED' }
                try {
                    $validatedId = Assert-ExactCidFile
                    if ($validatedId -cne $id) { throw 'DBPRE_VERIFIER_CLEANUP_ID_REJECTED' }
                    Test-ExactVerifierCleanupIdentity $id $name $evidence $ImageId
                    Invoke-Docker @('rm','-f',$id) | Out-Null
                    if (@(Invoke-Docker @('ps','-aq','--filter',"id=$id")).Count -ne 0 -or
                        @(Invoke-Docker @('ps','-aq','--filter',"name=^/$name$")).Count -ne 0 -or
                        @(Invoke-Docker @('ps','-aq','--filter',"label=$verifierLabel=$evidence")).Count -ne 0) {
                        throw 'DBPRE_VERIFIER_ABSENCE_REJECTED'
                    }
                    [void](Assert-ExactCidFile)
                    Remove-Item -LiteralPath $verifierCidPath -Force
                    $created = $false
                } catch { throw 'DBPRE_VERIFIER_CLEANUP_REQUIRED' }
                throw $originalError
            }
            try {
                $validatedId = Assert-ExactCidFile
                if ($validatedId -cne $id) { throw 'DBPRE_VERIFIER_CLEANUP_ID_REJECTED' }
                Test-ExactVerifierCleanupIdentity $id $name $evidence $ImageId
                Invoke-Docker @('rm','-f',$id) | Out-Null
                if (@(Invoke-Docker @('ps','-aq','--filter',"id=$id")).Count -ne 0 -or
                    @(Invoke-Docker @('ps','-aq','--filter',"name=^/$name$")).Count -ne 0 -or
                    @(Invoke-Docker @('ps','-aq','--filter',"label=$verifierLabel=$evidence")).Count -ne 0) {
                    throw 'DBPRE_VERIFIER_ABSENCE_REJECTED'
                }
                [void](Assert-ExactCidFile)
                Remove-Item -LiteralPath $verifierCidPath -Force
                $created = $false
            } catch {
                throw 'DBPRE_VERIFIER_CLEANUP_REQUIRED'
            }
        } elseif (Test-Path -LiteralPath $verifierCidPath) {
            throw 'DBPRE_VERIFIER_CLEANUP_REQUIRED'
        }
        throw
    }
}

function Invoke-MediaSourceSession([string]$Sql,[string]$ImageId) {
    $arguments = @('exec','-i','-e',"PGPASSFILE=$containerPassfile",
        '-e','PGSSLMODE=verify-full','-e','PGSSLROOTCERT=/run/secrets/database-ca',
        '-e','PGCONNECT_TIMEOUT=5',$container,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
        '-h','db','-U',$role,'-d',$database)
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = (Get-Command docker.exe -CommandType Application -ErrorAction Stop).Source
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardInputEncoding = [Text.UTF8Encoding]::new($false)
    foreach ($argument in $arguments) { [void]$psi.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new(); $process.StartInfo = $psi
    $started = $false
    $bodyFailed = $false
    try {
        $started = $process.Start()
        if (!$started) { throw 'DBPRE_MEDIA_SESSION_START_REJECTED' }
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.WriteLine($Sql)
        $process.StandardInput.Flush()
        $firstTask = $process.StandardOutput.ReadLineAsync()
        if (!$firstTask.Wait(5000)) { throw 'DBPRE_MEDIA_SESSION_TIMEOUT' }
        $first = $firstTask.Result
        $secondTask = $process.StandardOutput.ReadLineAsync()
        if (!$secondTask.Wait(5000)) { throw 'DBPRE_MEDIA_SESSION_TIMEOUT' }
        $second = $secondTask.Result
        if ($null -eq $first -or $null -eq $second -or $second -cne 'RB1SRC_READY' -or
            $first -cnotmatch '^RB1SRC\|([A-Za-z0-9+/]+={0,2})\|([0-9a-f]{64})\|([0-9]+)\|1\|2\|1$') {
            throw 'DBPRE_MEDIA_DESCRIPTOR_REJECTED'
        }
        $encodedKey = $Matches[1]
        $descriptorSha = $Matches[2]
        $descriptorSize = $Matches[3]
        $keyBytes = [Convert]::FromBase64String($encodedKey)
        $key = [Text.UTF8Encoding]::new($false,$true).GetString($keyBytes)
        if (!(Test-ApprovedMediaKey $key)) {
            throw 'DBPRE_MEDIA_DESCRIPTOR_REJECTED'
        }
        [uint64]$byteSize = 0
        if (![uint64]::TryParse($descriptorSize,[ref]$byteSize) -or $byteSize -gt [int64]::MaxValue) {
            throw 'DBPRE_MEDIA_DESCRIPTOR_REJECTED'
        }
        $descriptor = [ordered]@{ key=$key; sha256=$descriptorSha; byteSize=$byteSize }
        $descriptorJson = $descriptor | ConvertTo-Json -Compress
        if ([Text.Encoding]::UTF8.GetByteCount($descriptorJson) -gt 2048) { throw 'DBPRE_MEDIA_DESCRIPTOR_REJECTED' }
        [void](Invoke-MediaVerifier $descriptorJson $ImageId)
        return [ordered]@{ unmatchedDescriptors=1; resolvedFiles=1; eligibleUsages=2; excludedUsages=1 }
    } catch {
        $bodyFailed = $true
        throw
    } finally {
        $sessionCleanupFailed = $false
        if ($started) {
            try {
                $remainingTask = $process.StandardOutput.ReadToEndAsync()
                $process.StandardInput.WriteLine('ROLLBACK;')
                $process.StandardInput.WriteLine('\q')
                $process.StandardInput.Close()
                if (!$process.WaitForExit(5000)) {
                    try { $process.Kill($true) } catch { }
                    $sessionCleanupFailed = $true
                }
                $remaining = $remainingTask.GetAwaiter().GetResult()
                $stderr = $stderrTask.GetAwaiter().GetResult()
                if ($process.ExitCode -ne 0 -or $remaining -cne '' -or $stderr -cne '' -or
                    [Text.Encoding]::UTF8.GetByteCount($remaining) -gt 256 -or
                    [Text.Encoding]::UTF8.GetByteCount($stderr) -gt 256) {
                    $sessionCleanupFailed = $true
                }
            } catch { $sessionCleanupFailed = $true }
        }
        $process.Dispose()
        if ($sessionCleanupFailed -and !$bodyFailed) { throw 'DBPRE_MEDIA_SESSION_CLEANUP_REJECTED' }
    }
}

$createSql = @'
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
  IF current_database() <> 'estakada_foundation' THEN RAISE EXCEPTION 'target'; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='estakada_rebuild_reader') THEN RAISE EXCEPTION 'preexisting'; END IF;
END $$;
DO $$
DECLARE
  secret text := btrim(pg_read_file('/var/run/postgresql/rebuild-reader-password'));
  expires text := (clock_timestamp() + interval '15 minutes')::text;
BEGIN
  IF secret !~ '^[0-9a-f]{96}$' THEN RAISE EXCEPTION 'secret'; END IF;
  EXECUTE format(
    'CREATE ROLE estakada_rebuild_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1 PASSWORD %L VALID UNTIL %L',
    secret, expires);
END $$;
ALTER ROLE estakada_rebuild_reader SET default_transaction_read_only=on;
ALTER ROLE estakada_rebuild_reader SET search_path=pg_catalog,app;
GRANT CONNECT ON DATABASE estakada_foundation TO estakada_rebuild_reader;
GRANT USAGE ON SCHEMA app TO estakada_rebuild_reader;
GRANT SELECT ON TABLE __GRANT_TABLES__ TO estakada_rebuild_reader;
DO $$
DECLARE
  rid oid;
  allowed oid[];
BEGIN
  SELECT oid INTO STRICT rid FROM pg_roles WHERE rolname='estakada_rebuild_reader';
  SELECT array_agg(c.oid ORDER BY c.oid) INTO allowed
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='app' AND c.relkind IN ('r','p') AND c.relname=ANY(ARRAY[__ALLOWLIST_NAMES__]);
  IF cardinality(allowed) <> __EXPECTED_TABLE_COUNT__ THEN RAISE EXCEPTION 'allowlist'; END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=rid OR roleid=rid) THEN RAISE EXCEPTION 'membership'; END IF;
  IF EXISTS (SELECT 1 FROM pg_database WHERE datdba=rid)
     OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner=rid)
     OR EXISTS (SELECT 1 FROM pg_class WHERE relowner=rid AND relkind IN ('r','p','S'))
  THEN RAISE EXCEPTION 'ownership'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_database d WHERE
      (d.datallowconn AND has_database_privilege(rid,d.oid,'CONNECT'))
        IS DISTINCT FROM (d.datname='estakada_foundation')
      OR (d.datallowconn AND has_database_privilege(rid,d.oid,'CONNECT')
          AND has_database_privilege(rid,d.oid,'CREATE'))
      OR (d.datallowconn AND has_database_privilege(rid,d.oid,'CONNECT')
          AND has_database_privilege(rid,d.oid,'TEMP')))
  THEN RAISE EXCEPTION 'database-privileges'; END IF;
  -- System schemas are excluded only for catalog-backed identity and privilege proof.
  IF EXISTS (
    SELECT 1 FROM pg_namespace n
    WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND (
      has_schema_privilege(rid,n.oid,'USAGE') IS DISTINCT FROM (n.nspname='app')
      OR has_schema_privilege(rid,n.oid,'CREATE')))
  THEN RAISE EXCEPTION 'schema-privileges'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
      AND c.relkind IN ('r','p','v','m','f') AND (
      has_table_privilege(rid,c.oid,'SELECT') IS DISTINCT FROM (c.oid=ANY(allowed)) OR
      (c.oid<>ALL(allowed) AND has_any_column_privilege(rid,c.oid,'SELECT')) OR
      has_table_privilege(rid,c.oid,'INSERT') OR has_table_privilege(rid,c.oid,'UPDATE') OR
      has_table_privilege(rid,c.oid,'DELETE') OR has_table_privilege(rid,c.oid,'TRUNCATE') OR
      has_table_privilege(rid,c.oid,'REFERENCES') OR has_table_privilege(rid,c.oid,'TRIGGER') OR
      has_table_privilege(rid,c.oid,'MAINTAIN') OR
      has_any_column_privilege(rid,c.oid,'INSERT') OR has_any_column_privilege(rid,c.oid,'UPDATE') OR
      has_any_column_privilege(rid,c.oid,'REFERENCES')))
  THEN RAISE EXCEPTION 'table-privileges'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind='S' AND
      (has_sequence_privilege(rid,c.oid,'USAGE') OR has_sequence_privilege(rid,c.oid,'SELECT') OR
       has_sequence_privilege(rid,c.oid,'UPDATE')))
  THEN RAISE EXCEPTION 'sequence-privileges'; END IF;
END $$;
SELECT oid::text||'|'||floor(extract(epoch FROM rolvaliduntil)*1000000)::bigint::text
FROM pg_roles WHERE rolname='estakada_rebuild_reader';
COMMIT;
'@
$createSql = $createSql.Replace('__GRANT_TABLES__',$grantSqlTables)
$createSql = $createSql.Replace('__ALLOWLIST_NAMES__',$allowlistSqlNames)
$createSql = $createSql.Replace('__EXPECTED_TABLE_COUNT__',[string]$expectedTableCount)

$aggregateSql = @'
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='2000ms';
SET LOCAL lock_timeout='250ms';
SET LOCAL idle_in_transaction_session_timeout='5000ms';
DO $$
BEGIN
  IF current_user <> 'estakada_rebuild_reader'
     OR current_database() <> 'estakada_foundation'
     OR current_setting('transaction_read_only') <> 'on'
     OR current_setting('transaction_isolation') <> 'repeatable read'
     OR NOT COALESCE((SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()),false)
  THEN RAISE EXCEPTION 'identity'; END IF;
END $$;
WITH
selected_current AS (
  SELECT s.page_id,r.id,r.sequence,r.author_id,r.payload
  FROM app.page_versions_pagecontentstate s
  JOIN app.page_versions_pagerevision r ON r.id=s.current_revision_id AND r.page_id=s.page_id
  WHERE r.kind IN ('initial','automatic')
),
selected_previous AS (
  SELECT c.page_id,p.id,p.author_id,p.payload
  FROM selected_current c
  LEFT JOIN LATERAL (
    SELECT r.id,r.author_id,r.payload
    FROM app.page_versions_pagerevision r
    WHERE r.page_id=c.page_id AND r.sequence<c.sequence AND r.kind IN ('initial','automatic')
    ORDER BY r.sequence DESC LIMIT 1
  ) p ON true
),
staff_candidate AS (
  SELECT user_id AS id FROM app.accounts_userprofile
  UNION SELECT user_id FROM app.accounts_pagegrant
  UNION SELECT id FROM app.auth_user WHERE is_staff OR is_superuser
  UNION SELECT author_id FROM selected_current
  UNION SELECT author_id FROM selected_previous WHERE id IS NOT NULL
),
valid_staff AS (
  SELECT c.id
  FROM staff_candidate c
  JOIN app.auth_user u ON u.id=c.id
  JOIN app.accounts_userprofile p ON p.user_id=u.id AND p.role IN ('owner','employee')
  GROUP BY c.id HAVING count(*)=1
),
facts(query_id,value) AS (
  SELECT 'COUNT-ACCOUNTS-PAGEGRANT',count(*)::bigint FROM app.accounts_pagegrant UNION ALL
  SELECT 'COUNT-ACCOUNTS-USERPROFILE',count(*) FROM app.accounts_userprofile UNION ALL
  SELECT 'COUNT-AUTH-USER',count(*) FROM app.auth_user UNION ALL
  SELECT 'COUNT-CONTENT-PAGE',count(*) FROM app.content_page UNION ALL
  SELECT 'COUNT-CONTENT-ROUTE',count(*) FROM app.content_route UNION ALL
  SELECT 'COUNT-MEDIA-ASSET',count(*) FROM app.media_library_asset UNION ALL
  SELECT 'COUNT-MEDIA-ASSETFILE',count(*) FROM app.media_library_assetfile UNION ALL
  SELECT 'COUNT-MEDIA-ASSETUSAGE',count(*) FROM app.media_library_assetusage UNION ALL
  SELECT 'COUNT-MEDIA-FOLDER',count(*) FROM app.media_library_mediafolder UNION ALL
  SELECT 'COUNT-MEDIA-PAGEMEDIAHOME',count(*) FROM app.media_library_pagemediahome UNION ALL
  SELECT 'COUNT-VERSIONS-STATE',count(*) FROM app.page_versions_pagecontentstate UNION ALL
  SELECT 'COUNT-VERSIONS-REVISION',count(*) FROM app.page_versions_pagerevision UNION ALL
  SELECT 'COUNT-SHARED-BLOCK',count(*) FROM app.shared_content_sharedblock UNION ALL
  SELECT 'COUNT-SHARED-REVISION',count(*) FROM app.shared_content_sharedrevision UNION ALL
  SELECT 'STRUCT-CURRENT-INVALID',count(*) FROM app.page_versions_pagecontentstate s
    LEFT JOIN app.page_versions_pagerevision r ON r.id=s.current_revision_id AND r.page_id=s.page_id
    WHERE r.id IS NULL OR r.kind NOT IN ('initial','automatic') OR r.sequence<>s.sequence UNION ALL
  SELECT 'STRUCT-CURRENT-NEWER',count(*) FROM selected_current c
    WHERE EXISTS (SELECT 1 FROM app.page_versions_pagerevision r
      WHERE r.page_id=c.page_id AND r.sequence>c.sequence AND r.kind IN ('initial','automatic')) UNION ALL
  SELECT 'STRUCT-PAGE-WITHOUT-STATE',count(*) FROM app.content_page p
    LEFT JOIN app.page_versions_pagecontentstate s ON s.page_id=p.id WHERE s.page_id IS NULL UNION ALL
  SELECT 'STRUCT-PREVIOUS-COUNT',count(*) FROM selected_previous WHERE id IS NOT NULL UNION ALL
  SELECT 'BYTES-REVISION-TOTAL',COALESCE(sum(octet_length(payload::text)),0)::bigint FROM app.page_versions_pagerevision UNION ALL
  SELECT 'BYTES-REVISION-MAX',COALESCE(max(octet_length(payload::text)),0)::bigint FROM app.page_versions_pagerevision UNION ALL
  SELECT 'BYTES-MEDIA-TOTAL',COALESCE(sum(byte_size),0)::bigint FROM app.media_library_assetfile UNION ALL
  SELECT 'BYTES-MEDIA-MAX',COALESCE(max(byte_size),0)::bigint FROM app.media_library_assetfile UNION ALL
  SELECT 'BYTES-SHARED-TOTAL',COALESCE(sum(CASE WHEN storage_kind='file' THEN byte_size ELSE octet_length(html) END),0)::bigint FROM app.shared_content_sharedrevision UNION ALL
  SELECT 'BYTES-SHARED-MAX',COALESCE(max(CASE WHEN storage_kind='file' THEN byte_size ELSE octet_length(html) END),0)::bigint FROM app.shared_content_sharedrevision UNION ALL
  SELECT 'DBPRE-MAP-001',count(*) FROM selected_current c LEFT JOIN valid_staff v ON v.id=c.author_id
    WHERE c.author_id IS NULL OR c.author_id<=0 OR v.id IS NULL UNION ALL
  SELECT 'DBPRE-MAP-002',count(*) FROM selected_previous p LEFT JOIN valid_staff v ON v.id=p.author_id
    WHERE p.id IS NOT NULL AND (p.author_id IS NULL OR p.author_id<=0 OR v.id IS NULL) UNION ALL
  SELECT 'DBPRE-MAP-003',count(*) FROM staff_candidate c LEFT JOIN valid_staff v ON v.id=c.id WHERE v.id IS NULL UNION ALL
  SELECT 'DBPRE-MAP-004',count(*) FROM app.accounts_pagegrant g LEFT JOIN valid_staff v ON v.id=g.user_id WHERE v.id IS NULL UNION ALL
  SELECT 'DBPRE-MAP-005',count(*) FROM app.accounts_pagegrant g LEFT JOIN app.content_page p ON p.id=g.page_id WHERE p.id IS NULL
)
SELECT query_id||'|'||value::text FROM facts ORDER BY query_id;
ROLLBACK;
'@

try {
    if ($ApprovedGate -cnotin @('RB1-READ-Q001','RB1-MEDIA-BIND-Q001','RB1-MEDIA-SOURCE-Q001')) { throw 'DBPRE_GATE_REJECTED' }
    if (!(Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) { throw 'DBPRE_DOCKER_UNAVAILABLE' }
    $requiredPaths = @($work,$private,$manifestPath,$envFile,$composeFile)
    if ($mediaBinding) { $requiredPaths += @($evidencePath,(Join-Path $repo 'tools/rebuild-media-binding.sql')) }
    if ($mediaSource) { $requiredPaths += @($evidencePath,$mediaSourceSqlPath) }
    foreach ($path in $requiredPaths) {
        if (!(Test-Path -LiteralPath $path)) { throw 'DBPRE_SCOPE_MISSING' }
        $item = Get-Item -Force -LiteralPath $path
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'DBPRE_SCOPE_LINK_REJECTED' }
    }
    Assert-ExactPrivateAcl $private
    foreach ($variable in Get-ChildItem Env:FOUNDATION_*) { throw 'DBPRE_ENV_OVERRIDE_REJECTED' }
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($manifest.environment -ne 'dev' -or $manifest.active -ne $false -or
        $manifest.composeProject -ne $project -or $manifest.dbName -ne $database -or
        $manifest.containers.db -ne $container) { throw 'DBPRE_MANIFEST_REJECTED' }
    if ($expectedTables.Count -ne $expectedTableCount -or
        ($expectedTables | Sort-Object -Unique).Count -ne $expectedTableCount -or
        $expectedTableCount -ne $(if ($mediaScoped) { 8 } else { 14 })) {
        throw 'DBPRE_ALLOWLIST_REJECTED'
    }
    if ($mediaBinding) { $aggregateSql = New-MediaBindingSql }
    if ($mediaSource) { $aggregateSql = New-MediaBindingSql 'rebuild-media-source.sql' }
    $projectContainers = @(Invoke-Docker @('ps','-aq','--filter',"label=com.docker.compose.project=$project"))
    if ($projectContainers.Count -ne 0) { throw 'DBPRE_PROJECT_NOT_STOPPED' }
    $volume = (Invoke-Docker @('volume','inspect',"$project-dbdata") | ConvertFrom-Json)[0]
    if ($volume.Name -ne "$project-dbdata" -or $volume.Labels.'com.docker.compose.project' -ne $project) {
        throw 'DBPRE_VOLUME_REJECTED'
    }
    if ($mediaSource) {
        $failureCode = 'DBPRE_FAILED_MEDIA_SOURCE_VOLUME'
        $stateVolume = @((@(Invoke-Docker @('volume','inspect',$stateVolumeName)) -join "`n") | ConvertFrom-Json)
        if ($stateVolume.Count -ne 1 -or $stateVolume[0].Name -cne $stateVolumeName -or
            $stateVolume[0].Driver -cne 'local' -or $stateVolume[0].Scope -cne 'local' -or
            $stateVolume[0].Labels.'com.docker.compose.project' -cne $project -or
            $stateVolume[0].Labels.'com.docker.compose.volume' -cne 'state') {
            throw 'DBPRE_STATE_VOLUME_REJECTED'
        }
        $stateVolumeIdentity = '{0}|{1}|{2}|{3}|{4}|{5}' -f
            $stateVolume[0].Name,$stateVolume[0].Driver,$stateVolume[0].Scope,$stateVolume[0].Mountpoint,
            $stateVolume[0].Labels.'com.docker.compose.project',$stateVolume[0].Labels.'com.docker.compose.volume'
        $failureCode = 'DBPRE_FAILED_MEDIA_SOURCE_IMAGE'
        $imageId = [string]$manifest.selectedAppImage
        if ($imageId -cnotmatch '^sha256:[0-9a-f]{64}$') { throw 'DBPRE_IMAGE_ID_REJECTED' }
        $image = @((@(Invoke-Docker @('image','inspect',$imageId)) -join "`n") | ConvertFrom-Json)
        if ($image.Count -ne 1 -or $image[0].Id -cne $imageId -or $image[0].Os -cne 'linux' -or
            $image[0].Architecture -cne 'amd64' -or $image[0].Config.User -cne '10001:10001') {
            throw 'DBPRE_IMAGE_REJECTED'
        }
        [Guid]$manifestRunId = [Guid]::Empty
        if (![Guid]::TryParseExact([string]$manifest.runId,'D',[ref]$manifestRunId) -or
            $manifestRunId -eq [Guid]::Empty) { throw 'DBPRE_MANIFEST_RUN_ID_REJECTED' }
        $verifierEvidence = $manifestRunId.ToString('N')
        $verifierName = "nestakada-media-source-$verifierEvidence"
        if (@(Invoke-Docker @('ps','-aq','--filter',"name=^/$verifierName$")).Count -ne 0 -or
            @(Invoke-Docker @('ps','-aq','--filter',"label=$verifierLabel")).Count -ne 0) {
            throw 'DBPRE_VERIFIER_COLLISION'
        }
    }
    if (Test-Path -LiteralPath $hostSecret) { throw 'DBPRE_SECRET_PREEXISTS' }

    $failureCode = 'DBPRE_FAILED_START'
    $composeTouched = $true
    Invoke-Compose @('up','-d','--no-build','--pull','never','db') | Out-Null
    $ready = $false
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        & docker.exe exec $container pg_isready -h 127.0.0.1 -p 5432 -U postgres -d $database *> $null
        if ($LASTEXITCODE -eq 0) { $ready=$true; break }
        Start-Sleep -Milliseconds 500
    }
    if (!$ready) { throw 'DBPRE_DATABASE_NOT_READY' }
    $runningNames = @(Invoke-Docker @('ps','--filter',"label=com.docker.compose.project=$project",'--format','{{.Names}}'))
    if ($runningNames.Count -ne 1 -or $runningNames[0] -ne $container) { throw 'DBPRE_SERVICE_SCOPE_REJECTED' }
    if ($mediaSource) {
        $dbInspect = @((@(Invoke-Docker @('inspect',$container)) -join "`n") | ConvertFrom-Json)
        if ($dbInspect.Count -ne 1 -or $dbInspect[0].Name -cne "/$container" -or
            $dbInspect[0].State.Running -ne $true -or
            $dbInspect[0].Config.Labels.'com.docker.compose.project' -cne $project -or
            $dbInspect[0].Config.Labels.'com.docker.compose.service' -cne 'db' -or
            $dbInspect[0].Config.Labels.'com.docker.compose.oneoff' -cne 'False' -or
            @($dbInspect[0].Config.Labels.PSObject.Properties.Name | Where-Object { $_ -ceq $verifierLabel }).Count -ne 0) {
            throw 'DBPRE_DATABASE_IDENTITY_REJECTED'
        }
        $dbContainerId = [string]$dbInspect[0].Id
        $dbImageId = [string]$dbInspect[0].Image
        Assert-DbOnlyScope
    }

    $failureCode = 'DBPRE_FAILED_ROLE'
    New-ExactSecret
    $secretPayload = [IO.File]::ReadAllText($hostSecret)
    try {
        Invoke-DockerInputExact @('exec','-i',$container,'sh','-c',
            "umask 077 && cat > '$containerSecret' && chown 999:999 '$containerSecret' && chmod 600 '$containerSecret'") $secretPayload
    } finally {
        $secretPayload = $null
    }
    $createdOutput = @(Invoke-BootstrapSql $createSql | Where-Object { $_ -match '^\d+\|\d+$' })
    if ($createdOutput.Count -ne 1) { throw 'DBPRE_ROLE_OID_REJECTED' }
    $createdParts = $createdOutput[0].Split('|')
    $roleOid = [uint32]$createdParts[0]
    $roleValidUntilMicros = [int64]$createdParts[1]
    $roleCreated = $true
    Invoke-Docker @('exec',$container,'sh','-c',
        "umask 077; p=`$(cat '$containerSecret'); printf 'db:5432:${database}:${role}:%s\n' `"`$p`" > '$containerPassfile'; unset p") | Out-Null

    $failureCode = if ($mediaBinding) { 'DBPRE_FAILED_READ_SQL' } elseif ($mediaSource) { 'DBPRE_FAILED_MEDIA_SOURCE_SESSION' } else { 'DBPRE_FAILED_READ' }
    $watch = [Diagnostics.Stopwatch]::StartNew()
    if ($mediaSource) {
        $sourceResult = Invoke-MediaSourceSession $aggregateSql $imageId
    } else {
        $lines = @(Invoke-ReaderSql $aggregateSql | Where-Object { $_ })
    }
    $watch.Stop()
    if ($watch.Elapsed.TotalSeconds -gt 30) { throw 'DBPRE_WHOLE_TIMEOUT' }
    if ($mediaSource) {
        $safeResult = [ordered]@{
            contract=$script:Contract; status='RESOLVED'; source='foundation-dev';
            elapsedMs=[int][Math]::Ceiling($watch.Elapsed.TotalMilliseconds);
            unmatchedDescriptors=$sourceResult.unmatchedDescriptors;
            resolvedFiles=$sourceResult.resolvedFiles;
            eligibleUsages=$sourceResult.eligibleUsages;
            excludedUsages=$sourceResult.excludedUsages
        }
        $json = $safeResult | ConvertTo-Json -Depth 3 -Compress
        if ([Text.Encoding]::UTF8.GetByteCount($json) -gt 1024) { throw 'DBPRE_OUTPUT_CAP_REJECTED' }
        $failureCode = $null
    } else {
    if ($mediaBinding) { $failureCode = 'DBPRE_FAILED_READ_ENVELOPE' }
    $facts = [ordered]@{}
    foreach ($line in $lines) {
        if ($line -notmatch '^([A-Z0-9-]+)\|([0-9]+)$') { throw 'DBPRE_OUTPUT_REJECTED' }
        if ($facts.Contains($Matches[1])) { throw 'DBPRE_OUTPUT_DUPLICATE' }
        $facts[$Matches[1]] = [uint64]$Matches[2]
    }
    $expectedFactCount = if ($mediaBinding) { 56 } else { 29 }
    if ($facts.Count -ne $expectedFactCount) { throw 'DBPRE_OUTPUT_COUNT_REJECTED' }
    if ($mediaBinding) {
        $failureCode = 'DBPRE_FAILED_READ_CONTRACT'
        $expectedFactGroups = [ordered]@{
            COUNTS = [ordered]@{
                'COUNT-ASSET'=238; 'COUNT-ASSETFILE'=238; 'COUNT-ASSETUSAGE'=736
            }
            USAGE = [ordered]@{
                'USAGE-UNCLASSIFIED'=0; 'USAGE-PARTITION-DELTA'=0
            }
        }
        foreach ($group in $expectedFactGroups.GetEnumerator()) {
            $failureCode = 'DBPRE_FAILED_READ_CONTRACT_{0}' -f $group.Key
            foreach ($entry in $group.Value.GetEnumerator()) {
                if (!$facts.Contains($entry.Key) -or $facts[$entry.Key] -ne [uint64]$entry.Value) {
                    throw 'DBPRE_MEDIA_BINDING_REJECTED'
                }
            }
        }
        $failureCode = 'DBPRE_FAILED_READ_CONTRACT_BINDING'
        if (($facts['BIND-DB-MATCHED'] + $facts['BIND-DB-UNMATCHED']) -ne $facts['COUNT-ASSETFILE'] -or
            ($facts['BIND-CANDIDATE-MATCHED'] + $facts['BIND-CANDIDATE-ONLY']) -ne 301 -or
            ($facts['BIND-GALLERY-MATCHED'] + $facts['BIND-GALLERY-MISSING']) -ne 214) {
            throw 'DBPRE_MEDIA_BINDING_INVARIANT_REJECTED'
        }
        $failureCode = 'DBPRE_FAILED_READ_CONTRACT_RECON'
        $dupKindSum = $facts['RECON-DUP-KIND-PRIVATE-SOURCE'] + $facts['RECON-DUP-KIND-MAIN'] +
            $facts['RECON-DUP-KIND-PREVIEW'] + $facts['RECON-DUP-KIND-LEGACY-PUBLIC']
        $unmatchedKindSum = $facts['RECON-UNMATCHED-KIND-PRIVATE-SOURCE'] + $facts['RECON-UNMATCHED-KIND-MAIN'] +
            $facts['RECON-UNMATCHED-KIND-PREVIEW'] + $facts['RECON-UNMATCHED-KIND-LEGACY-PUBLIC']
        if ($facts['RECON-DUP-PAIR-GROUPS'] -ne 1 -or $facts['RECON-DUP-FILE-ROWS'] -lt 2 -or
            $facts['RECON-DUP-DISTINCT-ASSETS'] -lt 1 -or
            $facts['RECON-DUP-DISTINCT-ASSETS'] -gt $facts['RECON-DUP-FILE-ROWS'] -or
            $facts['RECON-DUP-READY-ROWS'] -gt $facts['RECON-DUP-FILE-ROWS'] -or
            $facts['RECON-DUP-LEGACY-ROWS'] -gt $facts['RECON-DUP-FILE-ROWS'] -or
            $dupKindSum -ne $facts['RECON-DUP-FILE-ROWS'] -or
            $facts['RECON-UNMATCHED-PAIR-GROUPS'] -ne 1 -or $facts['RECON-UNMATCHED-FILE-ROWS'] -ne 1 -or
            $facts['RECON-UNMATCHED-DISTINCT-ASSETS'] -ne 1 -or
            $facts['RECON-UNMATCHED-READY-ROWS'] -gt 1 -or $facts['RECON-UNMATCHED-LEGACY-ROWS'] -gt 1 -or
            $unmatchedKindSum -ne 1) {
            throw 'DBPRE_MEDIA_RECON_INVARIANT_REJECTED'
        }
    } else {
        foreach ($id in 1..5 | ForEach-Object { 'DBPRE-MAP-{0:D3}' -f $_ }) {
            if (!$facts.Contains($id) -or $facts[$id] -ne 0) { throw 'DBPRE_MAPPABILITY_REJECTED' }
        }
        foreach ($id in @('STRUCT-CURRENT-INVALID','STRUCT-CURRENT-NEWER','STRUCT-PAGE-WITHOUT-STATE')) {
            if (!$facts.Contains($id) -or $facts[$id] -ne 0) { throw 'DBPRE_STRUCTURE_REJECTED' }
        }
    }
    if ($mediaBinding) { $failureCode = 'DBPRE_FAILED_READ_OUTPUT' }
    if ($mediaBinding) {
        $drift = $false
        foreach ($id in @(
            'ANOM-CANDIDATE-DUPLICATE','ANOM-DB-PAIR-DUPLICATE','ANOM-DESCRIPTOR',
            'ANOM-ELIGIBLE-ASSET-STATE','ANOM-ELIGIBLE-NO-FILE','ANOM-ORPHAN-CONSUMER',
            'ANOM-UNKNOWN-KIND','ANOM-SELECTED-OVERLAP','STRUCT-CURRENT-INVALID',
            'STRUCT-CURRENT-NEWER','STRUCT-PAGE-WITHOUT-STATE','STRUCT-SHARED-CURRENT-INVALID')) {
            if ($facts[$id] -ne 0) { $drift = $true }
        }
        $safeResult = [ordered]@{
            contract=$script:Contract; status=$(if ($drift) { 'OBSERVED' } else { 'PASS' }); source='foundation-dev';
            elapsedMs=[int][Math]::Ceiling($watch.Elapsed.TotalMilliseconds);
            binding=[ordered]@{
                dbMatched=$facts['BIND-DB-MATCHED']; dbUnmatched=$facts['BIND-DB-UNMATCHED'];
                candidateMatched=$facts['BIND-CANDIDATE-MATCHED']; candidateOnly=$facts['BIND-CANDIDATE-ONLY'];
                galleryMatched=$facts['BIND-GALLERY-MATCHED']; galleryMissing=$facts['BIND-GALLERY-MISSING']
            };
            anomaly=[ordered]@{
                candidateDuplicate=$facts['ANOM-CANDIDATE-DUPLICATE'];
                dbPairDuplicate=$facts['ANOM-DB-PAIR-DUPLICATE']; descriptor=$facts['ANOM-DESCRIPTOR'];
                eligibleAssetState=$facts['ANOM-ELIGIBLE-ASSET-STATE'];
                eligibleNoFile=$facts['ANOM-ELIGIBLE-NO-FILE'];
                orphanConsumer=$facts['ANOM-ORPHAN-CONSUMER']; unknownKind=$facts['ANOM-UNKNOWN-KIND'];
                selectedOverlap=$facts['ANOM-SELECTED-OVERLAP']
            };
            structure=[ordered]@{
                currentInvalid=$facts['STRUCT-CURRENT-INVALID']; currentNewer=$facts['STRUCT-CURRENT-NEWER'];
                pageWithoutState=$facts['STRUCT-PAGE-WITHOUT-STATE'];
                sharedCurrentInvalid=$facts['STRUCT-SHARED-CURRENT-INVALID']
            };
            duplicateMatched=[ordered]@{
                pairGroups=$facts['RECON-DUP-PAIR-GROUPS']; fileRows=$facts['RECON-DUP-FILE-ROWS'];
                distinctAssets=$facts['RECON-DUP-DISTINCT-ASSETS']; readyRows=$facts['RECON-DUP-READY-ROWS'];
                legacyRows=$facts['RECON-DUP-LEGACY-ROWS'];
                privateSource=$facts['RECON-DUP-KIND-PRIVATE-SOURCE']; main=$facts['RECON-DUP-KIND-MAIN'];
                preview=$facts['RECON-DUP-KIND-PREVIEW']; legacyPublic=$facts['RECON-DUP-KIND-LEGACY-PUBLIC'];
                eligibleUsages=$facts['RECON-DUP-ELIGIBLE-USAGES']; excludedUsages=$facts['RECON-DUP-EXCLUDED-USAGES']
            };
            unmatchedDb=[ordered]@{
                pairGroups=$facts['RECON-UNMATCHED-PAIR-GROUPS']; fileRows=$facts['RECON-UNMATCHED-FILE-ROWS'];
                distinctAssets=$facts['RECON-UNMATCHED-DISTINCT-ASSETS']; readyRows=$facts['RECON-UNMATCHED-READY-ROWS'];
                legacyRows=$facts['RECON-UNMATCHED-LEGACY-ROWS'];
                privateSource=$facts['RECON-UNMATCHED-KIND-PRIVATE-SOURCE']; main=$facts['RECON-UNMATCHED-KIND-MAIN'];
                preview=$facts['RECON-UNMATCHED-KIND-PREVIEW']; legacyPublic=$facts['RECON-UNMATCHED-KIND-LEGACY-PUBLIC'];
                eligibleUsages=$facts['RECON-UNMATCHED-ELIGIBLE-USAGES'];
                excludedUsages=$facts['RECON-UNMATCHED-EXCLUDED-USAGES']
            }
        }
    } else {
        $safeResult = [ordered]@{
            contract=$script:Contract; status='PASS'; source='foundation-dev';
            factCount=$facts.Count; elapsedMs=[int][Math]::Ceiling($watch.Elapsed.TotalMilliseconds);
            facts=$facts
        }
    }
        $json = $safeResult | ConvertTo-Json -Depth 4 -Compress
        if ([Text.Encoding]::UTF8.GetByteCount($json) -gt 65536) { throw 'DBPRE_OUTPUT_CAP_REJECTED' }
        $failureCode = $null
    }
} catch {
    if ($mediaSource) {
        if ($_.Exception.Message -ceq 'DBPRE_MEDIA_SOURCE_UNKNOWN_ISOLATED') { $unknownIsolated = $true }
        $failureCode = switch -Regex ($_.Exception.Message) {
            '^DBPRE_MEDIA_SOURCE_UNKNOWN_ISOLATED$' { 'DBPRE_FAILED_MEDIA_SOURCE_UNKNOWN_ISOLATED'; break }
            '^DBPRE_VERIFIER_CLEANUP_REQUIRED$' { 'DBPRE_FAILED_MEDIA_SOURCE_CLEANUP'; break }
            'CID|VERIFIER_(?:COLLISION|INSPECT|IDENTITY|TMPFS|ABSENCE)' { 'DBPRE_FAILED_MEDIA_SOURCE_IDENTITY'; break }
            'IMAGE' { 'DBPRE_FAILED_MEDIA_SOURCE_IMAGE'; break }
            'VOLUME' { 'DBPRE_FAILED_MEDIA_SOURCE_VOLUME'; break }
            'DESCRIPTOR' { 'DBPRE_FAILED_MEDIA_SOURCE_DESCRIPTOR'; break }
            'VERIFIER|PROCESS' { 'DBPRE_FAILED_MEDIA_SOURCE_VERIFY'; break }
            default { $failureCode }
        }
    }
} finally {
    if ($roleCreated -and $null -ne $roleOid -and $null -ne $roleValidUntilMicros) {
        $cleanupSql = @"
BEGIN;
DO `$`$
BEGIN
  RAISE NOTICE 'DBPRE_CLEANUP_PROOF_IDENTITY';
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='$role' AND oid=$roleOid) THEN RAISE EXCEPTION 'identity'; END IF;
END `$`$;
ALTER ROLE $role NOLOGIN;
DO `$`$ BEGIN RAISE NOTICE 'DBPRE_CLEANUP_PROOF_ROLE_FLAGS'; END `$`$;
DO `$`$
DECLARE
  rid oid := $roleOid;
  allowed oid[];
  session_attempt integer;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE oid=rid AND rolname='$role'
      AND NOT rolsuper AND NOT rolinherit AND NOT rolcreaterole AND NOT rolcreatedb
      AND NOT rolcanlogin AND NOT rolreplication AND NOT rolbypassrls
      AND rolconnlimit=1
  ) THEN RAISE EXCEPTION 'role-flags'; END IF;
  RAISE NOTICE 'DBPRE_CLEANUP_PROOF_VALID_UNTIL';
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE oid=rid AND rolname='$role'
      AND floor(extract(epoch FROM rolvaliduntil)*1000000)::bigint=$roleValidUntilMicros
  ) THEN RAISE EXCEPTION 'valid-until'; END IF;
  RAISE NOTICE 'DBPRE_CLEANUP_PROOF_SETTINGS';
  IF (SELECT count(*) FROM pg_db_role_setting WHERE setrole=rid) <> 1
     OR NOT EXISTS (
       SELECT 1 FROM pg_db_role_setting
       WHERE setrole=rid AND setdatabase=0 AND cardinality(setconfig)=2
         AND setconfig @> ARRAY['default_transaction_read_only=on','search_path=pg_catalog, app']
         AND setconfig <@ ARRAY['default_transaction_read_only=on','search_path=pg_catalog, app'])
  THEN RAISE EXCEPTION 'role-settings'; END IF;
  RAISE NOTICE 'DBPRE_CLEANUP_PROOF_SESSIONS';
  FOR session_attempt IN 1..20 LOOP
    PERFORM pg_stat_clear_snapshot();
    EXIT WHEN NOT EXISTS (SELECT 1 FROM pg_stat_activity WHERE usename='$role');
    PERFORM pg_sleep(0.05);
  END LOOP;
  PERFORM pg_stat_clear_snapshot();
  IF EXISTS (SELECT 1 FROM pg_stat_activity WHERE usename='$role') THEN RAISE EXCEPTION 'sessions'; END IF;
  RAISE NOTICE 'DBPRE_CLEANUP_PROOF_RELATIONS';
  SELECT array_agg(c.oid ORDER BY c.oid) INTO allowed
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='app' AND c.relkind IN ('r','p') AND c.relname=ANY(ARRAY[$allowlistSqlNames]);
  IF cardinality(allowed) <> $expectedTableCount THEN RAISE EXCEPTION 'allowlist'; END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=rid OR roleid=rid)
     OR EXISTS (SELECT 1 FROM pg_shdepend
       WHERE refclassid='pg_authid'::regclass AND refobjid=rid AND deptype='o')
     OR EXISTS (SELECT 1 FROM pg_database WHERE datdba=rid)
     OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner=rid)
     OR EXISTS (SELECT 1 FROM pg_class WHERE relowner=rid AND relkind IN ('r','p','S'))
  THEN RAISE EXCEPTION 'role-relations'; END IF;
  RAISE NOTICE 'DBPRE_CLEANUP_PROOF_PRIVILEGES';
  IF EXISTS (
    SELECT 1 FROM pg_database d WHERE
      (d.datallowconn AND has_database_privilege(rid,d.oid,'CONNECT'))
        IS DISTINCT FROM (d.datname='$database')
      OR (d.datallowconn AND has_database_privilege(rid,d.oid,'CONNECT')
          AND has_database_privilege(rid,d.oid,'CREATE'))
      OR (d.datallowconn AND has_database_privilege(rid,d.oid,'CONNECT')
          AND has_database_privilege(rid,d.oid,'TEMP')))
  THEN RAISE EXCEPTION 'database-privileges'; END IF;
  -- System schemas are excluded only for catalog-backed identity and privilege proof.
  IF EXISTS (
    SELECT 1 FROM pg_namespace n
    WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND (
      has_schema_privilege(rid,n.oid,'USAGE') IS DISTINCT FROM (n.nspname='app')
      OR has_schema_privilege(rid,n.oid,'CREATE')))
  THEN RAISE EXCEPTION 'schema-privileges'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
      AND c.relkind IN ('r','p','v','m','f') AND (
      has_table_privilege(rid,c.oid,'SELECT') IS DISTINCT FROM (c.oid=ANY(allowed)) OR
      (c.oid<>ALL(allowed) AND has_any_column_privilege(rid,c.oid,'SELECT')) OR
      has_table_privilege(rid,c.oid,'INSERT') OR has_table_privilege(rid,c.oid,'UPDATE') OR
      has_table_privilege(rid,c.oid,'DELETE') OR has_table_privilege(rid,c.oid,'TRUNCATE') OR
      has_table_privilege(rid,c.oid,'REFERENCES') OR has_table_privilege(rid,c.oid,'TRIGGER') OR
      has_table_privilege(rid,c.oid,'MAINTAIN') OR
      has_any_column_privilege(rid,c.oid,'INSERT') OR has_any_column_privilege(rid,c.oid,'UPDATE') OR
      has_any_column_privilege(rid,c.oid,'REFERENCES')))
  THEN RAISE EXCEPTION 'table-privileges'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind='S' AND
      (has_sequence_privilege(rid,c.oid,'USAGE') OR has_sequence_privilege(rid,c.oid,'SELECT') OR
       has_sequence_privilege(rid,c.oid,'UPDATE')))
  THEN RAISE EXCEPTION 'sequence-privileges'; END IF;
END `$`$;
DO `$`$ BEGIN RAISE NOTICE 'DBPRE_CLEANUP_PROOF_REVOKE_DROP'; END `$`$;
REVOKE SELECT ON TABLE $grantSqlTables FROM $role;
REVOKE USAGE ON SCHEMA app FROM $role;
REVOKE CONNECT ON DATABASE $database FROM $role;
DROP ROLE $role;
COMMIT;
"@
        try { Invoke-BootstrapSql $cleanupSql | Out-Null } catch {
            if ($null -eq $cleanupFailureCode) {
                $cleanupFailureCode = switch -CaseSensitive ($_.Exception.Message) {
                    'DBPRE_CLEANUP_PROOF_FAILED_IDENTITY' { 'DBPRE_FAILED_CLEANUP_ROLE_IDENTITY' }
                    'DBPRE_CLEANUP_PROOF_FAILED_ROLE_FLAGS' { 'DBPRE_FAILED_CLEANUP_ROLE_ROLE_FLAGS' }
                    'DBPRE_CLEANUP_PROOF_FAILED_VALID_UNTIL' { 'DBPRE_FAILED_CLEANUP_ROLE_VALID_UNTIL' }
                    'DBPRE_CLEANUP_PROOF_FAILED_SETTINGS' { 'DBPRE_FAILED_CLEANUP_ROLE_SETTINGS' }
                    'DBPRE_CLEANUP_PROOF_FAILED_SESSIONS' { 'DBPRE_FAILED_CLEANUP_ROLE_SESSIONS' }
                    'DBPRE_CLEANUP_PROOF_FAILED_RELATIONS' { 'DBPRE_FAILED_CLEANUP_ROLE_RELATIONS' }
                    'DBPRE_CLEANUP_PROOF_FAILED_PRIVILEGES' { 'DBPRE_FAILED_CLEANUP_ROLE_PRIVILEGES' }
                    'DBPRE_CLEANUP_PROOF_FAILED_REVOKE_DROP' { 'DBPRE_FAILED_CLEANUP_ROLE_REVOKE_DROP' }
                    default { 'DBPRE_FAILED_CLEANUP_ROLE' }
                }
            }
            $disableSql = @"
DO `$`$
DECLARE actual_name text;
BEGIN
  SELECT rolname::text INTO actual_name FROM pg_roles WHERE oid=$roleOid;
  IF actual_name IS NOT NULL THEN
    EXECUTE format('ALTER ROLE %I NOLOGIN',actual_name);
    EXECUTE format('REVOKE SELECT ON TABLE $grantSqlTables FROM %I',actual_name);
    EXECUTE format('REVOKE USAGE ON SCHEMA app FROM %I',actual_name);
    EXECUTE format('REVOKE CONNECT ON DATABASE $database FROM %I',actual_name);
  END IF;
END `$`$;
"@
            try { Invoke-BootstrapSql $disableSql | Out-Null } catch { }
        }
    }
    if ($composeTouched) {
        try { Invoke-Docker @('exec',$container,'sh','-c',"rm -f '$containerSecret' '$containerPassfile'") | Out-Null } catch {
            if ($null -eq $cleanupFailureCode) { $cleanupFailureCode = 'DBPRE_FAILED_CLEANUP_CONTAINER_FILES' }
        }
    }
    try { Remove-ExactSecret } catch {
        if ($null -eq $cleanupFailureCode) { $cleanupFailureCode = 'DBPRE_FAILED_CLEANUP_HOST_SECRET' }
    }
    if ($composeTouched) {
        try { Invoke-Compose @('down','--timeout','10') | Out-Null } catch {
            if ($null -eq $cleanupFailureCode) { $cleanupFailureCode = 'DBPRE_FAILED_CLEANUP_COMPOSE' }
        }
    }
}

if ($mediaSource -and !$unknownIsolated -and $stateVolumeIdentity) {
    try {
        $nameResidual = @()
        if ($verifierName) {
            $nameResidual = @(Invoke-Docker @('ps','-aq','--filter',"name=^/$verifierName$"))
        }
        if (@(Invoke-Docker @('ps','-aq','--filter',"label=com.docker.compose.project=$project")).Count -ne 0 -or
            $nameResidual.Count -ne 0 -or @(Invoke-Docker @('ps','-aq','--filter',"label=$verifierLabel")).Count -ne 0 -or
            (Test-Path -LiteralPath $verifierCidPath)) {
            throw 'DBPRE_MEDIA_FINAL_SCOPE_REJECTED'
        }
        $finalVolume = @((@(Invoke-Docker @('volume','inspect',$stateVolumeName)) -join "`n") | ConvertFrom-Json)
        if ($finalVolume.Count -ne 1) { throw 'DBPRE_MEDIA_FINAL_VOLUME_REJECTED' }
        $finalVolumeIdentity = '{0}|{1}|{2}|{3}|{4}|{5}' -f
            $finalVolume[0].Name,$finalVolume[0].Driver,$finalVolume[0].Scope,$finalVolume[0].Mountpoint,
            $finalVolume[0].Labels.'com.docker.compose.project',$finalVolume[0].Labels.'com.docker.compose.volume'
        if ($finalVolumeIdentity -cne $stateVolumeIdentity) { throw 'DBPRE_MEDIA_FINAL_VOLUME_REJECTED' }
    } catch {
        $cleanupFailureCode = 'DBPRE_FAILED_MEDIA_SOURCE_CLEANUP'
    }
}

if ($cleanupFailureCode) { Stop-DbpreFailure $cleanupFailureCode }
if ($failureCode) { Stop-DbpreFailure $failureCode }
$safeResult | ConvertTo-Json -Depth 4 -Compress
