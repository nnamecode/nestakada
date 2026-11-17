# REBUILD-1 media baseline scope

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-SCOPE-001`.

## Цель и граница

Scope переиспользует существующие authority-файлы и не создаёт второй manifest/scanner/exporter:

- `app/content/dev10_gallery.json` — canonical gallery metadata package;
- `docs/analytics-media-evidence.csv` — reviewed media evidence и роли;
- `docs/media-inventory.csv` — исторический source index, не transfer manifest и не автоматический allowlist;
- всё дерево `media/` — архив/рабочие материалы; наличие файла там само по себе не разрешает перенос.

Читались только CSV/JSON и filesystem metadata существования/размера/reparse. Байты media-файлов не хэшировались заново, файлы не копировались и не изменялись. DB/media target, importer/exporter, Q002, product и live закрыты.

## Candidate allowlist

| Cohort | Files | Bytes | Основание |
|---|---:|---:|---|
| `gallery-original` | 214 | 41 176 391 | D-024 + canonical DEV-10 package |
| `new_design_asset` | 83 | 14 916 204 | D-025 reviewed evidence |
| `trusted_design_svg_not_user_upload` | 3 | 11 656 | trusted fixed design assets |
| existing `illustration-or-layout` | 1 | 30 190 | local reviewed evidence |
| **Итого candidate** | **301** | **56 134 441** | exact role allowlist; max file 656254 |

Все 301 candidate paths уникальны, существуют как regular non-reparse files и имеют размер, равный evidence. Это ещё не fresh byte/SHA baseline: новый hash pass отдельно gated.

## Gallery authority reconciliation

- `dev10-gallery-v1`: 17 albums, 214 photos, position base0, gaps0;
- gallery paths/source URLs/SHA-256 уникальны 214/214/214;
- CSV и DEV-10 package совпадают по всем 214 кортежам `local_file|source_url|bytes|sha256`;
- package: 187260 bytes, SHA-256 `9db5b026d6affa4668e2ca19268d8663355c1e22504f6aba6aa1676ed3d41b3b`;
- evidence CSV: 214707 bytes, SHA-256 `52823a26c535f6bcbb45601fccad630278d59d421ab5f87b25bb1390d28867ca`.

## Явные исключения

- 16 `unused_design_variant_or_source`, 3 318 200 bytes: рабочие/архивные варианты, не candidate transfer;
- `MED-ERR-001` и `MED-ERR-002`: historical HTTP404 rows без local file/bytes/SHA; выдуманный файл/hash запрещён;
- любые прочие файлы дерева `media/` вне exact301 allowlist не становятся transfer input по факту существования;
- source DB aggregate `AssetFile=238` и candidate filesystem301 описывают разные слои и не объявляются равными. Path/usage binding остаётся отдельной read-only reconciliation.

## Acceptance

- `RB1-MEDIA-SCOPE-AC-001`: authority ровно DEV-10 package + analytics evidence; второй manifest/scanner отсутствует.
- `RB1-MEDIA-SCOPE-AC-002`: gallery exact17/214/41176391, base0/gaps0, unique path/url/SHA214.
- `RB1-MEDIA-SCOPE-AC-003`: package↔CSV gallery tuple diff0; authority file bytes/SHA exact.
- `RB1-MEDIA-SCOPE-AC-004`: candidate exact301/56134441/max656254, paths unique301, missing0, size mismatch0, reparse0.
- `RB1-MEDIA-SCOPE-AC-005`: unused16/3318200 и error rows2 исключены; никакого headroom/guessing.
- `RB1-MEDIA-SCOPE-AC-006`: physical tree не allowlist; DB238 не приравнивается к files301 без binding evidence.
- `RB1-MEDIA-SCOPE-AC-007`: byte/SHA recheck, DB path/usage reconciliation, copy/import/target остаются отдельными gates.
- `RB1-MEDIA-SCOPE-AC-008`: no-bloat — новых runtime tool/service/manifest/registry/tracker нет.

Следующий gate: independent read-only review scope. Только после APPROVED и нового owner continuation допустим один bounded existing-file SHA pass exact301; постоянный scanner не нужен.
