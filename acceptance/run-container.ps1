param(
    [ValidateSet('harness', 'documents', 'driver-safety', 'public-http', 'public-contracts', 'application-contracts', 'form-contracts', 'form-windows', 'form-native', 'form-cache', 'home-source', 'shared-component-restore', 'url-reserve', 'url-reuse', 'url-transition', 'service-quota', 'version-storage', 'price-editor', 'price-home', 'shared-blocks', 'backup-contracts', 'html-build', 'content-lifecycle', 'fallback-contracts', 'media-contracts', 'logging-contracts', 'request-lifecycle', 'seo-contracts', 'editor-boundaries', 'editor-safety', 'rich-editor-native', 'price-editor-native', 'process-editor-native', 'links-editor-native', 'action-editor-native', 'version-time', 'auth-login', 'unsaved-editor', 'log-quota', 'background-jobs', 'restore-contracts', 'log-delete-failures', 'migration-contracts', 'migration-source', 'foundation-security', 'list')][string]$Mode = 'harness',
    [switch]$ListOnly
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$scratch = Join-Path $repo 'work\acceptance-container'
$richMode = $Mode -in @('rich-editor-native', 'price-editor-native', 'process-editor-native', 'links-editor-native', 'action-editor-native')
if ($ListOnly -and -not $richMode) { throw 'ListOnly is allowed only for native editor modes.' }
$richRoot = Join-Path $scratch $Mode
$package = if ($richMode) { Join-Path $richRoot 'acceptance' } else { Join-Path $scratch 'acceptance' }
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
if ($richMode) {
    $workRoot = Join-Path $repo 'work'
    foreach ($component in @(
        @{ Path = $workRoot; Parent = $repo },
        @{ Path = $scratch; Parent = $workRoot },
        @{ Path = $richRoot; Parent = $scratch }
    )) {
        if (Test-Path -LiteralPath $component.Path) {
            $componentItem = Get-Item -LiteralPath $component.Path -Force
            if (-not $componentItem.PSIsContainer -or
                ($componentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
                [IO.Path]::GetFullPath($componentItem.FullName) -ne [IO.Path]::GetFullPath($component.Path) -or
                [IO.Path]::GetFullPath([IO.Path]::GetDirectoryName($componentItem.FullName)) -ne [IO.Path]::GetFullPath($component.Parent)) {
                throw "Unsafe rich editor staging component: $($component.Path)"
            }
        }
    }
    $expectedRichRoot = [IO.Path]::GetFullPath((Join-Path $scratch $Mode))
    $actualRichRoot = [IO.Path]::GetFullPath($richRoot)
    if ($actualRichRoot -ne $expectedRichRoot -or [IO.Path]::GetDirectoryName($actualRichRoot) -ne [IO.Path]::GetFullPath($scratch)) {
        throw 'Rich editor staging path escaped the fixed scratch root.'
    }
    if (Test-Path -LiteralPath $actualRichRoot) {
        $richItem = Get-Item -LiteralPath $actualRichRoot -Force
        if (-not $richItem.PSIsContainer -or ($richItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Rich editor staging root must be a regular directory.'
        }
        Remove-Item -LiteralPath $actualRichRoot -Recurse -Force
    }
}
foreach ($directory in @($package, $results)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $store)) { throw 'Offline pnpm store missing; run the approved local install first.' }
if ($richMode) {
    $trustedInputs = @(
        @{ Name = 'package.json'; Sha256 = '4F67B18A01DEA58504AB72A98697514475423307D21BB5E42015DA14B6E2017B' },
        @{ Name = 'pnpm-lock.yaml'; Sha256 = '51E5ADEF0356129F1415DA50C4913064EA9435342F5DE6B7988FE40B2E7C1264' }
    )
    foreach ($trustedInput in $trustedInputs) {
        $sourcePath = Join-Path $PSScriptRoot $trustedInput.Name
        $sourceItem = Get-Item -LiteralPath $sourcePath -Force
        if ($sourceItem.PSIsContainer -or
            ($sourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash -cne $trustedInput.Sha256) {
            throw "Rich editor trusted input mismatch: $($trustedInput.Name)"
        }
    }
    $nativeSpec = switch ($Mode) {
        'price-editor-native' { 'price-editor-native.spec.js' }
        'process-editor-native' { 'process-editor-native.spec.js' }
        'links-editor-native' { 'links-editor-native.spec.js' }
        'action-editor-native' { 'action-editor-native.spec.js' }
        default { 'rich-editor-native.spec.js' }
    }
    foreach ($file in @('package.json', 'pnpm-lock.yaml', 'playwright.config.js', $nativeSpec)) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $package $file) -Force
    }
    foreach ($trustedInput in $trustedInputs) {
        $stagedPath = Join-Path $package $trustedInput.Name
        $stagedItem = Get-Item -LiteralPath $stagedPath -Force
        if ($stagedItem.PSIsContainer -or
            ($stagedItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            (Get-FileHash -LiteralPath $stagedPath -Algorithm SHA256).Hash -cne $trustedInput.Sha256) {
            throw "Rich editor staged trusted input mismatch: $($trustedInput.Name)"
        }
    }
} else {
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
    'rich-editor-native' {
        if ($ListOnly) { '--project=rich-editor-native --list' }
        else { '--project=rich-editor-native --max-failures=1' }
    }
    'price-editor-native' {
        if ($ListOnly) { '--project=price-editor-native --list' }
        else { '--project=price-editor-native --max-failures=1' }
    }
    'process-editor-native' {
        if ($ListOnly) { '--project=process-editor-native --list' }
        else { '--project=process-editor-native --max-failures=1' }
    }
    'links-editor-native' {
        if ($ListOnly) { '--project=links-editor-native --list' }
        else { '--project=links-editor-native --max-failures=1' }
    }
    'action-editor-native' {
        if ($ListOnly) { '--project=action-editor-native --list' }
        else { '--project=action-editor-native --max-failures=1' }
    }
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
$installCommand = if ($richMode) {
    'node --version && node /pnpm/bin/pnpm.mjs install --offline --frozen-lockfile --frozen-store --trust-lockfile --ignore-scripts --store-dir /store --config.package-import-method=copy --config.node-linker=hoisted'
} else {
    'node --version && node /pnpm/bin/pnpm.mjs install --prefer-offline --frozen-lockfile --ignore-scripts --store-dir /store --config.package-import-method=copy --config.node-linker=hoisted'
}
$testCommand = 'node node_modules/@playwright/test/cli.js test ' + $playwrightArgs
$dockerArgs = @('run', '--rm', '--init',
    '--memory=2g', '--cpus=2', '--pids-limit=256', '--shm-size=512m',
    '--cap-drop=ALL', '--security-opt=no-new-privileges')
if ($richMode) {
    $dockerArgs += @('--pull=never',
        '--mount', "type=bind,source=$package,target=/workspace/acceptance",
        '--mount', "type=bind,source=$pnpmPackage,target=/pnpm,readonly",
        '--mount', "type=bind,source=$store,target=/store,readonly",
        '--mount', "type=bind,source=$results,target=/workspace/test-results/acceptance")
} else {
    $dockerArgs += @('--mount', "type=bind,source=$scratch,target=/workspace",
        '--mount', "type=bind,source=$(Join-Path $repo 'docs'),target=/workspace/docs,readonly",
        '--mount', "type=bind,source=$pnpmPackage,target=/pnpm,readonly",
        '--mount', "type=bind,source=$store,target=/store",
        '--mount', "type=bind,source=$results,target=/workspace/test-results/acceptance")
}
$dockerArgs += @('--workdir', '/workspace/acceptance', '--env', 'CI=1',
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
# Rich mode is exact-image, offline and source-file-only; existing modes retain their preparation path.
$preparationNetwork = if ($richMode) { 'none' } else { 'bridge' }
if ($richMode) {
    & docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Pinned Playwright image is not present locally; pull is forbidden.' }
}
& docker @dockerArgs --network $preparationNetwork $image /bin/sh -c $installCommand
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Browser harness/list/red-without-target runs with network=none. Public HTTP is local-only in JS.
$richSourceMount = @()
if ($richMode) {
    $editorSource = Join-Path $repo 'src\modules\pages\static\pages\editor.js'
    $editorItem = Get-Item -LiteralPath $editorSource -Force
    if ($editorItem.PSIsContainer -or ($editorItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Rich editor source must be one regular file.'
    }
    $richSourceMount = @('--mount', "type=bind,source=$editorSource,target=/source/editor.js,readonly")
    if ($Mode -eq 'price-editor-native') {
        $priceSource = Join-Path $repo 'src\modules\pages\static\pages\price-editor.js'
        $priceItem = Get-Item -LiteralPath $priceSource -Force
        if ($priceItem.PSIsContainer -or ($priceItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Price editor source must be one regular file.'
        }
        $richSourceMount += @('--mount', "type=bind,source=$priceSource,target=/source/price-editor.js,readonly")
    }
    if ($Mode -eq 'process-editor-native') {
        $processSource = Join-Path $repo 'src\modules\pages\static\pages\process-steps-editor.js'
        $processItem = Get-Item -LiteralPath $processSource -Force
        if ($processItem.PSIsContainer -or ($processItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Process editor source must be one regular file.'
        }
        $richSourceMount += @('--mount', "type=bind,source=$processSource,target=/source/process-steps-editor.js,readonly")
    }
    if ($Mode -eq 'links-editor-native') {
        $linksSource = Join-Path $repo 'src\modules\pages\static\pages\partner-links-editor.js'
        $linksItem = Get-Item -LiteralPath $linksSource -Force
        if ($linksItem.PSIsContainer -or ($linksItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Partner links editor source must be one regular file.'
        }
        $richSourceMount += @('--mount', "type=bind,source=$linksSource,target=/source/partner-links-editor.js,readonly")
    }
    if ($Mode -eq 'action-editor-native') {
        $actionSource = Join-Path $repo 'src\modules\pages\static\pages\action-copy-editor.js'
        $actionItem = Get-Item -LiteralPath $actionSource -Force
        if ($actionItem.PSIsContainer -or ($actionItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Action copy editor source must be one regular file.'
        }
        $richSourceMount += @('--mount', "type=bind,source=$actionSource,target=/source/action-copy-editor.js,readonly")
    }
    & docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Pinned Playwright image disappeared before the test container.' }
}
if ($ListOnly) {
    $listOutputPath = Join-Path $richRoot 'list-output.txt'
    & docker @dockerArgs @migrationMount @foundationMount @authFixtureMount @richSourceMount --network $network $image /bin/sh -c $testCommand *> $listOutputPath
    $testExit = $LASTEXITCODE
    $listOutputItem = Get-Item -LiteralPath $listOutputPath -Force
    if ($listOutputItem.PSIsContainer -or
        ($listOutputItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        [IO.Path]::GetFullPath($listOutputItem.FullName) -ne [IO.Path]::GetFullPath($listOutputPath)) {
        throw 'Native editor list output is not the exact regular evidence file.'
    }
    if ($listOutputItem.Length -gt 65536) { throw 'Native editor list output exceeded the 64 KiB evidence bound.' }
    $testOutput = @(Get-Content -LiteralPath $listOutputPath)
    if ($testOutput.Count -gt 200) { throw 'Native editor list output exceeded the 200-line evidence bound.' }
    $testOutput | Write-Output
    if ($testExit -ne 0) { exit $testExit }
    $summaryLines = @($testOutput | ForEach-Object { ([string]$_).TrimEnd("`r") } |
        Where-Object { $_ -ceq 'Total: 8 tests in 1 file' })
    if ($summaryLines.Count -ne 1) { throw 'Native editor exact8 discovery summary mismatch.' }
} else {
    & docker @dockerArgs @migrationMount @foundationMount @authFixtureMount @richSourceMount --network $network $image /bin/sh -c $testCommand
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
