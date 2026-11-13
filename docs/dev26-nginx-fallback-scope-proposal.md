# DEV-26/27: bounded scope простого Nginx fallback

Статус: **repeat scope review APPROVED, P1/P2/P3=0; njs feasibility затем отклонён**. Дата: 2026-11-12. Основание: D-592, D-895, `NEXT-Q001=1`, REF-AC-020 и завершённый DEV-25. R26-S001–008 закрыты документально; product code/config/image не менялись. Read-only результат следующего gate — `docs/dev26-nginx-fallback-feasibility.md`.

## 1. Цель и граница результата

DEV-26 должен выдать последний валидный `current` HTML-набор DEV-25 только когда обычный upstream недоступен либо вернул `502`, `503` или `504`. DEV-27 не создаёт отдельную подсистему: следующий нормальный ответ Django автоматически снова имеет приоритет.

Это локальный foundation-инкремент этапа 8. Он не включает production/VPS/TLS, deployment, persistent apply, scheduler, Telegram, внешний мониторинг, TRUST/head, отдельную БД, service/daemon, state machine, автоматическую сборку HTML или восстановление данных.

## 2. Уже утверждённые обязательные правила

- fallback разрешён только для публичных `GET` и `HEAD`;
- `POST`, `/manage/`, `/request/submit/`, private/service paths и другие методы никогда не подменяются резервом;
- обычный upstream `404`, `301/302`, `200` и любой ответ кроме `502/503/504` возвращается без подмены;
- при transport failure Nginx получает обычный upstream error и может использовать fallback;
- после восстановления upstream следующий запрос сразу обслуживает Django, без команды возврата и сохранённого режима;
- fallback не обращается к PostgreSQL/Django, не пишет policy/readiness state и не принимает формы;
- форма заявки в уже собранном DEV-25 HTML отключена и не показывает ложный успех;
- HTML-набор не является backup/restore источником;
- при unreadable/tampered/missing current, manifest, response или resource выдаётся короткий `503` с `no-store`, а `previous` самовольно не выбирается;
- exact target включает согласованный query. Неизвестный query не открывает другой файл;
- status, exact nullable `Location`, robots/cache/security policy берутся только из validated manifest и fixed versioned policy mapping, а не из Host или пользовательского redirect-параметра.

## 3. Фактическая граница текущего репозитория

DEV-25 хранит:

- `active.json` с UUID `current/previous` и SHA-256 manifest;
- immutable `generations/<uuid>/manifest.json`;
- response-файлы под SHA-256 exact target;
- resource-файлы под SHA-256 canonical resource URL;
- status/Location/policy metadata только в manifest.

Текущий foundation ingress видит только `local-nginx.conf`, работает read-only от UID 101 и не имеет reserve mount. App пишет приватный reserve root от UID 10001 с mode `0700`. Текущий минимальный Nginx image 1.30.6 намеренно удаляет dynamic modules, включая `nginx-module-njs`.

Vanilla static Nginx не может без reload прочитать JSON pointer/manifest, сопоставить произвольный exact target с хеш-файлом и вернуть manifest-defined redirect Location. Поэтому нельзя честно закрыть REF-AC-020 одним `try_files` или `error_page`.

## 4. Кандидат минимального runtime и обязательный feasibility gate

Кандидат после отдельного согласования инструмента — оставить в закреплённом Nginx image официальный `nginx-module-njs` той же проверенной base-image линии и загрузить один малый read-only handler. Это **ещё не выбранный runtime**: до `DEV26-Q001` обязателен read-only feasibility report по точной pinned package/module version, dependencies/SBOM/advisories и фактическим API.

Handler вызывается только внутренним `error_page` публичной location после `502/503/504`:

1. Отклоняет всё кроме `GET/HEAD` и exact public interception matrix ниже.
2. Формирует exact request target из Nginx-owned normalized URI и exact raw query без Host-derived authority.
3. Одним request-local безопасным примитивом открывает exact regular `active.json` без symlink follow, ограниченно читает и canonical-проверяет его, требует UUID current и manifest SHA.
4. Тем же доказанным open/fstat/read protocol открывает current manifest, проверяет schema, UUID, digest, duplicate-key/canonical JSON, caps, exact response/resource row и fixed policy identifiers.
5. Exact response/resource file открывается без symlink follow, после open проверяется regular type/size, ограниченно читается в request-owned immutable bytes, сверяется с manifest `byte_size` и SHA-256 и удерживается до завершения ответа. User input никогда не становится path component.
6. Для `200`/resource handler отвечает только уже прочитанными и проверенными bytes. Отдельный static internal redirect или повторное открытие файла запрещены: они создают TOCTOU и cleanup race.
7. Для manifest redirect возвращается только разрешённый `301/302` и exact internal `Location` после existing target validation; body также берётся из уже проверенных bytes.
8. Для missing/tampered/unknown/unsupported состояния возвращается fixed contact `503`, `Cache-Control: no-store`, без exception/path/UUID. `previous` не выбирается.
9. `HEAD` проходит тот же open/read/hash/header protocol, получает тот же status/headers и заявленный `Content-Length`, но body клиенту не отправляется.

