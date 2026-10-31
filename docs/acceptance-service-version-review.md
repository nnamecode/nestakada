# Квоты служебных данных и отказы сохранения версий

2026-10-30. Этап7, D-301/302/303/305/308 и прямое поручение владельца. Прежние изменения сохранены. Только тесты/оснастка/документы; старый сайт/VPS/БД/файлы/ОС/настройки не менялись, код нового сайта не писался.

## Подготовлено

| Набор | Экземпляров | Частичная область |
|---|---:|---|
| service-quota.spec.js |4 | AT310/AC-OPS-010:receipt20000/16MiB, throttlekeys/tempпоactualconfig, ограниченныйнаблюдаемыйотказ, allvalidreceiptcohort сохранён, expired-onlycleanup, рабочиезаявки/согласия/usedmedia/solegoodset целы, positiveпослеосвобождения |
| version-storage.spec.js |15 | AT117/119/AC-DTL-017/019:Header/Footer common256MiB/10000snapshotquota, warning75%+успешнаязапись, publish/restoreотказбезauto-prune/потериввода; Page versioninsert/Assetref failure атомарны, несовместимыйsnapshotнепереписан |
| SAFE024по2cap/SAFE033 |3новых | service-quota/content-storage permits отделены друготдруга/прежнихdomains, businesssave/delete/quotaoverrideчерезcontrolзапрещены |

[Служебные данные](acceptance-service-quota.md), [версии](acceptance-version-storage.md), [транспорт](local-test-adapter.md). Новые численныеthrottle/tempлимиты не вводились. Конкретные значения/измерения/physicalscope ещё требуют ENV/ARCготовности. Бюджет120с относится только к тестовомуинструменту. Новых productionнастроек/интеграций/контроллера/поддельногобизнесдвижка нет.

19сценариев приложения **не исполнялись**:нет приложения/bridge/bindings/controller/physicalARC10. UIinput наблюдается в настоящем actor DOM; preparationконтракт требует actualDB pages+sharedBlocksbefore/after. Большие истории передаются boundedID/hash/count проекциями в пределах1MiBstdio, не всеми256MiBpayload. Provenance/неусечение/ресурсныйучёт ещё проверяются при реальном подключении.

## Независимое ревью

Автор versionstorage — version_quota_fault_tests, servicequota/оснастки/исправлений/интеграции — координатор. service_version_review проверял read-only, не исправлял результат.

| ID | Приоритет | Замечание | Исправление/результат |
|---|---|---|---|
| TEST-R059 | P2 | Проверка однойoldreceipt могла пропустить вытеснение другой действующей; будущийsurvivorcohortбезфактическоговремени мог скрыть раннееудаление | До любыхPOST capturedполныйactual-livecount/manifest; отказ/повторне меняетего. Доcleanup проверенexactactualclock==рассчитанномуcutoff, затем тотженепросроченныйcohort сохранён. Независимо закрыто |

Других существенных замечаний в целевой частичной области нет. Полные AC/TEST-07/UX-07 не утверждены.

## Фактические проверки

- **83 driver-safety passed**, skipped/unexpected/flaky=0,12,816с; `test-results/acceptance/driver-service-version-results.json`, `work/acceptance-driver-service-version.txt`. Рецензент отдельно сверил JSON. Предыдущие80 не суммируются с пересекающимися83.
- **1007 tests in 37 files**, контейнерное перечисление exit0, `work/acceptance-stage7-list-service-version.txt`. JS/PowerShell синтаксис проверен авторами/рецензентом/координатором по своим частям. Это сборка списка, не исполнение19сценариевсайта.
- После синхронизации **4 документные/изоляционные проверки passed**, skipped/unexpected/flaky=0,2,849с; `test-results/acceptance/documents-service-version-results.json`, `work/acceptance-documents-service-version.txt`. git diff --check без ошибок. Это проверки оснастки/документов, не19сценариевсайта.

Матрица140AT: **21 text_only /7 partial_http /112 assertions_waiting_driver**. AT117/119/310 впервые получили partialassertions. 140AC/63REQ/115MAP/RTE сохранены; ни один полный AC не объявлен пройденным. Всё сохранено локально без commit/push.

## Остаток

Физическийучёт индексов/резервов/temporaryпиков/конкурентныхwriters, точнаяграница74.99→75.00, всеTTL/cleanupcrash/unknowncommit/источникиpressurediagnostics, ручнаяочисткаистории/всеincompatibleсхемы и конкретныеSQL/FS/transaction/DOMbindingсвидетельства ещё отдельно. Source/rollback/measurements flags не подменяют испытание. Наследованиеправасотрудником/всеprotectedfields и другиеприёмочныеветви сохраняют своинаборы.

Этап7 продолжается, полный TEST-07/UX-07/physicalARC10 открыт. Код этапа8/production требуют отдельного согласования владельца.
