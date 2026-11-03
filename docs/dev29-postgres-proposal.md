# P29-A: PostgreSQL-проверки без изменения сохранённого корпуса

Дата: 2026-11-03. Статус: **способ согласован владельцем по DEV29-Q006/D-414; подготовка пакета приостановлена владельцу PG29-PACKAGE-RESUME-001, runtime не допущен**. Основание: DEV29-Q005, P29-A04, D-410–D-414; PR-04/08. [Ревью способа](dev29-postgres-review.md), [код-кандидат и продолжение](dev29-postgres-package-resume.md).

## 1. Выбор способа и предел результата

Рекомендуется отдельная конечная операторская probe-процедура по образцу принятых RB15/RF15/FC15: только точная существующая UNIT `test_estakada_trust`, исторически OID52766, внутри внешней PostgreSQL-транзакции с обязательным rollback. Процедура вызывает production-сервисы TRUST и consumer на synthetic fixture. Она не вызывает Django test runner и не меняет его защиту.

`tools/local_trust.mjs` и guard `TRUST_CAPACITY_CORPUS_PRESERVED`, capacity-attempt.json, исторические manifest/env, signed policy/permit/lease, EV63 и исходные архивы остаются побайтно прежними. Команды Start/Tests/Calibrate/ArchiveUnit не вызываются; guard не удаляется/не переименовывается/не перехватывается. Новый способ требует своего явного разрешения, code-review и допуска точного запуска; подготовка предложения не является таким разрешением.

Полный прогон прежнего `manage.py test journal` этим способом не выполняется: TransactionTestCase вызывает flush, а конкурентные/multi-connection/crash тесты несовместимы с одним внешним rollback. Исторические131 тестов не присваиваются новому source. Результат — новые отдельно именованные PG29-группы, частично закрывающие A29; весь P29-A не объявляется завершённым, пока остаются обязательные регрессии без свежих свидетельств.

Альтернативы: новая тестовая база/кластер позволили бы обычный runner, но добавляют ресурсы, роли и процедуру уничтожения; здесь не предлагаются. Архивировать/переименовывать текущую UNIT ещё раз — ненужная мутация каталога. Возврат boolean/данных «как было» после committed fixture слабее rollback и не допускается.

## 2. Проверенные основания, не текущее runtime-состояние

- `tools/trust_rollback_probe.py`, `trust_recovery_probe.py`, `trust_final_controls_probe.py`: точная UNIT, migrator/TLS, проверка пустых предметных таблиц, внешний atomic, rollback, reconnect и сравнение всех строк/sequence.
- `work/dev15-recovery-20261103/unit-audit.py`: отдельный read-only witness с OID/owner/marker/TLS/schema/all-row digest и migration sequence.
- `trust/journal/tests.py`: JournalFixture.setUp делает bootstrap synthetic Head/credentials и включает test-process calibration; никакого разрешения рабочей HTTP-записи этим не даёт.
- `trust/journal/test_bounded.py`: BoundedFixture создаёт временные synthetic key/permit, проверяет настоящий bounded admission в UNIT, ресурсы в этой fixture замещены; поэтому это service-level доказательство, не native deployment admission.
- Старые архивы: `test_estakada_trust_cal_7e145c49`/OID16387 и `test_estakada_trust_cap_32563`/OID32563, ожидаемые закрытые `datallowconn=false`; исторически UNIT52766 пуста кроме трёх migration rows. Эти значения — условия допуска, не свежий PASS. При расхождении остановиться без init/migrate/archive/исправления данных.

Docker в предыдущей работе был недоступен; в подготовке этого документа Docker/БД не запускаются и свежая SQL-сохранность не утверждается.

## 3. Новые артефакты и привязка исходников

После Q006 предлагаются только новые файлы в ignored `work/dev29-publication-20261103/pg-check/`: именованные controller.mjs, probe.py, unit-witness.py, gate/preflight/collector скрипты, закрытая схема intent/report, тесты их отказов, отдельный read-only candidate snapshot TRUST и append-only manifests/отчёты запуска. Редактирование продукта, существующего runner, compose и прежних проверочных скриптов не входит.

Контрольные копии исходников и конфигурации фиксируются до подготовки пакета. Candidate source: полный точный перечень Python TRUST (сейчас31), canonical fingerprint по текущему `profile.source_files()` и отдельные SHA трёх изменённых файлов из `dev29-publication-results.md`. Snapshot read-only, запрещены reparse/symlink/неучтённые файлы; после каждого этапа SHA повторно сверяются. Новый тестовый source не маскируется под прежний fingerprint014efc…; число файлов не заменяет их точный перечень.

Исторический source и EV63 сверяются по их замороженным каталогам/подписанным ссылкам, без требования равенства изменённому рабочему дереву. Разрешённый diff нового candidate относительно базового source — protocol.py, consumer.py, новый test_publication_profile.py; любое иное расхождение требует объяснения/повторного review. Старые подписи/доказательства не пересоздаются для придания новому коду прежнего допуска.

