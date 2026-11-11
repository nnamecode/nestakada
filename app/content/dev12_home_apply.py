"""Default-off exact DEV-12 design-media import and home writer boundary."""
from hashlib import sha256
import json
from pathlib import Path
import stat
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, models, transaction
from django.db.models import Q

from accounts.models import PageGrant, UserProfile
from accounts.services import lock_auth
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from media_library import services as media_services
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from media_library.storage import MediaStorage
from page_versions import engine, schema
from page_versions.home_profile import validate as validate_home_profile
from page_versions.models import (
    IdentityReservation, OperationReceipt, OwnerDraft, PageContentState,
    PageRevision, RestoreStage, RevisionMetadata, RevisionProtection,
    VersionBasePin,
)

from .dev09_migration_apply import (
    PARENT_DESCRIPTOR, _exact_aggregate as _exact_parent_aggregate,
    _parent_payload,
)
from .dev10_gallery_apply import _photo_rows, _read_package as _read_gallery
from .models import Page, Route, lock_content


PACKAGE_SHA256 = 'c12caba76e429ac11496b0a299f61919f7c8a1c200f494acb99e08baff9d4d56'
PACKAGE_MAX_BYTES = 512 * 1024
SOURCE_FILE_MAX_BYTES = 512 * 1024
SOURCE_TOTAL_MAX_BYTES = 4 * 1024 * 1024
MEDIA_FOLDER_ID = UUID('4acfa9d3-af47-565c-949c-66a9ad9ea2d2')
MEDIA_FOLDER_PATH = 'design/home'
PROVENANCE = 'DEV12 approved design media'
HOME_ID = PARENT_DESCRIPTOR['page_id']


def _fault(code):
    raise ValidationError(code)


def _enabled():
    database = connection.settings_dict
    if (getattr(settings, 'ENVIRONMENT', None) != 'test'
            or getattr(settings, 'DEV12_HOME_APPLY_ENABLED', False) is not True
            or database.get('ENGINE') != 'django.db.backends.postgresql'
            or database.get('NAME') != 'estakada_foundation_unit'
            or database.get('USER') != 'app_migrator'):
        _fault('HOME_APPLY_DISABLED')


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            _fault('HOME_PACKAGE_INVALID')
        result[key] = value
    return result


def _read_package():
    path = Path(__file__).with_name('dev12_home_profile.json')
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
        raw = path.read_bytes()
    except OSError:
        _fault('HOME_PACKAGE_UNAVAILABLE')
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or resolved != path.absolute() or len(raw) != info.st_size
            or len(raw) > PACKAGE_MAX_BYTES
            or sha256(raw).hexdigest() != PACKAGE_SHA256):
        _fault('HOME_PACKAGE_UNAVAILABLE')
    try:
        package = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, TypeError):
        _fault('HOME_PACKAGE_INVALID')
    if (type(package) is not dict
            or set(package) != {'schema', 'policy', 'inputs', 'home', 'profile', 'media'}
            or package.get('schema') != 'dev12-home-package-v1'
            or package.get('policy') != 'approved_v4_core_owner_versioned_profile'):
        _fault('HOME_PACKAGE_INVALID')
    _validate_media(package.get('media'))
    validate_home_profile(package.get('profile'), [
        {'id': row['image_id'], 'asset_id': row['asset_id']}
        for row in package['media']
    ] + [
        {'id': row['image_id'], 'asset_id': row['asset_id']}
        for row in package['profile']['works']
    ])
    return package


