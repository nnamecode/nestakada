[CmdletBinding()]
param([ValidateSet('Prepare','Cleanup','Status')][string]$Action = 'Status')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$foundation = Join-Path $repo 'work/foundation/test'
$foundationManifestPath = Join-Path $foundation 'manifest.json'
if (!(Test-Path -LiteralPath $foundationManifestPath)) { throw 'Active test foundation required.' }
$foundationManifest = Get-Content -Raw -LiteralPath $foundationManifestPath | ConvertFrom-Json
if (!$foundationManifest.active -or $foundationManifest.environment -ne 'test' -or
    $foundationManifest.composeProject -ne 'nestakada-foundation-test') {
    throw 'Exclusive active test foundation required.'
}
$runId = [guid]::Parse([string]$foundationManifest.runId).ToString()
if ($runId -cne $foundationManifest.runId) { throw 'Canonical foundation run UUID required.' }
$stagingParent = [IO.Path]::GetFullPath((Join-Path $foundation 'test08-fixture'))
$staging = [IO.Path]::GetFullPath((Join-Path $stagingParent $runId))
$source = Join-Path $staging 'source'
$manifestPath = Join-Path $staging 'manifest.json'

function Reject-Link([string]$Path) {
    $item = Get-Item -Force -LiteralPath $Path
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Reparse point rejected: $Path"
    }
}
function Assert-StagingPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (!$full.StartsWith($stagingParent + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase) -or
        $full -ne $staging) { throw 'Fixture staging scope mismatch.' }
}
function Remove-Staging {
    Assert-StagingPath $staging
    if (Test-Path -LiteralPath $staging) {
        Reject-Link $staging
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}

if ($Action -eq 'Cleanup') {
    Remove-Staging
    Write-Output "TEST08 fixture staging cleaned: $runId"
    exit 0
}
if ($Action -eq 'Status') {
    [pscustomobject]@{
        runId = $runId
        prepared = (Test-Path -LiteralPath $manifestPath)
        staging = $staging
    } | ConvertTo-Json
    exit 0
}
if (Test-Path -LiteralPath $staging) { throw 'Fixture staging already exists; Cleanup first.' }

$packages = [ordered]@{
    gallery = Join-Path $repo 'app/content/dev10_gallery.json'
    home = Join-Path $repo 'app/content/dev12_home_profile.json'
    remaining = Join-Path $repo 'app/content/dev09n_remaining_content.json'
    combined = Join-Path $repo 'app/content/dev09m_infographic_map019.json'
}
foreach ($path in $packages.Values) { Reject-Link $path }
$gallery = Get-Content -Raw -LiteralPath $packages.gallery | ConvertFrom-Json
$homePackage = Get-Content -Raw -LiteralPath $packages.home | ConvertFrom-Json
$remaining = Get-Content -Raw -LiteralPath $packages.remaining | ConvertFrom-Json
$combined = Get-Content -Raw -LiteralPath $packages.combined | ConvertFrom-Json

$rows = New-Object Collections.Generic.List[object]
foreach ($album in @($gallery.albums)) {
    foreach ($photo in @($album.photos)) {
        $rows.Add([pscustomobject]@{category='gallery';path=$photo.local_file;bytes=$photo.bytes;sha256=$photo.sha256})
    }
}
foreach ($row in @($homePackage.media)) {
    $rows.Add([pscustomobject]@{category='home';path=$row.local_file;bytes=$row.bytes;sha256=$row.sha256})
}
foreach ($row in @($remaining.media)) {
    $rows.Add([pscustomobject]@{category='remaining';path=$row.relative_path;bytes=$row.bytes;sha256=$row.sha256})
}
$rows.Add([pscustomobject]@{category='combined';path=$combined.media.relative_path;bytes=$combined.media.bytes;sha256=$combined.media.sha256})

$expectedCounts = @{gallery=214;home=15;remaining=7;combined=1}
foreach ($category in $expectedCounts.Keys) {
    if (@($rows | Where-Object category -eq $category).Count -ne $expectedCounts[$category]) {
        throw "Unexpected $category fixture file count."
    }
}
$ordered = @($rows | Sort-Object path)
$groups = @($ordered | Group-Object path)
$duplicate = @($groups | Where-Object Count -gt 1)
$logicalTotal = [int64](($ordered | Measure-Object bytes -Sum).Sum)
if ($ordered.Count -ne 237 -or $groups.Count -ne 236 -or $duplicate.Count -ne 1 -or
    $duplicate[0].Name -cne 'media/design-concepts/photo-strip-v4/exterior-bays-bright-v1.webp' -or
    $duplicate[0].Count -ne 2 -or
    (@($duplicate[0].Group.category | Sort-Object) -join ',') -cne 'home,remaining' -or
    @($duplicate[0].Group | Select-Object bytes,sha256 -Unique).Count -ne 1 -or
    $duplicate[0].Group[0].bytes -ne 201684 -or
    $duplicate[0].Group[0].sha256 -cne '640bc75001fede5e3c29c85ca2629af2263770da5014339edc0e5def9d83d43f' -or
    $logicalTotal -ne 45064743) {
    throw 'Fixture logical237/source236 overlap mismatch.'
}
$uniqueRows = @($groups | ForEach-Object { $_.Group[0] } | Sort-Object path)
$total = [int64](($uniqueRows | Measure-Object bytes -Sum).Sum)
if ($total -ne 44863059 -or $total -gt 64MB) { throw 'Fixture source byte budget mismatch.' }

try {
    New-Item -ItemType Directory -Force -Path $source | Out-Null
    Reject-Link $staging
    Reject-Link $source
    $manifestRows = New-Object Collections.Generic.List[object]
    foreach ($row in $uniqueRows) {
        if ($row.path -isnot [string] -or $row.path -notmatch '^[a-z0-9][a-z0-9._/-]+$' -or
            $row.path.StartsWith('/') -or $row.path.Contains('..') -or
            ($row.bytes -isnot [int] -and $row.bytes -isnot [long]) -or
            $row.bytes -le 0 -or $row.bytes -gt 1MB -or
            $row.sha256 -isnot [string] -or $row.sha256 -cnotmatch '^[a-f0-9]{64}$') {
            throw 'Fixture source descriptor rejected.'
        }
        $relative = $row.path.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $origin = [IO.Path]::GetFullPath((Join-Path $repo $relative))
        if (!$origin.StartsWith($repo + [IO.Path]::DirectorySeparatorChar,
                [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture source escaped repository.' }
        Reject-Link $origin
        $info = Get-Item -LiteralPath $origin
        if (!$info.PSIsContainer -and $info.Length -eq $row.bytes) {
            $hash = (Get-FileHash -LiteralPath $origin -Algorithm SHA256).Hash.ToLowerInvariant()
        } else { throw 'Fixture source type/size mismatch.' }
        if ($hash -cne $row.sha256) { throw 'Fixture source hash mismatch.' }
        $destination = [IO.Path]::GetFullPath((Join-Path $source $relative))
        if (!$destination.StartsWith($source + [IO.Path]::DirectorySeparatorChar,
                [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture destination escaped staging.' }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $origin -Destination $destination
        if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -cne $row.sha256) {
            throw 'Fixture staged copy hash mismatch.'
        }
        $manifestRows.Add([ordered]@{category=$row.category;path=$row.path;bytes=$row.bytes;sha256=$row.sha256})
    }
    $manifest = [ordered]@{
        schema='test08-fixture-assets-v1';runId=$runId;count=236;bytes=44863059
        files=@($manifestRows | ForEach-Object { $_ })
    }
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 5), $utf8)
    Write-Output "TEST08 fixture staging prepared: source236/44863059 logical237 run=$runId"
} catch {
    Remove-Staging
    throw
}
