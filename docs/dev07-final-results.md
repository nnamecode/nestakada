# DEV07-CLOSE-04 — фактический итог компонентной проверки

2026-11-02. Все семь конечных логических сценариев имеют положительные свидетельства; независимое итоговое компонентное ревью положительное, открытых обязательных локальных блокеров не обнаружено. DEV-07 и CLOSE-04 завершены в локальной области (100%); этап8 ориентировочно25% по количеству задач:7из29 основных DEV готовы локально. Это не процент всех AC и не оценка срока. Локальный стенд остановлен, все тестовые данные сохранены. Старый сайт/VPS не затронуты, push не выполнялся.

## Исправленные причины остановок

Продукт после CLOSE-03 не менялся. Исправлялся QA:

- Восстановление владельцем: D-261 разрешает полный content Snapshot, включая H1/SEO. Прежний oracle ошибочно применял employee protectedSame к owner restore. Readonly witness подтвердил точное совпадение source/restored Snapshot hash c5624a6b7d3df7e4ef56094e1737964e815bbe54ce9ffd20c004180a2e8b09e2, неизменные Page/Route/UserProfile/PageGrant, историю/файлы и один restored receipt/consumed stage. Исправлен только owner oracle; проверки сотрудника остались строгими.
- Фото: seed содержит существующий защищённый блок. Visual insert из default selection внутри esProtectedParent штатно запрещён. Тест ждал Check POST, хотя неподтверждённый выбор остановил его на клиенте. Actual readonly diagnostic: issue200, checkPOST0, UI pending; предусмотренный HTML-mode append + завершение issue callback дал COMPLETE/check200/три загруженных изображения. CF006 исправлен без ослабления защиты/повышения лимитов/нового Save.
- Прежние preseed-дефекты lowercase Route и Check-permit save=True устранены по отдельным сохранённым actual findings; публикация embedded источника была единственной bounded continuation, private intent записан до commit, повторной публикации нет.

Каждая QA-правка прошла независимый code review до запуска. Старые FAIL отчёты сохранены и не переименованы в PASS.

## Конечные сценарии

| ID | Фактический результат |
|---|---|
| CF07-001 | PASS как source-bound прежний реально выполненный prefix + новый readonly/UI tail. Exact retained8versions/source/current/receipt/stage/metadata и три роли подтверждены. Повторных Save/restore нет. Исходный native-resume-media остаётся FAIL по ошибочному owner oracle. |
| CF07-002 | PASS: Header и Footer по отдельности Apply A→B→restore A→отдельная отмена held stage; литеральный контакт/provenance/refs и другой блок/Page сохранены. |
| CF07-003 | PASS: complex corpus A, independent semantic oracle, Check/Save/history/selected restore. Canonical SHA9d3653909eb0839dab51c52fe20d8a8d1796fa18a65bab22d871548fca7e6f29. |
| CF07-004 | PASS: complex corpus B, те же проверки. Canonical SHA99239734807320d4161c07a9b06a7d49e5d9bef19550aa214bc12dc724db2c94. |
| CF07-005 | PASS: один отдельный framework test6.501s. Настоящий Save TX и второе PG cleanup-соединение, реальный pg_blocking_pids witness, точный отказ очистки/одна версия/receipt/три физических файла. Это не два socket запроса. |
| CF07-006 | PASS: существующий owner draft с непустыми main/embedded данными, настоящий picker/permit/projected Check и реальные загруженные bytes. После actor switch старых editor POST0, draft403 при действующем Page grant, сохранённые DOM handles очищены; domain/refs/files неизменны. Map clear обоснован source audit, прямое чтение heap/zeroization не заявляется. |
| CF07-007 | PASS: retained S/T и candidate C/D — каждое поле1МиБ UTF8/200000codepoints/20000элементов/depth32; независимые Python/DOM факты, normal Nginx/GUI Check, actual wire/input hashes и проверенный сервером signed receipt. MAX Save не выполнялся, domain неизменен. |