def _validate_media(rows):
    fields = {'role', 'image_id', 'asset_id', 'file_id', 'local_file',
              'storage_key', 'kind', 'mime', 'bytes', 'sha256', 'alt'}
    if type(rows) is not list or len(rows) != 15:
        _fault('HOME_PACKAGE_INVALID')
    unique = {key: set() for key in ('role', 'image_id', 'asset_id', 'file_id',
                                      'local_file', 'storage_key')}
    total = 0
    for row in rows:
        if type(row) is not dict or set(row) != fields:
            _fault('HOME_PACKAGE_INVALID')
        try:
            UUID(row['image_id']); UUID(row['asset_id']); UUID(row['file_id'])
        except (ValueError, TypeError, AttributeError):
            _fault('HOME_PACKAGE_INVALID')
        if (row['kind'] != AssetFile.Kind.MAIN or row['mime'] != 'image/webp'
                or type(row['bytes']) is not int
                or not 0 < row['bytes'] <= SOURCE_FILE_MAX_BYTES
                or type(row['sha256']) is not str or len(row['sha256']) != 64
                or any(char not in '0123456789abcdef' for char in row['sha256'])
                or not row['local_file'].startswith('media/design-concepts/')
                or '..' in Path(row['local_file']).parts
                or row['storage_key'] != f"img/{row['asset_id']}/main.webp"):
            _fault('HOME_PACKAGE_INVALID')
        total += row['bytes']
        for key in unique:
            if row[key] in unique[key]:
                _fault('HOME_PACKAGE_INVALID')
            unique[key].add(row[key])
    if total > SOURCE_TOTAL_MAX_BYTES:
        _fault('HOME_PACKAGE_INVALID')


def _source_bytes(row, source_root):
    root = Path(source_root).resolve(strict=True)
    path = root.joinpath(*Path(row['local_file']).parts)
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
        data = path.read_bytes()
    except OSError:
        _fault('HOME_MEDIA_SOURCE_UNAVAILABLE')
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or resolved != path.absolute() or root not in resolved.parents
            or len(data) != info.st_size or len(data) != row['bytes']
            or sha256(data).hexdigest() != row['sha256']):
        _fault('HOME_MEDIA_SOURCE_UNAVAILABLE')
    return data


def _raw(model):
    return models.QuerySet(model=model, using='default')


def _exact_asset(row, asset, files):
    return (asset.folder_id == MEDIA_FOLDER_ID
            and asset.provenance == PROVENANCE and not asset.is_legacy
            and asset.source_url == '' and asset.source_sha256 == row['sha256']
            and len(files) == 1 and str(files[0].pk) == row['file_id']
            and files[0].kind == row['kind']
            and files[0].key == row['storage_key']
            and files[0].sha256 == row['sha256']
            and files[0].byte_size == row['bytes'])


def import_home_media(*, source_root, storage=None):
    """Import exact approved bytes, or finish/verify the same interrupted import."""
    _enabled()
    package = _read_package()
    storage = storage or MediaStorage()
    rows = package['media']
    sources = [(row, _source_bytes(row, source_root)) for row in rows]
    with transaction.atomic():
        folder = MediaFolder.objects.select_for_update().filter(pk=MEDIA_FOLDER_ID).first()
        if folder is None:
            folder = MediaFolder.objects.create(id=MEDIA_FOLDER_ID, path=MEDIA_FOLDER_PATH)
        elif folder.path != MEDIA_FOLDER_PATH:
            _fault('HOME_MEDIA_EXISTING_CONFLICT')
    created = 0
    recovered = 0
    replayed = 0
    for row, data in sources:
        with transaction.atomic():
            asset = Asset.objects.select_for_update().filter(pk=row['asset_id']).first()
            if asset is None:
                asset = Asset.objects.create(
                    id=UUID(row['asset_id']), folder_id=MEDIA_FOLDER_ID,
                    provenance=PROVENANCE, source_sha256=row['sha256'])
                created += 1
            files = list(AssetFile.objects.select_for_update().filter(
                asset=asset).order_by('pk'))
            if asset.status == Asset.Status.READY:
                if not _exact_asset(row, asset, files):
                    _fault('HOME_MEDIA_EXISTING_CONFLICT')
                if storage.manifest(row['storage_key']) != {
                        'sha256': row['sha256'], 'byte_size': row['bytes']}:
                    _fault('HOME_MEDIA_PHYSICAL_MISMATCH')
                replayed += 1
                continue
            if asset.status != Asset.Status.STAGED:
                _fault('HOME_MEDIA_EXISTING_CONFLICT')
            if files:
                if not _exact_asset(row, asset, files):
                    _fault('HOME_MEDIA_EXISTING_CONFLICT')
                if storage.manifest(row['storage_key']) != {
                        'sha256': row['sha256'], 'byte_size': row['bytes']}:
                    _fault('HOME_MEDIA_PHYSICAL_MISMATCH')
                recovered += 1
            else:
                media_services.write_file(
                    asset_id=asset.pk, file_id=row['file_id'], kind=row['kind'],
                    key=row['storage_key'], chunks=data, storage=storage)
        media_services.mark_ready(asset_id=row['asset_id'], storage=storage)
    return {'status': 'pass', 'assets': len(rows), 'created': created,
            'recovered': recovered, 'replayed': replayed}


