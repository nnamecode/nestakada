#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Status','Inspect','SealSynthetic','Bootstrap','Switch','Recover','QuiesceRehearsal','DisposeRehearsal')]
    [string]$Action = 'Status',
    [ValidateSet('old','new')]
    [string]$TargetRole = 'new',
    [ValidateSet('actual','synthetic')]
    [string]$AuthoritySet = 'actual',
    [ValidateSet('none','after-prepared','after-ingress-stopped','after-selector-committed','after-ingress-started','after-observed','implementation-pre-cas','implementation-post-start','crash-after-ingress-stopped','crash-after-selector-committed')]
    [string]$TestFault = 'none'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workRoot = Join-Path $repo $(if ($AuthoritySet -ceq 'synthetic') { 'work\r7c-selector-synthetic' } else { 'work\r7c-selector' })
$authorityPath = Join-Path $workRoot 'authority.json'
$composeFile = Join-Path $repo 'environment\rebuild7-cutover\compose.yaml'
$envFile = Join-Path $workRoot 'compose.env'
$lockPath = Join-Path $workRoot 'coordinator.lock'
$resultRoot = Join-Path $workRoot 'results'
$utf8 = [Text.UTF8Encoding]::new($false)

if ($null -eq ('Estakada.R7C.NativeFile' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace Estakada.R7C {
    public static class NativeFile {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool MoveFileEx(string existingName, string newName, int flags);
    }
}
'@
}

function Fail-R7C([string]$Code = 'R7C_SELECTOR_OPERATION_UNAVAILABLE') { throw $Code }

function Invoke-CoordinatorFault([string]$Stage) {
    if ($TestFault -cne 'none' -and $AuthoritySet -cne 'synthetic') { Fail-R7C 'R7C_TEST_FAULT_FORBIDDEN' }
    if ($TestFault -ceq "crash-$Stage") { [Environment]::Exit(86) }
    if ($TestFault -ceq $Stage) { Fail-R7C "R7C_INJECTED_$Stage" }
}

function Invoke-ImplementationDrift([string]$Stage, [ref]$Binding) {
    if ($TestFault -ceq $Stage) {
        if ($AuthoritySet -cne 'synthetic') { Fail-R7C 'R7C_TEST_FAULT_FORBIDDEN' }
        $Binding.Value = '0' * 64
    }
}

function Move-FileWriteThrough([string]$Source, [string]$Destination, [bool]$Replace = $false) {
    $flags = if ($Replace) { 0x9 } else { 0x8 }
    if (![Estakada.R7C.NativeFile]::MoveFileEx($Source,$Destination,$flags)) {
        throw [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error())
    }
}

function Open-CoordinatorLock([bool]$AllowStaleRecovery = $false) {
    try { $handle=[IO.File]::Open($lockPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) } catch [IO.IOException] {
        if(!$AllowStaleRecovery){throw}
        $item=Get-Item -Force -LiteralPath $lockPath
        if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -gt 256){Fail-R7C 'R7C_COORDINATOR_LOCK_INVALID'}
        try{$record=Get-Content -Raw -LiteralPath $lockPath|ConvertFrom-Json}catch{Fail-R7C 'R7C_COORDINATOR_LOCK_INVALID'}
        $actualProperties = @($record.PSObject.Properties.Name | Sort-Object)
        $expectedProperties = @('pid','schema','startTicks' | Sort-Object)
        if(($actualProperties -join "`n") -cne ($expectedProperties -join "`n") -or [string]$record.schema -cne 'estakada.r7c-lock-v1' -or [int]$record.pid -lt 1 -or [long]$record.startTicks -lt 1){Fail-R7C 'R7C_COORDINATOR_LOCK_INVALID'}
        $live=Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
        if($null -ne $live -and $live.StartTime.ToUniversalTime().Ticks -eq [long]$record.startTicks){Fail-R7C 'R7C_COORDINATOR_LOCK_ACTIVE'}
        Remove-Item -LiteralPath $lockPath -Force
        $handle=[IO.File]::Open($lockPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    }
    $record=[ordered]@{schema='estakada.r7c-lock-v1';pid=$PID;startTicks=(Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks}
    $bytes=$utf8.GetBytes((ConvertTo-CompactJson $record)+"`n");$handle.Write($bytes,0,$bytes.Length);$handle.Flush($true)
    return $handle
}

function Close-CoordinatorLock([AllowNull()][IO.FileStream]$Handle) {
    if ($null -eq $Handle) { return }
    $Handle.Dispose()
    if (!(Test-Path -LiteralPath $lockPath -PathType Leaf)) { Fail-R7C 'R7C_COORDINATOR_LOCK_LOST' }
    $item = Get-Item -Force -LiteralPath $lockPath
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or ![string]::Equals($item.FullName,[IO.Path]::GetFullPath($lockPath),[StringComparison]::OrdinalIgnoreCase)) { Fail-R7C 'R7C_COORDINATOR_LOCK_INVALID' }
    Remove-Item -LiteralPath $lockPath -Force
}

function Assert-ExactProperties([object]$Value, [string[]]$Expected) {
    if ($null -eq $Value) { Fail-R7C }
    $actual = @($Value.PSObject.Properties.Name | Sort-Object)
    $wanted = @($Expected | Sort-Object)
    if (($actual -join "`n") -cne ($wanted -join "`n")) { Fail-R7C 'R7C_AUTHORITY_SHAPE_INVALID' }
}

function Assert-Hex([string]$Value, [int]$Length = 64, [string]$Code = 'R7C_HEX_INVALID') {
    if ($Value -cnotmatch "^[0-9a-f]{$Length}$") { Fail-R7C $Code }
}

function Assert-Name([string]$Value) {
    if ($Value -cnotmatch '^[a-z0-9][a-z0-9_.-]{2,127}$') { Fail-R7C 'R7C_RESOURCE_NAME_INVALID' }
}

function Assert-WorkDirectory([string]$Path, [bool]$Create = $false) {
    $full = [IO.Path]::GetFullPath($Path)
    $expectedParent = [IO.Path]::GetFullPath($workRoot)
    if ($full -cne $expectedParent -and ![string]::Equals([IO.Path]::GetDirectoryName($full),$expectedParent,[StringComparison]::OrdinalIgnoreCase)) { Fail-R7C 'R7C_WORK_DIRECTORY_INVALID' }
    if ($Create -and !(Test-Path -LiteralPath $full)) { [void](New-Item -ItemType Directory -Path $full) }
    if (!(Test-Path -LiteralPath $full -PathType Container)) { Fail-R7C 'R7C_WORK_DIRECTORY_INVALID' }
    $item = Get-Item -Force -LiteralPath $full
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail-R7C 'R7C_WORK_DIRECTORY_INVALID' }
    $owner = (Get-Acl -LiteralPath $full).Owner
    $current = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ($owner -cne $current) { Fail-R7C 'R7C_WORK_DIRECTORY_OWNER_INVALID' }
}

function Get-Sha256Text([string]$Value) {
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($Value))).ToLowerInvariant()
}

function ConvertTo-CompactJson([object]$Value, [int]$Depth = 12) {
    return ($Value | ConvertTo-Json -Depth $Depth -Compress)
}

function Read-Authority {
    if (!(Test-Path -LiteralPath $authorityPath -PathType Leaf)) { Fail-R7C 'R7C_AUTHORITY_MISSING' }
    $item = Get-Item -Force -LiteralPath $authorityPath
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -gt 65536) { Fail-R7C }
    $authority = Get-Content -Raw -LiteralPath $authorityPath | ConvertFrom-Json
    Assert-ExactProperties $authority @('schema','scope','runId','project','prefix','loopbackPort','appImage','ingressImage','selectorVolume','old','new','durableLocal')
    if ($authority.schema -cne 'estakada.r7c-authority-v1') { Fail-R7C }
    Assert-Hex ([string]$authority.runId) 32
    if ([string]$authority.scope -ceq "rehearsal:$($authority.runId)") {
        $expectedProject = "nestakada-r7c-rehearsal-$($authority.runId)"
        if ([int]$authority.loopbackPort -ne 18086) { Fail-R7C }
    } elseif ([string]$authority.scope -ceq 'local') {
        $expectedProject = 'nestakada-r7c-local'
        if ([int]$authority.loopbackPort -ne 18087) { Fail-R7C }
    } else { Fail-R7C 'R7C_SCOPE_INVALID' }
    if ([string]$authority.project -cne $expectedProject -or [string]$authority.prefix -cne $expectedProject) { Fail-R7C }
    if ([string]$authority.selectorVolume -cne "$expectedProject-selector") { Fail-R7C }
    foreach ($image in @([string]$authority.appImage,[string]$authority.ingressImage)) {
        if ($image -cnotmatch '^sha256:[0-9a-f]{64}$') { Fail-R7C 'R7C_IMAGE_ID_INVALID' }
    }
    foreach ($role in @('old','new')) {
        $target = $authority.$role
        Assert-ExactProperties $target @('generationSha256','storageBindingSha256','dbName','dbUser','dbContainer','dbImage','dbNetwork','sourceVolume','mediaVolume','secretsVolume','authorityVolume')
        Assert-Hex ([string]$target.generationSha256)
        Assert-Hex ([string]$target.storageBindingSha256)
        if ([string]$target.dbImage -cnotmatch '^sha256:[0-9a-f]{64}$') { Fail-R7C }
        foreach ($name in @('dbName','dbUser','dbContainer','dbNetwork','sourceVolume','mediaVolume','secretsVolume','authorityVolume')) { Assert-Name ([string]$target.$name) }
    }
    Assert-ExactProperties $authority.durableLocal @('selectorVolume','ingressName','ingressId','selectorSha256')
    foreach ($name in @('selectorVolume','ingressName')) { Assert-Name ([string]$authority.durableLocal.$name) }
    foreach ($value in @([string]$authority.durableLocal.ingressId,[string]$authority.durableLocal.selectorSha256)) {
        if ($value -cne 'ABSENT') { Assert-Hex $value }
    }
    if ($AuthoritySet -ceq 'synthetic') {
        if ([string]$authority.scope -cnotmatch '^rehearsal:' -or [string]$authority.project -cnotmatch '^nestakada-r7c-rehearsal-[0-9a-f]{32}$') { Fail-R7C 'R7C_SYNTHETIC_SCOPE_INVALID' }
        foreach ($role in @('old','new')) {
            $target = $authority.$role
            foreach ($field in @('dbContainer','dbNetwork','sourceVolume','mediaVolume','secretsVolume','authorityVolume')) {
                if ([string]$target.$field -cnotmatch "^$([regex]::Escape([string]$authority.project))-") { Fail-R7C 'R7C_SYNTHETIC_RESOURCE_INVALID' }
            }
        }
        if ([string]$authority.selectorVolume -cnotmatch "^$([regex]::Escape([string]$authority.project))-") { Fail-R7C 'R7C_SYNTHETIC_RESOURCE_INVALID' }
        foreach ($field in @('selectorVolume','ingressName')) {
            if ([string]$authority.durableLocal.$field -cnotmatch "^$([regex]::Escape([string]$authority.project))-sentinel-") { Fail-R7C 'R7C_SYNTHETIC_RESOURCE_INVALID' }
        }
    }
    return $authority
}

