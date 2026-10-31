# Восстановление и частичная очистка логов: этап 7

2026-10-30. Основания D-093/D-098/D-107/D-112/D-301–D-303/D-305/D-308 и прямое поручение владельца. Только приёмочные тесты/оснастка/документы. Старый сайт/VPS/их БД/файлы/ОС/настройки не меняются; кода приложения/его management-команд/инфраструктуры нет. Прежние локальные изменения сохранены.

## Подготовлено

| Поднабор | Экземпляров | Частичная область |
|---|---:|---|
| restore-contracts.spec.js |10 | AT-037/044:подтверждённый admin/external restore, safety и post-cutoff export, target DB/media, внешний tombstone, sessions/owner recovery/выключение сотрудников, smoke, отказы стадий/роли/пароль |
| log-delete-failures.spec.js |2 | AT-062/704/705/706:logical done/files pending, доступ/no-space на файловой стадии, новые/чужие записи/байты вне L, фактический размер/CAP, повтор только той же операции, аудит/cursor/cycle/critical |
| DRIVER-SAFE-024/026/027 |7 новых | Раздельные restore/log-deletion permits и защищённая передача новой framework session в отдельный неиспользованный probe actor |
| Исправление logging-contracts.spec.js |25→24 | Убрана только неутверждённая password-tamper проба и соответствующие обязательные условия; остальные стабильные IDs/сценарии сохранены |

Добавлены12сценариев и7selfchecks, убран1необоснованный экземпляр: прирост18 к881. Новые12сценариев приложения не исполнялись. Подготовленные assertions не являются пройденными AC или реальным восстановлением. Контракты: [restore](acceptance-restore-contracts.md), [partial delete](acceptance-log-delete-failures.md), [исправленный logging](acceptance-logging-contracts.md), [транспорт](local-test-adapter.md).

## Независимое ревью

Автор partial log deletion/исправления прежнего logging — stage7_partial_log_delete; restore/transport/интеграция — координатор. stage7_restore_log_review проверял read-only, не исправлял результат и не запускал сценарии. Все замечания перепроверены; новых существенных замечаний в целевой области нет.

| ID | Приоритет | Ошибка теста | Исправление |
|---|---|---|---|
| TEST-R046 | P2 | Для категории логов требовался повторный пароль без основания в D-093/архитектуре/MAN-03/UI-S041 | Обязательное password-условие/неверный пароль убраны из тестов, актуальное подтверждение/права сохранены. Обратный запрет password UI не вводится; независимо закрыто |
| TEST-R047 | P2 | Проверки точки/совместимости могли идти после применения рабочих данных | Point/compatibility/write fence и safety/export либо enhanced loss подтверждены до обеих рабочих замен DB/media; нормальный/admin доступ только после требуемых готовностей. Staging отделён от applied; независимо закрыто |
| TEST-R048 | P2 | Safety проверялась одним ID/flags, не обнаруживалась неполнота/потеря после отказа | Независимая реконструкция safety сравнивается с pre-restore business/media oracle, точный post-cutoff Request/consent export; тот же safety проверяется после post-replacement отказа; независимо закрыто |
| TEST-R049 | P2 | Счётчик записи читался до запроса, mutation+denied мог пройти | Реальный положительный pre-probe; отдельная новая framework session после invalidation, реальные state/counter после POST, действительные текущие права/CSRF/base как readiness binding. Старый session не используется для доказательства maintenance; независимо закрыто в частичной области |
| TEST-R050 | P2 | Один fixed action ожидал несовместимые args.text и args.fields.text | Оба log save helper используют общий save-text(page,base,text), документы согласованы; независимо закрыто |
| TEST-R051 | P2 | Audit.category!=удаляемой запрещало разрешённый внешний журнал с тем же label | Допускается другая protected category либо реальный separate external store: actual audit bytes/SHA/placement/ranges/root ancestry вне подтверждённого набора; независимо закрыто |

Это целевое ревью тестов; фактические CLI/framework/CSRF/controller/bridge/OS, keys/crypto и полный TEST-07 не утверждаются. Source/evidence flags требуют независимого подтверждения конкретного подключения, не заменяют его.

## Фактические проверки

- driver-safety: **74 passed**, skipped/unexpected/flaky=0,12,83с; `test-results/acceptance/driver-restore-log-results.json`, `work/acceptance-driver-restore-log.txt`. Рецензент отдельно сверил JSON. Это оснастка, не12restore/delete сценариев.
- Контейнерное перечисление: **899 tests in 28 files**, exit0; `work/acceptance-stage7-list-restore-log.txt`. Синтаксис JS/PowerShell и git diff --check без ошибок. Документные/изоляционные проверки после синхронизации: **4 passed**, skipped/unexpected/flaky=0,2,9с; `test-results/acceptance/documents-restore-log-results.json`, `work/acceptance-documents-restore-log.txt`.

Матрица140AT: **35 text_only /7 partial_http /98 assertions_waiting_driver**. AT-705 впервые получил частичные assertions, AT-037/044/062/704/706 дополнены с сохранением прежних проб. Постоянные140AC/63REQ/115MAP/RTE не перенумерованы; полный AC не объявляется пройденным.

Реальные БД/файлы не восстанавливались/не удалялись, команды break-glass/ротации секретов не запускались; сторонние хранилища не подключались. Временный локальный Docker выполнял только самопроверки инструмента. Предыдущие67не суммируются с пересекающимися74как разные проверки.

## Остаток

Полные restore/cleanup AC не пройдены. CLI и одноразовые signed-команды/replay/expiry, все crash/unknown commit/fencing, гонки tombstones/новых данных, полный объём схем/миграций/прав/сессий/CSRF, вся связанная payload-очистка по LEGAL, реальные ключи/storage/IO/decode/partial rewrite, очереди и внешние секреты, ресурсы и все smoke остаются отдельными ветвями/READY.

Новая probe session — только тестовая fixture для уже существующего owner без изменения прав, не способ добавить продуктовый обход. Конкретное применение cookie/CSRF к actual actor context и правильному path/expiry ещё требует независимой проверки. При недоступности такой пригодной среды сценарий остаётся непроверенным, а не считается pass по label.

Этап7 продолжается. Полные UX-07/физический ARC-10/TEST-07 открыты; код этапа8 и production требуют отдельных разрешений владельца.