def _target_payload(package):
    payload = _parent_payload()
    payload['description'] = package['home']['description']
    payload['indexing_allowed'] = package['home']['indexing_allowed']
    payload['embedded_images'] = [
        {'id': row['image_id'], 'asset_id': row['asset_id'], 'alt': row['alt'],
         'alignment': 'center', 'width_px': None, 'height_px': None}
        for row in [*package['media'], *package['profile']['works']]
    ]
    payload['home_profile'] = package['profile']
    return schema.Snapshot.trusted(payload, Page.Kind.HOME).data(Page.Kind.HOME)


def _media_descriptors(package):
    design = [{
        'asset_id': row['asset_id'], 'file_id': row['file_id'],
        'key': row['storage_key'], 'sha256': row['sha256'],
        'byte_size': row['bytes'], 'kind': AssetFile.Kind.MAIN,
        'legacy': False, 'source_url': '', 'source_sha256': row['sha256'],
        'folder_id': str(MEDIA_FOLDER_ID), 'provenance': PROVENANCE,
    } for row in package['media']]
    gallery = {row['asset_id']: row for row in _photo_rows(_read_gallery())}
    works = []
    for work in package['profile']['works']:
        row = gallery.get(work['asset_id'])
        if row is None:
            _fault('HOME_MEDIA_UNAVAILABLE')
        works.append({
            'asset_id': row['asset_id'], 'file_id': row['file_id'],
            'key': row['storage_key'], 'sha256': row['sha256'],
            'byte_size': row['bytes'], 'kind': AssetFile.Kind.LEGACY_PUBLIC,
            'legacy': True, 'source_url': row['source_url'],
            'source_sha256': row['sha256'], 'folder_id': None,
            'provenance': None,
        })
    result = sorted([*design, *works], key=lambda row: row['asset_id'])
    if len(result) != 21 or len({row['asset_id'] for row in result}) != 21:
        _fault('HOME_MEDIA_UNAVAILABLE')
    return result


def _physical_preflight(descriptors, storage):
    for row in descriptors:
        try:
            actual = storage.manifest(row['key'])
        except (OSError, ValidationError):
            _fault('HOME_MEDIA_UNAVAILABLE')
        if actual != {'sha256': row['sha256'], 'byte_size': row['byte_size']}:
            _fault('HOME_MEDIA_UNAVAILABLE')


def _identity():
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), current_user')
        if cursor.fetchone() != ('estakada_foundation_unit', 'app_migrator'):
            _fault('HOME_APPLY_DISABLED')


def _owner():
    rows = list(UserProfile.objects.select_for_update().select_related('user').filter(
        role=UserProfile.Role.OWNER, user__username='nesadmin',
        user__is_active=True))
    if len(rows) != 1:
        raise PermissionDenied('AUTH_OWNER_REQUIRED')
    return rows[0].user


