$script:Contract = 'rb1-media-source-offline-v1'
$script:FailureCode = 'OFFLINE_FAILED_PRECHECK'
$script:FailureCase = 'precheck'
$script:AllowedFailureCases = @(
    'precheck','extraction','identity-baseline','identity-tmpfs',
    'identity-inspect-count-0','identity-inspect-count-2','cleanup-identity','state',
    'identity-drift-id','identity-drift-name','identity-drift-image','identity-drift-label',
    'identity-drift-user','identity-drift-network','identity-drift-root','identity-drift-log',
    'identity-drift-memory','identity-drift-memory-swap','identity-drift-cpu','identity-drift-pids',
    'identity-drift-capdrop','identity-drift-capadd','identity-drift-privileged',
    'identity-drift-autoremove','identity-drift-restart','identity-drift-security',
    'identity-drift-entrypoint','identity-drift-entrypoint-count','identity-drift-argv-prefix',
    'identity-drift-argv-s','identity-drift-argv-c','identity-drift-argv-code',
    'identity-drift-argv-count','identity-drift-mount-type','identity-drift-mount-name',
    'identity-drift-mount-destination','identity-drift-mount-write','identity-drift-mount-count'
)

function Stop-OfflineFailure([string]$Code = 'OFFLINE_FAILED') {
    $allowed = @(
        'OFFLINE_FAILED','OFFLINE_FAILED_PRECHECK','OFFLINE_FAILED_EXTRACTION',
        'OFFLINE_FAILED_IDENTITY','OFFLINE_FAILED_CLEANUP_IDENTITY',
        'OFFLINE_FAILED_STATE','OFFLINE_FAILED_BOUNDARY','OFFLINE_FAILED_OUTPUT'
    )
    if ($Code -cnotin $allowed) { $Code = 'OFFLINE_FAILED' }
    $case = $script:FailureCase
    if ($case -cnotin $script:AllowedFailureCases) { $case = 'precheck' }
    [Console]::Error.WriteLine(
        ('{{"contract":"{0}","status":"FAIL","code":"{1}","case":"{2}"}}' -f
            $script:Contract,$Code,$case))
    exit 1
}

trap { Stop-OfflineFailure $script:FailureCode }

if ($args.Count -ne 0) { Stop-OfflineFailure }
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$watch = [Diagnostics.Stopwatch]::StartNew()
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runnerPath = Join-Path $repo 'tools/rebuild-dbpre.ps1'
$runnerItem = Get-Item -Force -LiteralPath $runnerPath
if ($runnerItem.PSIsContainer -or ($runnerItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $runnerItem.Length -le 0 -or $runnerItem.Length -gt 2097152) {
    throw 'OFFLINE_RUNNER_SCOPE_REJECTED'
}

$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(
    $runnerItem.FullName,[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'OFFLINE_RUNNER_PARSE_REJECTED' }

$script:FailureCode = 'OFFLINE_FAILED_EXTRACTION'
$script:FailureCase = 'extraction'
$requiredFunctions = @(
    'Test-ExactVerifierIdentity',
    'Test-ExactVerifierCleanupIdentity',
    'Invoke-MediaVerifier'
)
$functionText = [ordered]@{}
foreach ($name in $requiredFunctions) {
    $matches = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -ceq $name
    },$true))
    if ($matches.Count -ne 1) { throw 'OFFLINE_FUNCTION_EXTRACTION_REJECTED' }
    $functionText[$name] = $matches[0].Extent.Text
}

$script:FakeId = 'a' * 64
$script:FakeOtherId = 'd' * 64
$script:FakeImage = 'sha256:' + ('b' * 64)
$script:verifierEvidence = 'c' * 32
$script:verifierName = "nestakada-media-source-$script:verifierEvidence"
$script:verifierLabel = 'nestakada.rebuild.media-source'
$script:stateVolumeName = 'nestakada-foundation-dev-state'
$script:private = 'X:\offline\private'
$script:verifierCidPath = 'X:\offline\private\rebuild-media-verifier.cid'
$script:ExpectedCode = 'print("offline")'
$script:ExpectedDescriptor = '{"key":"img/a.jpg","sha256":"' + ('0' * 64) + '","byteSize":1}'
$script:Drift = ''
$script:InspectCount = 1
$script:Scenario = 'identity'
$script:ExpectedDockerOps = [Collections.Generic.Queue[string]]::new()
$script:ExpectedBoundaryOps = [Collections.Generic.Queue[string]]::new()
$script:BoundaryCalls = [Collections.Generic.List[string]]::new()
$script:CidCalls = 0
$script:RemoveCalls = 0
$script:BoundedCalls = 0
$script:CommandCalls = 0
$script:DbScopeCalls = 0
$script:AclCalls = 0