Nginx не кэширует pointer между запросами как authority: атомарная замена DEV-25 видна следующему запросу. Если после чтения bytes поколение удалено безопасной ротацией, request-owned bytes остаются целыми; если удаление произошло до open, запрос закрывается 503. Никакой `confirmedMode`, streak, switch command или return command не появляется.

Feasibility report должен доказать по первичным package/module docs и pinned artifacts: module load path; exact `lstat/open(O_NOFOLLOW)/fstat/read/close` либо эквивалент без check-then-open TOCTOU; binary Buffer response; SHA-256; duplicate-key rejection и canonical JSON; hard max reads до allocation; exception→fixed response; arbitrary nonroot UID; peak memory/CPU при `MAX_FILE_BYTES=8 MiB`, manifest2MiB, generation256MiB и ingress8 connections. Если njs не предоставляет такой request-local primitive, njs-кандидат отклоняется до owner gate и scope возвращается к архитектурному выбору. Если capability нельзя доказать read-only анализом, executable spike требует отдельного разрешения; image build/install сейчас запрещены.

### Exact interception matrix

- Текущий closed non-public inventory берётся из exact `app/estakada/urls.py` и ingress: `/manage` плюс `/manage/` subtree и exact `/request/submit/`. Отдельного HTTP readiness URL сейчас нет. Все existing specialized manage regex/prefix locations и общий `/manage/` fallback proxy имеют `proxy_intercept_errors off` и вообще не вызывают handler. Любой будущий private/service endpoint обязан до выпуска явно добавиться в этот inventory и negative oracles; слова «future private» без записи не дают допуска.
- Public resource locations ограничены exact `/static/public.css`, `/static/public-gallery.js`, `/static/public-home.js`, validated `/static/shared/<sha>/<allowlisted-name>` и validated `/public-media/<canonical-uuid>/` с exact allowed query.
- Public document candidate — только оставшийся normalized content namespace после более приоритетных private/service locations; окончательный допуск всё равно требует exact target row current manifest.
- Candidate standard-Nginx pre-proxy method split в оставшейся public `location /`: server default остаётся `proxy_intercept_errors off`; fixed internal code и только safe rewrite-module `return` отправляют `GET/HEAD` до proxying в named location:

  ```nginx
  error_page 418 = @public_read_proxy;
  if ($request_method = GET)  { return 418; }
  if ($request_method = HEAD) { return 418; }
  proxy_intercept_errors off;
  proxy_pass http://app:8000;
  ```

  В `@public_read_proxy` включаются `proxy_intercept_errors on`, `error_page 502 503 504 = @html_reserve` и тот же upstream. Все остальные методы proxy напрямую из исходной location с interception off, поэтому их upstream status/body/headers можно сохранить byte-identical. `418` зарезервирован только как internal dispatch и не является клиентским fallback status. Это кандидат, не принятая конфигурация.
- Routing feasibility до owner gate обязана по official Nginx docs, `nginx -t`/config-only smoke (только после отдельного разрешения executable spike, если read-only анализа недостаточно) доказать: fixed internal code не достижим как upstream response; GET/HEAD method+exact URI+raw query сохраняются при internal redirect; request body не проксируется дважды; non-eligible methods обходят named handler; existing body limits/rate limits/location precedence не меняются. Если этот split нельзя доказать стандартными уже доступными directives без unsafe rewrite side effects, runtime candidate возвращается на architecture review.
- Encoded/decoded slash, dot-segment, double slash, control/non-UTF-8 и normalization ambiguity закрываются до manifest lookup. Exact `/manage` и normalized `/manage/` subtree остаются private. Near-prefix `/manageX` или `/request/submitX` не объявляется private сам по сходству: это public candidate только если exact current manifest row существует, иначе fixed 503.
- Test-only routing/handler/file-read trace доказывает ноль обращений к reserve для private/service/non-eligible-method/normal-status cases и byte/status/header-identical upstream error для этих cases; runtime state/counter в продукт не добавляется.

