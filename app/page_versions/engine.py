"""Trusted content mutation engine; no public renderer or arbitrary HTTP writer."""
from datetime import datetime,timezone as datetime_timezone
from uuid import UUID,uuid4
import copy
import re
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import connection,models,transaction
from django.db.models import Q
from django.utils import timezone
from accounts.models import UserProfile
from accounts.services import lock_auth,allowed_fields
from audit.constants import Category,Level,Result,Source
from audit.services import record_event
from content.models import Page,Route,lock_content
from media_library.models import Asset,AssetUsage
from media_library import services as media
from media_library.storage import MediaStorage
from . import schema as S
from .models import (PageRevision,PageContentState,RevisionMetadata,RevisionProtection,OwnerDraft,
                     RestoreStage,VersionBasePin,OperationReceipt)


def raw(model):return models.QuerySet(model=model,using='default')


def outside():
    if connection.in_atomic_block:raise ValidationError('VERSIONS_CALL_FROM_AUTOCOMMIT')


def now():
    value=timezone.now()
    if timezone.is_naive(value):raise ValidationError('VERSIONS_SERVER_CLOCK_MUST_BE_AWARE')
    return value.astimezone(datetime_timezone.utc)


def uid(value):
    try:return UUID(str(value))
    except (ValueError,TypeError,AttributeError):raise ValidationError('VERSIONS_INVALID_ID') from None


def profile_for(actor_id,page,expected_generation):
    profile=UserProfile.objects.select_related('user').filter(user_id=actor_id,user__is_active=True).first()
    if profile is None or type(expected_generation) is not int or profile.generation!=expected_generation:
        raise PermissionDenied('VERSIONS_CURRENT_IDENTITY_REQUIRED')
    owner=profile.role=='owner' and profile.user.username=='nesadmin'
    if owner:fields=sorted(S.OWNER_FIELDS)
    elif profile.role=='employee':fields=sorted(allowed_fields(profile.user,page))
    else:raise PermissionDenied('VERSIONS_PAGE_DENIED')
    return profile,fields,owner


def enter(actor,page_id,generation,owner=False,optional=False):
    lock_content('default');lock_auth()
    page=Page.objects.select_for_update().get(pk=uid(page_id))
    profile,fields,is_owner=profile_for(actor.pk,page,generation)
    if owner and not is_owner:raise PermissionDenied('AUTH_OWNER_REQUIRED')
    state=PageContentState.objects.select_for_update().select_related('current_revision').defer('current_revision__payload').filter(page=page).first()
    if state is None and not optional:raise ValidationError('VERSIONS_NOT_INITIALIZED')
    if state is not None and state.current_revision.page_id!=page.pk:raise ValidationError('VERSIONS_CURRENT_PAGE_MISMATCH')
    return page,profile,fields,is_owner,state


def revision(page,version_id):
    row=PageRevision.objects.filter(page=page,pk=uid(version_id)).first()
    if row is None:raise ValidationError('VERSIONS_SOURCE_GONE')
    if S.digest(row.payload)!=row.payload_hash:raise ValidationError('VERSIONS_PAYLOAD_DAMAGED')
    return row


def draft_for(page):
    draft=OwnerDraft.objects.select_related('base_revision').defer('base_revision__payload').filter(page=page).first()
    if draft is not None and draft.base_revision.page_id!=page.pk:raise ValidationError('VERSIONS_DRAFT_PAGE_MISMATCH')
    return draft


def permission_hash(profile,fields):
    return S.digest({'actor':profile.user_id,'generation':profile.generation,'role':profile.role,'fields':sorted(fields)})


def page_context(page):
    target=Route.objects.filter(page=page,kind=Route.Kind.PRIMARY).values_list('target',flat=True).first()
    return {'id':str(page.pk),'name':page.name,'url':target}


