# DEV-15: конечные проверки ограничений нагрузки

2026-11-03, продолжение D-380/D-394 по поручению «Продолжай». RP15-016 / SC15-014. План до кода/исполнения, не PASS. DEV-15 около97%, этап8 около28%.

Прежние два слота Python256МиБ/0.5CPU и Nginx128МиБ/0.25CPU, PIDs64 каждый, существующие pinned images, неизменный nginx.conf, только прежняя internal API-сеть, без host ports. Проверенные synthetic CA/valid leaf/key TN15 повторно используются побайтно по принятым SHA, генерации сертификатов нет. MAIN/UNIT/архивы и PostgreSQL не открываются, реальные credentials/ключи не монтируются, writer lease не выдаётся. При удалённой Stop сетью восстанавливается только прежняя согласованная API-сеть; удаляется только собственная пустая сеть по run label/ID.

Python-slot запускает test-only HTTP fixture, импортирующую неизменный `journal.views.endpoint` и его реальный semaphore4. Django настраивается только внутри тестового процесса, auth заменяется считателем/синтетическим actor; функция endpoint удерживается Event. DB cursor instrumented fail-closed: любая попытка курсора увеличивает счётчик и падает. Это реальный HTTP к настоящему decorator, но не запуск штатного Django API/проверка настоящих credentials или БД. Контрольный URL/hold header доступны только fixture, не добавляются в продукт. Управление fixture только localhost helper; внешних портов нет. Nginx проходит к тому же fixture обычным upstream.

| ID | Ожидаемое конечное наблюдение |
| --- | --- |
| LD15-001 | Прямой внутренний HTTP:4 запроса действительно дошли до удерживаемой endpoint-функции. Пятый быстро429/BUSY/no-store (<2с), auth/service counters не растут, SQL cursor0. Release завершает исходные4 с200; следующий control200. |
| LD15-002 | Через неизменный TLS Nginx:4 действительно удерживаемых upstream requests, пятый быстро429/Busy/no-store (<2с), backend auth/service counters прежние, SQL0. Изолировать от rate:4 начала разнесены минимум0.12с, всего5requests в коротком окне при burst10. Release/control200. |
| LD15-003 | Отдельный свежий ingress без старой rate zone: один TLS HTTP/1.1 connection, конечный pipeline48 GET (одновременно active≤1). Реальные429 при10rps/burst10, нет очереди: первые429<2с/весь pipeline≤5с; успешные response/header/body корректны, backend auth/service число равно200, cursor0. Успешных≤11+ceil(10×elapsed), время/accepted/rejected записаны; отсутствие429 означает FAIL, лимиты не повышать. |
| LD15-004 | Через1.2с после burst control200, counters/held0, native requests/threads ограничены. Не считать 429 от active gate доказательством rate. |
| LD15-005 | Точные source30 host/frozen/config24/EV63/originalcerts/manifest/env/старые final artifacts прежние; Stop0контейнеров/пустойpermit/собственнаясетьудалена, private ACLowner/SYSTEM до private outputs и после. |

Каждая удерживаемая функция имеет deadline4с (меньше Nginx proxy_read_timeout5с), orchestration/clients bounded; holdTimeout обязан остаться0, на первой ошибке release в finally и cleanup только проверенных собственных IDs. Native один конечный набор после code-review точныхSHA/Node syntax/Python AST и закрытого gate, затем independent result-review. Однотипную ошибку не повторять без нового свидетельства; AGENTS-stop на втором эквивалентном отказе. Прежние FAIL/данные сохраняются. Исходные96Git-изменений сохранены перед подготовкой.

Synthetic SQL0 доказывает отсутствие попытки курсора в fixture, не измеряет запросы действующей БД. Полный RP15-018/privacy и штатный Django transport остаются отдельными controls. RP15-015/007/019, DEV-29 и production этим не закрываются. Старый сайт/VPS не затрагивать; новых программ/ресурсов/архитектуры/системных настроек/push нет.
