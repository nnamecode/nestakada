#requires -Version 7.0
[CmdletBinding()]
param([ValidateSet('Setup','Cleanup')][string]$Action = 'Setup')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work = Join-Path $repo 'work\r7c-selector-synthetic'
$statePath = Join-Path $work 'fixture-state.json'
$authorityPath = Join-Path $work 'authority.json'
$fixtureRoot = Join-Path $work 'fixture-files'
$utf8 = [Text.UTF8Encoding]::new($false)

function Fail-Fixture([string]$Code) { throw $Code }

function Assert-FixtureDirectory([string]$Path, [bool]$Create = $false) {
    $full=[IO.Path]::GetFullPath($Path)
    if($full -cne [IO.Path]::GetFullPath($work) -and ![string]::Equals([IO.Path]::GetDirectoryName($full),[IO.Path]::GetFullPath($work),[StringComparison]::OrdinalIgnoreCase)){Fail-Fixture 'R7C_SYNTHETIC_DIRECTORY_INVALID'}
    if($Create -and !(Test-Path -LiteralPath $full)){[void](New-Item -ItemType Directory -Path $full)}
    if(!(Test-Path -LiteralPath $full -PathType Container)){Fail-Fixture 'R7C_SYNTHETIC_DIRECTORY_INVALID'}
    $item=Get-Item -Force -LiteralPath $full
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){Fail-Fixture 'R7C_SYNTHETIC_DIRECTORY_INVALID'}
    if((Get-Acl -LiteralPath $full).Owner -cne [Security.Principal.WindowsIdentity]::GetCurrent().Name){Fail-Fixture 'R7C_SYNTHETIC_DIRECTORY_OWNER_INVALID'}
}

function Get-SafeTextFingerprint([string]$Value) {
    $bytes=[Text.Encoding]::UTF8.GetBytes($Value)
    return [pscustomobject]@{bytes=$bytes.Length;sha256=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()}
}

function Invoke-Docker(
    [ValidateSet('IMAGE_INSPECT','VOLUME_PRECHECK','VOLUME_CREATE','VOLUME_VERIFY','NETWORK_PRECHECK','NETWORK_CREATE','NETWORK_VERIFY','SOURCE_COPY','MEDIA_MKDIR','MEDIA_COPY','AUTHORITY_COPY','SECRET_COPY','CERT_CREATE','DB_START','DB_READY','DB_SCHEMA','DB_MIGRATE','DB_SEED','DB_GRANT','DB_READONLY','CLEANUP_CONTAINER_LIST','CLEANUP_CONTAINER_INSPECT','CLEANUP_CONTAINER_STOP','CLEANUP_CONTAINER_REMOVE','CLEANUP_NETWORK_LIST','CLEANUP_NETWORK_INSPECT','CLEANUP_NETWORK_REMOVE','CLEANUP_VOLUME_LIST','CLEANUP_VOLUME_INSPECT','CLEANUP_VOLUME_REMOVE')]
    [string]$Stage,
    [string[]]$Arguments,
    [bool]$AllowFailure = $false
) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = 'docker'; $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true; $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::Start($start)
    $stdoutTask = $process.StandardOutput.ReadToEndAsync(); $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit(); $stdout = $stdoutTask.GetAwaiter().GetResult(); $stderr = $stderrTask.GetAwaiter().GetResult(); $exit = $process.ExitCode; $process.Dispose()
    if ($exit -ne 0 -and !$AllowFailure) {
        $stdoutFingerprint=Get-SafeTextFingerprint $stdout;$stderrFingerprint=Get-SafeTextFingerprint $stderr
        $argumentsFingerprint=Get-SafeTextFingerprint (ConvertTo-Json -InputObject @($Arguments) -Compress)
        Fail-Fixture "R7C_SYNTHETIC_DOCKER_FAILED stage=$Stage exit=$exit argsSha256=$($argumentsFingerprint.sha256) stdoutBytes=$($stdoutFingerprint.bytes) stdoutSha256=$($stdoutFingerprint.sha256) stderrBytes=$($stderrFingerprint.bytes) stderrSha256=$($stderrFingerprint.sha256)"
    }
    return [pscustomobject]@{ExitCode=$exit;Stdout=$stdout;Stderr=$stderr}
}