Это шесть браузерных функций в связанных запусках (CF001 дополнительно prefix+tail), плюс один framework test. В финальном continue-media заново выполнены только CF006/007, четыре прежние группы явно помечены reused/evidenceSHA. Не заявляются семь browser tests, шесть заново пройденных групп или единый непрерывный runtime.

## Источники и измерения

App source232 SHA83742e5ae7876d2106ae390726e3723348914a78d3e395abad76dee765ff0bd1 один и тот же для всех CF. Source231 продукта CLOSE-03 отличается только новым test_final_media_http.py. Root final-source-verification.json подтвердил232host/frozen0drift/QA3zero drift/остановленный стенд, unit sourcec12a791501d9a757190fa7adefc1225837d247985cec6f684adf1dd5d917c88c совпадает.

| Свидетельство | Runtime cohort / источник |
|---|---|
| UnitCF005 | 98c423e9-45b2-40ef-a10a-7a0619dbcb16; media-first.txt |
| CF001 исходный prefix | 1a6ea354-a9ec-4b09-aa39-5a19b64072b4; native-resume-media/host-report.json (FAIL сохранён) |
| CF001 tail/CF002/003/004 | c26e1f36-2a49-4967-ac83-626290585bb3; native-continue-restore/host-report.json (поздний CF006 FAIL сохранён) |
| CF006/007 | 321987d2-a9f9-4114-94d0-632958ab9944; native-continue-media/host-report.json, PASS |

Артефакты находятся в ignored work/dev07-final-20261101. Exact final QA SHA: helper08e8c3f32575008638a21ea8a2a0d013ae5d24021502ffd5528a2389ae3a4ca4, probef6003fdc810daf5d8eb8cb7cc42d842a44c5ac4fcee3844a61a507ca5cd9e6ce, host35c1dd042f8d66183bdeaf6ed2109facfa892a584d3ed47f0c0fe9317bb13b8b. Config/package/caps hashes сохранены в host reports; новые компоненты/зависимости/ресурсы не добавлялись.

MAX actual wire2097509B, response2098658B, elapsed8824ms. App whole-container peak250945536/805306368B (около239/768МиБ), CPU1/pids128; browser whole-cohort peak925413376/1073741824B (около883/1024МиБ). OOM0/pageError0/externalRequest0/stderr0. Это измерение одного принятого corpus в данных caps, не универсальный worst-case/пропускная способность VPS/обещание отражения DDoS. Новых CF PNG нет: UI/CSS/JS не менялись, используются прежние6 просмотренных RP07 PNG с exact source binding из карты доказательств.

## Сохранность и остаток

Final retention PASS, baselineSharedPreserved/systemRoutePreserved true. Page versions core8/fmtA4/fmtB4/media3/foreign2/max1; Header/Footer по3. Shared quota usedBytes799744 не является размером всей БД/проекта. Users/assets/девять физических файлов, owner draft и terminal metadata остаются сохранены. No reset/reseed/delete/raw current rollback/forceUNKNOWN, прежние private seed/pending/retained неизменны; continued и media-tail seed/retained отдельные wx. Stop завершён: stop-after-continue-media.txt.

Карта прежних доказательств — dev07-final-evidence-map.md/source-reuse-audit.json. Публичный renderer/URL и дерево/импорт/214 originals остаются DEV08/09/10/15/20/29; полная нагрузка/восстановление/браузеры — TEST08/09/10, полнота unit/integration и общее ревью — этапы9/10. Текущий компонент не закрывает эти задачи и не разрешает deployment.

Итоговое независимое ревью: положительное (combined_review, 2026-11-02). Рецензент лично проверил actual linked reports/retention/232SHA/config/QA и reuse18строк с badRows0 по старым E3/CM manifests, hashes42c0faa8…/8631fa33…. Шесть RP PNG допустимы к reuse: RP231→current232 отличается только unit QA. Все конечные обязательные локальные свидетельства достаточны; DEV07/CLOSE04 закрыты в локальной области. Внутренние E/F/SH-BLOB завершены в этом scope, полного покрытия всех вариантов не объявлено. Следующая доступная DEV20 здесь не начинается.
