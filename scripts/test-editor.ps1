[CmdletBinding()]
param([ValidateSet('save','draft','races','source','media','embedded','failure','maximum','combined','price-gui','table-gui','restore-terminal','terminal-ui','final-media','guard','dev09','dev09-services','dev11','dev12-candidates','dev12-media','dev12-projector','dev12-public','dev12-remediation','dev12-schema','dev13','dev13-notifications','dev25','dev25-affected','dev26-projection','check','migrations','public-read','public-http','public-nav','public-visibility','public-layout','public-image','public-shared-page','shared-quota','shared','shared-check','shared-reads','shared-blob','shared-metadata','shared-provenance','shared-journal','shared-reservation','shared-public','shared-calibration','ref7d','unicode','parser','entity','editor','all')][string]$Suite='save')
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
if($Suite -in @('guard','dev25-affected','public-image','public-shared-page','shared-reservation','shared-public','shared-calibration','shared','all')){
    $stateVolume=@(docker.exe volume inspect nestakada-foundation-test-state|ConvertFrom-Json)[0]
    if($LASTEXITCODE -ne 0 -or !$stateVolume -or $stateVolume.Name -ne 'nestakada-foundation-test-state' -or
       $stateVolume.Driver -ne 'local' -or $stateVolume.Labels.'nestakada.scope' -ne 'foundation-test'){throw 'Existing private test state volume required'}
    $quotaRun=[guid]::Parse($manifest.runId).ToString()
    if($quotaRun -cne $manifest.runId){throw 'Canonical test run UUID required'}
    $quotaArgs=@('--mount','type=volume,source=nestakada-foundation-test-state,target=/rc-state',
        '--env',"ESTAKADA_SHARED_CALIBRATION_ROOT=/rc-state/rc-q351/$quotaRun")
    if($Suite -eq 'shared-calibration'){$quotaArgs+=@('--env','ESTAKADA_RUN_SHARED_CALIBRATION=1')}
}
$guardArgs=@()
if($Suite -in @('guard','all')){
    foreach($entry in @(@('routes','docs/analytics-route-map.csv','DEV20_ROUTES_SHA256'),@('media','docs/analytics-media-evidence.csv','DEV20_MEDIA_SHA256'))){
        $registry=[IO.Path]::GetFullPath((Join-Path $repo $entry[1]))
        if((Get-Item -LiteralPath $registry).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Registry link rejected'}
        $registryHash=(Get-FileHash -LiteralPath $registry -Algorithm SHA256).Hash.ToLowerInvariant()
        $guardArgs+=@('--mount',"type=bind,source=$registry,target=/legacy-docs/$($entry[0]).csv,readonly",'--env',"$($entry[2])=$registryHash")
    }
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
    '--env','ESTAKADA_DB_USER=app_migrator','--env','PYTHONDONTWRITEBYTECODE=1') + $quotaArgs + $guardArgs + @(
    $image,'python','-B','manage.py')
if($Suite -notin @('check','migrations')){$dockerArgs+=@('test')}
if($Suite -eq 'check'){$dockerArgs+=@('check')}
elseif($Suite -eq 'migrations'){$dockerArgs+=@('makemigrations','--check','--dry-run')}
elseif($Suite -eq 'save'){$dockerArgs+=@('page_editor.test_save_http')}
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
elseif($Suite -eq 'ref7d'){$dockerArgs+=@(
    'shared_content.test_shared_http.SharedHttpTests.test_simple_draft_does_not_require_legacy_reservation_profile',
    'shared_content.test_shared_http.SharedHttpTests.test_simple_apply_uses_inline_db_without_legacy_reservation_profile',
    'shared_content.test_shared_http.SharedHttpTests.test_simple_current_supports_simple_draft_without_legacy_stage_route',
    'shared_content.test_shared_http.SharedHttpTests.test_legacy_http_surface_is_unrouted_for_every_role_without_mutation',
    'shared_content.test_shared_http.SharedHttpTests.test_history_and_editor_assets_have_no_legacy_lifecycle_controls',
    'shared_content.test_shared_file_reads.SharedFileReadTests.test_real_check_current_file_and_direct_restore_read_outside_sql_transactions',
    'shared_content.test_shared_file_reads.SharedFileReadTests.test_simple_inline_writes_need_no_profile_and_create_no_blob_or_journal',
    'shared_content.test_shared_journal.SharedJournalRollbackTests.test_sjr005_legacy_book_does_not_block_simple_inline_writes_or_change_files',
    '--failfast')}
elseif($Suite -eq 'shared-reads'){$dockerArgs+=@('shared_content.test_shared_reads','--failfast')}
elseif($Suite -eq 'shared-blob'){$dockerArgs+=@('shared_content.test_shared_storage','shared_content.test_shared_file_reads','--failfast')}
elseif($Suite -eq 'shared-metadata'){$dockerArgs+=@('shared_content.test_shared_file_reads.SharedFileReadTests.test_mixed_unknown_and_malformed_file_metadata_rejected_by_database','--failfast')}
elseif($Suite -eq 'shared-provenance'){$dockerArgs+=@('shared_content.test_shared_provenance','--failfast')}
elseif($Suite -eq 'shared-journal'){$dockerArgs+=@('shared_content.test_shared_journal','--failfast')}
elseif($Suite -eq 'shared-reservation'){$dockerArgs+=@('shared_content.test_shared_reservation','--failfast')}
elseif($Suite -eq 'final-media'){$dockerArgs+=@('page_editor.test_final_media_http','--failfast')}
elseif($Suite -eq 'guard'){$dockerArgs+=@('request_guard.tests','audit','content','accounts','foundation_tests','--failfast')}
elseif($Suite -eq 'dev09'){$dockerArgs+=@('content.test_dev09_migration_apply','--failfast')}
elseif($Suite -eq 'dev09-services'){$dockerArgs+=@('content.test_dev09e_services_catalog','--failfast')}
elseif($Suite -eq 'dev11'){$dockerArgs+=@(
    'content.test_dev11_seo_projection',
    'content.test_dev11_auto_repair',
    'content.test_dev11_sitemap',
    'content.test_dev11_robots',
    'content.test_public_http',
    'content.test_dev10_gallery_public',
    '--failfast')}
elseif($Suite -eq 'dev12-schema'){$dockerArgs+=@(
            'page_versions.test_home_profile_schema',
            'page_editor.test_home_sources',
    'page_editor.test_home_candidates',
    'page_editor.test_home_save_http',
    'page_versions.test_simple_commands',
    'page_versions.test_http',
    'page_editor.test_check_http',
    'page_editor.test_save_http',
    '--failfast')}
elseif($Suite -eq 'dev12-candidates'){$dockerArgs+=@('page_editor.test_home_candidates','--failfast')}
elseif($Suite -eq 'dev12-media'){$dockerArgs+=@('content.test_dev12_home_media_import','content.test_dev12_home_writer','--failfast')}
elseif($Suite -eq 'dev12-projector'){$dockerArgs+=@('content.test_dev12_home_projection','content.test_dev12_home_delete_guard','content.test_simple_page_delete','--failfast')}
elseif($Suite -eq 'dev12-public'){$dockerArgs+=@('content.test_dev12_home_public','--failfast')}
elseif($Suite -eq 'dev12-remediation'){$dockerArgs+=@('page_versions.test_home_profile_schema','page_editor.test_home_sources','page_editor.test_home_save_http','--failfast')}
elseif($Suite -eq 'dev13'){$dockerArgs+=@('service_requests','--failfast')}
elseif($Suite -eq 'dev13-notifications'){$dockerArgs+=@('service_requests.test_notifications','--failfast')}
elseif($Suite -eq 'dev25'){$dockerArgs+=@('html_reserve','--failfast')}
elseif($Suite -eq 'dev26-projection'){$dockerArgs+=@('html_reserve.test_projection','html_reserve.test_delivery','html_reserve.test_delivery_tool','--failfast')}
elseif($Suite -eq 'dev25-affected'){$dockerArgs+=@(
    'content.test_public_http',
    'content.test_public_shared',
    'content.test_dev10_gallery_public',
    'content.test_dev12_home_public',
    'shared_content.test_shared_public',
    'media_library.test_html_reserve',
    'accounts.tests',
    'audit.test_http',
    'service_requests.tests',
    'service_requests.test_intake_http',
    '--failfast')}
elseif($Suite -eq 'public-read'){$dockerArgs+=@('content.test_public_read','--failfast')}
elseif($Suite -eq 'public-http'){$dockerArgs+=@('content.test_public_http','--failfast')}
elseif($Suite -eq 'public-nav'){$dockerArgs+=@('content.test_public_navigation','--failfast')}
elseif($Suite -eq 'public-visibility'){$dockerArgs+=@('content.test_public_read','content.test_public_http','content.test_public_navigation','--failfast')}
elseif($Suite -eq 'public-layout'){$dockerArgs+=@('content.test_public_body','content.test_public_http','--failfast')}
elseif($Suite -eq 'public-image'){$dockerArgs+=@('content.test_public_body','content.test_public_shared','--failfast')}
elseif($Suite -eq 'public-shared-page'){$dockerArgs+=@('content.test_public_shared','--failfast')}
elseif($Suite -eq 'shared-public'){$dockerArgs+=@('shared_content.test_shared_public','--failfast')}
elseif($Suite -eq 'price-gui'){$dockerArgs+=@('page_editor.test_price_gui_http','--failfast')}
elseif($Suite -eq 'table-gui'){$dockerArgs+=@('page_editor.test_table_gui_http','--failfast')}
elseif($Suite -eq 'restore-terminal'){$dockerArgs+=@('page_editor.test_restore_terminal_http','--failfast')}
elseif($Suite -eq 'terminal-ui'){$dockerArgs+=@('page_editor.test_terminal_ui_http','page_editor.test_restore_terminal_http','page_versions.test_http','--failfast')}
elseif($Suite -eq 'shared-calibration'){$dockerArgs+=@('shared_content.test_shared_calibration','--failfast')}
elseif($Suite -eq 'unicode'){$dockerArgs+=@('page_editor.test_unicode_admission','--failfast')}
elseif($Suite -eq 'parser'){$dockerArgs+=@('page_editor.test_html_parser','--failfast')}
elseif($Suite -eq 'entity'){$dockerArgs+=@('page_editor.test_entity_http','--failfast')}
elseif($Suite -eq 'editor'){$dockerArgs+=@('page_editor','--failfast')}
else{$dockerArgs+=@('request_guard.tests','audit','content','accounts','media_library','page_versions','foundation_tests','editor_runtime','page_editor','shared_content','--failfast')}
if($Suite -notin @('check','migrations')){$dockerArgs+=@('--keepdb','--noinput','--verbosity','2')}
& docker.exe @dockerArgs
if($LASTEXITCODE -ne 0){throw 'Editor check failed; inspect evidence before any retry'}
