# DEV-29: предложение координации публикации через журнал запретов

Дата: 2026-11-03. Статус: **предложение после реализации локального создания; код этого профиля не начинался**. Вопрос владельцу после независимого ревью — `DEV29-Q004`.

Основания: D-052, D-239/D-240, D-294–D-296, D-300, D-307, D-373–D-409; REQ-002/004/006/007/017/018/022/046–050; AC-004/006/007/017/018/022, AC-HTML-002–009/012, AC-PRO-009/010; PR-04/08; `analytics-html-reserve.md` §§6, 7, 11–12; `fallback-scheme-proposal.md` §§3–6; завершённая локальная область DEV-15 и результат создания DEV-29.

## 1. Граница предложения

Предлагается следующий локальный участок DEV-29:

- явные owner-действия `publish_page` и `unpublish_page` для уже созданной Page с единственным PRIMARY Route;
- долговечная координация основной БД APP и независимого TRUST через существующий журнал запретов;
- точный повтор по одному `operationId`, честные неопределённые исходы и восстановление продолжения после рестарта;
- feature flag по умолчанию выключен; локальные проверки только в UNIT;
- никакой новой публичной выдачи, аварийного HTML, sitemap или production-кнопки в этом участке; документ определяет полный порядок, но до ответа владельца на `DEV29-Q004` нельзя начинать никакой код этого профиля. Даже после ответа реализация возможна только по отдельному точному плану; изменение `is_published` при снятии публикации остаётся запрещено до появления независимо проверенного EDGE gate.

Не входят: создание Page, применение/удаление OwnerDraft, изменение текущей редакции, URL/301, удаление Page, изменение родителя/порядка, публикация поддерева, сборка ночного HTML, реализация EDGE gate, внешнее размещение TRUST, VPS и старый сайт.

Сохраняется принятая D-307 граница: в обычном режиме Nginx направляет запрос прямо в Django, а единый gate регулирует только аварийный HTML. Удалённого обращения к TRUST или EDGE на каждом обычном запросе нет. Однако один восстановленный `Page.is_published=True` не является достаточным разрешением: каждый допущенный к normal traffic процесс APP дополнительно применяет локальный deny-only срез TRUST по §8. Этот срез может только закрыть маршрут, но не опубликовать скрытую в APP страницу. Отказ аварийного gate не должен ломать уже допущенный исправный обычный сайт.

Отсюда следуют разные границы видимости:

- при публикации APP-коммит сам по себе не открывает страницу: обычный Django-ответ становится видимым лишь после доказанного TRUST-final `LIVE_NO_SET` и подтверждённого обновления deny-only среза всех допущенных APP-процессов; аварийный ответ остаётся закрытым до подходящего HTML-набора;
- при снятии публикации TRUST `PENDING_DENY` сначала закрывает normal traffic через локальный срез APP, а APP-коммит дополнительно запрещён, пока не получено подтверждение закрытия маршрута действующим EDGE gate для всех новых аварийных допусков.

До появления отдельно согласованного и проверенного `gate close receipt` код полного `unpublish_page` и изменение `Page.is_published` в этом направлении начинать нельзя. Одного feature flag или ответа TRUST Prepare недостаточно.

## 2. Почему нельзя переключить только Boolean

После отката APP старый `is_published=True` не должен открыть страницу, которую владелец позднее скрыл. При публикации нормальная Django-видимость начинается только после доказанного TRUST-final и применения его локального deny-only среза, а аварийная доступность остаётся закрытой до подходящего набора. Поэтому:

1. TRUST сначала долговечно переводит маршрут в консервативный `PENDING_DENY`.
2. Все допущенные APP-процессы применяют поколение как локальный deny и подтверждают общий cohort receipt. Для `unpublish_page` действующий EDGE gate также применяет это поколение и возвращает проверяемый close receipt; без обоих подтверждений APP-коммита нет. Для `publish_page` отдельное EDGE-закрытие не требуется: normal и emergency маршруты уже deny.
3. APP повторно проверяет основание и коротко фиксирует только своё предметное изменение.
4. TRUST получает фактический исход APP и сохраняет итоговую route policy; только после подтверждённого обновления APP-среза на этот final normal route может открыться.

