# DEV29-Q031 — независимый аудит NOAUTHORITY rehearsal

Verdict: REHEARSAL RESULT APPROVED. Qualification: PASS / NOAUTHORITY. Findings: []. Reviewer: q026_result_auditor. Дата: 2026-11-05.

## Точный binding

Root: work/dev29-bounded-20261104-resume007.
RunId: 35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1.
Package55 SHA256: efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460.
Все current source55 hashes совпали с revision004 manifest. Active code-review document SHA256 f6b9a0b62b5ad5dab8b02fa3d5a63b7521415d55a8ba320d494ec16a680bc3a4 проверен в начале и конце аудита, без изменений.

Public result: rehearsal-NOAUTHORITY/result.json,1438bytes.
Raw result SHA256: 9a963c58da7dedc8bcfe5fcd266e163b9b21f358f99769cfb43cf491dfad64a4.
Raw recorder-ack SHA256: 4037a9d48b940f85347e770e0b996c8ca1627d05f50d93f1f3acd4bd8ab87038.
Raw attempt SHA256: 6ce8a3785f785bb2878b338382619f90e391c4e55672e977aaa92c1ecd74bdbd.

Result scope BOUND29-REHEARSAL-RESULT/statusPASS/authorityNOAUTHORITY; recorder ack scope BOUND29-REHEARSAL-ACK; attempt scope BOUND29-REHEARSAL-ATTEMPT. ClockOwner во всех трёх — process-10568. Attempt связывает тот же runId/package. Result и ack требуют успешного recorder exit; ack связывает raw result SHA.

Координатор непосредственно наблюдал единственный recorder session36113, exit0/stderr0. Auditor принимает это как execution evidence координатора; один лишь result-файл не заменяет process-exit proof.

## Gate summary

Ровно шесть distinct gates и requestId, в точном порядке ниже. Значения таблицы округлены до4 знаков; bounds проверены по полным числам из result, не по округлениям.

| Gate | End-to-end elapsed, ms | Источник |
| --- | ---: | --- |
| START | 57717.5045 | HISTORICAL |
| INIT | 23972.1169 | SYNTHETIC |
| PAYLOAD-C | 23132.9702 | SYNTHETIC |
| C | 23153.6899 | SYNTHETIC |
| PAYLOAD-T | 25220.3217 | SYNTHETIC |
| T | 25244.8096 | SYNTHETIC |

Каждый gate <=80000ms. Максимум57717.5045ms. Result totalMs178531.6662; persisted recorder acknowledgedTotalMs178710.4495 <=490000ms.

root-rehearsal-001.stdout независимо разобран как7 JSON lines:6requests в том же порядке и финальный PASS/NOAUTHORITY/process-10568. Его enriched acknowledgedTotalMs178708.0395 — отдельная более ранняя граница, не поле persisted result и не замена persisted recorder ack. Final stdout ackSha256 совпал с raw recorder-ack. Approved frozen recorder включает readback и post-write/final deadline checks; successful exit замыкает их исполнение. Mtime не использовалась как authoritative elapsed.

## Проверка public graph

Для каждого gate independently проверены raw request/opinion hashes против result, exact requestId/kind/reviewer binding и соответствующий ack. Все семь полей opinions закрыты согласованной схемой, reviewer=/root/q025_reviewer, verdict=WOULD_APPROVE, findings=[]. Outbox raw hashes отличаются от канонических opinion bytes во всех шести случаях, но recursive canonical semantic equality подтверждена; различие порядка ключей не является tamper.

Каталог содержит один attempt, по шесть request/opinion/ack, один result/recorder-ack и шесть own outbox files. Root подтверждает один PublishRehearsal на gate назначенным независимым q025_reviewer, без копирования/подписания opinion за него. Public artifacts подтверждают identity/sequence/schema/byte bindings; сами NOAUTH файлы не являются криптографической аутентификацией личности автора.

Request windows ровно80000ms; facts/summary/request/opinion/ack имеют NOAUTHORITY. START — pinned historical Q025 value, stageCREATED, valueSha256 f849b915d5f12dc9b985c8f587dfafcd56ffae2455f2b1c670261ec9f3a45cf2. Остальные пять — SYNTHETIC typed fixtures: INIT/C/T COMPLETED_HELPER, PAYLOAD-C/T RUNNING. actualPG=false во всех шести summaries, assertions true/typed, value hashes корректной формы. Это не actual PG/key/SQL facts.

Дополнительные mtime observations согласованы: source после request и до expires, opinion не раньше source, ack не раньше opinion; следующий request после предыдущего ack, public artifacts не позже final recorder ack. Это лишь наблюдения freshness/последовательности. One-shot вывод также опирается на frozen once-write/absent-directory recorder и прямое наблюдение координатора. Повтор или resume этим audit не разрешён.

Public real-host/run namespace отсутствует; actual admission outputs в нём не создавались. Opinions имеют только WOULD_APPROVE; никакой runtime admission из NOAUTH схем не следует.

## Детерминированные summary pins

Canonical encoding для следующих hashes: рекурсивно сортировать object keys лексикографически, сохранять порядок arrays и числа JSON.parse/JSON.stringify, UTF-8 без whitespace/BOM.

GateSummary = result.results.
GateSummary SHA256: e29fcc2580df72cb168d5b6bc40accaf831e5fcda25ac49287e0780128f0a537.

Graph = object scope=KEYPG-REHEARSAL-GRAPH/v1, gates в указанном gate order. Каждая row имеет ровно kind,requestId,requestRawSha256,opinionRawSha256,outboxRawSha256,ackRawSha256. RequestId берётся из request-kind.json; outbox filename=requestId-kind.json. Все четыре row hashes — SHA256 фактических bytes соответствующих public files.
Graph SHA256: b8464a510b570ca3329ba567e3b75a0d336b46d3442b88d7654d71a968f12a4a.

## Границы результата

Одобрена только qualification единственной процедуры rehearsal. Реальные1000/1001/139, PostgreSQL/SQL/HMAC/ACL/key-readability и время будущего actual reviewer этим result не доказаны. Prepared/readiness/dispatch и шесть actual decisions будущего Run остаются обязательными отдельными gates.

Auditor читал только known public artifacts/source hashes/code marker. Private inputs/tag/key values и raw private logs не читались; тесты, новые recorder/rehearsal, Prepare/readiness/Docker/SQL/native не запускались. Real tool/read ошибок не было. Active code-review document, ownerline и source files не изменялись. Записан только этот review.