function Docker-Lines([string]$Stage,[string[]]$Arguments) {
    $text = (Invoke-Docker $Stage $Arguments).Stdout
    if ([string]::IsNullOrWhiteSpace($text)) { return @() }
    return @($text -split "`r?`n" | Where-Object { $_ })
}

function Write-SafeJson([string]$Path, [object]$Value) {
    $temporary = "$Path.tmp-$([guid]::NewGuid().ToString('N'))"
    $stream = [IO.FileStream]::new($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $bytes=$utf8.GetBytes(($Value | ConvertTo-Json -Depth 12 -Compress)+"`n");$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true) } finally { $stream.Dispose() }
    [IO.File]::Move($temporary,$Path)
}

function Assert-Image([string]$Id) {
    $rows = @((Invoke-Docker 'IMAGE_INSPECT' @('image','inspect',$Id)).Stdout | ConvertFrom-Json)
    if ($rows.Count -ne 1 -or [string]$rows[0].Id -cne $Id) { Fail-Fixture 'R7C_SYNTHETIC_IMAGE_MISSING' }
}

function Create-Volume([string]$Name, [string]$Scope) {
    if((Invoke-Docker 'VOLUME_PRECHECK' @('volume','inspect',$Name) $true).ExitCode -eq 0){Fail-Fixture 'R7C_SYNTHETIC_VOLUME_COLLISION'}
    $created=(Invoke-Docker 'VOLUME_CREATE' @('volume','create','--label',"estakada.r7c.scope=$Scope",'--label','estakada.r7c.synthetic=1',$Name)).Stdout.Trim()
    $row=@((Invoke-Docker 'VOLUME_VERIFY' @('volume','inspect',$Name)).Stdout|ConvertFrom-Json)[0]
    if($created -cne $Name -or [string]$row.Name -cne $Name -or [string]$row.Labels.'estakada.r7c.scope' -cne $Scope -or [string]$row.Labels.'estakada.r7c.synthetic' -cne '1'){Fail-Fixture 'R7C_SYNTHETIC_VOLUME_IDENTITY'}
}

function Create-Network([string]$Name, [string]$Scope) {
    if((Invoke-Docker 'NETWORK_PRECHECK' @('network','inspect',$Name) $true).ExitCode -eq 0){Fail-Fixture 'R7C_SYNTHETIC_NETWORK_COLLISION'}
    [void](Invoke-Docker 'NETWORK_CREATE' @('network','create','--internal','--label',"estakada.r7c.scope=$Scope",'--label','estakada.r7c.synthetic=1',$Name))
    $row=@((Invoke-Docker 'NETWORK_VERIFY' @('network','inspect',$Name)).Stdout|ConvertFrom-Json)[0]
    if([string]$row.Name -cne $Name -or [string]$row.Labels.'estakada.r7c.scope' -cne $Scope -or [string]$row.Labels.'estakada.r7c.synthetic' -cne '1'){Fail-Fixture 'R7C_SYNTHETIC_NETWORK_IDENTITY'}
}

