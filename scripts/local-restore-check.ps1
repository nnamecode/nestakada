[CmdletBinding()]
param(
    [ValidateSet('dev','test')][string]$Environment = 'test',
    [ValidateSet('current','previous')][string]$Generation = 'current'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work = [IO.Path]::GetFullPath((Join-Path $repo "work/foundation/$Environment"))
$scope = "foundation-$Environment"
$backupRoot = Join-Path $work 'backups'
$catalogPath = Join-Path $backupRoot 'catalog.json'
$generationsRoot = Join-Path $backupRoot 'generations'
$lockPath = Join-Path $backupRoot '.backup.lock'
$manifestPath = Join-Path $work 'manifest.json'
$envFile = Join-Path $work 'compose.env'
$helperPath = [IO.Path]::GetFullPath((Join-Path $repo 'tools/foundation_restore_check.sh'))
$generationBody = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
$generationPattern = "^$generationBody$"
$script:toolFailurePhase = ''
$restoreLock = $null
$staging = $null
$phase = 'preflight'

function Fail-Check { throw 'LOCAL_RESTORE_CHECK_UNAVAILABLE' }

function Reject-Link([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail-Check }
}

function Protect-Directory([string]$Path) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $directory = [IO.DirectoryInfo]::new($Path)
    $acl = [IO.FileSystemAclExtensions]::GetAccessControl(
        $directory,[Security.AccessControl.AccessControlSections]::Access)
    $acl.SetAccessRuleProtection($true,$false)
    $rules = $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])
    foreach ($rule in @($rules)) { $acl.RemoveAccessRuleSpecific($rule) }
    foreach ($sid in @($identity.User,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    [IO.FileSystemAclExtensions]::SetAccessControl($directory,$acl)
}

function Remove-RestoreStaging([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($backupRoot) + [IO.Path]::DirectorySeparatorChar
    if (!$full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($full) -notmatch "^\.restore-staging-$generationBody$") { Fail-Check }
    if (Test-Path -LiteralPath $full) {
        Reject-Link $full
        if (!(Get-Item -Force -LiteralPath $full).PSIsContainer) { Fail-Check }
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

function Docker([string[]]$Arguments) {
    $result = @(& docker.exe @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        foreach ($line in $result) {
            if ([string]$line -match '^LOCAL_RESTORE_CHECK_UNAVAILABLE phase=([a-z-]+)$') {
                $script:toolFailurePhase = $Matches[1]
            }
        }
        Fail-Check
    }
    return $result
}

function Read-FoundationValue([string]$Name) {
    $matches = @(Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^$([regex]::Escape($Name))='([^']*)'$" })
    if ($matches.Count -ne 1 -or $matches[0] -notmatch "^$([regex]::Escape($Name))='([^']*)'$") { Fail-Check }
    return $Matches[1]
}

function Get-ArtifactHashes([string]$Path) {
    $values = [ordered]@{}
    foreach ($name in @('checksums.sha256','database.dump','manifest.json','media.tar')) {
        $values[$name] = (Get-FileHash -LiteralPath (Join-Path $Path $name) -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return (ConvertTo-Json -Compress -InputObject $values)
}

function Assert-Generation([string]$Path,[string]$ExpectedId) {
    if (!(Test-Path -LiteralPath $Path -PathType Container)) { Fail-Check }
    Reject-Link $Path
    $expected = @('checksums.sha256','database.dump','manifest.json','media.tar')
    $actual = @(Get-ChildItem -Force -LiteralPath $Path | Sort-Object Name)
    if ($actual.Count -ne 4 -or (@($actual.Name) -join ',') -cne ($expected -join ',')) { Fail-Check }
    foreach ($file in $actual) {
        if ($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $file.Length -le 0) { Fail-Check }
    }
    $manifest = Get-Content -Raw -LiteralPath (Join-Path $Path 'manifest.json') | ConvertFrom-Json -DateKind String
    $fields = @('checksumAlgorithm','consistency','createdAt','database','databaseArchive','generation','mediaArchive','schemaVersion')
    if ((@($manifest.PSObject.Properties.Name | Sort-Object) -join ',') -cne (@($fields | Sort-Object) -join ',') -or
        $manifest.schemaVersion -ne 1 -or $manifest.generation -cne $ExpectedId -or
        $manifest.generation -notmatch $generationPattern -or $manifest.database -cne 'estakada_foundation' -or
        $manifest.databaseArchive -cne 'database.dump' -or $manifest.mediaArchive -cne 'media.tar' -or
        $manifest.consistency -cne 'maintenance-gate' -or $manifest.checksumAlgorithm -cne 'SHA-256' -or
        $manifest.createdAt -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$') { Fail-Check }
    $lines = @(Get-Content -LiteralPath (Join-Path $Path 'checksums.sha256'))
    if ($lines.Count -ne 2) { Fail-Check }
    $hashes = @{}
    foreach ($line in $lines) {
        if ($line -notmatch '^([0-9a-f]{64})  (database\.dump|media\.tar)$' -or $hashes.ContainsKey($Matches[2])) { Fail-Check }
        $hashes[$Matches[2]] = $Matches[1]
    }
    foreach ($name in @('database.dump','media.tar')) {
        if ((Get-FileHash -LiteralPath (Join-Path $Path $name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hashes[$name]) { Fail-Check }
    }
}

try {
    if (!(Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) { Fail-Check }
    foreach ($path in @($repo,$work,$backupRoot,$catalogPath,$generationsRoot,$lockPath,$manifestPath,$envFile,$helperPath)) {
        if (!(Test-Path -LiteralPath $path)) { Fail-Check }
        Reject-Link $path
    }
    $foundation = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($foundation.environment -cne $Environment -or [bool]$foundation.active) { Fail-Check }

    $phase = 'lock'
    $restoreLock = [IO.File]::Open($lockPath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $foundation = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($foundation.environment -cne $Environment -or [bool]$foundation.active) { Fail-Check }

    foreach ($item in @(Get-ChildItem -Force -LiteralPath $backupRoot)) {
        if ($item.Name -match "^\.restore-staging-$generationBody$") { Remove-RestoreStaging $item.FullName }
    }

    $phase = 'artifacts'
    $catalog = Get-Content -Raw -LiteralPath $catalogPath | ConvertFrom-Json -DateKind String
    $fields = @('current','previous','schemaVersion')
    if ((@($catalog.PSObject.Properties.Name | Sort-Object) -join ',') -cne (@($fields | Sort-Object) -join ',') -or
        $catalog.schemaVersion -ne 1 -or $catalog.current -notmatch $generationPattern -or
        $catalog.previous -notmatch $generationPattern -or $catalog.current -ceq $catalog.previous) { Fail-Check }
    $generationId = [string]$catalog.$Generation
    $generationPath = Join-Path $generationsRoot $generationId
    Assert-Generation $generationPath $generationId
    $beforeCatalog = (Get-FileHash -LiteralPath $catalogPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $beforeArtifacts = Get-ArtifactHashes $generationPath

    $postgresImage = Read-FoundationValue 'FOUNDATION_POSTGRES_IMAGE'
    if ($postgresImage -notmatch '^sha256:[0-9a-f]{64}$') { Fail-Check }
    $image = @(Docker @('image','inspect',$postgresImage) | ConvertFrom-Json)
    if ($image.Count -ne 1 -or $image[0].Id -cne $postgresImage -or $image[0].Os -cne 'linux' -or
        $image[0].Architecture -cne 'amd64') { Fail-Check }

    $phase = 'staging'
    $stagingId = [guid]::NewGuid().ToString()
    $staging = Join-Path $backupRoot ".restore-staging-$stagingId"
    New-Item -ItemType Directory -Path $staging | Out-Null
    Reject-Link $staging
    Protect-Directory $staging
    foreach ($name in @('checksums.sha256','database.dump','manifest.json','media.tar')) {
        [IO.File]::Copy((Join-Path $generationPath $name),(Join-Path $staging $name),$false)
    }
    if ((Get-ArtifactHashes $staging) -cne $beforeArtifacts) { Fail-Check }
    $permissionArguments = @(
        'run','--rm','--pull=never','--network','none','--read-only','--user','10001:10001',
        '--cap-drop=ALL','--security-opt=no-new-privileges:true','--memory=64m','--cpus=0.25','--pids-limit=16',
        '--label',"nestakada.scope=$scope-restore-permission",
        '--mount',"type=bind,source=$staging,target=/staging",
        '--entrypoint','/usr/bin/chmod',$postgresImage,'0444',
        '/staging/checksums.sha256','/staging/database.dump','/staging/manifest.json','/staging/media.tar'
    )
    $permissionResult = @(Docker $permissionArguments)
    if ($permissionResult.Count -ne 0 -or (Get-ArtifactHashes $staging) -cne $beforeArtifacts) { Fail-Check }

    $phase = 'tool'
    $arguments = @(
        'run','--rm','--pull=never','--network','none','--read-only','--user','999:999',
        '--cap-drop=ALL','--security-opt=no-new-privileges:true','--memory=1536m','--cpus=1.0','--pids-limit=128',
        '--label',"nestakada.scope=$scope-restore-check",
        '--tmpfs','/restore-db:rw,nosuid,nodev,noexec,size=512m,uid=999,gid=999,mode=0700',
        '--tmpfs','/restore-media:rw,nosuid,nodev,noexec,size=512m,uid=999,gid=999,mode=0700',
        '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=32m,uid=999,gid=999,mode=1777',
        '--mount',"type=bind,source=$staging,target=/backup,readonly",
        '--mount',"type=bind,source=$helperPath,target=/tools/foundation_restore_check.sh,readonly",
        '--entrypoint','/bin/sh',$postgresImage,'/tools/foundation_restore_check.sh'
    )
    $result = @(Docker $arguments)
    if ($result.Count -ne 1 -or [string]$result[0] -notmatch '^LOCAL_RESTORE_CHECK_OK tables=[1-9][0-9]* migrations=[1-9][0-9]* media_files=[0-9]+ media_bytes=[0-9]+$') { Fail-Check }

    $phase = 'immutability'
    if ((Get-FileHash -LiteralPath $catalogPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $beforeCatalog -or
        (Get-ArtifactHashes $generationPath) -cne $beforeArtifacts -or
        (Get-ArtifactHashes $staging) -cne $beforeArtifacts) { Fail-Check }
    Remove-RestoreStaging $staging
    $staging = $null
    Write-Output ([string]$result[0])
} catch {
    if ($script:toolFailurePhase) { $phase = "tool-$($script:toolFailurePhase)" }
    Write-Error "LOCAL_RESTORE_CHECK_UNAVAILABLE phase=$phase" -ErrorAction Continue
    exit 1
} finally {
    if ($staging) { try { Remove-RestoreStaging $staging } catch { } }
    if ($restoreLock) { $restoreLock.Dispose(); $restoreLock = $null }
}
