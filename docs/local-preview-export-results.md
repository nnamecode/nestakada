# Локальный предпросмотр base-MVP — результат

Дата: 2026-11-15. Статус: **REMEDIATED, GREEN AND FINAL INDEPENDENT REVIEW APPROVED**.

## Реализация

Утверждённая exact3 boundary соблюдена:

1. `app/content/test_local_preview_export.py` — isolated
   `TransactionTestCase`, existing TEST-08 fixture и DEV-25 reserve build;
2. `scripts/test-editor.ps1` — named `local-preview-export`, bounded ignored
   inventory, candidate smoke/restore/revalidation и atomic current promotion;
3. `scripts/serve-local-preview.py` — stdlib foreground loopback GET/HEAD
   server, canonical receipt/index и per-request size/SHA validation.

Product runtime, models, migrations, dependencies, management endpoints,
persistent DB/importer, DEV-26/Nginx, daemon/watchdog, Playwright, VPS/live не
изменялись.

## Выполнение

После возобновления D-1143 первый fresh named run подтвердил реальный reserve
contract и остановился на ошибочном plan oracle: expected115, actual139. Cleanup
оставил runs0/staging0/container0/current0. Source formula исправлена на
exact139=`114 DB routes + 1 page1 redirect + 17 album query + 7 page2-album
query`.

Следующий fresh named run прошёл Django tests2/2, но host smoke запросил
неутверждённый `/contacts/` вместо exact `/contacts`; candidate снова был
удалён, current отсутствовал. Literal target исправлен без renderer/product
изменений.

Финальный fresh run foundation
`51e6db6e-c4ae-4647-a507-3014e9205ca8`:

- только `scripts/test-editor.ps1 -Suite local-preview-export`;
- tests2/2 PASS за80.320s;
- responses139:200×138, redirect302×1;
- resources248, total files387, bytes48,759,881;
- fixture before0/after0, request rows0, external delivery0;
- wrapper HTTP smoke PASS: GET/HEAD, exact path+query, redirect, resources,
  headers, unknown/private/manage/POST/traversal/range negatives;
- controlled post-bind tamper вернул503, original bytes восстановлены, full
  revalidation PASS до promotion;
- staging removed, test container removed, foundation stopped/private volumes
  retained.

## Текущий export

- runId `69d039b7-a08b-43ae-bae2-88881ced28b9`;
- ignored path
  `work/local-preview/runs/69d039b7-a08b-43ae-bae2-88881ced28b9`;
- receipt SHA-256
  `3b90579f7d9b3e2b850a6deb452e674e99227f7f9cea1e4f916cdd5cc09bef5c`;
- index SHA-256
  `cfdab3accee69617d2713fffbf9442fd24ebfa23c37668634beb4023526b7d91`;
- `work/local-preview/current.json` matches both hashes;
- post-run `serve-local-preview.py --check` PASS;
- `git diff --check` PASS, only expected CRLF warnings.

## Remediation финального ревью

Первое final review вернуло P1/P2/P3=0/4/0. Исправлены только четыре найденные
границы: cleanup staging до promotion и exact own-temp cleanup; lexical
reparse/UUID root gate и canonical reserve manifest→index reconciliation;
body SHA/length/full headers для страниц и CSS/JS/image плюс query-order
negative; pre-create reservation256MiB и whole-candidate/global768MiB measure.

Первый exact wrapper run после remediation прошёл Django2/2, но на последнем
шаге впервые встретил существующий `current.json`: .NET отклонил null backup у
`File.Replace`. Старый current остался неизменным, candidate/temp/staging и
container удалены. Atomic same-directory overwrite исправлен на
`File.Move(..., overwrite=true)`. Единственный допустимый repeat прошёл2/2 за
79.304с и опубликовал указанный выше run; runs2, temps0, staging0, test
container0. Foundation остановлен.

Это локальный визуальный snapshot, не persistent import, acceptance или release.
Repeat review D-1148: `APPROVED`, P1/P2/P3=0/0/0. Foreground server можно
запустить на `127.0.0.1:8768` для просмотра владельцем; он не регистрируется как
служба и не требует работающего foundation. Product/persistent/live границы
закрыты.

## Visual gate D-1149

Через CUA browser без Playwright при доступном viewport643×834 визуально
проверены главная, каталог услуг, контакты, галерея, типовая страница услуги и
раскрытое мобильное меню. Clipping, overlap и broken media не обнаружены;
contacts body показывает утверждённые телефон, адрес и email. Synthetic shared
Header/Footer — данные изолированного TEST-08 fixture, не release evidence.
Мобильное меню функционально, но длинное из-за полного дерева D-023/D-032;
новый accordion/JS не добавлен по no-bloat. Foreground preview оставлен на
`127.0.0.1:8768` для владельца.
