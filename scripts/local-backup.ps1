[CmdletBinding()]
param(
    [ValidateSet('dev','test')][string]$Environment = 'test'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$scope = "foundation-$Environment"
$project = "nestakada-$scope"
$work = [IO.Path]::GetFullPath((Join-Path $repo "work/foundation/$Environment"))
$private = Join-Path $work 'private'
$manifestPath = Join-Path $work 'manifest.json'
$envFile = Join-Path $work 'compose.env'
$backupRoot = [IO.Path]::GetFullPath((Join-Path $work 'backups'))
$generationsRoot = Join-Path $backupRoot 'generations'
$catalogPath = Join-Path $backupRoot 'catalog.json'
$lockPath = Join-Path $backupRoot '.backup.lock'
$toolPath = [IO.Path]::GetFullPath((Join-Path $repo 'tools/foundation_backup.sh'))
$script:toolFailurePhase = ''
$script:publicationOutcome = 'not-started'
$backupLock = $null
$generationBody = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
$generationPattern = "^$generationBody$"

function Fail-Backup { throw 'LOCAL_BACKUP_UNAVAILABLE' }

function Reject-Link([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail-Backup }
}

function Protect-Directory([string]$Path) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $directory = [IO.DirectoryInfo]::new($Path)
    $acl = [IO.FileSystemAclExtensions]::GetAccessControl(
        $directory, [Security.AccessControl.AccessControlSections]::Access)
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

function Docker([string[]]$Arguments) {
    $result = @(& docker.exe @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        foreach ($line in $result) {
            if ([string]$line -match '^LOCAL_BACKUP_TOOL_UNAVAILABLE phase=([a-z-]+)$') {
                $script:toolFailurePhase = $Matches[1]
            }
        }
        Fail-Backup
    }
    return $result
}

function Read-FoundationValue([string]$Name) {
    $matches = @(Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^$([regex]::Escape($Name))='([^']*)'$" })
    if ($matches.Count -ne 1) { Fail-Backup }
    if ($matches[0] -notmatch "^$([regex]::Escape($Name))='([^']*)'$") { Fail-Backup }
    return $Matches[1]
}

function Assert-ScopedResource([string]$Kind,[string]$Name) {
    $item = @(Docker @($Kind,'inspect',$Name) | ConvertFrom-Json)
    if ($item.Count -ne 1 -or $item[0].Labels.'nestakada.scope' -cne $scope) { Fail-Backup }
}

function Get-MaintenanceSnapshot {
    $expected = [ordered]@{
        "$project-db" = $true
        "$project-app" = $false
        "$project-ingress" = $false
        "$project-media-worker" = $false
    }
    $rows = @()
    foreach ($name in $expected.Keys) {
        $item = @(Docker @('inspect',$name) | ConvertFrom-Json)
        if ($item.Count -ne 1 -or $item[0].Config.Labels.'nestakada.scope' -cne $scope -or
            [bool]$item[0].State.Running -ne $expected[$name]) { Fail-Backup }
        $rows += [ordered]@{
            name=$name; id=[string]$item[0].Id; running=[bool]$item[0].State.Running
            restartCount=[int]$item[0].RestartCount; startedAt=[string]$item[0].State.StartedAt
            finishedAt=[string]$item[0].State.FinishedAt
        }
    }
    return (ConvertTo-Json -Compress -InputObject $rows)
}

