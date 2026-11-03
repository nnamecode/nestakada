# DEV-15: независимое ревью ресурсного аудита

2026-11-02, D-385, RA15-001–006. DEV-15 около94%, этап8 около28%.

План принят для подготовки кода. Проверены общий бюджет без повторного суммированияSQL/WAL, точный preview из подписанного attempt, boundedartifactreserve и раздельные периоды ресурсов. Измерение DBdu повторяется после финальногоchain доStop; последующий shutdown не объявляется измеренным.

Первый code-review обнаружил RA-REV-001: два dbFacts писали один wx-файл. До runtime добавлены обязательные initial/after-chain labels и разные имена. Узкий diffgate принят. Итоговый общий **APPROVED** для одного аудита: controller `6b8c75213f68781ec3c7f59adf14957643734aa7eef27e97369689af6da5b18e`; Pythonhelper `532d378eb63d446cf04ce48355f77032fe5ebc52db90c40955a77c666d758883`.

Проверены fixed4DB/OID, bootstraponly/0sessions/readonlyrepeatable reads,6legacy/8currenttables, heap/table/index/TOAST без повторного суммирования, temp/WALcumulative scopes, возврат архивов кclosed/on безGRANT/defaultизменений. Ownedhelperreap предшествует следующемуhelper; completedSQLprobe cgroup снимается после егоexit до выходаsupervisor. Fullchain/source/finaldisabled/0owned остаются обязательными после выполнения.

Независимо принята документальная связь в dev15-capacity-gates.md: RP009 oldserverevidence/29неизменныхфайлов+new131/TLS; RP010 разрешённаяinjection в трёх точныхrp010тестах достаточна для combinedbudget/policycharge/fence/rollback/completion, дополнительный физический64МиБкорпус не обязателен; RP011 выбранный полныйTLS принят без обещания другой нагрузки. RP008legacyinclusion и результатRP012 пока открыты.

Codegate не подменяет фактический ресурсныйPASS. Старый сайт/VPS/MAINactivation/native/DEV-29 не затрагиваются; исторические данные и свидетельства сохраняются.

Фактический result-gate положительный: report SHA30f0510f…e0f29d1, HMAC/gate/inputhashes/rawframes/4DB/14hostroots+signedpreview проверены. Бюджет317325492<2147483648байт, WAL/relations не сложены повторно; closed/on/0sessions, chain601f… иsource/configdrift0. Completed-probepeak26877952байта/PIDpeak6, DBpeak332627968/OOM0; DB PID10 — current, legacytemp1.13ГБ — cumulative history. FinalPS5.1ACL223/446/ownerSYSTEM/0owned/inactive/disabled/permit{} подтверждены.

Принят выбранный ресурсный аудит RP15-012 с границей beforeStop/reserves, без hardquota или точного post-shutdown размера. TLSпериод отдельный. Legacy008, manifests/activation/native остаются открытыми; весь DEV-15 не закрыт. Рецензент читал сохранённые evidence, ничего не исполнял/не менял. DEV-15 около95%, этап8 около28%.