Сеть никогда не ожидается под общим content lock, auth lock или транзакцией APP. Слово «атомарно» применяется только к каждой локальной транзакции, а не к двум БД.

## 3. Итоговые политики маршрута

Для этого участка достаточно двух итогов одного PRIMARY route:

| Действие | До операции | Prepare в TRUST | APP-коммит | Итог TRUST |
|---|---|---|---|---|
| `unpublish_page` | опубликована | `PENDING_DENY` + подтверждённый EDGE close | `is_published=False` | `HIDDEN` |
| `publish_page` | скрыта | `PENDING_DENY`, normal закрыт локальным APP-срезом | `is_published=True`, normal ещё закрыт | `LIVE_NO_SET`; после APP cohort refresh normal может открыться |

`LIVE_NO_SET` означает: APP считает страницу опубликованной, но для её точного PageID/пути ещё нет допущенного ночного HTML-набора. Обычный Django-ответ действует по сочетанию `Page.is_published=True` и отсутствия запрета в актуальном локальном APP-срезе; аварийный режим для этого маршрута возвращает контактный 503 до подходящего набора. Переход `LIVE_NO_SET → LIVE` относится к DEV-25/26 и не входит в DEV-29.

Для скрытой страницы прежние входящие REDIRECT сохраняются по D-244 и продолжают вести на текущий PRIMARY; обычный Django даёт на PRIMARY пустой белый 200, а аварийный gate применяет HIDDEN. Сотрудник не меняет публикацию. Скрытие родителя не меняет флаги детей и не удаляет их политики.

## 4. Минимальные изменения данных

### 4.1. APP

Рекомендуется одна additive-таблица `PublicationIntent`, потому что существующая `OperationReceipt` хранит только завершённый локальный результат и не позволяет безопасно продолжить межсистемную операцию после рестарта.

Поля закрытого профиля:

- `operation_id` UUID, primary key;
- `page_id` UUID без каскадного удаления и `action` (`publish_page`/`unpublish_page`);
- точный PRIMARY target и `basis_hash`;
- actor ID, security generation и исходная server session binding в виде хэша, без cookie/пароля;
- ожидаемые TRUST incarnation/generation/writer epoch;
- отдельные `local_phase`, `trust_phase` и `intent_revision` для CAS;
- два отдельных неизменяемых digest APP cohort receipts: `prepare_cohort_receipt_digest` для применённого `PENDING_DENY` до APP-коммита и `final_cohort_receipt_digest` для применённой итоговой policy после TRUST report; каждый receipt содержит точные phase, TRUST incarnation/generation/head, digest среза и перечень допущенных APP process incarnation;
- digest подтверждённого EDGE close receipt для `unpublish_page`, если достигнута эта стадия;
- digest локального receipt после APP-коммита и безопасные коды результата;
- системные времена создания/обновления.

Таблица не хранит HTML, payload редактора, секрет TRUST, пароль, cookie или персональные данные. Один `operationId` не меняет action/Page/basis. Завершённые строки не очищаются этим участком; локальный профиль подчинён фактическому пределу 1000 операций DEV-15. Повышение квоты или новая очистка требуют отдельного решения.

APP-коммит одной короткой транзакцией изменяет `Page.is_published`, создаёт обычную неизменяемую `OperationReceipt` с действием `tree_publish` или `tree_unpublish`, безопасный AuditEvent категории «Страницы и ссылки» и переводит `PublicationIntent` в `MAIN_COMMITTED`. `mainReceipt` связывает только неизменяемый prepare/PENDING_DENY cohort receipt и, для unpublish, EDGE close receipt; появившийся позднее final cohort receipt не может его переписать. Ошибка любой части откатывает всё. Current revision, OwnerDraft, версии, Stable, Asset, URL, parent, position и главная не меняются.

