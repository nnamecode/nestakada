# REF-06G — изолированная проверка локального restore

Дата: 2026-11-06.
Основание: D-593, D-598, D-600, D-601, D-656, DEV-23.
Статус: завершено по D-659; независимое review — `APPROVED`.

## Граница

Добавить закрытый host wrapper, который проверяет выбранное catalog generation `current` или `previous` из REF-06F. Wrapper работает только при остановленном local foundation, удерживает тот же per-environment lock и запускает два pinned one-shot containers без сети, портов, постоянного volume и секретов. Первый видит только временную staging-копию и под UID10001 меняет её container-mode с сохранённого 0600 на read-only 0444; второй под UID999 видит staging только read-only и выполняет restore. Immutable generation никогда не монтируется writeable.

В контейнере два bounded tmpfs: до 512 MiB для новой PostgreSQL data directory и до 512 MiB для распакованного media. PostgreSQL слушает только Unix socket внутри контейнера; local auth trust допустим только в этом network-none одноразовом процессе, host auth reject. После проверки `--rm` удаляет весь restored DB/media state.

В инкремент не входят production restore, замена основной DB/media, внешний backup, ключ/шифрование, расписание, автоматический rollback, request deletion ledger до появления заявок/LEGAL, Django UI/command и проверка публичного сайта.

## Приёмочные сценарии

- **RCHK-001 — только catalog generation.** Разрешены literal `current|previous`; strict catalog указывает два разных canonical UUID, generation directory/manifest совпадают, exact четыре artifact files и SHA-256 проверяются host-side до Docker.
- **RCHK-002 — остановленный foundation.** Manifest должен иметь `active=false`; общий lock удерживается весь check и блокирует backup/foundation state actions. Несоответствие закрывается до container creation.
- **RCHK-003 — изоляция.** Два `--rm` containers с network none/read-only root/cap-drop ALL/no-new-privileges/bounded resources. Permission step работает UID10001 и имеет единственный RW mount временного staging; restore step работает UID999, staging/helper bind read-only и только два data tmpfs writeable. Ports/secrets/state/persistent volumes отсутствуют.
- **RCHK-004 — безопасный архив media.** До extraction повторно проходят SHA и tar list; разрешены только `media`/`media/...`, только directories/regular files, без absolute/`.`/`..`/links/devices. После extraction `find` подтверждает тот же типовой предел.
- **RCHK-005 — новая DB.** `initdb` создаёт новый кластер UTF-8 с local trust/host reject; PostgreSQL запускается с empty listen_addresses и единственным Unix socket; создаётся только новая `restore_check` DB.
- **RCHK-006 — атомарный restore.** `pg_restore --exit-on-error --single-transaction --no-owner --no-privileges` восстанавливает custom dump; failure не оставляет host/container state после `--rm`.
- **RCHK-007 — bounded smoke.** Проверяются schema `app`, наличие и ненулевой счёт `django_migrations`, ненулевой счёт user tables и читаемость всех table counts; результат раскрывает только агрегаты tables/migrations/media files/bytes.
- **RCHK-008 — deterministic stop.** EXIT trap останавливает временный PostgreSQL при success/failure; helper не оставляет child process. Host получает ровно safe success либо safe phase failure, без SQL/table/media names, DSN или exception text.
- **RCHK-009 — ничего не восстанавливает в рабочее окружение.** Main DB/media/catalog/generations побайтно не меняются. Host staging создаётся только внутри закрытого backup root, содержит exact четыре проверенные копии, удаляется в `finally`; startup удаляет только contained `.restore-staging-<uuid>`. Контейнеры/сети/volumes не остаются. Это restore verification, не production restore.
- **RCHK-010 — честные пределы.** 512+512 MiB tmpfs — локальный bounded profile; overflow даёт safe failure. Request ledger, migrations compatibility с будущим code и HTTP smoke станут отдельными prerequisites, поэтому результат не называется полной disaster-recovery проверкой.

## Проверки

Static syntax/security checks, реальные current и previous restore-check, ожидаемый отказ при active foundation, container/mount/network inspection при необходимости, unchanged catalog/generation SHA и main DB counts, отсутствие residual containers/networks/volumes, `git diff --check` и independent review. Production/VPS/старый сайт не затрагивать.