Новый intent связывает run UUID, candidate fingerprint, SHA controller/probe/witness и их code-review, ожидаемые DB OID/marker/schema, baseline UNIT/MAIN/архивов, images/caps/mounts, срок и закрытый список PG29. Перед исполнением intent привязывается к полным Docker ID существующего DB и единственного helper. При недоказанной связи или повторном UUID новый запуск запрещён; timeout не даёт автоматический retry.

## 4. Контейнеры, роли и изоляция

Только существующие pinned local images/volume/internal DB network; никаких pull/build/install/публичных портов/новых постоянных сетей/томов/БД. Одновременно DB 512МиБ/.5CPU/PIDs128 и один временный helper 256МиБ/.5CPU/PIDs64, прежние read-only rootfs/cap-drop/no-new-privileges. API/ingress выключены, рабочий writer disabled, штатный permit на диске обязан быть `{}` и не монтируется writable. Helper работает как10001:10001, с bounded tmpfs для synthetic fixture, source и secrets read-only. Предельные output/logs — 1МиБ на helper, 60с внутри и 90с на host; превышение — FAIL с точечным Stop своего полного container ID.

Сначала при доступном локальном Docker проверяется точный context/engine, labels/image IDs, сохранённый volume и config hashes. Если DB остановлена, её запуск возможен только после отдельного допуска точного пакета: использовать прежнюю конфигурацию DB без init/migrate/bootstrap-команды; запуск API запрещён. Если обнаружен чужой/неучтённый контейнер, mount, сеть, активная lease или непустой permit — STOP без kill чужих сессий и без переписывания состояния.

SQL probe получает только migrator credential и доступ только к фиксированной UNIT по TLS verify-full; настройки `TRUST_TEST_EXECUTION=1`, `TRUST_DB_NAME=test_estakada_trust`, `TRUST_DB_USER=trust_migrator`, начальный TRUST_WRITE_PROFILE=disabled. Секреты не включаются в arguments/URL/output/log. Synthetic credentials/pin/permit из fixture находятся только в tmpfs helper. MAIN credentials/working writer/recovery activation ему не передаются.

Read-only preservation witness выполняется отдельно, последовательно, с прежними полномочиями аудита, без расширения ролей/ACL. Для MAIN используется только read-only соединение и транзакция. Архивы не открываются для соединений: сверяются catalog OID/owner/marker/datallowconn и прежние signed proofs; проверку содержимого закрытого архива не подменять его новым чтением через включение datallowconn.

## 5. Preflight и сохранность

До любых fixture writes:

1. Сохранить новый checkpoint/точные source/config/EV ссылки. Проверить, что прежние guard и manifest/env/permit неизменны. Получить свежие MAIN state-v2/head/rows, archive catalog identities/proofs, UNIT full rows/schema/sequence через отдельный read-only witness. Исторический MAIN Head13 не использовать как новый CAS; если baseline изменился относительно принятого состояния, остановиться для выяснения.
2. UNIT: actual database/session_user/current_user, OID52766, owner postgres, точный marker из принятого signed archive receipt (не просто prefix), TLS, search_path только trust/pg_catalog, ожидаемый schema fingerprint и migration names; все предметные таблицы пусты. Не удалять строки, если это не так. Migration sequence last_value/is_called фиксируется, reset/setval не выполняется.
3. Убедиться в отсутствии других UNIT sessions. Взять transaction-scoped advisory lock для этой probe и блокировки нужных таблиц с lock_timeout1с; повторить identity/empty-state под блокировками до bootstrap. Ни одного второго записывающего соединения. Это не заменяет проверку остановленных API/ingress; весь процесс закрыт для параллельных тестовых запусков операторским lock-файлом.
4. В каждом helper единый фиксированный DB target; никаких пользовательских SQL/имён таблиц/команд. SQL/query interceptors не должны подменять сервисную семантику. Проверки запрета flush/DDL/COMMIT вне санкционированного lifecycle готовятся отдельными негативными тестами пакета до DB-допуска.

После работы: обязательный rollback внешней транзакции, cleanup context/settings/calibration/temporary fixture; закрытие соединения; новый независимый witness после reconnect сравнивает UNIT все строки/counts/schema/sequence и MAIN baseline, archive catalog/proofs. Ошибка cleanup/preservation имеет приоритет над функциональным PASS. SQL-сохранность не означает побайтную неизменность data directory: WAL/статистика могут меняться, объём/ресурсы измеряются отдельно в прежних лимитах.

## 6. Исполнение probe и приёмочные группы — NOT_RUN

Это прямые service probes, а не запуск/обход lifecycle TransactionTestCase. Fixture можно использовать только как явно проверенный builder: разрешены setUp/start/doCleanups в ограниченном scope по образцу RB15/FC15; запрещены fixture.run/__call__/_pre_setup/_post_teardown, flush, migrate, create/drop/rename DB, TRUNCATE/sequence reset, commit fixture и автоматический repair.

