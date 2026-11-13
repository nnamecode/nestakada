# MAP-019 — минимальный план размещения инфографики после вводного текста

Статус D-974 (2026-11-13): final bounded code review завершён, open P1/P2/P3=0/0/0. Metadata reader strengthened to existing bounded `O_NOFOLLOW` descriptor pattern; physical-manifest race and missing-usage replay oracles added. Fresh `dev09-services`47/47, check0, migrations0; prior public9/21/7 remain PASS. Minimal local integration complete; persistent invocation/publication/live and remaining23 remain closed.

Статус D-973 (2026-11-13): локальная реализация и приёмочные проверки завершены. WebP1200×900/104682 bytes/SHA `c86b3d2912b72c4169193777a4df62f0b8ab075bddb9551a77da0027dc6417c5`; metadata package1453 bytes/SHA `fe083d206a72a3850bb30a554e57d375eba3338aacd87842c6c17f99a0f34954`; wrapper-only `dev09-services`45/45, `public-read`9/9, `public-http`21/21, `public-nav`7/7, check0, migrations0. Persistent invocation/publication/live и remaining23 не выполнялись. Следующий gate — final review ограниченного инкремента.

Статус: **owner resume `INFO-Q006=1`; exact converter literal добавлен, требуется fresh independent plan review до conversion/code**.

Дата: 2026-11-13. Основание: D-969 и прямой выбор владельца «поставь после вводного текста», записанный D-970 как `INFO-Q005=1`: разрешены production WebP1200×900/≤1000000 bytes, локальная конвертация и интеграция только MAP-019 по принятому плану. `INFO-Q002` не открыт; remaining23/persistent apply/publication/live закрыты.

## 1. Результат

В первоначальной hidden revision canonical страницы MAP-019 `/services/kuzovnoj-remont/remont-kuzova` после layout-узла `intro_text` находится один обычный image node, затем прежние `main_text` и `price`. Используются существующие `page-content-v1`, `embedded_images`, `Asset`/`AssetFile`/`AssetUsage`, public body renderer и contextual media URL.

Новые model/migration/schema/renderer branch/API/JS/editor widget/service/queue/dependency не создаются. Остальные 23 инфографики, публикация, navigation enablement, persistent apply и live/VPS не входят.

## 2. Зафиксированные идентичности

| Объект | Значение |
| --- | --- |
| MAP/Page | `MAP-019` / `080d64ee-4ce1-5399-b672-83dc22f9f8bf` |
| URL | `/services/kuzovnoj-remont/remont-kuzova` |
| image ID | `db49b593-85b1-5377-8873-a4013f762d5e` |
| Asset ID | `6fa5cdd8-dabd-52ab-b994-4e10ef2cb2c8` |
| MAIN AssetFile ID | `b7cd2e13-9427-57cc-b65e-28fdc5aaff71` |
| layout block ID | `98ad3c39-de8d-5894-9ce4-a073179ff23e` |
| MediaFolder ID/path | `b6fbe54a-6483-5459-a856-0c4d3c6f6afd` / `design/services/infographics` |
| storage key | `img/6fa5cdd8-dabd-52ab-b994-4e10ef2cb2c8/main.webp` |
| alt | `Три этапа ремонта кузова: оценка повреждений, восстановление деталей и проверка результата.` |
| alignment | `center` |

Точная UUIDv5 provenance:

- image: namespace MAP-019 Page UUID, name `infographic-image:MAP-019:v1`;
- Asset: namespace MAP-019 Page UUID, name `infographic-asset:MAP-019:v1`;
- layout block: namespace MAP-019 Page UUID, name `infographic-block:MAP-019:v1`;
- MediaFolder: namespace MAP-019 Page UUID, name `infographic-folder:services:v1` (page-scoped frozen literal первой очереди, не общее правило будущих папок);
- MAIN AssetFile: namespace exact Asset UUID, name `main-file:v1`.

## 3. Production media candidate

Authority preview: `media/design-concepts/infographics/map-019-body-repair-sample-v1.png`,1448×1086,2025618 bytes,SHA `01bfda46e7dba90adb38affd6fe615beba90f9e182a77073a5ec6e27fa5c5678`.

Один existing pinned local image `sha256:6105f968d577220973fb9ed8e0caf3ba48a3e028d23d4d324059b4b4b3739f9c` используется one-shot только как offline converter: Pillow13.0.0/libwebp1.6.0, entrypoint `python`, network none, read-only root, cap-drop ALL, no-new-privileges, memory128MiB/CPU0.5/PIDs32, exact source-file mount read-only и exact output directory writable. Никакой установки в Windows и нового image/dependency нет.

Exact converter program передаётся `python -c` как literal UTF-8 source и фиксируется в implementation evidence SHA-256. Он:

