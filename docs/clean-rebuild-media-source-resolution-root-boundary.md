# REBUILD-1 source-resolution media-root boundary

Дата: 2026-11-17. Evidence ID: `RB1-MEDIA-SOURCE-ROOT-BOUNDARY-001`.

Статус: **ПРИОСТАНОВЛЕНО ВЛАДЕЛЬЦУ; implementation candidate не создан**.

## Статическое доказательство

Без Docker/runtime/DB/media read установлено:

- `app/estakada/settings/base.py`: `MEDIA_ROOT=/var/lib/estakada/media`;
- `environment/foundation/compose.yaml`: app service монтирует named volume `state` в `/var/lib/estakada`;
- volume имеет имя `nestakada-foundation-dev-state`;
- host manifest не содержит host bind path для media root;
- Windows host `File.OpenHandle` не может открыть путь внутри Docker named volume.

Следовательно, D-1354 trusted-host `File.OpenHandle` implementation была бы ложной и не создаётся. DB/Docker/media read и code edits0.

## Лёгкие варианты

1. **Рекомендуемый:** один owner-gated ephemeral container на уже существующем pinned app image, `network=none`, root/read-only, named state volume mounted read-only, inline bounded Python из stdin. Exact key передаётся только stdin; component walk использует Linux dir-relative `os.open` с `O_NOFOLLOW`, size/SHA одного fd; output только aggregate envelope. Новый image/service/script/file/dependency0, container удаляется и volume не меняется.
2. Отложить source resolution до migration freeze. Это не добавляет механизм сейчас, но оставляет REBUILD-1 media baseline незавершённым.

Compose/app service не изменяются. Existing long-running app не запускается. Любой container-based вариант требует отдельного amendment, independent review и fresh runtime gate.
