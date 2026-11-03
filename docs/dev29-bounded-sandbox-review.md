# DEV-29: независимое ревью ограниченного временного стенда

2026-11-03. **BOUND29-PLAN-REVIEW-002: APPROVED как архитектурное предложение DEV29-Q014.** Не code/runtime approval и не решение владельца. Автор плана — координатор; независимый рецензент `/root/dev29_publication_review` документ не редактировал.

Проверен [BOUND29-PLAN-001](dev29-bounded-sandbox-proposal.md), raw SHA256 `bf9633c9afef1cad5a0b742b1c04ac6c66a39dd4c5e868e1598cfd75d4b2577b`.

## Первое ревью и исправление

BOUND29-PLAN-REVIEW-001 — CHANGES REQUIRED. **BOUND29-REV-001 / P1:** не определён PID1, который оставит контейнер/tmpfs живым при смене bootstrap postmaster на runtime. Обычное завершение postgres как PID1 уничтожило бы временный кластер; неявный shell/supervisor добавил бы несогласованные полномочия.

Координатор добавил immutable `/bin/sh` PID1 с reviewed source/SHA, UID999/CAPdropALL/no-new-privileges, прямыми foreground children и закрытым автоматом INITDB→BOOTSTRAP_SOCKET_ONLY→CLEAN_CHILD_STOP→RUNTIME_TLS→FINAL_CLEAN_STOP. Child clean stop/wait/reap/control proof отделён от final container removal. Host проверяет full container ID/StartedAt/RestartCount0, mounts/nonce/system identifier и transition records. Restart/drift/timeout/unexpected exit дают terminal FAIL без C/T/повторного init. Перечислены негативные signal/orphan/restart/HBA сценарии, ограничен Stop/kill exact owned full ID. **Повторное ревью: REV-001 закрыто.**

## Остальные проверенные границы

- Tmpfs512MiB покрывает parent image VOLUME `/var/lib/postgresql`, не только вложенный PGDATA. Все writable data mounts/внешние WAL/tablespaces/symlinks/anonymous volumes проверяются; original volume не получает новый DB/worker.
- DB memory=memory-swap1GiB, helper256MiB; свежий MemAvailable≥2GiB, проверка swap support, отсутствие изменения Docker/WSL/OOM safeguards. Вместимость1000/139 и отсутствие OOM пока не доказаны; ENOSPC/OOM означают FAIL, не autogrow/retry.
- Сохранены separate persistent budget2GiB и консервативный B+1GiB+256MiB+32MiB+16MiB<2GiB envelope; tmpfs не выдан за физический лимит всего Windows/Docker VM/VHD.
- Original том только в двух закрытых RO inspectors до/после; прежний сервер/архивы не запускаются, новые OID/marker/baseline не имитируют старые. Bootstrap peer/socket-only сменяется exact runtime TLS HBA без fallback. Новые synthetic роли/DB/guard требуют Q014.
- Fixed run/prefix/once INIT/C/T scopes, отдельные RO intents, INIT90с/remaining110с, последовательность C→review→T, true1000/full139 acceptance, preservation/Stop и честные ограничения согласованы внутри предложения.

Новых противоречий не обнаружено. До runtime обязательны ответ Q014, реализация и independent code/QA/start/payload/result gates. Рецензент Docker/SQL/секреты/install не использовал.

Feasibility анализ `/root/pg29_probe_builder` также был только readonly/source: pinned PG18.6 `initdb.c:2548,2955–3014` допускает external WAL path, `tablespace.c:203–226,252,661` — external tablespaces; поэтому их запрет/проверка входят в план. Это не фактический запуск quota/mount проверки.