function Add-ExpectedDockerOps([string[]]$Operations) {
    $script:ExpectedDockerOps.Clear()
    foreach ($operation in $Operations) { $script:ExpectedDockerOps.Enqueue($operation) }
}

function Add-ExpectedBoundaryOps([string[]]$Operations) {
    $script:ExpectedBoundaryOps.Clear()
    foreach ($operation in $Operations) { $script:ExpectedBoundaryOps.Enqueue($operation) }
}

function Assert-BoundaryOp([string]$Operation) {
    if ($script:ExpectedBoundaryOps.Count -eq 0 -or
        $script:ExpectedBoundaryOps.Dequeue() -cne $Operation) {
        throw 'OFFLINE_BOUNDARY_ORDER_REJECTED'
    }
    $script:BoundaryCalls.Add($Operation)
}

function Assert-FakeDockerOp([string]$Operation) {
    if ($script:ExpectedDockerOps.Count -eq 0 -or
        $script:ExpectedDockerOps.Dequeue() -cne $Operation) {
        throw 'OFFLINE_UNEXPECTED_DOCKER_CALL'
    }
}

function New-FakeInspect([string]$Drift = '') {
    $labels = [ordered]@{ $script:verifierLabel = $script:verifierEvidence }
    $inspect = [ordered]@{
        Id = $script:FakeId
        Name = "/$script:verifierName"
        Image = $script:FakeImage
        Config = [ordered]@{
            Labels = $labels
            User = '10001:10001'
            Entrypoint = @('/usr/local/bin/python')
            Cmd = @('-I','-S','-c',$script:ExpectedCode)
        }
        HostConfig = [ordered]@{
            SecurityOpt = @('no-new-privileges')
            CapDrop = @('ALL')
            CapAdd = $null
            NetworkMode = 'none'
            ReadonlyRootfs = $true
            LogConfig = [ordered]@{ Type='none' }
            Memory = 134217728
            MemorySwap = 134217728
            NanoCpus = 250000000
            PidsLimit = 16
            Privileged = $false
            AutoRemove = $false
            RestartPolicy = [ordered]@{ Name='no' }
            Tmpfs = [ordered]@{
                '/tmp'='rw,nosuid,nodev,noexec,size=16m,uid=10001,gid=10001,mode=1777'
            }
        }
        Mounts = @([ordered]@{
            Type='volume'; Name=$script:stateVolumeName; Destination='/state'; RW=$false
        })
    }
    switch -CaseSensitive ($Drift) {
        'id' { $inspect['Id'] = $script:FakeOtherId }
        'name' { $inspect['Name'] = '/wrong' }
        'image' { $inspect['Image'] = 'sha256:' + ('e' * 64) }
        'label' { $inspect['Config']['Labels'][$script:verifierLabel] = 'f' * 32 }
        'user' { $inspect['Config']['User'] = '0:0' }
        'network' { $inspect['HostConfig']['NetworkMode'] = 'bridge' }
        'root' { $inspect['HostConfig']['ReadonlyRootfs'] = $false }
        'log' { $inspect['HostConfig']['LogConfig']['Type'] = 'json-file' }
        'memory' { $inspect['HostConfig']['Memory'] = 1 }
        'memory-swap' { $inspect['HostConfig']['MemorySwap'] = 1 }
        'cpu' { $inspect['HostConfig']['NanoCpus'] = 1 }
        'pids' { $inspect['HostConfig']['PidsLimit'] = 1 }
        'capdrop' { $inspect['HostConfig']['CapDrop'] = @('NET_RAW') }
        'capadd' { $inspect['HostConfig']['CapAdd'] = @('CHOWN') }
        'privileged' { $inspect['HostConfig']['Privileged'] = $true }
        'autoremove' { $inspect['HostConfig']['AutoRemove'] = $true }
        'restart' { $inspect['HostConfig']['RestartPolicy']['Name'] = 'always' }
        'security' { $inspect['HostConfig']['SecurityOpt'] = @() }
        'entrypoint' { $inspect['Config']['Entrypoint'] = @('/bin/sh') }
        'entrypoint-count' {
            $inspect['Config']['Entrypoint'] = @($inspect['Config']['Entrypoint']) + '/bin/false'
        }
        'argv-prefix' { $inspect['Config']['Cmd'][0] = '-B' }
        'argv-s' { $inspect['Config']['Cmd'][1] = '-B' }
        'argv-c' { $inspect['Config']['Cmd'][2] = '-m' }
        'argv-count' { $inspect['Config']['Cmd'] = @($inspect['Config']['Cmd']) + 'extra' }
        'argv-code' { $inspect['Config']['Cmd'][3] = 'wrong' }
        'mount-type' { $inspect['Mounts'][0]['Type'] = 'bind' }
        'mount-name' { $inspect['Mounts'][0]['Name'] = 'wrong' }
        'mount-destination' { $inspect['Mounts'][0]['Destination'] = '/wrong' }
        'mount-write' { $inspect['Mounts'][0]['RW'] = $true }
        'mount-count' {
            $inspect['Mounts'] = @($inspect['Mounts']) +
                [ordered]@{Type='volume';Name='extra';Destination='/extra';RW=$false}
        }
        'tmpfs' { $inspect['HostConfig']['Tmpfs']['/tmp'] = 'rw' }
        '' { }
        default { throw 'OFFLINE_UNKNOWN_DRIFT' }
    }
    return $inspect
}

