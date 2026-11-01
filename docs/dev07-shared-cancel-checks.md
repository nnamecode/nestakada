# DEV07-CLOSE-02 — явная отмена подготовки общего блока

Обновление после проверок, 2026-11-01: CLOSE-01 и CLOSE-02 выполнены; [результат отмены](dev07-shared-cancel-results.md). Остались CLOSE-03/04, DEV-07 около96%, этап8около20%. Ниже сохранён исходный контракт/аудит до реализации, не текущий перечень выполненного.

2026-11-01. До кода и запусков. Основания D-366, DEV07-CLOSE-02/SC-001, dev07-editor-contract §6, REQ-013/016/017/022/054 и AC-013/054/DTL-004/006/015–017. Сценарии уточняют предусмотренную отмену, не разрешают удаление истории или force UNKNOWN.

## Техническая граница для независимого pre-code ревью

POST `/manage/shared/{header|footer}/stages/<canonicalUUID>/cancel/`, только малый JSON≤16KiB: ровно protocol="shared-editor-v1", generation(int), operationId(canonicalUUID), confirmCancel=true. Stage связан с URL и fingerprint; query/лишние/повторяющиеся ключи/boolean generation запрещены. Nginx отдельный16KiB allowlist и shared admission до CSRF; прежний large allowlist не расширяется.

Action `restore_cancel` использует прежний leased `_run`/durable journal/reserve4MiB/snapshotIncrement0/actual quota/receipt/audit. Новый storage, schema/migration, компоненты или увеличение лимитов не нужны. Receipt result_id/type=NULL допустимы действующими ограничениями, result_code="released"; выбранный stage хранит terminal_operation_id/terminal_actor_id. ACK содержит только подтверждённые metadata, resultId=null, editorContext=null, stageId/outcomeKnown; не возвращает candidate/автоподстановку.

Cancel context — metadata-only: fresh owner/session/generation, свой held stage нужного блока, source/base и точный набор его active pins. Не читает HTML/blob/Asset, не вызывает parser. Метаданные и pins входят в stamp и перепроверяются внутри commit. Изменившийся current сам по себе не требует публикации/переноса старой основы: отменяется та же собственная подготовка. Terminal/wrong actor/generation/kind, подменённые metadata/pins отказывают до нового book. Поля schema/policy только фиксируются в stamp, payload не интерпретируется.

Exact replay проверяется до требования held и возвращает durable исход; altered action/path/body с прежним operation конфликтует. held→released, terminal provenance, удаление только pins выбранного stage, receipt/audit и квота атомарны. Stage/source/base metadata остаются; LC по-прежнему защищает их версии. Current/draft/revisions/AssetUsage/файлы не меняются. UNKNOWN не освобождается принудительно, долг не обнуляется.

UI: кнопка только для выбранного собственного stage, явное подтверждение. Отказ подтверждения не отправляет запрос. Текст остаётся в открытой вкладке при успехе/ошибке/потере ответа. После подтверждённой отмены старый stage больше не используется для Check/Draft/Apply; актуальный источник открывается отдельно. Неопределённый результат допускает только ручное выяснение/точный повтор той же операции, без autosend/new operation.

## Закрытый ACK и коды отказа

Pre-code ревью положительное, 2026-11-01; код разрешён в прежних D-366 границах. ACK отмены: ровно ok=true, operationId, resultId=null, resultCode="released", replay(boolean), gone=false, editorContext=null, stageId и outcomeKnown=true. Stage ищется по matching terminal operation/block/actor/generation/status, ровно одна запись; неоднозначный/потерянный terminal результат — SHARED_RESULT_UNAVAILABLE503.

Fingerprint включает protocol/generation/path stageId/confirmCancel=true. Некорректный DTO/query/confirmation — SHARED_INPUT_REJECTED400; недоступный/не held/чужой stage, неверные pins/metadata — SHARED_SOURCE_UNAVAILABLE409. Подмена operation — SHARED_OPERATION_CONFLICT409. Прежние session/owner/CSRF/reader/quota/BUSY/UNKNOWN коды сохраняются. Известный abort — прежний SHARED_OPERATION_ABORTED409/outcomeKnown=true, postcommit uncertain — SHARED_RESERVATION_UNCERTAIN503/outcomeKnown=false с operationId. Для fault используются существующие metadata_written/db_committed границы, не подмена бизнес-результата.

