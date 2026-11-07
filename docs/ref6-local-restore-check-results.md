# REF-06G — результат изолированной проверки локального restore

Дата: 2026-11-06. Решение: D-659. Приёмочный контракт: RCHK-001–010 из `docs/ref6-local-restore-check-plan.md`.

## Результат

Добавлены закрытый host wrapper `scripts/local-restore-check.ps1` и one-shot helper `tools/foundation_restore_check.sh`. Wrapper принимает только catalog label `current|previous`, работает при `active=false`, удерживает общий foundation/backup lock и до/после проверки сверяет catalog и SHA immutable generation.

Из-за намеренных UID10001/mode0600 backup artifacts wrapper создаёт exact временную копию внутри DACL-closed backup root. Первый pinned network-none `--rm` container под UID10001 имеет только staging RW и ставит копиям 0444. Второй pinned network-none `--rm` container под UID999 получает staging/helper read-only и два bounded tmpfs по 512 MiB для новой DB и media. Ports, secrets, state и persistent Docker volumes отсутствуют.

Helper повторно проверяет SHA, custom dump и tar paths/types до extraction. Временный PostgreSQL cluster использует UTF-8, host auth reject, empty listen_addresses и Unix socket внутри tmpfs. `pg_restore --exit-on-error --single-transaction --no-owner --no-privileges` восстанавливает новую `restore_check` DB; smoke читает schema/table counts и все app tables с quoted identifiers. EXIT/signal trap останавливает PostgreSQL, host finally удаляет contained staging и освобождает lock.

## Проверки

- `current`: `LOCAL_RESTORE_CHECK_OK tables=42 migrations=30 media_files=15 media_bytes=6240`.
- `previous`: тот же успешный результат 42/30/15/6240.
- Active foundation: exit1 `LOCAL_RESTORE_CHECK_UNAVAILABLE phase=preflight` до staging/container.
- Main test DB неизменна: AuditEvent 967, pages 6, revisions 22, states 6, drafts 1, restore stages 3, pins 1, receipts 396, identities 765.
- После тестов: restore permission containers 0, restore check containers 0, restore networks 0, restore volumes 0, staging 0; foundation stopped.
- Catalog неизменен: current `5adf6799-9797-49ac-b2ec-da22ea493868`, previous `818e2c86-6c38-4159-a05f-03e3633c48db`, generations 2.
- PowerShell/shell syntax и `git diff --check` — PASS.
- Независимое code/security/acceptance review: `APPROVED`, P1/P2 отсутствуют.

## Пределы

Это bounded local restore verification, а не production restore или полная disaster recovery. Профиль ограничен 512 MiB DB tmpfs и 512 MiB media tmpfs. Не проверяются будущий request deletion ledger, совместимость с будущей версией кода, HTTP/public smoke, внешний encrypted backup/key, production replacement и rollback. Эти действия требуют отдельных prerequisites и разрешения владельца.

## Следующая точка

Текущий этап — REF-06/REF-6. Следующий инкремент выбирается отдельно: внешний backup требует storage/key, HTML — настоящего public renderer, requests — LEGAL/design readiness. REF-Q004 закрыт.