Автомат состояния закрыт и разделяет локальный прогресс от наблюдаемого TRUST:

| Поле | Разрешённые переходы | Кто меняет |
|---|---|---|
| `local_phase` | `INTENT → APP_DENY_APPLIED → GATE_CLOSED → MAIN_COMMITTED → FINAL_APPLIED → COMPLETE` для unpublish; `INTENT → APP_DENY_APPLIED → MAIN_COMMITTED → FINAL_APPLIED → COMPLETE` для publish; `RECONCILE_REQUIRED` терминален для web-пути | Только короткая APP-транзакция с CAS по `intent_revision` |
| `trust_phase` | `NOT_PREPARED → PREPARE_UNKNOWN → PENDING_DENY → REPORT_UNKNOWN → FINAL_POLICY`; из подтверждённого состояния допустим только переход вперёд либо `RECONCILE_REQUIRED` | Результат точного TRUST response/status, сохранённый APP с CAS |

`PREPARE_UNKNOWN` и `REPORT_UNKNOWN` не взаимозаменяемы. Status может доказанно перевести первый в `PENDING_DENY`, а второй — в `FINAL_POLICY`; неизвестность не является терминальным успехом и не разрешает регрессию. `MAIN_COMMITTED`, `FINAL_POLICY`, `COMPLETE` и `RECONCILE_REQUIRED` не перезаписываются другой семантикой. Две вкладки с прежней `intent_revision` получают конфликт, а exact replay читает сохранённый результат.

### 4.2. TRUST

Новые таблицы TRUST не предлагаются. Используются существующие `Operation`, `RoutePolicy`, `Head`, admission policy, writer lease и квоты DEV-15.

Нужны ограниченные расширения закрытого протокола:

- новый kind `route_publication`;
- допустимая итоговая policy `LIVE_NO_SET` наряду с `HIDDEN/DELETED/REDIRECT`;
- Prepare независимо от желаемого итога записывает текущую route policy как `PENDING_DENY`;
- committed-report ставит ровно заявленный итог `HIDDEN` либо `LIVE_NO_SET`;
- exact replay возвращает прежний receipt и актуальную terminal stage без нового поколения;
- snapshot/consumer принимает `LIVE_NO_SET`, но не трактует его как наличие HTML-набора.

Закрытая wire-схема сохраняет текущие имена полей DEV-15 и добавляет не произвольный DTO, а kind-specific ограничения:

| Фаза | Обязательные инварианты `route_publication` |
|---|---|
| Prepare | Поля ровно как в текущем prepare; `kind=route_publication`; `requestIds=[]`; `objectId=PageID`; `policies` содержит ровно одну запись PRIMARY; её `objectId` равен PageID, `target` равен подписанному PRIMARY, `policy` соответствует action (`HIDDEN` для unpublish, `LIVE_NO_SET` для publish), `redirectTarget=null` |
| Basis/fingerprint | Canonical basis включает action, PageID, RouteID/target, current revision ID/hash, исходный publication, parent/position, actor/security generation и счётчик прежних publication receipts. Prepare semantic fingerprint связывает kind, весь basis и точную policy; чужой object/route/action под тем же UUID даёт 409 |
| Report unknown | `outcome=unknown`, `mainIncarnation=null`, `mainReceipt=null`, `policies=[]`; это только неизвестность report, не новый prepare |
| Report committed | Тот же operationId/incarnation/writer epoch; доказанный APP main incarnation/receipt; ровно та же итоговая policy из сохранённого Prepare. Для unpublish canonical main receipt включает digest EDGE close receipt |
| Report aborted | Текущий закрытый профиль `policies=[]`; после достигнутого Prepare маршрут остаётся deny/reconcile, а не возвращается в allow автоматически |