def _recapture_media(descriptors, storage):
    expected = {row['asset_id']: row for row in descriptors}
    assets = list(Asset.objects.select_for_update().filter(
        pk__in=expected).order_by('pk'))
    files = list(AssetFile.objects.select_for_update().filter(
        asset_id__in=expected).order_by('asset_id', 'pk'))
    by_asset = {}
    for file in files:
        by_asset.setdefault(str(file.asset_id), []).append(file)
    if len(assets) != len(expected):
        _fault('HOME_MEDIA_UNAVAILABLE')
    for asset in assets:
        wanted = expected[str(asset.pk)]
        owned = by_asset.get(str(asset.pk), [])
        if (asset.status != Asset.Status.READY or len(owned) != 1
                or asset.is_legacy is not wanted['legacy']
                or asset.source_url != wanted['source_url']
                or asset.source_sha256 != wanted['source_sha256']
                or (wanted['folder_id'] is not None
                    and str(asset.folder_id) != wanted['folder_id'])
                or (wanted['provenance'] is not None
                    and asset.provenance != wanted['provenance'])):
            _fault('HOME_MEDIA_UNAVAILABLE')
        file = owned[0]
        if ({'asset_id':str(asset.pk), 'file_id':str(file.pk), 'key':file.key,
             'sha256':file.sha256, 'byte_size':file.byte_size, 'kind':file.kind}
                != {key:wanted[key] for key in (
                    'asset_id', 'file_id', 'key', 'sha256', 'byte_size', 'kind')}):
            _fault('HOME_MEDIA_UNAVAILABLE')
        try:
            actual = storage.manifest(file.key)
        except (OSError, ValidationError):
            _fault('HOME_MEDIA_UNAVAILABLE')
        if actual != {'sha256': file.sha256, 'byte_size': file.byte_size}:
            _fault('HOME_MEDIA_UNAVAILABLE')


def _wanted_usages(kind, consumer_id, payload):
    return {(kind, consumer_id, slot, UUID(asset_id))
            for slot, asset_id in schema.asset_slots(payload).items()}


def _event_exact(actor_id):
    rows = list(AuditEvent.objects.filter(
        code='HOME_PROFILE_IMPORTED', object_ref='uuid:' + HOME_ID))
    if len(rows) != 1:
        return False
    row = rows[0]
    return (row.category == Category.PAGES_LINKS and row.level == Level.INFO
            and row.source == Source.APPLICATION and row.result == Result.SUCCESS
            and row.actor_id == actor_id and row.object_kind == 'page'
            and row.request_id is None and row.ip_address is None
            and row.occurrence_count == 1 and row.count_is_lower_bound is False)


def _exact_applied(actor, payload):
    page = Page.objects.filter(pk=HOME_ID).first()
    if (page is None or page.name != PARENT_DESCRIPTOR['name']
            or page.kind != Page.Kind.HOME or page.parent_id is not None
            or page.position != 0 or page.is_published):
        return False
    routes = list(Route.objects.filter(page=page))
    revisions = list(PageRevision.objects.filter(page=page).order_by('sequence'))
    states = list(PageContentState.objects.filter(page=page))
    drafts = list(OwnerDraft.objects.filter(page=page))
    if len(routes) != 1 or len(revisions) != 2 or len(states) != 1 or len(drafts) != 1:
        return False
    route, initial, current, state, draft = routes[0], *revisions, states[0], drafts[0]
    base = _parent_payload(); digest = schema.digest(payload)
    if (route.kind != Route.Kind.PRIMARY or route.target != '/'
            or route.is_legacy is not True
            or initial.sequence != 1 or initial.kind != PageRevision.Kind.INITIAL
            or initial.payload != base or initial.payload_hash != schema.digest(base)
            or initial.author_id != actor.pk or initial.source_revision_id is not None
            or current.sequence != 2 or current.kind != PageRevision.Kind.AUTOMATIC
            or current.payload != payload or current.payload_hash != digest
            or current.author_id != actor.pk or current.source_revision_id != initial.pk
            or state.current_revision_id != current.pk or state.sequence != 2
            or draft.revision != 2 or draft.base_revision_id != current.pk
            or draft.payload != payload or draft.payload_hash != digest
            or draft.author_id != actor.pk):
        return False
    metadata = list(RevisionMetadata.objects.filter(
        revision_id__in=[initial.pk, current.pk]).order_by('revision__sequence'))
    pins = list(VersionBasePin.objects.filter(
        Q(revision_id__in=[initial.pk, current.pk])
        | Q(holder_kind='owner_draft', holder_id=draft.pk)))
    usages = {(row.kind, row.consumer_id, row.slot, row.asset_id)
              for row in AssetUsage.objects.filter(
                  consumer_id__in=[page.pk, initial.pk, current.pk, draft.pk])}
    wanted = (_wanted_usages(AssetUsage.Kind.CURRENT_PAGE, page.pk, payload)
              | _wanted_usages(AssetUsage.Kind.ORDINARY_VERSION, current.pk, payload)
              | _wanted_usages(AssetUsage.Kind.DRAFT, draft.pk, payload))
    return (len(metadata) == 2
            and all(row.generation == 1 and row.name == '' and row.comment == ''
                    and row.manual_date is None for row in metadata)
            and len(pins) == 1 and pins[0].revision_id == current.pk
            and pins[0].holder_kind == 'owner_draft'
            and pins[0].holder_id == draft.pk and usages == wanted
            and not RevisionProtection.objects.filter(revision__page=page).exists()
            and not PageGrant.objects.filter(page=page).exists()
            and not RestoreStage.objects.filter(page=page).exists()
            and not OperationReceipt.objects.filter(page_id=page.pk).exists()
            and IdentityReservation.objects.filter(
                pk__in=[initial.pk, current.pk, draft.pk]).count() == 3
            and _event_exact(actor.pk))


