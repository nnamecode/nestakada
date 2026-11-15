# TEST-08 — план общего e2e базового MVP

Дата: 2026-11-15. Статус: **APPROVED**, independent review P1/P2/P3=`0/0/0`; fixture, bindings и execution не начаты. Review: `docs/test08-base-mvp-plan-review.md`.

## Принятое admission

Владелец командой «Продолжай» после D-1088 выбрал рекомендованный вариант 1. TEST-08 проверяет только текущий базовый MVP-профиль:

- реальные заявки/ПД, SMTP/Telegram delivery, analytics и внешние widgets выключены;
- DEV-26/27 остаются отложены;
- внешние backup/monitoring, production restore, target VPS и launch smoke остаются TEST-09/launch gates;
- реальные браузеры/устройства остаются TEST-10 и не подменяются локальным прогоном.

Это уточняет старый admission TEST-08 и не переводит deferred/external AC в PASS.

## Почему существующую acceptance-оснастку нельзя просто запустить

Текущий `acceptance-automation-status.csv`: 17 `text_only`, 20 `partial_http`, 103 `assertions_waiting_driver`. `acceptance/run-container.ps1` и Playwright specs содержат много проверок контрактов/harness, но общий `local-bindings.json` и собранный fixture приложения отсутствуют; фиксированные реальные bindings есть только у отдельных исторических срезов. Зелёный harness не является e2e сайта.

По прямому правилу владельца регрессию запускают только через `scripts/test-editor.ps1`, без Playwright. Stage9 уже выполнил эту регрессию и не повторяется. Для TEST-08 также не создаётся новый Playwright suite или универсальный driver: локальный e2e выполняется точными HTTP/ручными группами после отдельного fixture gate.

## Предусловие: один изолированный собранный fixture

До любого e2e нужен отдельный reviewed fixture plan, который переиспользует test foundation и существующие default-off writers/packages:

1. только environment `test`, отдельная UNIT/test DB и существующие private volumes;
2. синтетические owner/employee identities, без реальных ПД и сетевых уведомлений;
3. существующие canonical content/gallery/home/SEO packages применяются только в test DB; никаких production imports;
4. request intake, analytics, external embeds, SMTP/Telegram и DEV-26/27 выключены;
5. exact before/after manifest, bounded cleanup и доказательство отсутствия изменений main/live/VPS;
6. fixture не добавляет production endpoint, model, migration, dependency, generic runner или новый content format.

Fixture implementation/run требует отдельного плана, независимого ревью и явного разрешения. Этот документ его не создаёт и не разрешает.

## Десять групп TEST-08

После готовности fixture выполнить ровно следующие группы; точные сценарии и evidence IDs фиксируются в будущем execution plan до запуска:

1. **Public URL/content:** все 114 сохранённых path+query без замены редиректом; единственный approved extra wash route отдельно; статус, canonical и основной content projection.
2. **Public composition/navigation:** Header/Footer, hidden/public tree, breadcrumbs, service catalogs/details, responsive markup без оценки реальных устройств.
3. **Owner authentication/admin:** login/logout/session/private cache, dashboard и owner-only actions.
4. **Employee permissions/editor:** назначенная страница, разрешённые поля, protected fields, stale/revoked rights, explicit save/conflict.
5. **Versions/restore:** ordinary/manual/Stable history, compare, role-limited direct restore, limits and protected fields.
6. **Media:** synthetic upload/validation/picker/replace/cleanup guards; gallery originals только read/hash, без перекодирования.
7. **Gallery/home/SEO:** exact17 albums/214 originals, page2/modal links, home composition, metadata/canonical/sitemap/robots.
8. **Requests default-off:** публичная форма/intent отсутствуют, real PII/network delivery0; owner email setting остаётся private.
9. **Logs/readiness/local operations:** owner audit read, bounded local rotation/retention and closed readiness без внешнего monitor.
10. **Manual HTML reserve:** owner build/status/current/previous and retained bytes; Nginx delivery/fallback не проверяются.

## Инструменты и доказательства

- stage9 regression evidence переиспользуется и не пересчитывается;
- TEST-08 execution не использует wildcard, прямой широкий `manage.py test` или Playwright;
- HTTP выполняется через Django server-level Client с fixed test host/origin внутри того же named test process, который собрал fixture; отдельный app над unit DB и ручные браузерные действия не создаются и не считаются TEST-10;
- для каждой группы сохраняются exact fixture/run ID, paths, actor, expected/actual, before/after counts/hashes и честный `PASS/PARTIAL/BLOCKED`;
- отсутствие external/physical/real-device evidence явно остаётся за TEST-09/10/launch.

## Правила остановки и результат

Первая ошибка сохраняется с причиной и изменившимся условием для возможного повтора. Вторая эквивалентная ошибка останавливает работу; третьей попытки нет. Ошибка host/Docker не считается ошибкой продукта.

TEST-08 получает общий PASS только если все десять групп имеют PASS в утверждённом base-MVP scope. PARTIAL/BLOCKED не превращаются в PASS агрегированием. Успех TEST-08 не разрешает production, TEST-09/10 или сбор ПД.

Следующий gate — независимое read-only ревью этого плана. До `APPROVED` fixture/code/config/test execution запрещены.