def metadata_values(name='',comment='',manual_date=None):
    import unicodedata
    from django.utils.dateparse import parse_datetime
    if type(name) is not str or type(comment) is not str:S.invalid()
    # Reject one-line controls before strip can silently discard LF/TAB/CR.
    S.text(name)
    name=unicodedata.normalize('NFC',name.strip()) or 'Контрольная версия'
    comment=unicodedata.normalize('NFC',comment.replace('\r\n','\n').replace('\r','\n'))
    S.text(name,200);S.text(comment,1000,multiline=True)
    if manual_date is not None:
        try:
            value=parse_datetime(manual_date) if type(manual_date) is str else manual_date
            if not isinstance(value,datetime) or timezone.is_naive(value):raise ValueError()
            manual_date=value.astimezone(datetime_timezone.utc)
        except (ValueError,TypeError,OverflowError):raise ValidationError('VERSIONS_MANUAL_DATE_MUST_BE_AWARE') from None
    return {'name':name,'comment':comment,'manual_date':manual_date}


def serial_meta(meta):
    return {'generation':meta.generation,'name':meta.name,'comment':meta.comment,
            'manual_date':meta.manual_date.isoformat() if meta.manual_date else None}


def stamp(page,row):
    meta=RevisionMetadata.objects.get(revision=row)
    protection=RevisionProtection.objects.filter(revision=row).first()
    return {'page':page_context(page),'version':str(row.pk),'schema':row.schema_version,'payload_hash':row.payload_hash,
            'meta':S.digest(serial_meta(meta)),'protection':str(protection.pk) if protection else None}


def preflight(payload):
    """Actual filesystem evidence outside every content/auth transaction."""
    outside();evidence={};storage=MediaStorage()
    for asset_id in sorted(set(S.asset_slots(payload).values())):
        asset=Asset.objects.get(pk=asset_id)
        if asset.status!=Asset.Status.READY:raise ValidationError('VERSIONS_MEDIA_UNAVAILABLE')
        rows=[]
        for file in asset.files.order_by('key'):
            actual=storage.manifest(file.key)
            if actual!={'sha256':file.sha256,'byte_size':file.byte_size}:raise ValidationError('VERSIONS_MEDIA_UNAVAILABLE')
            rows.append({'id':str(file.pk),'key':file.key,'sha256':file.sha256,'bytes':file.byte_size,'kind':file.kind})
        if not rows:raise ValidationError('VERSIONS_MEDIA_UNAVAILABLE')
        evidence[asset_id]=S.digest(rows)
    return evidence


def check_evidence(payload,evidence):
    for asset_id in sorted(set(S.asset_slots(payload).values())):
        asset=Asset.objects.select_for_update().get(pk=asset_id)
        rows=[{'id':str(file.pk),'key':file.key,'sha256':file.sha256,'bytes':file.byte_size,'kind':file.kind} for file in asset.files.order_by('key')]
        if asset.status!=Asset.Status.READY or not rows or evidence.get(asset_id)!=S.digest(rows):raise ValidationError('VERSIONS_MEDIA_UNAVAILABLE')


def sync_usage(kind,consumer_id,payload):
    wanted=S.asset_slots(payload)
    existing={row.slot:row for row in AssetUsage.objects.filter(kind=kind,consumer_id=consumer_id)}
    for slot,row in existing.items():
        if slot not in wanted or str(row.asset_id)!=wanted[slot]:media.detach(kind=kind,consumer_id=consumer_id,slot=slot)
    for slot,asset_id in sorted(wanted.items()):
        if slot not in existing or str(existing[slot].asset_id)!=asset_id:
            media.attach(asset_id=asset_id,kind=kind,consumer_id=consumer_id,slot=slot)


def remove_usage(kind,consumer_id):
    for row in list(AssetUsage.objects.filter(kind=kind,consumer_id=consumer_id)):
        media.detach(kind=kind,consumer_id=consumer_id,slot=row.slot)


def move_usage(row,source_kind,target_kind):
    # Stable promotion uses existing ledger, never reparses an unsupported historical snapshot.
    for usage in list(AssetUsage.objects.filter(kind=source_kind,consumer_id=row.pk).order_by('slot')):
        media.attach(asset_id=usage.asset_id,kind=target_kind,consumer_id=row.pk,slot=usage.slot)
        media.detach(kind=source_kind,consumer_id=row.pk,slot=usage.slot)


