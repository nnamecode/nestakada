"""Prepare/stage only. Publication requires a later explicit trusted commit."""
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from . import engine as E,schema as S
from .models import RestoreStage,VersionBasePin
from .operations import ticket,load_ticket,_binding


def _candidate(page,source,current,fields,owner):
    past=S.validate(source.payload,page.kind);present=S.validate(current.payload,page.kind)
    if source.schema_version!=S.SCHEMA or current.schema_version!=S.SCHEMA:raise ValidationError('VERSIONS_INCOMPATIBLE_SCHEMA')
    if any(node['kind']=='protected_ref' for node in past['layout']):raise ValidationError('VERSIONS_COMPONENT_RESOLVER_UNAVAILABLE')
    wanted=sorted(S.OWNER_FIELDS if owner else set(fields)&S.EMPLOYEE_FIELDS)
    if not wanted:raise PermissionDenied('VERSIONS_NO_RESTORE_FIELDS')
    current_nodes={node['id']:node for node in present['layout']}
    for node in past['layout']:
        if node['kind']=='text' and (owner or node['field'] in wanted):
            active=current_nodes.get(node['id'])
            if node['protected_nodes']:
                if active is None or active.get('kind')!='text':raise ValidationError('VERSIONS_PROTECTED_BLOCK_REMOVED')
                active_ids={item['id'] for item in active['protected_nodes']}
                if any(item['id'] not in active_ids for item in node['protected_nodes']):raise ValidationError('VERSIONS_PROTECTED_BLOCK_REMOVED')
                if not owner and node['protected_nodes']!=active['protected_nodes']:raise ValidationError('VERSIONS_PROTECTED_MEDIA_CHANGED')
    if not owner:
        past_nodes={node['id']:node for node in past['layout']}
        past_images={image['id']:image for image in past['embedded_images']}
        current_images={image['id']:image for image in present['embedded_images']}
        for active in present['layout']:
            if active['kind']=='text' and active['field'] in wanted and active['protected_nodes']:
                old=past_nodes.get(active['id'])
                if old is None or old.get('kind')!='text' or old.get('field')!=active['field'] or old['protected_nodes']!=active['protected_nodes']:
                    raise ValidationError('VERSIONS_PROTECTED_MEDIA_CHANGED')
                for protected in active['protected_nodes']:
                    ref=protected['reference_id']
                    if past_images.get(ref)!=current_images.get(ref):raise ValidationError('VERSIONS_PROTECTED_MEDIA_CHANGED')
        # Employee cannot revive/move any deleted historical text container, even one without media.
        for node in past['layout']:
            if node['kind']=='text' and node['field'] in wanted:
                active=current_nodes.get(node['id'])
                if active is None or active.get('kind')!='text' or active.get('field')!=node['field']:raise ValidationError('VERSIONS_BLOCK_REMOVED')
        candidate=present.copy()
        for field in wanted:candidate[field]=past[field]
    else:candidate=past
    return {'payload':S.validate(candidate,page.kind),'fields':wanted}


def prepare_restore(*,actor,page_id,version_id,expected_generation):
    E.outside()
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation)
        source=E.revision(page,version_id);current=E.revision(page,state.current_revision_id)
        candidate=_candidate(page,source,current,fields,owner)
        data={'binding':_binding(actor,page,expected_generation),'source':str(source.pk),'source_stamp':E.stamp(page,source),
              'base':str(current.pk),'base_stamp':E.stamp(page,current),'permission_hash':E.permission_hash(profile,fields),'fields':candidate['fields'],
              'candidate_hash':S.digest(candidate['payload'])}
    E.preflight(candidate['payload'])
    return {**candidate,'source':source,'current':current,'preparation':ticket('restore',data)}


