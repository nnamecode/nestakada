# PostgreSQL 18.6 без XML/XSLT: локальная инфраструктурная сборка

Основание — D-314 и согласованный TEST-Q009/D-315, 2026-10-30. Это сборка сервера БД и проверочные синтетические данные, не код сайта. Прежние образы и тома не удалялись и не подменялись. Старый сайт/VPS/Windows-службы не затрагивались.

## Что изменено

`environment/foundation/Postgres.security.Dockerfile` собирает PostgreSQL **18.6** из официального release-архива на **Debian trixie/glibc**, отключая необязательные SQL XML/XSLT. В чистый runtime не попадают libxml2/libxslt и компиляторы. Это убирает соответствующий XML-парсер из работающего PostgreSQL, а не скрывает его advisory.

Сохранены OpenSSL, ICU, LZ4, Zstd, readline, PL/pgSQL, обычные типы и собираемые core/contrib. Внешние PL/Python/Perl/Tcl, LLVM JIT, GSSAPI/LDAP/PAM и UUID-OSSP не включались; встроенный UUID PostgreSQL не зависит от UUID-OSSP. Эти необязательные возможности не выдаются за сохранённые. Штатный entrypoint получен из закреплённого официального образа PostgreSQL. `gosu` и системные библиотеки — из подписанных Debian-репозиториев.

Bare image CMD — `postgres`, то есть штатная закрытая настройка listen_addresses. Для собственного испытания использовано явное `postgres -c listen_addresses=* -c max_connections=30 -c log_statement=none` **только в своей internal-сети без host-портов**. Это не production-конфигурация и не разрешение публиковать БД.

## Источники и фиксированные артефакты

- [Официальный source PostgreSQL 18.6](https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2), SHA256 **555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f**, сверенный с upstream `.sha256`.
- Base `debian@sha256:1e1a22175fbf1b32157ddaf0219e1db4e5401fab2b94ed285add64d18587cd2d`, linux/amd64; выбран из base annotation официального stock PG18.6-trixie.
- Entrypoint из `postgres@sha256:f4b419e350fd98d4a8429603295208976dea4c8fb8326d818d346d3e29f1db6f`.
- 82 записи build/runtime `.deb` имеют точные Package/Version/Architecture/SHA256 и были сопоставлены с APT-метаданными после успешной проверки подписанных InRelease/index штатным APT. Дальнейшая установка и сборка — offline. Не использовались `--allow-unauthenticated` или `dpkg --force-depends`; после установки проверен пустой `dpkg --audit`.
- Источники/зависимости, `inputs.sha256`, исходные APT-метаданные: `work/foundation-security-20261030/pg-context/`. BuildKit provenance: `pg-build-metadata.json`; итоговая identity: `pg-artifact.json` в родительской области.

Точные системные версии runtime: glibc/locales **2.41-12+deb13u4**, ICU **76.1-4**, libssl/OpenSSL **3.5.7-1~deb13u3**. Последняя — версия с vendor-backports, не вывод об исправлении по одному upstream version string. `pg-runtime-packages.tsv` содержит 86 фактически установленных binary/source-пакетов. PostgreSQL собран из source и учитывается отдельным компонентом, а не фиктивным установленным Debian-пакетом.

Состав и рецепт закреплены; битовая идентичность двух независимых clean-build не заявляется. Нашу сборку потребуется пересобирать и проверять при обновлениях PostgreSQL/зависимостей.

## Проверки и границы результата

Первичная сборка прошла **231 core SQL regression test upstream** (`make check` не от root). Обычные данные (кириллица/ё, numeric, JSONB, timestamptz), pgcrypto/pg_trgm, CREATE/CRUD/права, SCRAM, настоящий TLS 1.3 с verify-full и pg_dump/pg_restore проверены на собственном новом томе. XMLPARSE, cast в XML и XPath получили ожидаемый `feature_not_supported` (SQLSTATE 0A000). Отсутствие парсера проверено и по пакетам, и по `ldd`.

Locale/datcollversion/actual version и весь контрольный корпус порядка/lower/upper совпали с исходным stock PostgreSQL18.6-trixie. Это характеристическая регрессия, не новое бизнес-правило сортировки и не доказательство всех возможных locale-сценариев.

После пересоздания собственного контейнера при сохранении named volume и image сохранились контрольные данные и TLS; PID 1 работал UID999, CapEff=0, NoNewPrivs=1. Initial bootstrap имел только нужные chown/setuid/setgid filesystem capabilities; работающий postgres их не сохраняет. Контейнер с readonly root, собственными tmpfs и отдельным volume, без host-портов. Компиляторы отсутствуют, реальные postgres/pg_dump/pg_restore сообщают 18.6.