function Invoke-Docker([string[]]$Arguments) {
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 1 -or
        !$PSBoundParameters.ContainsKey('Arguments')) { throw 'OFFLINE_DOCKER_BINDING_REJECTED' }
    if ($Arguments.Count -lt 1) { throw 'OFFLINE_EMPTY_DOCKER_CALL' }
    $operation = $Arguments[0]
    if ($operation -ceq 'ps') {
        if ($Arguments.Count -ne 4 -or $Arguments[1] -cne '-aq' -or $Arguments[2] -cne '--filter') {
            throw 'OFFLINE_PS_ARGUMENT_REJECTED'
        }
        $filterIndex = [Array]::IndexOf($Arguments,'--filter')
        if ($filterIndex -lt 0 -or $filterIndex + 1 -ge $Arguments.Count) {
            throw 'OFFLINE_PS_FILTER_REJECTED'
        }
        $filter = $Arguments[$filterIndex + 1]
        if ($filter -ceq "name=^/$script:verifierName$") { $operation = 'ps-name' }
        elseif ($filter -ceq "label=$script:verifierLabel") { $operation = 'ps-label-any' }
        elseif ($filter -ceq "label=$script:verifierLabel=$script:verifierEvidence") {
            $operation = 'ps-label-evidence'
        }
        elseif ($filter -ceq "id=$script:FakeId") { $operation = 'ps-id' }
        else { throw 'OFFLINE_PS_FILTER_REJECTED' }
    }
    Assert-FakeDockerOp $operation
    Assert-BoundaryOp "docker:$operation"
    switch -CaseSensitive ($operation) {
        'inspect' {
            if ($Arguments.Count -ne 2 -or $Arguments[1] -cne $script:FakeId) {
                throw 'OFFLINE_INSPECT_ARGUMENT_REJECTED'
            }
            if ($script:InspectCount -eq 0) { return '[]' }
            $object = New-FakeInspect $script:Drift
            if ($script:InspectCount -eq 1) {
                return ($object | ConvertTo-Json -Depth 12 -Compress)
            }
            if ($script:InspectCount -eq 2) {
                return (@($object,$object) | ConvertTo-Json -Depth 12 -Compress)
            }
            throw 'OFFLINE_INSPECT_COUNT_FIXTURE_REJECTED'
        }
        'create' {
            $prefix = @(
                'create','--cidfile',$script:verifierCidPath,'--name',$script:verifierName,
                '--label',"$script:verifierLabel=$script:verifierEvidence",
                '--network','none','--read-only','--log-driver','none','--user','10001:10001',
                '--cap-drop','ALL','--security-opt','no-new-privileges','--memory','128m',
                '--memory-swap','128m','--cpus','0.25','--pids-limit','16','--tmpfs',
                '/tmp:rw,nosuid,nodev,noexec,size=16m,uid=10001,gid=10001,mode=1777',
                '--mount',"type=volume,source=$script:stateVolumeName,target=/state,readonly",
                '--entrypoint','/usr/local/bin/python',$script:FakeImage,'-I','-S','-c')
            if ($Arguments.Count -ne ($prefix.Count + 1)) { throw 'OFFLINE_CREATE_ARGUMENT_REJECTED' }
            for ($index=0; $index -lt $prefix.Count; $index++) {
                if ($Arguments[$index] -cne $prefix[$index]) { throw 'OFFLINE_CREATE_ARGUMENT_REJECTED' }
            }
            if ($Arguments[-1].Length -le 0) { throw 'OFFLINE_CREATE_CODE_REJECTED' }
            $script:ExpectedCode = $Arguments[-1]
            return $script:FakeId
        }
        'rm' {
            $expected = if ($script:Scenario -ceq 'config-fail') {
                @('rm','-f',$script:FakeId)
            } else { @('rm',$script:FakeId) }
            if ($Arguments.Count -ne $expected.Count) { throw 'OFFLINE_RM_ID_REJECTED' }
            for ($index=0; $index -lt $expected.Count; $index++) {
                if ($Arguments[$index] -cne $expected[$index]) { throw 'OFFLINE_RM_ID_REJECTED' }
            }
            return $script:FakeId
        }
        'ps-name' { return @() }
        'ps-label-any' { return @() }
        'ps-label-evidence' { return @() }
        'ps-id' { return @() }
        default { throw 'OFFLINE_DOCKER_OPERATION_REJECTED' }
    }
}