Прежний kind `route_restriction` по-прежнему допускает только `HIDDEN/DELETED/REDIRECT`; `LIVE_NO_SET` разрешён только `route_publication`. Operation status/restart считается доказательством лишь после сверки сохранённых prepare/phase fingerprint и receipt с заново вычисленной ожидаемой семантикой APP; одного имени stage недостаточно.

Существующее имя terminal stage `FINAL_RESTRICTION` сохраняется ради совместимости данных DEV-15 и означает «финальная политика журнала»; исторические deny-операции не переписываются. Текущая `RoutePolicy` может ссылаться на более новую publication-операцию, а прежний запрет остаётся в immutable `Operation` history. Это устраняет необходимость разрушительной миграции TRUST.

`aborted` и неизвестный исход не открывают маршрут автоматически. После достигнутого Prepare они остаются deny/reconcile по действующим правилам DEV-15. Возврат прежнего разрешения возможен только после доказанной сверки отдельным согласованным reconciliation, не по таймеру.

## 5. Полномочия и локальная сеть

APP получает только два отдельных машинных credential: `app-publication-writer` и `app-publication-reader`. Recovery credential, bootstrap/migrator secret, TRUST DB и ключ подписи admission policy в APP не передаются.

Для локальной проверки предлагается одна узкая internal Docker network между APP и существующим `trust-ingress`:

- без host ports и обычного internet egress;
- APP не видит сети TRUST API/DB напрямую;
- Nginx публичного входа не получает TRUST credentials;
- CA и два APP credential монтируются read-only отдельными файлами;
- применяются существующие pinned images и прежние индивидуальные caps; ресурсы автоматически не повышаются, совместный пик измеряется;
- writer включается только действующим signed permit/run lease D-380; при Stop permit снова пустой, контейнеров 0.

Это новая связь сетей и новый credential binding, поэтому их нельзя реализовать без явного ответа `DEV29-Q004`. Новых программ, образов, томов, публичных портов и платных сервисов предложение не добавляет.

### 5.1. Обязательный EDGE close для снятия публикации

Протокол unpublish зависит от принятого, но ещё не реализованного единого аварийного gate D-307. После TRUST Prepare APP передаёт gate только фиксированные поля: operation ID, TRUST incarnation/generation, PageID, PRIMARY target и policy `PENDING_DENY`. Gate под своей короткой сериализацией:

1. проверяет, что применяет не более старое поколение;
2. долговечно фиксирует deny в собственном локальном реестре;
3. исключает прежний активный экземпляр/отставший процесс из новых допусков;
4. возвращает bounded close receipt с gate incarnation, operation ID, generation, PageID/target и digest применённого состояния.

APP проверяет receipt по настроенному машинному ключу/каналу и сохраняет только его digest. Ранее допущенный медленный ответ может завершиться, новые допуски после receipt закрыты. Timeout/невалидный receipt/неподтверждённое исключение старого gate запрещают APP-коммит. Конкретный процесс, durable-файл, ключ, fencing и ресурсы EDGE проходят свой ARC-10 review; до этого PUB29 может иметь только интерфейс/fixture, но не заявлять успешный `unpublish_page`.

### 5.2. Локальный deny-only срез APP

Это не второй публичный gate и не сетевой вызов на обычном запросе. Admission-controller APP получает подписанный/аутентифицированный snapshot TRUST, проверяет incarnation, монотонный head/generation, policy fingerprint и привязку PageID/PRIMARY, после чего атомарно раздаёт каждому процессу текущего APP cohort локальный неизменяемый срез. Resolver Django сначала применяет обычные правила APP, затем этот срез:

