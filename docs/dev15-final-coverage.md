# DEV-15: итоговая матрица локального покрытия

2026-11-03, D-401/D-402. FC15 завершён; **независимое итоговое completion-review принято; DEV-15 готов локально**. DEV-15 готов локально100%, этап8 около31%. Источник обязательных условий — [RP15-001–020](dev15-runtime-verification-plan.md), не исторические списки остатка в ранних отчётах.

Исходники текущего принятого компонента:30Python-файлов, SHA `014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672`; schema `4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7`. Полные131регрессия на этом source приняты, skipped0. Старое capacity-свидетельство5fbcb9… переиспользуется только для29неизменных серверных файлов по принятой EV15 provenance; consumer проверен отдельно на новом source. Это не новый прогон.

| ID | Принятые доказательства | Оценка и граница |
| --- | --- | --- |
| RP15-001 |131регрессия; additive0003/legacy preservation; операторский before/after [AD15](dev15-local-admission-results.md) | Покрыто локально: исходные миграции/данные/identity сохранны; миграция сама запись не включает. |
| RP15-002 |131: signed closed-envelope/SQL0/cgroup/under-lock reread; [EV15](dev15-evidence-results.md); RL15 disabled/stale lease | Покрыто совокупностью. ENV и подпись без остальных условий запись не разрешают. |
| RP15-003 |131 activation/rollback/DB append-only; AD15 Prepare/Activate/Retry | Покрыто: одна policy, один Head advance, тот же receipt при точном повторе; старые строки/pin неизменны. |
| RP15-004 |131 test_rp004_old_trial_mode_is_retired_under_head_lock и valid signed legacy trial | Покрыта старая trial-ветка на текущем серверном source; режим/старый lease не откатывают policy. |
| RP15-005 |131 новыеUUID/roles/CAS/concurrent/overlap/replay/completion; RL15 настоящие prepare/UNKNOWN/committed | Покрыто локально. Нет необходимости повторять каждый конфликт через каждый транспорт. APP workflow отдельно. |
| RP15-006 |131 test_rp006_lease_restart_no_new_policy_and_latest_revision_authoritative и test_rp006_sixteen_revisions_keep_history_and_refuse_seventeenth; RL15 Restart/новыйCID/inode/lease | Restart/latest policy и отказ17-й revision подтверждены. **F15-001 подтверждён FC15-001/002:** после отказа17-й history16 неизменна, read_head/status/manifest/page работают, новый prepare/completion/точный replay успешны. UNITservice, не новая MAIN policy. |
| RP15-007 |131 full-state-v2/every persistent field/streaming/v1 rejection; [RF15](dev15-recovery-results.md); policy16 отдельно | Full digest/fence/activate/replay/oldkey/proof/exclusion/seed reserve и фактические4receipts покрыты. RF15 credentials5, не20. Предел20 присутствует в state_v2/bounded и консервативен: bootstrap configuration≤16, каждый новый credential требует activate из≤4receipts, то есть≤2добавлений; без внешнего вмешательства насыщение20 не объявляется выполненным. Численное доказательство принято независимым gap-review; насыщение20 не заявляется. |
| RP15-008 |[Capacity gates](dev15-capacity-gates.md), capacityA/B и LG15 legacy | Реальные1000operations/4096refs/1024tombs и следующие отказы; legacy входит в учёт. Принят составной LG semantic PASS + wrapper smoke, исходный hostFAIL сохранён. |
| RP15-009 |CapacityA и131 quoted256redirect wire-limit negative | Допустимые256keys/2048UTF8, точный case/query/Unicode; неверныеDTO отклоняются целиком. Не обещать256redirect с двумя полными2048байтными путями в1МиБ. |
| RP15-010 |CapacityA reserve16772006+8194>16777216;131 combined64MiB/policy/fence accounting injection | Покрыто в согласованной области.64МиБ — accounting injection, не физическое заполнение диска. Completion/replay используют сохранённый резерв. |
| RP15-011 |CapacityB mixed5120; полныйv2; [WT15](dev15-worker-tls-results.md)54/54requests за26.060125с | Покрыто одним принятым полным TLS-прогоном внутри30с. Произвольная нагрузка/другая площадка не обещаются. Старый TLSFAIL сохраняется. |
| RP15-012 |[RA15](dev15-resource-results.md) observed+reserved317325492байта<2ГиБ; отдельные accepted cgroup WT15/RL15/RB15/RF15 | Покрыто в измеренных периодах; это не hardquota и не сумма одновременных пиков. FC15-004 обновил финальное наблюдение: 337303077байт вместе с резервами <2ГиБ; RA15 остаётся прежним отдельным периодом. |
| RP15-013 |[RL15](dev15-runtime-lease-results.md) full UNKNOWN POST/headers/no body, SQL/status, exact retry | Покрыто: потеря чтения response body, тот жеUUID/receipt, один переход Head. Не kernel packet loss. |
| RP15-014 |RL15 terminal lost body/SQL/status/exact replay;131 other-terminal refusal | Покрыто terminal-переходом отдельно от prepare. |
| RP15-015 |RL15 partial POST/no operation; [PV15](dev15-privacy-results.md) serverbody EOF10с; [RB15](dev15-rollback-results.md)SQL22012/ENOSPC/rollback/retry; startup closed в131 | Составные transport/service доказательства. Authoritative503/неопределённыйtransport не дают готовый snapshot/HTML. Клиент удаления APP с сохранениемUUID ещё не реализуется вDEV-15: это DEV-29, нельзя приписывать ему PASS. Составная локальная граница принята независимым gap-review; APP workflow остаётся будущим. |
| RP15-016 |[LD15](dev15-load-results.md) actualendpoint4+пятый429, отдельный Nginxactive4, pipeline48/11accepted37rejected, recoverycontrol | Покрыто ограниченным реальным HTTPfixture с тем же decorator/config; auth/service synthetic, SQL spies0. БД/нагрузкаVPS не заявлены. |
| RP15-017 |[TN15](dev15-tls-negative-results.md)TLS1.2/1.3, wrongCA/SAN/expired, wireClientHelloTLS1.0/1.1 + serveralert | Покрыто actualTLS. Worker badCA проверен отдельно; отсутствие доступного клиентского протокола не выдаётся за serverPASS. |
| RP15-018 |PV15 body/header/serverEOF,7canarycases/8safelogevents/6captures/HTTPSReader childstderr;131 actualDjango endpoint safety | Покрыто совокупностью конкретных уровней, без утверждения «вся система испытана одним end-to-end запросом». SQLexception PV15 synthetic; реальный SQLrollback — RB15. |
| RP15-019 |AD15 exact persisted intent/retry; RL15 created/finalCID/exclusion/inodes/disabled/stale/restart; RF15 latefence/activate rollback | Покрыты названные окна переходов; failed/UNKNOWN outcomes не сбрасывают историю. Physicalpowerloss/откат внешнейTRUST не испытывались и сюда не добавляются. |
| RP15-020 |EV15/source/config provenance; RL15/RB15/RF15 независимые result-review/архивы/ACL/Stop | Последняя принятая точка RF15:MAIN Head13/epoch2/policy1/v2b42ec…, UNIT52766 пустая, обаархива неизменны/closed, source30/config24/EV63 прежние, Stop0/permit{}, ACL1060/2120. FC15-003/005 подтвердили прежнюю UNIT/MAIN/архивную точку и Stop0/permit{}. Финальное completion-review этой матрицы принято. |

