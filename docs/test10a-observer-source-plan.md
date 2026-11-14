# TEST-10A — minimal observer-source plan

Статус D-1076, 2026-11-15: independently `APPROVED`, P1/P2/P3=0/0/0. Основание: independently approved D-1075 exact40/7 source audit. Принято no-bloat решение `STOP/DEFER TEST-10 binding implementation`; это не остановка проекта. Product, fixture, registries, validator, evidence policy и runtime остаются без изменений.

## Решение по объёму

Сейчас не реализовывать частичный observer package. Два hard gaps не позволяют честно предложить Q003 даже при реализации остальных пяти observers:

1. `UI-118-EXPIRY` требует открыть editor в active session, затем состарить именно эту session и только после этого выполнить `EDITOR-CHECK`. Existing fixture/test support создаёт отдельные already-aged sessions, но не имеет closed callable для post-open aging.
2. `OBS-106-SERVER-EGRESS` требует полное фактическое наблюдение server-egress в exact интервале. Отсутствие fetch-кода и isolated-network policy сами по себе не доказывают отсутствие попытки; existing approved bounded observer не найден.

Новый generic runner, proxy, packet capture, egress service, clock subsystem, browser automation или восстановление retired writer/launcher ради этих gaps запрещены этим планом. Это существенно расширило бы проект ради одной ручной acceptance-ветви.

## Exact7 disposition

| Observer | Minimal future source | Что можно переиспользовать | Текущий gate |
|---|---|---|---|
| `OBS-014-SECRET-SINKS` | один bounded collector четырёх sinks, возвращающий только complete/hash/boolean map | `audit.models.AuditEvent`; transient response/browser inspection | application-log sink source отсутствует; не реализовывать частично |
| `OBS-021-CACHE` | transient response projector: status/class + parsed `private`/`no-store` booleans, raw headers/body discarded before evidence | protected history response; existing response-safety conventions | source contract можно спроектировать позже, но отдельно он Q003 не открывает |
| `OBS-022-PROTECTED-UNCHANGED` | transactionally consistent before/after snapshots projected only to approved boolean field maps | existing Page/Route/content/version/grant/shared/media models | feasible test-only projector, но не реализовывать до снятия hard gaps |
| `OBS-106-CLIENT-NETWORK` | manual current-Chrome bounded request summary for exact actor tab and interval | Chrome DevTools; approved output fields in registry | no Playwright adoption; safe canonical source/evidence handoff отсутствует |
| `OBS-106-SERVER-EGRESS` | independently bounded actual egress observation covering exact app interval and identity | existing isolation policy is only a prerequisite | hard gap; keep `BLOCKED/unbound` |
| `OBS-118-BROWSER-STORAGE` | manual current-Chrome boolean observation covering URL, localStorage, sessionStorage and the separately required IndexedDB/CacheStorage scope; the registry's current three-field output must not be misread as proof of the latter two | logic candidate `acceptance/browser-memory.js#inspectBrowserPersistence` covers only URL/localStorage/sessionStorage | candidate is Playwright-page coupled and incomplete; keep `BLOCKED` until one approved non-Playwright source covers all five sinks or the two extra sinks receive a separately approved closed observer contract |
| `OBS-REV-E1` | cursor-bounded PageGrant/UserProfile/AuditEvent before/after projection with drift/concurrency rejection | existing three Django models and exact event tuple | feasible test-only projector, но не реализовывать до снятия hard gaps |

## Stop/go rule

Current decision is **STOP/DEFER TEST-10 binding implementation**, not project stop:

- keep `registryReady=false`, bindings40/observers7 unbound;
- keep Q003, fixture Prepare, browser/direct HTTP and evidence writes closed;
- do not add source/projector code whose only result would remain unusable behind the two hard gaps;
- preserve D-1074 registries/validator and D-1075 source map as the future restart point;
- continue another already approved product task instead of expanding acceptance infrastructure.

Future TEST-10 restart requires a separate owner decision after one of these conditions changes:

1. an existing bounded post-open session-aging capability is identified and independently reviewed; and
2. an existing bounded server-egress observer is identified and independently reviewed.

If both become available, prepare a fresh exact implementation plan naming the smallest file set, focused tests and evidence projection. Regression, if any, remains restricted to named suites through `scripts/test-editor.ps1`, without wildcard or Playwright. TEST-10 execution still requires a separate later owner gate.

## Acceptance of this plan

The plan is accepted only if independent review confirms:

- all seven observer dispositions match D-1074/D-1075 contracts;
- the two hard gaps are real and not already solved by an existing approved source;
- deferral loses no approved product behavior and changes no status/PASS claim;
- no necessary small implementation is being incorrectly classified as infrastructure expansion.
