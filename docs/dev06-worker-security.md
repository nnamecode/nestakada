# DEV-06 — кандидат обработчика и безопасность native-библиотек

2026-10-31. Разрешение подготовки D-325; это ещё не допуск к upload или завершение DEV-06. Только локально, без VPS/старого сайта. Независимый рецензент выполнил ограниченный поиск первичных advisory; отсутствие найденного blocker не означает отсутствие всех CVE.

## Артефакт

Официальный Pillow13.0.0, CPython3.14 Linuxamd64, wheel SHA256 e91c2b1cbeae768c98752e67e717e283d68dae45717b41f2d91eaee648e37b7d. URL/размер/источник в environment/media-worker/pillow-input.json. Сборка offline из прежней Python-основы, отдельный образ; app/PG/Nginx не заменены. Кандидат Docker ID sha256:1b2bbbe9ac14fa723819209ea674c85d96d0dcaa4402f37b4bc53e0a0bc20af3, Docker size336283832байт (не прирост уникальных слоёв диска). PyPI vulnerabilities=[] — лишь ответ этого источника на дату проверки.

Реальный inventory/SBOM и ldd сохранены в work/dev06-20261031/pillow-inventory.json и native-links.json. Основной _imaging связан в том числе с TIFF/OpenJPEG/xcb; наличие библиотек не исчезает при выборе разрешённых форматов. Выбор JPEG/PNG/WebP обязан применяться непосредственно в каждом Image.open до load; расширение после декодирования не является защитой. Без ImageFont/ImageCms/ImageMath/EPS/AVIF/JP2/TIFF, subprocess только фиксированное собственное задание; не произвольный конвертер.

## Проверенные источники и остаток

| Компонент | Вывод ограниченного независимого поиска |
|---|---|
| Pillow13 | [GHSA-654x-cwwv-5j9c](https://github.com/python-pillow/Pillow/security/advisories/GHSA-654x-cwwv-5j9c) указывает исправление13; дата публикации advisory сама не делает13 уязвимым |
| OpenJPEG2.5.4 | [GHSA-78g4-xqwv-q3g8](https://github.com/python-pillow/Pillow/security/advisories/GHSA-78g4-xqwv-q3g8) исправлена в Pillow13, SBOM содержит cherry-pick91d08b11. Отдельный [PR1674](https://github.com/uclouvain/openjpeg/pull/1674) — другой encode-путь; JP2 запрещён. Не объявлять всю2.5.4 исправленной по одному patch |
| FreeType2.14.3 | Реальный остаток CVE-2026-95512/CVE-2026-50811; [объявление maintainer об2.15](https://www.openwall.com/lists/oss-security/2026/10/13/1). Font API должен оставаться недостижимым. Появление рендеринга шрифтов требует повторной проверки до применения |
| WebP1.6.0 | [Upstream NEWS](https://github.com/webmproject/libwebp/blob/main/NEWS); конкретного нового неисправленного blocker в разрешённом пути ограниченный поиск не выявил. Decode/encode достижимы, sandbox обязателен |
| libjpeg-turbo3.2.0 | [Релиз](https://github.com/libjpeg-turbo/libjpeg-turbo/releases/tag/3.2.0); JPEG достижим, конкретного нового неисправленного blocker не найдено |
| libtiff4.7.2 | [Upstream release](https://libtiff.gitlab.io/libtiff/releases/v4.7.2.html); TIFF запрещён. Это не отключает отдельный EXIF parser JPEG/PNG: metadata/decompression бюджеты остаются нужны |
| LittleCMS2.19.1 | [Upstream hotfix](https://github.com/mm2/Little-CMS/releases/tag/lcms2.19.1); SBOM точнее features2.19. Без ImageCms color-transform не используется |
| libavif1.4.2 | [Upstream release](https://github.com/AOMediaCodec/libavif/releases/tag/v1.4.2); AVIF/AV1 запрещены, сам SBOM не заменяет фактический ldd всех связанных кодеков |
| zlib-ng2.3.3 | [Upstream release](https://github.com/zlib-ng/zlib-ng/releases/tag/2.3.3); compatibility label1.3.1 не делает его обычной upstreamzlib1.3.1. PNG достижим; отдельно учитывать фактически связанные systemlibz и встроенную версию |

В SBOM также присутствуют raqm/FriBiDi/HarfBuzz/libimagequant/libxcb/libXau. Поиск всех их advisory не завершён и не выдаётся за exhaustive audit; font/display/quantize API не допускаются. Исходный Debian/vendor-остаток основы сохраняется. Инвентаризация, ограничение форматов и независимое ревью фактического worker-кода нужны совместно, а не вместо друг друга. [Официальная security guidance Pillow](https://pillow.readthedocs.io/en/stable/handbook/security.html).

## Фактическая квота exchange

Отдельный Docker local tmpfs volume nestakada-dev06-worker-check-exchange, метка nestakada.scope=dev06-worker-check, size128m uid10001 gid10001 mode0770. Реальный nonroot probe записал134217728байт и получил errno28 ENOSPC; файл пробы удалён. Это128МиБ памяти, не обещание обычного disk-volume quota. Доказательство work/dev06-20261031/exchange-quota.json. Это ещё не доказательство корректного отказа приложения при заполнении — потребуется worker/upload integration.
## Минимизированный кандидат после независимого замечания

В environment/media-worker/minimize.py оставлены только native extensions _imaging и _webp и их фактические транзитивные private dependencies. Удалены13неиспользуемых файлов: font/AVIF/CMS/Tk/math/morph модули и только их уникальные библиотеки. Поэтому описанный FreeType-остаток относится к исходному полному wheel, а соответствующий native-модуль/библиотека отсутствует в новом установленном составе. TIFF/OpenJPEG/XCB остаются связанными с core и не названы удалёнными.

Минимизация независимо проверена рецензентом без блокирующих замечаний. Source SBOM сохранён, отдельно фиксируется removal delta с exactpaths/SHA; sourcewheelhash не выдаётся за hash изменённого установленного дерева. environment/media-worker/candidate-receipt.json закрепляет образ/base/входы/удалённые файлы; статус candidate-not-admitted до runtime проверок. Новый DockerID sha256:6105f968d577220973fb9ed8e0caf3ba48a3e028d23d4d324059b4b4b3739f9c. Фактические SHA оставшихся13native файлов и ldd: work/dev06-20261031/minimal-native-evidence.json. Ни одной зависимости not found.

ELF-проверка work/dev06-20261031/native-hardening.json: все13имеют NX stack и RELRO. У12неполный RELRO (BIND_NOW не задан), __stack_chk_fail не найден; libXau имеет BIND_NOW/символ. Наличие/отсутствие символа не подменяет доказательство защиты каждой функции. Это стандартные свойства binarywheel, не обещание такого же compiler-hardening, как у отдельно собранного PostgreSQL. Нельзя объявлять полный hardening или нулевые CVE. Runtime sandbox/resource limits и gate JPEG/PNG/WebP обязательны; применимость остатка оценивается при приёмке worker.

Допуск31.10.2026: после21PASS и реальных probes независимый рецензент подтвердил ограниченную локальную интеграцию. Факты/пределы/точка продолжения — dev06-worker-implementation.md; это не приёмка HTTP-загрузки или production.
