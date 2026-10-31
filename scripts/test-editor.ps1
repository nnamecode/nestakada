[CmdletBinding()]
param([ValidateSet('save','all')][string]$Suite='save')
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$root=Join-Path $repo 'work/foundation/test'
$manifest=Get-Content -Raw -LiteralPath (Join-Path $root 'manifest.json')|ConvertFrom-Json
if(!$manifest.active -or $manifest.environment -ne 'test' -or $manifest.composeProject -ne 'nestakada-foundation-test'){throw 'Exclusive active test environment required'}
$source=[IO.Path]::GetFullPath($manifest.sourceDirectory)
if(!$source.StartsWith((Join-Path $root 'sources')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Foreign test source'}
if((Get-FileHash -LiteralPath $manifest.sourceManifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sourceSha256){throw 'Source manifest drift'}
foreach($row in (Get-Content -Raw -LiteralPath $manifest.sourceManifest|ConvertFrom-Json)){
    $path=[IO.Path]::GetFullPath((Join-Path $source $row.path))
    if(!$path.StartsWith($source+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
       ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) -or
       (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Frozen test source drift'}
}
$image='sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986'
$actual=docker.exe image inspect $image|ConvertFrom-Json
if($LASTEXITCODE -ne 0 -or $actual.Id -ne $image){throw 'Pinned candidate required'}
$network=docker.exe network inspect nestakada-foundation-test-db|ConvertFrom-Json
if($LASTEXITCODE -ne 0 -or !$network.Internal -or $network.Labels.'nestakada.scope' -ne 'foundation-test'){throw 'Private test DB network required'}
$private=Join-Path $root 'private'
$dockerArgs=@('run','--rm','--name',"nestakada-editor-tests-$Suite",'--network','nestakada-foundation-test-db',
    '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
    '--memory','768m','--memory-swap','768m','--cpus','1','--pids-limit','128',
    '--tmpfs','/tmp:rw,noexec,nosuid,size=128m','--mount',"type=bind,source=$source,target=/app,readonly",
    '--mount',"type=bind,source=$private\migrator-password,target=/run/secrets/database-password,readonly",
    '--mount',"type=bind,source=$private\django-secret,target=/run/secrets/django-secret,readonly",
    '--mount',"type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
    '--mount','type=volume,source=nestakada-foundation-test-media-exchange,target=/exchange',
    '--workdir','/app','--env','DJANGO_SETTINGS_MODULE=estakada.settings.local_http',
    '--env','ESTAKADA_LOCAL_ENV=test','--env','ESTAKADA_DB_NAME=estakada_foundation_unit',
    '--env','ESTAKADA_DB_USER=app_migrator','--env','PYTHONDONTWRITEBYTECODE=1',
    $image,'python','-B','manage.py','test')
if($Suite -eq 'save'){$dockerArgs+=@('page_editor.test_save_http')}
else{$dockerArgs+=@('audit','content','accounts','media_library','page_versions','foundation_tests','editor_runtime','page_editor')}
$dockerArgs+=@('--keepdb','--noinput','--verbosity','2')
& docker.exe @dockerArgs
if($LASTEXITCODE -ne 0){throw 'Editor tests failed; inspect evidence before any retry'}
