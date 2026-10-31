"""Exclusive DEV05 seed/observer/close. HTTP actions are never replaced by this fixture."""
import base64
import hashlib
import json
import os
import secrets
import sys
from uuid import UUID, uuid4


def execute(request):
    if os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http':
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
    from page_versions.models import (PageRevision, PageContentState, RevisionMetadata, RevisionProtection,
                                      OwnerDraft, RestoreStage, VersionBasePin, OperationReceipt)
    from page_versions.schema import digest
    from audit.models import AuditEvent
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise ValueError('Wrong database')
    run_id = str(UUID(request['runId']))
    User = get_user_model()
    raw = lambda model: models.QuerySet(model=model, using='default')
    if request['kind'] == 'seed':
        # Trusted producers are imported only for mutations, never by the observer.
        from accounts.services import bootstrap_owner, create_employee
        from media_library.uploads import upload
        from django.core.files.uploadedfile import SimpleUploadedFile
        from page_versions import services as versions, schema
        with transaction.atomic():
            lock_content('default')
            if any(model.objects.exists() for model in [User, Page, Asset, MediaFolder, PageRevision, PageContentState, OwnerDraft, RestoreStage]):
                raise ValueError('Nonempty exclusive fixture; nothing reset')
            passwords = {key: secrets.token_hex(48) for key in ['owner', 'employee', 'other']}
            owner = bootstrap_owner(passwords['owner'])
            employee = create_employee(actor=owner, username='version-assigned', password=passwords['employee'])
            other = create_employee(actor=owner, username='version-other', password=passwords['other'])
            users = [owner, employee, other]
            for user in users:
                user.first_name = run_id
                user.save(update_fields=['first_name'])
            pages = [Page.objects.create(kind=Page.Kind.ARTICLE, name='VERSION TEST '+run_id+' '+name) for name in ['A', 'B']]
            PageGrant.objects.create(user=employee, page=pages[0], intro_text=True, main_text=True)
            PageGrant.objects.create(user=other, page=pages[1], main_text=True)
        # Decoder and filesystem preflight must run in autocommit, outside global DB locks.
        images = request.get('images')
        if type(images) is not list or [item.get('name') for item in images] != ['valid.jpg', 'valid.png', 'valid.webp']:
            raise ValueError('Closed synthetic corpus required')
        assets = []
        for index, item in enumerate(images):
            data = base64.b64decode(item['base64'], validate=True)
            if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('Synthetic bytes changed')
            asset = upload(actor=owner, page_id=pages[0 if index < 2 else 1].pk,
                           upload=SimpleUploadedFile(item['name'], data, content_type=item['mime']), expected_generation=1)
            assets.append(asset)
        def image(asset):
            return {'asset_id':str(asset.pk), 'alt':'Synthetic historical image', 'alignment':'center', 'width_px':None, 'height_px':None}
        text_canary = '<script>globalThis.__version_probe_executed=true</script> VERSION DATA '+run_id
        draft_canary = 'PRIVATE OWNER DRAFT '+run_id
        layout = [{'id':str(uuid4()), 'kind':'text', 'field':'main_text', 'protected_nodes':[]}]
        def snapshot(number, asset=assets[0], main=None):
            return schema.snapshot_v1(pages[0].kind, intro_text='INTRO '+str(number),
                main_text=text_canary+' / '+str(number) if main is None else main,
                h1='PROTECTED H1 '+str(number), title='PROTECTED TITLE '+str(number),
                description='Protected description', main_image=image(asset), layout=layout)
        current = versions.initialize(actor=owner, page_id=pages[0].pk, snapshot=snapshot(1),
                                      expected_generation=1, operation_id=uuid4())['result_id']
        stable_ids = []
        for number in range(1, 13):
            if number > 1:
                if number == 11:
                    outcome = versions.commit_employee(actor=employee, page_id=pages[0].pk, base_revision=current,
                        patch=schema.TextPricePatch(main_text=text_canary+' / employee11'), expected_generation=1, operation_id=uuid4())
                else:
                    outcome = versions.commit_owner(actor=owner, page_id=pages[0].pk, base_revision=current,
                        snapshot=snapshot(number), expected_generation=1, operation_id=uuid4())
                current = outcome['result_id']
            if number in [1, 2]:
                view = versions.view_version(actor=owner, page_id=pages[0].pk, version_id=current, expected_generation=1)
                versions.set_stable(actor=owner, page_id=pages[0].pk, version_id=current, view_receipt=view['view_receipt'],
                                    expected_generation=1, operation_id=uuid4())
                stable_ids.append(current)
            if number == 10:
                draft_result = versions.save_owner_draft(actor=owner, page_id=pages[0].pk, base_revision=current,
                    snapshot=snapshot(number, assets[1], draft_canary), expected_generation=1, operation_id=uuid4())
                pinned_base = current
        versions.initialize(actor=owner, page_id=pages[1].pk,
            snapshot=schema.snapshot_v1(pages[1].kind, main_text='OTHER PAGE '+run_id, h1='Other page'),
            expected_generation=1, operation_id=uuid4())
        ordinary = PageRevision.objects.filter(page=pages[0], stable_protection__isnull=True).count()
        if ordinary != 10 or RevisionProtection.objects.filter(revision__page=pages[0]).count() != 2:
            raise ValueError('Seed corpus counts differ from independent oracle')
        return {'runId':run_id, 'userIds':[str(user.pk) for user in users], 'pageIds':[str(page.pk) for page in pages],
                'assetIds':[str(asset.pk) for asset in assets], 'draftId':draft_result['result_id'],
                'currentId':current, 'stableIds':stable_ids, 'pinnedBaseId':pinned_base,
                'textCanary':text_canary, 'draftCanary':draft_canary,
                'accounts':{key:{'username':user.username, 'password':passwords[key]} for key,user in zip(['owner','employee','other'],users)}}

    owned_users = [str(value) for value in request['userIds']]
    owned_pages = [str(UUID(value)) for value in request['pageIds']]
    owned_assets = [str(UUID(value)) for value in request['assetIds']]
    if sorted(str(value) for value in User.objects.values_list('pk', flat=True)) != sorted(owned_users):
        raise ValueError('Foreign user; fixture preserved')
    if any(user.first_name != run_id for user in User.objects.all()):
        raise ValueError('Fixture identity changed')
    if sorted(str(value) for value in Page.objects.values_list('pk', flat=True)) != sorted(owned_pages):
        raise ValueError('Foreign page; fixture preserved')
    if any(not page.name.startswith('VERSION TEST '+run_id+' ') for page in Page.objects.all()):
        raise ValueError('Page canary changed')
    if sorted(str(value) for value in Asset.objects.values_list('pk', flat=True)) != sorted(owned_assets):
        raise ValueError('Foreign asset; fixture preserved')
    homes = list(PageMediaHome.objects.select_related('folder').filter(page_id__in=owned_pages))
    folder_ids = [home.folder_id for home in homes]
    if set(MediaFolder.objects.values_list('pk', flat=True)) != set(folder_ids) or Asset.objects.exclude(folder_id__in=folder_ids).exists():
        raise ValueError('Foreign folder; fixture preserved')
    if PageRevision.objects.exclude(page_id__in=owned_pages).exists() or PageRevision.objects.exclude(author_id__in=owned_users).exists():
        raise ValueError('Foreign revision; fixture preserved')
    if OwnerDraft.objects.exclude(pk=UUID(request['draftId']), page_id__in=owned_pages, author_id__in=owned_users).exists():
        raise ValueError('Foreign draft; fixture preserved')
    if any(draft.payload.get('main_text') != 'PRIVATE OWNER DRAFT '+run_id for draft in OwnerDraft.objects.all()):
        raise ValueError('Draft canary changed')
    if PageContentState.objects.exclude(page_id__in=owned_pages).exists() or RestoreStage.objects.exclude(page_id__in=owned_pages, actor_id__in=owned_users).exists():
        raise ValueError('Foreign state/stage; fixture preserved')
    if OperationReceipt.objects.filter(page_id__in=owned_pages).exclude(actor_id__in=owned_users).exists():
        raise ValueError('Foreign operation; fixture preserved')
    if RevisionProtection.objects.exclude(marked_by_id__in=owned_users).exists():
        raise ValueError('Foreign protection actor; fixture preserved')
    revisions = {row.pk for row in PageRevision.objects.all()}
    drafts = {row.pk for row in OwnerDraft.objects.all()}
    stages = {row.pk for row in RestoreStage.objects.all()}
    for pin in VersionBasePin.objects.all():
        holders = drafts if pin.holder_kind == 'owner_draft' else stages if pin.holder_kind == 'restore_stage' else set()
        if pin.revision_id not in revisions or pin.holder_id not in holders:
            raise ValueError('Foreign pin; fixture preserved')
    for usage in AssetUsage.objects.all():
        consumers = {UUID(p) for p in owned_pages} if usage.kind == 'current_page' else revisions if usage.kind in ['ordinary_version','stable_version'] else drafts if usage.kind == 'draft' else set()
        if str(usage.asset_id) not in owned_assets or usage.consumer_id not in consumers:
            raise ValueError('Foreign consumer; fixture preserved')
    storage = MediaStorage()
    def physical(key):
        try:
            return storage.manifest(key)
        except FileNotFoundError:
            return None
        except MediaParentUnavailable:
            return {'unavailable':True}
    if request['kind'] == 'observe':
        page_rows = []
        for page in Page.objects.order_by('id'):
            state = PageContentState.objects.get(page=page)
            records = []
            for row in PageRevision.objects.filter(page=page).select_related('metadata').order_by('created_at','sequence','id'):
                meta = row.metadata
                records.append({'id':str(row.pk),'kind':row.kind,'createdAt':row.created_at.isoformat(),'sequence':row.sequence,
                    'authorId':str(row.author_id),'sourceRevisionId':str(row.source_revision_id) if row.source_revision_id else None,
                    'payloadHash':row.payload_hash, 'fieldHashes':{name:digest(value) for name,value in row.payload.items()},
                    'stable':RevisionProtection.objects.filter(revision=row).exists(),
                    'metadata':{'generation':meta.generation,'name':meta.name,'comment':meta.comment,'manualDate':meta.manual_date.isoformat() if meta.manual_date else None}})
            page_rows.append({'id':str(page.pk),'name':page.name,'parentId':str(page.parent_id) if page.parent_id else None,
                'position':page.position,'kind':page.kind,'isPublished':page.is_published,
                'routes':list(Route.objects.filter(page=page).values_list('target',flat=True)),
                'currentId':str(state.current_revision_id),'versions':records})
        asset_rows = [{'id':str(asset.pk),'status':asset.status,'folderId':str(asset.folder_id),
            'files':[{'id':str(file.pk),'kind':file.kind,'key':file.key,'physical':physical(file.key)} for file in asset.files.order_by('kind','id')],
            'usageCount':asset.usages.count()} for asset in Asset.objects.order_by('id')]
        receipts = list(OperationReceipt.objects.filter(page_id__in=owned_pages).order_by('id').values('id','action','actor_id','actor_generation','page_id','result_id','result_code'))
        events = list(AuditEvent.objects.filter(actor_id__in=owned_users,code__startswith='VERSION_').values('event_id','code','actor_id','object_ref','occurred_at'))
        forbidden = [user.password for user in User.objects.all()] + list(AuthSession.objects.filter(user_id__in=owned_users).values_list('pk',flat=True))
        raw_receipts = json.dumps(list(OperationReceipt.objects.filter(page_id__in=owned_pages).values()),default=str)
        raw_events = json.dumps(events,default=str)
        if any(value and value in raw_receipts+raw_events for value in forbidden):
            raise ValueError('Secret present in ledger/audit')
        return {'pages':page_rows,'assets':asset_rows,
            'drafts':[{'id':str(d.pk),'pageId':str(d.page_id),'baseId':str(d.base_revision_id),'revision':d.revision,'payloadHash':d.payload_hash} for d in OwnerDraft.objects.all()],
            'pins':[{'revisionId':str(p.revision_id),'holderKind':p.holder_kind,'holderId':str(p.holder_id)} for p in VersionBasePin.objects.all()],
            'stages':[{'id':str(s.pk),'pageId':str(s.page_id),'actorId':str(s.actor_id),'sourceId':str(s.source_revision_id),'baseId':str(s.base_revision_id),'status':s.status,'fields':s.fields} for s in RestoreStage.objects.all()],
            'receipts':receipts,'versionAuditCount':len(events),'secretHashesAndSessionIdsAbsent':True}
    if request['kind'] == 'close':
        from media_library.services import prepare_cleanup, confirm_cleanup
        owner = User.objects.get(username='nesadmin',first_name=run_id)
        # Bounded test teardown only, after full ownership checks. No production command/reset endpoint.
        with transaction.atomic():
            lock_content('default')
            raw(VersionBasePin).filter(revision_id__in=revisions).delete()
            raw(RestoreStage).filter(pk__in=stages).delete()
            raw(OwnerDraft).filter(pk__in=drafts).delete()
            raw(PageContentState).filter(page_id__in=owned_pages).delete()
            raw(RevisionProtection).filter(revision_id__in=revisions).delete()
            raw(RevisionMetadata).filter(revision_id__in=revisions).delete()
            raw(AssetUsage).filter(asset_id__in=owned_assets).delete()
            raw(PageRevision).filter(pk__in=revisions).delete()
            # Minimal consumed receipts and identity reservations are permanent; no fake TTL/reset.
        for asset in Asset.objects.filter(pk__in=owned_assets):
            if asset.status != 'ready' or asset.usages.exists():
                raise ValueError('Media pending/retained; preserve for investigation')
            preview = prepare_cleanup(actor=owner,asset_ids=[asset.pk],expected_generation=1,storage=storage)
            outcome = confirm_cleanup(actor=owner,confirmation=preview['confirmation'],expected_generation=1,storage=storage)
            if any(row['state'] != 'deleted' for row in outcome):
                raise ValueError('Physical fixture cleanup incomplete')
        with transaction.atomic():
            lock_content('default')
            sessions = list(AuthSession.objects.filter(user_id__in=owned_users).values_list('pk',flat=True))
            AuthSession.objects.filter(pk__in=sessions).delete()
            Session.objects.filter(pk__in=sessions).delete()
            PageGrant.objects.filter(user_id__in=owned_users).delete()
            raw(PageMediaHome).filter(page_id__in=owned_pages).delete()
            raw(MediaFolder).filter(pk__in=folder_ids).delete()
            raw(Page).filter(pk__in=owned_pages).delete()
            UserProfile.objects.filter(user_id__in=owned_users).delete()
            User.objects.filter(pk__in=owned_users).delete()
        return {'closed':True,'remainingUsers':User.objects.count(),'remainingPages':Page.objects.count(),
                'remainingAssets':Asset.objects.count(),'remainingVersions':PageRevision.objects.count(),
                'remainingStages':RestoreStage.objects.count(),'identityTombstonesPreserved':True,
                'minimalOperationReceiptsPreserved':True,'appendOnlyAuditPreserved':True}
    raise ValueError('Unknown fixture operation')


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin)),default=str))
    except Exception as exc:
        print(json.dumps({'errorClass':type(exc).__name__}),file=sys.stderr)
        sys.exit(1)
