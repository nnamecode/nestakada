# D-327: real history/version HTTP/UI only against the already started exclusive local test profile.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$node = (Get-Command node -ErrorAction Stop).Source
# No install/build/up/reset/fallback. The host coordinator verifies source/images and QA provenance.
& $node (Join-Path $repo 'tools/test-version-http.mjs')
if ($LASTEXITCODE -ne 0) { throw 'DEV-05 version HTTP checks failed. Inspect the safe report; no automatic retry.' }