## Итог конечных подтверждений

- F15-001 / FC15-001–003 — PASS: разрешённая работа после отказа17-й policy, история16, внешнийrollback и независимый UNITwitness.
- F15-002 / FC15-004 — PASS: свежие DBdu+host roots+резервы 337303077байт, лимит2147483648байт. Прежние317325492байта — отдельный исторический RA15-замер.
- F15-003 / FC15-005 — native/collector PASS: source30/config24/EV63 без изменений, UNIT/MAIN/архивы сохранны, ACL owner/SYSTEM, Stop0/permit{}. **Независимое итоговое completion-review принято.**

Точный итогFC15: [результаты](dev15-final-results.md). Матрица не объявляет каждыйRP отдельным новым прогоном; совокупность принятых доказательств и их области указаны выше.

## За пределами этого завершения

APP PR-08/main commit/gate ACK/in-flight withdrawal, реальное создание/удаление/перемещение страниц и301 — DEV-29; удаления заявок — DEV-16; полное восстановление сайта — DEV-23; admission ночногоHTML/автоматическое переключение — DEV-26/27. DEV-15 отдаёт только проверенный snapshot и полномочия журнала, не HTML admission.

Внешнее размещениеTRUST/контроллера, стоимость, сетьпровайдера/rollback/freshness, production/VPS, итоговые TEST-08/09/10 и READY требуют своих согласований и проверок. Они остаются открытыми в своих задачах и не являются поводом бесконечно держать локальный компонент незавершённым. Старый сайт/VPS не затрагивать. Старый launcherHead10 не запускать на текущейHead13.