function Get-SafeTextFingerprint([AllowNull()][string]$Value) {
    if ($null -eq $Value) { $Value = '' }
    $bytes=$utf8.GetBytes($Value)
    return [pscustomobject]@{bytes=$bytes.Length;sha256=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()}
}

function Invoke-DockerProcess(
    [ValidateSet('CONTAINER_INSPECT','IMAGE_INSPECT','VOLUME_INSPECT','NETWORK_INSPECT','IMPLEMENTATION_INVENTORY','BINDING_OLD','BINDING_NEW','AUTHORITY_OLD','AUTHORITY_NEW','MEDIA_OLD','MEDIA_NEW','PROBE_OLD','PROBE_NEW','STORAGE_BINDING','SELECTOR_INSPECT','SELECTOR_RENDER','SELECTOR_JOURNAL_CREATE','SELECTOR_JOURNAL_TRANSITION','SELECTOR_RECOVERY_TRANSITION','SELECTOR_CAS','SELECTOR_CLEANUP','SELECTOR_RECEIPT','SELECTOR_UNLINK','SELECTOR_OPERATION_CLOSE','SELECTOR_EXTERNAL_RECEIPT','INGRESS_VALIDATE','TOOL_REMOVE','APP_CREATE','APP_START','INGRESS_CREATE','INGRESS_STOP','INGRESS_START','DURABLE_LOCAL_INSPECT','QUIESCE_STOP','DISPOSE_CONTAINER_LIST','DISPOSE_CONTAINER_REMOVE','DISPOSE_NETWORK_INSPECT','DISPOSE_NETWORK_REMOVE','DISPOSE_LINK_LIST','DISPOSE_VOLUME_INSPECT','DISPOSE_VOLUME_REMOVE','DISPOSE_POST_AUDIT')]
    [string]$Stage,
    [string[]]$Arguments,
    [AllowNull()][string]$InputText = $null,
    [bool]$AllowFailure = $false
) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = 'docker'
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.RedirectStandardInput = $null -ne $InputText
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    if (!$process.Start()) { Fail-R7C 'R7C_DOCKER_START_FAILED' }
    if ($null -ne $InputText) { $process.StandardInput.Write($InputText); $process.StandardInput.Close() }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult().Trim()
    $exit = $process.ExitCode
    $process.Dispose()
    if ($exit -ne 0 -and !$AllowFailure) {
        $argumentsFingerprint=Get-SafeTextFingerprint (ConvertTo-CompactJson @($Arguments))
        $inputFingerprint=Get-SafeTextFingerprint $InputText;$stdoutFingerprint=Get-SafeTextFingerprint $stdout;$stderrFingerprint=Get-SafeTextFingerprint $stderr
        Fail-R7C "R7C_DOCKER_COMMAND_FAILED stage=$Stage exit=$exit argsSha256=$($argumentsFingerprint.sha256) inputPresent=$(if($null -eq $InputText){0}else{1}) inputBytes=$($inputFingerprint.bytes) inputSha256=$($inputFingerprint.sha256) stdoutBytes=$($stdoutFingerprint.bytes) stdoutSha256=$($stdoutFingerprint.sha256) stderrBytes=$($stderrFingerprint.bytes) stderrSha256=$($stderrFingerprint.sha256)"
    }
    return [pscustomobject]@{ ExitCode=$exit; Stdout=$stdout; Stderr=$stderr }
}

function Invoke-Docker([string]$Stage,[string[]]$Arguments) {
    return (Invoke-DockerProcess $Stage $Arguments).Stdout
}

function Get-DockerLines([string]$Stage,[string[]]$Arguments) {
    $text = Invoke-Docker $Stage $Arguments
    if ([string]::IsNullOrWhiteSpace($text)) { return @() }
    return @($text -split "`r?`n" | Where-Object { $_ -cne '' })
}

function Get-Container([string]$Name, [bool]$AllowMissing = $false) {
    $result = Invoke-DockerProcess 'CONTAINER_INSPECT' @('inspect',$Name) $null $true
    if ($result.ExitCode -ne 0) {
        if ($AllowMissing) { return $null }
        Fail-R7C 'R7C_CONTAINER_MISSING'
    }
    $rows = @($result.Stdout | ConvertFrom-Json)
    if ($rows.Count -ne 1) { Fail-R7C }
    return $rows[0]
}

function Assert-Image([string]$Image) {
    $rows = @(Invoke-Docker 'IMAGE_INSPECT' @('image','inspect',$Image) | ConvertFrom-Json)
    if ($rows.Count -ne 1 -or [string]$rows[0].Id -cne $Image) { Fail-R7C 'R7C_IMAGE_SUBSTITUTION' }
}

function Get-Volume([string]$Name) {
    $rows = @(Invoke-Docker 'VOLUME_INSPECT' @('volume','inspect',$Name) | ConvertFrom-Json)
    if ($rows.Count -ne 1 -or [string]$rows[0].Name -cne $Name) { Fail-R7C 'R7C_VOLUME_IDENTITY_MISMATCH' }
    return $rows[0]
}

function Assert-AuthorityResources([object]$Authority) {
    $selector = Get-Volume ([string]$Authority.selectorVolume)
    if ([string]$selector.Labels.'estakada.r7c.scope' -cne [string]$Authority.scope) { Fail-R7C 'R7C_SELECTOR_VOLUME_SCOPE_MISMATCH' }
    $names = @([string]$Authority.selectorVolume)
    foreach ($role in @('old','new')) {
        $target = $Authority.$role
        foreach ($field in @('sourceVolume','mediaVolume','secretsVolume','authorityVolume')) { $names += [string]$target.$field }
        $networkRows = @(Invoke-Docker 'NETWORK_INSPECT' @('network','inspect',[string]$target.dbNetwork) | ConvertFrom-Json)
        if ($networkRows.Count -ne 1 -or [string]$networkRows[0].Name -cne [string]$target.dbNetwork) { Fail-R7C 'R7C_DB_NETWORK_IDENTITY_MISMATCH' }
        $db = Get-Container ([string]$target.dbContainer)
        if (![bool]$db.State.Running -or [string]$db.Image -cne [string]$target.dbImage) { Fail-R7C 'R7C_DB_IDENTITY_MISMATCH' }
        $dbNetworks = @($db.NetworkSettings.Networks.PSObject.Properties.Name)
        if ([string]$target.dbNetwork -cnotin $dbNetworks) { Fail-R7C 'R7C_DB_NETWORK_IDENTITY_MISMATCH' }
    }
    $distinct = @($names | Sort-Object -Unique)
    if ($distinct.Count -ne $names.Count) { Fail-R7C 'R7C_VOLUME_ALIAS_COLLISION' }
    foreach ($name in $distinct) { [void](Get-Volume $name) }
}

function Assert-PortUnused([int]$Port) {
    $listeners = @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq $Port })
    if ($listeners.Count -ne 0) { Fail-R7C 'R7C_LOOPBACK_PORT_IN_USE' }
}

function Assert-Ingress([object]$Authority, [object]$Ingress) {
    if ([string]$Ingress.Image -cne [string]$Authority.ingressImage -or [string]$Ingress.Config.Labels.'estakada.r7c.scope' -cne [string]$Authority.scope) { Fail-R7C 'R7C_INGRESS_IDENTITY_MISMATCH' }
    $bindings = @($Ingress.HostConfig.PortBindings.'8080/tcp')
    if ($bindings.Count -ne 1 -or [string]$bindings[0].HostIp -cne '127.0.0.1' -or [string]$bindings[0].HostPort -cne [string]$Authority.loopbackPort) { Fail-R7C 'R7C_INGRESS_PORT_MISMATCH' }
}

function Get-ComposeArguments([object]$Authority, [string[]]$Tail) {
    return @('compose','--env-file',$envFile,'--project-name',[string]$Authority.project,'--file',$composeFile) + $Tail
}