def apply_home(*, storage=None):
    """Apply the exact approved hidden home profile, or verify zero-write replay."""
    _enabled()
    package = _read_package()
    payload = _target_payload(package)
    descriptors = _media_descriptors(package)
    storage = storage or MediaStorage()
    _physical_preflight(descriptors, storage)
    with transaction.atomic():
        _identity()
        lock_content('default'); lock_auth()
        actor = _owner()
        list(Page.objects.select_for_update().filter(pk=HOME_ID))
        _recapture_media(descriptors, storage)
        if _exact_applied(actor, payload):
            return {'status':'pass', 'replayed':True, 'page_id':HOME_ID,
                    'revision':2, 'assets':21, 'usages':63, 'published':0}
        if not _exact_parent_aggregate(PARENT_DESCRIPTOR, actor, _parent_payload()):
            _fault('HOME_EXISTING_CONFLICT')
        page = Page.objects.select_for_update().get(pk=HOME_ID)
        state = PageContentState.objects.select_for_update().get(page=page)
        draft = OwnerDraft.objects.select_for_update().get(page=page)
        initial = state.current_revision
        revision = engine.new_revision(
            page, state, payload, PageRevision.Kind.AUTOMATIC, actor,
            source=initial.pk)
        engine.raw(PageContentState).filter(pk=state.pk).update(
            current_revision=revision)
        engine.raw(VersionBasePin).filter(
            holder_kind='owner_draft', holder_id=draft.pk).delete()
        engine.raw(OwnerDraft).filter(pk=draft.pk).update(
            revision=2, base_revision=revision, payload=payload,
            payload_hash=schema.digest(payload), author_id=actor.pk,
            updated_at=engine.now())
        VersionBasePin.objects.create(
            revision=revision, holder_kind='owner_draft', holder_id=draft.pk)
        engine.sync_usage(AssetUsage.Kind.CURRENT_PAGE, page.pk, payload)
        engine.sync_usage(AssetUsage.Kind.DRAFT, draft.pk, payload)
        record_event(
            category=Category.PAGES_LINKS, event_code='HOME_PROFILE_IMPORTED',
            level=Level.INFO, source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=actor.pk, object_kind='page', object_ref=page.pk)
        return {'status':'pass', 'replayed':False, 'page_id':HOME_ID,
                'revision':2, 'assets':21, 'usages':63, 'published':0}
