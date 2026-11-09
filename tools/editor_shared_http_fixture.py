"""Closed own-run local HTTP fixture; no control endpoint or customer data."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
from types import SimpleNamespace
from uuid import UUID


def execute(request):
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import connection, models, transaction
    from accounts.models import UserProfile, PageGrant
    from accounts.services import bootstrap_owner, recover_owner, lock_auth
    from content.models import Page, Route, lock_content
    from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome
    from media_library.uploads import upload
    from shared_content.models import (SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage,
        SharedBasePin, SharedReceipt, SharedBudget, SharedIdentityReservation)
    from shared_content.content import content_html
    from shared_content.storage import SharedStorage
    from shared_content.policy import normalize_html
    from shared_content.test_shared_http import SharedHttpTests
    from page_editor.test_media_http import PNG
    from shared_content import quota
    if (type(request) is not dict or request.get('kind') not in ('seed', 'observe', 'reset', 'close')
            or os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or settings.ENVIRONMENT != 'test'
            or os.environ.get('DJANGO_SETTINGS_MODULE') != 'probe_settings'):
        raise ValueError('SHARED_HTTP_SCOPE')
    run_id = str(UUID(request['runId']))
    own_root = Path('/var/lib/estakada/rc-http351') / run_id
    media_root = own_root / 'media'
    if (str(settings.MEDIA_LIBRARY_ROOT) != str(media_root)
            or str(media_root.resolve(strict=False)) != str(media_root)):
        raise ValueError('SHARED_HTTP_ROOT')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(),current_user')
        if cursor.fetchone() != ('estakada_foundation', 'app_runtime'):
            raise ValueError('SHARED_HTTP_DATABASE')
    User = get_user_model()
    raw = lambda model: models.QuerySet(model=model, using='default')

    def validate(state):
        owner = User.objects.get(pk=state['ownerId'], username='nesadmin', first_name=run_id)
        if (User.objects.exclude(pk=owner.pk).exists() or Page.objects.exclude(pk=state['pageId']).exists()
                or Asset.objects.exclude(pk=state['assetId']).exists()
                or SharedRevision.objects.exclude(author_id=owner.pk).exists()
                or SharedDraft.objects.exclude(author_id=owner.pk).exists()
                or SharedRestoreStage.objects.exclude(actor_id=owner.pk).exists()):
            raise ValueError('SHARED_HTTP_FOREIGN_DATA')
        if {str(row.pk) for row in SharedBlock.objects.all()} != set(state['blockIds']):
            raise ValueError('SHARED_HTTP_BLOCKS_CHANGED')
        if set(Route.objects.values_list('target', flat=True)) != {'/manage/'}:
            raise ValueError('SHARED_HTTP_ROUTE_CHANGED')
        return owner

    if request['kind'] == 'seed':
        guarded = (User, Page, Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome,
                   SharedRevision, SharedDraft, SharedRestoreStage, SharedBasePin)
        if any(model.objects.exists() for model in guarded):
            raise ValueError('SHARED_HTTP_NONEMPTY_PRESERVED')
        if set(Route.objects.values_list('target', flat=True)) != {'/manage/'}:
            raise ValueError('SHARED_HTTP_SYSTEM_ROUTE')
        blocks = list(SharedBlock.objects.order_by('kind'))
        if (len(blocks) != 2 or {row.kind for row in blocks} != {'header', 'footer'}
                or any(row.current_revision_id is not None for row in blocks) or own_root.exists()):
            raise ValueError('SHARED_HTTP_NONEMPTY_BLOCKS')
        baseline_blocks = list(SharedBlock.objects.order_by('pk').values('id', 'generation', 'current_revision_id'))
        baseline_budget = SharedBudget.objects.values().get(singleton=True)
        media_root.mkdir(mode=0o700, parents=True)
        os.chmod(own_root, 0o700)
        if quota.measure().get('profileAvailable') is not True:
            raise ValueError('SHARED_HTTP_VERIFIED_PROFILE_REQUIRED')
        password = secrets.token_hex(48)
        owner = bootstrap_owner(password)
        owner.first_name = run_id
        owner.save(update_fields=['first_name'])
        page = Page.objects.create(kind=Page.Kind.ARTICLE, name='SHARED HTTP ' + run_id)
        asset = upload(actor=owner, page_id=page.pk, expected_generation=1,
            upload=SimpleUploadedFile('shared-http-synthetic.png', base64.b64decode(PNG), content_type='image/png'))
        if asset.status != 'ready' or asset.files.count() != 3:
            raise ValueError('SHARED_HTTP_READY_ASSET')
        markup, store = {}, SharedStorage()
        for block in blocks:
            normalized = normalize_html(SharedHttpTests.fixture(SimpleNamespace(asset=asset), block.kind,
                                                               'RSV-UI-SEED'), block.kind)
            html = normalized['html']
            descriptor = store.write_new(html)
            row = SharedRevision.objects.create(block=block, sequence=1, schema_version=block.kind + '-v1',
                html='', payload_hash=descriptor['file_sha256'], author_id=owner.pk, **descriptor)
            with transaction.atomic():
                lock_content('default')
                from media_library.services import attach
                for binding in normalized['bindings']:
                    attach(kind='shared_block', consumer_id=row.pk, slot=binding['slot'], asset_id=binding['assetId'])
                raw(SharedBlock).filter(pk=block.pk).update(current_revision_id=row.pk, generation=block.generation + 1)
            markup[block.kind] = html
        return {'runId': run_id, 'ownerId': owner.pk, 'username': 'nesadmin', 'password': password,
            'pageId': str(page.pk), 'assetId': str(asset.pk), 'folderId': str(asset.folder_id),
            'blockIds': [str(row.pk) for row in blocks], 'markup': markup,
            'baselineBlocks': baseline_blocks, 'baselineBudget': baseline_budget}

    state = request['state']
    owner = validate(state)
    if request['kind'] == 'reset':
        recover_owner(secrets.token_hex(48))
        return {'reset': True, 'generation': UserProfile.objects.get(user=owner).generation}
    if request['kind'] == 'observe':
        result = {}
        for block in SharedBlock.objects.order_by('kind'):
            row = SharedRevision.objects.filter(pk=block.current_revision_id).first()
            draft = SharedDraft.objects.filter(block=block).first()
            result[block.kind] = {'id': str(block.pk), 'current': str(row.pk) if row else None,
                'count': SharedRevision.objects.filter(block=block).count(),
                'sha256': hashlib.sha256(content_html(row).encode()).hexdigest() if row else None,
                'draftId': str(draft.pk) if draft else None, 'draftRevision': draft.revision if draft else None,
                'draftSha256': hashlib.sha256(content_html(draft).encode()).hexdigest() if draft else None}
        measured = quota.measure()
        return {'blocks': result, 'receiptCount': SharedReceipt.objects.filter(actor_id=owner.pk).count(),
            'generation': UserProfile.objects.get(user=owner).generation,
            'budget': {key: measured.get(key) for key in ('usedBytes', 'limitBytes', 'snapshotCount',
                'profileAvailable', 'heldBytes', 'retainedDebtBytes')},
            'journalCount': SharedStorage().inventory()['journalCount']}

    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [7342810601])
        if cursor.fetchone() != (True,):
            raise ValueError('SHARED_HTTP_CLEANUP_BUSY')
    try:
        with transaction.atomic():
            lock_content('default'); lock_auth(); validate(state)
            revisions = list(SharedRevision.objects.filter(author_id=owner.pk).values_list('pk', flat=True))
            drafts = list(SharedDraft.objects.filter(author_id=owner.pk).values_list('pk', flat=True))
            stages = list(SharedRestoreStage.objects.filter(actor_id=owner.pk).values_list('pk', flat=True))
            consumers = revisions + drafts + [UUID(state['pageId'])]
            if AssetUsage.objects.filter(asset_id=state['assetId']).exclude(consumer_id__in=consumers).exists():
                raise ValueError('SHARED_HTTP_FOREIGN_USAGE')
            raw(AssetUsage).filter(asset_id=state['assetId'], consumer_id__in=consumers).delete()
            raw(SharedBasePin).filter(revision_id__in=revisions).delete()
            raw(SharedDraft).filter(pk__in=drafts).delete()
            raw(SharedRestoreStage).filter(pk__in=stages).delete()
            for baseline in state['baselineBlocks']:
                raw(SharedBlock).filter(pk=baseline['id']).update(current_revision_id=None, generation=baseline['generation'])
            raw(SharedRevision).filter(pk__in=revisions).delete()
        from media_library.services import prepare_cleanup, confirm_cleanup
        generation = UserProfile.objects.get(user=owner).generation
        prepared = prepare_cleanup(actor=owner, asset_ids=[state['assetId']], expected_generation=generation)
        results = confirm_cleanup(actor=owner, confirmation=prepared['confirmation'], expected_generation=generation)
        if any(row['state'] != 'deleted' for row in results):
            raise ValueError('SHARED_HTTP_ASSET_CLEANUP')
        with transaction.atomic():
            lock_content('default'); lock_auth(); validate(state)
            raw(PageMediaHome).filter(page_id=state['pageId'], folder_id=state['folderId']).delete()
            raw(MediaFolder).filter(pk=state['folderId']).delete()
            own_session_keys = [session.session_key for session in Session.objects.all()
                if str(session.get_decoded().get('_auth_user_id')) == str(owner.pk)]
            Session.objects.filter(session_key__in=own_session_keys).delete()
            PageGrant.objects.filter(user_id=owner.pk, page_id=state['pageId']).delete()
            raw(Page).filter(pk=state['pageId']).delete()
            UserProfile.objects.filter(user_id=owner.pk).delete(); User.objects.filter(pk=owner.pk).delete()
            budget = dict(state['baselineBudget']); budget.pop('singleton', None)
            raw(SharedBudget).filter(singleton=True).update(**budget)
        if (own_root.is_symlink() or own_root.resolve() != own_root
                or own_root.parent != Path('/var/lib/estakada/rc-http351')
                or own_root.name != run_id or own_root.stat().st_uid != os.geteuid()):
            raise ValueError('SHARED_HTTP_CLEANUP_PATH')
        shutil.rmtree(own_root)
        return {'closed': True, 'remainingUsers': User.objects.count(), 'remainingPages': Page.objects.count(),
            'remainingVersions': SharedRevision.objects.count(), 'remainingDrafts': SharedDraft.objects.count(),
            'remainingStages': SharedRestoreStage.objects.count(), 'remainingAssets': Asset.objects.count(),
            'permanentSharedReceipts': SharedReceipt.objects.count(),
            'permanentSharedIdentities': SharedIdentityReservation.objects.count(), 'ownRootAbsent': not own_root.exists()}
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [7342810601])
            if cursor.fetchone() != (True,):
                raise ValueError('SHARED_HTTP_CLEANUP_LEASE_LOST')


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin)), default=str))
    except Exception as error:
        print(json.dumps({'errorClass': type(error).__name__, 'code': 'SHARED_HTTP_FIXTURE_FAILED'}), file=sys.stderr)
        raise SystemExit(1)
