# DEV29-Q028 — исправление image query и одна новая диагностика

Статус: предложение до согласования владельца. Q027 завершён FAIL до create; старый run/результат/frozen7 сохраняются без повторов. Цель и границы diagnostic-only Q027 сохраняются; SQL/PG/staging/keycopy/ACL/старый сайт/VPS исключены.

## Точное исправление

1. В новой изолированной копии с новымrunId заменить imageprojection Id/Config.Env/Config.Volumes на Id и целыйConfig. Не обращаться Go template к optionalConfig children. Нормализовать JSON после получения: Id строгоpinned; Config строгоobject; Env отсутствует/null→emptyarray, иначе толькоarrayстрок; Volumes отсутствует/null→emptymap, иначе толькоobject, и всёравнообязательноempty. Неверные present-типы/лишние volumes не скрывать. Не понижать APIversion и не менять Dockerнастройки.
2. Сохранять закрытую category неуспешной команды (IMAGE_MISSING/TEMPLATE_FIELD/ENGINE_UNAVAILABLE/PERMISSION/OTHER) из bounded stderr до удаления transientdata; никаких rawstderr/Env/keybytes в отчёте/Git. Сохранить существующие rawhashes иbytes/exit/clock. Unknowncase→OTHER бездогадок.
3. Сохранить отдельно sourceBeforeMetadataAclSha256 и sourceAfterMetadataAclSha256, чтобы независимый аудитор мог сопоставить fingerprints. Источник не читать/нехешировать: толькоmetadata/ACL. Не выдаватьfingerprints заbyteimmutability.

## Последовательность

Новаякопия без измененияQ027/Q026source/history; meaningfuloffline cases на absent/null/invalidConfig fields, extra volumes, errorcategories иpairedfingerprints. Затемsyntax/static/offlinePASS и независимое code review exacthash. Только после успеха одинPrepare; толькопри егоуспехе максимумодин новыйRun с исходнымиQ027caps ипрофилем: exactpinned Python image/UID999:999/netnone/rootfsRO/capdropALL/одинROfilebind, безreadbytes. СуществующийпланQ027 и KEY27-A01–A11 сохраняются.

Readinessfirstinventory≤44с/info+inventory≤90с; остальныеcommands/helper≤10с,cleanup≤30с,global≤180с,combinedoutput≤4096bytes. Никакихpull/build/install/restart/settings/новыхобразов. ОдинhelperтолькопослеexactCREATEDinspect; open RDONLY NOFOLLOW→fstatidentity→finallyclose безread. Отказopen — результат, неповтор. Очистка поimmutableid/runlabel/nonce/sameengine; terminalcontainer/network/volumeempty иmetadata/ACLunchanged. Прилюбомнеуспехе noRetry/честныйFAILилиUNPROVEN, независимыйresultaudit.

Одно будущeе разрешениеQ028 охватит новуюкопию, исправление/проверки/code review, одинPrepare иодинусловныйRun/cleanup/resultaudit; пока не получено. Доответа никакого новогоnative/helper.
