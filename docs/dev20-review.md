# DEV-20 — независимое ревью предложения

2026-11-02, combined_review. Precode-ревью положительное: блокеров для вынесения единого DEV20-Q001 нет. Это допуск предложения к владельцу, не факт реализации/безопасности работающего сайта и не согласование чисел вместо владельца.

Проверены dev20-proposal.md/dev20-checks.md, scanner-defense.md/D114–115/AT041 и фактическая структура журнала установленного Django. SC20-001–012 достаточны для начала ограниченной реализации после gate: ранний отказ/SQL0/connect-attempt0, кодирование/реестр адресов, конечные счётчики, оба logger, inheritance и сохранность прежних защит.

Кандидаты20/50rps/burst60/100/globalactive8/3МиБ обоснованы для локальной проверки; достаточная производительность ещё не доказана. Process-local counts не подменяют историю/источники/файлы/админку DEV17/18/21. Полный AT041 с публичным200 и TEST09 остаются открытыми.

При code review отдельно подтвердить строгий формат django.server requestline/status, все дочерние limit_req/limit_conn и невозможность подавления500/неожиданного2xx. До ответа владельца app/config/новые caps не менять. Рецензент файлы не менял, runtime не запускал.

Readonly compatibility: scratch candidate JS115MAP/316MED/543targets,0collisions/13known vectors/7allowed. Это не product Python PASS. В действующем pinned Nginx встроенные request/connection limiter modules имеются (read-only nginx-compiled-options.txt); новых пакетов не требуется. Существующие14изменений сохранены SHA-проверенной копией до DEV20.

## Продуктовый code gate после D-372

combined_review проверил ранний middleware/noSQL, будущие reserved routes, bounded counters, log shapes, Nginx inheritance и runner. Найденные long-query logging обход и unsafe lazy fork-reset устранены: bounded requestline parsing, os.register_at_fork reset до worker threads; raw invalid PATH_INFO и реальный fork проверены. Узкий повторный продуктовый gate положительный на source238/5b7e6d13…. Фактические95тестов/20.052с/OK подтверждены рецензентом. Native gate/результаты ещё отдельно; это не завершение DEV-20.


## Native QA gate и первый результат

combined_review разрешил first после исправлений stdout/stderr+positive control,3s/8s+hardalarm15s/host20s deadline, restore-intent до stop и timing diagnosis/CPUdelta. Freeze first fixture08e8c3f3…/probe883e5e9e…/host9da42644…. Фактический first6/6PASS/stderr0/OOM0 и сохранность данных проверены рецензентом; один429 в N04 доказывает global limit при двухsource и61запросе на каждый. Точный QA сохранён в native-first/qa до дальнейшего измененияhost.

SC20-011 потребовал отдельный mixed witness; SC20-009 actual many-source zone fill не проводится и остаётся TEST09 (active/release/config memory проверены). mixed-first gate положительный на probea9156ad8…/host50e12942…/freeze4; проверяется настоящий editor200 с marker/overlap/recovery. Результат mixed и итоговое завершение пока ожидаются.


## Итоговое независимое ревью — положительное

combined_review подтвердил actual95tests/20.052с и6+1nativePASS. N07: настоящая owner editor200/marker, overlap341мс со90сканами иrecovery200; noSave/domain unchanged. Независимо сверены238host/frozen файлов, конфигурация и4QA: drift0. Manifestinactive/Stop0, данные сохранены/OOM0/stderr0. DEV-20 можно завершить в согласованной локальной области; включение локального профиля разрешено D-372 и нового ответа владельца не требует. Production/many-source churn/fullPERF/TEST09 и будущие DEV17/18/21 не объявляются выполненными.

Текущий этап8 — Код, около28% по количеству основных задач (8/29, не взвешенная оценка времени). Следующая областьDEV-15 требует проработки отдельного профиля ARC-10; здесь она не начата. Старый сайт/VPS не затронуты; push не выполнялся.
