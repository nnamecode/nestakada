# TEST-08 — план сверки acceptance evidence

Дата: 2026-11-15. Статус: **READY FOR REPEAT INDEPENDENT PLAN REVIEW**.

## 1. Основание и цель

TEST-08 exact10 завершён D-1128: named run
`6ad87bdf-8f8f-41df-b037-508a963697ca`, methods2/2 и группы
`T08-G01`–`T08-G10` PASS. Это доказательство локального base-MVP fixture, но не
автоматический PASS 140 acceptance criteria.

Физический TEST-09 остаётся `BLOCKED` по D-1034 без выбранного disk-backed
hard-cap storage backend; owner D-1035/Q009 разрешил оставить backend на потом.
TEST-10 остаётся `DEFERRED` D-1076 из-за реальных browser/session-egress source
gaps. Ни один из этих gate не обходится локальным предположением.

Цель текущего этапа — механически связать закрытый TEST-08 result с уже
существующими строками `docs/acceptance-automation-status.csv`, не создавая
новых требований, тестов или функций.

## 2. Точный scope

Разрешены только:

1. read-only чтение `docs/acceptance-cases.csv`,
   `docs/acceptance-automation-status.csv`,
   `docs/implementation-traceability.csv`, `docs/acceptance-gap-register.md`,
   `docs/test08-execution-plan.md` и финального TEST-08 receipt;
2. изменение поля `executable_ids` и/или пояснения `remaining` только у строк,
   где конкретный `T08-Gxx-*` scenario прямо доказывает часть существующего AC;
3. один новый отчёт `docs/test08-acceptance-reconciliation-results.md` с exact
   before/after counts, changed case IDs и сохранёнными ограничениями;
4. обычные записи D-xxxx в `docs/tasks.md`, `docs/decisions.md`,
   `docs/pipeline.md`.

Запрещены product/runtime/test code, новый validator/runner/framework,
Playwright, Docker/Foundation/browser/network, изменение acceptance case text,
REQ/AC/AT IDs, `automation_state`, routing group, launch checklist и любые
production/live/VPS действия.

## 3. Неизменяемая исходная база

Сверка разрешена только при одновременном совпадении всех значений ниже.

| Артефакт | Размер, байт | SHA-256 | Строки/состав |
|---|---:|---|---|
| `docs/acceptance-automation-status.csv` | 40532 | `86BA721CF7A289F6EB69D451332BAE534798BC6B588EF2CB6A61D90DDC8D25A1` | exact140; `text_only=17`, `partial_http=20`, `assertions_waiting_driver=103` |
| `docs/acceptance-cases.csv` | 241481 | `CEFA16B77D62C5B5C99244472852384ECC57087BAD56B959912CF38A428B6538` | exact140 |
| `docs/implementation-traceability.csv` | 15294 | `D0643646A15FF3A1D22F1A6425CBF003BE93C9FA2881E4B5A8963D8FA4C55B12` | exact140 |
| `work/foundation/test/test08-results/6ad87bdf-8f8f-41df-b037-508a963697ca-execution.json` | 10543 | `280E9BE1E9CF1E0FAC02CD685A2A402470B7D12C5051C9CD48DA065FB6671214` | schema `test08-execution-result-v1`; runId `6ad87bdf-8f8f-41df-b037-508a963697ca`; `allPassed=true`; exact10 groups PASS |

Receipt обязан содержать exact37 уникальных scenario IDs:

`T08-G01-A..D`, `T08-G02-A..D`, `T08-G03-A..C`, `T08-G04-A..D`,
`T08-G05-A..D`, `T08-G06-A..D`, `T08-G07-A..C`, `T08-G08-A..C`,
`T08-G09-A..D`, `T08-G10-A..D`.

Несовпадение хотя бы одного SHA/размера/count/schema/runId/status/set прекращает
этап без записи. Эти значения являются before-image текущей сверки, а не
попыткой нормализовать ранее грязное рабочее дерево.

## 4. Exact whitelist и границы evidence

Из exact140 разрешено изменить ровно следующие 10 строк. Расширение списка
требует нового плана и независимого review. Все остальные 130 строк остаются
byte-for-byte прежними.

