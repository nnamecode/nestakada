# DEV-29: план первого участка публикации

Дата: 2026-11-03. Основание: D-410, архитектура `dev29-publication-proposal.md`, независимое DEV29-PUB-REVIEW-004. Статус: **DEV29-Q005 разрешён D-411, возобновлён D-412; код подготовлен, code-review APPROVED, PostgreSQL runtime BLOCKED**. [Результаты и точка продолжения](dev29-publication-results.md). [Ревью плана](dev29-publication-plan-review.md). Предыдущая пауза: [DEV29-PA-RESUME-001](dev29-publication-resume.md).

## 1. Выполняемый участок P29-A

Первым предлагается реализовать только закрытое расширение протокола TRUST и его consumer: `route_publication` и `LIVE_NO_SET`. Это проверяемая предпосылка APP workflow, не работающая кнопка публикации. APP не получает credentials и сетевую связь, `Page.is_published` не меняется. Дальнейшие участки не разрешаются ответом Q005.

Изменяемые существующие файлы: `trust/journal/protocol.py`, `models.py`, `services.py`, `consumer.py`; при необходимости только соответствующие проверки входа в `views.py`. Новые файлы: `trust/journal/test_publication_profile.py` и одна следующая additive-миграция после `0003_admission_policy.py`, только если сохранённые choices/constraints действительно требуют её. Перед кодом проверить фактические constraints и выбрать следующий свободный номер. Исторические миграции не переписывать. APP, compose, ingress, policy/permit, credential-файлы не входят в разрешённые изменения.

Связь требований: PR-04/08, REQ-004/017/018/046–050, AC-HTML-002–009/012. Полные PUB29-001–022 остаются в архитектуре; частичное покрытие ниже не означает их полного PASS.

## 2. Порядок и проверки до исполнения

1. P29-A01: сохранить перечень и SHA текущих изменённых/новых файлов в ignored `work/`, включая предложение/ревью/план. Снять inventory исходников и миграций; проверить disabled writer, пустой permit, закрытый журнал UNIT, существующие MAIN/UNIT/архивы по принятой методике DEV-15. При недоступном Docker не запускать ничего автоматически: подготовка кода допускается, runtime-проверки отмечаются BLOCKED.
2. P29-A02: написать тесты A29-001–008 до реализации, затем минимальные изменения закрытого протокола. Prepare по-прежнему пишет PENDING_DENY; финальный committed-report допускает только заранее записанную policy. `route_restriction` не получает право записывать LIVE_NO_SET.
3. P29-A03: независимое code/QA-review точного diff и тестов. После исправлений — повторная проверка затронутого. До принятия review не запускать DB/runtime-проверки.
4. P29-A04: статическая проверка, затем штатный изолированный test runner TRUST в существующей UNIT, только после проверки его реальной изоляции. Не выполнять миграции в MAIN, не вызывать production Prepare/report, не получать MAIN run lease и не включать рабочий writer. Если штатный runner не обеспечивает такую область, остановить runtime-часть и подготовить отдельный точный способ, а не менять права/ресурсы по догадке.
5. P29-A05: запустить новый набор и прежние TRUST protocol/state/snapshot/write/admission регрессии по фактическому inventory. Исторические результаты не присваивать новому source. Зафиксировать команды, source SHA, реальные counts и ограничения свидетельств.
6. P29-A06: проверить сохранность MAIN/архивов и прежних UNIT данных; удалить только точно учтённую собственную fixture штатным механизмом runner. При неизвестной очистке не удалять базы/тома вручную. Вернуть стенд в исходное остановленное состояние, writer disabled/permit пустой. Независимое result-review и актуализация реестров.

Никакого нового софта/образов/портов/томов/лимитов. Это изменение исходников и изолированные тесты в прежнем локальном стенде. Альтернатива — отложить весь участок до реализации APP admission/EDGE; она не даёт ранней проверки совместимости TRUST, но сохраняет тот же конечный порядок безопасности.

## 3. Приёмка P29-A — до кода, сейчас NOT_RUN

