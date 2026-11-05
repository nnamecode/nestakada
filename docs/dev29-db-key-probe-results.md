# Q027 — фактический результат

2026-11-04: один Prepare exit0/PREPARED, затем один Run exit1/FAIL KEY27_COMMAND. Runfd1ea899-6c3c-4874-b9be-099f7917f424, packagebc674f308fc3815a739832b66b481a11171153486b2736aae51f6483fe649856; resultSHA256dc14466e5e4a70e4b9d61236d14f386963e66232c47aaff645c4844333f9bfe1. Root наблюдал оба exit.

Независимый /root/q026_result_auditor подтвердил pins/attempt/7sourceSHA и отказ на image inspect: exit1/complete, неtimeout/signal; stdout1byte/stderr111bytes, сохранены толькоhashes. Точная ошибка не восстанавливается, imageabsence не доказана. Helper/create-intent отсутствуют, create/start не выполнялись; Linux metadata/read-open ключа NOT_RUN. Повторов нет.

Первый inventory19645.8214мс<44000. Lifecycle23608.8793мс<180000, всеcommand/outputcaps соблюдены. Engineinfo до/после соответствует согласованному Linuxengine. Terminal container/network/volume inventory exit0/empty; removedfalse означает отсутствие созданного helper. Source metadata/ACL equality проверена штатным frozenrunner; digest449335afcf779e46b70080439f54c73dea4e3cae350a705d249d7bd283c6abfc. Независимый пересчёт before/after не заявляется: отдельные snapshots не сохранялись. Ключ не открывался, его байты не читались/не хешировались, ACL/frozenQ026 не менялись.

## Совместимость запроса

[Docker Docs](https://docs.docker.com/engine/deprecated/#emptynil-fields-in-image-config-from-inspect-api) указывает: сv29 пустые поля imageConfig, в том числеVolumes, могут отсутствовать; отсутствие следует трактовать как defaultempty. Q027 template напрямую обращается к.Config.Volumes. Это конкретная зависимость от необязательного поля, требующая коррекции, но точную причину данногоexit1 не доказывает. Текущую engine/APIversion в Q027 не фиксировали.

SQL/PG/staging/копирования ключа/изменения ACL/старого сайта/VPS не было. Q027 diagnostic qualification не выполнена; одноразовый Run завершён.

Дополнительная offlineпроверка координатора: исторический Q026 preflight inspect, проецированный в форму HOST Q027, занимает3114bytes сnewline приcap4096; все необходимые поля присутствуют. Это проверка сохранённого исторического shape, не nativeQ027 и не гарантия размера будущегоinspect. RawEnv иkeydata не выводились.
