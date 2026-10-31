$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
& node (Join-Path $repo 'tools/collect-foundation-evidence.mjs')
if ($LASTEXITCODE -ne 0) { throw 'Foundation collection failed; acceptance was not started.' }
$guardSha256 = (Get-FileHash -LiteralPath (Join-Path $repo 'work/foundation/test/evidence/guard.json') -Algorithm SHA256).Hash.ToLowerInvariant()
$previous = $env:ESTAKADA_TEST_BASE_URL
try {
    & node (Join-Path $repo 'tools/collect-foundation-evidence.mjs') --verify $guardSha256
    if ($LASTEXITCODE -ne 0) { throw 'Foundation evidence changed before acceptance.' }
    $env:ESTAKADA_TEST_BASE_URL = 'http://host.docker.internal:8767'
    & (Join-Path $repo 'acceptance/run-container.ps1') -Mode foundation-security
    if ($LASTEXITCODE -ne 0) { throw 'Foundation acceptance failed.' }
} finally {
    $env:ESTAKADA_TEST_BASE_URL = $previous
    # Always verify the original snapshot; do not recollect after the suite.
    & node (Join-Path $repo 'tools/collect-foundation-evidence.mjs') --verify $guardSha256
    if ($LASTEXITCODE -ne 0) { throw 'Foundation evidence drift invalidated this acceptance run.' }
}
