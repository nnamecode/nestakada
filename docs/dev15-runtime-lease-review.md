# DEV-15: ревью допуска конкретного запуска

## Итог исполнения D-392, 2026-11-03 — APPROVED

Независимым result-review принят ограниченный RL15 scope: 8 lifecycle-фаз, 9 native checks/16 transport captures и фактический последующий SQL/архивный Inspect. HMAC, SHA-ссылки и сырые outputs согласованы. Подтверждены current Head13/writer epoch2/policy1/full-v2 b42ec… и связь с исходной точкой60e…, одинаковые receipt и отсутствие мутации при replay, старые строки, только одна новая synthetic operation/route, accounting4597/8362 с legacy reserve16708.

Архивы16387/32563 сохранны и снова закрыты; source30 host/frozen/config/EV63 без drift. Финальный permit пуст, собственных контейнеров0, FinalACL WinPS5.1 PASS689/1378 owner/SYSTEM/reparse0. Итоговый индекс48621879… и Inspect20a1da5d… проверены; root collector корректно пересчитал формулу Head/bytes и сохранил границы покрытия. Полный DEV-15/RP15, APP/DEV-29/production не закрываются. Рецензент файлов не менял и runtime не запускал. Текущая готовность DEV-15 около97%, этап8 около28%. Ниже история подготовки и снятой паузы.

Начало 2026-11-02, продолжение 2026-11-03. D-380/D-391, RL15-001–010. DEV-15 около 96%, этап 8 около 28%.

## Текущий итог: технически готов, runtime приостановлен

Независимый diff-review **APPROVED** для controller `579e37f6309529059e0446125b931c1dbce1087796cbf92d33fe37e16b8695d7`, guards `29e567c4cbc6b5f610a93fa1713cb159a58b9e82ae45d4ecd3ef1e718d4026bf` и неизменного probe fdd92…. LEASE-REV-001 закрыт: bounded exec reader читает regular file с O_NOFOLLOW/пределом 1 МиБ, capture происходит до остановки, недоступные результаты остаются FAIL. Exact Docker Desktop endpoint закреплён, добавлена 16-я VM-проверка другого pipe. Новых блокеров в ограниченном diff нет.

После этого координатор фактически получил quality-9fa7662d… PASS по точным SHA: Node syntax, 16 VM и AST пяти Python-блоков, без БД/ключей/выдачи lease. Именованный inspect-sources.mjs отдельно проверен: SHA совпали, VM16/AST5, Docker cp отсутствует. Старые quality10275 и backup сохранены.

Исполнитель повторил ошибку вложенного PowerShell quoting при информационном Node -e check; команда не исполнилась. Координатор остановил исполнителя, рецензент подтвердил признак цикла по AGENTS.md. **DEV15-RL-RESUME-001 требует решения владельца**. Техническое одобрение артефакта не разрешает runtime до снятия паузы; ни Prepare/Enable, ни API/SQL/native-фазы D-391 не запускались. План — work/dev15-lease-20261102/resume-plan.md, факты — dev15-runtime-lease-results.md. Ниже история предварительного ревью.

## План и происхождение

Независимый рецензент принял RL15-план в прежних ресурсах/архитектуре. Предыдущий MAIN API подтверждён отдельно от общего LG-результата: original LG961 → private facts/ARG → подписанный fixture intent aa96. CID `a4e2b6e5c3a38a6a28d20b852157da2e582d9861d2f1858ff4f64c4446f0cfba`, runtime `c6c4746d-c13e-40b3-8547-af77a14b01f4` совпадает с неизменным исходным manifest. Исторический LG hostFAIL не объявлялся PASS.

Обязательны initial disabled API и его исключение до final bounded CID, корректный аутентифицированный denial, публикация только при stopped API в прежний файл, exact source/config/runtime, пустые recovery descriptors и отсутствие policy/Head advance при reissue. Windows Node не предоставляет O_NOFOLLOW: проверяются lstat/FD/dev/ino до truncate, fsync и postidentity; гостевой Linux-парсер имеет собственный O_NOFOLLOW. Старый резерв 16708 байт сохраняется после завершения новой synthetic operation.

## Замечания до исполнения

| ID | Замечание и состояние |
| --- | --- |
| NF-REV-001 | Root fault-controller должен закреплять принятый baseline D-390, а не доверять произвольному unsigned final-result. Исправлено pin SHA e102… и связью с подписанным prepared-policy; узкое ревью принято. |
| NF-REV-002 | Ранний отказ до verifiedOwner не должен молча пропускать Stop уже работающего lease. Исправлено однократным делегированием доверенному lease-controller по проверенному SHA; невозможность cleanup явно NOT_PROVEN/FAIL. Узкое ревью принято. |
| LEASE-REV-001 | Docker cp не извлекает нужное содержимое tmpfs в ранее наблюдавшемся сценарии TLS Resume002. Текущий кандидат должен использовать принятый bounded docker exec reader O_NOFOLLOW/fstat/лимит 1 МиБ, собирать файлы при работающем API и только затем останавливать его. До исправления runtime-gate не выдан. |

Рецензент прочитал lifecycle/probe, 15 VM-проверок и root fault-controller 3881…: других блокеров ограниченного RL-scope не выявлено. Дополнительно согласовано выравнивание exact локального Docker endpoint в обоих инструментах; глобальные Windows/Docker-настройки не меняются.

Первый кандидат controller10275… / probefdd92… / guard5169… прошёл Node syntax, 15 VM и AST двух Python-файлов/двух встроенных команд. Это исторический quality-result `work/dev15-lease-20261102/quality-96c028d0-d119-4788-9932-53d30c421f0a.json`, не разрешение запуска вопреки LEASE-REV-001. Итоговый diff/gate и реальные результаты фиксируются после нового freeze. Docker admission/HTTP-write на момент этого ревью ещё не выполнялись.
