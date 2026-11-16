# TEST-08 exact10 execution — implementation/run status

## Финальный статус D-1128 — COMPLETE / APPROVED

Этот раздел заменяет прежний статус «приостановлено» ниже, который сохранён как
хронология диагностики. Итоговый named run
`6ad87bdf-8f8f-41df-b037-508a963697ca` через
`scripts/test-editor.ps1 -Suite test08-execution` завершён: methods2/2,
`T08-G01`–`T08-G10` PASS за159.755с, system check0, migrations no changes.

- public registry:114 ответов200 + runtime redirect302 =115 targets;
- fixture:112 pages/114 DB routes/237 READY media;
- media before/after237/45,064,743B, gallery originals214 preserved;
- requests0, public forms0, external delivery0;
- reserve2×48,759,896B/387 files, host peak97,519,792B;
- teardown: все закрытые DB counts0, media/reserve/staging removed;
- receipt: `work/foundation/test/test08-results/6ad87bdf-8f8f-41df-b037-508a963697ca-execution.json`.

Product remediation была ограничена exact3 contacts JPG→WebP и строгим bounded
ASCII `mailto:user@domain` для уже существующей contact-ссылки. Renderer/model/
migration/dependency/endpoint/new feature не добавлены. Named regression:
DEV-09 services65/65 PASS102.869с; DEV-25 73/73 PASS29.662с. Wildcard,
прямой широкий `manage.py`, Playwright, network delivery, live/deploy/VPS0.
Foundation stopped, private/named volumes retained. Final repeat independent
review: `APPROVED`, P1/P2/P3=`0/0/0`; TEST-08 execution завершён.

Первый final review вернул provenance findings P1/P2=1/1: запрещено менять
исторические analytics manifests и нельзя выдавать новые WebP за v3 originals.
Remediation вернула пять manifests без diff, сохранила MED-0005–0007 как
исходные JPG и добавила ровно MED-0315–0317 как offline derivatives с parent
SHA, pinned converter и `v3_exists=false`. Повторные named DEV-09/TEST-08 выше
подтвердили новые authority/package SHA. Repeat review закрыл оба findings;
новых замечаний нет.

Дата: 2026-11-15. Статус: **ПРИОСТАНОВЛЕНО ВЛАДЕЛЬЦУ** по anti-loop.

## Реализовано до остановки

В утверждённой границе подготовлены изменения:

- credential seam в `app/content/test_test08_fixture.py`;
- новый exact10 `app/content/test_test08_execution.py`;
- named `test08-execution`, closed marker/receipt и bounded reserve cleanup в
  `scripts/test-editor.ps1`.

PowerShell parser и `git diff --check` PASS. Product endpoint/model/migration/
dependency/template/JS/framework0. Foundation после остановки выключен,
private volumes retained; staging cleaned, reserve per-run directory absent.

## Две эквивалентные попытки

Обе named попытки выполнялись только через
`scripts/test-editor.ps1 -Suite test08-execution`, без wildcard, прямого
широкого `manage.py` и Playwright. Обе остановились в первом oracle-шаге до
fixture и до T08-G01:

1. Run `449eb448-9c3b-486e-9a9f-9c1e2b9514e9`: Python искал
   `/docs/analytics-route-map.csv`.
2. После изменения `BASE_DIR` и fresh immutable snapshot run
   `f7bf7aea-d5ac-492c-a523-e56bbb05c413` искал
   `/app/docs/analytics-route-map.csv`.

Причина одна: one-shot test container монтирует frozen application source в
`/app`, а repository `docs/` туда не входит; route map доступен отдельным mount.
Это test-harness path binding, не дефект продукта. Попытки2, третьей нет.

## Изменившееся условие для возобновления

После явной команды владельца выполнить одну ограниченную remediation без
новой функциональности:

1. package descriptors читать из существующего `/app/content/...`;
2. route registry читать из уже смонтированного `/test08-route-map.csv`;
3. `docs/analytics-media-evidence.csv` валидировать host SHA и смонтировать
   отдельным readonly `/test08-media-evidence.csv`;
4. fresh foundation, staging и одна named попытка. Эквивалентный повтор снова
   останавливает работу.

До успешного exact10 run общий TEST-08 остаётся NOT_COMPLETE; implementation
review, TEST-09/10, production/live/VPS закрыты.

## Owner resume D-1124 и product integration finding

Владелец разрешил «Почини и Продолжай». Oracle paths исправлены: packages
читаются из `/app/content`, route/media registries — из отдельных readonly
mounts с host SHA. Fresh run `fe2065fd-0952-4777-a688-e1a09fb3dc0b` собрал
fixture и дошёл до G01; первая harness-ошибка `Client is not callable` была
устранена механическим rename helper. Fresh run
`2fdd2c7f-8c32-4b98-9c60-319f4b431e32` дошёл до literal public URLs и получил
`/contacts` status503.

Read-only диагностика подтвердила product integration defect: exact3 contacts
assets из `dev09n_remaining_content.json` имеют JPEG bytes/storage `.jpg`, но
зарегистрированы как non-legacy `AssetFile.Kind.MAIN`. Existing public/shared и
media preview contracts разрешают non-legacy MAIN только RIFF/WebP. Изолированный
DEV-09N public test использовал fake shared renderer и не открывал host media
bytes, поэтому gap ранее не обнаружился. TEST-08 real shared renderer открыл
файлы и fail-closed вернул503. Это не основание расширять MAIN до JPEG.

Рекомендуемая minimal product-content remediation требует отдельного owner gate:
offline convert exact3 contacts JPG→WebP, update only their package
relative/storage paths+bytes+SHA and exact package/test hashes. No model,
migration, dependency, renderer widening, endpoint or new function. После
review/permission — focused DEV-09N real-shared regression, fresh TEST-08 named
run и independent review. Foundation stopped; staging/reserve absent.
