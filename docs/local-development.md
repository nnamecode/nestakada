# Локальная основа DEV-02/DEV-28

Основание: D-315/D-316. Используются существующие Docker Compose и три образа из `environment/foundation/runtime-images.lock.json`; сборка, установка инструментов, VPS и старый сайт не затрагиваются.

Из корня репозитория:

```powershell
.\scripts\local-foundation.ps1 -Environment test -Action Start
.\scripts\local-foundation.ps1 -Environment test -Action UnitTests
.\scripts\local-foundation.ps1 -Environment test -Action Status
.\scripts\local-foundation.ps1 -Environment test -Action Stop
```

Для рабочего окружения заменить `test` на `dev`. Тесты запускаются только в `test`: Django `test audit content accounts foundation_tests --keepdb --noinput`. Изначально создана отдельная БД `estakada_foundation_unit`; роль мигратора не получает CREATEDB. Действие по умолчанию — Status, окружение — test. Повторный Start требует предварительного Stop.

Проекты `nestakada-foundation-dev` и `nestakada-foundation-test` имеют раздельные именованные тома и три сети. Только Nginx публикует HTTP на `127.0.0.1:8766` / `127.0.0.1:8767`; приложение и БД не публикуют порты. Сети приложения и БД внутренние. Запуск ручной, без автозапуска и фонового наблюдателя. Проверка готовности ограничена временем запуска.

Приложение работает как UID 10001 с исходниками только для чтения, без capabilities, с no-new-privileges и отдельным томом состояния. В dev виден текущий каталог `app`; в test создаётся новый снимок файлов `.py`/`.lock` под `work/foundation/test/sources/<runId>`. Приёмочные доказательства должны независимо сверять снимок с файлами и реальным окружением. Nginx работает как UID 101; корневые ФС всех сервисов доступны только для чтения. Служебный кратковременный job только назначает UID 10001 корню нового тома состояния. PostgreSQL начинает штатную инициализацию как root и затем переходит на UID 999; ключ TLS копируется в tmpfs с режимом 0600. Приложение проверяет сертификат БД через verify-full, имя db.

Учётные данные находятся только в `work/foundation/<env>/private`; ACL оставляет владельца Windows и SYSTEM. Существующие пароли сохраняются, новые создаются криптографически случайными. Ключ и самоподписанный сертификат db создаются OpenSSL внутри закреплённого Python-образа, без установки на Windows. Срок сертификата — 30 дней; при остатке менее часа запуск останавливается для явного обновления локальной пары, существующие файлы не удаляются. Каталог private, дампы и runtime-артефакты не добавляются в Git.

БД создаётся с раздельными ролями bootstrap/migrator/runtime. Runtime получает CONNECT к основной БД, USAGE app, CRUD таблиц и USAGE/SELECT последовательностей; схемой и таблицами владеет мигратор. Runtime не получает DDL, административные полномочия и подключение к unit-БД. Приложение не видит bootstrap/migrator-паролей. Пользователи сайта не создаются. Начальные таблицы auth/contenttypes/sessions и audit создаются миграциями, интерфейс входа этим не реализуется.

`work/foundation/<env>/manifest.json` содержит runId, environment, active, composeProject, containers (app/db/ingress), sourceDirectory, sourceManifest, sourceSha256, privateDirectory (только путь), dbName, unitDbName и port. sourceSha256 — SHA-256 байтов указанного JSON-манифеста исходников (UTF-8 без BOM); каждый элемент содержит относительный path и SHA-256 файла. `compose.env` содержит только публичные пути, номера портов и ID образов. Эти файлы служат входом локального сборщика фактических свидетельств и сами по себе не доказывают прохождение проверок.

Перед Start проверяются хеши зафиксированных входов и наличие локальных образов с точным Docker ID. Имена ресурсов и метка `nestakada.scope=foundation-dev|foundation-test` защищают от управления чужими ресурсами. Stop выполняет только Compose down собственного проекта, без удаления томов, секретов, образов или снимков. Неудачный запуск оставляет ресурсы для диагностики и отдельного Stop. Служебные SQL-ошибки не печатаются вместе с запросами, содержащими пароль.

Это локальный HTTP-стенд: он не является схемой эксплуатации или разрешением на публикацию. Правила безопасности проверяются отдельными приёмочными наблюдениями и независимым ревью.

## Исполненная локальная очередь D-316/D-317

DEV-02/DEV-28: 21 unit/integration и 11 FOUNDATION PASS; результат в [dev02-dev28-progress.md](dev02-dev28-progress.md), независимое ревью в [dev02-dev28-review.md](dev02-dev28-review.md). После Start test запускать `scripts/test-foundation.ps1`. Adapter foundation-fixture-bridge.mjs предназначен только для 11 readonly проверок: host process/SQL snapshot текущего run плюс живой HTTP. Wrapper закрепляет SHA guard в памяти и проверяет исходники, snapshot, manifest, контейнеры и Nginx до/после suite; прямой Playwright без guard не является приёмкой. Нет инспектора в приложении и Docker socket в runner.

DEV-04 по D-318: добавлены модели content, миграция content.0001 и 20 PostgreSQL tests (включая 2 конкурентных). Общий unit-набор теперь 41; все прошли вместе с 11 FOUNDATION. Код моделей не включает пользовательские команды DEV-29. Результат: [dev04-models.md](dev04-models.md).

## DEV-03 / D-320–322

Завершено31.10.2026. 75unit,12сетевых AUTH,11FOUNDATION и96harness PASS. Вход /manage/login/, пользователи и права только владельцу. Постоянный owner не создавался, синтетические аккаунты после проверок удалены. Интерактивные create_owner/recover_owner и ограничения среды описаны в [dev03-auth.md](dev03-auth.md); реальный пароль в argv/env/чат не передавать. Для 12AUTH на активной test-среде использовать scripts/test-auth.ps1; он временно включает auth_isolated clock/two-IPhelpers и обязан вернуть local_http/убрать собственные данные. Сетевые режимы не запускать параллельно из-за общего scratch.
