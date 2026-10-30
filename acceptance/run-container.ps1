param(
    [ValidateSet('harness', 'documents', 'driver-safety', 'public-http', 'public-contracts', 'application-contracts', 'form-contracts', 'form-windows', 'shared-blocks', 'backup-contracts', 'html-build', 'content-lifecycle', 'fallback-contracts', 'media-contracts', 'logging-contracts', 'request-lifecycle', 'seo-contracts', 'list')][string]$Mode = 'harness'
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
                    'form-window-contracts.spec.js', 'shared-block-contracts.spec.js', 'backup-contracts.spec.js', 'html-build-contracts.spec.js')) {
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
$image = 'mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea'
$network = 'none'
if ($Mode -in @('public-http', 'public-contracts', 'application-contracts', 'form-contracts', 'form-windows', 'shared-blocks', 'backup-contracts', 'html-build', 'content-lifecycle', 'fallback-contracts', 'media-contracts', 'logging-contracts', 'request-lifecycle', 'seo-contracts') -and $env:ESTAKADA_TEST_BASE_URL) { $network = 'bridge' }
$playwrightArgs = switch ($Mode) {
    'harness' { '--project=harness --project=driver-safety --project=harness-chromium --project=harness-firefox --project=harness-webkit --max-failures=1' }
    'driver-safety' { '--project=driver-safety --max-failures=1' }
    'documents' { '--project=harness --max-failures=1' }
    'public-http' { '--project=public-http' }
    'public-contracts' { '--project=public-http --project=public-contracts' }
    'application-contracts' { '--project=application-contracts --max-failures=1' }
    'form-contracts' { '--project=form-contracts --max-failures=1' }
    'form-windows' { '--project=form-windows --max-failures=1' }
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
# Preparation may fetch registry metadata; package scripts are disabled. It never runs site tests.
& docker @dockerArgs --network bridge $image /bin/sh -c $installCommand
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Browser harness/list/red-without-target runs with network=none. Public HTTP is local-only in JS.
& docker @dockerArgs --network $network $image /bin/sh -c $testCommand
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
