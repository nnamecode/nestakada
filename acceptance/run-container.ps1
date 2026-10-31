param(
    [ValidateSet('harness', 'documents', 'driver-safety', 'public-http', 'public-contracts', 'application-contracts', 'form-contracts', 'form-windows', 'form-native', 'form-cache', 'home-source', 'shared-component-restore', 'url-reserve', 'url-reuse', 'url-transition', 'service-quota', 'version-storage', 'price-editor', 'price-home', 'shared-blocks', 'backup-contracts', 'html-build', 'content-lifecycle', 'fallback-contracts', 'media-contracts', 'logging-contracts', 'request-lifecycle', 'seo-contracts', 'editor-boundaries', 'editor-safety', 'version-time', 'auth-login', 'unsaved-editor', 'log-quota', 'background-jobs', 'restore-contracts', 'log-delete-failures', 'migration-contracts', 'migration-source', 'foundation-security', 'list')][string]$Mode = 'harness'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$scratch = Join-Path $repo 'work\acceptance-container'
$package = Join-Path $scratch 'acceptance'
$store = Join-Path $repo 'work\pnpm-store'
$results = Join-Path $repo 'test-results\acceptance'
$pnpmPackage = $env:ESTAKADA_PNPM_PACKAGE
if (-not $pnpmPackage) {
    $pnpmPackage = 'C:\Users\nname\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\pnpm'
}
if (-not (Test-Path -LiteralPath (Join-Path $pnpmPackage 'bin\pnpm.mjs'))) {
    throw 'Set ESTAKADA_PNPM_PACKAGE to the approved pnpm 11.25.0 package directory; no automatic download.'
}
$pnpmVersion = (Get-Content -Raw -LiteralPath (Join-Path $pnpmPackage 'package.json') | ConvertFrom-Json).version
if ($pnpmVersion -ne '11.25.0') { throw "Unapproved pnpm version: $pnpmVersion" }
foreach ($directory in @($package, $results)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $store)) { throw 'Offline pnpm store missing; run the approved local install first.' }
foreach ($file in @('package.json', 'pnpm-lock.yaml', 'playwright.config.js', 'test-support.js',
                    'harness.spec.js', 'browser-harness.spec.js', 'public-http.spec.js',
                    'public-contracts.spec.js', 'html-metadata.js', 'application-driver-contract.js', 'application-contracts.spec.js', 'form-contracts.spec.js',
                    'isolated-application-driver.js', 'driver-safety.js', 'driver-safety.spec.js', 'fixture-transport-selfcheck.mjs', 'content-lifecycle.spec.js', 'fallback-contracts.spec.js',
                    'upload-support.js', 'response-safety.js', 'media-contracts.spec.js', 'logging-contracts.spec.js', 'request-lifecycle.spec.js', 'seo-contracts.spec.js',
                    'form-window-contracts.spec.js', 'form-native.spec.js', 'form-cache.spec.js', 'home-source.spec.js', 'shared-component-restore.spec.js', 'url-reserve.spec.js', 'url-reuse.spec.js', 'url-transition.spec.js', 'service-quota.spec.js', 'version-storage.spec.js', 'price-editor.spec.js', 'price-home.spec.js', 'shared-block-contracts.spec.js', 'backup-contracts.spec.js', 'html-build-contracts.spec.js', 'editor-boundaries.spec.js', 'editor-safety.spec.js', 'version-time.spec.js', 'auth-login.spec.js', 'unsaved-editor.spec.js', 'log-quota.spec.js', 'background-jobs.spec.js', 'restore-contracts.spec.js', 'log-delete-failures.spec.js', 'browser-memory.js', 'migration-contracts.spec.js', 'migration-source.js', 'migration-source.spec.js', 'foundation-security.spec.js')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $package $file) -Force
}
# Private local bindings are optional until the real isolated application exists.
# Copy fixed regular files only; remove stale copies after an owner removes a binding.
foreach ($file in @('local-bindings.json', 'local-fixture-bridge.mjs', 'local-fixture-settings.json')) {
    $sourceFile = Join-Path $PSScriptRoot $file
    $targetFile = Join-Path $package $file
    if (Test-Path -LiteralPath $sourceFile) {
        $item = Get-Item -LiteralPath $sourceFile
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Private adapter input must be a regular file: $file"
        }
        Copy-Item -LiteralPath $sourceFile -Destination $targetFile -Force
    } elseif (Test-Path -LiteralPath $targetFile) {
        Remove-Item -LiteralPath $targetFile -Force
    }
}
# Exact official image downloaded under D-303; no latest, production ports or Docker socket.
$foundationMount = @()
$authFixtureMount = @()
if ($Mode -eq 'auth-login') {
    $approvedAuthDirectory = Join-Path $repo 'work/foundation/test/auth/runner'
    if ($env:ESTAKADA_TEST_BASE_URL -ne 'http://host.docker.internal:8767' -or
        $env:ESTAKADA_AUTH_FIXTURE_DIRECTORY -ne $approvedAuthDirectory) { throw 'Auth tests require the fixed isolated fixture and origin.' }
    foreach ($inputPath in @($approvedAuthDirectory,(Join-Path $approvedAuthDirectory 'control.json'))) {
        if (!(Test-Path -LiteralPath $inputPath) -or ((Get-Item -LiteralPath $inputPath).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Auth fixture input must be regular and present.' }
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'auth-bindings.json') -Destination (Join-Path $package 'local-bindings.json') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'auth-fixture-bridge.mjs') -Destination (Join-Path $package 'local-fixture-bridge.mjs') -Force
    $authFixtureMount = @('--mount', "type=bind,source=$approvedAuthDirectory,target=/auth-fixture,readonly")
}
if ($Mode -eq 'foundation-security') {
    if ($env:ESTAKADA_TEST_BASE_URL -ne 'http://host.docker.internal:8767') { throw 'Foundation requires the fixed isolated test origin.' }
    $evidence = Join-Path $repo 'work/foundation/test/evidence'
    $evidenceFile = Join-Path $evidence 'current.json'
    if (!(Test-Path -LiteralPath $evidenceFile)) { throw 'Collect real foundation evidence before running acceptance.' }
    foreach ($inputPath in @($evidence, $evidenceFile)) {
        if ((Get-Item -LiteralPath $inputPath).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Foundation evidence cannot be a reparse point.' }
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'foundation-bindings.json') -Destination (Join-Path $package 'local-bindings.json') -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'foundation-fixture-bridge.mjs') -Destination (Join-Path $package 'local-fixture-bridge.mjs') -Force
    $foundationMount = @('--mount', "type=bind,source=$evidence,target=/foundation-evidence,readonly")
}
$image = 'mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea'
$network = 'none'
if ($Mode -in @('public-http', 'public-contracts', 'application-contracts', 'form-contracts', 'form-windows', 'form-native', 'form-cache', 'home-source', 'shared-component-restore', 'url-reserve', 'url-reuse', 'url-transition', 'service-quota', 'version-storage', 'price-editor', 'price-home', 'shared-blocks', 'backup-contracts', 'html-build', 'content-lifecycle', 'fallback-contracts', 'media-contracts', 'logging-contracts', 'request-lifecycle', 'seo-contracts', 'editor-boundaries', 'editor-safety', 'version-time', 'auth-login', 'unsaved-editor', 'log-quota', 'background-jobs', 'restore-contracts', 'log-delete-failures', 'migration-contracts', 'foundation-security') -and $env:ESTAKADA_TEST_BASE_URL) { $network = 'bridge' }
$playwrightArgs = switch ($Mode) {
    'harness' { '--project=harness --project=driver-safety --project=harness-chromium --project=harness-firefox --project=harness-webkit --max-failures=1' }
    'foundation-security' { '--project=foundation-security --max-failures=1' }
    'driver-safety' { '--project=driver-safety --max-failures=1' }
    'documents' { '--project=harness --max-failures=1' }
    'public-http' { '--project=public-http' }
    'public-contracts' { '--project=public-http --project=public-contracts' }
    'application-contracts' { '--project=application-contracts --max-failures=1' }
    'migration-source' { '--project=migration-source --max-failures=1' }
    'editor-safety' { '--project=editor-safety --max-failures=1' }
    'auth-login' { '--project=auth-login --max-failures=1' }
    'unsaved-editor' { '--project=unsaved-editor --max-failures=1' }
    'log-quota' { '--project=log-quota --max-failures=1' }
    'background-jobs' { '--project=background-jobs --max-failures=1' }
    'restore-contracts' { '--project=restore-contracts --max-failures=1' }
    'log-delete-failures' { '--project=log-delete-failures --max-failures=1' }
    'version-time' { '--project=version-time --max-failures=1' }
    'editor-boundaries' { '--project=editor-boundaries --max-failures=1' }
    'migration-contracts' { '--project=migration-contracts --max-failures=1' }
    'form-contracts' { '--project=form-contracts --max-failures=1' }
    'form-windows' { '--project=form-windows --max-failures=1' }
    'form-native' { '--project=form-native --max-failures=1' }
    'home-source' { '--project=home-source --max-failures=1' }
    'shared-component-restore' { '--project=shared-component-restore --max-failures=1' }
    'url-reserve' { '--project=url-reserve --max-failures=1' }
    'url-reuse' { '--project=url-reuse --max-failures=1' }
    'url-transition' { '--project=url-transition --max-failures=1' }
    'service-quota' { '--project=service-quota --max-failures=1' }
    'version-storage' { '--project=version-storage --max-failures=1' }
    'price-editor' { '--project=price-editor --max-failures=1' }
    'price-home' { '--project=price-home --max-failures=1' }
    'form-cache' { '--project=form-cache --max-failures=1' }
    'shared-blocks' { '--project=shared-blocks --max-failures=1' }
    'backup-contracts' { '--project=backup-contracts --max-failures=1' }
    'html-build' { '--project=html-build --max-failures=1' }
    'content-lifecycle' { '--project=content-lifecycle --max-failures=1' }
    'fallback-contracts' { '--project=fallback-contracts --max-failures=1' }
    'media-contracts' { '--project=media-contracts --max-failures=1' }
    'logging-contracts' { '--project=logging-contracts --max-failures=1' }
    'request-lifecycle' { '--project=request-lifecycle --max-failures=1' }
    'seo-contracts' { '--project=seo-contracts --max-failures=1' }
    'list' { '--list' }
}
$installCommand = 'node --version && node /pnpm/bin/pnpm.mjs install --prefer-offline --frozen-lockfile --ignore-scripts --store-dir /store --config.package-import-method=copy --config.node-linker=hoisted'
$testCommand = 'node node_modules/@playwright/test/cli.js test ' + $playwrightArgs
$dockerArgs = @('run', '--rm', '--init',
    '--memory=2g', '--cpus=2', '--pids-limit=256', '--shm-size=512m',
    '--cap-drop=ALL', '--security-opt=no-new-privileges',
    '--mount', "type=bind,source=$scratch,target=/workspace",
    '--mount', "type=bind,source=$(Join-Path $repo 'docs'),target=/workspace/docs,readonly",
    '--mount', "type=bind,source=$pnpmPackage,target=/pnpm,readonly",
    '--mount', "type=bind,source=$store,target=/store",
    '--mount', "type=bind,source=$results,target=/workspace/test-results/acceptance",
    '--workdir', '/workspace/acceptance', '--env', 'CI=1',
    '--env', "ESTAKADA_TEST_REPORT=$Mode",
    '--env', 'XDG_CACHE_HOME=/tmp/cache', '--env', 'XDG_DATA_HOME=/tmp/data')
if ($env:ESTAKADA_TEST_BASE_URL) {
    $dockerArgs += @('--env', "ESTAKADA_TEST_BASE_URL=$env:ESTAKADA_TEST_BASE_URL")
}
$migrationMount = @()
if ($Mode -in @('migration-contracts', 'migration-source')) {
    # Only selected public snapshots; never mount the full audit/media directory.
    $sourceStage = Join-Path $repo ('work\acceptance-migration-source\' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $sourceStage -Force | Out-Null
    $sourceIds = @('MAP-003','MAP-009','MAP-033','MAP-039','MAP-044','MAP-045','MAP-049','MAP-078',
                   'MAP-090','MAP-097','MAP-013','MAP-038','MAP-073','MAP-015','MAP-032','MAP-088')
    $sourceRows = @(Import-Csv -LiteralPath (Join-Path $repo 'docs\analytics-route-map.csv') | Where-Object map_id -In $sourceIds)
    if ($sourceRows.Count -ne $sourceIds.Count) { throw 'Migration source selection is incomplete.' }
    foreach ($sourceRow in $sourceRows) {
        if ($sourceRow.source_snapshot -notmatch '^work/site-audit/crawl/[a-f0-9]{20}\.html$') { throw 'Invalid migration source path.' }
        $sourcePath = Join-Path $repo $sourceRow.source_snapshot
        $sourceItem = Get-Item -LiteralPath $sourcePath
        if ($sourceItem.PSIsContainer -or ($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Migration source must be a regular file.' }
        if ((Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceRow.source_sha256) { throw "Migration source hash mismatch: $($sourceRow.map_id)" }
        $stagedPath = Join-Path $sourceStage $sourceItem.Name
        Copy-Item -LiteralPath $sourcePath -Destination $stagedPath -Force
        if ((Get-FileHash -LiteralPath $stagedPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceRow.source_sha256) { throw 'Migration source staging hash mismatch.' }
    }
    $migrationMount = @('--mount', "type=bind,source=$sourceStage,target=/workspace/acceptance/local-migration-source,readonly")
}
# Preparation may fetch registry metadata; package scripts are disabled. It never runs site tests.
& docker @dockerArgs --network bridge $image /bin/sh -c $installCommand
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Browser harness/list/red-without-target runs with network=none. Public HTTP is local-only in JS.
& docker @dockerArgs @migrationMount @foundationMount @authFixtureMount --network $network $image /bin/sh -c $testCommand
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
