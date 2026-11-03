# DEV-29 / P29-A: код и частичные проверки

Дата: 2026-11-03. Основание: D-410–D-412, DEV29-Q005, `dev29-publication-plan.md`. Статус: **код подготовлен и code-review принят; изолированные PostgreSQL-проверки BLOCKED, P29-A не завершён**.

## Возобновление и сохранность

После разрешения владельца DEV29-PA-RESUME-001 выполнена read-only проверка ACL: work — обычный каталог, явного доказательства необходимости менять ACL нет. Штатное `require_escalated` создание только `work/dev29-publication-20261103` успешно; ACL не менялись. Через apply_patch сохранён checkpoint.json с SHA 10 существующих изменённых/новых файлов; чтение и пересчёт SHA всех 10 дали CHECKPOINT_PASS до дальнейших правок документов. Исторический checkpoint не переписывается.

Docker API недоступен (отсутствует pipe dockerDesktopLinuxEngine), запуск Docker автоматически не выполнялся. На диске runtime manifest имеет active=false/writeMode=disabled, compose.env содержит disabled; capacity-attempt.json существует, calibrationAttempted=true. Это сведения файлов, не доказательство текущего состояния контейнеров/БД/permit. Актуальная SQL-сохранность MAIN/UNIT/архивов и пустой permit в этой работе не подтверждены. Секреты не выводились.

## Изменения

- `trust/journal/protocol.py`: закрытый prepare kind route_publication, ровно одна policy HIDDEN/LIVE_NO_SET, одинаковый root/policy objectId, пустые requestIds; прежнему route_restriction LIVE_NO_SET запрещён. Report принимает форму LIVE_NO_SET, а неизменённый services.mutate проверяет точное равенство сохранённой policy list из Prepare.
- `trust/journal/consumer.py`: LIVE_NO_SET распознаётся как journal data. Возможность HTML admission не добавлена; StartupResult по-прежнему имеет html_admission=false.
- `trust/journal/test_publication_profile.py`: сначала написаны тесты, затем код; четыре stdlib теста и четыре PostgreSQL-теста через существующий JournalFixture. При отсутствии Django доступны только явно выбранные wire-тесты, DB-классы не определяются; это не считается полным тестовым запуском.

Models/services/views и миграции не менялись. Inventory миграций 0001–0003 проверен: kind/policy — CharField достаточной длины, без choices/ограничения множества значений; additive-миграция не требуется. APP/сеть/credentials/Boolean и настройки окружения не менялись.

## Проверки и границы

Использован уже установленный bundled Python 3.12 по адресу `C:/Users/nname/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`, без установки зависимостей. Ключи `-I -B`: изоляция Python и отсутствие записи bytecode. Django в этом интерпретаторе отсутствует.

Фактический вызов standalone: `unittest.defaultTestLoader.loadTestsFromName("journal.test_publication_profile.PublicationWireTests")` после добавления только каталога trust в sys.path. Результат: **4 tests / 0.002s / OK**. AST parse всех 31 `.py` в trust: **PASS**. `git diff --check`: PASS; предупреждения Git о будущей LF→CRLF конвертации не являются ошибками проверки.

| Сценарий | Факт | Остаток |
|---|---|---|
| A29-001 | PASS wire shape/negative schema | DB PENDING_DENY — BLOCKED |
| A29-002 | PASS формат report | policy equality/fingerprint/replay в PostgreSQL — BLOCKED |
| A29-003 | PASS прежние kind и запрет LIVE_NO_SET в route_restriction | DB replay/generation — BLOCKED |
| A29-004 | DB-тест unknown/abort/status подготовлен | NOT_RUN, runtime BLOCKED |
| A29-005 | PASS consumer item shape/key/generation/known policies | Полный snapshot transport/regressions — BLOCKED |
| A29-006 | Подготовлена реальная SQL division-by-zero injection при Head.save, проверки rollback и retry | NOT_RUN, runtime BLOCKED |
| A29-007 | Подготовлены disabled gate/count-cap тесты | NOT_RUN; прежние admission/reader/recovery регрессии BLOCKED |
| A29-008 | Изменения ограничены указанными исходниками/документами; сеть/APP/окружение не менялись | Свежие UNIT/MAIN/архивные fingerprints и runtime cleanup не проверялись; запусков не было |

Независимые P29-A-CODE-REVIEW-001 и P29-A-RESULT-REVIEW-001: APPROVED для частичного результата, замечаний P0–P3 нет. Рецензент подтвердил ограничения prepare/report и conditional discovery, независимо повторил 4 wire-теста, AST31, SHA и diff-check; БД/стенд не запускал. [Отчёт ревью](dev29-publication-code-review.md).

## Почему runtime не запущен и следующий шаг

В `tools/local_trust.mjs` action Tests имеет явный guard TRUST_CAPACITY_CORPUS_PRESERVED при наличии capacity-attempt.json. Сохранённый корпус нельзя обходить обычным Django TransactionTestCase runner: его flush уничтожит прежние данные UNIT. Даже доступный Docker сам по себе не снимает этот второй блокер.

Следующее разрешённое действие — подготовка отдельного точного способа UNIT-проверок, сохраняющего корпус, согласно P29-A04: read-only инвентаризация прежних процедур архивирования/изоляции, проверка реального исходного состояния при доступности Docker, затем независимое ревью конкретного плана. Не запускать текущий Tests, не снимать guard, не создавать/очищать базы и тома по догадке, не включать writer/MAIN lease. P29-A остаётся в работе, процент DEV-29 сохраняется около35%, этап8 около31%. Полный publication e2e, APP/cohort/EDGE и production не выполнены. Старый сайт/VPS не затронуты.

## Привязка проверенного кода (SHA256)

| Файл | SHA256 |
|---|---|
| protocol.py | a023c07e7de9dfda3d33b389991d6d7aea9f42650e4d14e2f8ac73b136318734 |
| consumer.py | 76896edeb2698065005c6d5a48413bbfa94706a4bb80ebfaea9414a8449fcf80 |
| test_publication_profile.py | eae1552c5c92394adf74b49608fef109fee893958a7225bdca4bc865d5ba1cf7 |