def event(code,actor,result_id=None,object_kind='page_revision'):
    return record_event(category=Category.USER_ACTIONS,event_code=code,level=Level.INFO,source=Source.APPLICATION,
                        result=Result.SUCCESS,actor_id=actor.pk,object_kind=object_kind,object_ref=uid(result_id) if result_id else None)


def fingerprint(action,actor,page,generation,params):
    return S.digest({'action':action,'actor':actor.pk,'page':str(page.pk),'generation':generation,'params':params})


def result(receipt,replay):
    model=OwnerDraft if receipt.action in ('save_draft','rebase_draft','cancel_draft') else RestoreStage if receipt.action in ('stage_restore','cancel_stage') else PageRevision
    gone=receipt.result_id is not None and not model.objects.filter(pk=receipt.result_id).exists()
    return {'operation_id':str(receipt.pk),'action':receipt.action,'result_id':str(receipt.result_id) if receipt.result_id else None,
            'result_code':receipt.result_code,'gone':gone,'replay':replay}


def replay(operation_id,action,actor,page,generation,params,*,editor_request_fingerprint=None):
    row=OperationReceipt.objects.filter(pk=uid(operation_id)).first()
    if row is None:return None
    if editor_request_fingerprint is not None and row.editor_request_fingerprint!=editor_request_fingerprint:
        raise ValidationError('VERSIONS_OPERATION_ID_CONSUMED')
    if row.action!=action or row.actor_id!=actor.pk or row.page_id!=page.pk or row.actor_generation!=generation or row.fingerprint!=fingerprint(action,actor,page,generation,params):
        raise ValidationError('VERSIONS_OPERATION_ID_CONSUMED')
    return result(row,True)


def finish(operation_id,action,actor,page,generation,params,result_id,code='applied',source=None,target=None,editor_request_fingerprint=''):
    row=OperationReceipt.objects.create(id=uid(operation_id),action=action,actor_id=actor.pk,actor_generation=generation,page_id=page.pk,
        source_revision_id=uid(source) if source else None,target_revision_id=uid(target) if target else None,
        fingerprint=fingerprint(action,actor,page,generation,params),result_code=code,result_id=uid(result_id) if result_id else None,created_at=now(),editor_request_fingerprint=editor_request_fingerprint)
    object_kind='page_draft' if action in ('save_draft','rebase_draft','cancel_draft') else 'restore_stage' if action in ('stage_restore','cancel_stage') else 'page_revision'
    event('VERSION_'+action.upper(),actor,result_id,object_kind)
    return result(row,False)


def new_revision(page,state,payload,kind,actor,source=None,metadata=None):
    sequence=state.sequence+1 if state is not None else 1
    row=PageRevision.objects.create(page=page,sequence=sequence,schema_version=payload['schema_version'],payload=payload,payload_hash=S.digest(payload),
        kind=kind,created_at=now(),author_id=actor.pk,source_revision_id=uid(source) if source else None)
    values=metadata or {'name':'','comment':'','manual_date':None}
    RevisionMetadata.objects.create(revision=row,**values)
    if state is not None:raw(PageContentState).filter(pk=state.pk).update(sequence=sequence)
    sync_usage('ordinary_version',row.pk,payload)
    return row


def terminate_stage(stage,status,reason,actor,operation_id):
    raw(VersionBasePin).filter(holder_kind=stage.holder_kind,holder_id=stage.pk).delete()
    raw(RestoreStage).filter(pk=stage.pk).update(status=status,terminal_reason=reason,terminal_actor_id=actor.pk,terminal_operation_id=uid(operation_id))


def invalidate_stages(page,current_id,actor,operation_id):
    for stage in RestoreStage.objects.filter(page=page,status='held').order_by('id'):
        reason=None
        if stage.base_revision_id!=current_id:reason='CURRENT_CHANGED'
        else:
            try:
                profile,fields,_=profile_for(stage.actor_id,page,stage.actor_generation)
                if permission_hash(profile,fields)!=stage.permission_hash:reason='GRANTS_CHANGED'
            except PermissionDenied:reason='IDENTITY_OR_GRANTS_CHANGED'
        if reason:terminate_stage(stage,'invalidated',reason,actor,operation_id)