- `PENDING_DENY`, `HIDDEN` и `DELETED` запрещают содержимое точного PageID/пути; `PENDING_DENY` и недоказанная согласованность дают контактный 503, `HIDDEN` — принятый пустой белый 200;
- `LIVE_NO_SET` только снимает прежний TRUST deny, но не может превратить `Page.is_published=False` в публикацию;
- неизвестная policy, несовпадение PageID/path/fingerprint, регресс generation или отсутствие свежего подтверждения не дают разрешения;
- новый процесс не попадает в load-balancer, пока не применил не более старый срез; исключённый/не ответивший процесс не входит в подтверждённый cohort;
- cohort receipt связывает APP run/incarnation, TRUST incarnation/head/generation, точный digest среза и все process incarnation. Он не заменяется ответом одного worker.

Контроллер обновляет срез по явной операции и при startup/restore; периодический scheduler этим предложением не вводится. Конкретные IPC, readiness endpoint, срок свежести, fencing процессов и хранение snapshot должны пройти отдельное ARC-10 review. До их реализации profile остаётся выключенным и ни fixture, ни один локальный worker не доказывают production-ready публикацию.

## 6. Клиент APP↔TRUST

Рекомендуется закрытый stdlib-клиент по образцу проверенного `trust/journal/consumer.py`, но отдельно для мутаций:

- HTTPS с проверкой собственного CA и фиксированным именем `trust-ingress`;
- child-процесс `python -I` для DNS/TLS/drip I/O, убиваемый по общему deadline;
- connect до 2 секунд, весь запрос до 6 секунд, body/response до 1 МиБ;
- только фиксированные targets `/v1/head`, `/v1/operations/<uuid>`, `/v1/prepare`, `/v1/report`;
- закрытая JSON-schema, canonical SHA-256 и десятичные bigint-строки;
- секреты не попадают в DTO, URL, исключения, audit и test artifacts;
- транспортная неопределённость всегда разрешается GET status по тому же ID, а не новым POST с новым ID.

Новых Python-зависимостей не требуется. Клиент не вызывается из модели, сигнала, `on_commit` или под DB/content lock.

## 7. Последовательность операции

### 7.1. GET подготовки

Owner получает точные название/PageID/PRIMARY URL, текущее состояние публикации, текущую редакцию и последствия. GET не создаёт `PublicationIntent`, receipt или TRUST operation. Сервер выдаёт UUID операции и подписанное основание: actor/security generation, action, PageID, PRIMARY Route ID/target, current revision ID/hash, публикация, parent/position и число завершённых publication receipts. В token нет HTML, секретов или произвольных команд.

### 7.2. POST

1. Проверить метод/content type, CSRF, активную owner-сессию, security generation, UUID и подпись. Даже exact replay повторно требует актуальный вход владельца.
2. В короткой APP-транзакции взять content → auth → Page/Route locks в принятом порядке, повторить права/основание и создать неизменяемый `PublicationIntent(LOCAL_INTENT)`. Освободить locks.
3. Вне APP-транзакции прочитать head и отправить закрытый TRUST Prepare `route_publication`. Потерянный ответ проверять по operation status и fingerprint. Подтверждённый Prepare переводит `trust_phase` в `PENDING_DENY`.
4. Вне APP-транзакции применить `PENDING_DENY` ко всему допущенному APP cohort по §5.2, проверить cohort receipt и CAS-перевести `local_phase` в `APP_DENY_APPLIED`. Без доказательства normal traffic остаётся закрытым, APP-коммита нет.
5. Только для `unpublish_page` вне APP-транзакции потребовать подтверждённый EDGE close по §5.1 и CAS-перевести `local_phase` в `GATE_CLOSED`. Без реального receipt выполнение здесь прекращается; тестовый fixture не разрешает менять Page.
6. Снова войти в короткую APP-транзакцию и повторить owner/session/basis/PRIMARY/current revision. При изменении основания не выполнять старое действие; оставить безопасный TRUST pending и показать необходимость reconciliation.
7. При актуальном основании изменить только `is_published`, создать локальный receipt/audit и `MAIN_COMMITTED`. Для unpublish дополнительно проверить сохранённые APP cohort и EDGE gate receipts. `mainReceipt` — canonical digest фактических неизменяемых локальных полей и обязательных receipts, а не доверенная строка браузера. Normal route остаётся закрыт локальным `PENDING_DENY`.
8. Вне транзакции отправить committed-report с точным local main incarnation/receipt и итогом `HIDDEN` или `LIVE_NO_SET`. При тайм-ауте запросить status по тому же ID.
9. После доказанного `FINAL_POLICY` применить соответствующий final-срез всему текущему APP cohort и проверить новый receipt. Для publish только этот шаг разрешает normal Django показать страницу; для unpublish APP остаётся false, normal Django даёт пустой 200, а аварийный gate закрыт.
10. После раздельной сверки неизменяемых prepare и final cohort receipts с их phase/head/generation перевести intent в `COMPLETE`. Digest final receipt записывается один раз и не заменяет prepare digest; receipts иной фазы взаимозаменять запрещено. Владелец получает полный успех только после этой сверки; после APP-коммита и до неё показывается «Изменение записано, проверка доступа не завершена» с безопасным ID операции.

