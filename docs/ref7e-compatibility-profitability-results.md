# REF-07E: проверка рентабельности оставшейся shared-совместимости

Дата: 2026-11-09
Основание: D-690 и поручение владельца продолжать без нерентабельного раздувания.

## Граница проверки

Read-only проверить только два оставшихся кандидата после REF-07D:

- прекращение новых `SharedIdentityReservation`;
- удаление file-backed fallback Header/Footer.

Критерий перехода к коду: изменение должно сокращать runtime и сопровождение без новой state machine, нового ledger, ослабления provenance/collision/security и без обязательной миграции резервных копий ради неиспользуемой функции.

## Факты

- Простые apply/draft/restore создают inline PostgreSQL rows и не используют file writer, journal, quota book или operation receipts.
- Новая revision получает `SharedIdentityReservation`; composite PostgreSQL FK использует identity для provenance `source_revision_id` при последующем direct restore.
- Identity также разделяет пространство UUID с page identities и media consumers. Простое удаление записи либо ломает FK восстановления, либо требует нового lazy-reservation/collision механизма.
- В актуальной БД file-backed revisions/drafts нет. Шесть legacy blobs физически сохранены, но текущей историей не читаются.
- Удаление file fallback затрагивает поля/constraints/migrations, content reader, storage/lifecycle/quota/cleanup compatibility, тесты и правила восстановления старых копий. Пользовательской функции или ускорения запуска это сейчас не добавляет.

## Решение по рентабельности

Ни один кандидат не допускается к реализации сейчас:

- identities оставить как узкую совместимость и provenance guard;
- file fallback и шесть blobs оставить до отдельного post-launch/schema-cleanup этапа;
- не строить lazy identity, новый collision ledger или конвертер старых backup ради удаления небольшого неактивного слоя.

Это не отказ от завершения проекта: прекращается дальнейшее углубление REF-7, а работа возвращается к блокирующим запуск пользовательским задачам. Ближайший фактический блокер кода — незавершённый `UX-07`; после согласования публичных экранов открывается `DEV-08` (общие публичные шаблоны и навигация).

## Безопасность

Код, schema, данные, blobs, backup, production/VPS и старый сайт не изменялись. SQL binding, CSRF, роли, sessions, current CAS, normalizer, media binding и provenance/collision guards сохранены.
