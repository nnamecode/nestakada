# D-326: real HTTP/browser checks only against the already started exclusive local test profile.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$node = (Get-Command node -ErrorAction Stop).Source
# No install/build/up/reset/fallback. The coordinator verifies the immutable foundation guard.
& $node (Join-Path $repo 'tools/test-media-http.mjs')
if ($LASTEXITCODE -ne 0) { throw 'DEV-06 media HTTP checks failed. Inspect the safe report; no automatic retry.' }
