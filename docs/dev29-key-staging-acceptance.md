# KEY29 — приёмка согласованной квалификации копии

D-514/Q029, proposal149b77d0acc3b38605594c859ffa6af81173f78087dff73a0a7114a3f93045f7. Ниже ID ужеутверждённыхкритериев, безрасширенияархитектуры.

| ID | Сценарий/ожидаемыйрезультат |
| --- | --- |
| KEY29-A01 | Original exactpath/RO/identity/coremetadata/ACL pinned; source10001:10001/0600, никакойзаписиворигинал/ACL. |
| KEY29-A02 | Новыйexclusive/private/nonreparseкаталог сrestrictedinheritedACL; новыйregular/nlink1file10001:999/0640 созданnofollow/exclusive, fchmodтольконового, безchown/новыхCAPs. Неожиданныеproperties→STOP. |
| KEY29-A03 | Writerread/readback≤8192bytes, FDidentity/size/driftпроверки, bytesEqualвRAM; descriptorsзакрываютсявуспехе/исключении. |
| KEY29-A04 | Никакихkeybytes/PEM/repr/contentdigest ввыводе/ledger/Git, втомчислевошибке/invalidpublicoutput. Сохраняетсятолькоclosedpublicschema/enum; rawoutput/hash непринятойschemaнепубликуется. |
| KEY29-A05 | Reader999:999consumesименноqualifiedstagefileRO, получает10001:999/0640/regular/nonsymlink, readable/open/identitytrue/errno=null. Readerбайтынанечитает. |
| KEY29-A06 | Sourceprotectedstat/ACLbeforeafter совпадают; atimeтолькоobservation, неrestore. Копияpinnedдо/послеReader; drift→FAIL/безPG. Fingerprintsнеbyteimmutabilityоригинала. |
| KEY29-A07 | WriterудалёнпередReadercreate; максимумодинhelper; exactCREATEDprofiles/argv/mounts/UID/caps/engine передstart. |
| KEY29-A08 | Fixedpinnedimage/pullnever иcaps128MiB/CPU0.25/PIDs32/shm16MiB/lognone/netnone/rootfsRO/capdropALL. Лимиты44/90/10/30/180с и4096bytes соблюдаютсябезrenewal/retry. |
| KEY29-A09 | Толькоimmutableownedid/nonce/runlabel/sameenginecleanup. Послеhelpersabsence — удалитьтолькоownedcopy, затемemptyownedfolder, безrecursive/prune. Partialwriter/failedreader/cancel/timeoutтакжеобрабатываются; неполныйproof→UNPROVEN. |
| KEY29-A10 | OldQ028/Q027/Q026source/history неизменны; actualkeyofflineтестынечитают. OnePrepare/atmostoneconditionalqualificationlifecycle, безPG/SQL/старогосайта/VPS. |
| KEY29-A11 | Syntax/static/offlinePASS→independentexactcodeAPPROVED→rootdispatch; послефактовотдельныйresultaudit. Mocked/dummydataнеnativeproof. |

Qualificationcopyудаляетсявэтомцикле. БудущийPGRunнеразрешён, долженсогласоватьсобственныйконкретныйпланисвежийзакреплённыйartifact.
