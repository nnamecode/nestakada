"""SC07 normal-only synthetic historical sources; no Budget/reset or root sweep."""
import base64
import hashlib
import json
import os
import secrets
import sys
from uuid import UUID


def execute(request):
    if (os.environ.get('ESTAKADA_LOCAL_ENV')!='test' or
            os.environ.get('DJANGO_SETTINGS_MODULE')!='estakada.settings.local_http'):
        raise ValueError('SC_FIXTURE_NORMAL_REQUIRED')
    import django
    django.setup()
    from django.apps import apps
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import connection,models,transaction
    from accounts.models import AuthSession,UserProfile,PageGrant
    from accounts.services import bootstrap_owner,lock_auth
    from content.models import Page,Route,lock_content
    from media_library.models import Asset,AssetFile,AssetUsage,MediaFolder,PageMediaHome
    from media_library.storage import MediaStorage
    from media_library.uploads import upload
    from media_library.services import attach,prepare_cleanup,confirm_cleanup
    from page_editor.test_media_http import PNG
    from shared_content.models import (SharedBlock,SharedRevision,SharedRestoreStage,
        SharedBasePin,SharedReceipt,SharedIdentityReservation,SharedBudget)
    from shared_content.storage import SharedStorage
    from shared_content import reservations
    from shared_content.policy import normalize_html
    from shared_content.test_shared_http import SharedHttpTests
    from types import SimpleNamespace
    from audit.models import AuditEvent
    if settings.ROOT_URLCONF!='estakada.urls' or settings.ENVIRONMENT!='test':
        raise ValueError('SC_FIXTURE_URLCONF')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(),current_user')
        if cursor.fetchone()!=('estakada_foundation','app_runtime'):
            raise ValueError('SC_FIXTURE_DATABASE')
    if type(request) is not dict or request.get('kind') not in ('seed','observe','close'):
        raise ValueError('SC_FIXTURE_OPERATION')
    run=str(UUID(request['runId'])); User=get_user_model()
    raw=lambda model:models.QuerySet(model=model,using='default')
    shared_models=sorted(apps.get_app_config('shared_content').get_models(),key=lambda model:model._meta.label)
    digest=lambda value:hashlib.sha256(json.dumps(value,default=str,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def catalogue():
        result={}
        for model in shared_models:
            rows={}
            for row in model.objects.order_by('pk').values().iterator(chunk_size=16):
                # C.finish legitimately updates these two caches. Policy/debt
                # and every other baseline field remain exact; no reset here.
                if model is SharedBudget:
                    row={key:value for key,value in row.items() if key not in ('snapshot_count','charged_bytes')}
                rows[str(row[model._meta.pk.attname])]=digest(row)
            result[model._meta.label]=rows
        return result
    def system():
        values=list(Route.objects.values('id','kind','target','page_id','is_legacy'))
        if len(values)!=1 or {key:value for key,value in values[0].items() if key!='id'}!={
                'kind':'system','target':'/manage/','page_id':None,'is_legacy':False}:
            raise ValueError('SC_FIXTURE_SYSTEM_ROUTE')
        return str(values[0]['id'])
    if request['kind']=='seed':
        from page_versions.models import PageRevision,OwnerDraft,RestoreStage,VersionBasePin
        empty=(User,Page,Asset,AssetFile,AssetUsage,MediaFolder,PageMediaHome,AuthSession,Session,
            PageRevision,OwnerDraft,RestoreStage,VersionBasePin)
        if any(model.objects.exists() for model in empty):raise ValueError('SC_FIXTURE_NONEMPTY_PRESERVED')
        baseline=catalogue(); route=system(); store=SharedStorage(); baseline_inventory=store.inventory()
        if baseline_inventory['journalCount']!=0:raise ValueError('SC_FIXTURE_UNKNOWN_BASELINE')
        password=secrets.token_hex(48); owner=bootstrap_owner(password)
        owner.first_name=run;owner.save(update_fields=['first_name'])
        page=Page.objects.create(kind=Page.Kind.ARTICLE,name='SC07 SYNTHETIC '+run)
        asset=upload(actor=owner,page_id=page.pk,expected_generation=1,
            upload=SimpleUploadedFile('sc07.png',base64.b64decode(PNG),content_type='image/png'))
        if asset.status!='ready' or asset.files.count()!=3:raise ValueError('SC_FIXTURE_READY_ASSET')
        from shared_content import quota
        sources={}; seed_measurements=[]
        with reservations.session_lease():
            for index,kind in enumerate(('header','footer')):
                block=SharedBlock.objects.get(kind=kind)
                normalized=normalize_html(SharedHttpTests.fixture(SimpleNamespace(asset=asset),kind,'SC07 SOURCE '+kind),kind)
                if len(normalized['html'].encode())>16384:raise ValueError('SC_FIXTURE_SMALL_SOURCE_BOUND')
                with transaction.atomic():
                    lock_content('default');lock_auth()
                    # Existing real admission, no invented allocator. The first
                    # check also reserves count capacity for BOTH fixture rows;
                    # own/all refs start 0/0, then remain all-owned (4/4,5/5).
                    measured=quota.admit_locked(snapshot_increment=2-index,new_refs=len(normalized['bindings']))
                    seed_measurements.append({key:measured[key] for key in ('usedBytes','snapshotCount','requiredBytes','limitBytes')})
                descriptor=store.write_new(normalized['html'])
                with transaction.atomic():
                    lock_content('default');lock_auth()
                    latest=SharedRevision.objects.filter(block=block).order_by('-sequence').values_list('sequence',flat=True).first() or 0
                    revision=SharedRevision.objects.create(block=block,sequence=latest+1,schema_version=kind+'-v1',
                        html='',payload_hash=descriptor['file_sha256'],author_id=owner.pk,**descriptor)
                    for binding in normalized['bindings']:
                        attach(kind='shared_block',consumer_id=revision.pk,slot=binding['slot'],asset_id=binding['assetId'])
                sources[kind]={'id':str(revision.pk),'blockId':str(block.pk),'descriptor':descriptor,
                    'htmlHash':hashlib.sha256(normalized['html'].encode()).hexdigest()}
                actual=quota.measure()
                if actual['usedBytes']>268435456 or actual['snapshotCount']>10000:
                    raise ValueError('SC_FIXTURE_AFTER_SEED_CAP')
        files=list(asset.files.order_by('id').values('id','key','sha256','byte_size','kind'))
        for file in files:file['id']=str(file['id'])
        return {'runId':run,'ownerId':str(owner.pk),'pageId':str(page.pk),'assetId':str(asset.pk),
            'folderId':str(asset.folder_id),'systemRouteId':route,'sources':sources,'files':files,
            'baseline':baseline,'baselineFiles':[row for row in baseline_inventory['files'] if row['kind']=='blob'],
            'seedQuotaMeasurements':seed_measurements,
            'username':owner.username,'password':password}
    state=request['state']
    if state['runId']!=run or system()!=state['systemRouteId']:raise ValueError('SC_FIXTURE_MANIFEST')
    owner=User.objects.get(pk=state['ownerId'],username='nesadmin',first_name=run)
    source_ids={UUID(value['id']) for value in state['sources'].values()}
    def validate(*, files=True):
        if (User.objects.exclude(pk=owner.pk).exists() or Page.objects.exclude(pk=state['pageId']).exists()
                or Page.objects.get(pk=state['pageId']).name!='SC07 SYNTHETIC '+run):
            raise ValueError('SC_FIXTURE_FOREIGN_PRINCIPAL')
        current=catalogue()
        for label,old in state['baseline'].items():
            if any(current[label].get(key)!=value for key,value in old.items()):
                raise ValueError('SC_FIXTURE_BASELINE_CHANGED')
        own_revisions=SharedRevision.objects.exclude(pk__in=state['baseline']['shared_content.SharedRevision'])
        if set(own_revisions.values_list('pk',flat=True))!=source_ids or own_revisions.exclude(author_id=owner.pk).exists():
            raise ValueError('SC_FIXTURE_FOREIGN_REVISION')
        stages=list(SharedRestoreStage.objects.exclude(pk__in=state['baseline']['shared_content.SharedRestoreStage']))
        if any(stage.actor_id!=owner.pk or stage.actor_generation!=1 or stage.source_revision_id not in source_ids
                or stage.status not in ('held','released') or str(stage.block_id)!=state['sources'][stage.schema_version.split('-')[0]]['blockId'] for stage in stages):
            raise ValueError('SC_FIXTURE_FOREIGN_STAGE')
        stage_ids={stage.pk for stage in stages}
        pins=list(SharedBasePin.objects.exclude(pk__in=state['baseline']['shared_content.SharedBasePin']))
        for stage in stages:
            actual={pin.revision_id for pin in pins if pin.holder_id==stage.pk and pin.holder_kind=='restore_stage'}
            expected=({stage.source_revision_id,stage.base_revision_id}-{None}) if stage.status=='held' else set()
            if actual!=expected:raise ValueError('SC_FIXTURE_PIN_SET')
        if any(pin.holder_id not in stage_ids or pin.holder_kind!='restore_stage' for pin in pins):raise ValueError('SC_FIXTURE_FOREIGN_PIN')
        receipts=list(SharedReceipt.objects.exclude(pk__in=state['baseline']['shared_content.SharedReceipt']))
        if any(receipt.actor_id!=owner.pk or receipt.actor_generation!=1 or receipt.action not in ('restore_prepare','restore_cancel')
                or receipt.source_revision_id not in source_ids for receipt in receipts):raise ValueError('SC_FIXTURE_FOREIGN_RECEIPT')
        receipt_map={receipt.pk:receipt for receipt in receipts}
        for stage in stages:
            if stage.status=='held':
                if stage.terminal_operation_id is not None or stage.terminal_actor_id is not None:raise ValueError('SC_FIXTURE_HELD_TERMINAL')
            else:
                receipt=receipt_map.get(stage.terminal_operation_id)
                if (stage.terminal_actor_id!=owner.pk or receipt is None or receipt.action!='restore_cancel'
                        or receipt.result_code!='released' or receipt.block_id!=stage.block_id
                        or receipt.source_revision_id!=stage.source_revision_id or receipt.base_revision_id!=stage.base_revision_id):raise ValueError('SC_FIXTURE_TERMINAL_RECEIPT')
        allowed_new={'shared_content.SharedRevision','shared_content.SharedRestoreStage','shared_content.SharedBasePin',
            'shared_content.SharedReceipt','shared_content.SharedIdentityReservation'}
        if any(set(rows)-set(state['baseline'][label]) for label,rows in current.items() if label not in allowed_new):raise ValueError('SC_FIXTURE_FOREIGN_SHARED_ROW')
        if (Asset.objects.exclude(pk=state['assetId']).exists() or Asset.objects.get(pk=state['assetId']).status!='ready'
                or AssetUsage.objects.exclude(asset_id=state['assetId'],consumer_id__in=source_ids).exists()
                or AssetUsage.objects.filter(asset_id=state['assetId']).exclude(consumer_id__in=source_ids,kind='shared_block').exists()
                or MediaFolder.objects.exclude(pk=state['folderId']).exists() or PageMediaHome.objects.exclude(page_id=state['pageId'],folder_id=state['folderId']).exists()):raise ValueError('SC_FIXTURE_FOREIGN_MEDIA')
        if AuthSession.objects.exclude(user_id=owner.pk).exists() or any(str(session.get_decoded().get('_auth_user_id'))!=str(owner.pk) for session in Session.objects.all()):raise ValueError('SC_FIXTURE_FOREIGN_SESSION')
        actual_files=list(AssetFile.objects.order_by('id').values('id','key','sha256','byte_size','kind'))
        for file in actual_files:file['id']=str(file['id'])
        if actual_files!=state['files']:raise ValueError('SC_FIXTURE_FILE_METADATA_CHANGED')
        if files:
            store=SharedStorage(); inventory=store.inventory()
            if inventory['journalCount']!=0:raise ValueError('SC_FIXTURE_UNKNOWN_BOOK_PRESERVED')
            rows={row['key']:row for row in inventory['files'] if row['kind']=='blob'}
            if set(rows)!={row['key'] for row in state['baselineFiles']}|{value['descriptor']['file_key'] for value in state['sources'].values()}:raise ValueError('SC_FIXTURE_FOREIGN_BLOB')
            for old in state['baselineFiles']:
                if rows.get(old['key'])!=old:raise ValueError('SC_FIXTURE_BASELINE_BLOB_CHANGED')
            for kind,source in state['sources'].items():
                text=store.read(source['descriptor'])
                if hashlib.sha256(text.encode()).hexdigest()!=source['htmlHash']:raise ValueError('SC_FIXTURE_SOURCE_CHANGED')
            storage=MediaStorage()
            for file in state['files']:
                if storage.manifest(file['key'])!={'sha256':file['sha256'],'byte_size':file['byte_size']}:raise ValueError('SC_FIXTURE_MEDIA_CHANGED')
        return stages,receipts
    stages,receipts=validate()
    if request['kind']=='observe':
        from shared_content.quota import measure
        measured=measure()
        return {'stages':[{'id':str(stage.pk),'kind':stage.schema_version.split('-')[0],
                'sourceId':str(stage.source_revision_id),'status':stage.status,'terminalActorId':str(stage.terminal_actor_id) if stage.terminal_actor_id else None,
                'terminalOperationId':str(stage.terminal_operation_id) if stage.terminal_operation_id else None} for stage in stages],
            'pins':list(SharedBasePin.objects.filter(holder_id__in=[stage.pk for stage in stages]).values_list('holder_id',flat=True)),
            'receipts':[{'id':str(receipt.pk),'action':receipt.action,'resultCode':receipt.result_code} for receipt in receipts],
            'auditCount':AuditEvent.objects.filter(actor_id=owner.pk).count(),'baselinePreserved':True,
            'currentDraftUnchanged':True,'budgetPolicyDebtPreserved':True,
            'cacheObserved':SharedBudget.objects.values('snapshot_count','charged_bytes').get(singleton=True),
            'sourceBlobHashes':{kind:value['htmlHash'] for kind,value in state['sources'].items()},
            'quota':{key:measured[key] for key in ('usedBytes','snapshotCount','heldBytes','retainedDebtBytes','limitBytes')}}
    # Only synthetic transient rows. Never delete permanent receipt/identity/audit
    # or mutate Budget: actual retained PG/FS growth remains charged.
    with reservations.session_lease():
        validate()
        with transaction.atomic():
            lock_content('default');lock_auth();stages,_=validate(files=False)
            stage_ids=[stage.pk for stage in stages]
            raw(SharedBasePin).filter(holder_kind='restore_stage',holder_id__in=stage_ids).delete()
            raw(SharedRestoreStage).filter(pk__in=stage_ids,actor_id=owner.pk,source_revision_id__in=source_ids).delete()
            raw(AssetUsage).filter(kind='shared_block',consumer_id__in=source_ids,asset_id=state['assetId']).delete()
            raw(SharedRevision).filter(pk__in=source_ids,author_id=owner.pk).delete()
        store=SharedStorage()
        for source in state['sources'].values():
            if (SharedRevision.objects.filter(file_key=source['descriptor']['file_key']).exists() or
                    AssetUsage.objects.filter(consumer_id=source['id']).exists()):raise ValueError('SC_FIXTURE_DESCRIPTOR_STILL_REFERENCED')
            store.unlink_verified(source['descriptor'])
    if AssetUsage.objects.filter(asset_id=state['assetId']).exists():raise ValueError('SC_FIXTURE_ASSET_STILL_REFERENCED')
    prepared=prepare_cleanup(actor=owner,asset_ids=[state['assetId']],expected_generation=1)
    cleaned=confirm_cleanup(actor=owner,confirmation=prepared['confirmation'],expected_generation=1)
    if len(cleaned)!=1 or cleaned[0]['state']!='deleted':raise ValueError('SC_FIXTURE_ASSET_PARTIAL')
    with transaction.atomic():
        lock_content('default');lock_auth()
        raw(PageMediaHome).filter(page_id=state['pageId'],folder_id=state['folderId']).delete()
        raw(MediaFolder).filter(pk=state['folderId']).delete()
        keys=list(AuthSession.objects.filter(user_id=owner.pk).values_list('session_key',flat=True))
        Session.objects.filter(session_key__in=keys).delete();AuthSession.objects.filter(user_id=owner.pk).delete()
        PageGrant.objects.filter(user_id=owner.pk).delete();raw(Page).filter(pk=state['pageId']).delete()
        UserProfile.objects.filter(user_id=owner.pk).delete();User.objects.filter(pk=owner.pk).delete()
    after=catalogue()
    if any(after[label].get(key)!=value for label,rows in state['baseline'].items() for key,value in rows.items()):raise ValueError('SC_FIXTURE_TEARDOWN_BASELINE_CHANGED')
    from shared_content.quota import measure
    actual=measure();cache=SharedBudget.objects.values('snapshot_count','charged_bytes').get(singleton=True)
    return {'closed':True,'users':User.objects.count(),'pages':Page.objects.count(),'assets':Asset.objects.count(),
        'ownStages':SharedRestoreStage.objects.filter(source_revision_id__in=source_ids).count(),
        'ownRevisions':SharedRevision.objects.filter(pk__in=source_ids).count(),'systemRoutePreserved':system()==state['systemRouteId'],
        'baselinePreserved':True,'budgetPolicyDebtPreserved':True,'budgetReset':False,
        'cacheObserved':cache,'cacheMayBeStaleAfterSyntheticTeardown':True,
        'actualQuota':{key:actual[key] for key in ('usedBytes','snapshotCount','heldBytes','retainedDebtBytes')},
        'permanentSharedReceipts':SharedReceipt.objects.count(),
        'permanentSharedIdentities':SharedIdentityReservation.objects.count(),'appendOnlyAuditEvents':AuditEvent.objects.count()}


if __name__=='__main__':
    try:print(json.dumps(execute(json.load(sys.stdin)),default=str))
    except Exception as error:
        print(json.dumps({'errorClass':type(error).__name__,'code':'SC_FIXTURE_FAILED'}),file=sys.stderr)
        sys.exit(1)