def prune(page,current_id,actor,operation_id,*,retained_ids=()):
    invalidate_stages(page,current_id,actor,operation_id)
    ordinary=list(PageRevision.objects.filter(page=page,stable_protection__isnull=True).defer('payload').order_by('created_at','sequence','id'))
    excess=max(0,len(ordinary)-10)
    pinned=set(VersionBasePin.objects.filter(revision__page=page).values_list('revision_id',flat=True))
    pinned.update(OwnerDraft.objects.filter(page=page).values_list('base_revision_id',flat=True))
    # A newly requested manual checkpoint must survive its own command. If all
    # older ordinary rows are valid bases, fail atomically rather than return a
    # successful receipt for a checkpoint pruned in the same transaction.
    retained={uid(value) for value in retained_ids}
    eligible=[row for row in ordinary if row.pk!=current_id and row.pk not in pinned and row.pk not in retained]
    if len(eligible)<excess:raise ValidationError('VERSIONS_HISTORY_BASES_HELD')
    for row in eligible[:excess]:
        remove_usage('ordinary_version',row.pk);raw(PageRevision).filter(pk=row.pk).delete()


def _assert_base(state,base_revision):
    if state.current_revision_id!=uid(base_revision):raise ValidationError('VERSIONS_CURRENT_CONFLICT')


def _snapshot(value,page):
    if type(value) is not S.Snapshot:raise ValidationError('VERSIONS_TYPED_PRODUCER_REQUIRED')
    payload=value.data(page.kind)
    if any(node['kind']=='protected_ref' for node in payload['layout']):raise ValidationError('VERSIONS_COMPONENT_RESOLVER_UNAVAILABLE')
    return payload


def initialize(*,actor,page_id,snapshot,expected_generation,operation_id):
    outside()
    with transaction.atomic():
        page,profile,fields,owner,state=enter(actor,page_id,expected_generation,owner=True,optional=True)
        payload=_snapshot(snapshot,page);params={'snapshot':S.digest(payload)}
        previous=replay(operation_id,'initialize',actor,page,expected_generation,params)
        if previous:return previous
        if state is not None:raise ValidationError('VERSIONS_ALREADY_INITIALIZED')
    evidence=preflight(payload)
    with transaction.atomic():
        page,profile,fields,owner,state=enter(actor,page_id,expected_generation,owner=True,optional=True)
        previous=replay(operation_id,'initialize',actor,page,expected_generation,params)
        if previous:return previous
        if state is not None:raise ValidationError('VERSIONS_ALREADY_INITIALIZED')
        check_evidence(payload,evidence)
        row=new_revision(page,None,payload,'initial',actor)
        PageContentState.objects.create(page=page,current_revision=row)
        sync_usage('current_page',page.pk,payload)
        return finish(operation_id,'initialize',actor,page,expected_generation,params,row.pk)


def check_editor_session(actor,generation,session_key):
    from accounts.models import AuthSession
    from accounts import clock
    from accounts.services import IDLE,ABSOLUTE
    if type(session_key) is not str or not session_key:
        raise ValidationError('EDITOR_SESSION_ENDED')
    session=AuthSession.objects.filter(pk=session_key,user_id=actor.pk,generation=generation).first()
    instant=clock.now()
    if (session is None or instant<session.issued_at or instant<session.last_seen
            or instant-session.last_seen>IDLE or instant-session.issued_at>ABSOLUTE):
        raise ValidationError('EDITOR_SESSION_ENDED')


def commit_employee(*,actor,page_id,base_revision,patch,expected_generation,operation_id,stage_id=None,editor_request_fingerprint=None,editor_session_key=None):
    if type(patch) is not S.TextPricePatch:raise ValidationError('VERSIONS_TYPED_PATCH_REQUIRED')
    return _commit(actor,page_id,base_revision,expected_generation,operation_id,'commit_employee',patch=patch,stage_id=stage_id,editor_request_fingerprint=editor_request_fingerprint,editor_session_key=editor_session_key)


