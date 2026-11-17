# REBUILD-1 exact301 media SHA result

Дата: 2026-11-17. Evidence ID: `RB1-MEDIA-HASH-001`.

Owner после D-1311 разрешил один bounded read-only SHA pass по exact301 allowlist из `docs/analytics-media-evidence.csv`. Использован одноразовый PowerShell/.NET SHA-256 pass без нового файла, scanner, manifest или зависимости.

Result envelope:

| Поле | Результат |
|---|---:|
| contract | `rb1-media-hash-v1` |
| status | `PASS` |
| files | 301 |
| bytes | 56 134 441 |
| gallery files / bytes | 214 / 41 176 391 |
| ordinary files / bytes | 87 / 14 958 050 |
| size/SHA mismatches | 0 |
| elapsed | 3504 ms |

Каждый exact relative path повторно прошёл containment/regular/non-reparse checks, был открыт read-only, а фактические bytes и SHA-256 сравнены с существующим evidence. Per-file path/hash и media bytes в output не выводились. Файлы не копировались и не изменялись.

Этот PASS закрывает fresh byte/SHA recheck exact301, но не DB AssetFile238 path/usage binding, manifest freeze, exporter/importer, target DB/media, WBS, Q002, product или live.

Следующий gate: независимое read-only result review. Повторный SHA pass не нужен.

## Exact historical execution appendix

Ниже дословно зафиксирован одноразовый PowerShell scriptblock, которым получен result. Это evidence text, а не подключённый tool/scanner. Canonical digest считается от UTF-8/LF текста внутри fence без завершающего перевода строки: lines35, bytes2410, SHA-256 `2b66f9dde15e37f10536613c8b5118cde5366e168d4f9f914533de37a10e446a`.

```powershell
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath('T:\nestakada')
$root=$repo+[IO.Path]::DirectorySeparatorChar
$roles=@('gallery-original','new_design_asset','trusted_design_svg_not_user_upload','illustration-or-layout')
$rows=@(Import-Csv (Join-Path $repo 'docs/analytics-media-evidence.csv') | Where-Object { $_.role -in $roles -and $_.local_exists -eq 'true' -and $_.archive_status -ne 'error_http404' })
if($rows.Count -ne 301){throw 'MEDIA_HASH_SCOPE_COUNT'}
if((@($rows.media_path|Sort-Object -Unique)).Count -ne 301){throw 'MEDIA_HASH_SCOPE_DUPLICATE'}
$watch=[Diagnostics.Stopwatch]::StartNew()
$mismatch=0
$totalBytes=[int64]0
$galleryFiles=0
$galleryBytes=[int64]0
$sha=[Security.Cryptography.SHA256]::Create()
try {
  foreach($row in $rows){
    if($row.media_path -notmatch '^media/[A-Za-z0-9._/-]+$' -or $row.media_path -match '(^|/)\.\.(/|$)'){throw 'MEDIA_HASH_PATH_REJECTED'}
    $full=[IO.Path]::GetFullPath((Join-Path $repo ($row.media_path -replace '/','\')))
    if(!$full.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)){throw 'MEDIA_HASH_PATH_ESCAPE'}
    $item=Get-Item -Force -LiteralPath $full
    if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'MEDIA_HASH_FILE_REJECTED'}
    $stream=[IO.FileStream]::new($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
      $actualBytes=$stream.Length
      $actualHash=[Convert]::ToHexString($sha.ComputeHash($stream)).ToLowerInvariant()
    } finally { $stream.Dispose() }
    if($actualBytes -ne [int64]$row.bytes -or $actualHash -cne $row.sha256){$mismatch++}
    $totalBytes += $actualBytes
    if($row.role -eq 'gallery-original'){$galleryFiles++;$galleryBytes += $actualBytes}
  }
} finally {$sha.Dispose();$watch.Stop()}
$ordinaryFiles=$rows.Count-$galleryFiles
$ordinaryBytes=$totalBytes-$galleryBytes
$status=if($mismatch -eq 0 -and $totalBytes -eq 56134441 -and $galleryFiles -eq 214 -and $galleryBytes -eq 41176391 -and $ordinaryFiles -eq 87 -and $ordinaryBytes -eq 14958050){'PASS'}else{'FAIL'}
[ordered]@{contract='rb1-media-hash-v1';status=$status;files=$rows.Count;bytes=$totalBytes;galleryFiles=$galleryFiles;galleryBytes=$galleryBytes;ordinaryFiles=$ordinaryFiles;ordinaryBytes=$ordinaryBytes;mismatches=$mismatch;elapsedMs=[int][Math]::Ceiling($watch.Elapsed.TotalMilliseconds)}|ConvertTo-Json -Compress
if($status -ne 'PASS'){exit 1}
```

Observed stdout был ровно одной строкой:

```json
{"contract":"rb1-media-hash-v1","status":"PASS","files":301,"bytes":56134441,"galleryFiles":214,"galleryBytes":41176391,"ordinaryFiles":87,"ordinaryBytes":14958050,"mismatches":0,"elapsedMs":3504}
```

Ошибочная ветка не исполнялась; appendix не заявляет наблюдавшийся failure output. Успешный stdout не содержит per-file path/hash, raw bytes или exception text.
