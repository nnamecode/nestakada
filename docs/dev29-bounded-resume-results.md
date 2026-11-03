# DEV-29: Q016 — ранний отказ и пауза владельцу

2026-11-04. **R016 — «Приостановлено владельцу»** по правилу AGENTS.md о повторной эквивалентной ошибке. Один разрешённый Run завершён; повторного Run не было. После обнаружения повторных timeout новые Docker/SQL вызовы не выполнялись. Ниже только файловый postmortem.

## Факты

Q016/D-440, package36 `594e33205f32ef2bc416aed37e5e9452eb180af37b20615b917cda0988ee4b84`, plan raw `2f369a4949659851bc91b572d1b3a92de4723d5141c9815457bbea9cc6e43768`, canonical payload `e10f7727ead1a21faa998714d85c02e47092fee72198ed3e745e65d5b39568d9`. Root `7a0fbaff-d7de-4376-be5a-0cca5f04760e`. Code, Prepare, prepared-result и one-dispatch gates приняты до запуска;86 локальных проверок PASS не являются результатами PostgreSQL.

| Вызов внутри одного Run | Результат |
|---|---|
|2 / PREFLIGHT / CONTAINER_LIST | ETIMEDOUT, native timeout8999мс, duration9010мс, SIGTERM, получено0bytes |
|4 / STOP / CONTAINER_LIST | Та же эквивалентная ошибка; timeout8999мс, duration9026мс, SIGTERM,0bytes |
|Последний terminal inventory | Container/network exact-label queries exit0, stdout/stderr пусты, activeIds[], cleanupError=null; тот же engine |

Два timeout произошли в preflight и предписанной проверке очистки внутри одного непрозрачного вызова контроллера. Terminal inventory также завершилась внутри него; это не дополнительный Run координатора. На доступной границе после выявления повторов дальнейшее выполнение остановлено; слепой новый запрос не делался.

Сбой теперь локализован: Docker CLI не завершил чтение списка контейнеров в отведённый срок. Причина задержки внутри CLI/daemon/окружения **не установлена**. Нельзя объявлять причиной Resource Saver, права, network, отсутствие image/volume или потерю данных без нового доказательства.

## Подписанный результат

`FAIL / PREFLIGHT / HOST_CLEANUP_UNPROVEN`, CLI exit1, `resultPersisted=true`, `cleanupProved=false`, `originalPreserved=false`, `fullP29A=false`, `diagnosticUnproven=false`, `evidenceIncomplete=false`. Общий код перезаписан ошибкой stand-cleanup; исходные timeout сохранены в trace. Не сглаживать FAIL после успешного terminal чтения.

**Original/helper/create/admission/SQL/INIT/C/T не запускались**; attempts/reviews/phases/witnesses пусты. Новых owned DB/network/helper не создавалось. Последний подписанный inventory подтверждает отсутствие owned containers/networks; aggregate cleanupProved остаётся false из-за несостоявшейся промежуточной проверки. Original preservation proof отсутствует: false означает NOT PROVEN, а не обнаруженное изменение тома. Старый сайт/VPS не затронуты.

| Private artifact | Raw SHA256 |
|---|---|
|result.json | `8a146ad30c099bcd45ee87a9b36fe795963fe49a08d33bc579e9e346012b23fe` |
|docker-failure-2.json | `0b8471d0be071af819287dede352be7a402b5d14d030b9afa0f39ffc820221a2` |
|docker-failure-4.json | `d044e1c02d827106d66d969107b44da81f45ae5bc50c5fc8d2514814a74bb6f0` |
|terminal-inventory.json | `8dae440e7a6f106b2ed8dd06dd9a8cee244ccc113bf0c4fcd3241d854c14522d` |

Файлы в новом ignored protected private namespace. Trace содержит22 закрытых поля, exact run/package/source/proposal/plan/engine/call bindings, rawContentsOmitted=true; оба потока partial/empty hashes. Координатор проверил HMAC результата и всех7 ledger envelopes, не читал остальные5 private values. Private key не выводился. Независимый рецензент `/root/dev29_publication_review` ключ не читал; independently matched7 hashes/bindings, trace schema/timings, terminal link, unchanged package/plan и отсутствие runtime phases.

**POSTMORTEM ACTUAL-RESULT APPROVED** только как честный terminal FAIL. Это не успешные1000/139, не доказательство исходного корпуса и не разрешение возобновления. Runtime-агенты и процесс завершены; сейчас сохраняются только отчёт и варианты решения, без новых обращений к Docker.

## Варианты продолжения

1. Оставить R016 приостановленным, владелец сам проверяет/изменяет внешнее состояние Docker Desktop.
2. После отдельного решения владельца — [одна ограниченная read-only диагностика через иной источник и иной формат](dev29-docker-diagnostic-resume.md), без новых Root/Prepare/SQL/полного Run.

До ответа владельца новые service calls/code changes/Root retry не выполнять. DEV-29 около35%, этап8 «Разработка сайта» около31%; P29-A открыт. Далее P29-B/C/D/E; общий этап9 «Unit-тесты» после завершения этапа8.
