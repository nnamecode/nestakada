# TEST-08 — аудит готовности к общему e2e

Дата: 2026-11-15. Статус: **admission resolved by owner variant 1; execution not started**. План: `docs/test08-base-mvp-plan.md`.

## Что уже доказано

- локальная регрессия этапа 9 прошла: all900, dev13 42/42, dev25 73/73, check и migrations PASS;
- локальная часть этапа 10 принята независимым ревью P1/P2/P3=`0/0/0`;
- acceptance registries содержат exact140 AC без missing/extra;
- текущий этап 8: 21 из 27 активных областей готовы локально или функционально заменены, 3 частичны, 3 отложены/ожидают внешних ворот.

Эти доказательства не заменяют TEST-08 и не дают разрешения на его запуск.

## Почему admission закрыт

Строка TEST-08 в `docs/tasks.md` требует завершить все DEV-02–DEV-30 и MONITOR-01. Фактический утверждённый MVP сохраняет:

- partial DEV-18/22/23: эксплуатационная ротация, внешняя backup-копия и production restore ещё не готовы;
- deferred DEV-26/27 по D-923: Nginx HTML delivery/fallback не входят в текущую локальную сборку;
- pending DEV-30/MONITOR/LEGAL/external inputs: первый запуск default-off без intake, analytics и внешних виджетов; backup/monitoring/provider choices отложены владельцем до завершения проекта;
- persistent import/publication и production environment не выполнялись.

Сгруппированный остаток exact140 по D-1015: owner/defer21 + launch/external94 + TEST-09 physical7 + TEST-10 real-device18. Пять старых oracle conflicts уже решены no-bloat вариантом, но соответствующие AC не стали PASS автоматически.

Следовательно, текущий буквальный admission TEST-08 противоречит утверждённым defer/default-off решениям: выполнить «все DEV завершены» без возврата отложенного объёма невозможно.

## Варианты

### Вариант 1 — рекомендуется, без раздувания

Уточнить admission TEST-08 как общий e2e **текущего базового MVP-профиля**:

- intake/реальные ПД, SMTP/Telegram delivery, analytics и внешние widgets выключены;
- DEV-26/27 не входят в профиль до отдельного возобновления;
- внешние backup/monitoring, production restore, target VPS и launch smoke остаются TEST-09/launch gates;
- TEST-10 real-browser/device остаётся отдельным и не подменяется Django/Playwright;
- TEST-08 проверяет только уже реализованную локальную поверхность, точные URL/content projections, роли, версии, media, gallery, SEO, home, default-off request UI и manual HTML reserve.

После решения требуется отдельный минимальный TEST-08 plan с точными сценариями и runner boundary до запуска. Нельзя автоматически создавать новый framework, Playwright suite или возвращать deferred product code.

### Вариант 2 — не рекомендуется

Сначала возобновить и завершить DEV-26/27, external backup/monitoring, production restore, DEV-30/LEGAL и persistent publication, а затем запускать TEST-08 по старому буквальному admission. Это смешивает локальный e2e с TEST-09/launch и возвращает отложенные подсистемы.

## Итог аудита

TEST-08 не запускался; Docker, Foundation, Playwright, browser, network, VPS и live не затронуты. Владелец выбрал вариант 1 командой «Продолжай» после этого аудита. Следующий gate — независимое ревью `docs/test08-base-mvp-plan.md`; до `APPROVED` fixture, продукт и test execution не меняются.