function Assert-Generation([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Container)) { Fail-Backup }
    Reject-Link $Path
    $expected = @('checksums.sha256','database.dump','manifest.json','media.tar')
    $actual = @(Get-ChildItem -Force -LiteralPath $Path | Sort-Object Name)
    if ($actual.Count -ne 4 -or (@($actual.Name) -join ',') -cne ($expected -join ',')) { Fail-Backup }
    foreach ($file in $actual) {
        if ($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $file.Length -le 0) { Fail-Backup }
    }
    $manifest = Get-Content -Raw -LiteralPath (Join-Path $Path 'manifest.json') | ConvertFrom-Json -DateKind String
    $fields = @('checksumAlgorithm','consistency','createdAt','database','databaseArchive','generation','mediaArchive','schemaVersion')
    if ((@($manifest.PSObject.Properties.Name | Sort-Object) -join ',') -cne (@($fields | Sort-Object) -join ',') -or
        $manifest.schemaVersion -ne 1 -or $manifest.database -cne 'estakada_foundation' -or
        $manifest.databaseArchive -cne 'database.dump' -or $manifest.mediaArchive -cne 'media.tar' -or
        $manifest.consistency -cne 'maintenance-gate' -or $manifest.checksumAlgorithm -cne 'SHA-256' -or
        $manifest.generation -notmatch $generationPattern -or
        $manifest.createdAt -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$') { Fail-Backup }
    $lines = @(Get-Content -LiteralPath (Join-Path $Path 'checksums.sha256'))
    if ($lines.Count -ne 2) { Fail-Backup }
    $hashes = @{}
    foreach ($line in $lines) {
        if ($line -notmatch '^([0-9a-f]{64})  (database\.dump|media\.tar)$' -or $hashes.ContainsKey($Matches[2])) { Fail-Backup }
        $hashes[$Matches[2]] = $Matches[1]
    }
    foreach ($name in @('database.dump','media.tar')) {
        $actualHash = (Get-FileHash -LiteralPath (Join-Path $Path $name) -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -cne $hashes[$name]) { Fail-Backup }
    }
}

function Get-GenerationId([string]$Path) {
    Assert-Generation $Path
    $manifest = Get-Content -Raw -LiteralPath (Join-Path $Path 'manifest.json') | ConvertFrom-Json -DateKind String
    return [string]$manifest.generation
}

function Get-Catalog {
    if (!(Test-Path -LiteralPath $catalogPath)) { return $null }
    Reject-Link $catalogPath
    $item = Get-Item -Force -LiteralPath $catalogPath
    if ($item.PSIsContainer -or $item.Length -le 0) { Fail-Backup }
    $catalog = Get-Content -Raw -LiteralPath $catalogPath | ConvertFrom-Json -DateKind String
    $fields = @('current','previous','schemaVersion')
    if ((@($catalog.PSObject.Properties.Name | Sort-Object) -join ',') -cne (@($fields | Sort-Object) -join ',') -or
        $catalog.schemaVersion -ne 1 -or $catalog.current -notmatch $generationPattern -or
        ($null -ne $catalog.previous -and $catalog.previous -notmatch $generationPattern) -or
        ($null -ne $catalog.previous -and $catalog.current -ceq $catalog.previous)) { Fail-Backup }
    foreach ($id in @($catalog.current,$catalog.previous)) {
        if ($null -eq $id) { continue }
        $path = Join-Path $generationsRoot $id
        if ((Get-GenerationId $path) -cne $id) { Fail-Backup }
    }
    return $catalog
}

function Copy-Generation([string]$Source,[string]$Generation) {
    if ($Generation -notmatch $generationPattern) { Fail-Backup }
    Assert-Generation $Source
    $destination = Join-Path $generationsRoot $Generation
    if (Test-Path -LiteralPath $destination) {
        if ((Get-GenerationId $destination) -cne $Generation) { Fail-Backup }
        return
    }
    $temporary = Join-Path $generationsRoot ".import-$Generation"
    if (Test-Path -LiteralPath $temporary) { Remove-SafeDirectory $temporary 'generation-temporary' }
    New-Item -ItemType Directory -Path $temporary | Out-Null
    Reject-Link $temporary
    Protect-Directory $temporary
    foreach ($name in @('checksums.sha256','database.dump','manifest.json','media.tar')) {
        [IO.File]::Copy((Join-Path $Source $name),(Join-Path $temporary $name),$false)
    }
    if ((Get-GenerationId $temporary) -cne $Generation) { Fail-Backup }
    [IO.Directory]::Move($temporary,$destination)
}

