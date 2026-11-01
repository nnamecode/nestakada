"""Exclusive E3 run fixture; embedded usages require actual payload bindings."""
import json
import os
import secrets
import sys
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
    from django.db import models, transaction
    from accounts.models import AuthSession, UserProfile, PageGrant
    from content.models import Page, Route, lock_content
    from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome
    from media_library.storage import MediaStorage, MediaParentUnavailable
    from page_versions.models import (PageRevision, PageContentState, RevisionMetadata,
        RevisionProtection, OwnerDraft, RestoreStage, VersionBasePin, OperationReceipt)
    from page_versions.models import IdentityReservation as VersionIdentityReservation
    from media_library.models import IdentityReservation as MediaIdentityReservation
    from page_versions.schema import digest, asset_slots, validate as validate_payload
    from audit.models import AuditEvent
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise ValueError('Wrong database')
    if type(request) is not dict or request.get('kind') not in ('seed', 'observe', 'close'):
        raise ValueError('Closed fixture operation required')
    run_id = str(UUID(request['runId']))
    User = get_user_model()
    raw = lambda model: models.QuerySet(model=model, using='default')
    forbidden = [Asset, AssetUsage, MediaFolder, PageMediaHome, RevisionProtection]
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
                    PageContentState, AuthSession, Session, OwnerDraft, RestoreStage, VersionBasePin] + forbidden):
                raise ValueError('Nonempty exclusive fixture; preserved')
            passwords = {name: secrets.token_hex(48) for name in ('owner', 'employee', 'other')}
            owner = bootstrap_owner(passwords['owner'])
            employee = create_employee(actor=owner, username='editor-assigned', password=passwords['employee'])
            other = create_employee(actor=owner, username='editor-other', password=passwords['other'])
            users = [owner, employee, other]
            for user in users:
                user.first_name = run_id
                user.save(update_fields=['first_name'])
            pages = [Page.objects.create(kind=Page.Kind.ARTICLE,
                     name='EDITOR TEST ' + run_id + ' ' + suffix) for suffix in ('A', 'B')]
            routes = [Route.objects.create(page=page, kind=Route.Kind.PRIMARY,
                      target='/editor-fixture/' + run_id + '/' + suffix + '/')
                      for page, suffix in zip(pages, ('a', 'b'))]
            PageGrant.objects.create(user=employee, page=pages[0], intro_text=True, main_text=True)
            PageGrant.objects.create(user=other, page=pages[1], main_text=True)
        current = []
        for index, page in enumerate(pages):
            result = V.initialize(actor=owner, page_id=page.pk,
                snapshot=S.snapshot_v1(page.kind, intro_text='<p>INTRO</p>',
                    main_text='<p>EDITOR ' + ('A' if index == 0 else 'B') + '</p>',
                    h1='Protected fixture heading', title='Protected fixture title'),
                expected_generation=1, operation_id=uuid4())
            current.append(result['result_id'])
        return {'runId':run_id, 'systemRouteIds':system_ids, 'userIds':[str(user.pk) for user in users],
                'pageIds':[str(page.pk) for page in pages], 'routeIds':[str(route.pk) for route in routes],
                'currentIds':current, 'accounts':{name:{'username':user.username, 'password':passwords[name]}
                    for name,user in zip(('owner','employee','other'), users)}}

    users = [str(int(value)) for value in request['userIds']]
    pages = [str(UUID(value)) for value in request['pageIds']]
    routes = [str(UUID(value)) for value in request['routeIds']]
    system_ids = [str(UUID(value)) for value in request['systemRouteIds']]
    if (len(set(users)) != 3 or len(set(pages)) != 2 or len(set(routes)) != 2
            or len(system_ids) != 1 or set(system_ids) & set(routes)):
        raise ValueError('Closed fixture manifest required')
    def validate():
        system_route(system_ids)
        if sorted(str(value) for value in User.objects.values_list('pk', flat=True)) != sorted(users):
            raise ValueError('Foreign user; preserved')
        if any(user.first_name != run_id for user in User.objects.all()):
            raise ValueError('User ownership changed; preserved')
        if sorted(str(value) for value in Page.objects.values_list('pk', flat=True)) != sorted(pages):
            raise ValueError('Foreign page; preserved')
        if any(not page.name.startswith('EDITOR TEST ' + run_id + ' ') for page in Page.objects.all()):
            raise ValueError('Page ownership changed; preserved')
        owned_routes = Route.objects.exclude(pk__in=system_ids)
        if sorted(str(value) for value in owned_routes.values_list('pk', flat=True)) != sorted(routes):
            raise ValueError('Foreign route; preserved')
        expected_targets = {'/editor-fixture/' + run_id + '/' + suffix + '/' for suffix in ('a','b')}
        if set(owned_routes.values_list('target', flat=True)) != expected_targets or owned_routes.exclude(page_id__in=pages).exists():
            raise ValueError('Route ownership changed; preserved')
        homes=list(PageMediaHome.objects.filter(page_id__in=pages).select_related('folder'))
        folder_ids=[home.folder_id for home in homes]
        if (PageMediaHome.objects.exclude(page_id__in=pages).exists() or
                any(home.folder.path != 'pages/'+str(home.page_id) for home in homes) or
                MediaFolder.objects.exclude(pk__in=folder_ids).exists() or
                Asset.objects.exclude(folder_id__in=folder_ids).exists()):
            raise ValueError('Foreign media; preserved')
        own_assets=Asset.objects.filter(folder_id__in=folder_ids)
        if own_assets.exclude(status='ready').exists() or own_assets.filter(is_legacy=True).exists():
            raise ValueError('Incomplete or legacy media; preserved')
        if AssetUsage.objects.exclude(asset__in=own_assets).exists():raise ValueError('Foreign media usage; preserved')
        for asset in own_assets.select_related('folder'):
            if asset.provenance!='owner-upload/webp82-v1' or asset.source_url:
                raise ValueError('Foreign media provenance; preserved')
            expected={'private-source':'private/sources/'+str(asset.pk)+'/original.bin',
                      'main':'img/'+asset.folder.path+'/'+str(asset.pk)+'/main.webp',
                      'preview':'img/'+asset.folder.path+'/'+str(asset.pk)+'/preview.webp'}
            if {file.kind:file.key for file in asset.files.all()}!=expected or asset.files.count()!=3:
                raise ValueError('Foreign media file; preserved')
        revision_ids=list(PageRevision.objects.filter(page_id__in=pages).values_list('pk',flat=True))
        draft_ids=list(OwnerDraft.objects.filter(page_id__in=pages).values_list('pk',flat=True))
        if RevisionProtection.objects.exclude(revision_id__in=revision_ids).exists():
            raise ValueError('Foreign protection; preserved')
        allowed={'current_page':set(pages),'ordinary_version':set(map(str,revision_ids)),
                 'stable_version':set(map(str,revision_ids)),'draft':set(map(str,draft_ids))}
        for use in AssetUsage.objects.filter(asset__in=own_assets):
            if use.kind not in allowed or str(use.consumer_id) not in allowed[use.kind]:
                raise ValueError('Foreign media usage; preserved')
            if use.kind=='current_page':
                state=PageContentState.objects.get(page_id=use.consumer_id)
                consumer=PageRevision.objects.get(pk=state.current_revision_id,page_id=use.consumer_id)
            elif use.kind=='draft':consumer=OwnerDraft.objects.get(pk=use.consumer_id,page_id__in=pages)
            else:
                consumer=PageRevision.objects.get(pk=use.consumer_id,page_id__in=pages)
                stable=RevisionProtection.objects.filter(revision_id=consumer.pk).exists()
                if stable!=(use.kind=='stable_version'):raise ValueError('Usage protection mismatch; preserved')
            payload=validate_payload(consumer.payload)
            if asset_slots(payload).get(use.slot)!=str(use.asset_id):
                raise ValueError('Usage payload mismatch; preserved')
            if use.slot not in ('main_image','preview_image'):
                if not use.slot.startswith('embedded:'):raise ValueError('Unknown usage slot; preserved')
                image_id=use.slot[len('embedded:'):]
                if str(UUID(image_id))!=image_id:raise ValueError('Invalid embedded usage slot; preserved')
                images={image['id']:image['asset_id'] for image in payload['embedded_images']}
                linked=any((node['kind']=='image' and node['image_id']==image_id) or
                    (node['kind']=='text' and any(marker['reference_id']==image_id for marker in node['protected_nodes']))
                    for node in payload['layout'])
                if images.get(image_id)!=str(use.asset_id) or not linked:
                    raise ValueError('Embedded layout mismatch; preserved')
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
    validate()
    homes=list(PageMediaHome.objects.filter(page_id__in=pages).select_related('folder'))
    folder_ids=[home.folder_id for home in homes]
    asset_ids=list(Asset.objects.filter(folder_id__in=folder_ids).values_list('pk',flat=True))
    if request['kind']=='close':
        if (sorted(map(str,asset_ids))!=sorted(request.get('assetIds',[])) or
                sorted(map(str,folder_ids))!=sorted(request.get('folderIds',[]))):
            raise ValueError('Observed media manifest mismatch; preserved')
    storage=MediaStorage()
    def physical(key):
        try:return storage.manifest(key)
        except FileNotFoundError:return None
        except MediaParentUnavailable:return {'unavailable':True}
    def asset_rows():
        return [{'id':str(asset.pk),'status':asset.status,'folder':asset.folder.path,
                 'files':[{'id':str(file.pk),'kind':file.kind,'key':file.key,'sha256':file.sha256,
                           'byte_size':file.byte_size,'physical':physical(file.key)} for file in asset.files.order_by('kind')],
                 'usages':[{'kind':use.kind,'consumerId':str(use.consumer_id),'slot':use.slot}
                            for use in asset.usages.order_by('kind','consumer_id','slot')]}
                for asset in Asset.objects.filter(pk__in=asset_ids).select_related('folder').order_by('id')]
    known=request.get('knownFiles',[])
    if type(known) is not list or len(known)>60:raise ValueError('Invalid known files')
    from media_library.paths import storage_key
    for row in known:
        if type(row) is not dict or set(row)!={'assetId','key'}:raise ValueError('Invalid known file')
        asset_id=str(UUID(row['assetId']));key=storage_key(row['key'])
        if not (key.startswith('private/sources/'+asset_id+'/') or any(
                key.startswith('img/pages/'+page+'/'+asset_id+'/') for page in pages)):
            raise ValueError('Known file ownership mismatch')
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
        return {'runId':run_id, 'systemRouteIds':system_ids, 'pages':rows,
                'drafts': drafts, 'stages': stages, 'pins': pins,
                'receipts':[{'id':str(row.pk), 'pageId':str(row.page_id), 'actorId':str(row.actor_id),
                    'action':row.action, 'resultId':str(row.result_id) if row.result_id else None,
                    'editorFingerprint':row.editor_request_fingerprint} for row in receipts],
                'versionAuditCount':events.count(), 'assets':asset_rows(),'folderIds':list(map(str,folder_ids)),
                'domainHash':digest({'pages': rows, 'drafts': drafts, 'stages': stages, 'pins': pins,'assets':asset_rows()}),
                'secretsExcluded':True}
    from accounts.services import lock_auth
    with transaction.atomic():
        lock_content('default')
        lock_auth()
        validate()
        revision_ids = list(PageRevision.objects.filter(page_id__in=pages).values_list('pk', flat=True))
        draft_ids = list(OwnerDraft.objects.filter(page_id__in=pages).values_list('pk', flat=True))
        stage_ids = list(RestoreStage.objects.filter(page_id__in=pages).values_list('pk', flat=True))
        raw(VersionBasePin).filter(holder_kind='owner_draft', holder_id__in=draft_ids).delete()
        raw(VersionBasePin).filter(holder_kind='restore_stage', holder_id__in=stage_ids).delete()
        raw(OwnerDraft).filter(pk__in=draft_ids).delete()
        raw(RestoreStage).filter(pk__in=stage_ids).delete()
        raw(PageContentState).filter(page_id__in=pages).delete()
        raw(AssetUsage).filter(asset_id__in=asset_ids).delete()
        raw(RevisionProtection).filter(revision_id__in=revision_ids).delete()
        raw(RevisionMetadata).filter(revision_id__in=revision_ids).delete()
        raw(PageRevision).filter(pk__in=revision_ids).delete()
    # Only previously validated owned IDs; physical IO outside domain locks.
    from media_library.services import prepare_cleanup,confirm_cleanup
    owner=User.objects.get(username='nesadmin',first_name=run_id)
    files=[{'assetId':row['id'],'key':part['key']} for row in asset_rows() for part in row['files']]
    for asset_id in asset_ids:
        prepared=prepare_cleanup(actor=owner,asset_ids=[asset_id],expected_generation=1,storage=storage)
        deleted=confirm_cleanup(actor=owner,confirmation=prepared['confirmation'],expected_generation=1,storage=storage)
        if any(row['state']!='deleted' for row in deleted):raise ValueError('Physical cleanup incomplete')
    physical_files=[{'assetId':row['assetId'],'key':row['key'],'physical':physical(row['key'])} for row in files+known]
    if any(row['physical'] is not None for row in physical_files):raise ValueError('Physical files remain or unavailable')
    with transaction.atomic():
        lock_content('default')
        lock_auth()
        validate()
        raw(PageMediaHome).filter(page_id__in=pages,folder_id__in=folder_ids).delete()
        raw(MediaFolder).filter(pk__in=folder_ids).delete()
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
            'remainingAssets':Asset.objects.count(),'remainingFiles':AssetFile.objects.count(),
            'physicalFiles':physical_files,
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
