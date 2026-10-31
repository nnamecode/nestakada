"""Internal ledger and explicit owner cleanup. Not a content-edit/version-write API."""
from uuid import UUID
import hashlib
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from content.models import lock_content
from accounts.services import _owner, lock_auth
from .models import Asset, AssetFile, AssetUsage, FileKeyReservation
from .storage import MediaStorage

SALT = 'estakada.media.cleanup.v1'


def _raw(model):
    # Internal lifecycle commands only; model/queryset public writes remain closed.
    return models.QuerySet(model=model, using='default')


def _owner_locked(actor, generation):
    lock_content('default')
    lock_auth()
    return _owner(actor, generation)


def _asset_ids(values):
    ids = sorted(str(UUID(str(value))) for value in values)
    if not ids or len(ids) != len(set(ids)):
        raise ValidationError('MEDIA_EXPLICIT_UNIQUE_ASSETS_REQUIRED')
    return ids


def _locked_assets(ids):
    assets = list(Asset.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    if sorted(str(asset.pk) for asset in assets) != ids:
        raise ValidationError('MEDIA_ASSET_NOT_FOUND')
    return assets


def write_file(*, asset_id, kind, key, chunks, storage=None):
    """Only a trusted producer; no input image acceptance/format inference here."""
    storage = storage or MediaStorage()
    with transaction.atomic():
        lock_content('default')
        asset = Asset.objects.select_for_update().get(pk=asset_id)
        if asset.status != Asset.Status.STAGED:
            raise ValidationError('MEDIA_FILES_REQUIRE_STAGED_ASSET')
        # Validate all metadata/path fields before a physical write.
        record = AssetFile(asset=asset,kind=kind,key=key,sha256='0'*64,byte_size=0)
        record.full_clean(validate_unique=True)
        if FileKeyReservation.objects.filter(pk=key).exists():
            raise ValidationError('MEDIA_STORAGE_KEY_ALREADY_RESERVED')
        actual = storage.write_new(key, chunks)
        record.sha256, record.byte_size = actual['sha256'], actual['byte_size']
        record.save()
        return record


def _manifest(asset, storage, allow_missing=False):
    rows = []
    for file in asset.files.order_by('key'):
        expected = {'sha256':file.sha256,'byte_size':file.byte_size}
        try:
            actual = storage.manifest(file.key)
        except FileNotFoundError:
            if not allow_missing:
                raise ValidationError('MEDIA_REGISTERED_FILE_MISSING') from None
            actual = None
        if actual is not None and actual != expected:
            raise ValidationError('MEDIA_REGISTERED_FILE_CHANGED')
        rows.append({'id':str(file.pk),'key':file.key,'kind':file.kind,**expected})
    return {'asset_id':str(asset.pk),'folder_id':str(asset.folder_id),'provenance':asset.provenance,
            'is_legacy':asset.is_legacy,'source_url':asset.source_url,'source_sha256':asset.source_sha256,'files':rows}


def mark_ready(*, asset_id, storage=None):
    storage = storage or MediaStorage()
    with transaction.atomic():
        lock_content('default')
        asset = Asset.objects.select_for_update().get(pk=asset_id)
        if asset.status != Asset.Status.STAGED or not asset.files.exists():
            raise ValidationError('MEDIA_READY_REQUIRES_STAGED_FILES')
        _manifest(asset, storage)
        if asset.is_legacy:
            legacy = list(asset.files.filter(kind=AssetFile.Kind.LEGACY_PUBLIC))
            if not legacy or any(file.sha256 != asset.source_sha256 for file in legacy):
                raise ValidationError('MEDIA_LEGACY_BYTES_DO_NOT_MATCH_SOURCE')
        _raw(Asset).filter(pk=asset.pk).update(status=Asset.Status.READY)
        asset.refresh_from_db()
        return asset


def attach(*, asset_id, kind, consumer_id, slot):
    """Call within future content command; this does not create versions/Stable/HTML."""
    with transaction.atomic():
        lock_content('default')
        asset = Asset.objects.select_for_update().get(pk=asset_id)
        return AssetUsage.objects.create(asset=asset,kind=kind,consumer_id=consumer_id,slot=slot)


def detach(*, kind, consumer_id, slot):
    with transaction.atomic():
        lock_content('default')
        return _raw(AssetUsage).filter(kind=kind,consumer_id=consumer_id,slot=slot).delete()[0]


def replace(*, asset_id, kind, consumer_id, slot):
    with transaction.atomic():
        lock_content('default')
        asset = Asset.objects.select_for_update().get(pk=asset_id)
        if asset.status != Asset.Status.READY:
            raise ValidationError('MEDIA_REFERENCE_REQUIRES_READY')
        # The delete rolls back if the new reference is rejected by validation/constraints.
        detach(kind=kind,consumer_id=consumer_id,slot=slot)
        return attach(asset_id=asset.pk,kind=kind,consumer_id=consumer_id,slot=slot)


def prepare_cleanup(*, actor, asset_ids, expected_generation, storage=None):
    storage = storage or MediaStorage()
    ids = _asset_ids(asset_ids)
    with transaction.atomic():
        owner = _owner_locked(actor, expected_generation)
        manifests = []
        for asset in _locked_assets(ids):
            if asset.status != Asset.Status.READY or asset.usages.exists():
                raise ValidationError('MEDIA_ASSET_RETAINED_OR_NOT_READY')
            manifests.append(_manifest(asset, storage))
        payload = {'owner_id':str(owner.user_id),'generation':owner.generation,'assets':manifests}
        return {'candidates':manifests,'total_bytes':sum(f['byte_size'] for a in manifests for f in a['files']),
                'confirmation':signing.dumps(payload,salt=SALT,compress=True)}


def _commit_boundary():
    if connection.in_atomic_block:
        raise ValidationError('MEDIA_CLEANUP_REQUIRES_COMMIT_BOUNDARY')


def confirm_cleanup(*, actor, confirmation, expected_generation, storage=None):
    _commit_boundary()
    storage = storage or MediaStorage()
    try:
        payload = signing.loads(confirmation,salt=SALT)
        ids = _asset_ids(item['asset_id'] for item in payload['assets'])
    except (signing.BadSignature,KeyError,TypeError,ValueError):
        raise ValidationError('MEDIA_INVALID_CLEANUP_CONFIRMATION') from None
    with transaction.atomic(durable=True):
        owner = _owner_locked(actor, expected_generation)
        if payload['owner_id'] != str(owner.user_id) or payload['generation'] != owner.generation:
            raise ValidationError('MEDIA_CLEANUP_OWNER_GENERATION_CHANGED')
        current = []
        for asset in _locked_assets(ids):
            if asset.status != Asset.Status.READY or asset.usages.exists():
                raise ValidationError('MEDIA_ASSET_RETAINED_OR_NOT_READY')
            current.append(_manifest(asset, storage))
        if current != payload['assets']:
            raise ValidationError('MEDIA_CLEANUP_MANIFEST_CHANGED')
        for manifest in current:
            _raw(Asset).filter(pk=manifest['asset_id']).update(status=Asset.Status.DELETING,deletion_manifest=manifest,deletion_error='')
    # Durable DELETING precedes every unlink; no global/domain lock across physical IO.
    return [_finish(asset_id, storage) for asset_id in ids]


def retry_cleanup(*, actor, asset_id, expected_generation, storage=None):
    _commit_boundary()
    storage = storage or MediaStorage()
    with transaction.atomic(durable=True):
        _owner_locked(actor, expected_generation)
        asset = _locked_assets(_asset_ids([asset_id]))[0]
        if asset.status not in (Asset.Status.DELETING,Asset.Status.DELETE_FAILED) or not asset.deletion_manifest or asset.usages.exists():
            raise ValidationError('MEDIA_NO_RETRYABLE_CLEANUP')
        if _manifest(asset,storage,allow_missing=True) != asset.deletion_manifest:
            raise ValidationError('MEDIA_RETRY_MANIFEST_CHANGED')
        _raw(Asset).filter(pk=asset.pk).update(status=Asset.Status.DELETING,deletion_error='')
    return _finish(str(asset.pk), storage)


def _finish(asset_id, storage):
    # A session-scoped per-asset lock prevents two physical retries from racing.
    # No content/auth transaction lock is held while waiting or unlinking.
    key = int.from_bytes(hashlib.sha256(('media-cleanup:'+asset_id).encode()).digest()[:4], 'big', signed=True)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s,%s)', [73428106,key])
        if not cursor.fetchone()[0]:
            raise ValidationError('MEDIA_CLEANUP_ALREADY_RUNNING')
    try:
        return _finish_locked(asset_id, storage)
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s,%s)', [73428106,key])


