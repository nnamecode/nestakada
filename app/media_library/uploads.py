"""Owner upload orchestration. Decoder/network operations run outside all DB locks."""
import hashlib
from pathlib import PurePath
from uuid import UUID
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from content.models import Page
from .models import MediaFolder, PageMediaHome, Asset, AssetFile
from .services import _owner_locked, write_file, mark_ready
from .storage import MediaStorage
from .worker_client import WorkerClient, UploadRejected, UploadPending, WorkerUnavailable, FORMATS, MAX_INPUT


def media_event(code,actor,asset_id=None,result=Result.SUCCESS):
    reference=UUID(str(asset_id)) if asset_id is not None else None
    return record_event(category=Category.USER_ACTIONS,event_code=code,level=Level.INFO,source=Source.APPLICATION,
                        result=result,actor_id=actor.pk,object_kind='media_asset',object_ref=reference)


def upload(*,actor,page_id,upload,expected_generation):
    if connection.in_atomic_block:raise ValidationError('MEDIA_UPLOAD_REQUIRES_COMMIT_BOUNDARY')
    page_id=UUID(str(page_id))
    with transaction.atomic():
        _owner_locked(actor,expected_generation)
        Page.objects.get(pk=page_id)
    extension=PurePath(upload.name).suffix.lower()
    mime=upload.content_type
    if extension not in FORMATS or mime!=FORMATS[extension] or upload.size>MAX_INPUT:
        media_event('MEDIA_UPLOAD_REJECTED',actor,result=Result.FAILURE)
        raise UploadRejected('MEDIA_INVALID_IMAGE_INPUT')
    upload.seek(0);source=upload.read(MAX_INPUT+1)
    if not 0<len(source)<=MAX_INPUT or len(source)!=upload.size:
        media_event('MEDIA_UPLOAD_REJECTED',actor,result=Result.FAILURE)
        raise UploadRejected('MEDIA_INPUT_SIZE_REJECTED')
    try:
        # Deliberately outside every DB transaction/domain/auth lock.
        decoded=WorkerClient().process(source,extension,mime)
    except (UploadRejected,UploadPending,WorkerUnavailable) as exc:
        media_event('MEDIA_UPLOAD_PENDING' if isinstance(exc,UploadPending) else 'MEDIA_UPLOAD_REJECTED',actor,
                    result=Result.PENDING if isinstance(exc,UploadPending) else Result.FAILURE)
        raise
    asset_id=None;committed=False
    try:
        with transaction.atomic(durable=True):
            _owner_locked(actor,expected_generation)
            page=Page.objects.select_for_update().get(pk=page_id)
            home=PageMediaHome.objects.select_related('folder').filter(page=page).first()
            if home is None:
                folder,_=MediaFolder.objects.get_or_create(path=f'pages/{page.pk}')
                home=PageMediaHome.objects.create(page=page,folder=folder)
            asset=Asset.objects.create(folder=home.folder,provenance='owner-upload/webp82-v1',source_sha256=hashlib.sha256(source).hexdigest())
            asset_id=asset.pk;storage=MediaStorage()
            write_file(asset_id=asset.pk,kind=AssetFile.Kind.PRIVATE_SOURCE,key=f'private/sources/{asset.pk}/original.bin',chunks=source,storage=storage)
            for name,kind in [('main',AssetFile.Kind.MAIN),('preview',AssetFile.Kind.PREVIEW)]:
                write_file(asset_id=asset.pk,kind=kind,key=f'img/{home.folder.path}/{asset.pk}/{name}.webp',chunks=decoded.outputs[name],storage=storage)
            asset=mark_ready(asset_id=asset.pk,storage=storage)
            media_event('MEDIA_UPLOAD_ACCEPTED',actor,asset.pk)
        committed=True
    except PermissionDenied:
        # A known terminal decoder reply is safe to discard; no DB registration committed.
        try:decoded.cleanup()
        except (OSError,ValueError):
            try:decoded.quarantine('OWNER_CHANGED',asset_id)
            except (OSError,ValueError):pass
        media_event('MEDIA_UPLOAD_DENIED',actor,result=Result.DENIED)
        raise
    except Exception:
        # A DB commit error cannot prove rollback. Keep evidence; do not remove stored files.
        try:decoded.quarantine('REGISTRATION_OUTCOME_UNKNOWN',asset_id)
        except (OSError,ValueError):pass
        raise UploadPending('MEDIA_REGISTRATION_PENDING') from None
    if committed:
        try:decoded.cleanup()
        except (OSError,ValueError):
            try:decoded.quarantine('TEMP_CLEANUP_PENDING',asset_id)
            except (OSError,ValueError):pass
    return asset
