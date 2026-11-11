"""Closed DEV-10 gallery package and default-off atomic writer boundary."""
from html import escape
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
from uuid import UUID, uuid5

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Q

from accounts.models import PageGrant, UserProfile
from accounts.services import lock_auth
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from media_library.models import Asset, AssetFile, AssetUsage
from media_library.storage import MediaStorage
from page_editor.clean import restricted_clean
from page_versions import engine, schema
from page_versions.creation import initial_snapshot
from page_versions.models import (
    IdentityReservation, OperationReceipt, OwnerDraft, PageContentState,
    PageRevision, RestoreStage, RevisionMetadata, RevisionProtection,
    VersionBasePin,
)

from .dev09_migration_apply import (
    PARENT_DESCRIPTOR, _exact_aggregate as _exact_parent_aggregate,
    _parent_payload,
)
from .models import Page, Route, lock_content


PACKAGE_SHA256 = '9db5b026d6affa4668e2ca19268d8663355c1e22504f6aba6aa1676ed3d41b3b'
PACKAGE_MAX_BYTES = 512 * 1024
NAMESPACE = UUID('4db16416-1035-5b77-84cf-c0d4ea7e9154')
HOME_ID = 'e80c3de1-feea-4847-b550-325a825ffc0e'
ROOT_ID = str(uuid5(NAMESPACE, 'page:MAP-008'))
MAP_ORDER = (
    'MAP-114', 'MAP-113', 'MAP-112', 'MAP-111', 'MAP-109', 'MAP-106',
    'MAP-102', 'MAP-099', 'MAP-096', 'MAP-092', 'MAP-086', 'MAP-081',
    'MAP-076', 'MAP-070', 'MAP-061', 'MAP-056', 'MAP-036',
)
PAGE2_MAP_IDS = MAP_ORDER[10:]
PHOTO_COUNTS = {
    'MAP-036': 7, 'MAP-056': 12, 'MAP-061': 8, 'MAP-070': 10,
    'MAP-076': 8, 'MAP-081': 7, 'MAP-086': 25, 'MAP-092': 14,
    'MAP-096': 15, 'MAP-099': 11, 'MAP-102': 21, 'MAP-106': 9,
    'MAP-109': 13, 'MAP-111': 32, 'MAP-112': 9, 'MAP-113': 9,
    'MAP-114': 4,
}
INPUTS = {
    'map_sha256': 'c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8',
    'media_inventory_sha256': '2be3bf2b24ca589c9eaf88a040ee80ed098417667e5c04db89ca669332155ad0',
    'approved_gallery_sha256': '5e9e5bbbdfdcae7a85a2575be441f209a3d32fb91b65169f2202c4c055bebc3d',
    'legacy_root_sha256': '89dea67b4dc41ff1520a9db31d38ca8d11c12a39f9c2c7c942ef94c0ca8cc974',
    'legacy_page2_sha256': '6e4bd964bb6f769ecb23250a907ba56ef6b4fc1a9c44907e9d99f2e845535d46',
}


def _fault(code):
    raise ValidationError(code)


def _enabled():
    database = connection.settings_dict
    if (getattr(settings, 'ENVIRONMENT', None) != 'test'
            or getattr(settings, 'DEV10_GALLERY_APPLY_ENABLED', False) is not True
            or database.get('ENGINE') != 'django.db.backends.postgresql'
            or database.get('NAME') != 'estakada_foundation_unit'
            or database.get('USER') != 'app_migrator'):
        _fault('GALLERY_APPLY_DISABLED')


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            _fault('GALLERY_PACKAGE_INVALID')
        result[key] = value
    return result


def _canonical(value):
    try:
        return (json.dumps(value, ensure_ascii=False, indent=2,
                           allow_nan=False) + '\n').encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        _fault('GALLERY_PACKAGE_INVALID')


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        _fault('GALLERY_PACKAGE_INVALID')


