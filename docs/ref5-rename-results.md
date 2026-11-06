# REF-5 — простое переименование страницы

Дата: 2026-11-05.
Решение: D-617.
Среда: локальный изолированный `foundation-test`; production, VPS и старый сайт не затрагивались.
Ревью: независимое code/test review — `APPROVED`.

## Результат

Owner rename переключён на одну простую PostgreSQL-транзакцию. Команда проверяет current generation/editor session, строгую signed форму и locked row-version `xmin`; затем меняет только `Page.name` и пишет bounded `TREE_RENAME` audit.

`xmin` меняется при любом UPDATE строки и поэтому закрывает stale form, ABA и конкурентный double-submit без отдельной generation-колонки, receipt или identity reservation. Повтор новой формы после success/потерянного ответа безопасно конфликтует без второй записи; актуальный GET показывает результат.

Не меняются URL и legacy routes, kind, parent, sibling order, publication, H1/SEO, revisions, Stable, drafts и media. Существующие `tree_rename` receipts продолжают replay старой командой; cross-action consumed UUID отклоняется. Move/reorder остаются на прежнем пути.

## Проверки

- исправленный authoritative owner-before-token сценарий: 1/1 PASS;
- simple rename + прежние tree commands: 32/32 PASS, 35.921 с;
- полный content: 87/87 PASS, 84.388 с;
- media_library + page_versions: 96/96 PASS, 136.853 с;
- real PostgreSQL ABA и concurrent double-submit;
- strict token/name/operation, anonymous/employee/CSRF/closed fields;
- lost response/repeat без второго audit или ledger;
- audit failure rollback;
- legacy exact replay и cross-action refusal;
- main test DB: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner-draft pins 1, receipts 396, identities 765, payload hashes valid;
- `/manage/login/`: HTTP 200;
- независимый review: `APPROVED`, открытых findings нет.

## Точка продолжения

Текущий общий этап — REF-05/REF-5. Следующий ограниченный инкремент REF-05I — сначала записать приёмочные сценарии простой reorder-команды: только siblings одного parent, атомарная нормализация позиций, stale/ABA/concurrency и rollback без новых receipts/identity. Move и удаления legacy-кода пока не менять; REF-Q004 закрыт.
