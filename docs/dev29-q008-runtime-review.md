# Q008: code gates перед read-only Audit

2026-11-03, D-419. Scope: восстановление прежних temporary ресурсов и один Q007 Audit, без fixture writes/Run/init/migrate/API.

## Volume inspector

VOLUME-REVIEW-001: CHANGES REQUIRED; VOL-REV-001 (P1 exact volume identity), 002 (P2 NoCopy inspect), 003 (P2 receipt/source freshness) исправлены. **VOLUME-REVIEW-002 APPROVED** для bounded RO helper, VerifyStart и DB-only compose. Рецензент независимо подтвердил syntax/22 fake checks, runtime не вызывал.

Фактический инспектор PASS: existing owned local/dbdata volume, PG18 initialized/clean shut down, network none, root/volume read-only и NoCopy. Helper56b2306a… удалён finally. Receipt связывает inspector SHA4497f78f…, canonical initial plan7123610f…, image de3d5ee4…, identity hash8d4b67ca… и observedUtc. Непосредственные VerifyStart+fresh0containers/0networks PASS; неизменённый compose запустил только DB bfb589a914239dcd1aad4579b275d2923bf714fe9d75f985cf53571cece3aae9 и internal сетьc0e60eddc8959269afd48c774a1f5f5d370eb48485c53f0cee6ab0d9cb7295c7. PG isready accepting. SQL/Audit на этой точке ещё не выполнялись.

## Совместимость фактического Docker API

До Observe обнаружены представления CAP_CHOWN и /run/desktop/mnt/host/t/... вместо CHOWN и T:/... . Capabilities и фактические mounts правильные, конфигурация не менялась. **CAPS-REVIEW-001** и **BIND-REVIEW-001 APPROVED**: strip только ведущего CAP_ перед exact closed set; canonicalBind переводит только точный Desktop host-drive prefix и сохраняет прежние type/RW/count/destination/path predicates. Unknown/extra capabilities и другой диск/path по-прежнему закрыты. Selfcheck43/preflight22/authorizer21 PASS независимо подтверждены рецензентом; он Docker/SQL не запускал.

Старые prepared runs1b296fa0… и7855223e… сохранены без Observe/admission/attempt и не используются для допуска. Это версии подготовки до первого Audit, не повтор неуспешной операции.

## Последний exact snapshot

Run `50a66937-6be2-4d76-bf50-9849f3601986`, source31 прежний fingerprint1d25e6fc…; canonical plan SHA256 `708495a6a6dc06ff673dd2d597e06078e669670f42211c1cc348f5d0fd32dcad`, raw `afdf2f3e58fd14e98b7a3103cc68933b3607757c9231804e692aaf278d750088`.

Exact changed runtime code:

- controller.mjs `1d201ca08bd167ed6732e1db4af23c48eb01ad3df1b57bcae256c8f447ae4baa`;
- core.mjs `c003ccb0e3ee4c80561620c5cf0ae7529398980555590177208054746649e81d`;
- selfcheck.mjs `f57753132ae85e9e829ddee047c7667d804d8806d4ed69177c255569a4052cd9`;
- audit-authorize.mjs `6b3e990d9a771e58ffc902fc9875e2ef3097e715e7bd1020fa8af99984440f7f`;
- audit-preflight.mjs `90ef0e16839d5022a8b414fe06c36c9dbd13bc56f5e92dfda18ab422761cdd93`.

**SNAPSHOT-ADMISSION-REVIEW-001 APPROVED:** рецензент независимо подтвердил latest Verify, raw/canonical hashes, exact9 package SHA,31source и32protected файлов; только controller/core/selfcheck отличаются от initial. Все3 prepared run unconsumed. Текущие audit7 SHA также независимо сверены. Перед Observe новый run-scoped current-code binding сохраняет эти hashes и raw SHA актуальных review reports; old audit-prepared-source.json не переписывается и не используется как current.

Полные9 package SHA входят в новый plan, дополнительные helper hashes — ignored q008-runtime-code.json. До подписи — свежая signed observation/payload проверка и сохранение code-review SHA, затем один read-only Audit. Finally cleanup по полным own IDs и сохранность тома обязательны независимо от исхода. Этот документ не разрешает запись или общий P29-A completion.
