# DEV07-N — точное сетевое покрытие

2026-11-01, D-342. DEV-07 около94%, этап8 около20%. NETWORK_6 first PASS на product05c24609…/test-only threaded+proxy150 при неизменном app120 и прежних caps. [Факты и SHA](dev07-network-results.md), [сценарии](dev07-network-scenarios.md).

| Требование / сценарий | Подтверждено | Открыто |
|---|---|---|
| FR07-004, H07-017/019, R07-006 | NET002: actual A partial read, B header-only Busy check(employee)/save/draft(owner), независимые PG try-locks, no B reader/child, separate manual retry | Все сочетания actors/pages/source modes, process/server production matrix |
| FR07-005 / positive slow | NET003: partial-then-complete200 и healthy, direct timer/FD/slot cleanup | Большие body/RSS и все pacing/abort regimes |
| FR07-005 / absolute deadline | NET004: настоящий120003/120002ms app408 при drip5s, no child/mutation, прямые flags и healthy after | Базовый нерасширенный proxy timeout, production stack и полный resource worst-case |
| FR07-005 / incomplete abort | NET005:3 actions8192B<CL, server400/outcome4/no child/no commit, здоровое следующее действие | Все FIN/RST half-close режимы; NET008 complete-body UNKNOWN отдельно |
| H07-015/026 / early denial | NET001: visitor/foreign/CSRF, реальные header-only ранние ответы; прежние ingress framing/caps controls сохранены | Полная framing/request-smuggling матрица и все denied modes |
| V07-008 / RAM and retry | NET006: actual UI Busy, RAM retained, no extra POST в измеренном workflow, manual Check/Save и одна версия | Любые будущие timers, все UI/source/media/browser combinations |
| Late session/grants | Отдельный N2 cohort: NET007 grant-revoke Check403 и password-reset Save401 после actualbody/realchild, owner controls/regrant/newlogin | Все field-downgrade/disable/logout/source/session/media сочетания |
| Complete Save + lost reply | Отдельный N2 cohort: NET008 paused application non-consumption/fullactualwrite/onecommit/exactBuffer replay +2negative409 | Kernel packet loss/моментмеждуcommit-write, replay послеотзываправ, browser UNKNOWN identity/source matrix |
| No resource/input leak |27 terminated traces, timer joined/duplicate FD closed, observer faultfalse, source/config guards unchanged, cleanup0 | Все FD/thread races, все log/temp carriers; отсутствие файлов по polling не является temporal proof |

Независимое ревью ограниченного cohort завершено без блокеров. Это не приёмка полного DEV-07 и не выбор production server. Прежние207server/22MODEL/6FORMAT+8E3 остаются самостоятельными связанными свидетельствами; текущие6сетевых групп не переименовывают их в новый общий прогон. Старый сайт/VPS не затронуты.

Продолжение D-343: N2 first2/2 PASS/12 terminated traces при том же product05c24609… и неизменных guards; independent review без блокеров. [Факты и ограничения NET007/008](dev07-network-late-results.md). DEV-07 теперь около95%, этап8 около20%; NETWORK_6 и N2 — разные реальные прогоны.
