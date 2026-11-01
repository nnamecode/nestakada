# DEV07-SH-LC — ручная очистка версии и диагностика

2026-11-01, D-354/D-355. **Ограниченный локальный инкремент выполнен; независимое ревью без открытых блокеров.** DEV-07 около98%, этап8 около20%; полный DEV-07 остаётся в работе. Старый сайт и VPS не затрагивались.

Основания: согласованные [предложение](dev07-shared-lifecycle-proposal.md) и [11сценариев до кода](dev07-shared-lifecycle-checks.md). После DEV07-LC-RESUME-001 сверены93paused app SHA без расхождений; сохранены164before/173paused файла. Чужие изменения не откатывались.

## Что работает

Только nesadmin выбирает одну допустимую старую file-version шапки/подвала, видит состав и причины запрета, подтверждает актуальным паролем. Current, draft base, source/base всех Stage независимо от terminal status, pins и неподдерживаемые/неясно защищённые состояния исключены. Причины показаны по-русски; новых Stable-команд, автоматической очистки и удаления фотографий нет.

Additive0005 добавляет SharedCleanupJob: постоянные operation/target/block/actor, fingerprint, descriptor HTML, фазы и удержанный запас. Задание фиксируется до удаления строки истории. Удаление выбранной строки, только её AssetUsage, фаза и audit атомарны; permanent identities и прежние receipts сохраняются. Unlink вне SQL проверяет конкретный файл, отсутствие оставшихся ссылок, inode/SHA/nofollow/parents/fsync. Если файл ещё используется, он сохраняется, что прямо показано владельцу.

При сбое после удаления metadata остаётся честный частичный результат и ручное продолжение того же задания. После потери ответа оно находится через ссылку в истории. Новый сеанс требует свежего подтверждения и пароля. Завершённые задания остаются учтёнными и запрещают повторное использование retired file key. Изменившиеся защиты у prepared job оставляют его заблокированным для технической проверки; автоматической отмены нет.

Диагностика показывает actual receipt/book/quota; известный matching outcome можно сверить вручную. Старые admitted shared-local-v1 книги совместимы только по точному4МиБ профилю и исходным receipt/SHA bindings; новые записи используют shared-local-lc-v1. No-receipt/corrupt/mismatch/fault остаются held/blocked; shared-unvetted-v1 не получает settlement authority. Неизвестный размер не превращается в0, долг не сбрасывается.

## Проверки и точные снимки

| Набор | Факт / источник |
|---|---|
| Functional LC |16PASS143.901с:13HTTP/PG и3standaloneFS;216files/run d765f032-1ce7-47cd-976f-e27c0f0ccc96, manifest ab7964ab13c43959fd9ef06c54db33dcefee06ff28b8b6449a212fdf6ec340fe; runtimeFalse |
| Калибровка |4PASS419.065с:3RC+1cleanup heavy, тот же216-file source ab7964ab… |
| Первый общий запуск |31тест/288.511с,1FAIL/4skip: старый oracle ожидал8roots вместо9. Отказ сохранён, не назван PASS |
| Исправленный общий запуск |98найдено/94выполнено PASS479.349с/4heavy skip;216files/run7e7c8dc5-e901-4ffd-a6c9-e1ac22bf4e2f, manifest3ee2333f5683592406414a9deb39dacbf483ab8254289cadd12bdce2a576f521; runtimeFalse |
| Chromium/Nginx LC |4/4PASS, включая русский запрет current/preview cancel, actual delete/файл/фото/несохранённый текст, commit→transport abort→history job link и read-only diagnostics/privacy |
| Chromium/Nginx RC |5/5RSV-UI действительно повторены на финальном source: late ACK/new text, exact lost-response replay без дубля, Footer Draft→Apply, real auth generation reset с сохранностью ввода |

Оба браузерных набора выполнялись на финальных216files/run364d47bf-cd6c-4c78-a547-ea6c12b5a760, manifest1567d8a9bcfb3008caa5fe8543621a9644dc7287bfa0fef2c3d31c7dd1e5402f; runtimeTrue для точной локальной среды. Это Chromium через согласованный Playwright1.64.1 и Nginx; версия Chromium отдельно не фиксировалась. PageErrors/stderr0, оба own cleanup подтверждены.

