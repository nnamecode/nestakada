# DEV07-CLOSE-02 — результат явной отмены подготовки

2026-11-01. Основания D-366, SC-001 и [SC07-001–008](dev07-shared-cancel-checks.md). CLOSE-02 завершён в ограниченной локальной области: 7 новых framework-тестов, 13 регрессий и 2 браузерные группы успешны. Независимые pre-code, product, QA и actual-evidence ревью положительные. DEV-07 остаётся в работе — около96%, этап8 около20%.

## Поведение

В выбранной собственной подготовке восстановления шапки/подвала появилась явная отмена с подтверждением. Она переводит held→released, атомарно снимает только её активные pins и записывает terminal provenance/receipt/audit. Current, draft, версии, фотографии и их usage не меняются. Изменение current после подготовки не требует возвращать сайт назад ради отмены; отмена работает только с собственным held stage и актуальными owner/session/generation.

HTML не загружается в parser отмены. Source/base, actor/generation, terminal metadata и точный набор pins входят в metadata stamp; подмена/неполный набор отвергаются. Прежние writer stamp/current guards сохранены, исключение current-base equality действует только для cancel. Stage metadata остаётся, поэтому LC продолжает защищать source/base версий; отмена не разрешает очистку истории или фото.

Малый закрытый POST stages/<canonicalUUID>/cancel/ имеет16KiB Nginx/application границы, early owner admission и genuine CSRF. Action restore_cancel идёт через прежний leased durable book/reserve4MiB/snapshotIncrement0/quota протокол. Released receipt имеет NULL result identity без изменения схемы; ACK bound к точным terminal operation/block/actor/generation/source/base и fingerprint пути. Exact replay проверяется до held lookup. Нет новых пакетов, схемы, ресурсов, томов или production-настроек.

UI сохраняет RAM-ввод, не отправляет запрос при отказе от подтверждения и блокирует Check/Draft/Apply отменённого stage. Актуальный источник открывается новой вкладкой с noopener/noreferrer. При потере ответа автоматического повтора нет; ручное действие повторяет прежние body/operation UUID и выясняет durable исход. UNKNOWN не освобождается принудительно.

## Проверки

| Свидетельство | Результат |
|---|---|
| Новый framework module, отдельная unit БД | 7 PASS,178.456s. Оба блока, source=base/≠base, один/два pins; preserved current/draft/other stages/refs/files; replay/new session/result; роли/CSRF/closed DTO; stale current, terminal/missing/wrong-block/corrupt pins/actor/generation; atomic rollback/postcommit uncertainty; held UNKNOWN/profile-off. |
| Конкуренция | Настоящие две PG connections: cancel command удерживает session lease на book_durable вне SQL, framework HTTP Apply получает503 BUSY; один cancel, без публикации. Это command↔framework HTTP witness, не два сетевых запроса. |
| Прежний reservation module | 13 PASS,144.268s. Сохранение/восстановление, replay, session revocation, actual abort/debt/partial blob/postcommit fault и accounting guards не сломаны. |
| SC07-007 через обычный Nginx/local_http | PASS с первого native запуска:6 прямых негативов (duplicate JSON/bool generation/query/kind/content type/16KiB+1), без stage/pin/receipt mutation. Confirm decline→0POST, accept→одна отмена; RAM сохранён, terminal Apply запрещён. |
| SC07-008 | PASS с первого native запуска: реальный fetch получил успешный200 после commit, ответ оборван; новый текст остался, ручной exact body/UUID replay дал прежнюю receipt/audit без второй отмены. |

Prepare в native — настоящий авторизованный HTTP после просмотра истории, а не нажатие несуществующей DOM prepare-формы. Browser cancellation выполнялась реальными кнопками. Observer не является product endpoint/middleware; нет QA URLConf/settings/image overlay. Framework читает JSON через явно обозначенный DjangoClient seam, native проверяет настоящий socket путь.

Raw PG/FS evidence:3 наблюдения/170 событий, максимальное effective usage5,382,144байт при прежнем пределе268,435,456; превышений0. Abort debt524,288байт сохранился после rollback/replay. Эти числа относятся к конечным сценариям, не доказывают универсальную стоимость любой отмены/новую MAX-калибровку.

## История замечаний

- Первый framework прогон:3 PASS, затем fixture FAIL на4-м тесте,110.816s. Повторный prepare пытался создать новый draft из current при уже существующем draft. Сохранён immutable failed snapshot; независимое ревью подтвердило одну правку повторного prepare(draft=False), которая сохраняет существующий draft и все negative oracles. Новый полный7-test прогон PASS. Product ради теста не менялся.
- До native запуска root и рецензент независимо нашли SC-QA001: hash всего Budget ошибочно запрещал законные derived-cache updates. Fixture теперь сохраняет singleton/accounting_version/retained_debt, отдельно измеряет actual quota и допускает только изменения snapshot_count/charged_bytes. Budget не переписывается. Добавлен actual admission перед собственными малыми seed-файлами. Это исправление QA до первого native запуска, не дополнительный native PASS.
- Первая диагностическая nginx -T команда root не указала compose-selected -c и проверила встроенный default, получив read-only pid ошибку. Вывод сохранён; после чтения реальной Compose-команды nginx -T -c /preflight/nginx.conf успешен на обоих cohorts. Рабочий конфиг/запуск продукта не менялись ради диагностики.

## Цепочка и завершение

Финальный ordinary cohort `80262f74-f2e4-4847-a0c7-113e33cccd06`:231 app файла, source manifest SHA256 `2832ddd4478673c67c0882cea8c7afef3ca4404776d037417069148f7bbbc924`. Host/frozen/product/QA без drift. Прежние проверенные app782/base094/worker и receipt634b9163… сохранены, миграций нет. Failed first cohort и его source manifest не перезаписывались.

Native run `3f9401c6-42da-40ca-9e59-0586667ba66b`, top PASS/failed=null/stderr0. Fixture создал только собственные исторические source snapshots, никогда не назначал их current. Scoped synthetic teardown удалил только свои transient stage/revision/refs/blob и Asset через product cleanup. Users/pages/assets/own stages/revisions0; baseline/system route/policy/debt сохранены. Permanent SharedReceipt24, SharedIdentity66 и append-only audit857 не очищались.

После synthetic teardown actual quota:655360байт, snapshots0/held0/debt0. Непереписанный derived cache наблюдался отдельно: snapshot_count2/charged_bytes753664; он может быть stale после прямого удаления синтетических fixture rows. Это не pristine cache, не reset бюджета и не product terminal GC. Фактическое измерение остаётся источником проверки квоты.

Локальные свидетельства вне Git: work/dev07-shared-cancel-20261101/{before-receipt.json,product-freeze.json,http-freeze.json,cohort-first.json,cohort-fixed-fixture.json,framework-first.txt,framework-fixed-fixture.txt,quota-evidence-summary.json,reservation-regression-first.txt,native-first/host-report.json,nginx-effective-fixed-fixture.txt,stop-final.txt,final-checks.json,final-preservation.json}. Стенд остановлен, private files/named volumes сохранены; commit/push не выполнялись. Старый сайт/VPS не затронуты.

Остались CLOSE-03 диагностика/исправление мобильного overflow и CLOSE-04 конечный normal cohort (включая Shared Apply/complex/media/MAX). TEST09/10 и зависимые DEV сохраняют обязательства; DEV-07 целиком/этап8/production не закрыты.