При последующей ELF-проверке первичного source-бинарника выявлены отсутствующие SSP и BIND_NOW. Он **не принят как финальный**. Рецепт дополнен стандартными `dpkg-buildflags` с `hardening=+all`: SSP/stack-clash/CET, FORTIFY и full RELRO/NOW. Финальная пересборка повторно прошла 231 upstream core SQL test; результат не суммируется с первым прогоном. ELF исполняемого postgres подтвердил импорт stack-protector, full RELRO/BIND_NOW, NX и PIE. Командные флаги сохранены отдельно; аппаратное исполнение CET отдельно не проверялось.

Это не прохождение AC приложения, не тесты production TLS, не общий аудит всех уязвимостей ОС. Однодневный CA и ключ нужны только своему fixture; ключ остаётся внутри собственного PG volume, пароли — в `pg-private` с Windows ACL owner+SYSTEM. Они вне Git; production-секретов здесь нет.

## Уточнения подготовки и исправленные ошибки

1. После успешной загрузки `.deb` ненужный завершающий shell-loop остановился на интерпретации `${Package}` с set-u. Повторная загрузка не делалась; metadata извлекались `dpkg-deb -f` отдельно.
2. Финальный cp InRelease из временного shell-файла получил CR в конце пути. Данные/хэши были уже извлечены; копирование подписей выполнено отдельной командой без CRLF.
3. После успешного source build/test ошибочный COPY несуществующего `regression.out` остановил экспорт. COPY удалён, использовано сохранённое свидетельство build log, компиляционный cache сохранён.
4. Docker cp-запись pgpass в readonly container была отклонена. Вместо ослабления readonly пароль передан по stdin пользовательскому exec в writable tmpfs с umask077.
5. Runtime-роль правильно не имеет TEMP. Проба первоначально пыталась агрегировать результаты в TEMP-таблице; исправлена на несекретные сессионные параметры, права не расширялись.
6. Запись итогового JSON обычным sandbox-вызовом получила EPERM; разрешённая запись повторена через scoped escalation без изменения Windows ACL.

Эквивалентных повторов этих действий без новых условий не делалось. Ошибки инструмента/проб не объявляются дефектами или успешными проверками PostgreSQL.

Последние сборки выполняются с `--file environment/foundation/Postgres.security.Dockerfile`; сохранённая `pg-context/Dockerfile` — историческая невыполняемая копия первого запуска. Это учитывается при проверке фактически использованного рецепта/provenance.

## Итог последней hardened-сборки

Готов локальный артефакт `nestakada-local/postgres:18.6-security-20261030`:

- **Docker-reported image ID и exported image digest:** `sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7`. В текущем containerd-store это не следует называть OCI config digest.
- SHA256 актуального рецепта: `f6eb187d464201e35501b31a86fe15bec7fa50dae55c5137cf8ed0be0fb9ddcb`.
- Основные identity/source/manifest pointers: `work/foundation-security-20261030/pg-artifact.json`. Старый `1171d32a…` сохранён в `pg-artifact-initial.json` только как история и не является финальным целевым образом.
- Финальный лог сборки/231 теста: `pg-build-hardened.txt`; все стадии выполнялись без сети после получения проверенных артефактов.
- Финальные реальные результаты: `pg-evidence/hardened-runtime.json`, `xml-negative.json`, `locale.json`, `elf-hardening.json`, `dump-restore.json`, `persistence.json`, `container-before-recreate.json`, `container-after-recreate.json`, `process-status-after.txt`. Первичные свидетельства архивированы в `pg-evidence-initial/`.

На конечном image повторены выбранные XML/locale/типовые/contrib/TLS проверки, dump/restore и пересоздание с прежним собственным fixture-томом. Набор locale/case/order снова точно совпал с исходным reference. Координатор отдельно подтвердил успешную интеграцию конечного hardened C-адаптера с конечным PG: TLS verify-full, SCRAM, обычные данные и отрицательные проверки; её свидетельство находится в общей evidence-области, не подменяется нашими psql-пробами.

Контейнер `nestakada-pgsecurity-20261030-server` **выключен**, что подтверждено `pg-evidence/running-after-shutdown.txt=false`. Свой volume `nestakada-pgsecurity-20261030-data`, сеть и секреты сохранены. Старые dev/test-тома не использовались. Никаких изменений сайта/VPS/автозапуска/системных настроек Windows нет.

Исправлено целевое присутствие SQL XML/XSLT-парсеров и недостающее hardening нашей сборки. Это не общий вывод «всех CVE больше нет»: vendor-unimportant/неисправленные записи других системных компонентов остаются предметом общего реестра применимости и выпуска. Верификация приложения/production отсутствует. Независимое ревью артефакта выполняет другой агент; этот документ сам по себе не является независимым заключением.
