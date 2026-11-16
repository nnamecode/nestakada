[CmdletBinding()]
param([ValidateSet('Check','Status','Load')][string]$Action='Status')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$foundation=Join-Path $repo 'work/foundation/dev'
$manifestPath=Join-Path $foundation 'manifest.json'
$private=Join-Path $foundation 'private'
$project='nestakada-foundation-dev'
$expectedSource=[IO.Path]::GetFullPath((Join-Path $repo 'app'))
$logo=[IO.Path]::GetFullPath((Join-Path $repo 'media/source-site/assets/1c7de03c1bd80ebbde8258aca12b3d4ac68bf699085fd8a7923c4b880f41af8a.png'))
$routeMap=[IO.Path]::GetFullPath((Join-Path $repo 'docs/analytics-route-map.csv'))
$approvedRouteSha='c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8'
$receiptPath=Join-Path $foundation 'local-admin-demo-receipt.json'
$utf8=New-Object Text.UTF8Encoding($false)

function Reject-Link([string]$Path){
    $item=Get-Item -Force -LiteralPath $Path
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw "Reparse point rejected: $Path"}
    return $item
}
function Docker([string[]]$Arguments){
    $value=& docker.exe @Arguments
    if($LASTEXITCODE -ne 0){throw "Docker operation failed ($($Arguments[0])); no automatic retry."}
    return $value
}
function Assert-Identity($Values){
    $parsed=[guid]::Empty
    if($Values.environment -cne 'dev' -or $Values.project -cne $project -or
       $Values.source -cne $expectedSource -or
       ![guid]::TryParseExact([string]$Values.runId,'D',[ref]$parsed) -or $parsed.ToString() -cne $Values.runId -or
       $Values.sourceSha -cne $Values.expectedSourceSha -or $Values.sourceSha -cnotmatch '^[a-f0-9]{64}$' -or
       $Values.image -cne $Values.expectedImage -or $Values.image -cnotmatch '^sha256:[a-f0-9]{64}$' -or
       $Values.network -cne "$project-db" -or $Values.volume -cne "$project-state" -or
       $Values.routeSha -cne $approvedRouteSha){throw 'Local demo identity admission rejected.'}
}
function Read-Admission{
    if(!(Test-Path -LiteralPath $manifestPath)){throw 'Fresh active dev foundation required.'}
    Reject-Link $manifestPath|Out-Null
    $m=Get-Content -Raw -LiteralPath $manifestPath|ConvertFrom-Json
    if(!$m.active -or $m.environment -cne 'dev' -or $m.composeProject -cne $project -or
       [IO.Path]::GetFullPath([string]$m.sourceDirectory) -cne $expectedSource){throw 'Dev foundation identity mismatch.'}
    if((Get-FileHash -LiteralPath $m.sourceManifest -Algorithm SHA256).Hash.ToLowerInvariant() -cne $m.sourceSha256){throw 'Dev source manifest drift.'}
    $rows=@(Get-Content -Raw -LiteralPath $m.sourceManifest|ConvertFrom-Json)
    $required=@('content/local_admin_demo.py','shared_content/policy.py','shared_content/public.py')
    foreach($name in $required){if($name -cnotin @($rows.path)){throw "Fresh dev source omits $name"}}
    $packageRelative=@(
        'content/dev09b_articles_slice.json','content/dev09e_services_catalog.json',
        'content/dev09g_service_roots.json','content/dev09h_service_details.json',
        'content/dev09i_planned_maintenance.json','content/dev09j_leading_price_details.json',
        'content/dev09k_diagnostics_branch.json','content/dev09m_combined_services.json',
        'content/dev09m_infographic_map019.json','content/dev09n_remaining_content.json',
        'content/dev10_gallery.json','content/dev12_home_profile.json')
    $runtimeExtensions=@('.py','.lock','.html','.css','.js','.mjs','.svg')
    $liveRelative=@(Get-ChildItem -Force -File -Recurse -LiteralPath $expectedSource|ForEach-Object{
        $relative=$_.FullName.Substring($expectedSource.Length+1).Replace('\','/')
        if($_.Extension -in $runtimeExtensions -or $relative -cin $packageRelative){$relative}
    }|Sort-Object)
    $manifestRelative=@($rows.path|Sort-Object)
    if($liveRelative.Count -ne $manifestRelative.Count -or
       (Compare-Object -CaseSensitive $manifestRelative $liveRelative)){throw 'Dev live source inventory differs from manifest.'}
    foreach($row in $rows){
        $path=[IO.Path]::GetFullPath((Join-Path $expectedSource $row.path))
        if(!$path.StartsWith($expectedSource+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Dev source path escaped.'}
        $item=Reject-Link $path
        if($item.PSIsContainer -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $row.sha256){throw 'Dev source bytes drifted.'}
    }
    foreach($path in @($repo,$expectedSource,$private,$logo,$routeMap)){Reject-Link $path|Out-Null}
    $logoItem=Get-Item -Force -LiteralPath $logo
    if($logoItem.PSIsContainer -or $logoItem.Length -ne 30190 -or
       (Get-FileHash -LiteralPath $logo -Algorithm SHA256).Hash.ToLowerInvariant() -cne '39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5'){
        throw 'Local demo logo mismatch.'
    }
    $routeHash=(Get-FileHash -LiteralPath $routeMap -Algorithm SHA256).Hash.ToLowerInvariant()
    if($routeHash -cne $approvedRouteSha){throw 'Approved route map hash mismatch.'}
    if(@(Import-Csv -LiteralPath $routeMap).Count -ne 115){throw 'Route map contract mismatch.'}
    $containers=@(Docker @('ps','-q','--filter',"label=com.docker.compose.project=$project"))
    if($containers.Count -ne 4){throw 'Exact active dev foundation containers required.'}
    $appImage=$null
    foreach($name in @("$project-app","$project-db","$project-ingress","$project-media-worker")){
        $item=@(Docker @('inspect',$name)|ConvertFrom-Json)[0]
        if(!$item.State.Running -or $item.Config.Labels.'nestakada.scope' -cne 'foundation-dev'){throw 'Dev container identity mismatch.'}
        if($name -ceq "$project-app"){$appImage=[string]$item.Image}
    }
    $network=@(Docker @('network','inspect',"$project-db")|ConvertFrom-Json)[0]
    if(!$network.Internal -or $network.Labels.'nestakada.scope' -cne 'foundation-dev'){throw 'Private dev DB network required.'}
    $volume=@(Docker @('volume','inspect',"$project-state")|ConvertFrom-Json)[0]
    if($volume.Driver -cne 'local' -or $volume.Labels.'nestakada.scope' -cne 'foundation-dev'){throw 'Exact dev state volume required.'}
    foreach($name in @('runtime-password','django-secret','database-ca')){Reject-Link (Join-Path $private $name)|Out-Null}
    $identity=[pscustomobject]@{environment=[string]$m.environment;project=[string]$m.composeProject
        source=[IO.Path]::GetFullPath([string]$m.sourceDirectory);runId=[string]$m.runId
        sourceSha=[string]$m.sourceSha256;expectedSourceSha=[string]$m.sourceSha256
        image=[string]$m.selectedAppImage;expectedImage=$appImage
        network=[string]$network.Name;volume=[string]$volume.Name;routeSha=$routeHash}
    Assert-Identity $identity
    return [pscustomobject]@{manifest=$m;routeHash=$routeHash;volume=$volume.Name;network=$network.Name;identity=$identity}
}

if($Action -eq 'Status'){
    $admission=Read-Admission
    $homeStatus=$null;$login=$null
    try{$homeStatus=[int](Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri 'http://127.0.0.1:8766/').StatusCode}catch{if($_.Exception.Response){$homeStatus=[int]$_.Exception.Response.StatusCode}}
    try{$login=[int](Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri 'http://127.0.0.1:8766/manage/login/').StatusCode}catch{if($_.Exception.Response){$login=[int]$_.Exception.Response.StatusCode}}
    [pscustomobject]@{environment='dev';active=$true;home=$homeStatus;login=$login;runId=$admission.manifest.runId;receipt=(Test-Path -LiteralPath $receiptPath)}|ConvertTo-Json
    return
}

$admission=Read-Admission
if($Action -eq 'Check'){
    foreach($case in @(
        @('environment','test'),@('project','foreign-project'),@('source','C:\foreign'),
        @('runId','NOT-A-UUID'),@('sourceSha',('0'*64)),@('image','sha256:'+('0'*64)),
        @('network','foreign-db'),@('volume','foreign-state'),@('routeSha',('0'*64)))){
        $candidate=($admission.identity|ConvertTo-Json|ConvertFrom-Json)
        $candidate.($case[0])=$case[1]
        $accepted=$true
        try{Assert-Identity $candidate}catch{$accepted=$false}
        if($accepted){throw "Local demo negative admission accepted $($case[0])."}
    }
    Write-Output "LOCAL_ADMIN_DEMO_CHECK_PASS foundation=$($admission.manifest.runId)"
    return
}

if(Test-Path -LiteralPath $receiptPath){throw 'Local admin demo receipt already exists; replay refused.'}

$runId=[guid]::NewGuid().ToString()
$sourceHash=[string]$admission.manifest.sourceSha256
$image=[string]$admission.manifest.selectedAppImage
$args=@('run','--rm','--name',"nestakada-local-admin-demo-$runId",'--network',$admission.network,
    '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
    '--memory','1536m','--memory-swap','1536m','--cpus','1','--pids-limit','128',
    '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=128m,uid=10001,gid=10001,mode=1777',
    '--mount',"type=bind,source=$expectedSource,target=/app,readonly",
    '--mount',"type=bind,source=$repo,target=/test08-source,readonly",
    '--mount',"type=bind,source=$routeMap,target=/test08-route-map.csv,readonly",
    '--mount',"type=bind,source=$logo,target=/local-demo-logo.png,readonly",
    '--mount',"type=bind,source=$(Join-Path $private 'runtime-password'),target=/run/secrets/database-password,readonly",
    '--mount',"type=bind,source=$(Join-Path $private 'django-secret'),target=/run/secrets/django-secret,readonly",
    '--mount',"type=bind,source=$(Join-Path $private 'database-ca'),target=/run/secrets/database-ca,readonly",
    '--mount',"type=volume,source=$($admission.volume),target=/var/lib/estakada",
    '--workdir','/app','--env','DJANGO_SETTINGS_MODULE=estakada.settings.local_http',
    '--env','ESTAKADA_LOCAL_ENV=dev','--env','ESTAKADA_DB_NAME=estakada_foundation','--env','ESTAKADA_DB_USER=app_runtime',
    '--env','ESTAKADA_TEST08_SOURCE_ROOT=/test08-source','--env','ESTAKADA_TEST08_ROUTE_MAP=/test08-route-map.csv',
    '--env',"ESTAKADA_TEST08_RUN_ID=$runId",'--env',"ESTAKADA_TEST08_ROUTE_SHA256=$($admission.routeHash)",
    '--env',"ESTAKADA_TEST08_INPUT_MANIFEST_SHA256=$sourceHash",'--env',"ESTAKADA_TEST08_SOURCE_MANIFEST_SHA256=$sourceHash",
    '--env','ESTAKADA_LOCAL_DEMO_APPLY_ENABLED=1','--env','ESTAKADA_LOCAL_DEMO_STATE_ROOT=/var/lib/estakada',
    '--env','ESTAKADA_LOCAL_DEMO_LOGO=/local-demo-logo.png','--env',"ESTAKADA_LOCAL_DEMO_RUN_ID=$runId",
    $image,'python','-B','-m','content.local_admin_demo')
$output=@(& docker.exe @args 2>&1);$exit=$LASTEXITCODE
$output|ForEach-Object{Write-Output $_}
if($exit -ne 0){throw 'Local admin demo load failed; inspect evidence before any retry.'}
$markers=@($output|Where-Object{"$_".StartsWith('LOCAL_ADMIN_DEMO_RESULT=')})
if($markers.Count -ne 1){throw 'Local admin demo result marker missing.'}
$encoded=$markers[0].Substring('LOCAL_ADMIN_DEMO_RESULT='.Length).Replace('-','+').Replace('_','/')
while($encoded.Length%4){$encoded+='='}
$receipt=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))|ConvertFrom-Json
$receiptKeys=@($receipt.PSObject.Properties.Name|Sort-Object)-join ','
if($receiptKeys -cne 'assets,databaseProjectionSha256,files,media,mediaProjectionSha256,owner,pages,profiles,published,requests,routeMapSha256,routes,runId,schema,socialLinks,sourceManifestSha256,users' -or
   $receipt.schema -cne 'local-admin-demo-result-v1' -or $receipt.runId -cne $runId -or
   $receipt.pages -ne 112 -or $receipt.routes -ne 115 -or $receipt.published -ne 112 -or
   $receipt.assets -ne 238 -or $receipt.files -ne 238 -or $receipt.media.count -ne 238 -or
   $receipt.media.bytes -ne 45094933 -or $receipt.requests -ne 0 -or $receipt.owner -cne 'nesadmin' -or
   $receipt.socialLinks -ne 0 -or $receipt.sourceManifestSha256 -cne $sourceHash -or
   $receipt.routeMapSha256 -cne $approvedRouteSha -or
   $receipt.mediaProjectionSha256 -cnotmatch '^[a-f0-9]{64}$' -or
   $receipt.databaseProjectionSha256 -cnotmatch '^[a-f0-9]{64}$'){
    throw 'Local admin demo result marker mismatch.'
}
$durable=[ordered]@{
    assets=238;databaseProjectionSha256=[string]$receipt.databaseProjectionSha256;files=238
    media=[ordered]@{bytes=45094933;count=238};mediaProjectionSha256=[string]$receipt.mediaProjectionSha256
    owner='nesadmin';pages=112;profiles=2;published=112;requests=0
    routeMapSha256=$approvedRouteSha;routes=115;runId=$runId;schema='local-admin-demo-result-v1'
    socialLinks=0;sourceManifestSha256=$sourceHash;users=2
}
$receiptTemp=Join-Path $foundation "local-admin-demo-receipt.$runId.tmp"
if(Test-Path -LiteralPath $receiptTemp){throw 'Local admin demo receipt temp already exists.'}
[IO.File]::WriteAllText($receiptTemp,($durable|ConvertTo-Json -Depth 4 -Compress),$utf8)
[IO.File]::Move($receiptTemp,$receiptPath)
Write-Output "LOCAL_ADMIN_DEMO_LOAD_PASS run=$runId"
