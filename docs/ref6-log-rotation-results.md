# REF-06D — результат стандартной ротации технических логов

Дата: 2026-11-06. Решение: D-643. Приёмочный контракт: ROT-001–008 из `docs/ref6-log-rotation-plan.md`.

## Результат

Для четырёх постоянных foundation-контейнеров `app`, `db`, `ingress`, `media-worker` явно настроен стандартный Docker logging driver `json-file` с `max-size=10m` и `max-file=3`. One-shot `state-init`, `init`, `migrate`, `units` настройку не наследуют.

Это ограничивает технические stdout/stderr примерно 30 МиБ на контейнер без отдельной log-платформы. Nginx access log остаётся выключен, raw error log — `/dev/null`; AuditEvent, admin UI и retention не менялись.

## Проверки

- `docker compose config`: exact `json-file`, `10m`, `3` только у четырёх runtime services.
- Actual inspect четырёх запущенных контейнеров подтвердил тот же `HostConfig.LogConfig`.
- Synthetic probe без сети, mounts и secrets записал более 35 МиБ. Retained `docker logs` — 26 478 606 символов; oldest marker отсутствует, newest marker присутствует.
- Probe: network `none`, mounts `[]`, exit 0, exact log config; после проверки контейнер удалён и его отсутствие подтверждено.
- App readiness после настройки: `healthy`, failing streak 0, output пустой; focused readiness 3/3 PASS за 1.859 с.
- `makemigrations --check --dry-run`: `No changes detected`; `git diff --check`: PASS.
- Основная локальная test-БД неизменна: AuditEvent 967, pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner pins 1, receipts 396, identities 765.
- Независимое review: `APPROVED`, findings отсутствуют.

Не добавлены Telegram, badges, mark-read/category-delete, новые log sources, Nginx unsafe logs, collector/shipping/search/alerting, service/dependency/volume/scheduler/state machine. Production, VPS и старый сайт не затрагивались. REF-Q004 закрыт.

## Следующая точка

Текущий этап — REF-06/REF-6. Оставшиеся функции требуют отдельных prerequisites: публичный renderer для HTML reserve, дизайн/LEGAL-01 для заявок, destination/key для external backup и отдельное решение о retention AuditEvent.
