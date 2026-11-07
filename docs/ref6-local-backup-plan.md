# REF-06F — локальный backup current/previous

Дата: 2026-11-06.
Основание: D-593, D-598, D-600, D-601, D-645, REF6-Q002.
Статус: завершено по D-656; финальное независимое review — `APPROVED`.

## Граница

Добавить закрытый host-side wrapper для локального foundation, который создаёт один проверяемый комплект PostgreSQL+media+manifest/checksums. Используется уже закреплённый PostgreSQL-образ с `pg_dump`, `tar` и `sha256sum`; новый образ, daemon, Django model/UI и backup-платформа не создаются.

Для согласованного короткого режима обслуживания wrapper принимает работу только при запущенной `db` и остановленных `app`, `ingress`, `media-worker`. Он не останавливает и не запускает runtime сам. PostgreSQL dump выполняется ролью `app_migrator` с принудительным read-only session default; пароль читается из закрытого файла и не передаётся аргументом командной строки или обычной environment variable.

В инкремент не входят внешняя зашифрованная копия, ключ, расписание, автоматический restore, production/VPS, HTML-резерв, заявки, удаление request ledger и админский экран результата.

## Приёмочные сценарии

- **LBK-001 — закрытая поверхность.** Backup запускается только локальным wrapper; нет URL, Django command, UI, порта или shell execution из приложения.
- **LBK-002 — maintenance gate.** Требуются `db=running`, `app/ingress/media-worker=stopped`; несоответствие завершает работу до staging/rotation и не меняет runtime.
- **LBK-003 — ограниченный tool.** Одноразовый контейнер использует закреплённый PostgreSQL-образ, только DB network, state read-only, output staging write-only по назначению, read-only root, dropped capabilities, no-new-privileges и bounded resources.
- **LBK-004 — безопасный credential.** `app_migrator` secret и CA монтируются read-only; временный `.pgpass` создаётся с mode 0600 в tmpfs, пароль отсутствует в argv/output/manifest/archive и удаляется вместе с контейнером. `PGOPTIONS` принудительно задаёт read-only transactions.
- **LBK-005 — полный комплект.** Staging содержит custom-format PostgreSQL dump, media tar, versioned manifest и SHA-256 checksums; manifest не содержит secret paths/values или содержимое пользовательских данных.
- **LBK-006 — проверка до публикации.** `pg_restore --list`, `tar --list`, повторный SHA-256 и строгая проверка состава проходят до смены поколений; failure удаляет только staging и сохраняет `current/previous` побайтно.
- **LBK-007 — два поколения.** Проверенные поколения хранятся неизменяемыми каталогами; атомарно заменяемый `catalog.json` назначает UUID `current` и `previous`. Новый каталог поколения публикуется до каталога-указателя, а прежние поколения не удаляются до успешной проверки нового catalog.
- **LBK-008 — закрытое host-хранилище.** Каталог `work/foundation/<env>/backups` не является reparse point, остаётся вне Git и получает тот же ограниченный Windows DACL, что private foundation data.
- **LBK-009 — безопасный результат.** Успех сообщает только generation/time/files/checksum status; failure не раскрывает SQL, DSN, пароль, имена media или exception text из контейнера.
- **LBK-010 — без ложных обещаний.** Локальный комплект не объявляется внешней/зашифрованной копией, расписанием или проверенным restore; эти части остаются отдельными инкрементами.
- **LBK-011 — один writer/state changer.** Эксклюзивный per-environment file lock удерживается backup от initial maintenance check до завершения publication/cleanup, а foundation — на протяжении всего Start/Stop/UnitTests. Второй writer/state changer fail-closed не создаёт staging и не меняет container/catalog state.
- **LBK-012 — crash-safe publication.** Generation directories immutable. `catalog.json` создаётся через flushed same-directory temp и atomic file replace/move. Crash до replace оставляет старый catalog authoritative; crash после replace оставляет новый catalog authoritative. Startup cleanup удаляет только проверенные unreferenced staging/orphan artifacts после чтения действующего catalog; cleanup failure не превращает уже опубликованный backup в ложный failure.

Перед atomic catalog publication wrapper повторно сверяет identity, running/restart/timestamp state `db/app/ingress/media-worker` с initial maintenance snapshot. Любое изменение блокирует публикацию и сохраняет прежний catalog.

## Проверки

Статические tests wrapper/helper, compose config, реальный backup только на локальном test foundation с неизменными счётчиками основной БД, проверка generation rotation и injected failure preservation, отсутствие секретов в process/config/result, `git diff --check` и независимое review. Production/VPS/старый сайт не затрагивать.
