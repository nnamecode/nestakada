[CmdletBinding()]
param([ValidateSet('save','draft','races','source','media','embedded','failure','maximum','combined','shared-quota','shared','shared-check','shared-reads','shared-blob','shared-metadata','shared-provenance','shared-journal','shared-reservation','shared-cleanup','shared-public','shared-calibration','unicode','parser','entity','editor','all')][string]$Suite='save')
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
$quotaArgs=@()
if($Suite -in @('shared-reservation','shared-cleanup','shared-public','shared-calibration','shared','all')){
    $stateVolume=@(docker.exe volume inspect nestakada-foundation-test-state|ConvertFrom-Json)[0]
    if($LASTEXITCODE -ne 0 -or !$stateVolume -or $stateVolume.Name -ne 'nestakada-foundation-test-state' -or
       $stateVolume.Driver -ne 'local' -or $stateVolume.Labels.'nestakada.scope' -ne 'foundation-test'){throw 'Existing private test state volume required'}
    $quotaRun=[guid]::Parse($manifest.runId).ToString()
    if($quotaRun -cne $manifest.runId){throw 'Canonical test run UUID required'}
    $quotaArgs=@('--mount','type=volume,source=nestakada-foundation-test-state,target=/rc-state',
        '--env',"ESTAKADA_SHARED_CALIBRATION_ROOT=/rc-state/rc-q351/$quotaRun")
    if($Suite -eq 'shared-calibration'){$quotaArgs+=@('--env','ESTAKADA_RUN_SHARED_CALIBRATION=1')}
}
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
    '--env','ESTAKADA_DB_USER=app_migrator','--env','PYTHONDONTWRITEBYTECODE=1') + $quotaArgs + @(
    $image,'python','-B','manage.py','test')
if($Suite -eq 'save'){$dockerArgs+=@('page_editor.test_save_http')}
elseif($Suite -eq 'draft'){$dockerArgs+=@('page_editor.test_draft_restore_http','page_editor.test_draft_cancel_admission')}
elseif($Suite -eq 'races'){$dockerArgs+=@('page_editor.test_draft_restore_concurrency')}
elseif($Suite -eq 'source'){$dockerArgs+=@('page_editor.test_source_admission')}
elseif($Suite -eq 'media'){$dockerArgs+=@('page_editor.test_media_http','--failfast')}
elseif($Suite -eq 'embedded'){$dockerArgs+=@('page_editor.test_embedded_http','--failfast')}
elseif($Suite -eq 'failure'){$dockerArgs+=@('page_editor.test_failure_http','--failfast')}
elseif($Suite -eq 'maximum'){$dockerArgs+=@('page_editor.test_failure_http.EditorFailureHttpTests.test_fr07_006_full_framework_handler_max_dto_real_child_no_mutation','--failfast')}
elseif($Suite -eq 'combined'){$dockerArgs+=@('page_editor.test_combined_http','--failfast')}
elseif($Suite -eq 'shared-quota'){$dockerArgs+=@('page_editor.test_shared_quota_probe','--failfast')}
elseif($Suite -eq 'shared'){$dockerArgs+=@('shared_content','--failfast')}
elseif($Suite -eq 'shared-check'){$dockerArgs+=@('shared_content.test_shared_http.SharedHttpTests.test_owner_header_real_child_canary_exact_slot_no_fake_paragraph','--failfast')}
elseif($Suite -eq 'shared-reads'){$dockerArgs+=@('shared_content.test_shared_reads','--failfast')}
elseif($Suite -eq 'shared-blob'){$dockerArgs+=@('shared_content.test_shared_storage','shared_content.test_shared_file_reads','--failfast')}
elseif($Suite -eq 'shared-metadata'){$dockerArgs+=@('shared_content.test_shared_file_reads.SharedFileReadTests.test_mixed_unknown_and_malformed_file_metadata_rejected_by_database','--failfast')}
elseif($Suite -eq 'shared-provenance'){$dockerArgs+=@('shared_content.test_shared_provenance','--failfast')}
elseif($Suite -eq 'shared-journal'){$dockerArgs+=@('shared_content.test_shared_journal','--failfast')}
elseif($Suite -eq 'shared-reservation'){$dockerArgs+=@('shared_content.test_shared_reservation','--failfast')}
elseif($Suite -eq 'shared-cleanup'){$dockerArgs+=@('shared_content.test_shared_cleanup.SharedCleanupStorageTests','shared_content.test_shared_cleanup.SharedCleanupTests','--failfast')}
elseif($Suite -eq 'shared-public'){$dockerArgs+=@('shared_content.test_shared_public','--failfast')}
elseif($Suite -eq 'shared-calibration'){$dockerArgs+=@('shared_content.test_shared_calibration','shared_content.test_shared_cleanup.SharedCleanupCalibrationTests','--failfast')}
elseif($Suite -eq 'unicode'){$dockerArgs+=@('page_editor.test_unicode_admission','--failfast')}
elseif($Suite -eq 'parser'){$dockerArgs+=@('page_editor.test_html_parser','--failfast')}
elseif($Suite -eq 'entity'){$dockerArgs+=@('page_editor.test_entity_http','--failfast')}
elseif($Suite -eq 'editor'){$dockerArgs+=@('page_editor','--failfast')}
else{$dockerArgs+=@('audit','content','accounts','media_library','page_versions','foundation_tests','editor_runtime','page_editor','shared_content','--failfast')}
$dockerArgs+=@('--keepdb','--noinput','--verbosity','2')
& docker.exe @dockerArgs
if($LASTEXITCODE -ne 0){throw 'Editor tests failed; inspect evidence before any retry'}
