# Проверенные локальные базовые образы

Основания: D-311, D-313, D-314, D-315. Это инструменты подготовки основы, не приложение сайта.

Текущие образы выбираются из **runtime-images.lock.json**. **images.lock.json содержит upstream build materials** и не должен использоваться как список готового runtime. Docker-reported image IDs и OCI config/export digests хранятся раздельно.

Рецепты:

- `Python.security.Dockerfile` — Python3.14.10/Django5.2.18/psycopg[c]3.3.6, системная libpq17.11 и patched Debian OpenSSL; compiler только в builder, PSYCOPG_IMPL=c.
- `Postgres.security.Dockerfile` — source PostgreSQL18.6 без SQL XML/XSLT, Debian/glibc, core+contrib, ICU/OpenSSL/LZ4/Zstd. Стандартные клиенты pg_dump/pg_restore включены.
- `Nginx.security.Dockerfile` — Nginx1.30.6, удалены неиспользуемые dynamic modules/curl и orphan libraries. Требуется явный entrypoint=nginx и отдельная readonly конфигурация; `nginx-preflight.conf` относится к сетевому маркеру, не к готовому сайту.

Входы компиляции/пакеты берутся из соответствующих *-inputs.lock.json и source-archives.lock.json. Холодная подготовка сначала восстанавливает публичные артефакты по точным версиям/хэшам и проверяет подписанные vendor metadata; затем выполняется offline build. Сохранённые Linux `.deb`, wheels и source archives лежат на T: в игнорируемом work. Компиляторы/сервисы Windows не устанавливаются.

Определение сборки всегда задаётся явно `docker buildx build --file environment/foundation/<рецепт> ... <отдельный подготовленный контекст>`. Исторический Dockerfile внутри work-контекста не использовать по умолчанию. Корень репозитория и секреты не являются build context. Пересборка должна обновлять hashes/identity/receipts и проходить применимые проверки; менять tag без проверки ID недостаточно.

Runtime-конфигурация и секреты остаются отдельными: internal app/db сети, loopback только у ingress, nonroot/read-only/capDropALL/no-new-privileges, собственные scoped тома/tmpfs. PG имеет ограниченный bootstrap, после него сервер работает от postgres999; network listener задаётся явно только в своей internal-сети. Тестовые CA/ключи и пароли никогда не включаются в образ/Git; однодневный CA из preflight не переиспользовать.

Инвентарь компонентов — runtime-components.cdx.json, результаты advisory — advisory-dispositions.json и docs/base-image-advisory-results.csv. Ненулевой vendor-остаток сохранён явно, zero-CVE/production-ready утверждения нет.

Фактические испытания и границы: [итог исправлений](../../docs/base-image-security-remediation.md), [сборка PG](../../docs/postgres-security-build.md). Код сайта и развёртывание требуют отдельных разрешений.
