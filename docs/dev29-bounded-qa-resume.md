# DEV-29: QA-RESUME-001 после отказа до send

2026-11-03. **Предложение DEV29-Q015, пока не разрешено.** Q014/D-434 и архитектура BOUND29-PLAN-001 остаются согласованными; здесь требуется только новый once intent для шести inert Linux QA сценариев после исправления совместимости ACL subprocess. Реальный PostgreSQL/INIT/C/T не запускались.

## Что произошло

Исходный пакет30 файлов `b23f889c746c46ad165b8323a7880a6ba8c6f24cc86adb7360c202ecb2340d78` прошёл BOUND29-QA-CODE-REVIEW-002 APPROVED_FOR_MOCK_QA. Подготовлены новый закрытый QA key и signed intent `4b348ef01f3c2d94fe243719946e8d2ab89d6567eae049daad5aca7be2624d20`, issued `2026-11-03T19:26:43.498Z`, expires `2026-11-03T19:41:43.498Z`.

Первый RunQa остановился с BOUND_QA_PRIVATE_ACL **до чтения QA key/consume/создания контейнеров**. Native Get-Acl подтвердил owner/SYSTEM-only FullControl с inheritance, без изменения ACL. Изолированная диагностика установила: Windows PowerShell5 не загрузил Microsoft.PowerShell.Security из унаследованного PSModulePath PowerShell7 (CouldNotAutoloadMatchingModule). Это ошибка совместимости subprocess, не недостаточные права каталога.

Независимый ENV-REPAIR-REVIEW разрешил только process-local native PSModulePath и RO witness, без code/ACL/intent/expiry изменений. RO ACL witness прошёл, но перед вызовом RunQa не прошёл minimum remaining700с; **второй RunQa не вызывался**. После остановки подтверждены remaining568295ms, неизменность исходного пакета/intent и отсутствие attempt.json. Отдельный read-only Docker ps по точному bound29.run завершился exit0 без ID: QA-контейнеров0. SQL/первого тестового случая не было, исходный том не подключался. Одинаковые ошибочные действия без нового свидетельства не повторялись; это не пауза из-за цикла.

Предел времени не продлевался и intent не переподписывался. План Q014 запрещает timestamp renewal/retry и автоматическое переиспользование root run/attempt. Поэтому новый допуск не создаётся без ответа на Q015.

## Конкретно подготовленное исправление

Отдельная append-only копия30 source inputs: `work/dev29-bounded-20261103/qa-resume-001/`, canonical package SHA256 **`60c6ed015c66a35e12ea39c23f9aa6e6339af857923de2fa63f343858fbf594f`**. Старые30 файлов/qa-run/QA key не менялись. Новый пакет подготовлен, **23 offline Node tests PASS, failures/skips0**; внутри model/path scripts219/83 checks, не отдельные product tests.

Изменены только qa-controller.mjs и qa-flow-test.mjs. ACL subprocess теперь использует абсолютный штатный Windows PowerShell5 path и **его собственный** `PSModulePath=C:/Windows/System32/WindowsPowerShell/v1.0/Modules`, переданный только в subprocess env. Родительский env/права/системные настройки не меняются. Инъекционный тест проверяет argv/env, отсутствие изменения parent env и сохранение DENY для чужого owner/лишнего ACL rule/ошибки процесса. Проверки ACL не ослаблены.

Nested package получает правильный ROOT `../../..`; отдельный private prefix `work/dev15-20261102/private/bound29-1e23c654-qa-resume001`, создаваемый только после Q015 с проверенным inherited owner/SYSTEM ACL. Новый intent scope **BOUND29-INERT-LINUX-QA-RESUME-001**; code требует в archived owner input исходное Q014/D-434 и явное Q015/QA-RESUME-001. Новые private key/qa-run/intent/attempt этой копии **не созданы**. Runtime/HBA/supervisor/fakes/resources/лимиты/fixtures/protocol и acceptance не изменены.

## Предлагаемый ограниченный порядок

1. После ответа Q015 и независимого code/resume review: проверить неизменность старого package/intent и отсутствие старого attempt; сохранить эти digest links в новых archived inputs. Старые файлы/key/intent/nonce/expiry не менять и не удалять.
2. Перед новым intent — readonly локальные engine/image/inventory diagnostics и готовность ACL native modules; при ошибке STOP, не расходовать permit на холодную/неготовую инфраструктуру. Только локальный npipe, старый сайт/VPS не доступны этому adapter.
3. Создать новый private prefix с проверенным inherited ACL без изменения существующих ACL, архивировать owner Q014+Q015/review, новый32-byte QA key и **ровно один** signed intent TTL≤900с/remaining≥700с. Он явно заменяет неисполненный истёкший/недостаточный допуск для первой dispatch, а не повторяет кейсы. Исходный root run `1e23c654-5baf-4b5e-a7b4-6235b1289c0a` разрешается продолжить только в этом новом scope/namespace; никто из6 случаев прежде не выполнялся.
4. Выполнить `qa-resume-001/qa-controller.mjs RunQa` один раз: good TERM/INT/HUP, runtime-exit, bootstrap-sql-timeout, ignore-stop. Только pinned PG image с пятью readonly inert Perl PG overrides, UID999/CAPdropALL/rootfsRO/networknone/memory=swap256MiB/bounded tmpfs/loggingnone. Никаких реальных PG binaries/SQL/старых DB/passwords/томов/нового network/порта. Public dummy secrets — явно не credentials.
5. Сохранить private stdout/inspect/cleanup/inventory и HMAC result, провести independent actual-result review; удалить exact owned QA containers. При FAIL/timeout/expiry/unknown cleanup — STOP без нового intent/повтора. Positive result квалифицирует только MOCK_SHELL_ONLY, не INIT/C/T/real PostgreSQL/1000/139.

После принятого QA — продолжать реализацию реальных INIT/C/T по уже согласованному Q014, сохраняя отдельные code/start/payload/result gates; Q015 их не обходит и не требует повторного согласования всей архитектуры. DEV-29 около35%, этап8 «Разработка сайта» около31%, затем P29-B/C/D/E; общий этап9 после этапа8. Старый сайт/VPS/production/push не затронуты.

**DEV29-Q015:** разрешить QA-RESUME-001 по этому исправленному пакету с одним новым ограниченным QA intent и сохранением всех прежних inputs/отказов, затем шесть ещё не запускавшихся inert Linux QA сценариев с independent review и exact-ID cleanup? Это только явное возобновление первой dispatch после pre-send отказа; без ослабления ACL/runner/TTL и без нового разрешения на реальный SQL.
