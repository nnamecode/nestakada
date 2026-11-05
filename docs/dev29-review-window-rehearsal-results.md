# DEV29-Q026: измеренная репетиция передачи ревью

2026-11-04. Recorder exit0/PASS, qualification принята отдельным аудитом и pinned review (D-498), см. [итог ревью](dev29-review-window-rehearsal-review.md). Код exact package42 2489595e6c86e7ea797af0e2276786ea46e7742a696412faa2bcbe592eba299e одобрен D-496. Один запуск по D-493; повторов нет.

Все факты и решения **NOAUTHORITY**: START — pinned исторические факты Q025, INIT/PAYLOAD-C/C/PAYLOAD-T/T — полные синтетические fixtures. ВсеactualPGfalse; реальные1000/139/SQL не запускались. Рецензент /root/q025_reviewer сам после каждой Inspect/nextSummary выбрал WOULD_APPROVE/findings[], одинраз записал собственный wxsource и вызвал PublishRehearsal. Root начал/наблюдал recorder и не копировал JSON/не делал автоматический verdict-loop.

| Гейт | Полное время, мс | Лимит |
|---|---:|---:|
| START | 55638.0512 | 80000 |
| INIT | 17740.5339 | 80000 |
| PAYLOAD-C | 17152.7549 | 80000 |
| C | 17168.7988 | 80000 |
| PAYLOAD-T | 16875.8454 | 80000 |
| T | 25278.6704 | 80000 |

Result total149890.0422мс; persisted recorder-ack acknowledgedTotalMs149957.6097мс; общий лимит490000мс. CLI отдельно вывел postreport acknowledgedTotalMs149955.339; normative persisted ack и границы измерения проверяются по approved recorder code, цифры не подгоняются. ClockOwnerprocess-31396 один, источник монотонный, process завершился exit0.

- result.json SHA4860ea34e01b9935d2aca8090d97a4c1b1806cba3c08347f07bf63e661bd696b.
- recorder-ack.json SHA09739b621c20c813ae6fb48ac430b25635db50604029f180610cb6b6abbd37d9.
- attempt.json SHAfa4c3950f89fdf3fe712ce88d9ecd016fde73db6abb88eda86bd3b861d52691b.

Артефакты находятся только в ignored resume006/rehearsal-NOAUTHORITY. Outbox rawJSON и canonical persisted opinion могут иметь разные hashes из-за stable key-order; обязательна semantic equality и hash-binding именно соответствующего артефакта. Это не runtime admission.

Для независимости результата от автора шести opinions приглашён отдельный readonly QA /root/q026_result_auditor; он не правил код и не выдавал opinions. После его фактического аудита pinned /root/q025_reviewer должен отдельно принять aggregate для строгого sampleGate; root не подменяет имя. До этого Prepare/readiness/private/native запрещены. Runtime HMAC/ACL/private-I/O затраты эта репетиция не доказывает; postPrepare readiness≤10с обязателен. Измеренная прошлая latency не гарантирует будущую модель/OS, runtime120с остаётся авторитетом. Корпус/runner/старый сайт/VPS не меняются.

Последний статус D-498: оба result review завершены, sampleGatePASS; sourceca9af647…15e6. Prepare ещё не выполнялся на момент этого решения; его результат фиксируется отдельно.
