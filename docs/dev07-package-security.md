# DEV-07 — проверка состава кандидата, допуск ещё не выдан

2026-10-31, D-330. Это факты подготовки и независимая triage, не утверждение безопасности готового редактора. К приложению ничего не подключено.

## Фактический инвентарь

Полный pnpm lock содержит74 package identities;25 optional esbuild binaries других платформ явно skipped,49 архивов скачаны сSRI/SHA и проверены без выполнения. Python:5 wheels, включая nh3 ABI3 SHA70f5ac8626e899a4bab0ef74ca2f5bd602f49c7b739e6e5026b4afc6d63dac42. Read-only zip-проверка подтвердила допустимые пути/типы, небольшой unpack footprint; AST QA Python прошёл. work/dev07-20261031/python-wheel-inspection.txt.

В самом wheel найден nh3/nh3.abi3.so (ELF64 little,2431944байта) со строкой ammonia-4.1.4 и встроенный nh3.cyclonedx.json. Фактический SBOM имеет78 Cargo-компонентов, SHA870dae533e49ff53c36785c9f623a3e39787826d832c39f4b0540a6f45c0284c; копия work/dev07-package-cache/qa/nh3.cyclonedx.json, протокол sbom-extract.txt. Это связь с составом wheel, а не только предположение по исходному Cargo.lock. Последующие фактические ABI/ELF/library пробы описаны в dev07-local-evidence.md; продуктовый producer ещё не допущен.

OSV querybatch проверил157 записей (npm74/PyPI5/Cargo78), snapshot work/dev07-20261031/osv-package-batch.json. Для npm/PyPI ответ не вернул совпадений, но это не полное доказательство отсутствия уязвимостей. Для ammonia4.1.4 вернулись три реальные affected записи:

| ID | Применимость и исправленные ветки |
|---|---|
| [RUSTSEC-2021-0157](https://rustsec.org/advisories/RUSTSEC-2021-0157.html) | Ошибка escaping CSS url(); требует одновременно разрешённый style и filter_style_properties. Исправления4.1.7 или4.2.3 в соответствующих ветках |
| [RUSTSEC-2021-0158](https://rustsec.org/advisories/RUSTSEC-2021-0158.html) | SVG animateMotion/animateTransform/animateColor при явном разрешении этих тегов; по умолчанию они запрещены. Исправления4.1.7 или4.2.3 |
| [RUSTSEC-2026-0373](https://rustsec.org/advisories/RUSTSEC-2026-0373.html) | Case-sensitive CSS URL() позволяет обход URL/tracking фильтра при включённой CSS-sanitization. Upstream не квалифицирует это как XSS. Исправления4.1.8 или4.2.4 |

**Ammonia4.1.4 не исправлена от этих трёх проблем.** Независимый рецензент подтвердил условия по первичным источникам и actual SBOM. Внешний SVG-анимационный advisory июля2026 с исправлением4.1.4 не заменяет эти более поздние записи. Пустой vulnerabilities в PyPI эту native-проблему не опровергает.

## Только ограниченные изолированные испытания

Рецензент разрешил продолжить изолированные испытания неизменного пакета при закрытом профиле, но не подключение к продукту. Предлагаемая обязательная граница:

- Единственный закрытый вызов nh3 без style/SVG/анимационных тегов и без filter_style_properties; конфигурация не поступает из документа/DTO/пользовательского HTML.
- Исходный опасный ввод отклоняется целиком ещё полноценным HTML5/CSS policy producer до очистки. Нельзя выдать удаление SVG/style библиотекой за реализацию полного отказа пользовательской операции.
- tinycss2 проверяет только принятые семантические значения. Доверенная сериализация переносит их в закрытые server-owned атрибуты/классы, CSSOM получает только построенные из этих значений правила. Произвольные client classes/data/CSS text не переносятся. Форматирование не теряется.
- PoC-регрессии всех трёх записей, положительные форматирование/таблицы/цвет/размер, source-guard неизменяемой конфигурации и тесты будущего реального producer обязательны. При drift профиля допуск открывается заново.

До реализации/прохождения этих условий остаётся native vendor residual; zero-CVE и окончательный security-pass не заявляются. Автоматическая замена версии/состава, компилятор Rust или новый сервис не разрешены; если ограниченный профиль не проходит, новое решение выносится владельцу.

## Остальные первичные записи

- [ProseMirror-view GHSA-c8x8-7fp4-3x9w](https://github.com/ProseMirror/prosemirror-view/security/advisories/GHSA-c8x8-7fp4-3x9w): fixed1.42.3, выбранная1.42.8 выше исправления.
- [Tiptap mergeAttributes GHSA-cp6q-959q-f8rh](https://github.com/ueberdosis/tiptap/security/advisories/GHSA-cp6q-959q-f8rh): upstream fixed3.30.4, выбранная3.32.2. В записи противоречивые текст/ranges, поэтому требуется actual source-check и безопасная prototype-регрессия, а не только сравнение номера.
- [Tiptap Markdown GHSA-j95f-988m-3j2f](https://github.com/ueberdosis/tiptap/security/advisories/GHSA-j95f-988m-3j2f): upstream fixed3.30.5, выбранная линейка3.32.2; наличие/отсутствие markdown в actual графе проверяется отдельно, пакет ради теста не добавляется.
- [esbuild GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99): fixed0.25.0, выбранная0.28.2; serve не используется, binary исполняется только явно после проверки.
- [Tiptap PHP GHSA-4595-7fjw-r3jh](https://github.com/advisories/GHSA-4595-7fjw-r3jh) относится Composer tiptap-php, не выбранному npm графу. [Deprecated html5lib sanitizer](https://html5lib.readthedocs.io/en/latest/changes.html) не используется: html5lib только parser etree, отдельный policy producer обязателен. Запись Bleach не подменяет проверку html5lib parser.

Фактические import/native/12 Python probes завершены, результат и пределы — dev07-local-evidence.md. JS probe выявил реальную потерю форматирования при повторном открытии под CSP; default Tiptap не допущен. Restricted producer/source guard, semantic adapter и полный runtime/HTTP pipeline остаются открытыми gate. Vendor residual сохраняется независимо от library PASS.