function Validate-State([object]$State) {
    $properties=@($State.PSObject.Properties.Name|Sort-Object)
    $expectedProperties=@('appImage','containers','dbImage','ingressImage','networks','project','runId','schema','scope','volumes'|Sort-Object)
    if(($properties-join "`n")-cne($expectedProperties-join "`n") -or [string]$State.schema -cne 'estakada.r7c-synthetic-fixture-v1' -or [string]$State.runId -cnotmatch '^[0-9a-f]{32}$'){Fail-Fixture 'R7C_SYNTHETIC_STATE_INVALID'}
    $project="nestakada-r7c-rehearsal-$($State.runId)";$scope="rehearsal:$($State.runId)"
    if([string]$State.project -cne $project -or [string]$State.scope -cne $scope){Fail-Fixture 'R7C_SYNTHETIC_STATE_INVALID'}
    foreach($image in @([string]$State.appImage,[string]$State.ingressImage,[string]$State.dbImage)){if($image -cnotmatch '^sha256:[0-9a-f]{64}$'){Fail-Fixture 'R7C_SYNTHETIC_STATE_INVALID'}}
    $containers=@("$project-old-db","$project-new-db","$project-old-app","$project-new-app","$project-ingress")
    $networks=@("$project-old-dbnet","$project-new-dbnet","$project-ingress","$project-old-web","$project-new-web")
    $volumes=@("$project-selector","$project-sentinel-selector")
    foreach($role in @('old','new')){$volumes+=@("$project-$role-source","$project-$role-media","$project-$role-secrets","$project-$role-authority","$project-$role-dbdata")}
    if((@($State.containers|Sort-Object)-join "`n")-cne(@($containers|Sort-Object)-join "`n") -or (@($State.networks|Sort-Object)-join "`n")-cne(@($networks|Sort-Object)-join "`n") -or (@($State.volumes|Sort-Object)-join "`n")-cne(@($volumes|Sort-Object)-join "`n")){Fail-Fixture 'R7C_SYNTHETIC_STATE_INVALID'}
    return [pscustomobject]@{project=$project;scope=$scope;containers=$containers;networks=$networks;volumes=$volumes}
}

function Common-DbEnvironment([string]$Role, [string]$DbUser, [object]$State, [bool]$ReadOnlyTarget = $false) {
    $settings = if($ReadOnlyTarget){'config.settings.local_cutover'}else{'config.settings.local_restore'}
    $result = @(
        '--env','PYTHONPATH=/app','--env',"DJANGO_SETTINGS_MODULE=$settings",'--env','ESTAKADA_LOCAL_RESTORE=1',
        '--env','ESTAKADA_DJANGO_SECRET=r7c-synthetic-only','--env','ESTAKADA_ALLOWED_HOSTS=localhost,r7c-probe.invalid',
        '--env',"ESTAKADA_DB_NAME=r7c_$Role",'--env',"ESTAKADA_DB_USER=$DbUser",'--env','ESTAKADA_DB_HOST=db','--env','ESTAKADA_DB_PORT=5432',
        '--env','ESTAKADA_DB_PASSWORD_FILE=/run/secrets/db-password','--env','ESTAKADA_DB_SSLROOTCERT=/run/secrets/database-ca',
        '--env',"ESTAKADA_APP_IMAGE_DIGEST=$($State.appImage)"
    )
    if($ReadOnlyTarget){$result += @('--env',"ESTAKADA_R7C_ROLE=$Role",'--env',"ESTAKADA_R7C_GENERATION_SHA256=$(if($Role -ceq 'old'){'a'*64}else{'b'*64})",'--env',"ESTAKADA_R7C_STORAGE_BINDING_SHA256=$('0'*64)")}else{$result += @('--env','ESTAKADA_RESTORE_VERIFY_WRITE=1')}
    return $result
}