## Конечный набор

| ID | Проверка | Обязательный результат |
|---|---|---|
| SC07-001 | Реально подготовить свои Header/Footer stage, отменить каждый при существующем current/draft и references; source=base и source≠base | held→released, exact terminal actor/operation, только свои один/два pins сняты; одна receipt/audit, без новой версии/изменения current/draft/других stages/AssetUsage/blob. Реальный quota внутри прежнего предела, permanent ledger сохранён. |
| SC07-002 | Exact replay после terminal состояния и новая session того же actor/generation; повтор operation с другим stage/kind/body/action; lookup result | Прежний durable исход без повторного commit/audit/долга; подмена конфликтует. Никакого payload чтения для replay. Чужой result недоступен. |
| SC07-003 | Anonymous/employee/чужой actor/stale generation/завершённая session/нет CSRF; direct GET/неверный kind/UUID/query/DTO/бюджет | Точный ожидаемый отказ до protected body там, где admission предусмотрен; никакой частичной отмены/receipt/pins mutation. Owner positive control тем же реальным handler. |
| SC07-004 | Terminal/missing/wrong-block stage, изменённые pins/metadata; отдельно current изменён после prepare | Недоступные/повреждённые подготовки не отменяются частично; собственный неизменный held stage отменяется без возврата current назад и без чтения source HTML. История и terminal LC защита остаются. |
| SC07-005 | Реальная ошибка перед/после metadata и до подтверждения commit, потерянный ответ; настоящие конкурирующие cancel/Apply через отдельные PG connections | До commit нет partial stage/pins/receipt; известный abort честный. После commit только durable result/reconcile, не повторная отмена. UNKNOWN остаётся удержанным и не force released. При гонке один допустимый победитель, loser не публикует после отмены и не снимает чужие pins. |
| SC07-006 | Фактическое измерение отмены и отсутствие профиля/резерва/неразрешённая UNKNOWN book | Безопасный отказ без bypass/увеличения бюджета/сброса долга; успешная metadata операция укладывается в существующий reserve, измерения записаны. |
| SC07-007 | Браузер: выбранный Header stage, отказ и принятие confirm, несохранённый canary, затем повторные клики | До подтверждения запросов0. После явного cancel ровно одна операция, текст сохранён, старый stage не отправляется на Apply/Check, current не изменился. |
| SC07-008 | Браузер: Footer cancel с потерей ответа, ввод и ручной exact retry | Нет автоотправок/новой UUID, RAM сохранён, подтверждён прежний результат; current/draft/другой блок сохранены. |

Framework/PG/FS проверки используют отдельную unit БД и существующий calibration scope; подмена quota/profile готовым успехом запрещена. Fault hook только в уже принятых смысловых границах с проверкой фактического достижения. Запрет чтения payload относится к cancel command/replay: существующий quota scanner вправе измерять реальные файлы, это не загрузка HTML в редактор/парсер.

Native свидетели — обычный local_http через Nginx, без product observer/QA URLConf. Перед кодом ревью конкретного fixture: один точно собственный исторический file snapshot на kind с typed identity и READY Asset, не становится current; реальный prepare/cancel через UI/HTTP. Baseline current/draft/block generation/чужая history сохраняются. Teardown под существующим lease/locks касается только owned transient IDs/pins/refs и exact verified blob при0refs; Asset удаляется продуктовой cleanup. Permanent receipt/identity/audit и фактический PG/FS growth сохраняются, SharedBudget/debt не сбрасываются. Если безопасный fixture не подтверждён, native не запускать и не объявлять эти2строки PASS.

Полный Shared Apply/MAX/complex/media набор остаётся CLOSE-04; TEST09/10 и production отдельно. Старый сайт/VPS не затрагиваются.