Отказ до TRUST Prepare не меняет APP. После Prepare безопасность имеет приоритет над доступностью: недоказанный abort/commit не открывает маршрут. Слепой повтор с новым UUID запрещён.

## 8. Рестарт и сверка

Owner-only экран состояния показывает незавершённые `PublicationIntent` без секретов. При открытии или точном retry система:

- читает TRUST operation status и сверяет prepare/phase fingerprint, а не только stage;
- сравнивает Page/Route/current local receipt и, для unpublish, EDGE close receipt по неизменяемым ID и digest;
- если APP-коммита нет, новый текущий owner-сеанс должен получить свежее подписанное основание и явно подтвердить продолжение; исходная session binding сама по себе не переносит право между сессиями;
- если APP-коммит уже доказан immutable local receipt, текущий заново аутентифицированный owner может выполнить только транспортную финализацию того же committed-report без повторного предметного действия и без требования старой session binding;
- отозванный/истёкший сеанс без нового входа ничего не продолжает; смена security generation до APP-коммита требует нового основания;
- если APP и TRUST расходятся или status недоступен, сохраняет deny и `RECONCILE_REQUIRED`;
- не запускает автоматический scheduler, массовое исправление или открытие по времени.

Операторское recovery/fence/activate остаётся DEV-15 и не вызывается из web APP. После восстановления ни аварийный gate, ни normal Django не открываются по одному старому локальному `is_published`; до допуска normal traffic обязателен следующий барьер D-307/PR-04.

Normal-start/restore admission contract является обязательной зависимостью, а не будущей оговоркой:

1. После старта или восстановления APP readiness закрыта; Nginx не направляет normal traffic в новый cohort и возвращает безопасный контактный 503.
2. Admission-controller получает свежие TRUST head/snapshot и сверяет TRUST incarnation, монотонные generation/head, policy fingerprints и сохранённые publication receipts с восстановленной APP DB.
3. Он строит deny-only срез §5.2. Более новая `HIDDEN`/`PENDING_DENY` перекрывает восстановленный старый `is_published=True`; `LIVE_NO_SET` не перекрывает локальный `is_published=False` в сторону разрешения.
4. Каждый worker применяет один точный срез и возвращает process receipt. Только полный receipt текущего cohort разрешает readiness и прямой normal Nginx→Django без дальнейшего сетевого вызова на каждом запросе.
5. Недоступный TRUST, невалидный snapshot, потерянный локальный receipt, неизвестная policy, несовпадение incarnation/generation или незавершённая reconciliation оставляют readiness закрытой. Автоматически доверять старому Boolean, локальному кэшу до restore или истёкшему cohort receipt запрещено.

