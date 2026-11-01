"""NH normal-only fixture/observer/cleanup; no HTTP control endpoint."""
import json
import os
import base64
import hashlib
import secrets
import sys
from pathlib import Path
from uuid import UUID, uuid4


def execute(request):
    if (os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or
            os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http'):
        raise ValueError('Exclusive ordinary local test profile required')
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import connection, models, transaction
    from django.apps import apps
    from django.core.files.uploadedfile import SimpleUploadedFile
    from accounts.models import AuthSession, UserProfile, PageGrant
    from content.models import Page, Route, lock_content
    from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome
    from media_library.storage import MediaStorage
    from page_versions.models import (PageRevision, PageContentState, RevisionMetadata,
        RevisionProtection, OwnerDraft, RestoreStage, VersionBasePin, OperationReceipt)
    from page_versions.models import IdentityReservation as VersionIdentityReservation
    from media_library.models import IdentityReservation as MediaIdentityReservation
    from page_versions.schema import digest
    from audit.models import AuditEvent
    if settings.ROOT_URLCONF != 'estakada.urls':
        raise ValueError('Exact normal editor URLConf required')
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise ValueError('Wrong database')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(),current_user')
        if cursor.fetchone() != ('estakada_foundation', 'app_runtime'):
            raise ValueError('Exact ordinary runtime database role required')
    if type(request) is not dict or request.get('kind') not in ('seed', 'observe', 'passive', 'close'):
        raise ValueError('Closed fixture operation required')
    run_id = str(UUID(request['runId']))
    User = get_user_model()
    raw = lambda model: models.QuerySet(model=model, using='default')
    forbidden = [RevisionProtection]
    def shared_hash():
        # Streaming full rows, including Budget and permanent rows. No mutation,
        # no payload/secret output, and no restore of accounting counters.
        value = hashlib.sha256()
        for model in sorted(apps.get_app_config('shared_content').get_models(), key=lambda item:item._meta.db_table):
            value.update(model._meta.db_table.encode())
            for record in model.objects.order_by('pk').values().iterator(chunk_size=16):
                value.update(json.dumps(record, default=str, sort_keys=True, separators=(',', ':')).encode())
                value.update(b'\n')
        return value.hexdigest()
    def system_route(system_ids=None):
        rows = list(Route.objects.filter(target='/manage/').values('id','target','kind','page_id','is_legacy'))
        if len(rows) != 1:
            raise ValueError('Exact migrated system route required; preserved')
        row = rows[0]
        if row != {'id':row['id'], 'target':'/manage/', 'kind':'system', 'page_id':None, 'is_legacy':False}:
            raise ValueError('Migrated system route changed; preserved')
        ids = [str(row['id'])]
        if system_ids is not None and ids != system_ids:
            raise ValueError('Migrated system route identity changed; preserved')
        return ids
    if request['kind'] == 'seed':
        from accounts.services import bootstrap_owner, create_employee, lock_auth
        from page_versions import services as V, schema as S
        with transaction.atomic():
            lock_content('default')
            lock_auth()
            system_ids = system_route()
            if Route.objects.exclude(pk__in=system_ids).exists():
                raise ValueError('Foreign route at seed; preserved')
            if any(model.objects.exists() for model in [User, Page, PageRevision,
                    PageContentState, AuthSession, Session, OwnerDraft, RestoreStage, VersionBasePin,
                    Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome] + forbidden):
                raise ValueError('Nonempty exclusive fixture; preserved')
            shared_baseline = shared_hash()
            passwords = {name: secrets.token_hex(48) for name in ('owner', 'employee', 'priceOnly')}
            owner = bootstrap_owner(passwords['owner'])
            employee = create_employee(actor=owner, username='editor-assigned', password=passwords['employee'])
            other = create_employee(actor=owner, username='editor-price-only', password=passwords['priceOnly'])
            users = [owner, employee, other]
            for user in users:
                user.first_name = run_id
                user.save(update_fields=['first_name'])
            pages = [Page.objects.create(kind=Page.Kind.ARTICLE,
                     name='NH TEST ' + run_id + ' ' + suffix) for suffix in ('A', 'B')]
            routes = [Route.objects.create(page=page, kind=Route.Kind.PRIMARY,
                      target='/normal-editor-fixture/' + run_id + '/' + suffix + '/')
                      for page, suffix in zip(pages, ('a', 'b'))]
            PageGrant.objects.create(user=employee, page=pages[0], intro_text=True, main_text=True)
            PageGrant.objects.create(user=other, page=pages[0], price=True)
        current = []
        for index, page in enumerate(pages):
            result = V.initialize(actor=owner, page_id=page.pk,
                snapshot=S.snapshot_v1(page.kind, intro_text='<p>INTRO</p>',
                    main_text='<p>NH HISTORICAL SOURCE</p>' if index == 0 else '<p>NH PAGE B</p>',
                    h1='Protected fixture heading', title='Protected fixture title'),
                expected_generation=1, operation_id=uuid4())
            current.append(result['result_id'])
        V.commit_owner(actor=owner, page_id=pages[0].pk, base_revision=current[0],
            snapshot=S.snapshot_v1(pages[0].kind, intro_text='<p>INTRO</p>', main_text='<p>NH CURRENT SAFE</p>',
                h1='Current protected H1', title='Current protected title'), expected_generation=1, operation_id=uuid4())
        # One real READY image used only for normal shared Check; never Apply.
        from media_library.uploads import upload
        from page_editor.test_media_http import PNG
        from shared_content.policy import normalize_html
        from shared_content.storage import SharedStorage
        asset = upload(actor=owner, page_id=pages[0].pk, expected_generation=1,
            upload=SimpleUploadedFile('nh-synthetic.png', base64.b64decode(PNG), content_type='image/png'))
        if asset.status != 'ready' or asset.files.count() != 3 or asset.usages.exists():
            raise ValueError('Normal READY fixture failed')
        image = '<img data-es-shared-asset="%s" alt="Synthetic brand">' % asset.pk
        markup = '<footer class="es-footer"><div class="es-footer-left">' + \
            '<a class="es-brand" href="/">' + image + '</a><p>NH SHARED CHECK</p></div>' + \
            '<div class="es-footer-legal"><span>Политика</span><span>Cookie</span>' + \
            '<span class="es-footer-credit">Сделано в <b>noname</b></span></div></footer>'
        markup = normalize_html(markup, 'footer')['html']
        files = list(asset.files.order_by('id').values('id', 'key', 'sha256', 'byte_size', 'kind'))
        for record in files:
            record['id'] = str(record['id'])
        if shared_hash() != shared_baseline:
            raise ValueError('Shared baseline changed during seed')
        asset_hashes = {name:hashlib.sha256((Path(settings.BASE_DIR) / 'page_editor' / 'assets' / name).read_bytes()).hexdigest()
                        for name in ('editor.bundle.js', 'editor.css', 'editor-bridge.mjs')}
        return {'runId':run_id, 'systemRouteIds':system_ids, 'userIds':[str(user.pk) for user in users],
                'pageIds':[str(page.pk) for page in pages], 'routeIds':[str(route.pk) for route in routes],
                'assetHashes':asset_hashes, 'shared':{'markup':markup},
                'sharedBaseline':shared_baseline, 'sharedInventoryStamp':SharedStorage().inventory()['inventoryStamp'],
                'asset':{'id':str(asset.pk), 'folderId':str(asset.folder_id), 'files':files},
                'currentIds':current, 'accounts':{name:{'username':user.username, 'password':passwords[name]}
                    for name,user in zip(('owner','employee','priceOnly'), users)}}

    users = [str(int(value)) for value in request['userIds']]
    pages = [str(UUID(value)) for value in request['pageIds']]
    routes = [str(UUID(value)) for value in request['routeIds']]
    system_ids = [str(UUID(value)) for value in request['systemRouteIds']]
    asset_id, folder_id = str(UUID(request['asset']['id'])), str(UUID(request['asset']['folderId']))
    if (len(set(users)) != 3 or len(set(pages)) != 2 or len(set(routes)) != 2
            or len(system_ids) != 1 or set(system_ids) & set(routes)):
        raise ValueError('Closed fixture manifest required')
    def validate(*, media_present=True):
        system_route(system_ids)
        if sorted(str(value) for value in User.objects.values_list('pk', flat=True)) != sorted(users):
            raise ValueError('Foreign user; preserved')
        if any(user.first_name != run_id for user in User.objects.all()):
            raise ValueError('User ownership changed; preserved')
        if sorted(str(value) for value in Page.objects.values_list('pk', flat=True)) != sorted(pages):
            raise ValueError('Foreign page; preserved')
        if any(not page.name.startswith('NH TEST ' + run_id + ' ') for page in Page.objects.all()):
            raise ValueError('Page ownership changed; preserved')
        owned_routes = Route.objects.exclude(pk__in=system_ids)
        if sorted(str(value) for value in owned_routes.values_list('pk', flat=True)) != sorted(routes):
            raise ValueError('Foreign route; preserved')
        expected_targets = {'/normal-editor-fixture/' + run_id + '/' + suffix + '/' for suffix in ('a','b')}
        if set(owned_routes.values_list('target', flat=True)) != expected_targets or owned_routes.exclude(page_id__in=pages).exists():
            raise ValueError('Route ownership changed; preserved')
        if any(model.objects.exists() for model in forbidden):
            raise ValueError('Unexpected media/draft/stage/protection; preserved')
        from shared_content.storage import SharedStorage
        if (shared_hash() != request['sharedBaseline'] or
                SharedStorage().inventory()['inventoryStamp'] != request['sharedInventoryStamp']):
            raise ValueError('Shared baseline changed; preserved')
        if media_present:
            if (list(Asset.objects.values_list('id', flat=True)) != [UUID(asset_id)] or
                    Asset.objects.get(pk=asset_id).status != 'ready' or AssetUsage.objects.exists() or
                    list(MediaFolder.objects.values_list('id', flat=True)) != [UUID(folder_id)] or
                    not PageMediaHome.objects.filter(page_id=pages[0], folder_id=folder_id).exists() or
                    PageMediaHome.objects.count() != 1):
                raise ValueError('Foreign or referenced fixture media; preserved')
            files = list(AssetFile.objects.order_by('id').values('id', 'key', 'sha256', 'byte_size', 'kind'))
            for record in files:
                record['id'] = str(record['id'])
            if files != request['asset']['files']:
                raise ValueError('Media descriptor changed; preserved')
            storage = MediaStorage()
            for record in files:
                if storage.manifest(record['key']) != {'sha256':record['sha256'], 'byte_size':record['byte_size']}:
                    raise ValueError('Media bytes changed; preserved')
        elif Asset.objects.exists() or AssetFile.objects.exists() or AssetUsage.objects.exists():
            raise ValueError('Unremoved fixture media; preserved')
        drafts = list(OwnerDraft.objects.all())
        stages = list(RestoreStage.objects.all())
        if any(str(row.page_id) not in pages or str(row.author_id) not in users for row in drafts):
            raise ValueError('Foreign draft; preserved')
        revisions = {str(row.pk): str(row.page_id) for row in PageRevision.objects.all()}
        if any(revisions.get(str(row.base_revision_id)) != str(row.page_id) for row in drafts):
            raise ValueError('Draft base ownership mismatch; preserved')
        if any(str(row.page_id) not in pages or str(row.actor_id) not in users
               or any((revisions.get(str(value)) != str(row.page_id) if row.status == 'held'
                       else str(value) in revisions and revisions[str(value)] != str(row.page_id))
                      for value in (row.base_revision_id, row.source_revision_id)) for row in stages):
            raise ValueError('Stage ownership mismatch; preserved')
        holders = {('owner_draft', str(row.pk)): {str(row.base_revision_id)} for row in drafts}
        holders.update({('restore_stage', str(row.pk)): {str(row.base_revision_id), str(row.source_revision_id)}
                        for row in stages if row.status == 'held'})
        actual_pins = {}
        for pin in VersionBasePin.objects.all():
            key = (pin.holder_kind, str(pin.holder_id))
            if key not in holders or str(pin.revision_id) not in holders[key]:
                raise ValueError('Unowned pin; preserved')
            actual_pins.setdefault(key, set()).add(str(pin.revision_id))
        if actual_pins != holders:
            raise ValueError('Pin set mismatch; preserved')
        if (PageRevision.objects.exclude(page_id__in=pages).exists() or
                PageRevision.objects.exclude(author_id__in=users).exists() or
                PageContentState.objects.exclude(page_id__in=pages).exists()):
            raise ValueError('Foreign revision/state; preserved')
        if (PageGrant.objects.exclude(user_id__in=users).exists() or
                PageGrant.objects.exclude(page_id__in=pages).exists() or
                AuthSession.objects.exclude(user_id__in=users).exists()):
            raise ValueError('Foreign grant/session; preserved')
        if OperationReceipt.objects.filter(page_id__in=pages).exclude(actor_id__in=users).exists():
            raise ValueError('Foreign operation actor; preserved')
        # Historical permanent receipts with no live Page are intentionally kept.
        if OperationReceipt.objects.filter(page_id__in=Page.objects.values('pk')).exclude(page_id__in=pages).exists():
            raise ValueError('Foreign live operation; preserved')
        for session in Session.objects.all():
            if str(session.get_decoded().get('_auth_user_id')) not in users:
                raise ValueError('Unowned Django session; preserved')

    def passive():
        # Read-only Linux/PG evidence. Never acquire flock or domain locks.
        import stat
        from pathlib import Path
        from django.db import connection
        slot = Path('/tmp/estakada-editor.slot')
        info = None
        try:
            info = slot.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10001
                    or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError('PASSIVE_SLOT_TYPE')
        except FileNotFoundError:
            pass
        with open('/proc/locks', 'r', encoding='ascii') as stream:
            lines = stream.read(65537)
        if len(lines) > 65536:
            raise ValueError('PASSIVE_LOCK_BOUND')
        held = []
        if info is not None:
            for line in lines.splitlines():
                fields = line.split()
                if len(fields) < 8 or fields[1] != 'FLOCK':
                    continue
                device = fields[5].split(':')
                if len(device) == 3 and (int(device[0], 16), int(device[1], 16), int(device[2])) == (
                        os.major(info.st_dev), os.minor(info.st_dev), info.st_ino):
                    if fields[2:4] != ['ADVISORY', 'WRITE']:
                        raise ValueError('PASSIVE_SLOT_LOCK_TYPE')
                    held.append(int(fields[4]))
        processes = []
        pids = [name for name in os.listdir('/proc') if name.isdecimal()]
        if len(pids) > 512:
            raise ValueError('PASSIVE_PROCESS_BOUND')
        children = 0
        for pid in pids:
            path = Path('/proc') / pid
            try:
                if int(pid) == os.getpid() or path.stat().st_uid != 10001:
                    continue
                cmd = (path / 'cmdline').read_bytes()
                if len(cmd) > 16384:
                    raise ValueError('PASSIVE_COMMAND_BOUND')
                args = cmd.split(b'\0')
                if b'manage.py' in args and b'runserver' in args:
                    processes.append({'pid': int(pid), 'fdCount': len(list((path / 'fd').iterdir()))})
                elif b'editor_runtime.child_bootstrap' in args or any(item.endswith(b'/child_bootstrap.py') for item in args):
                    children += 1
            except (FileNotFoundError, ProcessLookupError):
                continue
        if len(processes) != 1 or any(pid != processes[0]['pid'] for pid in held):
            raise ValueError('PASSIVE_SERVER_IDENTITY')
        with connection.cursor() as cursor:
            cursor.execute("""SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid
                WHERE a.datname=current_database() AND a.usename=current_user
                AND l.pid<>pg_backend_pid() AND l.locktype='advisory' AND l.granted""")
            locks = cursor.fetchone()[0]
            cursor.execute("""SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()
                AND usename=current_user AND pid<>pg_backend_pid() AND state='active'""")
            active = cursor.fetchone()[0]
        return {'slotExists': info is not None, 'slotHeld': bool(held), 'holderCount': len(held),
                'server': processes[0], 'childCount': children, 'grantedAdvisoryLocks': locks,
                'otherActiveConnections': active, 'passive': True}

    validate()
    if request['kind'] == 'passive':
        return passive()
    if request['kind'] == 'observe':
        rows = []
        for page in Page.objects.order_by('id'):
            state = PageContentState.objects.get(page=page)
            revision = PageRevision.objects.get(pk=state.current_revision_id)
            history = PageRevision.objects.filter(page=page).order_by('sequence')
            rows.append({'id':str(page.pk), 'name':page.name, 'currentId':str(revision.pk),
                'payloadHash':revision.payload_hash, 'payload':revision.payload,
                'history':[{'id':str(row.pk), 'kind':row.kind, 'authorId':str(row.author_id),
                    'sourceId':str(row.source_revision_id) if row.source_revision_id else None,
                    'payloadHash':row.payload_hash} for row in history]})
        receipts = OperationReceipt.objects.filter(page_id__in=pages).order_by('id')
        events = AuditEvent.objects.filter(actor_id__in=users, code__startswith='VERSION_')
        drafts = [{'id': str(row.pk), 'pageId': str(row.page_id), 'revision': row.revision,
                   'baseRevisionId': str(row.base_revision_id), 'payload': row.payload,
                   'payloadHash': row.payload_hash} for row in OwnerDraft.objects.order_by('id')]
        stages = [{'id': str(row.pk), 'pageId': str(row.page_id), 'actorId': str(row.actor_id),
                   'sourceId': str(row.source_revision_id), 'baseRevisionId': str(row.base_revision_id),
                   'status': row.status} for row in RestoreStage.objects.order_by('id')]
        pins = [{'holderKind': row.holder_kind, 'holderId': str(row.holder_id),
                 'revisionId': str(row.revision_id)} for row in VersionBasePin.objects.order_by('id')]
        receipt_rows=[{'id':str(row.pk), 'pageId':str(row.page_id), 'actorId':str(row.actor_id),
                    'action':row.action, 'resultId':str(row.result_id) if row.result_id else None,
                    'editorFingerprint':row.editor_request_fingerprint} for row in receipts]
        return {'runId':run_id, 'systemRouteIds':system_ids, 'pages':rows,
                'drafts': drafts, 'stages': stages, 'pins': pins,
                'receipts':receipt_rows,
                'versionAuditCount':events.count(), 'sharedBaselinePreserved':True, 'assetRefs':AssetUsage.objects.count(),
                'assetFiles':request['asset']['files'],
                'domainHash':digest({'pages': rows, 'drafts': drafts, 'stages': stages, 'pins': pins, 'receipts': receipt_rows}),
                'secretsExcluded':True}
    # Product cleanup verifies exact manifests and refuses any new reference.
    # It runs outside the Page teardown transaction; partial cleanup is reported.
    from media_library.services import prepare_cleanup, confirm_cleanup
    owner = User.objects.get(pk=users[0], username='nesadmin', first_name=run_id)
    generation = UserProfile.objects.get(user=owner).generation
    prepared = prepare_cleanup(actor=owner, asset_ids=[asset_id], expected_generation=generation)
    cleaned = confirm_cleanup(actor=owner, confirmation=prepared['confirmation'], expected_generation=generation)
    if len(cleaned) != 1 or cleaned[0]['state'] != 'deleted':
        raise ValueError('Fixture media cleanup incomplete; preserved')
    from accounts.services import lock_auth
    with transaction.atomic():
        lock_content('default')
        lock_auth()
        validate(media_present=False)
        revision_ids = list(PageRevision.objects.filter(page_id__in=pages).values_list('pk', flat=True))
        draft_ids = list(OwnerDraft.objects.filter(page_id__in=pages).values_list('pk', flat=True))
        stage_ids = list(RestoreStage.objects.filter(page_id__in=pages).values_list('pk', flat=True))
        raw(VersionBasePin).filter(holder_kind='owner_draft', holder_id__in=draft_ids).delete()
        raw(VersionBasePin).filter(holder_kind='restore_stage', holder_id__in=stage_ids).delete()
        raw(OwnerDraft).filter(pk__in=draft_ids).delete()
        raw(RestoreStage).filter(pk__in=stage_ids).delete()
        raw(PageContentState).filter(page_id__in=pages).delete()
        raw(RevisionMetadata).filter(revision_id__in=revision_ids).delete()
        raw(PageRevision).filter(pk__in=revision_ids).delete()
        raw(PageMediaHome).filter(page_id=pages[0], folder_id=folder_id).delete()
        raw(MediaFolder).filter(pk=folder_id).delete()
        session_keys = list(Session.objects.values_list('pk', flat=True))
        AuthSession.objects.filter(user_id__in=users).delete()
        Session.objects.filter(pk__in=session_keys).delete()
        PageGrant.objects.filter(user_id__in=users, page_id__in=pages).delete()
        raw(Route).filter(pk__in=routes).delete()
        raw(Page).filter(pk__in=pages).delete()
        UserProfile.objects.filter(user_id__in=users).delete()
        User.objects.filter(pk__in=users).delete()
        system_route(system_ids)
    return {'closed':True, 'remainingUsers':User.objects.count(), 'remainingPages':Page.objects.count(),
            'remainingRoutes':Route.objects.count(), 'remainingVersions':PageRevision.objects.count(),
            'remainingDrafts':OwnerDraft.objects.count(), 'remainingStages':RestoreStage.objects.count(),
            'remainingPins':VersionBasePin.objects.count(),
            'remainingAssets':Asset.objects.count(), 'sharedBaselinePreserved':shared_hash() == request['sharedBaseline'],
            'systemRouteIds':system_ids, 'systemRoutePreserved':True,
            'versionIdentityTombstones':VersionIdentityReservation.objects.count(),
            'mediaIdentityTombstones':MediaIdentityReservation.objects.count(),
            'permanentOperationReceipts':OperationReceipt.objects.count(),
            'appendOnlyAuditEvents':AuditEvent.objects.count(), 'permanentLedgersPreserved':True}


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin)), default=str))
    except Exception as error:
        reasons = {'Foreign draft; preserved': 'FIXTURE_FOREIGN_DRAFT',
            'Draft base ownership mismatch; preserved': 'FIXTURE_DRAFT_BASE',
            'Stage ownership mismatch; preserved': 'FIXTURE_STAGE_OWNER',
            'Unowned pin; preserved': 'FIXTURE_FOREIGN_PIN',
            'Pin set mismatch; preserved': 'FIXTURE_PIN_SET',
            'Unexpected media/draft/stage/protection; preserved': 'FIXTURE_UNEXPECTED_DATA',
            'Foreign revision/state; preserved': 'FIXTURE_FOREIGN_VERSION',
            'Foreign grant/session; preserved': 'FIXTURE_FOREIGN_SESSION'}
        print(json.dumps({'errorClass':type(error).__name__,
                          'code':reasons.get(str(error), 'FIXTURE_OPERATION_FAILED')}), file=sys.stderr)
        sys.exit(1)
