# DEV-29: фактический Linux mock QA Q015

2026-11-03. **Все6 сценариев PASS; BOUND29-Q015-ACTUAL-RESULT-REVIEW-001 APPROVED. Квалификация только MOCK_SHELL_ONLY.** Это не INIT/C/T, реальный PostgreSQL/SQL, quota1000/1001, full139 или завершение P29-A.

Исполнен ровно один QA-RESUME-001 по D-436/Q015. Root run `1e23c654-5baf-4b5e-a7b4-6235b1289c0a`, package30 SHA256 `60c6ed015c66a35e12ea39c23f9aa6e6339af857923de2fa63f343858fbf594f`. До выдачи допуска readonly engine/image/inventory и исправленная native ACL проверка прошли. Создан отдельный private prefix с inherited owner/SYSTEM ACL; существующие ACL не менялись. Новые ключи в Git/чат не передавались.

| Сценарий | Результат | Exit контейнера | Frames | Работа контейнера, мс |
|---|---|---:|---:|---:|
| good-term | PASS, clean final proof |0|8|4653|
| good-int | PASS, clean final proof |0|8|2942|
| good-hup | PASS, clean final proof |0|8|3902|
| runtime-exit | PASS, ожидаемое отклонение unexpected exit |1|8|4592|
| bootstrap-sql-timeout | PASS, ожидаемое отклонение таймаута **заглушки** |1|4|17063|
| ignore-stop | PASS, ожидаемое отклонение неподтверждённой остановки child |1|9|14789|

Отрицательные сценарии действительно завершались FAIL внутри supervisor; PASS означает, что host QA распознал правильный отказ и очистил контейнер. Это не эквивалентные ошибочные повторные попытки: каждый сценарий выполнен один раз в отдельном контейнере. Во всех6 OOMKilled=false. Продолжительность получена из actual StartedAt/FinishedAt, не из модели.

Реальные shell/procfs/signals/wait/timeout выполнялись в локальном Docker Engine29.9.2, daemon `18f3b425-a862-4cbe-ba14-438caef2aab2`. При этом **все5 PG binaries заменены инертными readonly Perl substitutes**, networknone, UID999/no caps/rootfsRO, memory=memory-swap256MiB, bounded tmpfs/loggingnone. Supervisor/host gates проверили mounts/config, primitive process continuity и закрытые stdout frames. QA inputs — public dummy strings, не настоящие пароли/cert/key. Реальные initdb/postgres/psql, SQL и original volume не использовались.

## Подписи и сохранённые доказательства

- Intent scope `BOUND29-INERT-LINUX-QA-RESUME-001`, raw/stable SHA256 `03b29b0c44e91f050e26a61999a0b8fc52c31e3cdca52c99d7f6c9105aaa4552`; TTL900000ms, remaining при attempt888329ms≥700000ms. HMAC/owner Q014+Q015/review/package links проверены независимо.
- Once attempt raw SHA256 `546fad0852bcd5f8b0a5ea1feb068187099e81f05f16132189dd499343edd379`; key/intent после issue не менялись, nonce/expiry не продлевались.
- Signed result file raw SHA256 `601a4989ad8d50723f02f076316eee25208e720a5bd88a137c6b42b87b81fb18`; canonical payload SHA256 `b65089a97ee6e3f01559799f0a247b272b2399ebb289852386d84034427e4f94`. Result HMAC проверен без вывода ключа.
- Все6 уникальных full container IDs связаны с before/after inspect hashes, private capture/raw SHA и cleanup receipt/raw SHA в подписанном результате. Исторические stopped/removed/absence proofs проверены; сокращённые имена не подменяют ID.
- Final inventory receipt canonical SHA256 `d190e2e7107c1605c9cd21d5c107559462ea232d00349be50b3920c5f30a61bd`; private `{receipt,raw}` file raw SHA256 `7462edbc1d81e42ddeab1cbbacf2cbc5d07d445b2320c464787fb450682c3784`. Receipt связывает тот же daemon/run-label с0 IDs. Это два разных хеша по двум разным объектам.

Private raw/inspect/cleanup/inventory/key остаются только в ignored закрытом `work/dev15-20261102/private/bound29-1e23c654-qa-resume001/`; public intent/owner/review/attempt — в ignored `work/dev29-bounded-20261103/qa-resume-001/qa-run/`. В Git — только этот summary и ревью, без raw logs/ключей.

Все собственные QA containers удалены, новых network не создавалось. Старый package `b23f889c…`, intent `4b348ef0…`, старые ключи/expiry не переписывались; old attempt по-прежнему отсутствует. Residual source/ancestry Verify сохранён, старые5+8 PostgreSQL probes не повторялись. Свежий SQL/hash original DB/тома здесь не заявляется: том не подключался.

## Дальше по Q014

Снята только неопределённость shell/mock lifecycle. Подготовить отдельно реальные INIT/C/T helper/controller, closed readonly audit+target/role/system identity, guarded migration/reuse-existing runner и настоящий1000-loop; затем code/QA/start/payload/result gates. До их прохождения реальный SQL не запускается. Повторно согласовывать уже разрешённый Q014 профиль при неизменном объёме не требуется.

DEV-29 около35%, этап8 «Разработка сайта» около31%; P29-A открыт, далее P29-B/C/D/E. Общий этап9 после этапа8. Старый сайт/VPS/production/push не затронуты.
