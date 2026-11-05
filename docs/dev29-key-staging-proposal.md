# DEV29-Q029 — квалификация временной TLS-копии

Статус: предложение до согласования владельца. Основание — Q028 actual/auditPASS: оригинал Linux10001:10001/0600, DB999:999 получаетEACCES. Цель — квалифицировать способ доступа, не запускать PostgreSQL. Никакихкопий/новогоnative сегодня по этому предложению не выполнялось.

## Сравнение

| Вариант | Последствия |
| --- | --- |
| Отдельная копия10001:999/0640 | СохраняетDB999/существующиеTLS_CA/supervisor; требуетновыйprivateкаталог иrootlesswriter/readerqualification. Рекомендуется. |
| Secret-bearingstdin/IPC | МеняетDBstdin=false, supervisor/runner/протокол capture; большеизмененийиотдельныйсекретныйканал. Не выбран. |
| НовыйTLSкаждыйrun | Исключаетчтениестарогоключа, но меняетCA/pins иpublictrustdistribution; инструментивпрофилине квалифицированы. Не выбран. |

МенятьDBUID на10001 не предлагается: это затрагиваетутверждённыеPGDATA/identityguards ине решаетсязаменойоднойконстанты.

## Новый ограниченный способ

НовыйrunId иnamespace; оригинал<LOCAL_PRIVATE_ROOT>/database-server-key остаётсяRO. Host создаётровноодинexclusiveпустойкаталог work/dev15-20261102/private/key29-<uuid>, наследующийrestrictedWindowsACL; до любогоbind проверитьchain/nonreparse/regularidentity/ACLowner+SYSTEM. Не изменятьACL оригинала/родителя; при неподходящемнаследованииSTOP, безSet-Acl. Исходныйключнеоткрыватьназапись.

Writer:UID10001:GID999, одинROfilebind оригинала в/probe/source иодинRWbind тольконовогоownedкаталога в/probe/out. Читаеторигинал какнаблюдённыйвладелец, создаёткопию database-server-key exclusive/nofollow иmode0640; fchmod толькоНОВОГОфайла. Неиспользуетchown/chgrp/CAP_CHOWN/DACoverride/root/privileged. Ожидаемыефактическиеmetadata копии10001:999/0640, regular/nonsymlink/nlink1. Еслиfilesystem/parentgroup/umask недаютэтихсвойств — STOP, безавтоисправленияпрофиля.

Writerпроверяетsource stat/fstatidentity иограничение8192bytes; byteidentity source/copy подтверждается автоматическимreadback вRAM. Никакихбайтов/PEM/секретныхrepr/contentdigest вstdout/stderr/ledger/Git. ТолькоclosedJSON сbytesEqual/metadata/resultenum. Невалидныйpublicoutput — отказ; непубликоватьrawoutput илиегоhash, еслиJSONschema не принята. Ошибкиобезличеныдоenum. Это новая разрешаемая операция ЧТЕНИЯ/КОПИРОВАНИЯсекрета, не частьQ028.

Writerзавершить/удалитьдоReader. Reader:UID999:GID999, толькоROfilebind ЭТОЙЖЕкопии в/probe/key; os.lstat/stat/access/openRDONLY|NOFOLLOW/fstat/finallyclose БЕЗчтениябайтов. ТребуютсяUID/GID/mode10001:999/0640, readable/openReadOnly/identity=true, errno=null. Hostidentity/metadata/ACLкопии закрепитьдо/послеReader; дрейф→FAIL. УспехсозданиячерезWindowsне считатьдоказательствомLinuxправ.

## Границы и доказательства

ТолькосуществующийpinnedPythonimage sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951, pullnever. Обаhelper:networknone/rootfsRO/capdropALL/no-new-privileges,128MiB/CPU0.25/PIDs32/shm16MiB/lognone/restartno/stdinTTYfalse; никакихдополнительныхmounts/ports/socket/volumes. ОтличаютсятолькоUID/GID/согласованныеbinds/fixedcode. Одновременнонеболеeодногоhelper. ExactCREATEDinspect/immutableid+nonce+runlabel/sameengine доstart/mutations. Необходимыеinspectprojections≤4096bytes, разбиениебезпотерипроверок допустимо.

Endpoint/engine прежниеQ028: npipe:////./pipe/dockerDesktopLinuxEngine /18f3b425-a862-4cbe-ba14-438caef2aab2. Первыйinventory≤44с/info+inventory≤90с; остальныеcommands икаждыйhelper≤10с; cleanup≤30с, весьоднократныйqualificationlifecycle≤180с, combinedoutput≤4096bytes. Резервcleanupне расходоватьнаработу. Безpull/build/install/settings/restart/новыхобразов.

Original before/after: identity/size/mode/nlink/mtime/ctime/birthtime/ACLfingerprints совпадают. Access-time можетобновитьсяиз-зачтения: этонаблюдаемаяметрика, не immutablefingerprint; невосстанавливатьего записьювmetadata. Любойдрейфзащищённыхполей→STOP/FAIL/безPG. Fingerprints не являютсяbyteproof оригинала; byteequality касаетсятолькокопиивмоментwriterreadback.

Наконецsameengine/ownedidcleanuphelpers иterminalempty. Только послеотсутствияобоихhelpers удалитьтолькоownedновыйфайл сidentity/path/reparseпроверкой, затемпустойновыйкаталог; безrecursive/prune/удалениячужихфайлов. Подтвердитьabsenceкопии/каталога, sourcecoremetadata/ACL иcontainer/network/volumeinventory. Неполныйproof→UNPROVEN/STOP, безповторов. Удаление не гарантируетsecureerase; оригиналостаётсявсвоёмзащищённомхранилище.

## Порядок до любого запуска

Владелецсогласуетэтотспособиограниченныйплан. Затемноваякопиякода/offline(staticno-secret-output, filesystem/race/failure/cleanup/profile/caps cases)/независимыйcodeAPPROVED, одинPrepare, приуспехеодинqualificationlifecycle инезависимыйresultaudit. Код/копирование/nativeдоответане начинать.

PG/SQL/старыйсайт/VPS/публикация/push не входят. Этаqualificationкопияудаляетсяпослецикла. БудущийPGRun требуетотдельногоконкретногоплана/разрешения иповторнойквалификации своейсвежейкопии; Reader иDBтогобудущегоRun должныиспользоватьодинзакреплённыйartifact. Текущийproposal неразрешаетизменениестарогоrunner/обходегоguard.