function Assert-ExactPrivateAcl([string]$Path) {
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 1 -or
        !$PSBoundParameters.ContainsKey('Path') -or $Path -cne $script:private) {
        throw 'OFFLINE_ACL_PATH_REJECTED'
    }
    $script:AclCalls++
    Assert-BoundaryOp 'private-acl'
}

function Assert-DbOnlyScope {
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 0) {
        throw 'OFFLINE_DB_SCOPE_ARGUMENT_REJECTED'
    }
    $script:DbScopeCalls++
    Assert-BoundaryOp 'db-scope'
}

function Assert-ExactCidFile {
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 0) {
        throw 'OFFLINE_CID_ARGUMENT_REJECTED'
    }
    $script:CidCalls++
    Assert-BoundaryOp 'cid'
    if ($script:Scenario -ceq 'invalid-cid') { throw 'DBPRE_CID_FORMAT_REJECTED' }
    return $script:FakeId
}

function Get-Command {
    [CmdletBinding()]
    param([Parameter(Position=0)][string]$Name,[string]$CommandType)
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 3 -or
        !$PSBoundParameters.ContainsKey('Name') -or
        !$PSBoundParameters.ContainsKey('CommandType') -or
        $Name -cne 'docker.exe' -or $CommandType -cne 'Application' -or
        !$PSBoundParameters.ContainsKey('ErrorAction') -or
        [string]$PSBoundParameters['ErrorAction'] -cne 'Stop') {
        throw 'OFFLINE_COMMAND_REJECTED'
    }
    $script:CommandCalls++
    Assert-BoundaryOp 'get-command'
    return [pscustomobject]@{ Source='X:\offline\docker.exe' }
}

function Invoke-BoundedProcess(
    [string]$File,[string[]]$Arguments,[string]$Payload,[int]$TimeoutMs) {
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 4 -or
        !$PSBoundParameters.ContainsKey('File') -or
        !$PSBoundParameters.ContainsKey('Arguments') -or
        !$PSBoundParameters.ContainsKey('Payload') -or
        !$PSBoundParameters.ContainsKey('TimeoutMs') -or
        $File -cne 'X:\offline\docker.exe' -or $Arguments.Count -ne 4 -or
        $Arguments[0] -cne 'start' -or $Arguments[1] -cne '-a' -or
        $Arguments[2] -cne '-i' -or $Arguments[3] -cne $script:FakeId -or
        $Payload -cne $script:ExpectedDescriptor -or $TimeoutMs -ne 15000) {
        throw 'OFFLINE_BOUNDED_ARGUMENT_REJECTED'
    }
    $script:BoundedCalls++
    Assert-BoundaryOp 'bounded-process'
    if ($script:Scenario -ceq 'post-start-ambiguity') { throw 'DBPRE_PROCESS_TIMEOUT' }
    if ($script:Scenario -ceq 'verifier-fail') {
        return [ordered]@{ExitCode=1;Stdout="RB1SRC_FAIL`n";Stderr=''}
    }
    return [ordered]@{ExitCode=0;Stdout="RB1SRC_OK`n";Stderr=''}
}