def _check_preparation(data,actor,page,profile,fields,owner,state):
    if data['binding']!=_binding(actor,page,profile.generation) or data['base']!=str(state.current_revision_id) or data['permission_hash']!=E.permission_hash(profile,fields):raise ValidationError('VERSIONS_RESTORE_STALE')
    source=E.revision(page,data['source']);current=E.revision(page,state.current_revision_id)
    if data['source_stamp']!=E.stamp(page,source) or data['base_stamp']!=E.stamp(page,current):raise ValidationError('VERSIONS_RESTORE_STALE')
    candidate=_candidate(page,source,current,fields,owner)
    if candidate['fields']!=data['fields'] or S.digest(candidate['payload'])!=data['candidate_hash']:raise ValidationError('VERSIONS_RESTORE_STALE')
    return candidate


def stage_restore(*,actor,page_id,preparation,confirm_input_replacement,expected_generation,operation_id):
    E.outside()
    if confirm_input_replacement is not True:raise ValidationError('VERSIONS_CONFIRM_INPUT_REPLACEMENT')
    data=load_ticket(preparation,'restore');params={'preparation':data,'input_replacement':True}
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation)
        previous=E.replay(operation_id,'stage_restore',actor,page,expected_generation,params)
        if previous:return previous
        candidate=_check_preparation(data,actor,page,profile,fields,owner,state)
    evidence=E.preflight(candidate['payload'])
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation)
        previous=E.replay(operation_id,'stage_restore',actor,page,expected_generation,params)
        if previous:return previous
        checked=_check_preparation(data,actor,page,profile,fields,owner,state)
        E.check_evidence(checked['payload'],evidence)
        stage=RestoreStage.objects.create(page=page,actor_id=actor.pk,actor_generation=expected_generation,source_revision_id=E.uid(data['source']),
            base_revision_id=state.current_revision_id,permission_hash=E.permission_hash(profile,fields),fields=candidate['fields'],created_at=E.now())
        for version_id in sorted({stage.source_revision_id,stage.base_revision_id},key=str):
            VersionBasePin.objects.create(revision_id=version_id,holder_kind='restore_stage',holder_id=stage.pk)
        return E.finish(operation_id,'stage_restore',actor,page,expected_generation,params,stage.pk,source=stage.source_revision_id)


def candidate_for_stage(page,profile,fields,stage_id,state):
    stage=RestoreStage.objects.filter(pk=stage_id,page=page,actor_id=profile.user_id,status='held').first()
    if stage is None or stage.actor_generation!=profile.generation or stage.base_revision_id!=state.current_revision_id or stage.permission_hash!=E.permission_hash(profile,fields):raise ValidationError('VERSIONS_STAGE_STALE')
    source=E.revision(page,stage.source_revision_id);current=E.revision(page,stage.base_revision_id)
    candidate=_candidate(page,source,current,fields,profile.role=='owner' and profile.user.username=='nesadmin')
    if candidate['fields']!=stage.fields:raise ValidationError('VERSIONS_STAGE_FIELDS_CHANGED')
    return candidate


def get_stage(*,actor,page_id,stage_id,expected_generation):
    E.outside()
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation)
        candidate=candidate_for_stage(page,profile,fields,E.uid(stage_id),state)
        stage=RestoreStage.objects.get(pk=stage_id,page=page,actor_id=actor.pk)
    E.preflight(candidate['payload'])
    return {**candidate,'stage':stage}


def cancel_stage(*,actor,page_id,stage_id,expected_generation,operation_id):
    params={'stage':str(E.uid(stage_id))}
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation)
        previous=E.replay(operation_id,'cancel_stage',actor,page,expected_generation,params)
        if previous:return previous
        stage=RestoreStage.objects.filter(pk=E.uid(stage_id),page=page,actor_id=actor.pk).first()
        if stage is None:raise PermissionDenied('VERSIONS_OWN_STAGE_REQUIRED')
        if stage.status=='held':E.terminate_stage(stage,'released','EXPLICIT_CANCEL',actor,operation_id)
        return E.finish(operation_id,'cancel_stage',actor,page,expected_generation,params,stage.pk,code='released')