Разница A→B — только test_shared_http.py:9roots/9OID плюс независимая сверка Job таблицы через pg_class/pg_namespace; размеры/forks/sum/corrupt-cache oracles не ослаблены. Разница B→финал — только3пути: profiles.py (3reviewed constants enable/signature/FSid) и2шаблона с русскими причинами/подписями. Backend, численные параметры и selectors не изменились. Условие роли unit исключает runtime branch; mainDB/app_runtime проверены браузером. Не заявляется один source для всех запусков;16проверок входят в94 и не прибавляются к ним как уникальные.4heavy пропущены в общем запуске намеренно, их отдельный PASS указан выше. Исторические402регрессии этим инкрементом не повторялись.

## Учёт и измеренный запас

Job — девятый собственный PG root с индексами/TOAST/forks. Maintenance reserve2097152 и headroom131072байт находятся внутри прежних268435456байт; ordinary Save оставляет запас обслуживания. Учёт собственных файлов/orphans/PG bloat, назначенной доли общей AssetUsage и retained debt сохраняется. Ресурсы и бюджет не повышались, VACUUM FULL/автосброс долга не применялись.

В конечной калибровке Save отклонён при used264253440. Холодное создание job дало264310784 (рост57344), с hold2097152 effective266407936≤268435456; запас2027520байт. Headroom131072 превосходит наблюдавшийся рост на73728байт. После unlink большого файла used263258112, малого263249920; PostgreSQL после DELETE не уменьшился. Hold стал0 только после complete.

Профиль допущен только для dev/test, mainDB estakada_foundation/app_runtime, PG180006/block8192, FS4096/fsid16471834453763965976 и exact schema a4190d7eb672ccc7de7453158803d2d826d1c9a9923e3ba802cc2feb7b54cf14. Иная схема/среда закрыта. Эти числа — конечные наблюдения с запасом, не универсальное доказательство для произвольного накопленного числа jobs/аллокатора или отключения хоста.

## Независимое ревью

LC-REV001: защищены все Stage зависимости. LC-REV002: diagnostics известной книги использует точный held/resolved proof. LC-REV003: после потери ответа доступна настоящая history UI ссылка. LC-UI001: русские причины и безопасный fallback вместо технических кодов; current label проверен браузером.

LC-QA001: actual hidden confirmation/CSRF tokens проверены на утечку. LC-QA002: только тестовый child получил тот же разрешённый hasher, production настройки не менялись; обе реальные границы os._exit79 достигнуты и продолжены HTTP. LC-QA003: новые destructive unlink negatives wrongSHA/symlink/hardlink/inode replacement/parent rename сохранили old/new victims и не вызвали unlink. LC-QA004: устаревшие8roots исправлены на9 с независимым catalog oracle; actual общий PASS подтверждён.

Рецензент лично прочитал actual результаты, сверил216SHA без drift и различия снимков. [Запись ревью](dev07-review.md). Проверки process exit не доказывают физическое отключение VPS.

## Завершение и остаток

Стенд остановлен с сохранением томов: manifest activeFalse, работающих foundation-test и собственных browser контейнеров0. Оба synthetic root удалены, live users/pages/versions/drafts/stages/assets0. Permanent jobs/receipts/identities сохранены; baseline Budget восстановлен только как synthetic teardown, это не продуктовый обход долга/защит.

Final216 frozen/host SHA совпадают;50прежних app файлов вне shared_content неизменны.0001–0004 совпадают с before, применённая0005 не переписывалась. `makemigrations shared_content --check --dry-run` на калибровочном unit-контейнере: exit0, No changes detected; после него моделей не меняли. Git push не выполнялся.

Локальные свидетельства: work/dev07-lifecycle-20261101/{cleanup-first.txt,calibration-first.txt,calibration-summary.json,shared-final.txt,shared-root-oracle-fixed.txt,native-first/host-report.json,rc-native-final.txt,stop-final.txt,final-checks.json}; RC host-report — work/dev07-reservation-20261101/native-fixed-lc355/host-report.json. Секреты и логи не отправлялись в Git.

Полный DEV-07 остаётся в работе: публичные Header/Footer/menu/validators, остатки table/price/legacy/browser, явные stage lifecycle/cancel и полное операторское восстановление no-receipt UNKNOWN отдельно. Массовая очистка orphan/terminal Stage metadata не включена. Старый сайт/VPS/production не менялись.