### Доступ к файлам

Foundation получает новый dedicated named volume `html-reserve`, не существующий общий `state`: app монтирует только этот volume RW в exact `HTML_RESERVE_ROOT`, ingress — тот же volume RO. Volume precreation/init создаёт только reserve root mode `0700`, owner UID10001; app source, DB secrets, общий state, media-exchange и request ledger в ingress не монтируются. Inventory ingress-mount обязан содержать только разрешённые DEV-25 root entries `build.lock`, `active.json`, `staging`, `generations`.

Минимальный UID-кандидат — запуск ingress под тем же непривилегированным UID10001, что и builder, только для чтения dedicated mount. Это не даёт доступ к остальному app state, потому что отдельный volume не содержит его. Сохраняются read-only rootfs, `cap_drop: ALL`, `no-new-privileges`, internal web network и loopback port. Feasibility gate проверяет arbitrary UID, module/config readability и корректный tmpfs owner.

Изменять DEV-25 root с `0700`, делать world/group-readable public tree, передавать Docker socket, общий PID namespace или право app сигналить Nginx запрещено.

## 5. Почему альтернативы не входят

- **Generated Nginx include + reload:** требует нового безопасного control/reload пути после каждого owner build; web app не получает Docker socket, signal/PID namespace или shell.
- **Helper/sidecar static server:** добавляет отдельный runtime service, health/restart/network boundary и возвращает сложность, удалённую D-592/REF-7.
- **Symlink/current directory без manifest interpreter:** не выдаёт exact dynamic redirects/query metadata и конфликтует с closed DEV-25 root inventory.
- **Всегда HTML 200/meta refresh:** нарушает exact status/Location, cache и SEO contract.
- **Fallback на `previous` при повреждённом current:** скрывает corruption и может вернуть устаревший/отозванный набор; должен быть fail-closed 503.

## 6. Предлагаемые изменения только после будущего code gate

- до owner gate подготовить read-only feasibility report по точной njs package/module version, dependencies/SBOM/advisories и capability matrix; при недоказанном no-TOCTOU primitive njs отклонить;
- только после plan+code gate сохранить проверенную module version в Nginx image lock/SBOM/receipt;
- добавить один versioned njs handler и закрытую Nginx-конфигурацию;
- добавить отдельный `html-reserve` volume: app RW, ingress RO, и проверенный nonroot UID/tmpfs профиль только в local foundation;
- добавить отдельный named wrapper suite `dev26`, без wildcard и Playwright;
- не менять DEV-25 schema без отдельного finding plan review; handler потребляет существующие canonical pointer/manifest;
- не менять production config, compose/deployment или VPS в этом инкременте.

## 7. Приёмочные сценарии до кода

