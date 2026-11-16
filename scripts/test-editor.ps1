[CmdletBinding()]
param([ValidateSet('save','draft','races','source','media','embedded','failure','maximum','combined','price-gui','table-gui','restore-terminal','terminal-ui','final-media','guard','auth-login','admin-workshop','dev09','dev09-services','dev11','dev12-candidates','dev12-media','dev12-projector','dev12-public','dev12-remediation','dev12-schema','dev13','dev13-notifications','dev25','dev25-affected','dev26-projection','test08-fixture','test08-execution','local-preview-export','local-admin-demo','test10-fixture','check','migrations','public-read','public-http','public-nav','public-visibility','public-layout','public-image','public-shared-page','shared-quota','shared','shared-check','shared-reads','shared-blob','shared-metadata','shared-provenance','shared-journal','shared-reservation','shared-public','shared-calibration','ref7d','unicode','parser','entity','editor','all')][string]$Suite='save')
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$root=Join-Path $repo 'work/foundation/test'
$manifest=Get-Content -Raw -LiteralPath (Join-Path $root 'manifest.json')|ConvertFrom-Json
if(!$manifest.active -or $manifest.environment -ne 'test' -or $manifest.composeProject -ne 'nestakada-foundation-test'){throw 'Exclusive active test environment required'}
$source=[IO.Path]::GetFullPath($manifest.sourceDirectory)
if(!$source.StartsWith((Join-Path $root 'sources')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Foreign test source'}
if((Get-FileHash -LiteralPath $manifest.sourceManifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sourceSha256){throw 'Source manifest drift'}
if($Suite -eq 'admin-workshop'){
    $logoRelative='accounts/assets/brand-logo.png'
    $logo=[IO.Path]::GetFullPath((Join-Path $source $logoRelative))
    if(!$logo.StartsWith($source+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Admin logo escaped frozen source'}
    $item=Get-Item -Force -LiteralPath $logo
    if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -ne 30190 -or
       (Get-FileHash -LiteralPath $logo -Algorithm SHA256).Hash.ToLowerInvariant() -cne '39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5'){
        throw 'Frozen admin logo mismatch'
    }
    $sourceRows=@(Get-Content -Raw -LiteralPath $manifest.sourceManifest|ConvertFrom-Json)
    if(@($sourceRows|Where-Object{$_.path -ceq $logoRelative}).Count -ne 1){throw 'Exact admin logo source admission required'}
}
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
if($Suite -in @('guard','dev25-affected','public-image','public-shared-page','shared-reservation','shared-public','shared-calibration','shared','local-admin-demo','all')){
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
$test08Args=@()
$test08Receipt=$null
$test08Reserve=$null
$localPreviewRun=$null
$localPreviewRoot=$null
$localPreviewRuns=$null
if($Suite -in @('test08-fixture','test08-execution','local-preview-export','local-admin-demo')){
    $runId=[guid]::Parse([string]$manifest.runId).ToString()
    if($runId -cne $manifest.runId){throw 'Canonical test run UUID required'}
    $staging=[IO.Path]::GetFullPath((Join-Path $root "test08-fixture/$runId"))
    $stagingParent=[IO.Path]::GetFullPath((Join-Path $root 'test08-fixture'))
    if(!$staging.StartsWith($stagingParent+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Foreign TEST-08 staging'}
    $assetManifestPath=Join-Path $staging 'manifest.json'
    $assetRoot=Join-Path $staging 'source'
    foreach($path in @($staging,$assetManifestPath,$assetRoot)){
        $item=Get-Item -Force -LiteralPath $path
        if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 staging link rejected'}
    }
    $assetManifest=Get-Content -Raw -LiteralPath $assetManifestPath|ConvertFrom-Json
    if($assetManifest.schema -cne 'test08-fixture-assets-v1' -or $assetManifest.runId -cne $runId -or
       $assetManifest.count -ne 236 -or $assetManifest.bytes -ne 44863059 -or @($assetManifest.files).Count -ne 236){throw 'TEST-08 asset manifest mismatch'}
    $seen=@{};$total=[int64]0
    foreach($row in @($assetManifest.files)){
        if($row.path -isnot [string] -or $row.path -notmatch '^[a-z0-9][a-z0-9._/-]+$' -or $seen.ContainsKey($row.path) -or
           ($row.bytes -isnot [int] -and $row.bytes -isnot [long]) -or
           $row.bytes -le 0 -or $row.bytes -gt 1MB -or
           $row.sha256 -isnot [string] -or $row.sha256 -cnotmatch '^[a-f0-9]{64}$'){throw 'TEST-08 asset row rejected'}
        $seen[$row.path]=$true;$total+=$row.bytes
        $path=[IO.Path]::GetFullPath((Join-Path $assetRoot $row.path.Replace('/',[IO.Path]::DirectorySeparatorChar)))
        if(!$path.StartsWith($assetRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'TEST-08 asset path escaped'}
        $item=Get-Item -Force -LiteralPath $path
        if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -ne $row.bytes -or
           (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $row.sha256){throw 'TEST-08 staged asset mismatch'}
    }
    if($seen.Count -ne 236 -or $total -ne 44863059){throw 'TEST-08 staged asset totals mismatch'}
    $routeMap=[IO.Path]::GetFullPath((Join-Path $repo 'docs/analytics-route-map.csv'))
    $routeItem=Get-Item -Force -LiteralPath $routeMap
    if($routeItem.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 route map link rejected'}
    $routeHash=(Get-FileHash -LiteralPath $routeMap -Algorithm SHA256).Hash.ToLowerInvariant()
    $routeTargets=@((Import-Csv -LiteralPath $routeMap).requested_path|Sort-Object)
    if($routeTargets.Count -ne 115 -or @($routeTargets|Sort-Object -Unique).Count -ne 115){throw 'TEST-08 route set rejected'}
    $routeSetJson=ConvertTo-Json -Compress -InputObject @($routeTargets)
    $routeSetHash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
        [Text.Encoding]::UTF8.GetBytes($routeSetJson))).ToLowerInvariant()
    $inputManifestHash=(Get-FileHash -LiteralPath $assetManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $mediaEvidence=[IO.Path]::GetFullPath((Join-Path $repo 'docs/analytics-media-evidence.csv'))
    $mediaEvidenceItem=Get-Item -Force -LiteralPath $mediaEvidence
    if($mediaEvidenceItem.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 media evidence link rejected'}
    $mediaEvidenceHash=(Get-FileHash -LiteralPath $mediaEvidence -Algorithm SHA256).Hash.ToLowerInvariant()
    if($mediaEvidenceHash -cne '52823a26c535f6bcbb45601fccad630278d59d421ab5f87b25bb1390d28867ca'){throw 'TEST-08 media evidence hash mismatch'}
    $test08Args=@('--mount',"type=bind,source=$assetRoot,target=/test08-source,readonly",
        '--mount',"type=bind,source=$routeMap,target=/test08-route-map.csv,readonly",
        '--mount',"type=bind,source=$mediaEvidence,target=/test08-media-evidence.csv,readonly",
        '--env','ESTAKADA_TEST08_SOURCE_ROOT=/test08-source','--env','ESTAKADA_TEST08_ROUTE_MAP=/test08-route-map.csv',
        '--env','ESTAKADA_TEST08_MEDIA_EVIDENCE=/test08-media-evidence.csv',
        '--env',"ESTAKADA_TEST08_RUN_ID=$runId",'--env',"ESTAKADA_TEST08_ROUTE_SHA256=$routeHash",
        '--env',"ESTAKADA_TEST08_INPUT_MANIFEST_SHA256=$inputManifestHash",
        '--env',"ESTAKADA_TEST08_SOURCE_MANIFEST_SHA256=$($manifest.sourceSha256)")
    if($Suite -eq 'local-admin-demo'){
        $demoLogo=[IO.Path]::GetFullPath((Join-Path $repo 'media/source-site/assets/1c7de03c1bd80ebbde8258aca12b3d4ac68bf699085fd8a7923c4b880f41af8a.png'))
        $demoLogoItem=Get-Item -Force -LiteralPath $demoLogo
        if($demoLogoItem.PSIsContainer -or ($demoLogoItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
           $demoLogoItem.Length -ne 30190 -or
           (Get-FileHash -LiteralPath $demoLogo -Algorithm SHA256).Hash.ToLowerInvariant() -cne '39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5'){
            throw 'Local admin demo logo mismatch'
        }
        $test08Args+=@('--mount',"type=bind,source=$demoLogo,target=/local-demo-logo.png,readonly",
            '--env','ESTAKADA_LOCAL_DEMO_LOGO_TEST=/local-demo-logo.png')
    }
    $resultRoot=[IO.Path]::GetFullPath((Join-Path $root 'test08-results'))
    $expectedResultRoot=[IO.Path]::GetFullPath((Join-Path $root 'test08-results'))
    if($resultRoot -cne $expectedResultRoot){throw 'TEST-08 result root mismatch'}
    if(Test-Path -LiteralPath $resultRoot){
        if((Get-Item -Force -LiteralPath $resultRoot).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 result root link rejected'}
    }else{
        New-Item -ItemType Directory -Path $resultRoot|Out-Null
        if((Get-Item -Force -LiteralPath $resultRoot).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 result root link rejected'}
    }
    if($Suite -ne 'local-preview-export'){
        $receiptName=if($Suite -eq 'test08-execution'){"$runId-execution.json"}else{"$runId.json"}
        $test08Receipt=[IO.Path]::GetFullPath((Join-Path $resultRoot $receiptName))
        if(!$test08Receipt.StartsWith($resultRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'TEST-08 receipt path escaped'}
        if(Test-Path -LiteralPath $test08Receipt){throw 'TEST-08 receipt already exists'}
    }
    if($Suite -eq 'test08-execution'){
        $reserveParent=[IO.Path]::GetFullPath((Join-Path $root 'test08-reserve'))
        if(Test-Path -LiteralPath $reserveParent){
            if((Get-Item -Force -LiteralPath $reserveParent).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 reserve parent link rejected'}
        }else{New-Item -ItemType Directory -Path $reserveParent|Out-Null}
        $test08Reserve=[IO.Path]::GetFullPath((Join-Path $reserveParent $runId))
        if(!$test08Reserve.StartsWith($reserveParent+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'TEST-08 reserve path escaped'}
        if(Test-Path -LiteralPath $test08Reserve){throw 'TEST-08 reserve already exists'}
        $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($test08Reserve))
        if($drive.AvailableFreeSpace -lt 1GB){throw 'TEST-08 reserve free-space gate failed'}
        New-Item -ItemType Directory -Path $test08Reserve|Out-Null
        if((Get-Item -Force -LiteralPath $test08Reserve).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 reserve link rejected'}
        $test08Args+=@('--mount',"type=bind,source=$test08Reserve,target=/test08-reserve",
            '--env','ESTAKADA_TEST08_RESERVE_ROOT=/test08-reserve/root')
    }elseif($Suite -eq 'local-preview-export'){
        $localPreviewRoot=[IO.Path]::GetFullPath((Join-Path $repo 'work/local-preview'))
        $localPreviewRuns=[IO.Path]::GetFullPath((Join-Path $localPreviewRoot 'runs'))
        foreach($path in @($localPreviewRoot,$localPreviewRuns)){
            if(Test-Path -LiteralPath $path){
                if((Get-Item -Force -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Local preview parent link rejected'}
            }else{New-Item -ItemType Directory -Path $path|Out-Null}
        }
        $runInventory=@(Get-ChildItem -Force -LiteralPath $localPreviewRuns)
        if(@($runInventory|Where-Object{!$_.PSIsContainer}).Count){throw 'Local preview runs inventory rejected'}
        $runDirectories=@($runInventory)
        $inventoryBytes=[int64]0
        foreach($directory in $runDirectories){
            $parsed=[guid]::Empty
            if(![guid]::TryParseExact($directory.Name,'D',[ref]$parsed) -or $parsed.ToString() -cne $directory.Name -or
               ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Local preview run inventory rejected'}
            $children=@(Get-ChildItem -Force -LiteralPath $directory.FullName -Recurse)
            if(@($children|Where-Object{$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'Local preview inventory link rejected'}
            $measured=@($children|Where-Object{!$_.PSIsContainer}|Measure-Object -Property Length -Sum)[0]
            if($null -ne $measured.Sum){$inventoryBytes+=[int64]$measured.Sum}
        }
        if($runDirectories.Count -ge 3 -or $inventoryBytes + 256MB -gt 768MB){throw 'Local preview inventory cap reached; owner cleanup required'}
        $previewRunId=[guid]::NewGuid().ToString()
        $localPreviewRun=[IO.Path]::GetFullPath((Join-Path $localPreviewRuns $previewRunId))
        if(([IO.DirectoryInfo]$localPreviewRun).Parent.FullName -cne ([IO.DirectoryInfo]$localPreviewRuns).FullName -or (Test-Path -LiteralPath $localPreviewRun)){throw 'Local preview run path rejected'}
        $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($localPreviewRun))
        if($drive.AvailableFreeSpace -lt 1GB){throw 'Local preview free-space gate failed'}
        New-Item -ItemType Directory -Path $localPreviewRun|Out-Null
        if((Get-Item -Force -LiteralPath $localPreviewRun).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Local preview run link rejected'}
        $test08Args+=@('--mount',"type=bind,source=$localPreviewRun,target=/local-preview-export",
            '--env','ESTAKADA_LOCAL_PREVIEW_ROOT=/local-preview-export',
            '--env',"ESTAKADA_LOCAL_PREVIEW_RUN_ID=$previewRunId")
    }
}
$private=Join-Path $root 'private'
$testMemory=if($Suite -in @('test08-execution','local-preview-export','local-admin-demo')){'1536m'}else{'768m'}
$dockerArgs=@('run','--rm','--name',"nestakada-editor-tests-$Suite",'--network','nestakada-foundation-test-db',
    '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','10001:10001',
    '--memory',$testMemory,'--memory-swap',$testMemory,'--cpus','1','--pids-limit','128',
    '--tmpfs','/tmp:rw,noexec,nosuid,size=128m','--mount',"type=bind,source=$source,target=/app,readonly",
    '--mount',"type=bind,source=$private\migrator-password,target=/run/secrets/database-password,readonly",
    '--mount',"type=bind,source=$private\django-secret,target=/run/secrets/django-secret,readonly",
    '--mount',"type=bind,source=$private\database-ca,target=/run/secrets/database-ca,readonly",
    '--mount','type=volume,source=nestakada-foundation-test-media-exchange,target=/exchange',
    '--workdir','/app','--env','DJANGO_SETTINGS_MODULE=estakada.settings.local_http',
    '--env','ESTAKADA_LOCAL_ENV=test','--env','ESTAKADA_DB_NAME=estakada_foundation_unit',
    '--env','ESTAKADA_DB_USER=app_migrator','--env','PYTHONDONTWRITEBYTECODE=1') + $quotaArgs + $guardArgs + $test08Args + @(
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
elseif($Suite -eq 'dev09-services'){$dockerArgs+=@('content.test_dev09e_services_catalog','content.test_dev09m_combined_services','content.test_dev09n_remaining_content','--failfast')}
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
elseif($Suite -eq 'test10-fixture'){$dockerArgs+=@('page_editor.test_test10_fixture','--failfast')}
elseif($Suite -eq 'test08-fixture'){$dockerArgs+=@('content.test_test08_fixture','--failfast')}
elseif($Suite -eq 'test08-execution'){$dockerArgs+=@('content.test_test08_execution','--failfast')}
elseif($Suite -eq 'local-preview-export'){$dockerArgs+=@('content.test_local_preview_export','--failfast')}
elseif($Suite -eq 'local-admin-demo'){$dockerArgs+=@(
    'content.test_local_admin_demo',
    'shared_content.test_shared_http.SharedHttpTests.test_header_social_cardinality_allows_only_zero_or_three',
    'shared_content.test_shared_public.SharedPublicTests.test_pub000_header_binding_count_allows_brand_only_or_brand_plus_three',
    '--failfast')}
elseif($Suite -eq 'auth-login'){$dockerArgs+=@(
    'accounts.tests.AccountTests.test_both_roles_login_identity_logout_and_private_headers',
    'accounts.tests.AccountTests.test_local_login_prefills_owner_and_normalizes_outer_username_whitespace',
    'accounts.tests.AccountTests.test_local_owner_recovery_is_interactive_hides_password_and_revokes_sessions',
    '--failfast')}
elseif($Suite -eq 'admin-workshop'){$dockerArgs+=@(
    'accounts.test_admin_workshop.AdminWorkshopTests.test_admw_001_anonymous_login_shell_and_no_password_value',
    'accounts.test_admin_workshop.AdminWorkshopTests.test_admw_002_logo_transport_and_exact_bytes',
    'accounts.test_admin_workshop.AdminWorkshopTests.test_admw_003_owner_navigation_and_dashboard_contract',
    'accounts.test_admin_workshop.AdminWorkshopTests.test_admw_004_employee_navigation_and_editor_contract',
    'accounts.test_admin_workshop.AdminWorkshopTests.test_admw_005_representative_screen_and_form_hook_inventory',
    'accounts.test_admin_workshop.AdminWorkshopTests.test_admw_006_css_scope_and_source_manifest_admission',
    '--failfast')}
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
if($Suite -eq 'test08-fixture'){
    $receipt=$null;$cleanup=$null;$primary=$null
    try{
        $previousErrorAction=$ErrorActionPreference
        try{
            $ErrorActionPreference='Continue'
            $rawOutput=@(& docker.exe @dockerArgs 2>&1);$exitCode=$LASTEXITCODE
        }finally{$ErrorActionPreference=$previousErrorAction}
        $output=@($rawOutput|ForEach-Object{"$_"})
        $output|ForEach-Object{Write-Output $_}
        if($exitCode -ne 0){throw 'Editor check failed; inspect evidence before any retry'}
        $markers=@($output|Where-Object{$_ -is [string] -and $_.StartsWith('TEST08_FIXTURE_RESULT=')})
        if($markers.Count -ne 1 -or $markers[0].Length -gt 16384){throw 'TEST-08 result marker missing or invalid'}
        $encoded=$markers[0].Substring('TEST08_FIXTURE_RESULT='.Length).Replace('-','+').Replace('_','/')
        while($encoded.Length%4){$encoded+='='}
        try{$json=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded));$receipt=$json|ConvertFrom-Json}catch{throw 'TEST-08 result marker decode failed'}
        $keys=@($receipt.PSObject.Properties.Name|Sort-Object)
        $countKeys='assets,auditEvents,fileKeyReservations,files,grants,identityReservations,mediaFolders,mediaIdentityReservations,ownerDrafts,pages,pageStates,profiles,requests,revisionMetadata,revisionProtections,revisions,routes,sessions,sharedBlocks,sharedBudgets,sharedIdentityReservations,sharedRevisions,usages,users,versionBasePins'
        $afterKeys=@($receipt.after.PSObject.Properties.Name|Sort-Object)-join ','
        $assembledKeys=@($receipt.assembled.PSObject.Properties.Name|Sort-Object)-join ','
        $beforeKeys=@($receipt.before.PSObject.Properties.Name|Sort-Object)-join ','
        $defaultKeys=@($receipt.defaultOff.PSObject.Properties.Name|Sort-Object)-join ','
        $mediaKeys=@($receipt.media.PSObject.Properties.Name|Sort-Object)-join ','
        if(($keys -join ',') -cne 'after,assembled,before,defaultOff,fixtureReady,inputManifestSha256,media,routeMapSha256,routeSetSha256,runId,schema,sourceManifestSha256' -or
           $afterKeys -cne $countKeys -or $assembledKeys -cne $countKeys -or $beforeKeys -cne $countKeys -or
           $defaultKeys -cne 'serviceRequestIntake,serviceRequestRows,transportProfile' -or $mediaKeys -cne 'bytes,count' -or
           $receipt.schema -cne 'test08-fixture-result-v1' -or $receipt.runId -cne $manifest.runId -or $receipt.fixtureReady -ne $true -or
           $receipt.inputManifestSha256 -cne $inputManifestHash -or $receipt.routeMapSha256 -cne $routeHash -or
           $receipt.routeSetSha256 -cne $routeSetHash -or $receipt.sourceManifestSha256 -cne $manifest.sourceSha256 -or
           $receipt.media.count -ne 237 -or $receipt.media.bytes -ne 45064743 -or
           $receipt.assembled.assets -ne 237 -or $receipt.assembled.files -ne 237 -or
           $receipt.assembled.pages -ne 112 -or $receipt.assembled.routes -ne 114 -or
           $receipt.assembled.requests -ne 0 -or $receipt.defaultOff.serviceRequestIntake -ne $false -or
           $receipt.defaultOff.serviceRequestRows -ne 0 -or $receipt.defaultOff.transportProfile -cne 'disabled' -or
           @($receipt.before.PSObject.Properties|Where-Object{$_.Value -ne 0}).Count -ne 0 -or
           @($receipt.after.PSObject.Properties|Where-Object{$_.Value -ne 0}).Count -ne 0){throw 'TEST-08 result marker schema mismatch'}
    }catch{$primary=$_;throw}
    finally{
        $cleanupOutput=@(& (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File (Join-Path $PSScriptRoot 'prepare-test08-fixture-assets.ps1') -Action Cleanup 2>&1)
        $cleanupExit=$LASTEXITCODE
        if($cleanupExit -eq 0 -and @($cleanupOutput|Where-Object{"$_" -eq "TEST08 fixture staging cleaned: $runId"}).Count -eq 1){
            $cleanup=[ordered]@{runId=$runId;status='removed'}
        }elseif($primary){$primary.Exception.Data['TEST08_CLEANUP']='failed'}
        else{throw 'TEST-08 staging cleanup failed'}
    }
    $receipt|Add-Member -NotePropertyName cleanup -NotePropertyValue $cleanup
    $finalJson=$receipt|ConvertTo-Json -Depth 8 -Compress
    $utf8=New-Object Text.UTF8Encoding($false);[IO.File]::WriteAllText($test08Receipt,$finalJson,$utf8)
}elseif($Suite -eq 'test08-execution'){
    $receipt=$null;$cleanup=$null;$primary=$null
    try{
        $previousErrorAction=$ErrorActionPreference
        try{
            $ErrorActionPreference='Continue'
            $rawOutput=@(& docker.exe @dockerArgs 2>&1);$exitCode=$LASTEXITCODE
        }finally{$ErrorActionPreference=$previousErrorAction}
        $output=@($rawOutput|ForEach-Object{"$_"})
        $output|ForEach-Object{Write-Output $_}
        if($exitCode -ne 0){throw 'Editor check failed; inspect evidence before any retry'}
        $markers=@($output|Where-Object{$_ -is [string] -and $_.StartsWith('TEST08_EXECUTION_RESULT=')})
        if($markers.Count -ne 1 -or $markers[0].Length -gt 32800){throw 'TEST-08 execution marker missing or invalid'}
        $encoded=$markers[0].Substring('TEST08_EXECUTION_RESULT='.Length).Replace('-','+').Replace('_','/')
        while($encoded.Length%4){$encoded+='='}
        try{$json=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded));$receipt=$json|ConvertFrom-Json}catch{throw 'TEST-08 execution marker decode failed'}
        $keys=@($receipt.PSObject.Properties.Name|Sort-Object)-join ','
        $countKeys='assets,auditEvents,fileKeyReservations,files,grants,identityReservations,mediaFolders,mediaIdentityReservations,ownerDrafts,pages,pageStates,profiles,requests,revisionMetadata,revisionProtections,revisions,routes,sessions,sharedBlocks,sharedBudgets,sharedIdentityReservations,sharedRevisions,usages,users,versionBasePins'
        $beforeKeys=@($receipt.fixtureBefore.PSObject.Properties.Name|Sort-Object)-join ','
        $assembledKeys=@($receipt.fixtureAssembled.PSObject.Properties.Name|Sort-Object)-join ','
        $afterKeys=@($receipt.fixtureAfter.PSObject.Properties.Name|Sort-Object)-join ','
        if($keys -cne 'allPassed,externalDelivery,fixtureAfter,fixtureAssembled,fixtureBefore,groups,inputManifestSha256,mediaAfter,mediaBefore,reserve,routeMapSha256,routeSetSha256,runId,schema,sourceManifestSha256' -or
           $receipt.schema -cne 'test08-execution-result-v1' -or $receipt.runId -cne $manifest.runId -or
           $receipt.inputManifestSha256 -cne $inputManifestHash -or $receipt.routeMapSha256 -cne $routeHash -or
           $receipt.routeSetSha256 -cne $routeSetHash -or $receipt.sourceManifestSha256 -cne $manifest.sourceSha256 -or
           $receipt.allPassed -ne $true -or $receipt.externalDelivery -ne 0 -or
           $beforeKeys -cne $countKeys -or $assembledKeys -cne $countKeys -or $afterKeys -cne $countKeys -or
           @($receipt.fixtureBefore.PSObject.Properties|Where-Object{$_.Value -ne 0}).Count -ne 0 -or
           @($receipt.fixtureAfter.PSObject.Properties|Where-Object{$_.Value -ne 0}).Count -ne 0 -or
           $receipt.fixtureAssembled.assets -ne 237 -or $receipt.fixtureAssembled.files -ne 237 -or
           $receipt.fixtureAssembled.pages -ne 112 -or $receipt.fixtureAssembled.routes -ne 114 -or
           $receipt.mediaBefore.count -ne 237 -or $receipt.mediaBefore.bytes -ne 45064743 -or
           $receipt.mediaAfter.count -ne 237 -or $receipt.mediaAfter.bytes -ne 45064743 -or
           $receipt.reserve.generations -ne 2 -or @($receipt.reserve.totals).Count -ne 2 -or
           $receipt.reserve.hostPeakBytes -lt 1 -or $receipt.reserve.hostPeakBytes -gt 544MB -or
           @($receipt.groups).Count -ne 10){throw 'TEST-08 execution result schema mismatch'}
        $expectedGroups=1..10|ForEach-Object{'T08-G{0:d2}' -f $_}
        for($index=0;$index -lt 10;$index++){
            $group=$receipt.groups[$index]
            $groupKeys=@($group.PSObject.Properties.Name|Sort-Object)-join ','
            if($groupKeys -cne 'actors,actual,after,before,expected,fixtureRunId,groupId,paths,projectionSha256,scenarioIds,status' -or
               $group.groupId -cne $expectedGroups[$index] -or $group.fixtureRunId -cne $runId -or
               $group.status -cne 'PASS' -or @($group.scenarioIds).Count -lt 3 -or
               @($group.actors|Where-Object{$_ -cnotin @('anonymous','owner','employee','system')}).Count -ne 0 -or
               $group.paths.count -lt 1 -or $group.paths.sha256 -cnotmatch '^[a-f0-9]{64}$' -or
               $group.before.sha256 -cnotmatch '^[a-f0-9]{64}$' -or $group.after.sha256 -cnotmatch '^[a-f0-9]{64}$' -or
               $group.projectionSha256 -cnotmatch '^[a-f0-9]{64}$' -or
               (ConvertTo-Json $group.expected -Depth 8 -Compress) -cne (ConvertTo-Json $group.actual -Depth 8 -Compress)){
                throw 'TEST-08 execution group schema mismatch'
            }
        }
        foreach($total in @($receipt.reserve.totals)){
            if($total.files -lt 1 -or $total.bytes -lt 1 -or $total.bytes -gt 256MB){throw 'TEST-08 reserve total rejected'}
        }
    }catch{$primary=$_;throw}
    finally{
        $stagingOutput=@(& (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File (Join-Path $PSScriptRoot 'prepare-test08-fixture-assets.ps1') -Action Cleanup 2>&1)
        $stagingExit=$LASTEXITCODE
        $reserveRemoved=$false
        try{
            if($test08Reserve -and (Test-Path -LiteralPath $test08Reserve)){
                if(!$test08Reserve.StartsWith($reserveParent+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
                   (Get-Item -Force -LiteralPath $test08Reserve).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'TEST-08 reserve cleanup scope rejected'}
                $links=@(Get-ChildItem -Force -LiteralPath $test08Reserve -Recurse|Where-Object{$_.Attributes -band [IO.FileAttributes]::ReparsePoint})
                if($links.Count){throw 'TEST-08 reserve child link rejected'}
                Remove-Item -LiteralPath $test08Reserve -Recurse -Force
            }
            $reserveRemoved=!(Test-Path -LiteralPath $test08Reserve)
        }catch{if($primary){$primary.Exception.Data['TEST08_RESERVE_CLEANUP']='failed'}else{throw}}
        if($stagingExit -eq 0 -and @($stagingOutput|Where-Object{"$_" -eq "TEST08 fixture staging cleaned: $runId"}).Count -eq 1 -and $reserveRemoved){
            $cleanup=[ordered]@{runId=$runId;staging='removed';reserve='removed'}
        }elseif($primary){$primary.Exception.Data['TEST08_CLEANUP']='failed'}
        else{throw 'TEST-08 execution cleanup failed'}
    }
    $receipt|Add-Member -NotePropertyName cleanup -NotePropertyValue $cleanup
    $finalJson=$receipt|ConvertTo-Json -Depth 10 -Compress
    $utf8=New-Object Text.UTF8Encoding($false);[IO.File]::WriteAllText($test08Receipt,$finalJson,$utf8)
}elseif($Suite -eq 'local-preview-export'){
    $receipt=$null;$primary=$null;$promoted=$false;$stagingCleaned=$false;$tempPath=$null
    function Test-LocalPreviewCandidateTree([string]$Path,[string]$ExpectedRun){
        try{
            $resolved=[IO.Path]::GetFullPath($Path)
            if(([IO.DirectoryInfo]$resolved).Parent.FullName -cne ([IO.DirectoryInfo]$localPreviewRuns).FullName -or
               ([IO.DirectoryInfo]$resolved).Name -cne $ExpectedRun){return $false}
            $rootItem=Get-Item -Force -LiteralPath $resolved
            if(!$rootItem.PSIsContainer -or ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)){return $false}
            foreach($item in @(Get-ChildItem -Force -LiteralPath $resolved -Recurse)){
                if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){return $false}
                $relative=$item.FullName.Substring($resolved.Length+1).Replace('\','/')
                if($item.PSIsContainer){
                    if($relative -notmatch '^(reserve|reserve/(staging|generations)|reserve/(staging|generations)/[0-9a-f-]{36}|reserve/(staging|generations)/[0-9a-f-]{36}/(responses|resources))$'){return $false}
                }else{
                    if($relative -notmatch '^(preview-index-v1\.json|receipt\.json|reserve/(active\.json|build\.lock|active\.[0-9a-f-]{36}\.tmp)|reserve/(staging|generations)/[0-9a-f-]{36}/manifest\.json|reserve/(staging|generations)/[0-9a-f-]{36}/responses/[a-f0-9]{64}\.html|reserve/(staging|generations)/[0-9a-f-]{36}/resources/[a-f0-9]{64}\.(css|js|webp|jpg|png))$'){return $false}
                }
            }
            return $true
        }catch{return $false}
    }
    try{
        $previousErrorAction=$ErrorActionPreference
        try{
            $ErrorActionPreference='Continue'
            $rawOutput=@(& docker.exe @dockerArgs 2>&1);$exitCode=$LASTEXITCODE
        }finally{$ErrorActionPreference=$previousErrorAction}
        $output=@($rawOutput|ForEach-Object{"$_"})
        $output|ForEach-Object{Write-Output $_}
        if($exitCode -ne 0){throw 'Local preview export test failed; inspect evidence before any retry'}
        $markers=@($output|Where-Object{$_ -is [string] -and $_.StartsWith('LOCAL_PREVIEW_EXPORT_RESULT=')})
        if($markers.Count -ne 1 -or $markers[0].Length -gt 32800){throw 'Local preview result marker missing or invalid'}
        $encoded=$markers[0].Substring('LOCAL_PREVIEW_EXPORT_RESULT='.Length).Replace('-','+').Replace('_','/')
        while($encoded.Length%4){$encoded+='='}
        try{$json=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded));$receipt=$json|ConvertFrom-Json}catch{throw 'Local preview result marker decode failed'}
        $keys=@($receipt.PSObject.Properties.Name|Sort-Object)-join ','
        $countKeys='assets,auditEvents,fileKeyReservations,files,grants,identityReservations,mediaFolders,mediaIdentityReservations,ownerDrafts,pages,pageStates,profiles,requests,revisionMetadata,revisionProtections,revisions,routes,sessions,sharedBlocks,sharedBudgets,sharedIdentityReservations,sharedRevisions,usages,users,versionBasePins'
        if($keys -cne 'externalDelivery,fixtureAfter,fixtureAssembled,fixtureBefore,generation,indexSha256,reserveManifestSha256,resources,responses,runId,schema,totals' -or
           $receipt.schema -cne 'local-preview-export-result-v1' -or $receipt.runId -cne $previewRunId -or
           $receipt.generation -cnotmatch '^[0-9a-f-]{36}$' -or $receipt.indexSha256 -cnotmatch '^[a-f0-9]{64}$' -or
           $receipt.reserveManifestSha256 -cnotmatch '^[a-f0-9]{64}$' -or $receipt.responses -ne 139 -or
           $receipt.resources -lt 1 -or $receipt.responses+$receipt.resources -gt 4096 -or
           $receipt.totals.files -ne $receipt.responses+$receipt.resources -or $receipt.totals.bytes -lt 1 -or $receipt.totals.bytes -gt 256MB -or
           $receipt.externalDelivery -ne 0 -or
           (@($receipt.fixtureBefore.PSObject.Properties.Name|Sort-Object)-join ',') -cne $countKeys -or
           (@($receipt.fixtureAfter.PSObject.Properties.Name|Sort-Object)-join ',') -cne $countKeys -or
           @($receipt.fixtureBefore.PSObject.Properties|Where-Object{$_.Value -ne 0}).Count -ne 0 -or
           @($receipt.fixtureAfter.PSObject.Properties|Where-Object{$_.Value -ne 0}).Count -ne 0 -or
           $receipt.fixtureAssembled.assets -ne 237 -or $receipt.fixtureAssembled.files -ne 237 -or
           $receipt.fixtureAssembled.pages -ne 112 -or $receipt.fixtureAssembled.routes -ne 114 -or
           $receipt.fixtureAssembled.requests -ne 0){throw 'Local preview result schema mismatch'}
        if(!(Test-LocalPreviewCandidateTree $localPreviewRun $previewRunId)){throw 'Local preview candidate tree rejected'}
        $indexPath=Join-Path $localPreviewRun 'preview-index-v1.json'
        if((Get-FileHash -LiteralPath $indexPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $receipt.indexSha256){throw 'Local preview index hash mismatch'}
        $hostReceipt=[ordered]@{
            indexSha256=$receipt.indexSha256
            reserveManifestSha256=$receipt.reserveManifestSha256
            resources=[int]$receipt.resources
            responses=[int]$receipt.responses
            runId=$previewRunId
            schema='local-preview-host-receipt-v1'
            totals=[ordered]@{bytes=[int64]$receipt.totals.bytes;files=[int]$receipt.totals.files}
        }
        $receiptPath=Join-Path $localPreviewRun 'receipt.json'
        if(Test-Path -LiteralPath $receiptPath){throw 'Local preview host receipt already exists'}
        $utf8=New-Object Text.UTF8Encoding($false)
        [IO.File]::WriteAllText($receiptPath,($hostReceipt|ConvertTo-Json -Depth 4 -Compress),$utf8)
        if(!(Test-LocalPreviewCandidateTree $localPreviewRun $previewRunId)){throw 'Local preview candidate tree changed'}
        $candidateFiles=@(Get-ChildItem -Force -LiteralPath $localPreviewRun -Recurse|Where-Object{!$_.PSIsContainer})
        $candidateMeasure=@($candidateFiles|Measure-Object -Property Length -Sum)[0]
        $candidateBytes=if($null -eq $candidateMeasure.Sum){[int64]0}else{[int64]$candidateMeasure.Sum}
        if($candidateBytes -gt 256MB -or $inventoryBytes + $candidateBytes -gt 768MB){throw 'Local preview candidate cap reached; owner cleanup required'}
        $previewPython=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        $previewServer=Join-Path $PSScriptRoot 'serve-local-preview.py'
        if(!(Test-Path -LiteralPath $previewPython) -or (Get-Item -Force -LiteralPath $previewServer).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Local preview smoke runtime unavailable'}
        $smokeOutput=@(& $previewPython -B $previewServer --root $localPreviewRun --smoke 2>&1)
        if($LASTEXITCODE -ne 0 -or @($smokeOutput|Where-Object{"$_" -eq "LOCAL_PREVIEW_SMOKE_PASS run=$previewRunId"}).Count -ne 1){$smokeOutput|ForEach-Object{Write-Output $_};throw 'Local preview HTTP smoke failed'}
        $checkOutput=@(& $previewPython -B $previewServer --root $localPreviewRun --check 2>&1)
        if($LASTEXITCODE -ne 0 -or @($checkOutput|Where-Object{"$_" -like "LOCAL_PREVIEW_VALID run=$previewRunId receipt=*"}).Count -ne 1){$checkOutput|ForEach-Object{Write-Output $_};throw 'Local preview final validation failed'}
        if(!(Test-LocalPreviewCandidateTree $localPreviewRun $previewRunId)){throw 'Local preview final tree rejected'}
        $stagingOutput=@(& (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File (Join-Path $PSScriptRoot 'prepare-test08-fixture-assets.ps1') -Action Cleanup 2>&1)
        $stagingExit=$LASTEXITCODE
        if($stagingExit -ne 0 -or @($stagingOutput|Where-Object{"$_" -eq "TEST08 fixture staging cleaned: $runId"}).Count -ne 1){throw 'Local preview staging cleanup failed'}
        $stagingCleaned=$true
        if(!(Test-LocalPreviewCandidateTree $localPreviewRun $previewRunId)){throw 'Local preview post-cleanup tree rejected'}
        $receiptSha=(Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $current=[ordered]@{indexSha256=$receipt.indexSha256;receiptSha256=$receiptSha;runId=$previewRunId;schema='local-preview-current-v1'}
        $currentPath=Join-Path $localPreviewRoot 'current.json'
        $tempPath=Join-Path $localPreviewRoot "current.$previewRunId.tmp"
        if(Test-Path -LiteralPath $tempPath){throw 'Local preview current temp already exists'}
        if((Test-Path -LiteralPath $currentPath) -and (Get-Item -Force -LiteralPath $currentPath).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Local preview current link rejected'}
        [IO.File]::WriteAllText($tempPath,($current|ConvertTo-Json -Compress),$utf8)
        [IO.File]::Move($tempPath,$currentPath,$true)
        $promoted=$true
        Write-Output "LOCAL_PREVIEW_EXPORT_PASS run=$previewRunId path=$localPreviewRun"
    }catch{$primary=$_;throw}
    finally{
        if(!$stagingCleaned){
            $stagingOutput=@(& (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File (Join-Path $PSScriptRoot 'prepare-test08-fixture-assets.ps1') -Action Cleanup 2>&1)
            $stagingExit=$LASTEXITCODE
            if($stagingExit -ne 0 -or @($stagingOutput|Where-Object{"$_" -eq "TEST08 fixture staging cleaned: $runId"}).Count -ne 1){
                if($primary){$primary.Exception.Data['LOCAL_PREVIEW_STAGING_CLEANUP']='failed'}else{throw 'Local preview staging cleanup failed'}
            }else{$stagingCleaned=$true}
        }
        if(!$promoted -and $tempPath -and (Test-Path -LiteralPath $tempPath)){
            try{
                $expectedTemp=[IO.Path]::GetFullPath((Join-Path $localPreviewRoot "current.$previewRunId.tmp"))
                if([IO.Path]::GetFullPath($tempPath) -cne $expectedTemp -or
                   (Get-Item -Force -LiteralPath $tempPath).PSIsContainer -or
                   (Get-Item -Force -LiteralPath $tempPath).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Local preview current temp cleanup scope rejected'}
                Remove-Item -LiteralPath $tempPath -Force
            }catch{if($primary){$primary.Exception.Data['LOCAL_PREVIEW_TEMP_CLEANUP']='failed'}else{throw}}
        }
        if(!$promoted -and $localPreviewRun -and (Test-Path -LiteralPath $localPreviewRun)){
            try{
                $remaining=@(docker.exe ps -aq --filter 'name=nestakada-editor-tests-local-preview-export')
                if($LASTEXITCODE -ne 0 -or $remaining.Count -ne 0){throw 'Local preview container unmount not proved'}
                if(!(Test-LocalPreviewCandidateTree $localPreviewRun $previewRunId)){throw 'Local preview failure tree ambiguous'}
                Remove-Item -LiteralPath $localPreviewRun -Recurse -Force
            }catch{if($primary){$primary.Exception.Data['LOCAL_PREVIEW_RUN_CLEANUP']='preserved'}else{throw}}
        }
    }
}elseif($Suite -eq 'local-admin-demo'){
    $primary=$null
    try{
        & docker.exe @dockerArgs
        if($LASTEXITCODE -ne 0){throw 'Local admin demo tests failed; inspect evidence before any retry'}
    }catch{$primary=$_;throw}
    finally{
        $cleanupOutput=@(& (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File (Join-Path $PSScriptRoot 'prepare-test08-fixture-assets.ps1') -Action Cleanup 2>&1)
        $cleanupExit=$LASTEXITCODE
        if($cleanupExit -ne 0 -or @($cleanupOutput|Where-Object{"$_" -eq "TEST08 fixture staging cleaned: $runId"}).Count -ne 1){
            if($primary){$primary.Exception.Data['LOCAL_ADMIN_DEMO_STAGING_CLEANUP']='failed'}else{throw 'Local admin demo staging cleanup failed'}
        }
    }
}else{
    & docker.exe @dockerArgs
    if($LASTEXITCODE -ne 0){throw 'Editor check failed; inspect evidence before any retry'}
}