def commit_owner(*,actor,page_id,base_revision,snapshot,expected_generation,operation_id,stage_id=None,draft_id=None,draft_revision=None,editor_request_fingerprint=None,editor_session_key=None):
    return _commit(actor,page_id,base_revision,expected_generation,operation_id,'commit_owner',snapshot=snapshot,
        stage_id=stage_id,draft_id=draft_id,draft_revision=draft_revision,editor_request_fingerprint=editor_request_fingerprint,editor_session_key=editor_session_key)


def _commit(actor,page_id,base_revision,generation,operation_id,action,patch=None,snapshot=None,stage_id=None,draft_id=None,draft_revision=None,editor_request_fingerprint=None,editor_session_key=None):
    outside();owner_required=action=='commit_owner'
    if editor_request_fingerprint is not None and (type(editor_request_fingerprint) is not str or re.fullmatch('[a-f0-9]{64}',editor_request_fingerprint) is None):
        raise ValidationError('VERSIONS_INVALID_EDITOR_FINGERPRINT')
    changes=patch.changes() if patch is not None else None
    params={'base':str(uid(base_revision)),'changes':S.digest(changes) if changes is not None else None,
        'snapshot':S.digest(snapshot.data()) if type(snapshot) is S.Snapshot else None,'stage':str(uid(stage_id)) if stage_id else None,
        'draft':str(uid(draft_id)) if draft_id else None,'draft_revision':draft_revision}
    def candidate(page,profile,fields,state):
        _assert_base(state,base_revision)
        if changes is not None:
            if not set(changes).issubset(set(fields)):raise PermissionDenied('VERSIONS_FIELD_DENIED')
            payload=revision(page,state.current_revision_id).payload.copy();payload.update(copy.deepcopy(changes))
            payload=S.validate(payload,page.kind)
        else:payload=_snapshot(snapshot,page)
        if stage_id:
            from .restoration import candidate_for_stage
            restored=candidate_for_stage(page,profile,fields,uid(stage_id),state)
            if changes is not None and set(changes)!=set(restored['fields']):raise ValidationError('VERSIONS_STAGE_FIELDS_CHANGED')
            # DEV07 may edit the staged fields before explicitly saving. The typed
            # producer still validates the final candidate; stage/base/rights stay exact.
        if draft_id:
            draft=draft_for(page)
            if draft is None or draft.pk!=uid(draft_id) or draft.revision!=draft_revision or draft.base_revision_id!=state.current_revision_id or draft.payload!=payload:
                raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        return payload
    with transaction.atomic():
        page,profile,fields,owner,state=enter(actor,page_id,generation,owner=owner_required)
        if editor_request_fingerprint is not None:check_editor_session(actor,generation,editor_session_key)
        if changes is not None and (not set(fields)&S.EMPLOYEE_FIELDS or not set(changes).issubset(set(fields))):raise PermissionDenied('VERSIONS_FIELD_DENIED')
        previous=replay(operation_id,action,actor,page,generation,params,editor_request_fingerprint=editor_request_fingerprint)
        if previous:return previous
        payload=candidate(page,profile,fields,state)
    evidence=preflight(payload)
    with transaction.atomic():
        page,profile,fields,owner,state=enter(actor,page_id,generation,owner=owner_required)
        if editor_request_fingerprint is not None:check_editor_session(actor,generation,editor_session_key)
        if changes is not None and (not set(fields)&S.EMPLOYEE_FIELDS or not set(changes).issubset(set(fields))):raise PermissionDenied('VERSIONS_FIELD_DENIED')
        previous=replay(operation_id,action,actor,page,generation,params,editor_request_fingerprint=editor_request_fingerprint)
        if previous:return previous
        if candidate(page,profile,fields,state)!=payload:raise ValidationError('VERSIONS_CURRENT_CONFLICT')
        check_evidence(payload,evidence)
        source_id=RestoreStage.objects.get(pk=stage_id).source_revision_id if stage_id else uid(base_revision)
        row=new_revision(page,state,payload,'automatic',actor,source=source_id)
        # Explicit same-Page check immediately before raw pointer update.
        if row.page_id!=page.pk:raise ValidationError('VERSIONS_CURRENT_PAGE_MISMATCH')
        raw(PageContentState).filter(pk=state.pk).update(current_revision_id=row.pk)
        sync_usage('current_page',page.pk,payload)
        if stage_id:terminate_stage(RestoreStage.objects.get(pk=stage_id),'consumed','COMMITTED',actor,operation_id)
        if draft_id:
            remove_usage('draft',draft_id);raw(VersionBasePin).filter(holder_kind='owner_draft',holder_id=draft_id).delete()
            raw(OwnerDraft).filter(pk=draft_id).delete()
        prune(page,row.pk,actor,operation_id)
        return finish(operation_id,action,actor,page,generation,params,row.pk,code='restored' if stage_id else 'applied',source=source_id,editor_request_fingerprint=editor_request_fingerprint or '')