def _text(value, *, characters, byte_limit=None, pattern=None):
    if type(value) is not str or len(value) > characters:
        _fault('GALLERY_PACKAGE_INVALID')
    try:
        encoded = value.encode('utf-8')
    except UnicodeError:
        _fault('GALLERY_PACKAGE_INVALID')
    if ((byte_limit is not None and len(encoded) > byte_limit)
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or (pattern is not None and re.fullmatch(pattern, value) is None)):
        _fault('GALLERY_PACKAGE_INVALID')
    return value


def _uuid(value, expected=None):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            _fault('GALLERY_PACKAGE_INVALID')
    except (ValueError, TypeError, AttributeError):
        _fault('GALLERY_PACKAGE_INVALID')
    if expected is not None and value != str(expected):
        _fault('GALLERY_PACKAGE_INVALID')
    return value


def _page_common(page, *, map_id, kind, parent_id, position):
    _keys(page, {
        'page_id', 'map_id', 'url', 'kind', 'parent_id', 'position', 'name',
        'h1', 'title', 'description', 'is_published',
    })
    _uuid(page['page_id'], uuid5(NAMESPACE, 'page:' + map_id))
    if (page['map_id'] != map_id or page['kind'] != kind
            or page['parent_id'] != parent_id or page['position'] != position
            or page['is_published'] is not False):
        _fault('GALLERY_PACKAGE_INVALID')
    _text(page['url'], characters=2048, byte_limit=2048,
          pattern=r'/gallery-of-works(?:/|/[a-z0-9-]+)')
    for field in ('name', 'h1', 'title'):
        _text(page[field], characters=255, byte_limit=1024)
    if page['description'] != '':
        _fault('GALLERY_PACKAGE_INVALID')


def _photo(value, map_id, position, seen):
    _keys(value, {
        'position', 'image_id', 'block_id', 'asset_id', 'file_id',
        'source_url', 'local_file', 'storage_key', 'bytes', 'sha256', 'alt',
    })
    if value['position'] != position:
        _fault('GALLERY_PACKAGE_INVALID')
    url = _text(value['source_url'], characters=2048, byte_limit=2048,
                pattern=r'https://estakada-service\.ru/assets/images/resources/[a-z0-9._/-]+')
    local_file = _text(
        value['local_file'], characters=1024, byte_limit=1024,
        pattern=r'media/source-site/assets/[0-9a-f]{64}\.(?:jpg|jpeg|png)')
    extension = Path(local_file).suffix
    asset = _uuid(value['asset_id'], uuid5(NAMESPACE, 'asset:' + url))
    _uuid(value['file_id'], uuid5(NAMESPACE, 'file:' + url))
    _uuid(value['image_id'], uuid5(NAMESPACE, f'image:{map_id}:{position}'))
    _uuid(value['block_id'], uuid5(NAMESPACE, f'block:{map_id}:{position}'))
    if value['storage_key'] != f'img/{asset}/original{extension}':
        _fault('GALLERY_PACKAGE_INVALID')
    if (type(value['bytes']) is not int or type(value['bytes']) is bool
            or not 0 < value['bytes'] <= 1024 * 1024
            or re.fullmatch(r'[0-9a-f]{64}', value['sha256']) is None):
        _fault('GALLERY_PACKAGE_INVALID')
    _text(value['alt'], characters=300, byte_limit=1200)
    identities = (url, local_file, value['sha256'], asset, value['file_id'],
                  value['image_id'], value['block_id'], value['storage_key'])
    if any(item in seen[index] for index, item in enumerate(identities)):
        _fault('GALLERY_PACKAGE_INVALID')
    for index, item in enumerate(identities):
        seen[index].add(item)
    return value['bytes']