def _finish_locked(asset_id, storage):
    if not Asset.objects.filter(pk=asset_id).exists():
        return {'asset_id':asset_id,'state':'already_deleted','files':[],'pending_files':0,'released_bytes':0}
    asset = Asset.objects.get(pk=asset_id)
    results = []
    for file in asset.deletion_manifest['files']:
        try:
            released = storage.unlink(file['key'],{'sha256':file['sha256'],'byte_size':file['byte_size']})
            results.append({'key':file['key'],'state':'removed','released_bytes':released})
        except FileNotFoundError:
            results.append({'key':file['key'],'state':'already_absent','released_bytes':0})
        except (OSError,ValidationError) as exc:
            results.append({'key':file['key'],'state':'pending','released_bytes':0,'error':type(exc).__name__})
    pending = [item for item in results if item['state']=='pending']
    with transaction.atomic(durable=True):
        lock_content('default')
        current = Asset.objects.select_for_update().get(pk=asset_id)
        if current.usages.exists():
            raise ValidationError('MEDIA_UNEXPECTED_REFERENCE_DURING_DELETE')
        if pending:
            _raw(Asset).filter(pk=asset_id).update(status=Asset.Status.DELETE_FAILED,deletion_error=pending[0]['error'])
        else:
            _raw(AssetFile).filter(asset_id=asset_id).delete()
            _raw(Asset).filter(pk=asset_id).delete()
    return {'asset_id':asset_id,'state':'delete_failed' if pending else 'deleted','files':results,
            'pending_files':len(pending),'released_bytes':sum(item['released_bytes'] for item in results)}