- `DEV26-AT-001`: upstream public GET `200/301/302/404` проходит byte/status/header-identical; test trace доказывает handler/file reads0.
- `DEV26-AT-002`: public GET при transport failure и каждом `502/503/504` получает exact current body/status/security/cache metadata из request-owned verified bytes.
- `DEV26-AT-003`: HEAD при тех же отказах совпадает status/headers с GET и имеет пустое тело.
- `DEV26-AT-004`: POST/unsupported methods на public URI, exact/encoded/normalized `/manage`/`/manage/` subtree и exact `/request/submit/` при upstream error сохраняют byte/status/header-identical upstream response; trace доказывает routing в non-intercept proxy и handler/file reads0. Near-prefix public candidate fallback возможен только при exact manifest row.
- `DEV26-AT-005`: exact query targets gallery/page/modal выбирают только свои manifest rows; unknown/duplicate/noncanonical query закрывается fixed 503, не другим response.
- `DEV26-AT-006`: manifest redirects возвращают exact allowed status и internal Location; Host/userinfo/external/malformed Location не отражается и закрывается 503.
- `DEV26-AT-007`: HTML local static/shared/media resources выдаются только по exact manifest URL и digest из request-owned verified bytes; unknown/tampered/missing resource закрывается 503/no-store.
- `DEV26-AT-008`: missing/malformed/oversize/duplicate-key pointer/manifest, wrong digest/schema/UUID/policy/file bytes, short read, non-regular entry и symlink дают 503 без path/UUID/exception; `previous` не используется. Race between validation/open/read не может выдать unverified bytes.
- `DEV26-AT-009`: атомарная ротация и cleanup current во время параллельных запросов даёт каждому запросу один целый old/new verified body либо fixed 503, без mixed files/headers/use-after-delete.
- `DEV26-AT-010`: после восстановления upstream следующий GET/HEAD сразу возвращает live Django canary; reserve не остаётся sticky.
- `DEV26-AT-011`: reserve HTML не содержит working form/admin/history/preview/PII/token/cookie, не ставит cookies и не обращается к DB/app.
- `DEV26-AT-012`: pinned module/package/advisory/capability report, Nginx config, dedicated-volume mount/inventory, UID preflight, bounded peak memory/CPU/file reads и full existing ingress/request-guard regression проходят; foundation после проверки остановлен.
- `DEV26-AT-013`: один combined e2e fixture обязательно выполняет реальный owner POST `/manage/html-reserve/` с CSRF, настоящими owner gate/session/audit и **непатченым** `build_run`; `HTML_RESERVE_ROOT` указывает в dedicated volume. Затем ingress читает тот же volume RO без seed/copy/rewrite JSON/files, и REF-AC-017–021 проходят на этом поколении. Прямой production `html_reserve.build/storage` API разрешён только низкоуровневым fault/tamper fixtures и не считается evidence owner HTTP wiring/REF-AC-017/020.
- `DEV26-AT-014`: hostile intercepted upstream headers (`Set-Cookie`, `Vary`, `Location`, auth/cache/CSP/robots/content headers) полностью удаляются. Closed fallback policy: HTML/redirect `Content-Type: text/html; charset=utf-8`, `Cache-Control: no-cache`, digest-derived quoted ETag, fixed `PUBLIC_CSP`, `nosniff`, exact nullable manifest robots; redirect дополнительно exact `Location`; resource — exact manifest content type, quoted digest ETag, fixed `public, max-age=31536000, immutable` для digest-addressed shared resources и fixed `no-cache` для non-immutable public/media URLs, `nosniff`; contact/error503 — `text/plain; charset=utf-8`, `no-store`, fixed CSP/nosniff, no ETag/Location/robots. HEAD совпадает с GET headers/Content-Length и не имеет тела; cookies/Vary/private headers запрещены во всех fallback classes.

REF-AC-020 закрывается DEV26-AT-001–010/012–014. REF-AC-021 остаётся совместным evidence DEV-25 + DEV26-AT-011/013. Hand-seeded files не считаются e2e evidence. Старые TRUST/state-machine `FALLBACK-*` assertions не возрождаются и не выдаются за актуальный driver.

До согласования CONTACT-01 fixed contact503 содержит только нейтральное «Страница временно недоступна. Повторите позже.» и не обещает телефон/канал/срок. Это не заменяет уже отключённую форму внутри валидного reserve HTML; безопасный альтернативный контакт в ней берётся только из проверенного DEV-25 content.

## 8. Fault/security matrix

| Граница | Ожидаемый результат |
|---|---|
| Upstream connect/timeout/502/503/504 | Только public GET/HEAD направляется во внутренний handler |
| Upstream normal 404/200/redirect | Ответ upstream, reserve не читается |
| Pointer меняется во время чтения | Request-owned fully verified bytes одного generation либо 503; mixed generation запрещён |
| Manifest/file меняется, удаляется или повреждён | Safe open/fstat/read + digest/schema/size mismatch → fixed 503/no-store; internal reopen отсутствует |
| Unknown target/resource/query | Fixed 503/no-store; traversal/nearest-match отсутствуют |
| Hostile upstream error headers | Полностью удалены до closed fallback headers; cookie/Location/Vary/cache не наследуются |
| Nginx/njs exception | Fixed 503 без exception/path/UUID; worker не раскрывает детали клиенту |
| App восстановился | Следующий запрос идёт в Django автоматически |
| Reserve mount отсутствует/permission denied | Nginx остаётся работоспособным и даёт fixed 503 на fallback, normal upstream не затронут |

## 9. Ворота

1. Repeat independent scope review после R26-S001–006.
2. Read-only njs feasibility/package/capability report. Если нужен executable spike — отдельное owner permission до image build/install.
3. Явный ответ владельца `DEV26-Q001` только на доказанный runtime candidate, dedicated volume и границы DEV26-AT-001–014.
4. Minimal implementation plan, independent plan review и отдельный owner code gate.
5. Только затем tests-first изменения foundation image/config/harness.

До прохождения всех ворот njs не сохраняется в image, reserve не монтируется в ingress, Nginx/config/compose/product code не меняются.
