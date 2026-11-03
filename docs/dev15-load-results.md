# DEV-15: ограничения одновременных запросов и частоты

2026-11-03, D-395, RP15-016/LD15-001–005. Первый конечный native-набор PASS; итоговое независимое result-review — **APPROVED в ограниченной HTTP-fixture области с настоящим decorator**. DEV-15 около97%, этап8 около28%.

Проверены реальный неизменный `journal.views.endpoint`/semaphore4 внутри test-only HTTP fixture и прежний TLS Nginx/config. Два прежних слота256/128МиБ,0.5/0.25CPU, без host ports, новых программ и увеличения ресурсов. Сертификаты TN15 переиспользованы по точным SHA; генерации и изменения системных настроек нет.

| ID | Реальное наблюдение |
| --- | --- |
| LD15-001 | Через прямой HTTP четыре endpoint-функции действительно удерживались. Пятый получил429/BUSY/no-store за0.002540с. Auth/service counters остались4/4, курсоров0. Явный release завершил все4 с200; новый control200, active/held/holdTimeout0. |
| LD15-002 | Через TLS Nginx четыре upstream-функции удерживались до release. Пятый получил429/Busy/no-store за0.007947с до backend; auth/service4/4 без изменений, курсоров0. Все4 после release200; новый control200, holdTimeout0. Начала запросов разнесены0.12с, rate/burst не исчерпаны. |
| LD15-003 | На отдельном свежем ingress один TLS connection/pipeline48 обработан целиком за0.067826с:11ответов200 и37ответов429. Первый429 за0.066092с; backend auth/service11/11, peak1. Таким образом active4 не объясняет отказы этого набора. Измерение соответствует10rps/burst10 без очереди. |
| LD15-004 | Через1.2с после burst контроль снова200. Нет застрявших hold или попыток курсора. |
| LD15-005 | Source30 host/frozen, config24, EV63, оригинальные manifest/env/cert/key и предыдущий MAIN final-result прежние. Контейнеров0/пустойpermit/собственнаясетьудалена. PrivateACL до outputs2объекта/4правила, после13/26, owner/SYSTEM/reparse0. |

Run `d3af5053-5dae-4b81-bc6f-d65da766e36f`, report `work/dev15-load-20261103/result-d3af5053-5dae-4b81-bc6f-d65da766e36f.json`, SHA `5f5a4dbc0fa36511ba862bf62cb2fbc32856abfc4c1e0999261f33d70caae09a`. Три группы охватывают четыре поведения; финальная сохранность проверена отдельно. Collector `final-result.json` SHA `376da8a751573f6a7d161ba2ae562ea18328fe780b27914d379fdfb1c3774586` сверил raw-case joins, signed synthetic intent/code-gate, числа/таймеры, все SHA и текущий Stop. Native прошёл с первого запуска, предыдущие TLS-отказы не переписывались. Исходные96Git-изменений сохранены до подготовки.

## Границы результата

Подлинный decorator/semaphore обслуживал реальные HTTP-запросы, но auth actor и конечная функция синтетические. SQL0 означает0попыток инструментированного курсора fixture; БД и настоящая Django-аутентификация этим не проверены. PostgreSQL не запускалась и не монтировалась, MAIN lease не выдавался; свежего SQL-снимка нет. Прежний Head13/epoch2/policy1/v2b42ec… остаётся последним принятым SQL-свидетельством D-392.

Это конечный bounded burst, а не многочасовое нагрузочное испытание, измерение числа посетителей или устойчивость произвольного VPS. Заявленные времена относятся только к этому запуску. Реальные ключи/credentials не монтировались, private raw metadata/фикстуры остались в ignored work. Старый сайт/VPS/APP/DEV-29/production не затронуты.

Остаются RP15-015 SQL/disk-error injection и серверная partial-body граница, RP15-018 body/header/slow/privacy/log-canaries, остаточные recovery/отказные окна RP15-007/019. Для MAIN нужен новый signed context от Head13; старый Prepare с baselineHead10 и сброс данных запрещены. Весь DEV-15 этим не закрыт.
