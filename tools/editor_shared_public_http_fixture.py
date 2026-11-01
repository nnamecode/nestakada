"""Closed synthetic public-host fixture; no product control endpoint."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
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
    from accounts.models import AuthSession, UserProfile, PageGrant
    from accounts.services import bootstrap_owner, lock_auth
    from content.models import Page, Route, lock_content
    from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome
    from media_library.uploads import upload
    from media_library.storage import MediaStorage
    from shared_content.models import (SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage,
        SharedBasePin, SharedReceipt, SharedBudget, SharedCleanupJob)
    from shared_content.storage import SharedStorage
    from shared_content.content import content_html
    from shared_content.policy import normalize_html
    from shared_content.test_shared_http import SharedHttpTests
    from page_editor.test_media_http import PNG
    from shared_content import quota
    if (type(request) is not dict or request.get('kind') not in ('seed', 'observe', 'rename', 'close')
            or settings.ENVIRONMENT != 'test' or os.environ.get('ESTAKADA_LOCAL_ENV') != 'test'
            or os.environ.get('DJANGO_SETTINGS_MODULE') != 'probe_settings'
            or settings.ROOT_URLCONF != 'shared_content.public_test_urls'):
        raise ValueError('PUBLIC_HTTP_SCOPE')
    run_id = str(UUID(request['runId']))
    prefix = Path('/var/lib/estakada/pub-http356')
    own_root, media_root = prefix / run_id, prefix / run_id / 'media'
    if str(settings.MEDIA_LIBRARY_ROOT) != str(media_root) or media_root.resolve(strict=False) != media_root:
        raise ValueError('PUBLIC_HTTP_ROOT')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(),current_user')
        if cursor.fetchone() != ('estakada_foundation', 'app_runtime'):
            raise ValueError('PUBLIC_HTTP_DATABASE')
    User = get_user_model()
    raw = lambda model: models.QuerySet(model=model, using='default')

    def validate(state):
        owner = User.objects.get(pk=state['ownerId'], username='nesadmin', first_name=run_id)
        if (User.objects.exclude(pk=owner.pk).exists()
                or Page.objects.exclude(pk__in=state['pageIds']).exists()
                or Asset.objects.exclude(pk=state['assetId']).exists()
                or SharedRevision.objects.exclude(author_id=owner.pk).exists()
                or SharedDraft.objects.exclude(author_id=owner.pk).exists()
                or SharedRestoreStage.objects.exclude(actor_id=owner.pk).exists()
                or SharedCleanupJob.objects.exclude(phase='complete').exists()):
            raise ValueError('PUBLIC_HTTP_FOREIGN_OR_UNFINISHED')
        if set(Route.objects.values_list('target', flat=True)) != {'/manage/', *state['navTargets']}:
            raise ValueError('PUBLIC_HTTP_ROUTE_CHANGED')
        if {str(value) for value in SharedBlock.objects.values_list('pk', flat=True)} != set(state['blockIds']):
            raise ValueError('PUBLIC_HTTP_BLOCKS_CHANGED')
        return owner

    if request['kind'] == 'seed':
        guarded = (User, Page, Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome,
                   SharedRevision, SharedDraft, SharedRestoreStage, SharedBasePin)
        if any(model.objects.exists() for model in guarded) or SharedCleanupJob.objects.exclude(phase='complete').exists():
            raise ValueError('PUBLIC_HTTP_NONEMPTY_PRESERVED')
        if set(Route.objects.values_list('target', flat=True)) != {'/manage/'} or own_root.exists():
            raise ValueError('PUBLIC_HTTP_NONEMPTY_NAMESPACE')
        blocks = list(SharedBlock.objects.order_by('kind'))
        if len(blocks) != 2 or any(block.current_revision_id is not None for block in blocks):
            raise ValueError('PUBLIC_HTTP_NONEMPTY_BLOCKS')
        baseline_blocks = list(SharedBlock.objects.order_by('pk').values('id', 'generation', 'current_revision_id'))
        baseline_budget = SharedBudget.objects.values().get(singleton=True)
        prefix.mkdir(mode=0o700, exist_ok=True)
        info = prefix.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('PUBLIC_HTTP_PREFIX_INVALID')
        own_root.mkdir(mode=0o700); media_root.mkdir(mode=0o700)
        if quota.measure().get('profileAvailable') is not True:
            raise ValueError('PUBLIC_HTTP_VERIFIED_PROFILE_REQUIRED')
        password = secrets.token_hex(48)
        owner = bootstrap_owner(password); owner.first_name = run_id; owner.save(update_fields=['first_name'])
        page = Page.objects.create(kind=Page.Kind.ARTICLE, name='PUBLIC HTTP ' + run_id)
        asset = upload(actor=owner, page_id=page.pk, expected_generation=1,
            upload=SimpleUploadedFile('public-synthetic.png', base64.b64decode(PNG), content_type='image/png'))
        if asset.status != 'ready' or asset.files.count() != 3:
            raise ValueError('PUBLIC_HTTP_READY_ASSET')
        nav_ids, nav_targets = [], []
        with transaction.atomic():
            lock_content('default')
            for index, label in enumerate(('Услуги и цены', 'Акции', 'Наши работы', 'Отзывы', 'Статьи', 'Контакты')):
                node = Page.objects.create(kind=Page.Kind.ARTICLE, name=label, is_published=True)
                target = '/pub-fixture-' + run_id + '/item-' + str(index) + '/'
                Route.objects.create(kind=Route.Kind.PRIMARY, page=node, target=target)
                nav_ids.append(str(node.pk)); nav_targets.append(target)
        markup = {}
        for block in blocks:
            normalized = normalize_html(SharedHttpTests.fixture(SimpleNamespace(asset=asset), block.kind, 'PUB-UI-SEED'), block.kind)
            descriptor = SharedStorage().write_new(normalized['html'])
            row = SharedRevision.objects.create(block=block, sequence=1, schema_version=block.kind + '-v1',
                html='', payload_hash=descriptor['file_sha256'], author_id=owner.pk, **descriptor)
            with transaction.atomic():
                lock_content('default')
                from media_library.services import attach
                for binding in normalized['bindings']:
                    attach(kind='shared_block', consumer_id=row.pk, slot=binding['slot'], asset_id=binding['assetId'])
                raw(SharedBlock).filter(pk=block.pk).update(current_revision_id=row.pk, generation=block.generation + 1)
            markup[block.kind] = normalized['html']
        return {'runId': run_id, 'ownerId': owner.pk, 'username': 'nesadmin', 'password': password,
            'pageId': str(page.pk), 'pageIds': [str(page.pk), *nav_ids], 'navPageIds': nav_ids, 'navTargets': nav_targets,
            'assetId': str(asset.pk), 'folderId': str(asset.folder_id),
            'assetFiles': {file.kind: str(file.pk) for file in asset.files.all()},
            'blockIds': [str(block.pk) for block in blocks], 'markup': markup,
            'baselineBlocks': baseline_blocks, 'baselineBudget': baseline_budget}

    state = request['state']; owner = validate(state)
    if request['kind'] == 'rename':
        with transaction.atomic():
            lock_content('default'); validate(state)
            raw(Page).filter(pk=state['navPageIds'][0]).update(name='Услуги — проверка обновления')
        return {'renamed': True}
    if request['kind'] == 'observe':
        blocks = {}
        for block in SharedBlock.objects.order_by('kind'):
            row = SharedRevision.objects.filter(pk=block.current_revision_id).first()
            blocks[block.kind] = {'current': str(row.pk) if row else None,
                'count': SharedRevision.objects.filter(block=block).count(),
                'sha256': hashlib.sha256(content_html(row).encode()).hexdigest() if row else None}
        actual_nav = list(Page.objects.filter(pk__in=state['navPageIds']).order_by('position', 'id').values('id', 'name', 'is_published'))
        return {'blocks': blocks, 'nav': actual_nav, 'sessionCount': Session.objects.count(),
            'authSessionCount': AuthSession.objects.count(), 'receiptCount': SharedReceipt.objects.filter(actor_id=owner.pk).count(),
            'jobCount': SharedCleanupJob.objects.count(), 'pinCount': SharedBasePin.objects.count(),
            'assetManifests': {str(file.pk): MediaStorage().manifest(file.key) for file in asset_files(state)},
            'inventoryStamp': SharedStorage().inventory()['inventoryStamp']}

    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [7342810601])
        if cursor.fetchone() != (True,): raise ValueError('PUBLIC_HTTP_CLEANUP_BUSY')
    try:
        with transaction.atomic():
            lock_content('default'); lock_auth(); validate(state)
            revisions = list(SharedRevision.objects.filter(author_id=owner.pk).values_list('pk', flat=True))
            drafts = list(SharedDraft.objects.filter(author_id=owner.pk).values_list('pk', flat=True))
            consumers = revisions + drafts + [UUID(value) for value in state['pageIds']]
            if AssetUsage.objects.filter(asset_id=state['assetId']).exclude(consumer_id__in=consumers).exists():
                raise ValueError('PUBLIC_HTTP_FOREIGN_USAGE')
            raw(AssetUsage).filter(asset_id=state['assetId'], consumer_id__in=consumers).delete()
            raw(SharedBasePin).filter(revision_id__in=revisions).delete()
            raw(SharedDraft).filter(pk__in=drafts).delete()
            raw(SharedRestoreStage).filter(actor_id=owner.pk).delete()
            for baseline in state['baselineBlocks']:
                raw(SharedBlock).filter(pk=baseline['id']).update(current_revision_id=None, generation=baseline['generation'])
            raw(SharedRevision).filter(pk__in=revisions).delete()
        from media_library.services import prepare_cleanup, confirm_cleanup
        generation = UserProfile.objects.get(user=owner).generation
        prepared = prepare_cleanup(actor=owner, asset_ids=[state['assetId']], expected_generation=generation)
        result = confirm_cleanup(actor=owner, confirmation=prepared['confirmation'], expected_generation=generation)
        if any(row['state'] != 'deleted' for row in result): raise ValueError('PUBLIC_HTTP_MEDIA_CLEANUP')
        with transaction.atomic():
            lock_content('default'); lock_auth(); validate(state)
            raw(PageMediaHome).filter(page_id=state['pageId'], folder_id=state['folderId']).delete()
            raw(MediaFolder).filter(pk=state['folderId']).delete()
            keys = list(AuthSession.objects.filter(user_id=owner.pk).values_list('pk', flat=True))
            Session.objects.filter(session_key__in=keys).delete()
            AuthSession.objects.filter(user_id=owner.pk, session_key__in=keys).delete()
            PageGrant.objects.filter(user_id=owner.pk, page_id__in=state['pageIds']).delete()
            raw(Route).filter(page_id__in=state['navPageIds'], target__in=state['navTargets']).delete()
            raw(Page).filter(pk__in=state['pageIds']).delete()
            UserProfile.objects.filter(user_id=owner.pk).delete(); User.objects.filter(pk=owner.pk).delete()
            budget = dict(state['baselineBudget']); budget.pop('singleton', None)
            raw(SharedBudget).filter(singleton=True).update(**budget)
        if own_root.is_symlink() or own_root.resolve() != own_root or own_root.parent != prefix or own_root.stat().st_uid != os.geteuid():
            raise ValueError('PUBLIC_HTTP_CLEANUP_PATH')
        shutil.rmtree(own_root)
        return {'closed': True, 'remainingUsers': User.objects.count(), 'remainingPages': Page.objects.count(),
            'remainingVersions': SharedRevision.objects.count(), 'remainingAssets': Asset.objects.count(),
            'remainingOwnRoutes': Route.objects.filter(page_id__in=state['navPageIds']).count(), 'ownRootAbsent': not own_root.exists()}
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [7342810601])
            if cursor.fetchone() != (True,): raise ValueError('PUBLIC_HTTP_CLEANUP_LEASE_LOST')


def asset_files(state):
    from media_library.models import AssetFile
    return AssetFile.objects.filter(asset_id=state['assetId']).order_by('pk')


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin)), default=str))
    except Exception as error:
        print(json.dumps({'errorClass': type(error).__name__, 'code': 'PUBLIC_HTTP_FIXTURE_FAILED'}), file=sys.stderr)
        raise SystemExit(1)
