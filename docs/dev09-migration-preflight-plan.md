# DEV-09A: offline preflight карты миграции без записи в БД

Дата: 2026-11-09
Основание: D-023–D-025, D-301, D-726, READY-04/MIG-01, TECH-07, AC-MIG-001–009.

## Цель и граница

Перед любым импортом доказать, что утверждённые локальные входы согласованы между собой: 115 MAP, 115 RTE и исходные HTML snapshot имеют точные идентификаторы, пути и SHA-256. Результат — bounded machine-readable preflight report с готовыми строками и явными блокерами. Скрипт host-only, read-only, не подключается к Django/PostgreSQL, сети, Docker API или production и не становится runtime-зависимостью сайта.

Текущая карта содержит 81 строку `design_basis_present_verify_migration_before_launch` и 34 строки с явными блокерами: 3 price resolution, 1 master catalog, 10 legacy designs, 17 standalone album designs, wash alias/canonical, gallery page=1 chain и page=2 subset. ANA-Q041/READY-04 также остаётся внешним условием полного DEV-09: публичный обход не доказывает все рекламные посадочные URL. DEV-09A ничего из этого не «закрывает» и не выполняет частичный импорт.

Используется существующий Node host-tooling репозитория и только встроенные `fs/path/crypto`; новый пакет, версия runtime, установка или конфигурация не добавляются. Python/Django остаются единственным runtime-стеком CMS.

## Приёмочные сценарии

- `MIGP-001`: CLI принимает только `--inventory` или `--selfcheck` и читает фиксированные repo-relative `docs/analytics-route-map.csv`, `docs/analytics-route-evidence.csv`, `work/site-audit/crawl`; произвольные входные пути отсутствуют.
- `MIGP-002`: RFC4180-compatible parser принимает текущие quoted comma/double-quote/UTF-8/CRLF поля и закрывает malformed quote, duplicate/unknown header, пустую или лишнюю колонку; exact header order зафиксирован для MAP и RTE.
- `MIGP-003`: требуется ровно115 строк, последовательные `MAP-001..MAP-115`, `RTE-001..RTE-115`, уникальные `map_id`, `evidence_id`, `requested_path` и exact one-to-one MAP↔RTE.
- `MIGP-004`: requested path — только внутренний absolute path без scheme/host/backslash/fragment/control; query допускается только у exact `/gallery-of-works/?page=1|2`. Observed path/status и новый MAP-115 не выдумываются: пустые observed-поля разрешены только MAP-115, остальные требуют status200.
- `MIGP-005`: `source_snapshot` после `resolve/realpath` остаётся внутри exact `work/site-audit/crawl`, является обычным файлом, не symlink/reparse; actual SHA-256 равен 64-lowercase `source_sha256`. Повторно используемый wash snapshot проверяется один раз по согласованному path+hash.
- `MIGP-006`: MAP и RTE обязаны совпасть по map/evidence ID, requested path, source snapshot/SHA, H1/facts/template state; расхождение закрывает весь preflight, частичного ready-result нет.
- `MIGP-007`: ready определяется только exact state `design_basis_present_verify_migration_before_launch`; остальные состояния не интерпретируются эвристикой и группируются как blockers. На текущем immutable наборе ожидаются total115, ready81, blocked34 и точные counts по семи blocker states.
- `MIGP-008`: stdout — один bounded JSON без source text/excerpts, HTML, media bytes, absolute host paths, секретов или персональных данных: schema/tool policy, input hashes, counts, sorted ready MAP IDs и blocker state→sorted MAP IDs. stderr/ошибка не выводят CSV row или file contents.
- `MIGP-009`: `--selfcheck` использует только временные synthetic fixtures и доказывает принятие quoted CSV, а также отказ duplicate ID/path, malformed quote/header, path traversal/symlink, SHA drift, MAP↔RTE mismatch и unknown review state. Реальные входы selfcheck не меняет.
- `MIGP-010`: inventory не пишет файлы/БД, не создаёт каталогов, не выполняет сеть/child process и не меняет source atime намеренно; до/после input SHA и git diff совпадают. Production/VPS/старый сайт не затрагиваются.

## Минимальная реализация

- Один `tools/dev09-migration-preflight.mjs`, без npm-пакетов и генерации артефактов.
- Малый строгий CSV parser и pure validation functions находятся в этом же файле; `--selfcheck` покрывает отрицательные ветки без отдельного test framework.
- Inventory report выводится только в stdout; будущий importer сможет принимать его контракт отдельно, но importer/apply сейчас не создаётся.

Новых model/schema/migration/query/cache/worker/dependency/background/state-machine слоёв нет. До кода требуется independent plan review.

## Решение D-728

Independent plan review — `APPROVED`, новых P1/P2/P3 нет. Фактически подтверждены115 MAP/115 RTE,81 exact ready-state и34 blockers по семи состояниям. Preflight признан полезным integrity gate, а не runtime-слоем; Node уже является host tooling и новых packages/config не требует. `ready` означает только preflight-классификацию, не разрешение импорта. Разрешена реализация MIGP-001–010; importer/apply и READY-04/ANA-Q041 остаются вне scope.

## Итог D-729

DEV-09A завершён; independent code review — `APPROVED`, новых P1/P2/P3 нет. Один dependency-free host script имеет exact CLI `--inventory|--selfcheck`, strict UTF-8/RFC4180/header/column parser, exact115 sequence/uniqueness/MAP↔RTE equality, internal path/query policy, lexical+realpath regular/no-symlink source boundary и cached SHA verification. Error output содержит только постоянный код; report — только relative input hashes/counts/MAP IDs/states и явную policy `integrity_only_not_import_authority`. Syntax PASS, selfcheck PASS, actual inventory PASS:115 MAP,115 RTE,114 source snapshots,81 ready,34 blocked; input SHA `c1d542…ad8`/`c3a8a3…9bc` неизменны, invalid usage закрыт `USAGE`, diff-check clean. DB/Django/network/Docker/child process/file write/import отсутствуют; READY-04/MIG-01/ANA-Q041 и34 blockers остаются открытыми.