| Group | Единственная строка | Добавляемые IDs | Доказанный фрагмент по receipt `actual=expected` | Обязательный сохранённый остаток |
|---|---|---|---|---|
| G01 | `AT-001 / AC-001` | `T08-G01-A..D` | exact115 route set: 114×200 и 1×302; pinned public projection | полный source/content oracle вне fixture и production apply |
| G02 | `AT-003 / AC-003` | `T08-G02-B..C` | выбранный parent скрыт пустым 200, дети/URL/parent сохранены, повторная публикация и navigation projection | persistent real-tree apply; responsive/manual не заявлять |
| G03 | `AT-015 / AC-015` | `T08-G03-A..C` | login/logout и прекращение доступа текущей session к private routes | idle/hard expiry, unsaved real-tab и different-user workflow |
| G04 | `AT-018 / AC-018` | `T08-G04-A..D` | назначенный сотрудник, разрешённое сохранение, protected fields, stale conflict, revoke | persistent public observation и полная role/field matrix |
| G05 | `AT-019 / AC-019` | `T08-G05-A..D` | manual/Stable/compare/employee restore и exact10 ordinary | production accumulated-history/resource behaviour и races вне fixture |
| G06 | `AT-026 / AC-026` | `T08-G06-A..D` | допустимый upload, picker/cleanup guard, invalid rejection и exact214 originals unchanged | worker-down/unknown receipt, production storage/runtime и vendor gate |
| G07 | `AT-008 / AC-008` | `T08-G07-A..C` | exact17 albums/exact214 originals, home/page2/modal 200 и SEO projection | persistent publication, responsive/manual TEST-10 и source-content oracle |
| G08 | `AT-030 / AC-030` | `T08-G08-A..C` | base profile: public forms0, requests0, external delivery0; owner setting200/employee403 | enabled intake, required fields, LEGAL, real PII, SMTP/TG и production |
| G09 | `AT-038 / AC-038` | `T08-G09-A..D` | owner audit200/employee403, bounded retention, readiness safe output и rotation evidence | full9 source/category fixture, storage-fault incompleteness и production |
| G10 | `AT-047 / AC-047` | `T08-G10-A..D` | two builds, current/previous generations, removed partial, closed reserve output | night/day scheduling, production durability, physical/external operation |

Диапазон в таблице — сокращённая запись только плана. В CSV записываются
литеральные IDs через `;`, например четыре отдельных `T08-G01-A` …
`T08-G01-D`; синтетические wildcard/range IDs запрещены.

## 5. Правило включения evidence

Для каждой строки exact whitelist независимо применяются четыре условия:

1. AC и AT существуют по одному разу во всех канонических реестрах;
2. конкретный TEST-08 scenario проверяет тот же observable result, actor и
   boundary, а не только соседний компонент;
3. evidence действительно присутствует в final receipt group со status PASS;
4. все непокрытые production/external/manual/physical/real-device/LEGAL gates
   остаются перечислены в `remaining`.

Если хотя бы одно условие не выполнено, весь bounded pass прекращается без
записи. Строка вне whitelist всегда остаётся byte-for-byte прежней.
Общие формулировки вроде «группа прошла» или совпадение по названию подсистемы
не являются основанием.

## 6. Формат изменения

- В `executable_ids` допускаются только canonical IDs вида `T08-G01-A` …
  `T08-G10-D`, существующие в финальном receipt и плане.
- Существующие IDs не удаляются и не переименовываются; новый ID добавляется
  через `;` без дублей.
- `remaining` получает короткую датированную ссылку `D-xxxx TEST-08 local
  evidence` и затем явно сохраняет прежний остаток.
- `automation_state` всех140 строк сохраняется дословно. Full PASS count остаётся
  0; exact vector остаётся `text_only=17`, `partial_http=20`,
  `assertions_waiting_driver=103`.
- Default-off G08 может доказывать только отсутствие формы/заявок/delivery в
  base profile; он не доказывает enabled intake, LEGAL, real PII, SMTP/TG или
  production transport.
- Server markup G02/G07 не заменяет TEST-10 responsive/visual/device evidence.
- G09/G10 local operations не заменяют TEST-09 physical ENOSPC/load и external
  monitoring/backup/production restore.

## 7. Атомарная запись и закрытые проверки

До изменения строятся в памяти candidate CSV, changed-row report и точный
before-image исходного файла с pinned SHA выше. Candidate обязан пройти все
проверки ниже до замены рабочего файла. Затем выполняется одна замена только
`docs/acceptance-automation-status.csv` и запись одного отчёта; management docs
обновляются отдельным обычным patch после успешной проверки.

Если ошибка возникла до замены — рабочий файл не меняется. Если ошибка возникла
после замены — восстанавливается только текущий
`docs/acceptance-automation-status.csv` из сохранённого before-image и удаляется
только незавершённый reconciliation report. Запрещены `git reset`, `git
checkout`, восстановление всего дерева и затрагивание чужих dirty changes.

После будущей сверки coordinator обязан read-only подтвердить:

- rows140, unique AT140, unique AC140, missing/extra0;
- exact allowed automation states и неизменный vector `17/20/103`;
- все добавленные `T08-*` IDs принадлежат exact final receipt scenario set;
- удалённых прежних executable IDs0;
- changed rows равны exact whitelist10; остальные exact130 строки
  byte-for-byte эквивалентны before-image;
- no full-PASS wording, no TEST-09/10/launch gate removal;
- `git diff --check` PASS.

Регрессионные тесты не запускаются: это traceability reconciliation, а не
изменение продукта или test harness. Финальный diff требует независимого
read-only review.

## 8. Stop rule и следующий gate

Первая ошибка mapping/validator останавливает изменение до точной причины.
Повтор разрешён только после изменившегося условия; вторая эквивалентная ошибка
приостанавливает этап владельцу, третьей попытки нет.

Текущий gate — независимый review этого плана. Только `APPROVED` открывает одну
bounded reconciliation pass; TEST-09 backend installation/physical run,
TEST-10 execution, launch/live/VPS остаются закрыты.