function Setup-Fixture {
    if (Test-Path -LiteralPath $statePath) { Fail-Fixture 'R7C_SYNTHETIC_STATE_EXISTS' }
    if (!(Test-Path -LiteralPath $work)) { [void](New-Item -ItemType Directory -Path $work) }
    if (!(Test-Path -LiteralPath $fixtureRoot)) { [void](New-Item -ItemType Directory -Path $fixtureRoot) }
    Assert-FixtureDirectory $work
    Assert-FixtureDirectory $fixtureRoot
    $runtime = Get-Content -Raw -LiteralPath (Join-Path $repo 'environment\foundation\runtime-images.lock.json') | ConvertFrom-Json
    $editor = Get-Content -Raw -LiteralPath (Join-Path $repo 'environment\editor-package\local-runtime.json') | ConvertFrom-Json
    $appImage = [string]$editor.appImageId
    $ingressImage = [string]($runtime.images | Where-Object component -ceq 'local-ingress').dockerReportedImageId
    $dbImage = [string]($runtime.images | Where-Object component -ceq 'postgres').dockerReportedImageId
    foreach ($image in @($appImage,$ingressImage,$dbImage)) { Assert-Image $image }
    $runId = [guid]::NewGuid().ToString('N'); $scope = "rehearsal:$runId"; $project = "nestakada-r7c-rehearsal-$runId"
    $volumes = @("$project-selector","$project-sentinel-selector")
    foreach ($role in @('old','new')) { $volumes += @("$project-$role-source","$project-$role-media","$project-$role-secrets","$project-$role-authority","$project-$role-dbdata") }
    $networks = @("$project-old-dbnet","$project-new-dbnet","$project-ingress","$project-old-web","$project-new-web")
    $containers = @("$project-old-db","$project-new-db","$project-old-app","$project-new-app","$project-ingress")
    $state = [ordered]@{schema='estakada.r7c-synthetic-fixture-v1';runId=$runId;scope=$scope;project=$project;appImage=$appImage;ingressImage=$ingressImage;dbImage=$dbImage;containers=$containers;networks=$networks;volumes=$volumes}
    Write-SafeJson $statePath $state
    foreach ($name in $volumes) { Create-Volume $name $scope }
    foreach ($name in @("$project-old-dbnet","$project-new-dbnet")) { Create-Network $name $scope }

    $logo = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>' + "`n"
    $logoPath = Join-Path $fixtureRoot 'logo.svg'; [IO.File]::WriteAllText($logoPath,$logo,$utf8)
    $logoBytes = [IO.File]::ReadAllBytes($logoPath); $logoSha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($logoBytes)).ToLowerInvariant()
    $inventory = @([ordered]@{path='img/11111111-1111-4111-8111-111111111111/main.svg';sha256=$logoSha;bytes=$logoBytes.Length})
    $inventoryPath = Join-Path $fixtureRoot 'media-inventory.json'; [IO.File]::WriteAllText($inventoryPath,((ConvertTo-Json -InputObject $inventory -Compress)+"`n"),$utf8)
    $passwordPath = Join-Path $fixtureRoot 'db-password'; [IO.File]::WriteAllText($passwordPath,"r7c-synthetic-only-password`n",$utf8)

    foreach ($role in @('old','new')) {
        $sourceVolume="$project-$role-source";$mediaVolume="$project-$role-media";$authorityVolume="$project-$role-authority";$secretsVolume="$project-$role-secrets"
        [void](Invoke-Docker 'SOURCE_COPY' @('run','--rm','--user','0:0','--network','none','--read-only','--mount',"type=bind,src=$(Join-Path $repo 'src'),dst=/source,readonly",'--mount',"type=volume,src=$sourceVolume,dst=/dest",'--entrypoint','/bin/cp',$appImage,'-a','/source/.','/dest/'))
        [void](Invoke-Docker 'MEDIA_MKDIR' @('run','--rm','--user','0:0','--network','none','--read-only','--mount',"type=volume,src=$mediaVolume,dst=/media",'--entrypoint','/bin/mkdir',$appImage,'-p','/media/img/11111111-1111-4111-8111-111111111111'))
        [void](Invoke-Docker 'MEDIA_COPY' @('run','--rm','--user','0:0','--network','none','--read-only','--mount',"type=bind,src=$logoPath,dst=/input/logo.svg,readonly",'--mount',"type=volume,src=$mediaVolume,dst=/media",'--entrypoint','/bin/cp',$appImage,'/input/logo.svg','/media/img/11111111-1111-4111-8111-111111111111/main.svg'))
        [void](Invoke-Docker 'AUTHORITY_COPY' @('run','--rm','--user','0:0','--network','none','--read-only','--mount',"type=bind,src=$inventoryPath,dst=/input/media-inventory.json,readonly",'--mount',"type=volume,src=$authorityVolume,dst=/authority",'--entrypoint','/bin/cp',$appImage,'/input/media-inventory.json','/authority/media-inventory.json'))
        [void](Invoke-Docker 'SECRET_COPY' @('run','--rm','--user','0:0','--network','none','--read-only','--mount',"type=bind,src=$passwordPath,dst=/input/db-password,readonly",'--mount',"type=volume,src=$secretsVolume,dst=/out",'--entrypoint','/bin/cp',$appImage,'/input/db-password','/out/db-password'))
        [void](Invoke-Docker 'CERT_CREATE' @('run','--rm','--user','0:0','--network','none','--read-only','--mount',"type=volume,src=$secretsVolume,dst=/out",'--entrypoint','openssl',$dbImage,'req','-x509','-newkey','rsa:2048','-nodes','-keyout','/out/database-server-key','-out','/out/database-ca','-days','1','-subj','/CN=db','-addext','subjectAltName=DNS:db'))
        $dbName="$project-$role-db";$dbNetwork="$project-$role-dbnet";$dbData="$project-$role-dbdata";$dbAdmin="r7c_$($role)_admin";$dbRuntime="r7c_$($role)_runtime"
        [void](Invoke-Docker 'DB_START' @('run','-d','--name',$dbName,'--label',"estakada.r7c.scope=$scope",'--label','estakada.r7c.synthetic=1','--network',$dbNetwork,'--network-alias','db','--read-only','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','DAC_OVERRIDE','--cap-add','FOWNER','--cap-add','SETGID','--cap-add','SETUID','--security-opt','no-new-privileges','--tmpfs','/var/run/postgresql:rw,nosuid,nodev,noexec,size=16m,uid=999,gid=999,mode=3775','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=32m,mode=1777','--mount',"type=volume,src=$dbData,dst=/var/lib/postgresql",'--mount',"type=volume,src=$secretsVolume,dst=/run/secrets,readonly",'--mount',"type=bind,src=$(Join-Path $repo 'environment\foundation\db-start.sh'),dst=/tools/db-start.sh,readonly",'--env',"POSTGRES_DB=r7c_$role",'--env',"POSTGRES_USER=$dbAdmin",'--env','POSTGRES_PASSWORD_FILE=/run/secrets/db-password','--env','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','--entrypoint','/bin/sh',$dbImage,'/tools/db-start.sh','postgres','-c','listen_addresses=*','-c','max_connections=20','-c','log_statement=none','-c','ssl=on','-c','ssl_cert_file=/run/secrets/database-ca','-c','ssl_key_file=/var/run/postgresql/server.key','-c','ssl_min_protocol_version=TLSv1.2'))
        $ready=$false
        for($attempt=0;$attempt -lt 45;$attempt++){ if((Invoke-Docker 'DB_READY' @('exec',$dbName,'pg_isready','-h','127.0.0.1','-p','5432','-U',$dbAdmin,'-d',"r7c_$role") $true).ExitCode -eq 0){$ready=$true;break};Start-Sleep -Seconds 1 }
        if(!$ready){Fail-Fixture 'R7C_SYNTHETIC_DB_NOT_READY'}
        [void](Invoke-Docker 'DB_SCHEMA' @('exec',$dbName,'psql','-v','ON_ERROR_STOP=1','-U',$dbAdmin,'-d',"r7c_$role",'-c',"CREATE SCHEMA app AUTHORIZATION $dbAdmin"))
        $common = Common-DbEnvironment $role $dbAdmin $state
        [void](Invoke-Docker 'DB_MIGRATE' (@('run','--rm','--name',"$project-tool-migrate-$role",'--label',"estakada.r7c.scope=$scope",'--network',$dbNetwork,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--mount',"type=volume,src=$sourceVolume,dst=/app,readonly",'--mount',"type=volume,src=$secretsVolume,dst=/run/secrets,readonly",'--workdir','/app')+$common+@($appImage,'python','-B','manage.py','migrate','--noinput')))
        [void](Invoke-Docker 'DB_SEED' (@('run','--rm','--name',"$project-tool-seed-$role",'--label',"estakada.r7c.scope=$scope",'--network',$dbNetwork,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--mount',"type=bind,src=$repo,dst=/project,readonly",'--mount',"type=volume,src=$sourceVolume,dst=/app,readonly",'--mount',"type=volume,src=$secretsVolume,dst=/run/secrets,readonly",'--workdir','/app','--env','ESTAKADA_R7C_SYNTHETIC_FIXTURE=1')+$common+@($appImage,'python','-B','/project/tools/rebuild7_selector_fixture.py','seed','--media-sha256',$logoSha,'--media-bytes',[string]$logoBytes.Length)))
        $grantSql="CREATE ROLE $dbRuntime LOGIN PASSWORD 'r7c-synthetic-only-password'; GRANT CONNECT ON DATABASE r7c_$role TO $dbRuntime; GRANT USAGE ON SCHEMA app TO $dbRuntime; GRANT SELECT ON ALL TABLES IN SCHEMA app TO $dbRuntime; GRANT SELECT ON ALL SEQUENCES IN SCHEMA app TO $dbRuntime; ALTER DEFAULT PRIVILEGES FOR ROLE $dbAdmin IN SCHEMA app GRANT SELECT ON TABLES TO $dbRuntime;"
        [void](Invoke-Docker 'DB_GRANT' @('exec',$dbName,'psql','-v','ON_ERROR_STOP=1','-U',$dbAdmin,'-d',"r7c_$role",'-c',$grantSql))
        $runtimeEnvironment = Common-DbEnvironment $role $dbRuntime $state $true
        [void](Invoke-Docker 'DB_READONLY' (@('run','--rm','--name',"$project-tool-readonly-$role",'--label',"estakada.r7c.scope=$scope",'--network',$dbNetwork,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m','--mount',"type=bind,src=$repo,dst=/project,readonly",'--mount',"type=volume,src=$sourceVolume,dst=/app,readonly",'--mount',"type=volume,src=$secretsVolume,dst=/run/secrets,readonly",'--workdir','/app','--env','ESTAKADA_R7C_SYNTHETIC_FIXTURE=1')+$runtimeEnvironment+@($appImage,'python','-B','/project/tools/rebuild7_selector_fixture.py','verify-readonly','--expected-user',$dbRuntime)))
    }
    $authority = [ordered]@{
        schema='estakada.r7c-authority-v1';scope=$scope;runId=$runId;project=$project;prefix=$project;loopbackPort=18086;appImage=$appImage;ingressImage=$ingressImage;selectorVolume="$project-selector"
        old=[ordered]@{generationSha256=('a'*64);storageBindingSha256=('0'*64);dbName='r7c_old';dbUser='r7c_old_runtime';dbContainer="$project-old-db";dbImage=$dbImage;dbNetwork="$project-old-dbnet";sourceVolume="$project-old-source";mediaVolume="$project-old-media";secretsVolume="$project-old-secrets";authorityVolume="$project-old-authority"}
        new=[ordered]@{generationSha256=('b'*64);storageBindingSha256=('0'*64);dbName='r7c_new';dbUser='r7c_new_runtime';dbContainer="$project-new-db";dbImage=$dbImage;dbNetwork="$project-new-dbnet";sourceVolume="$project-new-source";mediaVolume="$project-new-media";secretsVolume="$project-new-secrets";authorityVolume="$project-new-authority"}
        durableLocal=[ordered]@{selectorVolume="$project-sentinel-selector";ingressName="$project-sentinel-ingress";ingressId='ABSENT';selectorSha256='ABSENT'}
    }
    Write-SafeJson $authorityPath $authority
    & (Join-Path $PSScriptRoot 'rebuild7-selector.ps1') -AuthoritySet synthetic -Action SealSynthetic
    Write-Output "R7C_SYNTHETIC_SETUP_PASS scope=$scope"
}

function Cleanup-Fixture {
    if (!(Test-Path -LiteralPath $statePath -PathType Leaf)) { Write-Output 'R7C_SYNTHETIC_CLEANUP_PASS state=ABSENT'; return }
    Assert-FixtureDirectory $work
    $stateItem=Get-Item -Force -LiteralPath $statePath
    if(($stateItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $stateItem.Length -gt 65536){Fail-Fixture 'R7C_SYNTHETIC_STATE_INVALID'}
    $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    $closed=Validate-State $state
    foreach($name in @($closed.containers)){
        $inspect=Invoke-Docker 'CLEANUP_CONTAINER_INSPECT' @('inspect',[string]$name) $true
        if($inspect.ExitCode -eq 0){$container=@($inspect.Stdout|ConvertFrom-Json)[0];if([string]$container.Config.Labels.'estakada.r7c.scope' -cne [string]$closed.scope -or [string]$container.Config.Labels.'estakada.r7c.synthetic' -cne '1'){Fail-Fixture 'R7C_SYNTHETIC_FOREIGN_CONTAINER'};if([bool]$container.State.Running){[void](Invoke-Docker 'CLEANUP_CONTAINER_STOP' @('stop','--time','10',[string]$container.Id))};[void](Invoke-Docker 'CLEANUP_CONTAINER_REMOVE' @('rm',[string]$container.Id))}
    }
    foreach($name in @($closed.networks)){
        $inspect=Invoke-Docker 'CLEANUP_NETWORK_INSPECT' @('network','inspect',[string]$name) $true
        if($inspect.ExitCode -eq 0){$network=@($inspect.Stdout|ConvertFrom-Json)[0];if([string]$network.Labels.'estakada.r7c.scope' -cne [string]$closed.scope -or [string]$network.Labels.'estakada.r7c.synthetic' -cne '1' -or @($network.Containers.PSObject.Properties).Count -ne 0){Fail-Fixture 'R7C_SYNTHETIC_NETWORK_LINKED'};[void](Invoke-Docker 'CLEANUP_NETWORK_REMOVE' @('network','rm',[string]$network.Id))}
    }
    foreach($name in @($closed.volumes)){
        $inspect=Invoke-Docker 'CLEANUP_VOLUME_INSPECT' @('volume','inspect',[string]$name) $true
        if($inspect.ExitCode -eq 0){$volume=@($inspect.Stdout|ConvertFrom-Json)[0];if([string]$volume.Labels.'estakada.r7c.scope' -cne [string]$closed.scope -or [string]$volume.Labels.'estakada.r7c.synthetic' -cne '1'){Fail-Fixture 'R7C_SYNTHETIC_FOREIGN_VOLUME'};[void](Invoke-Docker 'CLEANUP_VOLUME_REMOVE' @('volume','rm',[string]$name))}
    }
    if(@(Docker-Lines 'CLEANUP_CONTAINER_LIST' @('ps','-aq','--filter',"label=estakada.r7c.scope=$($closed.scope)")).Count -ne 0 -or @(Docker-Lines 'CLEANUP_NETWORK_LIST' @('network','ls','-q','--filter',"label=estakada.r7c.scope=$($closed.scope)")).Count -ne 0 -or @(Docker-Lines 'CLEANUP_VOLUME_LIST' @('volume','ls','-q','--filter',"label=estakada.r7c.scope=$($closed.scope)")).Count -ne 0){Fail-Fixture 'R7C_SYNTHETIC_CLEANUP_POST_AUDIT'}
    foreach($path in @((Join-Path $fixtureRoot 'logo.svg'),(Join-Path $fixtureRoot 'media-inventory.json'),(Join-Path $fixtureRoot 'db-password'),$authorityPath,$statePath)){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path -Force}}
    if(Test-Path -LiteralPath $fixtureRoot){Remove-Item -LiteralPath $fixtureRoot -Force}
    Write-Output "R7C_SYNTHETIC_CLEANUP_PASS scope=$($closed.scope) containers=0 networks=0 volumes=0"
}

if($Action -ceq 'Setup'){Setup-Fixture}else{Cleanup-Fixture}
