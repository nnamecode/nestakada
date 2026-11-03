# DEV-15: независимое ревью WB15-005

2026-11-02, D-384, WT15-001–007. DEV-15 около92%, этап8 около28%.

План dev15-worker-tls-plan.md принят для реализации в прежнем D-380 профиле. Нового ownergate не требуется: историческая policy не меняется, новый source связывается отдельным test-only read-binding, рабочая запись выключена.

Отдельный helper tools/trust_worker_tls_access.py SHA `ac15b6315468ece7cf9805a0af21d105ebc34f031fe40bc72d99df9d9c40a745` получил APPROVED. Проверены fixed archive name/OID32563, baseline false/on и0сессий, минимальные ACL с MAINTAIN/sequence=false, session-only readonly-off, rollback-rowlock/реальные отказы записи, cleanup после ошибкиGRANT. ALTER DATABASE/ROLE readonly-off отсутствует. Контрольное соединение MAIN используется для системного каталога, строки журнала MAIN не меняются.

Это gate только helper. Controller/probe ещё должны пройти review: подписанный attempt до служебного открытия архива, подписанный ACL baseline доGRANT, принадлежность и остановка API до restore, потерянный ответ/timeout, полная chain verify после восстановления. Синтаксис, реальный прогон и result-review ещё не объявлены выполненными. Старый сайт/VPS не затронуты.

Первый общий code-review выявил WTLS-REV-001 (provenance: pin именно принятых candidate-report/integration/historicalB/snapshot SHA и runtimeId) и WTLS-REV-002 (SQL actual identity при возвратеMAIN). Обе точечные правки приняты узким повторным diffgate. Итоговый APPROVED для одного WT-прогона: host `d69b546f69f7f73972d80d985df2779bbe6750d116531e3080564f5cf8fa43da`, helperac15… и probe `74436b01559a7a98f32e31548765e68b4a1fb69dc6565a435e6c9f7c956b5869` неизменны. Старыйhost355cc3… сохранён отдельно с провереннымSHA.

Node syntax PASS; реальная PythonAST network-none проверила непустые исходники и их SHA:44/13top-level nodes дляhelper/probe. Парсер без сети/секретов удалён. Missing-gate control дал отказ до attempt/report/Docker. Невыполненные bad-signature/timeout-fault варианты этим не закрываются. Codegate не подменяет фактический TLS-результат.

Независимое result-review: выбранный RP15-011/WB15-005 принят — один полный TLSснимок26.060125с,54/54запроса/52страницы/5120items/SHA5933…; report SHA4c78d149…799d7. Проверены4HMAC/binding/gate links, точное равенство private probeJSON и report.probe, source/config drift0, trace54allPASS/noRetry/30/6, неизменная chain601f… до/после, raw/effectiveACL equality/closed/on и MAIN-return. CPU/peaks/OOM/IDs согласованы; API окно30.871с, delta14.102278CPU/7.658304throttle, OOM0.

Дополнение result-review принято по final-check.ps1/final-preservation.json: WindowsPS5.1 проверил215объектов/430правил ownerSYSTEMonly, reparse0;0owned, включаяstopped; inactive/disabled/permit{}; SHA связан с TLSreport. Рецензент проверял сохранённые результаты, не выполнял повторный runtime-прогон.

Запас3.939875с относится только к этому прогону. Не заявлены воспроизводимость при иной нагрузке, отсутствие throttling, полная ресурснаяRP15-012, рабочий writer или готовность всегоDEV-15. Итог — dev15-worker-tls-results.md. DEV-15 около94%, этап8 около28%; старый сайт/VPS не затронуты.