def save_owner_draft(*,actor,page_id,base_revision,snapshot,expected_generation,operation_id,draft_revision=None,rebase=False):
    outside();action='rebase_draft' if rebase else 'save_draft'
    params={'base':str(uid(base_revision)),'payload':S.digest(snapshot.data()) if type(snapshot) is S.Snapshot else None,'draft_revision':draft_revision}
    def inspect(page,state):
        payload=_snapshot(snapshot,page);base=revision(page,base_revision);draft=draft_for(page)
        if draft is None:
            if draft_revision is not None or base.pk!=state.current_revision_id:raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        elif draft.revision!=draft_revision or (base.pk!=state.current_revision_id if rebase else base.pk!=draft.base_revision_id):
            raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        return payload,draft
    with transaction.atomic():
        page,profile,fields,owner,state=enter(actor,page_id,expected_generation,owner=True)
        previous=replay(operation_id,action,actor,page,expected_generation,params)
        if previous:return previous
        payload,draft=inspect(page,state)
    evidence=preflight(payload)
    with transaction.atomic():
        page,profile,fields,owner,state=enter(actor,page_id,expected_generation,owner=True)
        previous=replay(operation_id,action,actor,page,expected_generation,params)
        if previous:return previous
        checked,draft=inspect(page,state)
        if checked!=payload:raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        check_evidence(payload,evidence)
        if draft is None:
            draft=OwnerDraft.objects.create(page=page,base_revision_id=uid(base_revision),payload=payload,payload_hash=S.digest(payload),author_id=actor.pk,created_at=now(),updated_at=now())
        else:
            raw(VersionBasePin).filter(holder_kind='owner_draft',holder_id=draft.pk).delete()
            raw(OwnerDraft).filter(pk=draft.pk).update(base_revision_id=uid(base_revision),payload=payload,payload_hash=S.digest(payload),author_id=actor.pk,updated_at=now(),revision=draft.revision+1)
        VersionBasePin.objects.create(revision_id=uid(base_revision),holder_kind='owner_draft',holder_id=draft.pk)
        sync_usage('draft',draft.pk,payload)
        return finish(operation_id,action,actor,page,expected_generation,params,draft.pk,source=base_revision)


def cancel_owner_draft(*,actor,page_id,draft_id,draft_revision,expected_generation,operation_id):
    params={'draft':str(uid(draft_id)),'draft_revision':draft_revision}
    with transaction.atomic():
        page,profile,fields,owner,state=enter(actor,page_id,expected_generation,owner=True)
        previous=replay(operation_id,'cancel_draft',actor,page,expected_generation,params)
        if previous:return previous
        draft=draft_for(page)
        if draft is None or draft.pk!=uid(draft_id) or draft.revision!=draft_revision:raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        remove_usage('draft',draft.pk);raw(VersionBasePin).filter(holder_kind='owner_draft',holder_id=draft.pk).delete();raw(OwnerDraft).filter(pk=draft.pk).delete()
        return finish(operation_id,'cancel_draft',actor,page,expected_generation,params,draft.pk,code='released')
