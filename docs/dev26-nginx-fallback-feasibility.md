# DEV-26: read-only feasibility Nginx/njs fallback

Статус: **njs-кандидат отклонён до owner gate**. Дата: 2026-11-12. Основание: D-592, D-895, D-898 и одобренный scope DEV-26/27. Product code, Nginx config, image, compose и containers не менялись.

## 1. Проверенная закреплённая основа

- Foundation использует Nginx `1.30.6` из base manifest `sha256:84ed8c0dd296c188bfc24ed506f46589e9285fb0b11cf3a04d91d524d3067e11`.
- `environment/foundation/Nginx.security.Dockerfile` и `nginx-build-inputs.lock.json` по D-314 явно удаляют `nginx-module-njs` вместе с другими неиспользуемыми dynamic modules.
- Ingress работает как UID/GID `101:101`, read-only rootfs, `cap_drop: ALL`, без reserve mount. App работает как `10001:10001`; общий state нельзя открывать ingress.
- Штатный `scripts/local-foundation.ps1 -Action Status` подтвердил `Environment=test`, `Active=False` и отсутствие контейнеров. Первый sandbox-вызов не имел доступа к Docker API; единственный повтор с изменённым условием read-only Docker access прошёл.

## 2. Capability matrix по первичной документации njs

| Требование scope | Результат | Evidence/вывод |
|---|---|---|
| Binary request-owned response | PASS по API | njs документирует `Buffer`, а request API допускает buffer body |
| SHA-256 | PASS по API | njs crypto документирует `createHash('sha256')` |
| Descriptor read | PASS по API | Документированы `openSync`, `fstatSync`, `readSync`, `closeSync` |
| Regular-file/type/size/inode checks | PASS по API | `fs.Stats` даёт `isFile`, `dev`, `ino`, `size` |
| Atomic no-symlink open | **FAIL / не доказано** | `openSync` документирует только строковые file flags; `O_NOFOLLOW`, numeric open flags и `openat`/dir-fd API не документированы |
| No check-then-open TOCTOU | **FAIL** | `lstatSync(path)` перед обычным `openSync(path, 'r')` не атомарен; inode comparison после open не предотвращает сам open через заменённую symlink/FIFO и возможную блокировку worker |
| Canonical/duplicate-key JSON | Требует собственного parser | Стандартный JSON parse сам по себе не доказывает duplicate-key rejection/canonical bytes; это не снимает основной blocker |
| Hard read caps | Возможны вручную | `fstat` + bounded allocation/read могут ограничить bytes, но только после безопасного open |
| Arbitrary UID/module load/SBOM/advisories | Не исследовалось исполнением | Не имеет смысла строить или устанавливать модуль после обязательного capability blocker; executable spike не запускался |

## 3. Routing feasibility

Официальная документация Nginx подтверждает, что rewrite `return` завершает обработку текущих rewrite directives, а `error_page ... = @named` может передать обработку в named location без изменения URI и method. Поэтому candidate method split не имеет выявленного read-only blocker. До implementation он всё равно потребовал бы `nginx -t` и config-only oracles точной precedence/interception matrix.

Routing feasibility не компенсирует file-open blocker: handler не допускается к owner gate, даже если dispatch реализуем.

## 4. Решение feasibility gate

Одобренный scope требует точный `lstat/open(O_NOFOLLOW)/fstat/read/close` или эквивалент **без** check-then-open TOCTOU. Доступный официальный njs API этого не доказывает. Ослаблять requirement до `lstat → open → fstat` нельзя: это повторно откроет закрытый review finding R26-S001 и позволит запросу открыть подменённый объект до проверки.

Поэтому:

1. `nginx-module-njs` не возвращается в image и не предлагается в `DEV26-Q001`.
2. Image build/install, executable spike и container mutation не выполняются.
3. DEV-26 возвращается к architecture review, сохраняя exact interception/header/e2e requirements DEV26-AT-001–014.

## 5. Bounded варианты следующего решения

### A. Generated Nginx projection + controlled reload

DEV-25 формирует отдельную проверяемую Nginx-safe projection/config; доверенный host-side operator валидирует её и делает controlled reload. Плюсы: runtime остаётся vanilla Nginx, нет JS file interpreter. Минусы: owner build сам по себе не активирует fallback, нужен новый operator/control protocol и точная atomic rollback/reload модель.

### B. Minimal stateless reserve helper

Отдельный read-only process открывает файлы системными безопасными flags, валидирует manifest/digest и отдаёт только reserve responses; Nginx проксирует к нему на fallback. Плюсы: требование safe-open выполнимо и тестируемо. Минусы: новый service/runtime/health/network boundary, то есть явное изменение упрощённой границы D-592.

### C. Пересмотреть delivery contract DEV-25

Добавить заранее материализованный immutable delivery package, который vanilla Nginx может выдавать без JSON interpreter. Плюсы: меньше runtime logic. Минусы: exact query/status/redirect/header mapping всё равно требует generated configuration/reload либо ограниченного contract change; затрагивает уже завершённый DEV-25 и требует отдельного scope review.

Рекомендация для следующего обсуждения: вариант A как наименьшее число новых runtime-компонентов, но только после отдельного owner architecture answer; он не считается утверждённым решением.

## 6. Gate

`DEV26-Q002` (ожидает владельца): выбрать направление A/B/C либо отложить DEV-26. После выбора — bounded scope update, independent review, minimal implementation plan/review и отдельное разрешение кода. До ответа DEV-26 product/config implementation не начинается.