function Test-Path([string]$LiteralPath) {
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 1 -or
        !$PSBoundParameters.ContainsKey('LiteralPath') -or
        $LiteralPath -cne $script:verifierCidPath) { throw 'OFFLINE_TEST_PATH_REJECTED' }
    Assert-BoundaryOp 'test-path'
    return $false
}

function Remove-Item {
    [CmdletBinding()]
    param([string]$LiteralPath,[switch]$Force)
    if ($args.Count -ne 0 -or $PSBoundParameters.Count -ne 2 -or
        !$PSBoundParameters.ContainsKey('LiteralPath') -or
        !$PSBoundParameters.ContainsKey('Force') -or
        $LiteralPath -cne $script:verifierCidPath -or !$Force) {
        throw 'OFFLINE_REMOVE_PATH_REJECTED'
    }
    $script:RemoveCalls++
    Assert-BoundaryOp 'remove-intent'
}

foreach ($name in $requiredFunctions) {
    . ([ScriptBlock]::Create($functionText[$name]))
}

function Reset-Fixture([string]$Scenario,[string[]]$DockerOps,[string[]]$BoundaryOps) {
    $script:Scenario = $Scenario
    $script:Drift = ''
    $script:InspectCount = 1
    $script:ExpectedCode = 'print("offline")'
    $script:BoundaryCalls.Clear()
    $script:CidCalls = 0
    $script:RemoveCalls = 0
    $script:BoundedCalls = 0
    $script:CommandCalls = 0
    $script:DbScopeCalls = 0
    $script:AclCalls = 0
    Add-ExpectedDockerOps $DockerOps
    Add-ExpectedBoundaryOps $BoundaryOps
}

function Assert-QueueEmpty {
    if ($script:ExpectedDockerOps.Count -ne 0 -or $script:ExpectedBoundaryOps.Count -ne 0) {
        throw 'OFFLINE_EXPECTED_BOUNDARY_CALL_MISSING'
    }
}

function Assert-Throws([scriptblock]$Action,[string]$ExpectedMessage) {
    $caught = $null
    try { & $Action } catch { $caught = $_.Exception.Message }
    if ($caught -cne $ExpectedMessage) { throw 'OFFLINE_EXCEPTION_REJECTED' }
}

$caseCount = 0
$identityBoundary = @('docker:inspect')
$successBoundary = @(
    'test-path','private-acl','db-scope','docker:ps-name','docker:ps-label-any','docker:create',
    'cid','docker:inspect','get-command','bounded-process','docker:inspect','docker:rm',
    'docker:ps-id','docker:ps-name','docker:ps-label-evidence','cid','remove-intent')
$configFailBoundary = @(
    'test-path','private-acl','db-scope','docker:ps-name','docker:ps-label-any','docker:create',
    'cid','docker:inspect','cid','docker:inspect','docker:rm','docker:ps-id','docker:ps-name',
    'docker:ps-label-evidence','cid','remove-intent')
$invalidCidBoundary = @(
    'test-path','private-acl','db-scope','docker:ps-name','docker:ps-label-any','docker:create','cid')
$unknownBoundary = @(
    'test-path','private-acl','db-scope','docker:ps-name','docker:ps-label-any','docker:create',
    'cid','docker:inspect','get-command','bounded-process')
