# DEV-07 — фактические локальные проверки

2026-10-31. D-329/D-330/D-331. DEV-07 в работе; подключение редактора к приложению ещё не допущено. Старый сайт и VPS не использовались. Артефакты с содержимым проверок остаются в ignored `work/`.

Этот документ фиксирует предыдущую подготовку пакета/pure/runtime. Последующее продолжение D-332/D-333, поддержка таблиц/actualURLContext и isolated HTTPcheck описаны в [dev07-check-implementation.md](dev07-check-implementation.md); прежние пометки table/context pending ниже относятся к исходной ограниченной когорте. Основная конфигурация и полная DEV-07 по-прежнему не приняты.

## Пакет

Canonical pnpm lock сохранён в `environment/editor-package/pnpm-lock.yaml`, SHA256 `30606d44defa218232418b780977a7707f4b6fb547fc8232e3afffb99bded7b6`: 74 identities, 25 необязательных esbuild-платформ пропущены, 49 архивов проверены. Производный file-tarball lock отклонён policy pnpm и не используется. Фактический путь: canonical frozen fetch, затем отключение сети контейнера и frozen/offline install с запретом lifecycle scripts. Peak временного builder 349294592 байта. Протоколы: `work/dev07-20261031/npm-canonical-fetch.txt`, `npm-builder-detached.json`, `npm-canonical-offline-install.txt`, `npm-store-resource.json`.

Python установлен из пяти проверенных wheels в ограниченном контейнере без сети: pip check PASS, peak 89804800 байт. COPY-only образ кандидата `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986`; UID10001:10001, linux/amd64. Docker inspect подтвердил восемь исходных слоёв базы `sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951` и один добавленный слой `sha256:8246b813e7a5fcc81bfe567de6e45f0d6bc8c9af19c6b48b61af4624bacaf5fe`. Основа стенда и media worker не переключены.

Python library probes: 12 PASS, включая реальные импорты/native ABI, HTML5/CSS, ограниченный pathological corpus и три restricted-profile upstream PoC. Максимальный наблюдавшийся RSS 53168 КиБ. Протокол `work/dev07-20261031/python-candidate-probe.txt`. ELF NX/RELRO/BIND_NOW и зависимости проверены в `native-elf.json`. Это не проверка будущего producer и не устранение трёх vendor advisory ammonia4.1.4; условия и остаток — `dev07-package-security.md`.

## Браузер и реальная несовместимость

Первоначальный JS oracle ошибочно требовал удалить own data key `__proto__`; фактическая безопасная реализация использует Object.defineProperty. Oracle исправлен с сохранением проверки prototypes/canary. Исходный результат сохранён в `work/dev07-20261031/js-first-probe/`.

Исправленная проба: семь групп PASS, затем реальный FAIL `PKG-JS006 SAFE_STYLE_ROUNDTRIP`: повторное открытие стандартного inline-style HTML теряет форматирование и даёт пять CSP style-src-attr нарушений. Группы007/008 после отказа не запускались. Повторный отчёт и bundle сохранены в `work/dev07-20261031/js-corrected-oracle-probe/`, stdout — `js-candidate-probe-corrected-oracle.txt`. CSP не ослаблена, oracle не изменяется ради этого FAIL. Нужен проверенный semantic carrier adapter; default Tiptap пока не допущен.

## Неподключённый runtime helper

`app/editor_runtime/` реализует профили64/5/4МиБ, process/thread-safe неблокирующий слот, socket deadline чтения, фиксированный framed child exchange, bounded stdout/stderr, kill/reap и resource limits. HTTP handlers его ещё не используют; producer module пока отсутствует.

20 unit/socket/process проверок PASS за1.709с: `work/dev07-20261031/runtime-unit-first.txt`. Независимый рецензент прочитал код и протокол; блокеров на этой ограниченной границе не нашёл. Реальные HTTP auth/CSRF/framing, полный максимальный payload, aggregate parent+child RAM/CPU и доменная фиксация не проверены. JSON encoding context и decoding результата у родителя также входят в будущий общий ресурсный замер.

Отдельная синтетическая JSON/pipe проба в контейнере768МиБ/1CPU: 43469413байт,500строк/32колонки/10000текстовыхячеек и два текста по200000astral codepoints; обмен с JSON parse/serialize дочернего процесса и decode родителя PASS за1.141с. Parent peak232380КиБ, child145756КиБ, cgroup peak246403072байта. `work/dev07-20261031/transport-memory-first.txt`, исходник `transport-memory-probe.py`. Это проверка механизма обмена, не максимального HTML/schema/политики/HTTP; поля умышленно синтетические, productPolicyValidated=false/httpAdmission=false.

## Чистый валидатор прайса

`app/page_editor/price_policy.py`: закрытый PriceV1 без Django/SQL/записи, устойчивые UUID и порядок,500строк/32колонки/10000ячеек, Unicode codepoint limits, пустые/текстовые ячейки не превращаются в ноль. Decimal принимает экспонентный ввод и даёт canonical сумму без float/округления; нечисловые/отрицательные/сверхпредельные значения и доли меньше копейки отклоняются. Нормализация должна быть явно показана будущим UI перед записью.

