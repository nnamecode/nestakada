param(
    [string]$BaseArchive = "deliverables/estakada-static-site-new-explicit-links-2026-10-29.zip",
    [string]$OutputDirectory = "deliverables/estakada-static-site-new-2026-10-29-v3",
    [string]$OutputArchive = "deliverables/estakada-static-site-new-2026-10-29-v3.zip"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$baseArchivePath = Join-Path $repoRoot $BaseArchive
$outputPath = Join-Path $repoRoot $OutputDirectory
$archivePath = Join-Path $repoRoot $OutputArchive

if (-not (Test-Path -LiteralPath $baseArchivePath -PathType Leaf)) {
    throw "Base archive not found: $baseArchivePath"
}
if (Test-Path -LiteralPath $outputPath) {
    throw "Output directory already exists; choose a new path: $outputPath"
}
if (Test-Path -LiteralPath $archivePath) {
    throw "Output archive already exists; choose a new path: $archivePath"
}

New-Item -ItemType Directory -Path $outputPath | Out-Null
& tar.exe -xf $baseArchivePath -C $outputPath
if ($LASTEXITCODE -ne 0) { throw "tar.exe extraction failed with exit code $LASTEXITCODE" }

$homepageSource = Join-Path $repoRoot "work/public-light-v4.html"
$homepageTarget = Join-Path $outputPath "index.html"
Copy-Item -LiteralPath $homepageSource -Destination $homepageTarget -Force

$carWashSource = Join-Path $repoRoot "work/avtomojka.html"
$carWashTarget = Join-Path $outputPath "services/avtomojka/index.html"
New-Item -ItemType Directory -Path (Split-Path -Parent $carWashTarget) -Force | Out-Null
Copy-Item -LiteralPath $carWashSource -Destination $carWashTarget -Force

$galleryTarget = Join-Path $outputPath "gallery-of-works/index.html"
$galleryContent = [System.IO.File]::ReadAllText($galleryTarget)
$galleryHook = "    document.querySelectorAll('.album-card').forEach((card) => card.addEventListener('click', () => openAlbum(Number(card.dataset.album))));"
$galleryQuerySupport = @"
$galleryHook
    const requestedAlbum = Number(new URLSearchParams(window.location.search).get('album'));
    if (Number.isInteger(requestedAlbum) && requestedAlbum >= 0 && requestedAlbum < galleryAlbums.length) {
      openAlbum(requestedAlbum);
    }
"@
if (-not $galleryContent.Contains($galleryHook)) {
    throw "Gallery album hook not found in base archive"
}
$galleryContent = $galleryContent.Replace($galleryHook, $galleryQuerySupport.TrimEnd())
[System.IO.File]::WriteAllText($galleryTarget, $galleryContent, [System.Text.UTF8Encoding]::new($false))

$designSource = Join-Path $repoRoot "media/design-concepts"
$mediaRoot = Join-Path $outputPath "media"
$designTarget = Join-Path $mediaRoot "design-concepts"
if (Test-Path -LiteralPath $designTarget) {
    $resolvedOutput = (Resolve-Path -LiteralPath $outputPath).Path.TrimEnd('\')
    $resolvedTarget = (Resolve-Path -LiteralPath $designTarget).Path
    if (-not $resolvedTarget.StartsWith($resolvedOutput + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace media outside output directory: $resolvedTarget"
    }
    Remove-Item -LiteralPath $designTarget -Recurse -Force
}
Copy-Item -LiteralPath $designSource -Destination $designTarget -Recurse

$routeMap = @{}
Get-ChildItem -LiteralPath $outputPath -Recurse -File -Filter "index.html" | ForEach-Object {
    $relative = $_.FullName.Substring($outputPath.Length).TrimStart('\').Replace('\', '/')
    if ($relative -eq "index.html") {
        $routeMap[""] = "/new/index.html"
    } else {
        $route = $relative.Substring(0, $relative.Length - "/index.html".Length).Trim('/')
        $routeMap[$route] = "/new/$route/index.html"
    }
}
$routeMap['services/drugie-uslugi/avtomojka'] = '/new/services/avtomojka/index.html'

$internalUrlPattern = 'https://estakada-service\.ru/(?<path>[^"''<>\s?#]*)(?<suffix>[?#][^"''<>\s]*)?'
$htmlFiles = Get-ChildItem -LiteralPath $outputPath -Recurse -File -Filter "*.html"
foreach ($file in $htmlFiles) {
    $content = [System.IO.File]::ReadAllText($file.FullName)
    $content = $content.Replace('../../media/', '/new/media/').Replace('../media/', '/new/media/')
    $content = $content.Replace('href="avtomojka.html"', 'href="/new/services/avtomojka/index.html"').Replace('data-href="avtomojka.html"', 'data-href="/new/services/avtomojka/index.html"')
    $content = [regex]::Replace($content, 'href="gallery-of-works\.html\?album=(?<album>\d+)"', 'href="/new/gallery-of-works/index.html?album=${album}"')
    $content = [regex]::Replace($content, $internalUrlPattern, {
        param($match)
        $route = $match.Groups['path'].Value.Trim('/')
        $suffix = $match.Groups['suffix'].Value
        if ($routeMap.ContainsKey($route)) {
            return $routeMap[$route] + $suffix
        }
        return $match.Value
    })
    $content = [regex]::Replace($content, '/new/media/design-concepts/(?<asset>[^"''<>\s?)]+)\.png', {
        param($match)
        $asset = $match.Groups['asset'].Value
        $candidate = Join-Path $designTarget (($asset + '.webp').Replace('/', '\'))
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return "/new/media/design-concepts/$asset.webp"
        }
        return $match.Value
    })
    [System.IO.File]::WriteAllText($file.FullName, $content, [System.Text.UTF8Encoding]::new($false))
}

$readme = @"
Статическая HTML-версия сайта для каталога /new/

1. Удалите старое содержимое каталога /new/ на хостинге.
2. Распакуйте СОДЕРЖИМОЕ этого архива непосредственно в /new/.
3. Главная должна открываться по адресу https://estakada-service.ru/new/index.html.
4. Внутренние ссылки явно ведут на /new/.../index.html и не требуют правил rewrite.
5. Проектные иллюстрации поставляются в WebP. Оригинальные фотографии галереи не перекодированы.

Сборка: 29 октября 2026 года.
"@
[System.IO.File]::WriteAllText((Join-Path $outputPath "README-DEPLOY.txt"), $readme, [System.Text.UTF8Encoding]::new($false))

$missing = New-Object System.Collections.Generic.List[string]
$oldDomainLinks = New-Object System.Collections.Generic.List[string]
$implicitNewLinks = New-Object System.Collections.Generic.List[string]
$internalReferenceCount = 0
foreach ($file in $htmlFiles) {
    $content = [System.IO.File]::ReadAllText($file.FullName)
    foreach ($match in [regex]::Matches($content, '(?:href|src)=["''](?<url>[^"'']+)["'']')) {
        $url = $match.Groups['url'].Value
        if ($url.StartsWith('https://estakada-service.ru/', [System.StringComparison]::OrdinalIgnoreCase)) {
            $oldDomainLinks.Add("$($file.FullName): $url")
        }
        if (-not $url.StartsWith('/new/')) { continue }
        $internalReferenceCount++
        $clean = ($url -split '[?#]', 2)[0]
        if ($clean.EndsWith('/') -and -not $clean.EndsWith('/media/')) {
            $implicitNewLinks.Add("$($file.FullName): $url")
        }
        $relative = $clean.Substring('/new/'.Length).Replace('/', '\')
        $target = Join-Path $outputPath $relative
        if (-not (Test-Path -LiteralPath $target)) {
            $missing.Add("$($file.FullName): $url")
        }
    }
}

$designPngCount = @(Get-ChildItem -LiteralPath $designTarget -Recurse -File -Filter "*.png").Count
$designWebpCount = @(Get-ChildItem -LiteralPath $designTarget -Recurse -File -Filter "*.webp").Count
if ($oldDomainLinks.Count -gt 0) {
    throw "Found $($oldDomainLinks.Count) links that still point to the old site. First: $($oldDomainLinks[0])"
}
if ($implicitNewLinks.Count -gt 0) {
    throw "Found $($implicitNewLinks.Count) implicit /new/ links. First: $($implicitNewLinks[0])"
}
if ($missing.Count -gt 0) {
    throw "Found $($missing.Count) missing /new/ targets. First: $($missing[0])"
}
if ($designPngCount -ne 0) {
    throw "Found $designPngCount PNG files in media/design-concepts"
}
if ($designWebpCount -eq 0) {
    throw "No WebP files found in media/design-concepts"
}

Push-Location $outputPath
try {
    & tar.exe -a -c -f $archivePath *
    if ($LASTEXITCODE -ne 0) { throw "tar.exe failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$archive = Get-Item -LiteralPath $archivePath
$hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
[pscustomobject]@{
    OutputDirectory = $outputPath
    OutputArchive = $archivePath
    ArchiveBytes = $archive.Length
    Sha256 = $hash
    HtmlFiles = $htmlFiles.Count
    InternalReferences = $internalReferenceCount
    MissingTargets = $missing.Count
    OldDomainLinks = $oldDomainLinks.Count
    ImplicitNewLinks = $implicitNewLinks.Count
    DesignPng = $designPngCount
    DesignWebp = $designWebpCount
}