$verifierFailBoundary = @($successBoundary + 'test-path')
$script:FailureCode = 'OFFLINE_FAILED_IDENTITY'
$script:FailureCase = 'identity-baseline'
Reset-Fixture 'identity' @('inspect') $identityBoundary
Test-ExactVerifierIdentity $script:FakeId $script:verifierName $script:verifierEvidence `
    $script:FakeImage $script:ExpectedCode
Assert-QueueEmpty
$caseCount++

$fullDrifts = @(
    'id','name','image','label','user','network','root','log','memory','memory-swap','cpu','pids',
    'capdrop','capadd','privileged','autoremove','restart','security','entrypoint','entrypoint-count',
    'argv-prefix','argv-s','argv-c','argv-code','argv-count','mount-type','mount-name',
    'mount-destination','mount-write','mount-count'
)
foreach ($drift in $fullDrifts) {
    $script:FailureCase = "identity-drift-$drift"
    Reset-Fixture 'identity' @('inspect') $identityBoundary
    $script:Drift = $drift
    Assert-Throws {
        Test-ExactVerifierIdentity $script:FakeId $script:verifierName `
            $script:verifierEvidence $script:FakeImage $script:ExpectedCode
    } 'DBPRE_VERIFIER_IDENTITY_REJECTED'
    Assert-QueueEmpty
    $caseCount++
}
$script:FailureCase = 'identity-tmpfs'
Reset-Fixture 'identity' @('inspect') $identityBoundary
$script:Drift = 'tmpfs'
Assert-Throws {
    Test-ExactVerifierIdentity $script:FakeId $script:verifierName `
        $script:verifierEvidence $script:FakeImage $script:ExpectedCode
} 'DBPRE_VERIFIER_TMPFS_REJECTED'
Assert-QueueEmpty
$caseCount++
foreach ($count in @(0,2)) {
    $script:FailureCase = "identity-inspect-count-$count"
    Reset-Fixture 'identity' @('inspect') $identityBoundary
    $script:InspectCount = $count
    Assert-Throws {
        Test-ExactVerifierIdentity $script:FakeId $script:verifierName `
            $script:verifierEvidence $script:FakeImage $script:ExpectedCode
    } 'DBPRE_VERIFIER_INSPECT_REJECTED'
    Assert-QueueEmpty
    $caseCount++
}

$script:FailureCode = 'OFFLINE_FAILED_CLEANUP_IDENTITY'
$script:FailureCase = 'cleanup-identity'
Reset-Fixture 'cleanup-identity' @('inspect') $identityBoundary
$script:Drift = 'user'
Test-ExactVerifierCleanupIdentity $script:FakeId $script:verifierName `
    $script:verifierEvidence $script:FakeImage
Assert-QueueEmpty
$caseCount++

foreach ($drift in @('id','name','label','image')) {
    Reset-Fixture 'cleanup-identity' @('inspect') $identityBoundary
    $script:Drift = $drift
    Assert-Throws {
        Test-ExactVerifierCleanupIdentity $script:FakeId $script:verifierName `
            $script:verifierEvidence $script:FakeImage
    } 'DBPRE_VERIFIER_CLEANUP_IDENTITY_REJECTED'
    Assert-QueueEmpty
    $caseCount++
}
Reset-Fixture 'cleanup-identity' @('inspect') $identityBoundary
$script:InspectCount = 0
Assert-Throws {
    Test-ExactVerifierCleanupIdentity $script:FakeId $script:verifierName `
        $script:verifierEvidence $script:FakeImage
} 'DBPRE_VERIFIER_CLEANUP_IDENTITY_REJECTED'
Assert-QueueEmpty
$caseCount++
Reset-Fixture 'cleanup-identity' @('inspect') $identityBoundary
$script:InspectCount = 2
Assert-Throws {
    Test-ExactVerifierCleanupIdentity $script:FakeId $script:verifierName `
        $script:verifierEvidence $script:FakeImage
} 'DBPRE_VERIFIER_CLEANUP_IDENTITY_REJECTED'
Assert-QueueEmpty
$caseCount++

$descriptor = $script:ExpectedDescriptor
$script:FailureCode = 'OFFLINE_FAILED_STATE'
$script:FailureCase = 'state'

Reset-Fixture 'success' @(
    'ps-name','ps-label-any','create','inspect','inspect','rm','ps-id','ps-name','ps-label-evidence') `
    $successBoundary
[void](Invoke-MediaVerifier $descriptor $script:FakeImage)
if ($script:CidCalls -ne 2 -or $script:RemoveCalls -ne 1 -or
    $script:BoundedCalls -ne 1 -or $script:CommandCalls -ne 1 -or
    $script:DbScopeCalls -ne 1 -or $script:AclCalls -ne 1) {
    throw 'OFFLINE_SUCCESS_BOUNDARY_REJECTED'
}
Assert-QueueEmpty
$caseCount++

Reset-Fixture 'config-fail' @(
    'ps-name','ps-label-any','create','inspect','inspect','rm','ps-id','ps-name','ps-label-evidence') `
    $configFailBoundary