function Write-AtomicCatalog([string]$Current,[AllowNull()][string]$Previous) {
    if ($Current -notmatch $generationPattern -or
        ($null -ne $Previous -and ($Previous -notmatch $generationPattern -or $Previous -ceq $Current))) { Fail-Backup }
    if ((Get-GenerationId (Join-Path $generationsRoot $Current)) -cne $Current) { Fail-Backup }
    if ($null -ne $Previous -and (Get-GenerationId (Join-Path $generationsRoot $Previous)) -cne $Previous) { Fail-Backup }
    $temporary = Join-Path $backupRoot ".catalog-$Current.tmp"
    $backup = Join-Path $backupRoot ".catalog-$Current.previous"
    foreach ($path in @($temporary,$backup)) { if (Test-Path -LiteralPath $path) { Remove-SafeFile $path } }
    $value = [ordered]@{schemaVersion=1;current=$Current;previous=$Previous}
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -Compress -InputObject $value))
    $stream = [IO.File]::Open($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    $probe = Get-Content -Raw -LiteralPath $temporary | ConvertFrom-Json -DateKind String
    if ($probe.schemaVersion -ne 1 -or $probe.current -cne $Current -or $probe.previous -cne $Previous) { Fail-Backup }
    $script:publicationOutcome = 'unknown'
    if (Test-Path -LiteralPath $catalogPath) {
        [IO.File]::Replace($temporary,$catalogPath,$backup,$true)
    } else {
        [IO.File]::Move($temporary,$catalogPath)
    }
    $script:publicationOutcome = 'published'
    return $backup
}