def _validate(value):
    _keys(value, {'schema', 'policy', 'inputs', 'root', 'page2_map_ids', 'albums'})
    if (value['schema'] != 'dev10-gallery-v1'
            or value['policy'] != 'exact_legacy_originals_shared_album_data'
            or value['inputs'] != INPUTS
            or value['page2_map_ids'] != list(PAGE2_MAP_IDS)
            or type(value['albums']) is not list
            or len(value['albums']) != 17):
        _fault('GALLERY_PACKAGE_INVALID')
    root = value['root']
    _keys(root, {
        'page_id', 'map_id', 'url', 'page2_alias', 'kind', 'parent_id',
        'position', 'name', 'h1', 'title', 'description', 'is_published',
    })
    root_common = {key: item for key, item in root.items() if key != 'page2_alias'}
    _page_common(root_common, map_id='MAP-008', kind='gallery_catalog',
                 parent_id=HOME_ID, position=2)
    if root['page_id'] != ROOT_ID or root['url'] != '/gallery-of-works/' \
            or root['page2_alias'] != '/gallery-of-works/?page=2':
        _fault('GALLERY_PACKAGE_INVALID')
    seen = [set() for _ in range(8)]
    total = 0
    for position, album in enumerate(value['albums']):
        map_id = MAP_ORDER[position]
        _keys(album, {
            'page_id', 'map_id', 'url', 'kind', 'parent_id', 'position',
            'name', 'h1', 'title', 'description', 'is_published', 'source',
            'paragraphs', 'photos',
        })
        common = {key: album[key] for key in (
            'page_id', 'map_id', 'url', 'kind', 'parent_id', 'position',
            'name', 'h1', 'title', 'description', 'is_published')}
        _page_common(common, map_id=map_id, kind='gallery_album',
                     parent_id=ROOT_ID, position=position)
        _keys(album['source'], {'relative_path', 'sha256'})
        _text(album['source']['relative_path'], characters=1024, byte_limit=1024,
              pattern=r'work/site-audit/crawl/[0-9a-f]{20}\.html')
        if re.fullmatch(r'[0-9a-f]{64}', album['source']['sha256']) is None:
            _fault('GALLERY_PACKAGE_INVALID')
        if (type(album['paragraphs']) is not list
                or len(album['paragraphs']) != 1):
            _fault('GALLERY_PACKAGE_INVALID')
        _text(album['paragraphs'][0], characters=4096, byte_limit=4096)
        if (type(album['photos']) is not list
                or len(album['photos']) != PHOTO_COUNTS[map_id]):
            _fault('GALLERY_PACKAGE_INVALID')
        for photo_position, photo in enumerate(album['photos']):
            total += _photo(photo, map_id, photo_position, seen)
    if total != 41176391 or total > 48 * 1024 * 1024:
        _fault('GALLERY_PACKAGE_INVALID')
    return value