Этим документом normal-start/restore barrier только конкретизируется как зависимость. DEV-29 не реализует и не включает его, а production publication flag остаётся выключенным, пока механизм не пройдет отдельный план, ARC-10 review, многопроцессную проверку и сценарии ниже.

## 9. Предварительные проверки до кода

| ID | Проверяемый результат |
|---|---|
| PUB29-001 | GET owner показывает точный PageID/PRIMARY/current/publication и не пишет APP/TRUST; employee/direct request получает отказ. |
| PUB29-002 | Hidden→publish: Prepare даёт PENDING_DENY, cohort применяет deny; APP-коммит меняет только publication/receipt/audit, но normal остаётся 503. После final LIVE_NO_SET и нового полного cohort receipt normal Django видит страницу; аварийный путь остаётся 503. Draft/current/URL/tree/Stable/media/главная прежние. |
| PUB29-003 | Published→unpublish: TRUST PENDING_DENY применён полным APP cohort и закрывает normal traffic; подтверждённый EDGE close receipt закрывает новые аварийные допуски до APP-коммита. После APP false и до доказанного TRUST HIDDEN + полного final cohort receipt normal остаётся контактным 503; только затем даёт пустой белый 200. Дети сохраняют свои flags/ID/URL. |
| PUB29-004 | Exact replay каждого завершённого action возвращает тот же APP/TRUST receipt без второй версии, audit, intent или generation. Другой payload под тем же ID — конфликт. |
| PUB29-005 | Потерять ответ Prepare/report/status по очереди: различаются PREPARE_UNKNOWN и REPORT_UNKNOWN, один operationId, честный unknown, без второго APP-коммита и без открытия pending. |
| PUB29-006 | Изменить current revision, PRIMARY, права, session generation или publication во время сети: повторная проверка отказывает старому действию; TRUST остаётся deny/reconcile. |
| PUB29-007 | Одновременные publish/unpublish и две вкладки сериализуются CAS по intent revision; устаревшая операция не затирает более новую и не создаёт ABA через возврат Boolean. |
| PUB29-008 | Ошибка APP receipt/audit/commit полностью откатывает APP; TRUST pending сохраняется. Ошибка TRUST finalize после APP-коммита показывает незавершённость. |
| PUB29-009 | Рестарт APP на каждой стадии позволяет продолжить только точный intent по fingerprint/status/receipt; до APP-коммита новая сессия требует нового основания/подтверждения, после доказанного коммита разрешена только транспортная финализация. Потеря локальной записи не превращает deny в allow. |
| PUB29-010 | Snapshot и consumer различают PENDING_DENY/HIDDEN/LIVE_NO_SET; LIVE_NO_SET не принимается как готовый аварийный HTML и не обходит PageID/path binding. |
| PUB29-011 | Redirect на скрытую страницу сохраняется; PRIMARY скрыт. Hidden parent не меняет child publication. Неизвестный/второй PRIMARY отклоняется. |
| PUB29-012 | Writer/reader/recovery разделены; неверный role/secret/epoch/incarnation/permit, drift credentials и прямой доступ к TRUST API/DB закрыты до предметного SQL. |
| PUB29-013 | Доказано отсутствие HTTP/DNS/TLS ожидания под APP transaction/content/auth/Page locks; deadline/kill/reap и bounded body/response соблюдены. |
| PUB29-014 | UNIT и MAIN fingerprints, прежние TRUST history/head/архивы и исходники до/после связаны; собственная fixture очищена, права возвращены, journal CLOSED, контейнеров 0. |
| PUB29-015 | Измерены новые строки/байты, combined APP+TRUST RAM/CPU/PIDs и сеть без повышения caps; полный профиль отказывает при фактическом пределе вместо очистки истории. |
| PUB29-016 | Feature flag по умолчанию выключен; нет production-кнопки, публичной/аварийной выдачи, sitemap или объявления полного DEV-29/ARC-10/DEV-26/27 готовыми. |
| PUB29-017 | Wire negatives: пустая/двойная policy, чужой PageID/PRIMARY, непустые requestIds, REDIRECT/DELETED/LIVE_NO_SET в неправильном kind, другой action/basis под тем же UUID и доверие одному stage без fingerprint отклоняются до APP-коммита. |
| PUB29-018 | EDGE close: timeout, старое generation, иной PageID/target, неверная подпись, не исключённый прежний gate и рестарт между close/APP-коммитом оставляют APP опубликованной и intent незавершённым; ложный close receipt не принимается. |
| PUB29-019 | Завершить unpublish до HIDDEN, восстановить более старую APP DB с `is_published=True` и перезапустить: readiness закрыта, normal Django не выдаёт содержимое; свежий TRUST snapshot применяет HIDDEN до допуска cohort. |
| PUB29-020 | Startup/restore при недоступном TRUST, неверном snapshot/receipt, регрессе generation, неполном cohort или неизвестной policy остаётся 503. Один worker/старый receipt не открывает load-balancer. |
| PUB29-021 | Восстановленная APP DB с `is_published=False` не публикуется одним TRUST `LIVE_NO_SET`: deny-only срез не имеет разрешающей силы. После PENDING_DENY→LIVE_NO_SET normal publish открывается только новым final cohort receipt. |
| PUB29-022 | Prepare/PENDING_DENY cohort receipt нельзя подменить final receipt и наоборот: phase/head/generation/digest mismatch отклоняется; `mainReceipt` сохраняет prepare proof, а COMPLETE требует отдельный final proof после рестарта и exact replay. |