Первый набор9 pure unit проверок PASS за0.216с, `work/dev07-20261031/price-policy-first.txt`. Независимое ревью выявило ошибку измерения codepoints до CRLF normalization: исправлена, добавлены точные positive1000/negative1001 после normalization. Повтор9тестов PASS за0.208с — `price-policy-crlf-fix.txt`; других блокеров в этой pure-части рецензент не нашёл. [Промежуточное ревью](dev07-review.md). HTTP, права на price и сохранение этим не проверены; модуль ещё не подключён к child/handlers.

## Чистая политика HTML/CSS

`app/page_editor/html_policy.py` и закрытые вспомогательные модули реализуют проверку полного исходника до nh3, HTML5 дерево, допустимые semantic marks/styles→carrier, безопасные абсолютные/корневые ссылки и explicit anchor binding, отдельные source/text/node/depth бюджеты, повторный parse/semantic comparison/idempotence. Произвольные шаблоны/JS/CSS/загрузки не исполняются. Restricted cleaner имеет один фиксированный профиль без style/SVG/filter_style_properties; upstream vendor residual остаётся.

Независимые [сценарии N07](dev07-normalizer-checks.md) и `test_policy.py`: **23 unit methods с подслучаями PASS за4.403с**, `work/dev07-20261031/html-policy-first.txt`. Reviewer подтвердил регрессии закрывающих тегов с attrs, незавершённой разметки EOF, опасных native PoC до cleaner, cleaner-drift и границ. Изменённый ввод получает предупреждение необходимости явного принятия; UI принятия пока отсутствует.

**Не реализованы в этой части:** valid tables/protected media placement/relative URL public context и semantic style reset. Они возвращают ControlledUnsupported после полной проверки безопасности, не успешный усечённый HTML. Это не прохождение всей N07/полных функций редактора. Браузерный carrier adapter и публичный renderer не подключены.

Реальная совместная pure policy+pipe проба в контейнере768МиБ/1CPU: price500строк/32колонки/10000ячеек с1000astral codepoints, полные подписи500 и **два HTML поля ровно1МиБ с200000text codepoints каждое**. Вход43966555байт; настоящие normalize_price/normalize_html и framed обмен PASS за4.502с. Child AS384МиБ/CPU10с и exchange wall20с; raw удержан до результата как в bootstrap. Parent peak238044КиБ/child239032КиБ, cgroup peak290615296байт. Исходник/протокол — `work/dev07-20261031/policy-memory-probe.py` и `policy-memory-first.txt`. Это уже реальная pure policy на этом corpus, но completeWireDtoValidated=false/httpAdmission=false: полный DTO, Django, identity/CSRF/commit/остальные допустимые структуры не проверены. Пределы не повышались.

Усиленная отдельная проба совмещает **во всех двух HTML полях одновременно1МиБ/200000text codepoints/20000узлов/depth32** с тем же большим прайсом. Реальные возвращённые metrics и содержимое проверены независимо в probe. PASS за8.688с; parent peak238008КиБ/child265352КиБ, cgroup peak343117824байта; все пределы прежние. `work/dev07-20261031/policy-complexity-probe.py` и `policy-complexity-first.txt`. Это подтверждение конкретного сочетания границ, не доказательство худшего времени каждого допустимого варианта оформления и не запас полного Django/HTTP процесса. Интеграционный допуск остаётся закрыт.

## Открытые ворота

Продолжение D-334 и более поздние actual save/adapter/Nginx свидетельства вынесены в [dev07-ui-save-implementation.md](dev07-ui-save-implementation.md). Ниже сохранены исходные ворота library/pure cohort; они не означают, что последующая работа отсутствует. Полный transport, draft/restore/protected/shared и production admission остаются открытыми. Native advisory residual не снимается браузерными PASS.

- Довести оставшиеся table/protected/relative/reset возможности pure producer и semantic Tiptap roundtrip под прежней CSP; текущий ограниченный cohort не подменяет готовый редактор.
- Согласованный transport profile: реальные early auth/CSRF, slow/abort/framing, полный допустимый максимум и общий ресурсный бюджет до допуска handlers.
- Атомарные сохранения/права/restore и реальный UI, отдельные общие блоки и измеренный учёт их квот. Удаление строк PostgreSQL не обещает уменьшить физический размер отношений.
- Полные публичные renderer/cross-page anchors, миграция и production остаются зависимыми задачами; library probes не закрывают соответствующие AC.

## Повтор чистых проверок

Из корня проекта, только при наличии ровно указанного локального образа кандидата. Команда не запускает стенд и не даёт приложению сетевой доступ:

```powershell
docker.exe run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --user 10001:10001 --memory 768m --memory-swap 768m --cpus 1 --pids-limit 128 --tmpfs /tmp:rw,noexec,nosuid,size=128m --mount 'type=bind,source=T:\nestakada\app,target=/app,readonly' --workdir /app sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986 python -B -m unittest editor_runtime.test_guards editor_runtime.test_processing page_editor.test_price_policy -v
```

Для независимого HTML/CSS набора тем же контейнером выполнить `python -B -m unittest page_editor.test_policy -v`. Комбинированная команда приведена для воспроизводимости; фактические вышеуказанные результаты получены отдельными адресными прогонами. Кандидат не заменяет принятую основу до остальных ворот.
