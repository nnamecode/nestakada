[CmdletBinding()]
param(
    [ValidateSet('dev','test')][string]$Environment = 'test',
    [ValidateSet('Start','Stop','Status','UnitTests')][string]$Action = 'Status'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$scope = "foundation-$Environment"
$project = "nestakada-$scope"
$port = if ($Environment -eq 'dev') { 8766 } else { 8767 }
$work = Join-Path $repo "work/foundation/$Environment"
$private = Join-Path $work 'private'
$manifestPath = Join-Path $work 'manifest.json'
$envFile = Join-Path $work 'compose.env'
$composeFile = Join-Path $repo 'environment/foundation/compose.yaml'
$utf8 = New-Object Text.UTF8Encoding($false)
function Write-Utf8([string]$Path, [string]$Value) { [IO.File]::WriteAllText($Path, $Value, $utf8) }
function Docker {
    param([string[]]$Arguments)
    $result = & docker.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker operation failed ($($Arguments[0])); no automatic retry." }
    return $result
}
function Compose {
    param([string[]]$Arguments)
    Docker (@('compose','--env-file',$envFile,'--project-name',$project,'--file',$composeFile) + $Arguments)
}
function Read-Manifest {
    if (!(Test-Path -LiteralPath $manifestPath)) { throw 'No foundation manifest; Start first.' }
    $m = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($m.environment -ne $Environment -or $m.composeProject -ne $project -or $m.privateDirectory -ne $private) { throw 'Manifest scope mismatch.' }
    return $m
}
function Save-Manifest($Manifest) { Write-Utf8 $manifestPath ($Manifest | ConvertTo-Json -Depth 8) }
function Reject-Link([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point rejected: $Path" }
}
function Check-OwnedResources {
    $ids = @(Docker @('ps','-aq','--filter',"label=com.docker.compose.project=$project"))
    foreach ($id in $ids) {
        $v = (Docker @('inspect',$id) | ConvertFrom-Json)[0]
        if ($v.Config.Labels.'nestakada.scope' -ne $scope) { throw 'Foreign container in foundation project.' }
    }
    foreach ($kind in @('network','volume')) {
        $names = if ($kind -eq 'network') { @('ingress','web','db') } else { @('dbdata','state','media-exchange') }
        $all = @(Docker @($kind,'ls','--format','{{.Name}}'))
        foreach ($suffix in $names) {
            $name = "$project-$suffix"
            if ($all -contains $name) {
                $v = (Docker @($kind,'inspect',$name) | ConvertFrom-Json)[0]
                if ($v.Labels.'nestakada.scope' -ne $scope) { throw "Foreign $kind name collision." }
                if ($kind -eq 'volume' -and $suffix -eq 'media-exchange' -and
                    ($v.Driver -ne 'local' -or $v.Options.type -ne 'tmpfs' -or $v.Options.device -ne 'tmpfs' -or
                     $v.Options.o -ne 'size=128m,uid=10001,gid=10001,mode=0770')) { throw 'Media exchange quota/options mismatch.' }
            }
        }
    }
    return $ids
}
function Check-Locks {
    $lockPath = Join-Path $repo 'environment/foundation/runtime-images.lock.json'
    $lock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json
    if ($lock.approvedBy -ne 'D-315' -or $lock.status -ne 'independently-reviewed-local-artifacts') { throw 'Runtime lock is not approved.' }
    $pointers = @($lock.requirements)
    foreach ($image in $lock.images) { $pointers += @($image.recipe,$image.inputs,$image.receipt) }
    foreach ($pointer in $pointers) {
        $path = [IO.Path]::GetFullPath((Join-Path $repo $pointer.path))
        if (!$path.StartsWith($repo + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Lock path outside workspace.' }
        Reject-Link $path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pointer.sha256) { throw "Locked input changed: $($pointer.path)" }
    }
    foreach ($image in $lock.images) {
        if ($image.reference -ne $image.dockerReportedImageId -or $image.reference -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Invalid image lock identity.' }
        $actual = (Docker @('image','inspect',$image.reference) | ConvertFrom-Json)[0]
        if ($actual.Id -ne $image.reference -or $actual.Os -ne 'linux' -or $actual.Architecture -ne 'amd64') { throw 'Local image does not match approved lock.' }
    }
    return $lock
}
function Check-MediaWorker($BaseLock) {
    foreach ($parent in @((Join-Path $repo 'tools'),(Join-Path $repo 'tools/media_worker'),(Join-Path $repo 'environment'),(Join-Path $repo 'environment/media-worker'))) { Reject-Link $parent }
    $receiptPath = Join-Path $repo 'environment/media-worker/candidate-receipt.json'
    Reject-Link $receiptPath
    $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
    $base = @($BaseLock.images | Where-Object component -eq 'python-runtime')[0]
    if ($receipt.status -ne 'independently-reviewed-for-local-integration' -or $receipt.authorizedBy -ne 'D-325' -or
        $receipt.baseDockerReportedImageId -ne $base.reference -or $receipt.dockerReportedImageId -notmatch '^sha256:[a-f0-9]{64}$') {
        throw 'Media worker is not admitted for local integration.'
    }
    foreach ($entry in $receipt.inputs) {
        $path = [IO.Path]::GetFullPath((Join-Path $repo $entry.path))
        if (!$path.StartsWith((Join-Path $repo 'environment/media-worker') + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
            throw 'Worker input escaped its directory.'
        }
        Reject-Link $path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw 'Worker input changed.' }
    }
    $names = @($receipt.workerSource | ForEach-Object name | Sort-Object)
    if (($names -join ',') -ne 'probe.py,test_worker.py,worker.py') { throw 'Unexpected worker source set.' }
    foreach ($entry in $receipt.workerSource) {
        $path = Join-Path $repo ('tools/media_worker/' + $entry.name)
        Reject-Link $path
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw 'Reviewed worker source changed.' }
    }
    $actual = (Docker @('image','inspect',$receipt.dockerReportedImageId) | ConvertFrom-Json)[0]
    if ($actual.Id -ne $receipt.dockerReportedImageId -or $actual.Os -ne 'linux' -or $actual.Architecture -ne 'amd64') { throw 'Worker image mismatch.' }
    return $receipt
}
function Protect-Private {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    # Edit only the DACL. A newly constructed owner/security descriptor can ask
    # Set-Acl for SeSecurityPrivilege on an existing directory during restart.
    $acl = [IO.Directory]::GetAccessControl($private, [Security.AccessControl.AccessControlSections]::Access)
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($rule in @($acl.Access)) { $acl.RemoveAccessRuleSpecific($rule) }
    foreach ($sid in @($identity.User,(New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    [IO.Directory]::SetAccessControl($private, $acl)
}
function Prepare-Secrets([string]$Image) {
    New-Item -ItemType Directory -Force -Path $private | Out-Null
    Reject-Link $private
    Protect-Private
    foreach ($file in Get-ChildItem -LiteralPath $private -File -Force) {
        Reject-Link $file.FullName
        $acl = [IO.File]::GetAccessControl($file.FullName, [Security.AccessControl.AccessControlSections]::Access)
        $acl.SetAccessRuleProtection($false,$true)
        foreach ($rule in @($acl.Access | Where-Object { !$_.IsInherited })) { $acl.RemoveAccessRuleSpecific($rule) }
        [IO.File]::SetAccessControl($file.FullName, $acl)
    }
    foreach ($name in @('bootstrap-password','migrator-password','runtime-password','django-secret','deployment-django-secret')) {
        $path = Join-Path $private $name
        if (!(Test-Path -LiteralPath $path)) {
            $bytes = New-Object byte[] 48
            $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
            try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
            Write-Utf8 $path ([BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant())
        }
        Reject-Link $path
        if ([IO.File]::ReadAllText($path) -notmatch '\A[0-9a-f]{96}\z') { throw "Invalid existing credential file: $name" }
    }
    $cert = Join-Path $private 'database-ca'
    $key = Join-Path $private 'database-server-key'
    if ((Test-Path -LiteralPath $cert) -xor (Test-Path -LiteralPath $key)) { throw 'Incomplete TLS pair; preserved for investigation.' }
    $helper = @('run','--rm','--pull=never','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
        '--memory=128m','--cpus=0.25','--pids-limit=32','--label',"nestakada.scope=$scope",'--mount',"type=bind,source=$private,target=/private",'--entrypoint=openssl',$Image)
    if (!(Test-Path -LiteralPath $cert)) {
        Docker ($helper + @('req','-x509','-newkey','rsa:2048','-sha256','-nodes','-days','30','-subj','/CN=db',
            '-addext','subjectAltName=DNS:db','-keyout','/private/database-server-key','-out','/private/database-ca')) | Out-Null
    }
    Reject-Link $cert
    Reject-Link $key
    Docker ($helper + @('x509','-in','/private/database-ca','-checkend','3600','-noout')) | Out-Null
    # Inherited restrictions also replace any explicit broad ACL on existing files.
    foreach ($file in Get-ChildItem -LiteralPath $private -File -Force) {
        $acl = Get-Acl -LiteralPath $file.FullName
        $acl.SetAccessRuleProtection($false,$true)
        foreach ($rule in @($acl.Access | Where-Object { !$_.IsInherited })) { $acl.RemoveAccessRuleSpecific($rule) }
        Set-Acl -LiteralPath $file.FullName -AclObject $acl
    }
}

if (!(Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue)) { throw 'Approved Docker CLI is not available.' }
foreach ($path in @($repo,(Join-Path $repo 'work'),(Join-Path $repo 'work/foundation'),$work,$private)) {
    if (Test-Path -LiteralPath $path) { Reject-Link $path }
}
foreach ($variable in Get-ChildItem Env:FOUNDATION_*) { throw 'Clear inherited FOUNDATION_* overrides before using this wrapper.' }
if ($Action -eq 'Status') {
    if (!(Test-Path -LiteralPath $manifestPath)) { Write-Output 'Foundation has not been started.'; return }
    $m = Read-Manifest
    Write-Output "Environment=$Environment Active=$($m.active) Run=$($m.runId)"
    Check-OwnedResources | Out-Null
    Compose @('ps','--all')
    return
}
if ($Action -eq 'Stop') {
    $m = Read-Manifest
    Check-OwnedResources | Out-Null
    Compose @('down','--timeout','10')
    $m.active = $false
    Save-Manifest $m
    Write-Output 'Foundation stopped; private files and named volumes retained.'
    return
}
if ($Action -eq 'UnitTests') {
    if ($Environment -ne 'test') { throw 'UnitTests requires the isolated test environment.' }
    $m = Read-Manifest
    if (!$m.active) { throw 'Start test environment before running UnitTests.' }
    Check-OwnedResources | Out-Null
    Compose @('--profile','tools','run','--rm','--no-deps','units')
    return
}

$lock = Check-Locks
$worker = Check-MediaWorker $lock
$existing = @(Check-OwnedResources)
if ($existing.Count) { throw 'Foundation containers already exist; run Stop before a new Start.' }
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "Local port $port is occupied; no process was stopped." }
$runId = [guid]::NewGuid().ToString()
$source = Join-Path $repo 'app'
Reject-Link $source
$items = @(Get-ChildItem -LiteralPath $source -Recurse -Force)
foreach ($item in $items) { Reject-Link $item.FullName }
$files = @($items | Where-Object { !$_.PSIsContainer -and $_.Extension -in @('.py','.lock','.html','.css','.js','.mjs','.svg') } | Sort-Object FullName)
if (!(Test-Path -LiteralPath (Join-Path $source 'manage.py'))) { throw 'Application source is incomplete.' }
New-Item -ItemType Directory -Force -Path $work | Out-Null
Reject-Link $work
if ($Environment -eq 'test') {
    $snapshot = Join-Path $work "sources/$runId"
    New-Item -ItemType Directory -Force -Path $snapshot | Out-Null
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($source.Length + 1)
        $destination = Join-Path $snapshot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination
    }
    $source = $snapshot
}
$sourceFiles = @(Get-ChildItem -LiteralPath $source -Recurse -File | Where-Object { $_.Extension -in @('.py','.lock','.html','.css','.js','.mjs','.svg') } | Sort-Object FullName | ForEach-Object {
    [ordered]@{path=$_.FullName.Substring($source.Length+1).Replace('\','/'); sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
$sourceManifest = Join-Path $work "source-$runId.json"
Write-Utf8 $sourceManifest (ConvertTo-Json -InputObject $sourceFiles -Depth 4)
$workerSource = Join-Path $work "worker-sources/$runId"
if (Test-Path -LiteralPath (Split-Path -Parent $workerSource)) { Reject-Link (Split-Path -Parent $workerSource) }
New-Item -ItemType Directory -Force -Path $workerSource | Out-Null
Reject-Link (Split-Path -Parent $workerSource)
Reject-Link $workerSource
foreach ($entry in $worker.workerSource) {
    $origin = Join-Path $repo ('tools/media_worker/' + $entry.name)
    $destination = Join-Path $workerSource $entry.name
    Copy-Item -LiteralPath $origin -Destination $destination
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw 'Worker snapshot changed during copy.' }
}
$workerManifest = Join-Path $work "worker-source-$runId.json"
Write-Utf8 $workerManifest (ConvertTo-Json -InputObject @($worker.workerSource) -Depth 4)
$images = @{}
foreach ($image in $lock.images) { $images[$image.component] = $image.reference }
Prepare-Secrets $images['python-runtime']
$values = [ordered]@{
    FOUNDATION_PROJECT=$project; FOUNDATION_PREFIX=$project; FOUNDATION_ENV=$Environment; FOUNDATION_PORT=$port
    FOUNDATION_PYTHON_IMAGE=$images['python-runtime']; FOUNDATION_POSTGRES_IMAGE=$images['postgres']; FOUNDATION_INGRESS_IMAGE=$images['local-ingress']
    FOUNDATION_SOURCE=$source; FOUNDATION_PRIVATE=$private
    FOUNDATION_WORKER_IMAGE=$worker.dockerReportedImageId; FOUNDATION_WORKER_SOURCE=$workerSource
    FOUNDATION_DB_START=(Join-Path $repo 'environment/foundation/db-start.sh')
    FOUNDATION_NGINX_CONFIG=(Join-Path $repo 'environment/foundation/local-nginx.conf')
    FOUNDATION_DB_INIT=(Join-Path $repo 'tools/foundation_db_init.py')
}
Write-Utf8 $envFile (($values.GetEnumerator() | ForEach-Object { "$($_.Key)='$(([string]$_.Value).Replace('\','/'))'" }) -join "`n")
$manifest = [ordered]@{runId=$runId; environment=$Environment; active=$false; composeProject=$project
    containers=[ordered]@{app="$project-app";db="$project-db";ingress="$project-ingress";'media-worker'="$project-media-worker"}
    sourceDirectory=$source; sourceManifest=$sourceManifest; sourceSha256=(Get-FileHash -LiteralPath $sourceManifest -Algorithm SHA256).Hash.ToLowerInvariant()
    workerSourceDirectory=$workerSource; workerSourceManifest=$workerManifest
    workerSourceSha256=(Get-FileHash -LiteralPath $workerManifest -Algorithm SHA256).Hash.ToLowerInvariant()
    workerReceiptSha256=(Get-FileHash -LiteralPath (Join-Path $repo 'environment/media-worker/candidate-receipt.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    privateDirectory=$private; dbName='estakada_foundation'; unitDbName='estakada_foundation_unit'; port=$port}
Save-Manifest $manifest
Compose @('config','--quiet')
Compose @('up','-d','--no-build','--pull','never','db')
$ready = $false
for ($attempt=0; $attempt -lt 60; $attempt++) {
    # The official entrypoint starts a temporary socket-only bootstrap server.
    # Wait for final TCP service, not that temporary socket.
    & docker.exe exec "$project-db" pg_isready -h 127.0.0.1 -p 5432 -U postgres -d estakada_foundation *> $null
    if ($LASTEXITCODE -eq 0) { $ready=$true; break }
    Start-Sleep -Milliseconds 500
}
if (!$ready) { throw 'PostgreSQL did not become ready within the bounded startup check.' }
Compose @('--profile','tools','run','--rm','--no-deps','init')
Compose @('--profile','tools','run','--rm','--no-deps','state-init')
Compose @('--profile','tools','run','--rm','--no-deps','migrate')
Compose @('up','-d','--no-build','--pull','never','media-worker')
$workerReady = @'
import socket,time
deadline=time.monotonic()+10
while time.monotonic()<deadline:
    try:
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(1);sock.connect('/exchange/media-worker.sock')
            sock.sendall(b'{}\n')
            assert b'"rejected"' in sock.recv(4096)
        break
    except (OSError,AssertionError):time.sleep(0.1)
else:raise SystemExit('Worker readiness failed')
'@
Docker @('exec',"$project-media-worker",'python','-c',$workerReady)
Compose @('up','-d','--no-build','--pull','never','app','ingress')
$ready = $false
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try {
        $request = [Net.HttpWebRequest]::Create("http://127.0.0.1:$port/")
        $request.Timeout = 1000
        $response = $request.GetResponse(); $response.Close(); $ready=$true
    } catch [Net.WebException] {
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            $_.Exception.Response.Close()
            if ($status -eq 404) { $ready=$true }
        }
    }
    if ($ready) { break }
    Start-Sleep -Milliseconds 500
}
if (!$ready) { throw 'Local ingress did not become ready; resources retained for inspection and Stop.' }
$manifest.active = $true
Save-Manifest $manifest
Write-Output "Foundation $Environment ready at http://127.0.0.1:$port/; run $runId"