| ID | Результат | Связь с архитектурой |
|---|---|---|
| A29-001 | route_publication принимает ровно одну policy: root/policy objectId равны, requestIds=[], redirectTarget=null, policy только HIDDEN/LIVE_NO_SET. Basis — строгая 64-hex строка, включённая в prepare semantic fingerprint; изменение basis под тем же UUID конфликтует. Prepare сохраняет PENDING_DENY. TRUST не видит action внутри непрозрачного basis: canonical action/basis и соответствие действию проверяются только будущим APP workflow P29-B/D. | PUB29-017, только TRUST-часть |
| A29-002 | Report имеет собственный semantic fingerprint; committed принимает ровно policy list из Prepare. Неверный формат incarnation/receipt/epoch отклоняется; replay той же report phase с изменённым receipt/incarnation даёт PHASE_CONFLICT без частичной записи. Первый корректно оформленный mainReceipt/mainIncarnation принимается от аутентифицированного writer: его предметное происхождение доказывает будущий APP workflow, а не P29-A. | PUB29-004/017, только TRUST-часть |
| A29-003 | Exact replay Prepare/report сохраняет прежние receipts и generation; иной payload под тем же UUID — конфликт. Исторический route_restriction с HIDDEN/DELETED/REDIRECT прежний, LIVE_NO_SET для него запрещён. | PUB29-004/007/017 |
| A29-004 | unknown/aborted после Prepare не снимает deny. Потеря response разрешается status того же ID с fingerprint; terminal stage не регрессирует. | PUB29-005/009 |
| A29-005 | Snapshot/consumer принимает LIVE_NO_SET как отсутствие допуска HTML. PENDING_DENY/HIDDEN/DELETED/REDIRECT сохраняют прежнюю семантику; UUID/shape/generation/digest и key=sha256(target) проверяются, неизвестная policy fail closed. Предметное соответствие PageID конкретному PRIMARY/APP Route отложено до P29-C и здесь не считается проверенным. | PUB29-010, только consumer-часть |
| A29-006 | Реальная транзакционная ошибка между изменениями Operation/RoutePolicy/Head откатывает их вместе; точный retry не дублирует результат. | PUB29-008, TRUST-часть |
| A29-007 | Прежние admission/writer epoch/квоты/reader и recovery ограничения не ослаблены новым kind; превышение действующей квоты сохраняет историю. | PUB29-012/015, TRUST-часть |
| A29-008 | Тесты изолированы; MAIN, прежние данные и архивы сохранны; APP Boolean/сеть/credential/production flags не менялись, стенд остановлен. | PUB29-014/016, ограниченная область |

Каждый результат имеет PASS/FAIL/BLOCKED/NOT_RUN и доказательства. Ни один A29 не доказывает APP publication e2e, startup/restore cohort barrier или EDGE close. Fixture не объявляется реальным многопроцессным допуском.

## 4. Последующие участки — пока только порядок зависимостей

- P29-B: additive PublicationIntent, immutable prepare/final receipts, CAS и закрытый APP↔TRUST client. Отдельный точный план, сеть/credentials только после его разрешения; без предметного переключения публикации.
- P29-C: конкретные IPC/readiness/fencing/cohort receipts и startup/restore barrier с ARC-10 review и многопроцессной проверкой PUB29-019–022. Без них normal publication flag остаётся выключенным.
- P29-D: owner publish workflow только после принятого P29-C; отдельный план и полный охват PUB29 publish/session/restart/concurrency. Нет production-разрешения.
- P29-E: unpublish только после реального независимо проверенного EDGE close и отдельного плана; PUB29-003/018 нельзя закрыть fixture.

## 5. Разрешение владельца

**DEV29-Q005.** Разрешить P29-A: реализацию и изолированные локальные проверки закрытого расширения TRUST/consumer по этому плану, с независимыми code/result review? Остальные участки B–E, APP-сеть/credentials, изменение Page.is_published, production, старый сайт/VPS и push этим ответом не разрешаются.

Согласование требуется потому, что DEV29-Q004/D-410 утверждают архитектуру и прямо оставляют реализацию за отдельным точным планом. До ответа владельца P29-A не начинается.