1. lstat/realpath проверяет `/input/source.png`: exact regular/no-symlink,1448×1086,2025618 bytes,SHA `01bfda46e7dba90adb38affd6fe615beba90f9e182a77073a5ec6e27fa5c5678`;
2. выполняет только `ImageOps.exif_transpose`, `convert('RGB')`, `resize((1200,900), Image.Resampling.LANCZOS)` и `save(BytesIO(), format='WEBP', quality=84, method=6, exif=b'', icc_profile=None)`;
3. проверяет декодированием полученных bytes exact WEBP/1200×900 и cap1..1000000;
4. для `/output/map-019-body-repair-v1.webp` проверяет parent realpath; если target отсутствует — создаёт exact file через `open(...,'xb')`, flush+fsync; если exact bytes уже существуют — replay writes0; regular-file mismatch/symlink/другой target даёт stop без overwrite;
5. печатает только JSON с source/output dimensions,bytes,SHA и `created|replayed`.

Source PNG не удаляется и не перезаписывается. После создания output actual bytes/SHA фиксируются в package/docs и визуально повторно проверяются четыре точных строки, композиция и отсутствие артефактов. Если image/program/version/source/output boundary не выполнен, остановка без package/code.

### Exact converter literal

Canonical program bytes: содержимое следующего code block, переводы строк перед hashing/runtime нормализуются `CRLF|CR → LF`, после последней строки сохраняется ровно один LF. Любое другое содержимое запрещено.

```python
import hashlib
import json
import os
import stat
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

SOURCE = Path('/input/source.png')
OUTPUT_DIR = Path('/output')
TARGET = OUTPUT_DIR / 'map-019-body-repair-v1.webp'
SOURCE_SHA256 = '01bfda46e7dba90adb38affd6fe615beba90f9e182a77073a5ec6e27fa5c5678'
SOURCE_BYTES = 2025618
SOURCE_SIZE = (1448, 1086)
OUTPUT_SIZE = (1200, 900)
OUTPUT_MAX_BYTES = 1000000


def sha256(data):
    return hashlib.sha256(data).hexdigest()


source_info = SOURCE.lstat()
if (not stat.S_ISREG(source_info.st_mode) or SOURCE.is_symlink()
        or SOURCE.resolve(strict=True) != SOURCE.absolute()
        or source_info.st_size != SOURCE_BYTES):
    raise SystemExit('MAP019_SOURCE_INVALID')
source_bytes = SOURCE.read_bytes()
if len(source_bytes) != SOURCE_BYTES or sha256(source_bytes) != SOURCE_SHA256:
    raise SystemExit('MAP019_SOURCE_INVALID')

with Image.open(BytesIO(source_bytes)) as source_image:
    if source_image.format != 'PNG' or source_image.size != SOURCE_SIZE:
        raise SystemExit('MAP019_SOURCE_INVALID')
    converted = ImageOps.exif_transpose(source_image).convert('RGB').resize(
        OUTPUT_SIZE, Image.Resampling.LANCZOS)
    output_buffer = BytesIO()
    converted.save(output_buffer, format='WEBP', quality=84, method=6,
                   exif=b'', icc_profile=None)
output_bytes = output_buffer.getvalue()
if not 0 < len(output_bytes) <= OUTPUT_MAX_BYTES:
    raise SystemExit('MAP019_OUTPUT_INVALID')
with Image.open(BytesIO(output_bytes)) as output_image:
    if output_image.format != 'WEBP' or output_image.size != OUTPUT_SIZE:
        raise SystemExit('MAP019_OUTPUT_INVALID')

output_dir_info = OUTPUT_DIR.lstat()
if (not stat.S_ISDIR(output_dir_info.st_mode) or OUTPUT_DIR.is_symlink()
        or OUTPUT_DIR.resolve(strict=True) != OUTPUT_DIR.absolute()):
    raise SystemExit('MAP019_OUTPUT_BOUNDARY_INVALID')

status = 'created'
created = False
try:
    with TARGET.open('xb') as target_file:
        created = True
        target_file.write(output_bytes)
        target_file.flush()
        os.fsync(target_file.fileno())
except FileExistsError:
    target_info = TARGET.lstat()
    if (not stat.S_ISREG(target_info.st_mode) or TARGET.is_symlink()
            or TARGET.resolve(strict=True) != TARGET.absolute()
            or TARGET.read_bytes() != output_bytes):
        raise SystemExit('MAP019_TARGET_CONFLICT')
    status = 'replayed'
except BaseException:
    if created:
        TARGET.unlink(missing_ok=True)
    raise

written = TARGET.read_bytes()
if written != output_bytes:
    raise SystemExit('MAP019_TARGET_CONFLICT')
print(json.dumps({
    'output_bytes': len(output_bytes),
    'output_height': OUTPUT_SIZE[1],
    'output_sha256': sha256(output_bytes),
    'output_width': OUTPUT_SIZE[0],
    'source_bytes': len(source_bytes),
    'source_height': SOURCE_SIZE[1],
    'source_sha256': sha256(source_bytes),
    'source_width': SOURCE_SIZE[0],
    'status': status,
}, ensure_ascii=True, separators=(',', ':'), sort_keys=True))
```

Canonical converter source: 3050 UTF-8 bytes, SHA-256 `e409499422bc9f9e1bf5faa798238438e265f846e10033fe0b2e3f18c4532ed7`.

Exact Docker argv после runtime extraction+LF normalization и проверки converter SHA:

