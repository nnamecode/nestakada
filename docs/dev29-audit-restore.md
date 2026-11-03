# Q007: восстановление временных ресурсов после штатного Stop

2026-11-03. Статус: **Q008 разрешён D-419 и выполнен; RO volume inspector/DB-only restore/Audit/cleanup PASS, независимое итоговое review APPROVED**. [Результаты](dev29-readonly-audit-results.md), [итоговое ревью](dev29-readonly-audit-review.md). Ниже сохранены принятый план и исходные факты; повторного ответа Q008 не требуется.

## Свежие факты

- source SHA всех7 audit-модулей совпали с audit-prepared-source.json, controller Verify существующего run PASS/runtimeAdmitted=false;
- Docker desktop-linux: Linux/29.9.2, engine ID18f3b425-a862-4cbe-ba14-438caef2aab2; sandbox pipe denial устранён штатным require_escalated, затем чтение успешно;
- TRUST containers по точному compose project:0; TRUST networks по label и по имени nestakada-trust-test:0;
- том nestakada-trust-test-dbdata существует, driver local, labels scope=trust-test/project=nestakada-trust-test/volume=dbdata;
- все3 pinned image IDs из plan.json присутствуют Linux/amd64; pull/build не выполнялись.

Полные CLI результаты сохранены в контексте выполнения; никакого содержимого БД/секретов не выводилось. Наличие тома не является свежим доказательством SQL-сохранности или правильности data directory. Объекты не создавались, том не монтировался/не изменялся.

Причина ожидаемого отсутствия временных ресурсов подтверждается tools/local_trust.mjs: Stop вызывает compose down без удаления тома. При этом пункт A.2 dev29-runtime-admission-plan.md требует остановиться при отсутствующей сети. Поэтому несмотря на Q007 восстановление не выполнено автоматически. Это уточнение недоработанного плана, не новая архитектура сайта.

## Предлагаемое уточнение границы

Вместо требования наличия всех временных сетей/контейнера разрешить **единственное восстановление ранее объявленных compose-ресурсов** вокруг точно существующего тома:

1. Не менять исходный compose/env/manifest, source/config hashes, images/secret/permit/runner guard. Сначала Verify и ownership/наличие точного тома и images. Любой отсутствующий том/image или чужая сущность с тем же именем — STOP, без создания замены.
2. До первого writable DB-start проверить существующий том bounded одноразовым helper из уже принятого PostgreSQL image, network=none, rootfs read-only, volume read-only с volume-nocopy, cap-drop ALL/no-new-privileges, прежний helper cap256МиБ/.5CPU/PIDs64. Только fixed data-directory metadata/PG_VERSION/control-file/наличие уже инициализированного cluster; не печатать файлы данных, ключи, строки или рекурсивный список. PGDATA взять из проверенного image config, проверить абсолютный путь внутри /var/lib/postgresql, не конструировать SQL/команды из непроверенного текста. Entry point только read-only inspector, не docker-entrypoint/initdb. При недоказанной инициализации/версии/path — STOP, не запуск DB и не initdb.
3. Разрешённые временные network names только nestakada-trust-test-db, -api, -client из неизменённого environment/trust/compose.yaml, все internal=true/scope=trust-test. Никакой другой сети/host port. Compose может создать перечисленные unused internal networks; это допустимо лишь в этом точном восстановлении, затем удаляются собственные временные сети без данных. Постоянных новых топологий нет.
4. Запустить **только db** прежним compose/env/project, --no-deps/--no-build/--pull never. Ни Start/Tests/Calibrate/ArchiveUnit существующего runner, ни init/migrate/API/ingress/working writer не вызываются. Перед writable start обязательна проверка п.2, иначе standard postgres entrypoint потенциально мог бы инициализировать пустой том.
5. Зафиксировать полные новые container/network IDs, actual mounts/image/entrypoint/config/caps512МиБ/.5CPU/PIDs128, отсутствие публичных портов и чужих endpoints. Стартовое копирование TLS-key в tmpfs — только штатное поведение неизменённого db-start.sh; секрет не попадает в output. WAL/recovery/статистика могут меняться как при обычном старте PostgreSQL; прикладные записи MAIN не выполняются.
6. Дальше **продолжить существующий Q007 без нового согласования**: принятый signed preflight producer → независимая сверка exact observation/payload → один audit-only signer → один read-only Audit → независимое result-review. Никаких runtime-admission/Run/fixture writes.
7. В finally остановить и удалить только свои вновь созданные DB/helper containers по полным ID+labels; свои восстановленные пустые internal networks удалить только после подтверждения отсутствия endpoints, чужие не трогать. Том никогда не удалять/переименовывать, compose down -v запрещён. Вернуть исходное состояние0контейнеров/0сетей при сохранённом томе; все phase/receipt/failure artifacts оставить. Если остановка/проверка backend/сохранности не доказана — FAIL/PRESERVATION_UNPROVED, не автоповтор/удаление ledger.

Реализация точного inspector и цепочки восстановления перед запуском проходит независимое code/QA-review и offline негативные проверки; документационного approval недостаточно для непроверенного inline shell. Остальные принятые9+7 source SHA не переписываются, новые helpers отдельные и связываются с run/provenance. Ошибки останавливаются по прежним правилам AGENTS; параллельные запускающие агенты запрещены.

## DEV29-Q008

Разрешить это ограниченное восстановление только прежних temporary compose-ресурсов с обязательной read-only проверкой сохранённого тома перед стартом, затем продолжить уже разрешённый Q007 Audit и вернуть исходное stopped-состояние? Никаких новых логических сетей/томов/образов/миграций/тестовой записи/Run/старого сайта/VPS/production/push.

Отдельный ответ нужен только потому, что прежний Q007-план прямо предписал STOP при отсутствующей сети. Общая архитектура/способ Audit/Q007 повторно не согласовываются. Пока ответ не получен, выполняются только чтение метаданных и подготовка предложения, не восстановление. DEV-29 около35%, этап8 около31%.