function Remove-SafeFile([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = $backupRoot + [IO.Path]::DirectorySeparatorChar
    $leaf = [IO.Path]::GetFileName($full)
    if (!$full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or
        $leaf -notmatch "^\.catalog-$generationBody\.(tmp|previous)$") { Fail-Backup }
    if (Test-Path -LiteralPath $full) {
        Reject-Link $full
        $item = Get-Item -Force -LiteralPath $full
        if ($item.PSIsContainer) { Fail-Backup }
        Remove-Item -LiteralPath $full -Force
    }
}

function Remove-SafeDirectory([string]$Path,[string]$Kind) {
    $full = [IO.Path]::GetFullPath($Path)
    $leaf = [IO.Path]::GetFileName($full)
    if ($Kind -ceq 'root-temporary') {
        $prefix = $backupRoot + [IO.Path]::DirectorySeparatorChar
        $valid = $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -and $leaf -match "^\.staging-$generationBody$"
    } elseif ($Kind -ceq 'generation-temporary') {
        $prefix = [IO.Path]::GetFullPath($generationsRoot) + [IO.Path]::DirectorySeparatorChar
        $valid = $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -and $leaf -match "^\.import-$generationBody$"
    } elseif ($Kind -ceq 'generation') {
        $prefix = [IO.Path]::GetFullPath($generationsRoot) + [IO.Path]::DirectorySeparatorChar
        $valid = $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -and $leaf -match $generationPattern
    } elseif ($Kind -ceq 'legacy') {
        $prefix = $backupRoot + [IO.Path]::DirectorySeparatorChar
        $valid = $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -and $leaf -in @('current','previous')
    } else { $valid = $false }
    if (!$valid) { Fail-Backup }
    if (Test-Path -LiteralPath $full) {
        Reject-Link $full
        if (!(Get-Item -Force -LiteralPath $full).PSIsContainer) { Fail-Backup }
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

function Invoke-StorageCleanup([bool]$Strict) {
    try {
        $catalog = Get-Catalog
        foreach ($item in @(Get-ChildItem -Force -LiteralPath $backupRoot)) {
            if ($item.Name -match "^\.staging-$generationBody$") { Remove-SafeDirectory $item.FullName 'root-temporary' }
            elseif ($item.Name -match "^\.catalog-$generationBody\.(tmp|previous)$") { Remove-SafeFile $item.FullName }
            elseif ($item.Name -notin @('.backup.lock','catalog.json','generations','current','previous')) { Fail-Backup }
        }
        if (Test-Path -LiteralPath $generationsRoot) {
            Reject-Link $generationsRoot
            foreach ($item in @(Get-ChildItem -Force -LiteralPath $generationsRoot)) {
                if ($item.Name -match "^\.import-$generationBody$") { Remove-SafeDirectory $item.FullName 'generation-temporary'; continue }
                if (!$item.PSIsContainer -or $item.Name -notmatch $generationPattern) { Fail-Backup }
                if ($null -ne $catalog -and $item.Name -cne $catalog.current -and $item.Name -cne $catalog.previous) {
                    if ((Get-GenerationId $item.FullName) -cne $item.Name) { Fail-Backup }
                    Remove-SafeDirectory $item.FullName 'generation'
                }
            }
        }
        if ($null -ne $catalog) {
            foreach ($name in @('current','previous')) {
                $legacy = Join-Path $backupRoot $name
                if (Test-Path -LiteralPath $legacy) {
                    $id = Get-GenerationId $legacy
                    if ($id -cne $catalog.current -and $id -cne $catalog.previous) { Fail-Backup }
                    Remove-SafeDirectory $legacy 'legacy'
                }
            }
        }
        return $true
    } catch {
        if ($Strict) { throw }
        return $false
    }
}

function Initialize-Storage {
    New-Item -ItemType Directory -Force -Path $generationsRoot | Out-Null
    Reject-Link $generationsRoot
    Protect-Directory $generationsRoot
    if ($null -ne (Get-Catalog)) { return }
    $legacyCurrent = Join-Path $backupRoot 'current'
    $legacyPrevious = Join-Path $backupRoot 'previous'
    if (!(Test-Path -LiteralPath $legacyCurrent)) {
        if (Test-Path -LiteralPath $legacyPrevious) { Fail-Backup }
        return
    }
    $currentId = Get-GenerationId $legacyCurrent
    $previousId = $null
    if (Test-Path -LiteralPath $legacyPrevious) { $previousId = Get-GenerationId $legacyPrevious }
    Copy-Generation $legacyCurrent $currentId
    if ($null -ne $previousId) { Copy-Generation $legacyPrevious $previousId }
    $null = Write-AtomicCatalog $currentId $previousId
    if ($script:publicationOutcome -cne 'published') { Fail-Backup }
}

function Remove-TemporaryGeneration([string]$Path) {
    Remove-SafeDirectory $Path 'root-temporary'
}

$phase = 'preflight'
try {
    if (!(Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) { Fail-Backup }
    foreach ($path in @($repo,$work,$private,$manifestPath,$envFile,$toolPath)) {
        if (!(Test-Path -LiteralPath $path)) { Fail-Backup }
        Reject-Link $path
    }
    $foundation = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($foundation.environment -cne $Environment -or $foundation.composeProject -cne $project -or
        $foundation.privateDirectory -cne $private) { Fail-Backup }

    $postgresImage = Read-FoundationValue 'FOUNDATION_POSTGRES_IMAGE'
    if ($postgresImage -notmatch '^sha256:[0-9a-f]{64}$') { Fail-Backup }
    $image = @(Docker @('image','inspect',$postgresImage) | ConvertFrom-Json)
    if ($image.Count -ne 1 -or $image[0].Id -cne $postgresImage -or $image[0].Os -cne 'linux' -or
        $image[0].Architecture -cne 'amd64') { Fail-Backup }

    Assert-ScopedResource 'network' "$project-db"
    Assert-ScopedResource 'volume' "$project-state"

    $phase = 'lock'
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    Reject-Link $backupRoot
    Protect-Directory $backupRoot
    if (Test-Path -LiteralPath $lockPath) { Reject-Link $lockPath }
    $backupLock = [IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)

    $phase = 'maintenance'
    $maintenanceSnapshot = Get-MaintenanceSnapshot

    $phase = 'storage'
    Initialize-Storage
    $script:publicationOutcome = 'not-started'
    $null = Invoke-StorageCleanup $true

    $generation = [guid]::NewGuid().ToString()
    $createdAt = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ',[Globalization.CultureInfo]::InvariantCulture)
    $staging = Join-Path $backupRoot ".staging-$generation"
    New-Item -ItemType Directory -Path $staging | Out-Null
    Reject-Link $staging
    Protect-Directory $staging

    $phase = 'tool'
    $arguments = @(
        'run','--rm','--pull=never','--network',"$project-db",'--read-only','--user','10001:10001',
        '--cap-drop=ALL','--security-opt=no-new-privileges:true','--memory=512m','--cpus=1.0','--pids-limit=64',
        '--label',"nestakada.scope=$scope",'--tmpfs','/run/backup:rw,nosuid,nodev,noexec,size=1m,uid=10001,gid=10001,mode=0700',
        '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=32m,uid=10001,gid=10001,mode=1777',
        '--mount',"type=volume,source=$project-state,target=/var/lib/estakada,readonly",
        '--mount',"type=bind,source=$staging,target=/backup",
        '--mount',"type=bind,source=$private/migrator-password,target=/run/secrets/migrator-password,readonly",
        '--mount',"type=bind,source=$private/database-ca,target=/run/secrets/database-ca,readonly",
        '--mount',"type=bind,source=$toolPath,target=/tools/foundation_backup.sh,readonly",
        '--env','PGCONNECT_TIMEOUT=5','--env','PGSSLMODE=verify-full','--env','PGSSLROOTCERT=/run/secrets/database-ca',
        '--env','PGOPTIONS=-c default_transaction_read_only=on','--env',"BACKUP_GENERATION=$generation",'--env',"BACKUP_CREATED_AT=$createdAt",
        '--entrypoint','/bin/sh',$postgresImage,'/tools/foundation_backup.sh'
    )
    $toolResult = @(Docker $arguments)
    if ($toolResult.Count -ne 1 -or [string]$toolResult[0] -cne 'LOCAL_BACKUP_TOOL_OK') { Fail-Backup }
    $phase = 'validation'
    Assert-Generation $staging

    $phase = 'maintenance-recheck'
    if ((Get-MaintenanceSnapshot) -cne $maintenanceSnapshot) { Fail-Backup }

    $catalog = Get-Catalog
    $previousGeneration = if ($null -eq $catalog) { $null } else { [string]$catalog.current }
    $generationPath = Join-Path $generationsRoot $generation
    if (Test-Path -LiteralPath $generationPath) { Fail-Backup }
    [IO.Directory]::Move($staging,$generationPath)

    $phase = 'publication'
    $null = Write-AtomicCatalog $generation $previousGeneration
    if ($script:publicationOutcome -cne 'published') { Fail-Backup }
    $cleanupOk = Invoke-StorageCleanup $false
    if ($backupLock) { $backupLock.Dispose(); $backupLock = $null }
    $cleanup = if ($cleanupOk) { 'ok' } else { 'pending' }
    Write-Output "LOCAL_BACKUP_OK generation=$generation files=4 checksums=verified cleanup=$cleanup"
} catch {
    if (Get-Variable staging -ErrorAction SilentlyContinue) {
        try { Remove-TemporaryGeneration $staging } catch { }
    }
    if ($backupLock) { $backupLock.Dispose(); $backupLock = $null }
    if ($script:toolFailurePhase) { $phase = "tool-$($script:toolFailurePhase)" }
    if ($script:publicationOutcome -ceq 'unknown') {
        Write-Error 'LOCAL_BACKUP_OUTCOME_UNKNOWN phase=publication' -ErrorAction Continue
    } else {
        Write-Error "LOCAL_BACKUP_UNAVAILABLE phase=$phase" -ErrorAction Continue
    }
    exit 1
}