```text
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --memory 128m --cpus 0.5 --pids-limit 32 --mount type=bind,src=<exact-preview-file>,dst=/input/source.png,readonly --mount type=bind,src=<exact-infographics-directory>,dst=/output --entrypoint python sha256:6105f968d577220973fb9ed8e0caf3ba48a3e028d23d4d324059b4b4b3739f9c -c <exact-canonical-program>
```

`<exact-preview-file>` и `<exact-infographics-directory>` перед dispatch разрешаются в уже проверенные absolute paths внутри workspace; shell string interpolation внутрь program запрещена. Coordinator до Docker вычисляет SHA canonical program и требует literal equality с указанным SHA; evidence повторяет SHA того же переданного argv element.

## 4. Canonical input и import

Добавить один bounded tracked metadata package `app/content/dev09m_infographic_map019.json` без бинарных данных. Exact keys: schema/policy/source/media/binding. Он фиксирует source preview SHA/dimensions, production local path/bytes/SHA/dimensions/MIME, IDs, folder/storage key, alt и точную позицию `after_intro_text`.

`dev09_migration_apply.py` получает:

1. closed reader/validator пакета с literal SHA constant, regular-file/no-symlink/realpath/byte cap и exact key/type/value checks;
2. отдельный default-off `import_combined_infographic_media(source_root, storage=None)`, повторяющий принятый DEV-12 pattern для одного exact MAIN WebP: create/recover/replay exact folder/Asset/AssetFile, physical manifest и `mark_ready`; чужой/existing drift fail closed;
3. `apply_combined_services()` выполняет two-phase evidence: вне DB transaction package-based physical manifest preflight exact storage key/SHA/bytes и frozen evidence digest; затем внутри existing transaction/order `lock_content → lock_auth`, сохраняя parent/page/route/sibling locks, блокирует exact MediaFolder/Asset/AssetFile rows, повторно захватывает READY descriptor+physical manifest и сравнивает evidence digest до `_create_aggregate`; storage writes в content apply запрещены. Descriptor/status/file race между preflight и locked recapture даёт полный rollback/no pages/usages;
4. после successful recapture writer строит MAP-019 payload с одним embedded image и layout order `intro_text → image → main_text → price`; остальные 23 payload byte-for-byte semantic-equivalent прежним;
5. `_create_aggregate` синхронизирует existing current/draft usages после создания state/draft; ordinary usage уже создаёт `engine.new_revision`;
6. `_exact_aggregate` ожидает для MAP-019 ровно три usages: ordinary_version/current_page/draft с одним exact `embedded:<image_id>` slot/Asset; для остальных23 usages0. Missing/extra/wrong usages fail replay.

Media import и content apply остаются разными явными командами. Content apply без exact READY file прекращается до page mutation. Persistent invocation не выполняется этой реализацией.

## 5. Приёмочные сценарии

| ID | Сценарий |
| --- | --- |
| INF19-AT-001 | Exact source preview → full-digest pinned Pillow13/libwebp1.6 literal-program conversion → WebP1200×900,≤1000000 bytes; source unchanged; create-new/exact replay/mismatch-no-overwrite; text/composition visual PASS. Wrong source SHA/dimension or codec failure gives no package/code continuation. |
| INF19-AT-002 | Metadata package принимает только exact one source/media/binding and frozen IDs/path/SHA/bytes/MIME/alt/position; unknown/missing/duplicate/cap+1/traversal/symlink/drift reject. |
| INF19-AT-003 | Media import default-off guard, exact create/recover/replay; wrong folder/Asset/file/key/hash/bytes/manifest/status/extras reject without content mutation. Content apply uses outside physical evidence then locked folder/Asset/file READY recapture; induced descriptor/status/file race gives full rollback/no pages/usages. |
| INF19-AT-004 | MAP-019 payload has exact one embedded image and `intro → image → main → price`; all other23 remain no embedded image and original layout. |
| INF19-AT-005 | All-absent writer creates existing exact24 Page/25 Route plus exact three MAP-019 usages; all-exact replay writes0; missing/extra/wrong usage, mixed state, collision, exception and concurrent contender rollback. |
| INF19-AT-006 | Pure/public fixture projects intro, one contextual image URL with exact alt, main and price in order; missing/corrupt media fails closed. Page remains hidden and published count0. |
| INF19-AT-007 | Named wrapper only: `dev09-services`, `public-read`, `public-http`, `public-nav`; Django check and no migrations. No wildcard/direct broad run/Playwright. |
| INF19-AT-008 | Foundation stopped/containers0 after checks; no persistent apply/publication/live; media binary remains outside Git. |

## 6. Exact implementation file set

- new ignored binary `media/design-concepts/infographics/map-019-body-repair-v1.webp`;
- new tracked `app/content/dev09m_infographic_map019.json`;
- modify `app/content/dev09_migration_apply.py`;
- modify `app/content/test_dev09m_combined_services.py`;
- modify `scripts/local-foundation.ps1` exact snapshot/package allowlists for the literal new JSON name;
- stage documentation only.

`scripts/test-editor.ps1` не меняется: existing named suites уже маршрутизируют нужные modules. Любой иной product file требует остановки и amendment review.