def _decode_package(raw):
    if type(raw) is not bytes or not raw or len(raw) > PACKAGE_MAX_BYTES \
            or b'\r' in raw:
        _fault('GALLERY_PACKAGE_INVALID')
    try:
        text = raw.decode('utf-8', errors='strict')
        value = json.loads(text, object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        _fault('GALLERY_PACKAGE_INVALID')
    if _canonical(value) != raw:
        _fault('GALLERY_PACKAGE_INVALID')
    return _validate(value)


def _read_package():
    package = Path(__file__).with_name('dev10_gallery.json')
    try:
        info = package.lstat()
        resolved = package.resolve(strict=True)
    except OSError:
        _fault('GALLERY_PACKAGE_UNAVAILABLE')
    if (not stat.S_ISREG(info.st_mode) or package.is_symlink()
            or resolved != package.absolute()
            or info.st_size > PACKAGE_MAX_BYTES):
        _fault('GALLERY_PACKAGE_UNAVAILABLE')
    try:
        raw = package.read_bytes()
    except OSError:
        _fault('GALLERY_PACKAGE_UNAVAILABLE')
    if len(raw) != info.st_size or sha256(raw).hexdigest() != PACKAGE_SHA256:
        _fault('GALLERY_PACKAGE_UNAVAILABLE')
    return _decode_package(raw)


def load_for_apply():
    """Default-off read-only package boundary."""
    _enabled()
    return _read_package()


def _payload(page):
    payload = initial_snapshot(
        page['kind'], h1=page['h1'], title=page['title']).data(page['kind'])
    payload['description'] = page['description']
    if page['kind'] == Page.Kind.GALLERY:
        return schema.Snapshot.trusted(payload, page['kind']).data(page['kind'])
    main_text = '<p>' + escape(page['paragraphs'][0], quote=False) + '</p>'
    if restricted_clean(main_text) != main_text:
        _fault('GALLERY_PACKAGE_INVALID')
    payload['main_text'] = main_text
    payload['embedded_images'] = [{
        'id': photo['image_id'], 'asset_id': photo['asset_id'],
        'alt': photo['alt'], 'alignment': 'center',
        'width_px': None, 'height_px': None,
    } for photo in page['photos']]
    payload['layout'] = [
        {'id': '71de8370-3105-5209-a189-82bb243b0051', 'kind': 'text',
         'field': 'intro_text', 'protected_nodes': []},
        {'id': '71de8370-3105-5209-a189-82bb243b0052', 'kind': 'text',
         'field': 'main_text', 'protected_nodes': []},
        *[{'id': photo['block_id'], 'kind': 'image',
           'image_id': photo['image_id']} for photo in page['photos']],
    ]
    return schema.Snapshot.trusted(payload, page['kind']).data(page['kind'])


def _photo_rows(package):
    return [photo for album in package['albums'] for photo in album['photos']]


def _descriptor(photo):
    return {
        'asset_id': photo['asset_id'], 'file_id': photo['file_id'],
        'source_url': photo['source_url'], 'source_sha256': photo['sha256'],
        'key': photo['storage_key'], 'sha256': photo['sha256'],
        'byte_size': photo['bytes'], 'kind': AssetFile.Kind.LEGACY_PUBLIC,
    }


def _evidence_digest(rows):
    return schema.digest(sorted(rows, key=lambda row: row['asset_id']))


def _preflight_blobs(package, storage=None):
    """Prove exact package blobs without reading database state."""
    storage = storage or MediaStorage()
    rows = []
    try:
        for photo in _photo_rows(package):
            expected = {'sha256': photo['sha256'], 'byte_size': photo['bytes']}
            if storage.manifest(photo['storage_key']) != expected:
                _fault('GALLERY_MEDIA_UNAVAILABLE')
            rows.append(_descriptor(photo))
    except (OSError, ValidationError):
        _fault('GALLERY_MEDIA_UNAVAILABLE')
    return _evidence_digest(rows)


def _identity():
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), current_user')
        if cursor.fetchone() != ('estakada_foundation_unit', 'app_migrator'):
            _fault('GALLERY_APPLY_DISABLED')


def _owner():
    rows = list(UserProfile.objects.select_for_update().select_related('user').filter(
        role=UserProfile.Role.OWNER, user__username='nesadmin',
        user__is_active=True))
    if len(rows) != 1:
        raise PermissionDenied('AUTH_OWNER_REQUIRED')
    return rows[0].user


def _recapture_assets(package, evidence):
    photos = _photo_rows(package)
    expected = {photo['asset_id']: _descriptor(photo) for photo in photos}
    assets = list(Asset.objects.select_for_update().filter(
        pk__in=expected).order_by('pk'))
    files = list(AssetFile.objects.select_for_update().filter(
        asset_id__in=expected).order_by('asset_id', 'pk'))
    files_by_asset = {}
    for row in files:
        files_by_asset.setdefault(str(row.asset_id), []).append(row)
    actual = []
    if len(assets) != len(expected):
        _fault('GALLERY_MEDIA_UNAVAILABLE')
    for asset in assets:
        wanted = expected.get(str(asset.pk))
        owned = files_by_asset.get(str(asset.pk), [])
        if (wanted is None or asset.status != Asset.Status.READY
                or asset.is_legacy is not True
                or asset.source_url != wanted['source_url']
                or asset.source_sha256 != wanted['source_sha256']
                or len(owned) != 1):
            _fault('GALLERY_MEDIA_UNAVAILABLE')
        file = owned[0]
        row = {
            'asset_id': str(asset.pk), 'file_id': str(file.pk),
            'source_url': asset.source_url,
            'source_sha256': asset.source_sha256, 'key': file.key,
            'sha256': file.sha256, 'byte_size': file.byte_size,
            'kind': file.kind,
        }
        if row != wanted:
            _fault('GALLERY_MEDIA_UNAVAILABLE')
        actual.append(row)
    if _evidence_digest(actual) != evidence:
        _fault('GALLERY_MEDIA_UNAVAILABLE')