$script:Drift = 'user'
Assert-Throws { [void](Invoke-MediaVerifier $descriptor $script:FakeImage) } `
    'DBPRE_VERIFIER_IDENTITY_REJECTED'
if ($script:CidCalls -ne 3 -or $script:RemoveCalls -ne 1 -or
    $script:BoundedCalls -ne 0 -or $script:CommandCalls -ne 0) {
    throw 'OFFLINE_CONFIG_FAIL_BOUNDARY_REJECTED'
}
Assert-QueueEmpty
$caseCount++

Reset-Fixture 'invalid-cid' @('ps-name','ps-label-any','create') $invalidCidBoundary
Assert-Throws { [void](Invoke-MediaVerifier $descriptor $script:FakeImage) } `
    'DBPRE_VERIFIER_CLEANUP_REQUIRED'
if ($script:CidCalls -ne 1 -or $script:RemoveCalls -ne 0 -or
    $script:BoundedCalls -ne 0 -or $script:CommandCalls -ne 0) {
    throw 'OFFLINE_INVALID_CID_BOUNDARY_REJECTED'
}
Assert-QueueEmpty
$caseCount++

Reset-Fixture 'post-start-ambiguity' @('ps-name','ps-label-any','create','inspect') $unknownBoundary
Assert-Throws { [void](Invoke-MediaVerifier $descriptor $script:FakeImage) } `
    'DBPRE_MEDIA_SOURCE_UNKNOWN_ISOLATED'
if ($script:CidCalls -ne 1 -or $script:RemoveCalls -ne 0 -or
    $script:BoundedCalls -ne 1 -or $script:CommandCalls -ne 1) {
    throw 'OFFLINE_UNKNOWN_BOUNDARY_REJECTED'
}
Assert-QueueEmpty
$caseCount++

Reset-Fixture 'verifier-fail' @(
    'ps-name','ps-label-any','create','inspect','inspect','rm','ps-id','ps-name','ps-label-evidence') `
    $verifierFailBoundary
Assert-Throws { [void](Invoke-MediaVerifier $descriptor $script:FakeImage) } `
    'DBPRE_VERIFIER_RESULT_REJECTED'
if ($script:CidCalls -ne 2 -or $script:RemoveCalls -ne 1 -or
    $script:BoundedCalls -ne 1 -or $script:CommandCalls -ne 1) {
    throw 'OFFLINE_VERIFIER_FAIL_BOUNDARY_REJECTED'
}
Assert-QueueEmpty
$caseCount++

$script:FailureCode = 'OFFLINE_FAILED_PRECHECK'
$script:FailureCase = 'precheck'
$dbScopeFunctions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'Assert-DbOnlyScope'
},$true))
if ($dbScopeFunctions.Count -ne 1) { throw 'OFFLINE_DB_SCOPE_FUNCTION_REJECTED' }
$scopedPsNoTrunc = @($dbScopeFunctions[0].FindAll({
    param($node)
    if ($node -isnot [Management.Automation.Language.CommandAst] -or
        $node.GetCommandName() -cne 'Invoke-Docker') { return $false }
    $values = @($node.FindAll({
        param($child)
        $child -is [Management.Automation.Language.StringConstantExpressionAst]
    },$true) | ForEach-Object { $_.Value })
    return (($values | Where-Object { $_ -ceq 'ps' }).Count -eq 1 -and
        ($values | Where-Object { $_ -ceq '-aq' }).Count -eq 1 -and
        ($values | Where-Object { $_ -ceq '--no-trunc' }).Count -eq 1 -and
        ($values | Where-Object { $_ -ceq '--filter' }).Count -eq 1 -and
        $node.Extent.Text.Contains('"label=com.docker.compose.project=$project"'))
},$true))
$emptyNameResidual = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left.Extent.Text -ceq '$nameResidual' -and $node.Right.Extent.Text -ceq '@()'
},$true))
if ($scopedPsNoTrunc.Count -ne 1 -or $emptyNameResidual.Count -ne 1) {
    throw 'OFFLINE_STATIC_GUARD_REJECTED'
}
$caseCount += 2

$watch.Stop()
$result = [ordered]@{
    contract=$script:Contract
    status='PASS'
    cases=$caseCount
    astErrors=0
    externalProcesses=0
    dockerCalls=0
    dbReads=0
    mediaReads=0
    writes=0
    elapsedMs=[int][Math]::Ceiling($watch.Elapsed.TotalMilliseconds)
}
$json = $result | ConvertTo-Json -Compress
if ([Text.Encoding]::UTF8.GetByteCount($json) -gt 512) {
    $script:FailureCode = 'OFFLINE_FAILED_OUTPUT'
    throw 'OFFLINE_OUTPUT_CAP_REJECTED'
}
$json
