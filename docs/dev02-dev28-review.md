# Независимое ревью ограниченной DEV-02/DEV-28

2026-10-30. Основание — D-316: разрешена локальная основа Django/PostgreSQL и ранний безопасный аудит. Рецензент `base_image_security_review` не авторствовал исправления. Область: `app/**`, локальные Compose/Nginx/DB init/launcher, фиксированные диагностические пробы и FOUNDATION-адаптер. Секретные private-каталоги не читались.

## Вердикт

**Блокирующие замечания текущего ревью устранены. Новых открытых существенных замечаний к ограниченной очереди не выявлено.** Локальная основа, запись структурного аудита и её реальные проверки соответствуют согласованной области DEV-02/DEV-28.

Это не приёмка сайта целиком и не разрешение других DEV-модулей или production. Допуск по оставшимся требованиям, before-module проверкам и выпускным воротам сохраняется. Ненулевой vendor-остаток базовых образов из предыдущего ревью также не объявляется исправленным этим кодом.

## Замечания и закрытие

| Постоянный ID | Приоритет / исходный дефект | Исправление и свидетельство | Статус |
|---|---|---|---|
| DEV-REV-001 | P2, блокировал заявление о безопасном process logging: Nginx error_log мог записать URI/query с секретом при отказе upstream, несмотря на access_log off и Django formatter | `environment/foundation/local-nginx.conf:6` отключает неочищенный error log для этого локального этапа. Реальная проба с остановленным app дала HTTP502; новый synthetic token не обнаружен в ingress Docker logs. `checks/nginx-privacy.json` | Закрыто для локального ingress |
| DEV-REV-002 | P2, блокировал IP-only privacy: ipaddress допускал IPv6 `%scope` с произвольным текстом, который process formatter мог вывести | `app/audit/safety.py:56` отвергает zone suffix до парсинга IP. Добавлены formatter-canary и writer-rejection проверки; они входят в актуальный прошедший набор unit/integration | Закрыто |
| DEV-REV-003 | P1, блокировал достоверность приёмки: исходный snapshot мог относиться к другому запуску/составу, чем последующий live HTTP | `scripts/test-foundation.ps1:5` захватывает SHA256 исходного guard; обе проверки `--verify` получают именно этот неизменяемый anchor. Collector сверяет run/manifest/source/snapshot/config/IDs/StartedAt/restarts и metadata до/после; подмена одновременно snapshot и guard тоже отвергается. Реальная негативная проба и восстановление исходного guard прошли: `checks/drift-negative.json` | Закрыто |
| DEV-REV-004 | P2, блокировал заявленный append-only Model.save API: новый instance с существующим PK и `_state.adding=True` мог выполнить UPDATE | `app/audit/models.py:49` отвергает заданный PK, positional/update semantics и повторный save; новая запись принудительно использует INSERT. Регрессия с существующим PK проверяет обычный save, force_update и update_fields, сохраняя исходный event_id/code | Закрыто |
| DEV-REV-005 | P2, не блокировал GET-only основу, но мешал бы будущим same-origin POST: `$host` терял локальный порт и создавал несовпадение Origin/Host для CSRF | `environment/foundation/local-nginx.conf:29` передаёт полный `$http_host` при прежнем hostname whitelist. Trusted origins и forwarded trust не расширены. Полноценный POST/CSRF бизнес-процесс относится к последующим разрешённым модулям | Закрыто на уровне транспорта |

Дополнительно хэш выполненной Python-пробы теперь вычисляется из реально переданного stdin-buffer, а не из повторно прочитанного файла. Это предотвращает неверное указание provenance при редактировании host-файла во время сбора.

## Что проверено по коду

