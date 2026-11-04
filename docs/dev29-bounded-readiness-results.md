# DEV-29: результат однократного Q022 Run

2026-11-04. R022, owner D461/Q022. Один разрешённый Run завершён FAIL/PREFLIGHT/HOST_COMMAND. Второй Run не разрешён; повторов Docker после результата не выполнялось. Это новый первый отказ command-profile gate, не повторная equivalent timeout/не новый loop.

## Пройденные gates

COW36 package78cc127f04887321a28fad68bcdbeb8115fa5e74afd208308b95f56bd64e2c8a, plan07c412cd04d86039eb670ee975d2c8b6998d182409d9e96c483af244b6dc9809. Syntax12Python/13Node,95 distinct offline PASS; independent host27 PASS; code review APPROVED. AC9 входят вhost27, не double-count. Одна процессная ошибка ineffective test filter описана вcode review; итоговый полныйhost27/0skip фактически выполнен, повторовfilter не было, known nonsecret ancestor receipt прочитан дляretention, keys/credentials не читались.

ОдинPrepare PREPARED и independent prepared/dispatch APPROVED. Rawplanfaa3a6d67f5bb6ab033e7b67742d7d38a747c7c99ec09cab272777f29a3faec3, canonicalpayload0f58e7008b8d1e3a0f9cd96bbe16aff786558005df1b553d6862311030d73d71. Source31 unchanged1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e. Publicphaseattempts/reviews/admissions0, всефазовыегейтыосталисьNOT_RUN.

## Readiness исправление прошло реальный холодный старт

Run прошёл первый inventory и остальные проверки до создания preflight helper. Новых docker-failure traces нет: Docker-команды не вернули timeout/error; остановился собственный inspect-validator.

Ограниченное чтение host log (210983bytes, сыройфайлне копировался) заUTC01:00:45–01:01:20: querywake01:00:47.5093803, engine stopped→starting01:00:47.5159113, daemonready01:01:06.4513727 after18.929s, running01:01:06.4519275. Таким образом новая начальнаяпара дошла до работающегоengine при холодномстарте дольше прежних9с. Это не native timing trace отдельногоchild и не заменяет actualevidence.

## Новый блокер R022-REV-001 (P1)

В preflight был создан один owned helper, но он не был запущен. Конструктор зарегистрировал его вactive registry, затем inspectGate отклонил Config до возвратаcreate(). Вspec.mjs:48 команда сравнивается по User/OpenStdin/Tty/StdinOnce/Entrypoint/Cmd. Все поля совпали, кроме StdinOnce:

| Поле | Ожидание frozen guard | Сохранённый Docker inspect |
| --- | --- | --- |
| OpenStdin | true | true |
| AttachStdin | отдельно не проверяется | true |
| StdinOnce | false | true |
| Tty | false | false |
| User, Entrypoint, Cmd | exact profile | exact match |

helperArgs намеренно передаёт --interactive. [Docker CLI v29.9.2 opts.go](https://github.com/docker/cli/blob/v29.9.2/cli/command/container/opts.go#L691-L694) выставляет StdinOnce=true при OpenStdin&&AttachStdin; stdin flag также включает AttachStdin (341–343,619–620,691–694). Actualprojection соответствует CLI. Старый mock вhost-test.mjs:9 жёстко задавалStdinOnce=false длявсехprofiles и скрывалэторасхождение.

Это не основание пропускатьpredicate/разрешатьобаboolean. Следующее предложение — строгий per-profile StdinOnce: helper с stdin требуетtrue, DB/RO-inspectors безstdin требуютfalse, остальныеguards неизменны. Нужны independent literaltypedfixtures, negativeboolean cases и новый согласованныйpackage/lifecycle. Текущий frozenpackage не исправлялся.

## Результат и очистка

ResultPersisted=true, FAIL/PREFLIGHT/HOST_COMMAND, cleanupProved=true, originalPreserved=false, fullP29A=false, diagnosticUnproven=false/evidenceIncomplete=false; phases{} иwitnesses{}. Исходныйтомне монтировался; отсутствиеRO-before/afterproof отраженоfalse=NOT PROVEN, не изменение/потеряданных. Новые DB/network/SQL/START/INIT/C/T/1000/139 не запускались.

Helper cleanup receipt подтверждает exactownedid/nonce/engine/package/plan, inspectState=created/runningfalse/StartedAtzero; stopped+removed=true, exactidabsence exit0/empty. Stand-stop иterminal inventories empty/sameengine/active0; cleanupError=null. Preflight-helper evidence имеет id/before/after/raw/cleanupsha=null, потомуcreate() упалдовозвратаid; отдельныйcleanup изglobalactive registry доказан. Последующаяclearance не превращаетfunctionalFAIL вPASS.

| Evidence artifact | Raw SHA256 |
| --- | --- |
| result.json | 112d2c1d15a638850ef56ee597dfcfcaf24d0eb33cc2b5c8c7db5466c55060ed |
| cleanup-preflight (точныйid вprotectedledger) | 83dae816e98dab04edf443afd35a1c4e2546529fa89ee3e740bf101b27642bad |
| terminal-inventory.json | 205dca4a3cacee4464de0645a7ee22c7f6985ddaba54d9a15478285df946b4d2 |

Независимый рецензент /root/dev29_publication_review: ACTUAL POSTMORTEM FILE REVIEW APPROVED как честныйFAIL, все12ledgerrawhashes/bindings совпали; R022-REV-001 P1 остаётся открытым. HMAC независимо не проверялся, keys не читались. Source/runner/старыеpackages/корпус/старыйсайт/VPS не изменялись. Следующийшаг — согласоватьстрогийstdin-profilefix и новыйone-shotroot; старыйRunисчерпан. DEV-29≈35%, этап8≈31%.