До исполнения эти сценарии имеют статус `NOT_RUN`. PUB29-003/018 нельзя объявить PASS на fixture вместо настоящего проверенного EDGE close. Полный e2e ночного набора, 301/URL/delete и production остаётся в соответствующих DEV/TEST задачах.

## 10. Альтернативы

1. **Рекомендуется:** additive `PublicationIntent` в APP + минимальное расширение текущего TRUST protocol/state + локальный deny-only срез и startup/restore barrier APP + обязательный подтверждённый EDGE close перед unpublish APP-коммитом. Даёт restart/retry/restore evidence, сохраняет прямой normal Nginx→Django без удалённого per-request gate и не ломает историю DEV-15.
2. Переиспользовать только `OperationReceipt` APP. Меньше схемы, но нет долговечной стадии до main commit и надёжной инвентаризации незавершённых операций после рестарта; не рекомендуется.
3. Ждать полного DEV-25/26/27 и реализовать всё одним большим участком. Уменьшает число временных feature flags, но объединяет APP writer, gate, HTML sets, controller и внешнее размещение в один рискованный шаг; можно выбрать, если владелец не хочет промежуточную локальную проверку.
4. Переключать `is_published` и отправлять TRUST позже через `on_commit`/очередь. Окно раскрытия и откат APP нарушают PR-04; не допускается.

## 11. Вопрос владельцу

**DEV29-Q004.** Согласовать ли конкретную архитектуру координации `publish_page`/`unpublish_page`: additive `PublicationIntent` в APP, `route_publication` + `LIVE_NO_SET` в существующем TRUST, deny-only срез и startup/restore barrier для APP cohort, два APP credential, одна internal network и обязательный подтверждённый EDGE close перед APP-коммитом снятия публикации, при сохранении прямого normal Nginx→Django режима D-307 без удалённого вызова на каждом запросе?

Ответ утвердит или отклонит только архитектуру; никакую реализацию публикации этим ответом автор не начинает. После согласования сначала нужен отдельный точный план и его разрешение владельцем. Даже тогда TRUST/APP/publish выполняются лишь в явно разрешённом локальном объёме, production flag остаётся выключенным, а изменение `is_published` для `unpublish_page` заблокировано до реального независимо проверенного EDGE close. Ответ **не разрешает** ночной HTML, URL/delete, внешнее размещение, старый сайт, VPS или production.