Для каждой независимой группы — новая внешняя atomic и новая synthetic fixture; внутри неё сервисы открывают свои обычные вложенные atomic/savepoints. Внешний atomic никогда не коммитится, даже при FAIL; transaction.set_rollback(True) в finally перед выходом, при аварии соединение закрывается. Каждый rollback проверяется reconnect witness до следующей группы; подтверждённый PASS группы выдаётся только после сохранности. Любой FAIL останавливает последовательность.

| ID | Действия и доказательства | Связь |
|---|---|---|
| PG29-001 | HIDDEN и LIVE_NO_SET отдельными synthetic PageID/path: Prepare создаёт Operation/RoutePolicy=PENDING_DENY; неверная wire/schema отклоняется до предметного SQL; mismatch policy list при report не меняет full state. | A29-001/002 |
| PG29-002 | Оба финальных исхода: раздельные prepare/report fingerprints, точный replay до/после final, неизменные generation/receipts при replay, другой basis/receipt/incarnation даёт конфликт. | A29-002/003 |
| PG29-003 | Unknown→status→aborted сохраняет deny; terminal immutable; потерянный ответ моделируется игнорированием результата локального вызова, не называется реальной потерей TLS. | A29-004 |
| PG29-004 | Реальные read_head/status/snapshot_manifest/snapshot → consumer.read_snapshot через прямой bounded transport; LIVE_NO_SET валиден, но startup_check.html_admission=false. Отрицательные key/shape/generation/digest, unknown policy fail closed. Это service transport, не HTTP/TLS e2e и не PageID↔APP Route proof. | A29-005 |
| PG29-005 | Перед поздним SQL division-by-zero зафиксировать существование uncommitted Operation/RoutePolicy/phase; проверить SQLSTATE22012 и полное восстановление state/charge/reserve после вложенного rollback, затем exact same UUID retry/replay. Внешний rollback сохраняет UNIT. | A29-006 |
| PG29-006 | Прежние route_restriction HIDDEN/DELETED/REDIRECT, request_tombstone, их replay/unknown/abort и чтение — отдельные ограниченные regression branches на новом source. LIVE_NO_SET в прежнем kind запрещён. | A29-003/регрессии |
| PG29-007 | Сначала disabled-gate/reader HTTP-role rejection/неверный epoch. Отдельный BoundedFixture scope: signed synthetic policy/lease, реальная граница действующей квоты1000 без mock count, отказ1001 с full state equality, завершение принятой операции и replay после отказа. Настоящая native lease/worker exclusion не доказаны fixture; recovery регрессии отдельно отмечаются, если не исполнены. | A29-007, частично |
| PG29-008 | Независимые UNIT/MAIN/архивные witnesses, source/config/guard/permit before=after, migration sequence прежняя, fixture rollback, cleanup, resource limits и Stop собственных контейнеров. Никакого общего PASS при отсутствии любой preservation-проверки. | A29-008 |

Полная квота1000 может потребовать времени/места: перед допуском проверить bounded estimate на существующем budget; deadline/caps не повышать. Если ветка не помещается — BLOCKED, не заменять её mock count и не объявлять PASS. Reader-role check — через endpoint в том же process/соединении, не запуск публичного HTTP API. Исключаются многопоточные тесты и реальные restart/crash durability: внешний rollback не доказывает их. Для остальных обязательных регрессий сохраняется отдельный список NOT_RUN.

## 7. Gates до запуска

Пакет должен сначала пройти независимые code/QA-review и статические/VM-негативные проверки: wrong DB/OID/marker/role/schema/source, nonempty UNIT, другая сессия, непустой permit, чужой container, source drift, попытка runner/flush/DDL/commit, timeout после send, частичный cleanup/потерянный output. При сигнале завершения helper его SQL-соединение должно быть закрыто/откачено; факт завершения backend проверяется read-only witness. Пока это не доказано, повторный helper запрещён.

Отдельно закрываются происхождение intent/run/source/container и after-witness. Code approval не равен runtime admission, а runtime failure не исправляется третьей эквивалентной попыткой. Результаты PG29 не переписывают исторические FAIL/PASS/подписи.

## 8. Согласование

**DEV29-Q006.** Согласовать ли описанный способ и подготовку нового конечного probe-пакета: точная существующая пустая UNIT, service probes во внешнем rollback, независимые preservation witnesses и прежние ресурсы, без вызова/изменения защищённого runner? После подготовки кода и его независимого ревью потребуется отдельный допуск точного локального запуска. Сейчас ни запуск Docker, ни SQL writes этим предложением не выполняются.

Причина отдельного согласования: P29-A04 требует подготовить точный способ, если штатный runner не обеспечивает изоляцию; это предложение меняет способ получения PostgreSQL-свидетельств и требует нового проверочного пакета. Полные APP/EDGE workflow, старый сайт/VPS/production/push не входят. DEV-29 около35%, этап8 около31%.