def _event_rows(page_id):
    return AuditEvent.objects.filter(
        code='MIGRATION_PAGE_IMPORTED', object_ref='uuid:' + str(page_id))


def _exact_event(page_id, actor_id):
    rows = list(_event_rows(page_id))
    if len(rows) != 1:
        return False
    row = rows[0]
    return (row.category == Category.PAGES_LINKS
            and row.level == Level.INFO and row.source == Source.APPLICATION
            and row.result == Result.SUCCESS and row.actor_id == actor_id
            and row.object_kind == 'page' and row.request_id is None
            and row.ip_address is None and row.occurrence_count == 1
            and row.count_is_lower_bound is False)


def _create_aggregate(page_data, actor, payload, *, alias=None):
    page = Page.objects.create(
        id=UUID(page_data['page_id']), name=page_data['name'],
        kind=page_data['kind'], parent_id=page_data['parent_id'],
        position=page_data['position'], is_published=False)
    Route.objects.create(
        page=page, target=page_data['url'], kind=Route.Kind.PRIMARY,
        is_legacy=True)
    if alias is not None:
        Route.objects.create(
            page=page, target=alias, kind=Route.Kind.ALIAS, is_legacy=True)
    revision = engine.new_revision(
        page, None, payload, PageRevision.Kind.INITIAL, actor)
    state = PageContentState.objects.create(
        page=page, current_revision=revision, sequence=1)
    instant = engine.now()
    draft = OwnerDraft.objects.create(
        page=page, revision=1, base_revision=revision, payload=payload,
        payload_hash=schema.digest(payload), author_id=actor.pk,
        created_at=instant, updated_at=instant)
    VersionBasePin.objects.create(
        revision=revision, holder_kind='owner_draft', holder_id=draft.pk)
    engine.sync_usage(AssetUsage.Kind.CURRENT_PAGE, page.pk, payload)
    engine.sync_usage(AssetUsage.Kind.DRAFT, draft.pk, payload)
    record_event(
        category=Category.PAGES_LINKS,
        event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
        source=Source.APPLICATION, result=Result.SUCCESS,
        actor_id=actor.pk, object_kind='page', object_ref=page.pk)
    return page, revision, state, draft


def _wanted_usage(kind, consumer_id, payload):
    return {(kind, consumer_id, slot, asset_id)
            for slot, asset_id in schema.asset_slots(payload).items()}


def _exact_aggregate(page_data, actor, payload, *, alias=None):
    page_id = UUID(page_data['page_id'])
    page = Page.objects.filter(pk=page_id).first()
    if (page is None or page.name != page_data['name']
            or page.kind != page_data['kind']
            or str(page.parent_id) != page_data['parent_id']
            or page.position != page_data['position'] or page.is_published):
        return False
    routes = list(Route.objects.filter(page=page).order_by('target'))
    wanted_routes = {(page_data['url'], Route.Kind.PRIMARY, True)}
    if alias is not None:
        wanted_routes.add((alias, Route.Kind.ALIAS, True))
    if {(row.target, row.kind, row.is_legacy) for row in routes} != wanted_routes:
        return False
    revisions = list(PageRevision.objects.filter(page=page))
    states = list(PageContentState.objects.filter(page=page))
    drafts = list(OwnerDraft.objects.filter(page=page))
    if len(revisions) != 1 or len(states) != 1 or len(drafts) != 1:
        return False
    revision, state, draft = revisions[0], states[0], drafts[0]
    digest = schema.digest(payload)
    if (revision.sequence != 1 or revision.kind != PageRevision.Kind.INITIAL
            or revision.schema_version != payload['schema_version']
            or revision.payload != payload or revision.payload_hash != digest
            or revision.author_id != actor.pk or revision.source_revision_id is not None
            or state.current_revision_id != revision.pk or state.sequence != 1
            or draft.revision != 1 or draft.base_revision_id != revision.pk
            or draft.payload != payload or draft.payload_hash != digest
            or draft.author_id != actor.pk):
        return False
    metadata = list(RevisionMetadata.objects.filter(revision=revision))
    pins = list(VersionBasePin.objects.filter(
        Q(revision=revision)
        | Q(holder_kind='owner_draft', holder_id=draft.pk)))
    reservations = {(row.pk, row.kind) for row in IdentityReservation.objects.filter(
        pk__in=[revision.pk, draft.pk])}
    usages = {(row.kind, row.consumer_id, row.slot, str(row.asset_id))
              for row in AssetUsage.objects.filter(
                  consumer_id__in=[revision.pk, page.pk, draft.pk])}
    wanted_usages = set().union(
        _wanted_usage(AssetUsage.Kind.ORDINARY_VERSION, revision.pk, payload),
        _wanted_usage(AssetUsage.Kind.CURRENT_PAGE, page.pk, payload),
        _wanted_usage(AssetUsage.Kind.DRAFT, draft.pk, payload))
    return (len(metadata) == 1 and metadata[0].generation == 1
            and metadata[0].name == '' and metadata[0].comment == ''
            and metadata[0].manual_date is None and len(pins) == 1
            and pins[0].holder_kind == 'owner_draft'
            and pins[0].holder_id == draft.pk
            and reservations == {(revision.pk, 'pagerevision'),
                                  (draft.pk, 'ownerdraft')}
            and not IdentityReservation.objects.filter(pk=page_id).exists()
            and not RevisionProtection.objects.filter(revision=revision).exists()
            and not PageGrant.objects.filter(page=page).exists()
            and not RestoreStage.objects.filter(page=page).exists()
            and not OperationReceipt.objects.filter(page_id=page_id).exists()
            and usages == wanted_usages and _exact_event(page_id, actor.pk))