function Write-ComposeEnvironment([object]$Authority) {
    $lines = [ordered]@{
        R7C_PROJECT=[string]$Authority.project; R7C_PREFIX=[string]$Authority.prefix; R7C_SCOPE=[string]$Authority.scope
        R7C_SYNTHETIC=$(if($AuthoritySet -ceq 'synthetic'){'1'}else{'0'})
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
    $text = (($lines.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "`n") + "`n"
    if ($text -match 'ESTAKADA_RESTORE_VERIFY_WRITE') { Fail-R7C }
    [IO.File]::WriteAllText($envFile,$text,$utf8)
}

function Invoke-Tool(
    [object]$Authority,
    [ValidateSet('IMPLEMENTATION_INVENTORY','BINDING_OLD','BINDING_NEW','AUTHORITY_OLD','AUTHORITY_NEW','MEDIA_OLD','MEDIA_NEW','PROBE_OLD','PROBE_NEW','STORAGE_BINDING','SELECTOR_INSPECT','SELECTOR_RENDER','SELECTOR_JOURNAL_CREATE','SELECTOR_JOURNAL_TRANSITION','SELECTOR_RECOVERY_TRANSITION','SELECTOR_CAS','SELECTOR_CLEANUP','SELECTOR_RECEIPT','SELECTOR_UNLINK','SELECTOR_OPERATION_CLOSE','SELECTOR_EXTERNAL_RECEIPT','INGRESS_VALIDATE')]
    [string]$Stage,
    [string]$Service,
    [string[]]$Command = @(),
    [AllowNull()][string]$InputText = $null
) {
    if ($Service -notin @('selector-control','selector-verify','binding-old','binding-new','media-old','media-new','authority-old','authority-new','probe-old','probe-new','ingress-validate')) { Fail-R7C }
    $name = "$($Authority.prefix)-tool-$Service-$([guid]::NewGuid().ToString('N'))"
    $args = Get-ComposeArguments $Authority (@('run','--name',$name,'--no-deps','-T',$Service) + $Command)
    $container = $null
    try {
        $result = Invoke-DockerProcess $Stage $args $InputText $false
        $container = Get-Container $name
        if ([string]$container.Config.Labels.'com.docker.compose.project' -cne [string]$Authority.project -or [string]$container.Config.Labels.'estakada.r7c.scope' -cne [string]$Authority.scope) { Fail-R7C 'R7C_TOOL_IDENTITY_MISMATCH' }
        return [pscustomobject]@{ Output=$result.Stdout; Container=$container }
    } finally {
        $existing = Get-Container $name $true
        if ($null -ne $existing) {
            $id = [string]$existing.Id
            $check = Get-Container $id
            if ([string]$check.Id -cne $id) { Fail-R7C }
            Invoke-Docker 'TOOL_REMOVE' @('rm',$id) | Out-Null
        }
    }
}

function Read-ToolJson([object]$ToolResult) {
    if ([string]::IsNullOrWhiteSpace([string]$ToolResult.Output)) { Fail-R7C }
    try { return ([string]$ToolResult.Output | ConvertFrom-Json) } catch { Fail-R7C 'R7C_TOOL_JSON_INVALID' }
}

function Get-ImplementationBinding([object]$Authority) {
    foreach ($image in @([string]$Authority.appImage,[string]$Authority.ingressImage,[string]$Authority.old.dbImage,[string]$Authority.new.dbImage)) { Assert-Image $image }
    $tool = Invoke-Tool $Authority 'IMPLEMENTATION_INVENTORY' 'selector-verify' @('python','-B','/project/tools/rebuild7_selector.py','implementation-inventory')
    $inventory = Read-ToolJson $tool
    if ([string]$inventory.schema -cne 'estakada.r7c-implementation-inventory-v1') { Fail-R7C }
    Assert-Hex ([string]$inventory.sha256)
    return Get-Sha256Text ((@([string]$inventory.sha256,[string]$Authority.appImage,[string]$Authority.ingressImage,[string]$Authority.old.dbImage,[string]$Authority.new.dbImage) -join '|'))
}

function Get-MountToken([object]$Container, [string]$Destination, [string]$ExpectedName) {
    $mounts = @($Container.Mounts | Where-Object { [string]$_.Destination -ceq $Destination })
    if ($mounts.Count -ne 1 -or [string]$mounts[0].Type -cne 'volume' -or [string]$mounts[0].Name -cne $ExpectedName -or [bool]$mounts[0].RW) { Fail-R7C 'R7C_MOUNT_IDENTITY_MISMATCH' }
    return Get-Sha256Text ("volume|$ExpectedName|$Destination|False")
}

function Get-StorageBinding([object]$Authority, [ValidateSet('old','new')][string]$Role, [bool]$EnforceExpected = $true) {
    $target = $Authority.$Role
    $db = Get-Container ([string]$target.dbContainer)
    if (![bool]$db.State.Running -or [string]$db.Image -cne [string]$target.dbImage) { Fail-R7C 'R7C_DB_IDENTITY_MISMATCH' }
    $capture = Read-ToolJson (Invoke-Tool $Authority $(if($Role -ceq 'old'){'BINDING_OLD'}else{'BINDING_NEW'}) "binding-$Role")
    $authorityResult = Read-ToolJson (Invoke-Tool $Authority $(if($Role -ceq 'old'){'AUTHORITY_OLD'}else{'AUTHORITY_NEW'}) "authority-$Role")
    $mediaRun = Invoke-Tool $Authority $(if($Role -ceq 'old'){'MEDIA_OLD'}else{'MEDIA_NEW'}) "media-$Role"
    $match = [regex]::Match([string]$mediaRun.Output,'^R7_MEDIA_CHECK_OK files=([0-9]+) bytes=([0-9]+)(?:\r?\n)?$')
    if (!$match.Success -or [int]$match.Groups[1].Value -ne [int]$authorityResult.files -or [long]$match.Groups[2].Value -ne [long]$authorityResult.bytes) { Fail-R7C 'R7C_MEDIA_CHECK_INVALID' }
    $authorityAfter = Read-ToolJson (Invoke-Tool $Authority $(if($Role -ceq 'old'){'AUTHORITY_OLD'}else{'AUTHORITY_NEW'}) "authority-$Role")
    if ((ConvertTo-CompactJson $authorityAfter) -cne (ConvertTo-CompactJson $authorityResult)) { Fail-R7C 'R7C_MEDIA_AUTHORITY_DRIFT' }
    $mediaReceipt = [ordered]@{
        schema='estakada.r7-media-check-v1'; verifierContainerId=[string]$mediaRun.Container.Id; verifierImageId=[string]$mediaRun.Container.Image
        mediaMountToken=(Get-MountToken $mediaRun.Container '/media-source' ([string]$target.mediaVolume))
        authorityFileSha256=[string]$authorityResult.authorityFileSha256; authorityCanonicalSha256=[string]$authorityResult.authorityCanonicalSha256
        inventorySha256=[string]$authorityResult.inventorySha256; files=[int]$authorityResult.files; bytes=[long]$authorityResult.bytes; result='PASS'
    }
    $input = [ordered]@{ capture=$capture; mediaCheck=$mediaReceipt }
    $binding = Read-ToolJson (Invoke-Tool $Authority 'STORAGE_BINDING' 'selector-verify' @('python','-B','/project/tools/rebuild7_selector.py','storage-binding') ((ConvertTo-CompactJson $input) + "`n"))
    if ($EnforceExpected -and [string]$binding.storageBindingSha256 -cne [string]$target.storageBindingSha256) { Fail-R7C 'R7C_STORAGE_BINDING_MISMATCH' }
    return $binding
}

function Invoke-SealSynthetic([object]$Authority) {
    if ($AuthoritySet -cne 'synthetic' -or [string]$Authority.scope -cnotmatch '^rehearsal:') { Fail-R7C 'R7C_SYNTHETIC_SEAL_FORBIDDEN' }
    Assert-AuthorityResources $Authority
    $old = Get-StorageBinding $Authority 'old' $false
    $new = Get-StorageBinding $Authority 'new' $false
    $Authority.old.storageBindingSha256 = [string]$old.storageBindingSha256
    $Authority.new.storageBindingSha256 = [string]$new.storageBindingSha256
    $temporary = "$authorityPath.tmp-$([guid]::NewGuid().ToString('N'))"
    $stream = [IO.FileStream]::new($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {
        $bytes = $utf8.GetBytes((ConvertTo-CompactJson $Authority) + "`n")
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    Move-FileWriteThrough $temporary $authorityPath $true
    Write-Output "R7C_SYNTHETIC_SEAL_PASS old=$($old.storageBindingSha256) new=$($new.storageBindingSha256)"
}

function Get-App([object]$Authority, [ValidateSet('old','new')][string]$Role, [bool]$RequireRunning = $true) {
    $target = $Authority.$Role
    $name = "$($Authority.prefix)-$Role-app"
    $container = Get-Container $name
    if (($RequireRunning -and ![bool]$container.State.Running) -or [string]$container.Image -cne [string]$Authority.appImage -or [string]$container.Config.Labels.'estakada.r7c.scope' -cne [string]$Authority.scope) { Fail-R7C 'R7C_APP_IDENTITY_MISMATCH' }
    $environment = @($container.Config.Env)
    if ($environment -match '^ESTAKADA_RESTORE_VERIFY_WRITE=') { Fail-R7C 'R7C_WRITE_ESCAPE_PRESENT' }
    foreach ($expected in @("ESTAKADA_R7C_ROLE=$Role","ESTAKADA_R7C_GENERATION_SHA256=$($target.generationSha256)","ESTAKADA_R7C_STORAGE_BINDING_SHA256=$($target.storageBindingSha256)")) {
        if ($expected -cnotin $environment) { Fail-R7C 'R7C_APP_ENV_MISMATCH' }
    }
    [void](Get-MountToken $container '/app' ([string]$target.sourceVolume))
    [void](Get-MountToken $container '/media-source' ([string]$target.mediaVolume))
    [void](Get-MountToken $container '/run/secrets' ([string]$target.secretsVolume))
    $webName = "$($Authority.prefix)-$Role-web"
    $networkNames = @($container.NetworkSettings.Networks.PSObject.Properties.Name | Sort-Object)
    $expectedNetworks = @($webName,[string]$target.dbNetwork | Sort-Object)
    if (($networkNames -join "`n") -cne ($expectedNetworks -join "`n")) { Fail-R7C 'R7C_APP_NETWORK_MISMATCH' }
    $networkRows = @(Invoke-Docker 'NETWORK_INSPECT' @('network','inspect',$webName) | ConvertFrom-Json)
    if ($networkRows.Count -ne 1 -or [string]$networkRows[0].Labels.'estakada.r7c.scope' -cne [string]$Authority.scope) { Fail-R7C 'R7C_APP_NETWORK_MISMATCH' }
    $alias = "r7c-$Role-app"
    $endpoint = $container.NetworkSettings.Networks.$webName
    if ($alias -cnotin @($endpoint.Aliases)) { Fail-R7C 'R7C_APP_ALIAS_MISMATCH' }
    if ($RequireRunning) {
        $aliasOwners = @()
        foreach ($member in @($networkRows[0].Containers.PSObject.Properties)) {
            $memberContainer = Get-Container ([string]$member.Name)
            if ($alias -cin @($memberContainer.NetworkSettings.Networks.$webName.Aliases)) { $aliasOwners += [string]$memberContainer.Id }
        }
        if ($aliasOwners.Count -ne 1 -or $aliasOwners[0] -cne [string]$container.Id) { Fail-R7C 'R7C_APP_ALIAS_MISMATCH' }
    }
    return $container
}

function Ensure-Apps([object]$Authority) {
    $oldName = "$($Authority.prefix)-old-app"; $newName = "$($Authority.prefix)-new-app"
    $old = Get-Container $oldName $true; $new = Get-Container $newName $true
    if (($null -eq $old) -xor ($null -eq $new)) { Fail-R7C 'R7C_PARTIAL_TARGET_TOPOLOGY' }
    if ($null -eq $old) {
        Invoke-Docker 'APP_CREATE' (Get-ComposeArguments $Authority @('create','old-app','new-app')) | Out-Null
        $old = Get-Container $oldName; $new = Get-Container $newName
    }
    [void](Get-App $Authority 'old' $false); [void](Get-App $Authority 'new' $false)
    foreach ($container in @($old,$new)) {
        if (![bool]$container.State.Running) { Invoke-Docker 'APP_START' @('start',[string]$container.Id) | Out-Null }
    }
    return [pscustomobject]@{old=(Get-App $Authority 'old');new=(Get-App $Authority 'new')}
}

function Invoke-DirectProbe([object]$Authority, [ValidateSet('old','new')][string]$Role) {
    $probe = Read-ToolJson (Invoke-Tool $Authority $(if($Role -ceq 'old'){'PROBE_OLD'}else{'PROBE_NEW'}) "probe-$Role")
    $target = $Authority.$Role
    if ([string]$probe.result -cne 'PASS' -or [string]$probe.role -cne $Role -or [string]$probe.generationSha256 -cne [string]$target.generationSha256 -or [string]$probe.storageBindingSha256 -cne [string]$target.storageBindingSha256) { Fail-R7C 'R7C_DIRECT_PROBE_MISMATCH' }
}

function Get-SingleHeader([Net.Http.HttpResponseMessage]$Response, [string]$Name) {
    $values = $null
    if (!$Response.Headers.TryGetValues($Name,[ref]$values)) { Fail-R7C 'R7C_HOST_PROBE_HEADER_MISSING' }
    $rows = @($values)
    if ($rows.Count -ne 1) { Fail-R7C 'R7C_HOST_PROBE_HEADER_DUPLICATE' }
    return [string]$rows[0]
}

function Invoke-HostProbe([object]$Authority, [ValidateSet('old','new')][string]$Role) {
    $target = $Authority.$Role
    $handler = [Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $handler.AllowAutoRedirect = $false
    $client = [Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(5)
    try {
        $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Get,"http://127.0.0.1:$($Authority.loopbackPort)/__r7c_target_identity__")
        $request.Headers.Host = 'r7c-probe.invalid'
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        $body = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        if ([int]$response.StatusCode -ne 204 -or $body.Length -ne 0 -or $response.Headers.Location -or $response.Headers.Contains('Set-Cookie')) { Fail-R7C 'R7C_HOST_MARKER_FAILED' }
        if ((Get-SingleHeader $response 'X-Estakada-R7C-Role') -cne $Role -or (Get-SingleHeader $response 'X-Estakada-R7C-Generation') -cne [string]$target.generationSha256 -or (Get-SingleHeader $response 'X-Estakada-R7C-Storage-Binding') -cne [string]$target.storageBindingSha256 -or (Get-SingleHeader $response 'Cache-Control') -cne 'no-store') { Fail-R7C 'R7C_HOST_MARKER_MISMATCH' }
        $response.Dispose(); $request.Dispose()
        $canaryPath = if ($AuthoritySet -ceq 'synthetic') { '/synthetic-canary/' } else { '/robots.txt' }
        $canary = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Head,"http://127.0.0.1:$($Authority.loopbackPort)$canaryPath")
        $canary.Headers.Host = "localhost:$($Authority.loopbackPort)"
        $canaryResponse = $client.SendAsync($canary).GetAwaiter().GetResult()
        if ([int]$canaryResponse.StatusCode -ne 200 -or $canaryResponse.Headers.Location) { Fail-R7C 'R7C_PUBLIC_CANARY_FAILED' }
        $canaryResponse.Dispose(); $canary.Dispose()
    } finally { $client.Dispose(); $handler.Dispose() }
}

function Invoke-SelectorTool([object]$Authority, [string[]]$Command, [AllowNull()][object]$Payload = $null) {
    $stage = switch -CaseSensitive ([string]$Command[0]) {
        'inspect' { 'SELECTOR_INSPECT' }
        'render-candidate' { 'SELECTOR_RENDER' }
        'journal-create' { 'SELECTOR_JOURNAL_CREATE' }
        'journal-transition' { 'SELECTOR_JOURNAL_TRANSITION' }
        'journal-recovery-transition' { 'SELECTOR_RECOVERY_TRANSITION' }
        'selector-cas' { 'SELECTOR_CAS' }
        'cleanup-staging' { 'SELECTOR_CLEANUP' }
        'receipt-finalize' { 'SELECTOR_RECEIPT' }
        'selector-unlink' { 'SELECTOR_UNLINK' }
        'operation-close' { 'SELECTOR_OPERATION_CLOSE' }
        default { Fail-R7C 'R7C_SELECTOR_STAGE_INVALID' }
    }
    $text = if ($null -eq $Payload) { $null } else { (ConvertTo-CompactJson $Payload) + "`n" }
    return Read-ToolJson (Invoke-Tool $Authority $stage 'selector-control' (@('python','-B','/project/tools/rebuild7_selector.py') + $Command) $text)
}

function Update-Journal([object]$Authority, [object]$Journal, [string]$Phase) {
    return Invoke-SelectorTool $Authority @('journal-transition','--expected',[string]$Journal.sha256,'--phase',$Phase)
}

function Update-RecoveryJournal([object]$Authority, [object]$Journal, [string]$SelectorDigest, [string]$Phase) {
    return Invoke-SelectorTool $Authority @('journal-recovery-transition','--expected',[string]$Journal.sha256,'--selector',$SelectorDigest,'--phase',$Phase)
}

function Get-RollbackRunId([string]$RunId) { return (Get-Sha256Text "rollback:$RunId").Substring(0,32) }

function Write-ExternalReceipt([object]$Authority, [object]$Receipt) {
    Assert-WorkDirectory $workRoot
    Assert-WorkDirectory $resultRoot $true
    $path = Join-Path $resultRoot "$($Authority.runId)-$($Receipt.sha256).json"
    if (Test-Path -LiteralPath $path) { Fail-R7C 'R7C_EXTERNAL_RECEIPT_EXISTS' }
    $temporary = "$path.tmp-$([guid]::NewGuid().ToString('N'))"
    Assert-Hex ([string]$Receipt.sha256)
    $record = [ordered]@{schema='estakada.r7c-external-receipt-v1';receiptSha256=[string]$Receipt.sha256;receipt=$Receipt}
    $stream = [IO.FileStream]::new($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {
        $bytes = $utf8.GetBytes((ConvertTo-CompactJson $record) + "`n")
        $stream.Write($bytes,0,$bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    Move-FileWriteThrough $temporary $path
    $reopened = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if ([string]$reopened.receiptSha256 -cne [string]$Receipt.sha256) { Fail-R7C 'R7C_EXTERNAL_RECEIPT_WRITE_FAILED' }
}

function Read-ExternalReceipt([string]$RunId, [AllowNull()][object]$ReceiptSha256 = $null, [AllowNull()][object]$JournalSha256 = $null) {
    if ($RunId -cnotmatch '^[0-9a-f]{32}$') { Fail-R7C 'R7C_EXTERNAL_RECEIPT_RUN_INVALID' }
    if ($null -ne $ReceiptSha256) {
        if ($ReceiptSha256 -isnot [string]) { Fail-R7C 'R7C_EXTERNAL_RECEIPT_ARGUMENT_INVALID' }
        Assert-Hex ([string]$ReceiptSha256) 64 'R7C_EXTERNAL_RECEIPT_ARGUMENT_INVALID'
    }
    if ($null -ne $JournalSha256) {
        if ($JournalSha256 -isnot [string]) { Fail-R7C 'R7C_EXTERNAL_JOURNAL_ARGUMENT_INVALID' }
        Assert-Hex ([string]$JournalSha256) 64 'R7C_EXTERNAL_JOURNAL_ARGUMENT_INVALID'
    }
    Assert-WorkDirectory $workRoot
    Assert-WorkDirectory $resultRoot
    $paths = if ($null -ne $ReceiptSha256) {
        @(Join-Path $resultRoot "$RunId-$ReceiptSha256.json")
    } else {
        @(Get-ChildItem -LiteralPath $resultRoot -File -Filter "$RunId-*.json" | ForEach-Object { $_.FullName })
    }
    $candidates = @()
    foreach ($path in $paths) {
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $candidateItem = Get-Item -Force -LiteralPath $path
        if (($candidateItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $candidateItem.Length -gt 65536 -or $candidateItem.Name -cnotmatch "^$RunId-[0-9a-f]{64}\.json$") { Fail-R7C 'R7C_EXTERNAL_RECEIPT_INVALID' }
        try { $candidate = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json } catch { Fail-R7C 'R7C_EXTERNAL_RECEIPT_INVALID' }
        if ([string]$candidateItem.Name -cne "$RunId-$($candidate.receiptSha256).json") { Fail-R7C 'R7C_EXTERNAL_RECEIPT_INVALID' }
        if ($null -eq $JournalSha256 -or [string]$candidate.receipt.journalSha256 -ceq $JournalSha256) { $candidates += [pscustomobject]@{Path=$path;Value=$candidate} }
    }
    if ($candidates.Count -ne 1) { Fail-R7C 'R7C_EXTERNAL_RECEIPT_MISSING' }
    $path = [string]$candidates[0].Path
    $external = $candidates[0].Value
    Assert-ExactProperties $external @('schema','receiptSha256','receipt')
    if ([string]$external.schema -cne 'estakada.r7c-external-receipt-v1' -or [string]$external.receipt.sha256 -cne [string]$external.receiptSha256) { Fail-R7C 'R7C_EXTERNAL_RECEIPT_INVALID' }
    Assert-Hex ([string]$external.receiptSha256) 64 'R7C_EXTERNAL_RECEIPT_DIGEST_INVALID'
    return $external
}

function Close-PreviousOperation([object]$Authority, [object]$State) {
    if ($null -eq $State.journal -and $null -eq $State.receipt) { return }
    if ($null -eq $State.journal -or [string]$State.journal.state -cne 'PRESENT' -or [string]$State.journal.phase -notin @('CONFIRMED','ROLLED_BACK')) { Fail-R7C 'R7C_PREVIOUS_OPERATION_INCOMPLETE' }
    $receiptDigest = if ($null -ne $State.receipt -and [string]$State.receipt.state -ceq 'PRESENT') { [string]$State.receipt.sha256 } else { $null }
    $external = Read-ExternalReceipt ([string]$State.journal.runId) $receiptDigest ([string]$State.journal.sha256)
    if ([string]$external.receipt.journalSha256 -cne [string]$State.journal.sha256 -or [string]$external.receipt.scope -cne [string]$Authority.scope) { Fail-R7C 'R7C_PREVIOUS_OPERATION_AUTHORITY_MISMATCH' }
    if ($null -ne $State.receipt -and ([string]$State.receipt.state -cne 'PRESENT' -or [string]$State.receipt.sha256 -cne [string]$external.receiptSha256)) { Fail-R7C 'R7C_PREVIOUS_OPERATION_AUTHORITY_MISMATCH' }
    [void](Invoke-SelectorTool $Authority @('operation-close','--expected-receipt',[string]$external.receiptSha256,'--expected-journal',[string]$State.journal.sha256) $external.receipt)
    $closed = Invoke-SelectorTool $Authority @('inspect')
    if ($null -ne $closed.journal -or $null -ne $closed.receipt) { Fail-R7C 'R7C_PREVIOUS_OPERATION_CLOSE_FAILED' }
}

function Assert-PreviousOperationIdentities([object]$Authority, [object]$State) {
    if ($null -eq $State.journal -and $null -eq $State.receipt) { return }
    if ($null -eq $State.journal -or $null -eq $State.receipt -or [string]$State.journal.state -cne 'PRESENT' -or [string]$State.receipt.state -cne 'PRESENT') { Fail-R7C 'R7C_PREVIOUS_OPERATION_INCOMPLETE' }
    $external=Read-ExternalReceipt ([string]$State.journal.runId) ([string]$State.receipt.sha256) ([string]$State.journal.sha256)
    $expected=[ordered]@{"$($Authority.prefix)-old-app"=[string]$external.receipt.oldTargetId;"$($Authority.prefix)-new-app"=[string]$external.receipt.newTargetId;"$($Authority.prefix)-ingress"=[string]$external.receipt.ingressId}
    foreach($entry in $expected.GetEnumerator()){
        $container=Get-Container ([string]$entry.Key) $true
        if($null -eq $container -or [string]$container.Id -cne [string]$entry.Value){Fail-R7C 'R7C_TARGET_REPLACED'}
    }
}

function New-ReceiptInput([object]$Authority, [object]$Journal, [object]$Selector, [string]$Role, [string]$Result, [string]$ImplementationBinding) {
    $target = $Authority.$Role
    return [ordered]@{
        schema='estakada.r7c-receipt-v1'; scope=[string]$Authority.scope; runId=[string]$Authority.runId; result=$Result
        journalSha256=[string]$Journal.sha256; selectorSha256=[string]$Selector.selector.sha256; implementationImageBindingSha256=$ImplementationBinding
        ingressId=[string]$Journal.ingressId;oldTargetId=[string]$Journal.oldTargetId;newTargetId=[string]$Journal.newTargetId;expectedSelector=[string]$Journal.expectedSelector
        observedRole=$Role; observedGenerationSha256=[string]$target.generationSha256; storageBindingSha256=[string]$target.storageBindingSha256
        mutationBitmap=[ordered]@{admin='CLOSED';cleanup='CLOSED';editor='CLOSED';request='CLOSED';scheduler='CLOSED';upload='CLOSED'}; cleanup='EXACT'
    }
}

function Invoke-Operation([object]$Authority, [bool]$Bootstrap, [string]$Role) {
    $lock = $null; $journal = $null; $ingress = $null; $committed = $false; $candidate = $null; $preState = $null; $implementation = $null; $previousRole = $null
    try {
        if (!(Test-Path -LiteralPath $workRoot -PathType Container)) { Fail-R7C 'R7C_WORK_ROOT_MISSING' }
        $lock = Open-CoordinatorLock
        Write-ComposeEnvironment $Authority
        Assert-AuthorityResources $Authority
        $implementation = Get-ImplementationBinding $Authority
        $preState = Invoke-SelectorTool $Authority @('inspect')
        Assert-PreviousOperationIdentities $Authority $preState
        $apps = Ensure-Apps $Authority
        $oldApp = $apps.old; $newApp = $apps.new
        [void](Get-StorageBinding $Authority 'old'); [void](Get-StorageBinding $Authority 'new')
        Invoke-DirectProbe $Authority 'old'; Invoke-DirectProbe $Authority 'new'
        Close-PreviousOperation $Authority $preState
        $preState = Invoke-SelectorTool $Authority @('inspect')
        if ($Bootstrap) {
            if ([string]$preState.selector.state -cne 'ABSENT' -or $Role -cne 'old') { Fail-R7C 'R7C_BOOTSTRAP_PRECONDITION' }
            $expected = 'ABSENT'
        } else {
            if ([string]$preState.selector.state -cne 'PRESENT') { Fail-R7C 'R7C_SWITCH_PRECONDITION' }
            $previousRole = [string]$preState.selector.selector.role
            if ($previousRole -notin @('old','new') -or $previousRole -ceq $Role) { Fail-R7C 'R7C_SWITCH_PRECONDITION' }
            $expected = [string]$preState.selector.selector.sha256
        }
        $candidate = Invoke-SelectorTool $Authority @('render-candidate','--run',[string]$Authority.runId,'--scope',[string]$Authority.scope,'--role',$Role,'--generation',[string]$Authority.$Role.generationSha256)
        [void](Invoke-Tool $Authority 'INGRESS_VALIDATE' 'ingress-validate')
        $rollbackRun = Get-RollbackRunId ([string]$Authority.runId)
        if (!$Bootstrap) { [void](Invoke-SelectorTool $Authority @('render-candidate','--run',$rollbackRun,'--scope',[string]$Authority.scope,'--role',$previousRole,'--generation',[string]$Authority.$previousRole.generationSha256)) }
        $existingIngress = Get-Container "$($Authority.prefix)-ingress" $true
        if ($null -eq $existingIngress) { Assert-PortUnused ([int]$Authority.loopbackPort) }
        Invoke-Docker 'INGRESS_CREATE' (Get-ComposeArguments $Authority @('create','ingress')) | Out-Null
        $ingress = Get-Container "$($Authority.prefix)-ingress"
        Assert-Ingress $Authority $ingress
        $journalInput = [ordered]@{
            schema='estakada.r7c-journal-v1';scope=[string]$Authority.scope;runId=[string]$Authority.runId;phase='PREPARED';ingressId=[string]$ingress.Id
            oldTargetId=[string]$oldApp.Id;newTargetId=[string]$newApp.Id;oldStorageBindingSha256=[string]$Authority.old.storageBindingSha256
            newStorageBindingSha256=[string]$Authority.new.storageBindingSha256;expectedSelector=$expected;candidateSelectorSha256=[string]$candidate.sha256
            implementationImageBindingSha256=$implementation;mutationBitmap=[ordered]@{admin='CLOSED';cleanup='CLOSED';editor='CLOSED';request='CLOSED';scheduler='CLOSED';upload='CLOSED'}
        }
        $journal = Invoke-SelectorTool $Authority @('journal-create') $journalInput
        Invoke-CoordinatorFault 'after-prepared'
        $freshIngress = Get-Container ([string]$ingress.Id)
        if ([bool]$freshIngress.State.Running) { Invoke-Docker 'INGRESS_STOP' @('stop','--time','10',[string]$ingress.Id) | Out-Null }
        $freshIngress = Get-Container ([string]$ingress.Id)
        if ([bool]$freshIngress.State.Running) { Fail-R7C 'R7C_INGRESS_STOP_FAILED' }
        Assert-PortUnused ([int]$Authority.loopbackPort)
        $journal = Update-Journal $Authority $journal 'INGRESS_STOPPED'
        Invoke-CoordinatorFault 'after-ingress-stopped'
        Invoke-ImplementationDrift 'implementation-pre-cas' ([ref]$implementation)
        if ((Get-ImplementationBinding $Authority) -cne $implementation) { Fail-R7C 'R7C_IMPLEMENTATION_DRIFT' }
        $freshOld = Get-App $Authority 'old'; $freshNew = Get-App $Authority 'new'
        if ([string]$freshOld.Id -cne [string]$journal.oldTargetId -or [string]$freshNew.Id -cne [string]$journal.newTargetId) { Fail-R7C 'R7C_TARGET_REPLACED' }
        [void](Get-StorageBinding $Authority 'old'); [void](Get-StorageBinding $Authority 'new')
        Invoke-DirectProbe $Authority 'old'; Invoke-DirectProbe $Authority 'new'
        $selector = Invoke-SelectorTool $Authority @('selector-cas','--expected',$expected,'--run',[string]$Authority.runId)
        $committed = $true
        $journal = Update-Journal $Authority $journal 'SELECTOR_COMMITTED'
        Invoke-CoordinatorFault 'after-selector-committed'
        $freshIngress = Get-Container ([string]$ingress.Id)
        if ([string]$freshIngress.Id -cne [string]$ingress.Id) { Fail-R7C }
        Invoke-Docker 'INGRESS_START' @('start',[string]$ingress.Id) | Out-Null
        $freshIngress = Get-Container ([string]$ingress.Id)
        if (![bool]$freshIngress.State.Running) { Fail-R7C 'R7C_INGRESS_START_FAILED' }
        $journal = Update-Journal $Authority $journal 'INGRESS_STARTED'
        Invoke-CoordinatorFault 'after-ingress-started'
        Invoke-ImplementationDrift 'implementation-post-start' ([ref]$implementation)
        if ((Get-ImplementationBinding $Authority) -cne $implementation) { Fail-R7C 'R7C_IMPLEMENTATION_DRIFT' }
        $freshTarget = Get-App $Authority $Role
        $expectedTargetId = if ($Role -ceq 'old') { [string]$journal.oldTargetId } else { [string]$journal.newTargetId }
        if ([string]$freshTarget.Id -cne $expectedTargetId) { Fail-R7C 'R7C_TARGET_REPLACED' }
        [void](Get-StorageBinding $Authority $Role); Invoke-DirectProbe $Authority $Role; Invoke-HostProbe $Authority $Role
        $observedPhase = if ($Role -ceq 'old') { 'OBSERVED_OLD' } else { 'OBSERVED_NEW' }
        $journal = Update-Journal $Authority $journal $observedPhase
        Invoke-CoordinatorFault 'after-observed'
        $journal = Update-Journal $Authority $journal 'CONFIRMED'
        if ((Get-ImplementationBinding $Authority) -cne $implementation) { Fail-R7C 'R7C_IMPLEMENTATION_DRIFT' }
        [void](Invoke-SelectorTool $Authority @('cleanup-staging','--run',[string]$Authority.runId))
        if (!$Bootstrap) { [void](Invoke-SelectorTool $Authority @('cleanup-staging','--run',$rollbackRun)) }
        $receiptInput = New-ReceiptInput $Authority $journal $selector $Role 'CONFIRMED' $implementation
        $receipt = Invoke-SelectorTool $Authority @('receipt-finalize') $receiptInput
        Write-ExternalReceipt $Authority $receipt
        Write-Output "R7C_SELECTOR_PASS scope=$($Authority.scope) role=$Role selector=$($selector.selector.sha256)"
    } catch {
        $original = $_.Exception.Message
        if ($null -ne $journal -and [string]$journal.phase -ceq 'CONFIRMED') {
            try {
                $confirmedIngress = Get-Container ([string]$ingress.Id)
                Assert-Ingress $Authority $confirmedIngress
                if (![bool]$confirmedIngress.State.Running) { Fail-R7C 'R7C_CONFIRMED_INGRESS_STOPPED' }
                Invoke-HostProbe $Authority $Role
            } catch { Fail-R7C 'R7C_CONFIRMED_STATE_UNPROVEN' }
            Fail-R7C "R7C_CONFIRMED_RECEIPT_INCOMPLETE_$original"
        }
        if ($null -ne $ingress) {
            try { $currentIngress = Get-Container ([string]$ingress.Id) $true; if ($null -ne $currentIngress -and [bool]$currentIngress.State.Running) { Invoke-Docker 'INGRESS_STOP' @('stop','--time','10',[string]$ingress.Id) | Out-Null } } catch {}
        }
        if ($committed -and $null -ne $journal) {
            try {
                if ((Get-ImplementationBinding $Authority) -cne $implementation) { Fail-R7C }
                $rollbackRole = if ($Bootstrap) { 'old' } else { $previousRole }
                [void](Get-StorageBinding $Authority $rollbackRole); Invoke-DirectProbe $Authority $rollbackRole
                if ([string]$preState.selector.state -ceq 'PRESENT') {
                    $rollbackRun = Get-RollbackRunId ([string]$Authority.runId)
                    $rollbackSelector = Invoke-SelectorTool $Authority @('selector-cas','--expected',[string]$candidate.sha256,'--run',$rollbackRun)
                    Invoke-Docker 'INGRESS_START' @('start',[string]$ingress.Id) | Out-Null
                    if ([string]$journal.phase -ceq 'SELECTOR_COMMITTED') { $journal = Update-Journal $Authority $journal 'INGRESS_STARTED' }
                    Invoke-HostProbe $Authority $rollbackRole
                    if ([string]$journal.phase -ceq 'INGRESS_STARTED') {
                        $rollbackObserved = if ($rollbackRole -ceq 'old') { 'OBSERVED_OLD' } else { 'OBSERVED_NEW' }
                        $journal = Update-Journal $Authority $journal $rollbackObserved
                    }
                    $journal = Update-Journal $Authority $journal 'ROLLED_BACK'
                    [void](Invoke-SelectorTool $Authority @('cleanup-staging','--run',[string]$Authority.runId)); [void](Invoke-SelectorTool $Authority @('cleanup-staging','--run',$rollbackRun))
                    $receipt = Invoke-SelectorTool $Authority @('receipt-finalize') (New-ReceiptInput $Authority $journal $rollbackSelector $rollbackRole 'ROLLED_BACK' $implementation)
                    Write-ExternalReceipt $Authority $receipt
                } else {
                    [void](Invoke-SelectorTool $Authority @('selector-unlink','--expected',[string]$candidate.sha256))
                    $journal = Update-Journal $Authority $journal 'UNKNOWN'
                }
            } catch {
                try { if ($null -ne $journal -and [string]$journal.phase -notin @('CONFIRMED','ROLLED_BACK','UNKNOWN')) { $journal = Update-Journal $Authority $journal 'UNKNOWN' } } catch {}
            }
        } elseif ($null -ne $journal) {
            try { if ([string]$journal.phase -notin @('CONFIRMED','ROLLED_BACK','UNKNOWN')) { $journal = Update-Journal $Authority $journal 'UNKNOWN' } } catch {}
        }
        Fail-R7C "R7C_SELECTOR_FAILED_$original"
    } finally {
        if (Test-Path -LiteralPath $envFile) { Remove-Item -LiteralPath $envFile -Force }
        Close-CoordinatorLock $lock
        $lock = $null
    }
}

function Invoke-Status([object]$Authority) {
    $names = @("$($Authority.prefix)-old-app","$($Authority.prefix)-new-app","$($Authority.prefix)-ingress")
    $containers = foreach ($name in $names) { $item = Get-Container $name $true; [ordered]@{name=$name;present=($null -ne $item);id=$(if($null -eq $item){$null}else{[string]$item.Id});state=$(if($null -eq $item){'ABSENT'}else{[string]$item.State.Status})} }
    $volumeResult = Invoke-DockerProcess 'VOLUME_INSPECT' @('volume','inspect',[string]$Authority.selectorVolume) $null $true
    $state = $null
    if ($volumeResult.ExitCode -eq 0) { $state = Invoke-SelectorTool $Authority @('inspect') }
    [ordered]@{schema='estakada.r7c-status-v1';scope=[string]$Authority.scope;selectorVolumePresent=($volumeResult.ExitCode -eq 0);state=$state;mutationBitmap=[ordered]@{admin='CLOSED';cleanup='CLOSED';editor='CLOSED';request='CLOSED';scheduler='CLOSED';upload='CLOSED'};containers=$containers} | ConvertTo-Json -Depth 8 -Compress
}

function Invoke-Recover([object]$Authority) {
    $state = Invoke-SelectorTool $Authority @('inspect')
    if ($null -eq $state.journal -or [string]$state.journal.state -cne 'PRESENT') { Fail-R7C 'R7C_RECOVERY_JOURNAL_REQUIRED' }
    $journal = $state.journal.value
    Assert-Hex ([string]$state.journal.sha256) 64 'R7C_RECOVERY_JOURNAL_INVALID'
    $journal | Add-Member -MemberType NoteProperty -Name sha256 -Value ([string]$state.journal.sha256)
    $ingress = Get-Container ([string]$journal.ingressId)
    if (([string]$ingress.Name).TrimStart('/') -cne "$($Authority.prefix)-ingress") { Fail-R7C 'R7C_RECOVERY_INGRESS_UNAUTHORIZED' }
    Assert-Ingress $Authority $ingress
    if ((Get-ImplementationBinding $Authority) -cne [string]$journal.implementationImageBindingSha256) { Fail-R7C 'R7C_IMPLEMENTATION_DRIFT' }
    $oldApp = Get-App $Authority 'old'; $newApp = Get-App $Authority 'new'
    if ([string]$oldApp.Id -cne [string]$journal.oldTargetId -or [string]$newApp.Id -cne [string]$journal.newTargetId) { Fail-R7C 'R7C_TARGET_REPLACED' }
    [void](Get-StorageBinding $Authority 'old'); [void](Get-StorageBinding $Authority 'new')
    Invoke-DirectProbe $Authority 'old'; Invoke-DirectProbe $Authority 'new'
    if ([string]$journal.phase -in @('CONFIRMED','ROLLED_BACK')) {
        if ($null -eq $state.receipt -or [string]$state.receipt.state -cne 'PRESENT') { Fail-R7C 'R7C_RECOVERY_RECEIPT_REQUIRED' }
        $role = [string]$state.selector.selector.role
        if (![bool]$ingress.State.Running) { Invoke-Docker 'INGRESS_START' @('start',[string]$ingress.Id) | Out-Null }
        Invoke-HostProbe $Authority $role
        Write-Output "R7C_RECOVERY_PASS phase=$($journal.phase) role=$role mutation=0"
        return
    }
    if ([string]$journal.phase -ceq 'UNKNOWN') {
        if ([bool]$ingress.State.Running) { Invoke-Docker 'INGRESS_STOP' @('stop','--time','10',[string]$ingress.Id) | Out-Null }
        Fail-R7C 'R7C_RECOVERY_OWNER_INSPECTION_REQUIRED'
    }
    if ([bool]$ingress.State.Running) { Invoke-Docker 'INGRESS_STOP' @('stop','--time','10',[string]$ingress.Id) | Out-Null }
    $selector = Invoke-SelectorTool $Authority @('inspect')
    if ([string]$selector.selector.state -cne 'PRESENT') { Fail-R7C 'R7C_RECOVERY_SELECTOR_UNKNOWN' }
    if ([string]$journal.phase -in @('PREPARED','INGRESS_STOPPED')) {
        if ([string]$journal.expectedSelector -ceq 'ABSENT' -or [string]$selector.selector.selector.sha256 -cne [string]$journal.expectedSelector) { Fail-R7C 'R7C_RECOVERY_OWNER_INSPECTION_REQUIRED' }
        $role = [string]$selector.selector.selector.role
        $selected = $selector.selector
        $precommitRecovery = $true
    } else {
        if ([string]$selector.selector.selector.sha256 -cne [string]$journal.candidateSelectorSha256 -or [string]$journal.expectedSelector -ceq 'ABSENT') { Fail-R7C 'R7C_RECOVERY_OWNER_INSPECTION_REQUIRED' }
        $role = if ([string]$selector.selector.selector.role -ceq 'old') { 'new' } else { 'old' }
        $rollbackRun = Get-RollbackRunId ([string]$journal.runId)
        $selected = Invoke-SelectorTool $Authority @('selector-cas','--expected',[string]$journal.candidateSelectorSha256,'--run',$rollbackRun)
        if ([string]$selected.selector.sha256 -cne [string]$journal.expectedSelector) { Fail-R7C 'R7C_RECOVERY_ROLLBACK_MISMATCH' }
        if ([string]$journal.phase -ceq 'SELECTOR_COMMITTED') { $journal = Update-Journal $Authority $journal 'INGRESS_STARTED' }
        $precommitRecovery = $false
    }
    Invoke-Docker 'INGRESS_START' @('start',[string]$ingress.Id) | Out-Null
    Invoke-HostProbe $Authority $role
    if ([string]$journal.phase -in @('PREPARED','INGRESS_STOPPED','INGRESS_STARTED')) {
        $observed = if ($role -ceq 'old') { 'OBSERVED_OLD' } else { 'OBSERVED_NEW' }
        if ($precommitRecovery) {
            $journal = Update-RecoveryJournal $Authority $journal ([string]$selected.selector.sha256) $observed
        } else {
            $journal = Update-Journal $Authority $journal $observed
        }
    }
    $journal = Update-Journal $Authority $journal 'ROLLED_BACK'
    [void](Invoke-SelectorTool $Authority @('cleanup-staging','--run',[string]$journal.runId))
    [void](Invoke-SelectorTool $Authority @('cleanup-staging','--run',(Get-RollbackRunId ([string]$journal.runId))))
    $receipt = Invoke-SelectorTool $Authority @('receipt-finalize') (New-ReceiptInput $Authority $journal $selected $role 'ROLLED_BACK' ([string]$journal.implementationImageBindingSha256))
    Write-ExternalReceipt $Authority $receipt
    Write-Output "R7C_RECOVERY_PASS phase=ROLLED_BACK role=$role"
}

function Get-DurableLocalSnapshot([object]$Authority) {
    if ([string]$Authority.scope -cnotmatch '^rehearsal:' -or [string]$Authority.durableLocal.selectorVolume -ceq [string]$Authority.selectorVolume) { Fail-R7C 'R7C_DURABLE_LOCAL_AUTHORITY_INVALID' }
    $volume = Get-Volume ([string]$Authority.durableLocal.selectorVolume)
    $run = Invoke-DockerProcess 'DURABLE_LOCAL_INSPECT' @(
        'run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--env','ESTAKADA_R7C_SELECTOR_OWNER_UID=0',
        '--mount',"type=bind,src=$repo,dst=/project,readonly",'--mount',"type=volume,src=$($Authority.durableLocal.selectorVolume),dst=/selector,readonly",
        '--workdir','/project',[string]$Authority.appImage,'python','-B','/project/tools/rebuild7_selector.py','inspect'
    )
    $state = $run.Stdout | ConvertFrom-Json
    $selectorDigest = if ([string]$state.selector.state -ceq 'ABSENT') { 'ABSENT' } elseif ([string]$state.selector.state -ceq 'PRESENT') { [string]$state.selector.selector.sha256 } else { Fail-R7C 'R7C_DURABLE_LOCAL_SELECTOR_UNKNOWN' }
    if ($selectorDigest -cne [string]$Authority.durableLocal.selectorSha256) { Fail-R7C 'R7C_DURABLE_LOCAL_DRIFT' }
    $ingress = Get-Container ([string]$Authority.durableLocal.ingressName) $true
    if ([string]$Authority.durableLocal.ingressId -ceq 'ABSENT') {
        if ($null -ne $ingress) { Fail-R7C 'R7C_DURABLE_LOCAL_DRIFT' }
        $ingressToken = 'ABSENT'
    } else {
        if ($null -eq $ingress -or [string]$ingress.Id -cne [string]$Authority.durableLocal.ingressId) { Fail-R7C 'R7C_DURABLE_LOCAL_DRIFT' }
        $ingressToken = "$($ingress.Id)|$($ingress.State.Status)"
    }
    return Get-Sha256Text "$($volume.Name)|$selectorDigest|$ingressToken"
}

function Get-RehearsalReceiptManifest([object]$Authority) {
    if ([string]$Authority.scope -cnotmatch '^rehearsal:') { Fail-R7C 'R7C_REHEARSAL_SCOPE_INVALID' }
    $state = Invoke-SelectorTool $Authority @('inspect')
    if ($null -eq $state.receipt -or [string]$state.receipt.state -cne 'PRESENT') { Fail-R7C 'R7C_RECEIPT_PRESERVATION_MISMATCH' }
    $external = Read-ExternalReceipt ([string]$Authority.runId) ([string]$state.receipt.sha256)
    $externalCheck = Read-ToolJson (Invoke-Tool $Authority 'SELECTOR_EXTERNAL_RECEIPT' 'selector-verify' @('python','-B','/project/tools/rebuild7_selector.py','receipt-verify-external') ((ConvertTo-CompactJson $external.receipt) + "`n"))
    if ([string]$externalCheck.sha256 -cne [string]$state.receipt.sha256 -or [string]$external.receipt.scope -cne [string]$Authority.scope) { Fail-R7C 'R7C_RECEIPT_PRESERVATION_MISMATCH' }
    return [pscustomobject]@{State=$state;External=$external}
}

function Invoke-QuiesceRehearsal([object]$Authority) {
    $manifest = Get-RehearsalReceiptManifest $Authority
    $expected = [ordered]@{
        "$($Authority.prefix)-old-app"=[string]$manifest.External.receipt.oldTargetId
        "$($Authority.prefix)-new-app"=[string]$manifest.External.receipt.newTargetId
        "$($Authority.prefix)-ingress"=[string]$manifest.External.receipt.ingressId
    }
    foreach ($entry in $expected.GetEnumerator()) {
        $container = Get-Container ([string]$entry.Value)
        if (([string]$container.Name).TrimStart('/') -cne [string]$entry.Key -or [string]$container.Config.Labels.'estakada.r7c.scope' -cne [string]$Authority.scope) { Fail-R7C 'R7C_QUIESCE_IDENTITY_MISMATCH' }
        if ([bool]$container.State.Running) { Invoke-Docker 'QUIESCE_STOP' @('stop','--time','10',[string]$container.Id) | Out-Null }
        if ([bool](Get-Container ([string]$container.Id)).State.Running) { Fail-R7C 'R7C_QUIESCE_FAILED' }
    }
    Write-Output "R7C_QUIESCE_PASS scope=$($Authority.scope) containers=3 stopped=3"
}

function Assert-NoSelectorVolumeMount([object]$Container, [string]$SelectorVolume) {
    foreach ($mount in @($Container.Mounts)) {
        $typeProperty = $mount.PSObject.Properties['Type']
        if ($null -eq $typeProperty -or $typeProperty.Value -isnot [string] -or ![string]$typeProperty.Value) { Fail-R7C 'R7C_DISPOSE_MOUNT_INVALID' }
        if ([string]$typeProperty.Value -cne 'volume') { continue }
        $nameProperty = $mount.PSObject.Properties['Name']
        if ($null -eq $nameProperty -or $nameProperty.Value -isnot [string] -or ![string]$nameProperty.Value) { Fail-R7C 'R7C_DISPOSE_MOUNT_INVALID' }
        if ([string]$nameProperty.Value -ceq $SelectorVolume) { Fail-R7C 'R7C_DISPOSE_VOLUME_LINKED' }
    }
}

function Invoke-DisposeRehearsal([object]$Authority) {
    if ([string]$Authority.scope -cnotmatch '^rehearsal:') { Fail-R7C 'R7C_DISPOSE_SCOPE_INVALID' }
    Write-ComposeEnvironment $Authority
    $durableBefore = Get-DurableLocalSnapshot $Authority
    $oldBindingBefore = ConvertTo-CompactJson (Get-StorageBinding $Authority 'old')
    $newBindingBefore = ConvertTo-CompactJson (Get-StorageBinding $Authority 'new')
    $manifest = Get-RehearsalReceiptManifest $Authority
    $state = $manifest.State; $external = $manifest.External
    if ([string]$external.schema -cne 'estakada.r7c-external-receipt-v1' -or [string]$state.receipt.state -cne 'PRESENT' -or [string]$state.receipt.sha256 -cne [string]$external.receiptSha256 -or [string]$external.receipt.sha256 -cne [string]$external.receiptSha256) { Fail-R7C 'R7C_RECEIPT_PRESERVATION_MISMATCH' }
    $ids = @(Get-DockerLines 'DISPOSE_CONTAINER_LIST' @('ps','-aq','--no-trunc','--filter',"label=com.docker.compose.project=$($Authority.project)"))
    $expectedNames = @("$($Authority.prefix)-old-app","$($Authority.prefix)-new-app","$($Authority.prefix)-ingress")
    $expectedIds = @([string]$external.receipt.oldTargetId,[string]$external.receipt.newTargetId,[string]$external.receipt.ingressId)
    if ($ids.Count -ne 3) { Fail-R7C 'R7C_DISPOSE_MANIFEST_MISMATCH' }
    foreach ($id in $ids) {
        $container = Get-Container $id
        $plainName = ([string]$container.Name).TrimStart('/')
        if ([string]$container.Config.Labels.'estakada.r7c.scope' -cne [string]$Authority.scope -or $plainName -cnotin $expectedNames -or [string]$container.Id -cnotin $expectedIds) { Fail-R7C 'R7C_DISPOSE_FOREIGN_CONTAINER' }
        if ([bool]$container.State.Running) { Fail-R7C 'R7C_DISPOSE_REQUIRES_QUIESCED' }
        Invoke-Docker 'DISPOSE_CONTAINER_REMOVE' @('rm',$id) | Out-Null
    }
    foreach ($networkName in @("$($Authority.prefix)-ingress","$($Authority.prefix)-old-web","$($Authority.prefix)-new-web")) {
        $result = Invoke-DockerProcess 'DISPOSE_NETWORK_INSPECT' @('network','inspect',$networkName) $null $true
        if ($result.ExitCode -eq 0) {
            $network = @($result.Stdout | ConvertFrom-Json)[0]
            if ([string]$network.Labels.'estakada.r7c.scope' -cne [string]$Authority.scope -or @($network.Containers.PSObject.Properties).Count -ne 0) { Fail-R7C 'R7C_DISPOSE_NETWORK_LINKED' }
            Invoke-Docker 'DISPOSE_NETWORK_REMOVE' @('network','rm',[string]$network.Id) | Out-Null
        }
    }
    if ((ConvertTo-CompactJson (Get-StorageBinding $Authority 'old')) -cne $oldBindingBefore -or (ConvertTo-CompactJson (Get-StorageBinding $Authority 'new')) -cne $newBindingBefore) { Fail-R7C 'R7C_DATA_POST_AUDIT_DRIFT' }
    $linked = @(Get-DockerLines 'DISPOSE_LINK_LIST' @('ps','-aq','--no-trunc'))
    foreach ($id in $linked) {
        $container = Get-Container $id
        Assert-NoSelectorVolumeMount $container ([string]$Authority.selectorVolume)
    }
    $volumeRows = @(Invoke-Docker 'DISPOSE_VOLUME_INSPECT' @('volume','inspect',[string]$Authority.selectorVolume) | ConvertFrom-Json)
    if ($volumeRows.Count -ne 1 -or [string]$volumeRows[0].Labels.'estakada.r7c.scope' -cne [string]$Authority.scope) { Fail-R7C 'R7C_DISPOSE_VOLUME_IDENTITY' }
    Invoke-Docker 'DISPOSE_VOLUME_REMOVE' @('volume','rm',[string]$Authority.selectorVolume) | Out-Null
    if (@(Get-DockerLines 'DISPOSE_POST_AUDIT' @('ps','-aq','--no-trunc','--filter',"label=com.docker.compose.project=$($Authority.project)")).Count -ne 0) { Fail-R7C 'R7C_DISPOSE_POST_AUDIT_FAILED' }
    foreach ($networkName in @("$($Authority.prefix)-ingress","$($Authority.prefix)-old-web","$($Authority.prefix)-new-web")) {
        if ((Invoke-DockerProcess 'DISPOSE_POST_AUDIT' @('network','inspect',$networkName) $null $true).ExitCode -eq 0) { Fail-R7C 'R7C_DISPOSE_POST_AUDIT_FAILED' }
    }
    if ((Invoke-DockerProcess 'DISPOSE_POST_AUDIT' @('volume','inspect',[string]$Authority.selectorVolume) $null $true).ExitCode -eq 0) { Fail-R7C 'R7C_DISPOSE_POST_AUDIT_FAILED' }
    if ((Get-DurableLocalSnapshot $Authority) -cne $durableBefore) { Fail-R7C 'R7C_DURABLE_LOCAL_DRIFT' }
    $externalAfter = Read-ExternalReceipt ([string]$Authority.runId) ([string]$state.receipt.sha256)
    if ([string]$externalAfter.receiptSha256 -cne [string]$external.receiptSha256) { Fail-R7C 'R7C_EVIDENCE_POST_AUDIT_DRIFT' }
    Write-Output "R7C_DISPOSE_PASS scope=$($Authority.scope) containers=0 networks=0 selector_volume=0"
}

if ($TestFault -cne 'none' -and $AuthoritySet -cne 'synthetic') { Fail-R7C 'R7C_TEST_FAULT_FORBIDDEN' }
Assert-WorkDirectory $workRoot
$authority = Read-Authority
$actionLock = $null
try {
    if ($Action -ceq 'Status') {
        $actionLock = Open-CoordinatorLock
        Write-ComposeEnvironment $authority
        Invoke-Status $authority
    } elseif ($Action -ceq 'Inspect') {
        $actionLock = Open-CoordinatorLock
        Write-ComposeEnvironment $authority
        $state = Invoke-SelectorTool $authority @('inspect')
        $implementation = Get-ImplementationBinding $authority
        [ordered]@{schema='estakada.r7c-inspect-v1';state=$state;implementationImageBindingSha256=$implementation} | ConvertTo-Json -Depth 8 -Compress
    } elseif ($Action -ceq 'SealSynthetic') {
        $actionLock = Open-CoordinatorLock
        Write-ComposeEnvironment $authority
        Invoke-SealSynthetic $authority
    } elseif ($Action -ceq 'Bootstrap') {
        Invoke-Operation $authority $true 'old'
    } elseif ($Action -ceq 'Switch') {
        Invoke-Operation $authority $false $TargetRole
    } elseif ($Action -ceq 'Recover') {
        $actionLock = Open-CoordinatorLock $true
        Write-ComposeEnvironment $authority
        Invoke-Recover $authority
    } elseif ($Action -ceq 'QuiesceRehearsal') {
        $actionLock = Open-CoordinatorLock
        Write-ComposeEnvironment $authority
        Invoke-QuiesceRehearsal $authority
    } else {
        $actionLock = Open-CoordinatorLock
        Write-ComposeEnvironment $authority
        Invoke-DisposeRehearsal $authority
    }
} finally {
    if (Test-Path -LiteralPath $envFile) { Remove-Item -LiteralPath $envFile -Force }
    Close-CoordinatorLock $actionLock
}
