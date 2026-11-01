# DEV07-SJR — журнал: локальный результат

2026-11-01, D-350 при сохранённых D-347/D-349. DEV-07 около96%, этап8 около20%. **Закрытый immutable journal primitive реализован и проверен. Сохранение Header/Footer ещё выключено:** координация pending операции, reconciliation и достаточный численный резерв остаются следующей частью SH3. Старый сайт и VPS не затрагивались.

## Изменение

Новый `shared_content.journal.SharedJournal` создаёт, повторно подтверждает и читает закрытый `journal/<operationuuidhex>.json`. Ровно11 полей, canonical UTF8 JSON≤4096Б, фиксированный unvetted профиль, строгие UUID/числа/хеши. Unknown/duplicate fields, некорректная или неполная запись не превращаются в нулевой резерв. HTML, пароли и CSRF в book не входят.

Создание O_EXCL не перезаписывает файл. Exact replay подтверждает тот же book; изменённый book под прежним ID даёт конфликт. На file fd действует nonblocking flock, удерживаемый до окончания проверок имён каталогов и закрытия contexts. Каждый успешный create/read/replay заново подтверждает fsync файла и цепочку journal→shared-content→private→pre-existing MEDIA_ROOT, включая восстановление после прежнего сбоя между mkdir и fsync родителя. Частичные файлы не удаляются автоматически и остаются в scanner либо вызывают безопасный отказ измерения.

В storage.py добавлены только закрытые journal helpers. Команды сохранения, admission, модели и миграции не изменены; новых программ/томов/ресурсов нет. Возвращаемые profileAvailable=false и heldAuthority=false обязательны: durable book подтверждает лишь эту запись, не достаточность резерва или результат SQL-операции.

## Факты

| Проверка | Результат |
|---|---|
| Новый journal набор |13PASS10.651с:11 FS/process методов и2 PostgreSQL/framework HTTP |
| Полный shared_content |**65PASS215.130с**, включая эти13 и прежние52; не78 уникальных |
| Start/Stop |exit0; No migrations to apply; стенд остановлен, active=false |
| Source |203файла, drift0; run cbe4731d-6172-4b55-9552-957d52b52b4e |

Frozen manifest SHA256 `a0a6956bd48d86f8f97c26a6e4e6ebf6977209519060d584c67bc0f73e288e7b`. Product journal SHA `6916e91bbb369cdb06104113411e41fbaa29e132fdaca5b30464e1e3ec2ec512`, storage `c618f87aec7147229084ab317a5b3c03e4f6fe3e20ff0e9f439402ea7aa5e67b`, QA `7258ad6fdb82b28c2139a8c0698bb33f479056beed173ac038cd3cf17c10a961`.

От предыдущего201-file cohort изменён только storage.py, добавлены journal.py и test_shared_journal.py; удалений нет. Исторические402 общие регрессии не повторялись. Все65 относятся к текущему203-source и прежнему согласованному image782f53c4…/пределам контейнера; новые инструменты не устанавливались. Нет нового модельного изменения, отдельный makemigrations не повторялся; actual migration cases входят в65.

## Проверенный конечный набор SJR-001–005

- Настоящие bytes/SHA/0600/UID/nlink/UUID-name binding, строгие поля/типы/JSON и raw4096/+1; фактические fsync цели сверяются по FD dev/inode, дескрипторы закрываются.
- Exact replay сохраняет inode и выполняет свои barriers; изменённые bindings конфликтуют без overwrite. Второй настоящий fd не может получить kernel flock на последних named guards, а после return получает его.
- Два настоящих ограниченных Python-процесса: writer остановлен на partial write с удержанным lock, contender получает BUSY; после завершения writer проверен fresh replay, оба процесса reaped.
- Реально достигнутые partial/file/ancestor-fsync faults, повторное подтверждение всей цепочки новым instance, подмена journal при read/write, symlink/hardlink/FIFO/mode отказы. Остатки сохраняются, чужой baseline не меняется.
- Durable book сохраняется после отдельного SQL rollback и завершения собственного writer; business state/receipt не появляются. Реальные draft/apply/restore с валидным book всё ещё503, DB/FS manifests неизменны.

Независимый `/root/combined_review` проверил контракт92463fdc…, product/QA до запуска, фактические13/65, все203 hashes и delta. Блокеров ограниченного primitive нет. Это injected faults и orderly process exit, **не испытание host powerloss**, глобального held-total или восстановления DB+FS после аварии. Нативный UI/Nginx/публичная композиция не проверялись этим набором.

## Продолжение внутри этапа8

Следующий шаг SH3 — связать book с единственной pending операцией под общим content domain, доказанным receipt/outcome и безопасным reconciliation/release. Затем откалибровать достаточный запас для реальных операций и пройти75%/256МиБ/10000/concurrency/fault corpus. Правило успешного commit≤256МиБ и10000 сохраняется, warning75% не блокирует допустимую запись. Профиль не включать по одному факту journal PASS.

Также открыты положительные Draft/Apply/restore/cancel, полные dirty/nonce UI проверки, ручная очистка и остальные DEV-07 матрицы. Сценарии и ревью до кода сохраняются, дополнительное разрешение только ради очередного исполнения D-347/D-350 не добавляется. Production и старый сайт/VPS этим результатом не разрешены; перехода к этапу9 нет.

До правок145 прежних dirty/untracked файлов скопированы и сверены SHA256: work/dev07-journal-20261101/before, backup-paths.json. Там же start-first.txt, journal-first.txt, shared-first.txt, stop-final.txt и final-checks.json. Логи/секреты/синтетические данные остаются вне Git. Стенд остановлен с сохранением штатных томов, push не выполнялся.
