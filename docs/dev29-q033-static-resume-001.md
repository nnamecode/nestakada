# Q033-STATIC-RESUME-001 — предложение возобновления

Дата: 2026-11-05. Статус: предложение, до ответа владельца исполнитель остановлен.

## Основание и границы

DEV29-Q033 уже согласован (D-557). Исполнитель q025_builder остановлен по AGENTS.md после двух нарушений ограничения вывода: первое усечение контекста, затем uncaught ALLOWLIST_SHAPE с выводом публичного stdin/stack. Между ними сохранённый validator завершился PROTECTED_COUNT: все выбранные 22 сравнения прошли, но ожидалось24. Третья однотипная попытка не допускается. Freeze отсутствует. Source59, syntax44, 220 distinct PASS сохраняются; они не означают static PASS. Docker/SQL/private/Prepare/Readiness/Rehearsal/Run в Q033 не запускались.

Разрешение требуется только на возобновление остановленной статической задачи. Архитектура, единственный условный Run, все review-gates, rollback, сохранение корпуса, очистка и лимиты Q033 остаются прежними. Новый цикл/UUID не создаётся. Старые partial files сохраняются. Старый сайт/VPS исключены.

## Точное доказательство списка

Канонический список — files[].path в work/dev29-bounded-20261104-resume007/protected-equivalence.json (SHA256 3fdb922f869898480f07b66f5755054a09bf5302cabb1864fbda5dbf3c2c1cb6), а не revision004/static-protected-equivalence.json: последний содержит флаг и цепочку хешей, не массив24. Цепочка revision004→revision003→revision002→корневой evidence и parent package проверена координатором в публичной карте docs/dev29-q033-protected24-map.json (b3c25cc5268f0e8e7975f0e7fdd178e90d9bd556b8a535a91981312fe001c2a8).

Исполнитель использует docs/dev29-q033-protected24-execution-map.json (7ed0cbaf582a386b5a053544dfd03c8fa9d136419f71b16952eeb2edaab4af50). Все24 пути связаны с baseline-checkpoint/manifest.json новой resume008 (df4543a0f9b08b140f9e940fa61a49b8ecb4f4d65147fdd57aacd2b1d7d6bb6b) точным путём и beforeSha256. Нормализация только обратных слешей. Нельзя выбирать по одному хешу: одинаковые HBA-файлы остаются отдельными путями. Registry path получается path.posix.relative('real-host', canonicalPath).

Прежняя выборка22 содержит16 канонических и6 дополнительных путей. Сохранить все22 сравнения и отдельно обеспечить канонические24: объединение30, без удаления6 прежних. Новые8 канонических путей вне прежней выборки также проверяются. Карта пока подтверждает только parent/checkpoint metadata, не текущие байты candidate.

## Последовательность после ответа владельца

1. Прочитать один известный публичный файл за раз; raw-фрагмент≤800, весь вывод предварительно≤1000 символов. Без индексов, JSON-context crop, широкого поиска, raw stack/source echo. Любая диагностика имеет гарантированный top-level catch с коротким кодом. NOT_FOUND — навигационные данные, не разрешение угадывать schema.
2. Зафиксировать исходный final-static-validator.mjs SHA256 3718f258f92c9def83eb60b9281dbd67776087f7c579aae63be53b905cc62a84. Сначала прочитать оставшиеся проверки, не потерять ancestry/dependency/identity/registry/exact-patch checks. Исправлять только validation input, не runtime source59 и не архитектуру. Project imports перенести под гарантированный catch (dynamic import) либо использовать ограниченный launcher, перехватывающий stderr без вывода содержимого. До запуска сохранить/readback/hash исправленного checker и launcher, проверить синтаксис. Все syntax checks, включая checker и launcher, запускать только через внешний bounded capture: parse error возникает до JS catch. Raw stdout/stderr, фрагменты source и stack не передавать в модель; выводить лишь закрытый код/счётчики в пределах1000. При syntax failure validator execution не начинать.
3. Заменить ошибочную папочную интерпретацию protected24 на pinned exact map. Для каждого пути сверить checkpoint hash и текущий candidate с разрешённой точной миграцией run/prefix и единственным derived SQL digest; ожидаемые изменения определять из утверждённых baseline/proofs, не из фактического candidate. Сохранить все22 прежних сравнения и все остальные ограничения. Source registry59 и точный key-host patch56e1af… остаются обязательными.
4. Один исправленный static execution после успешных предпосылок. Зависимые шаги только после PASS предыдущего. Вывод только закрытые счётчики/коды≤1000; полный публичный отчёт в файле с readback/hash. При первой ошибке сообщить факт и новое свидетельство; не повторять автоматически. Повтор эквивалентной ошибки — немедленный STOP по AGENTS.
5. Только после static PASS — exact source freeze и независимое whole-candidate code review. Checker/launcher/map hashes входят в validation evidence отдельно от runtime/test registry59. Не повторять220 тестов без изменения соответствующих исходников/зависимостей. Если source59 всё же требует изменения — остановить этот план и предъявить причину; молча менять пакет нельзя.
6. Fresh NOAUTH rehearsal, Prepare и остальные независимые допуски возможны только по исходной последовательности Q033 после code APPROVED. Ни один actual mode этим предложением сейчас не выполняется; все одноразовые бюджеты Q033 пока не израсходованы.

## Приёмка

SR33-01: canonical24 exact paths + parent/checkpoint bindings, сохранены legacy22 и union30.
SR33-02: все прежние static checks сохранены; source59 unchanged; никаких ослаблений expected/guard.
SR33-03: закрытый вывод и ошибки, saved/readback/hash validator; отсутствие raw stack/source echo.
SR33-04: static PASS и freeze только по факту, затем независимое code review; до этого actual modes0.
SR33-05: сохранены220 distinct PASS без двойного счёта counters17 внутри focused43; прогресс DEV-29≈35%, этап8≈31%.