def _preflight_absent(pages, targets):
    page_ids = [UUID(page['page_id']) for page in pages]
    if (Page.objects.filter(pk__in=page_ids).exists()
            or Route.objects.filter(page_id__in=page_ids).exists()
            or Route.objects.filter(target__in=targets).exists()
            or IdentityReservation.objects.filter(pk__in=page_ids).exists()):
        _fault('GALLERY_EXISTING_CONFLICT')
    for page in pages:
        if (Page.objects.filter(parent_id=page['parent_id'],
                                position=page['position']).exists()
                or _event_rows(page['page_id']).exists()):
            _fault('GALLERY_EXISTING_CONFLICT')


def apply_gallery(*, storage=None):
    """Create the exact hidden gallery aggregate, or verify a zero-write replay."""
    _enabled()
    package = _read_package()
    evidence = _preflight_blobs(package, storage=storage)
    pages = [package['root'], *package['albums']]
    payloads = [_payload(page) for page in pages]
    alias = package['root']['page2_alias']
    with transaction.atomic():
        _identity()
        lock_content('default')
        lock_auth()
        actor = _owner()
        list(Page.objects.select_for_update().filter(pk=HOME_ID))
        if not _exact_parent_aggregate(
                PARENT_DESCRIPTOR, actor, _parent_payload()):
            _fault('GALLERY_PARENT_REQUIRED')
        _recapture_assets(package, evidence)
        page_ids = [UUID(page['page_id']) for page in pages]
        existing = list(Page.objects.select_for_update().filter(pk__in=page_ids))
        if len(existing) == len(pages):
            if (set(Page.objects.filter(parent_id=ROOT_ID).values_list('id', flat=True))
                    != {UUID(page['page_id']) for page in package['albums']}
                    or not all(_exact_aggregate(
                        page, actor, payload,
                        alias=alias if page is package['root'] else None)
                        for page, payload in zip(pages, payloads, strict=True))):
                _fault('GALLERY_EXISTING_CONFLICT')
            return {'status': 'pass', 'replayed': True, 'pages': 18,
                    'routes': 19, 'photos': 214, 'usages': 642,
                    'published': 0}
        if existing:
            _fault('GALLERY_EXISTING_CONFLICT')
        _preflight_absent(pages, [page['url'] for page in pages] + [alias])
        for page, payload in zip(pages, payloads, strict=True):
            _create_aggregate(
                page, actor, payload,
                alias=alias if page is package['root'] else None)
        return {'status': 'pass', 'replayed': False, 'pages': 18,
                'routes': 19, 'photos': 214, 'usages': 642,
                'published': 0}