- Секреты обязательны, читаются ограниченно из собственных readonly mounts, без SQLite/секретных defaults. DEBUG=False, строгие Host, CSRF middleware, HttpOnly/SameSite, отсутствие доверия входящим forwarded-заголовкам и CSP report-only соответствуют локальному профилю. Deployment-audit остаётся отдельной проверкой конфигурации, а не production.
- Bootstrap/migrator/runtime разделены. Приложение получает только runtime credential, а не bootstrap/migrator; runtime не получает DDL или подключение к unit-БД. Основной schema owner — migrator, grants/default privileges задаются явно, membership проверяется. Инициализация не удаляет чужие схемы/БД/тома и проверяет реальные credentials.
- Compose разделяет dev/test сети и тома. App/БД без опубликованных портов; ingress публикует только loopback. App использует nonroot/readonly/capDropALL/NNP и ограниченные tmpfs/state. TLS ключ PostgreSQL копируется в собственный tmpfs с режимом0600; сервер переходит к UID999.
- Launcher выбирает закреплённые локальные image IDs и проверяет hashes. Источники test сохраняются отдельным readonly snapshot. Управление ресурсами ограничено именами/labels собственного проекта; Stop сохраняет тома/секреты/снимки. Нативный вызов `docker.exe` исключает прежнюю рекурсию функции Docker. Готовность БД теперь проверяется через TCP127.0.0.1:5432, что исключает преждевременную готовность временного Unix-only bootstrap-сервера.
- Audit writer принимает фиксированную схему и типизированные внутренние ссылки, не свободный payload. Он делает один INSERT, участвует в транзакции вызывающего кода и не выдаёт ошибку за успех. Event UUID уникален на уровне БД. Formatter не выводит raw msg/args/trace/request/неизвестные extras и имеет безопасный fallback.
- Append-only ограничение относится к описанному save API. Документированная будущая защита от raw SQL/QuerySet.update/удаления/retention не выдана за уже готовую абсолютную DB-immutability.
- Collector выполняет фиксированные host-side Docker exec/inspect и реальные SQL/config/library пробы. У приложения и тестового контейнера нет Docker socket; публичный inspector endpoint не создан. Readonly snapshot ограничен текущим run и временем, HTTP остаётся живым запросом к своему origin. Для действительного результата требуется весь wrapper с успешным post-guard, не один JSON Playwright.

## Фактические проверки и границы свидетельств

Координатор выполнил **21 unit/integration test**, `makemigrations --check --dry-run` без изменений и системную проверку Django без silenced checks. Рецензент просмотрел код регрессий и сообщение координатора с результатом; отдельный повтор этих тестов рецензентом не выполнялся.

Проверен машинный отчёт `test-results/acceptance/foundation-security-results.json`: **11 expected / 0 unexpected / 0 skipped / 0 flaky**, продолжительность 7.063 с, запуск30.10.2026 19:46:32UTC. Координатор подтвердил exit0 полного wrapper с до/после guard, включая повтор после последнего исправления Host.

Принятый source/run: `49ffdb0d-9716-4eb1-a92a-aaad17360d75`. Рецензент независимо пересчитал **21 файл snapshot** и подтвердил их manifest hashes. `sourceSha256=2c61638ba413d7306af5801df9f49a34bd40bc95e582c84f77a16eb990f392be`. Snapshot, guard и manifest имели одинаковый run ID; исходные hash-связи совпали при проверке до штатного выключения. После Stop ожидаемо изменяется active/status manifest; это не переопределяет сохранённое свидетельство завершённого запуска.

Просмотрены непубличные локальные результаты без секретных значений:

- `work/foundation/test/checks/nginx-privacy.json` — настоящий upstream fault и отсутствие synthetic token.
- `work/foundation/test/checks/drift-negative.json` — одновременная подмена snapshot/guard отвергнута, исходный набор восстановлен и проверен.
- `work/foundation/test/checks/runtime-capabilities.json` — реальный app_runtime, TLS, SQLSTATE42501 для DDL, audit insert/read и откат enclosing transaction.
- `work/foundation/test/checks/dev-test-isolation.json` — одновременно работающие dev/test с различными run IDs, DB volumes, secret sources и DB networks.

Синтаксис collector/bridge проверен рецензентом через `node --check`. Docker и приложение рецензент не запускал; runtime-утверждения основаны на сохранённых результатах автора и проверенном пути их получения. Сырые credentials, ключи и private-файлы не читались и в отчёт не включались.

## Остаток и следующий шаг

Реализована основа, а не страницы/навигация/вход/права сотрудников/редактор/формы/резервы/аварийный контроллер. Публичный URLconf намеренно пуст; текущие HTTP404 не являются дефектом незаявленных страниц. Встроенные Django auth/contenttypes/session таблицы не означают реализованный интерфейс входа или готовые бизнес-права.

CSP enforcement браузером, реальные авторизованные POST/CSRF, все AC логов/очистки/Telegram, ограничения других бизнес-модулей и production проверяются на следующих соответствующих этапах. **11 FOUNDATION не превращаются в 140 пройденных полных AC.**

Открытых блокирующих замечаний этого ограниченного ревью нет. Текущий этап — **8, локальная DEV-02/DEV-28 по D-316**; последующие DEV-модули допускаются по согласованному поэтапному плану и своим before-module условиям. Старый сайт, VPS и публикация этим ревью не разрешаются.
