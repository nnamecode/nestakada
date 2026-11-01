# DEV07-N2 — закрытый read-only adapter

2026-11-01. Предложение до code gate; NET007/008: dev07-network-late-checks.md948991… и QA2a445db0…. Новый `tools/editor_network_late_http_fixture.py`; прежние fixture772b… и network witness2d845… неизменны. Старые3 witness operations вызываются старым helper; только network_late_read — новым. Никаких DB writers, endpoints, новых инструментов/лимитов или runtime здесь нет.

## Вход и ownership

Ровно один JSON request, UTF8≤4096B, запрет duplicate keys/NaN/лишних полей:

```text
{operation:"network_late_read",run:lowercaseHEX32,fixtureRun:canonicalUUID,
 ownerId:canonicalPositiveDecimalString,employeeId:canonicalPositiveDecimalString,
 pageId:canonicalUUID,operationIds:[canonicalUUID,canonicalUUID,canonicalUUID]}
```

Три distinct operationIds создаёт host заранее: denied late Save, lost-reply Save, stale-new-ID negative; изменённый replay использует второй ID повторно. User IDs — decimal без leading zero,1..9223372036854775807 (не более19digits), сравниваются/передаются строками. Host берёт userIds[0]/[1], pageIds[0], fixtureRun и эти IDs из private seed/своего фиксированного allowlist. Browser RPC передаёт только закрытое имя операции: ни actor/Page/opID, ни пользовательскую команду/путь/query. При каждом вызове host сам строит request. Credentials/cookies/CSRF/пароль/их hashes/session keys запрещены во входе и выходе.

До DB: UID10001, ESTAKADA_LOCAL_ENV=test, DJANGO_SETTINGS_MODULE=estakada.settings.local_http, actual DB estakada_foundation, request.run==ESTAKADA_NETWORK_PROBE_RUN. Host отдельно проверяет owned container/manifest/actual nonce и source hashes; fixtureRun UUID и observer run HEX — разные идентификаторы. Никакого reset/reseed observer через adapter.

На DB проверяются оба user.first_name==fixtureRun, owner username=nesadmin/roleowner, employee username=editor-assigned/roleemployee; IDs distinct. Page имеет переданный UUID, kindarticle, exact name `EDITOR TEST <fixtureRun> A` и ровно одну primary Route `/editor-fixture/<fixtureRun>/a/`. Это ownership proof существующего772b seed, не одно совпадение произвольного UUID. Отсутствие/чужое владение — закрытый boundary error без вывода найденных данных. Existing host exclusive fixture guard остаётся обязательным.

Один короткий transaction.atomic с `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY` до первого ORM query; без domain advisory locks/row locks и без изменения global connection settings. Queries выбирают только перечисленную metadata, не payload/пароли/данные сессий. Ошибки — фиксированный NETWORK_LATE_BOUNDARY либо NETWORK_LATE_UNAVAILABLE, никаких str(exception)/SQL/raw request в ответе.

## Выход≤8192B, фиксированная схема

```text
{version:1,run,fixtureRun,pageId,
 owner:{id,generation,active,authSessionCount,linkedNativeSessionCount},
 employee:{id,generation,active,hasGrant,allowedFields,
           authSessionCount,currentGenerationSessionCount,linkedNativeSessionCount},
 receipts:[{operationId,status:"absent"|"present",metadata:null|{
   action,actorId,pageId,actorGeneration,editorFingerprint,
   resultCode,resultId:null|UUID,resultExists:boolean}}]}
```

IDs — canonical strings, generation/counts — safe nonnegative integers (generation≥1), flags — строгие booleans. Receipts ровно3, порядок входного operationIds. allowedFields — sorted subset intro_text/main_text/price: фактические PageGrant flags только при active=true; отсутствие grant/неактивность даёт[], hasGrant отражает наличие строки независимо от flags. Owner implicit page rights не выдаются за PageGrant.

AuthSession counts фильтруются по собственному user_id, currentGeneration — также profile.generation. linkedNativeSessionCount — Session.objects.filter(session_key__in=AuthSession той же user).count() через SQL subquery: keys не извлекаются в Python/IPC, Session.session_data не читается/не декодируется; ALL Session scan ради «поиска прежней» запрещён. После reset AuthSession0 и linked count0 не доказывают отсутствие старой уже НЕсвязанной native Session. Утверждение ограничено связанным count, поздним401 старого request и source proof reset_password→invalidate; прямого наблюдения конкретной старой native Session здесь нет.

OperationReceipt модель фактически содержит action/actor_id/actor_generation/page_id/editor_request_fingerprint/result_code/result_id. Существующая row допускается в ответ только если Page равна owned page, actor — один из двух owned users, action=commit_owner|commit_employee. Иначе boundary error, не existence oracle чужого UUID. Result при наличии должен указывать на PageRevision той же Page; resultExists=false допустим лишь при отсутствии этой revision, не чужой Page. Fingerprint ровно64lowercaseHEX; resultCode читается из row и для этого current-only scope должен быть applied (engine.finish default, restored относится к отдельному stage scope), а не синтезируется как «ожидаемый успех». Никаких payload/source/checkReceipt из DB. Независимый engine result()/HTTP replay oracle сравнивает tuple и gone=!resultExists; adapter не применяет действие.

## Свидетельство и cleanup

Late grant: hasGrant=false при прежней generation/active; late password reset: generation+1, active=true, authSessionCount0. Прямые мутации выполняются только настоящими owner HTTP forms. Lost reply: durable receipt metadata + reader/normalizer events, затем exact same request replay; одна row/result/revision. DomainHash и receipts сравниваются отдельно. Нарушение schema, ownership, budget или readonly transaction останавливает тест, не подменяет product outcome.

Фиксированный source hash нового helper, private allowlist и closed host dispatch проходят независимое ревью до запуска. Cleanup делегируется старому fixture по прежним правилам permanent receipts; новый adapter ничего не удаляет/не исправляет. Доказательство не распространяется на все сессии БД, другие source modes или production.
