"""Owner confirmations: manual versions, Stable protection and exact deletion."""
from uuid import UUID
from django.contrib.auth.hashers import check_password
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from . import engine as E
from .models import PageRevision,RevisionMetadata,RevisionProtection,VersionBasePin,OwnerDraft

SALT='estakada.page-versions.v1'


def ticket(action,data):return signing.dumps({'action':action,**data},salt=SALT,compress=True)


def load_ticket(value,action):
    try:
        data=signing.loads(value,salt=SALT)
        if type(data) is not dict or data.get('action')!=action:raise ValueError()
        return data
    except (signing.BadSignature,ValueError,TypeError):raise ValidationError('VERSIONS_INVALID_CONFIRMATION') from None


def _binding(actor,page,generation):return {'actor':actor.pk,'page':str(page.pk),'generation':generation}


def view_version(*,actor,page_id,version_id,expected_generation):
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation)
        row=E.revision(page,version_id)
        proof={'binding':_binding(actor,page,expected_generation),'stamp':E.stamp(page,row)}
        return {'revision':row,'metadata':RevisionMetadata.objects.get(revision=row),'current':state.current_revision_id==row.pk,
            'stable':proof['stamp']['protection'] is not None,'owner':owner,'fields':fields,'view_receipt':ticket('view',proof)}


def prepare_manual(*,actor,page_id,expected_generation):
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        row=E.revision(page,state.current_revision_id)
        return {'source':row,'page':E.page_context(page),'confirmation':ticket('manual',{'binding':_binding(actor,page,expected_generation),'source':str(row.pk),'stamp':E.stamp(page,row)})}


def create_manual(*,actor,page_id,confirmation,expected_generation,operation_id,name='',comment='',manual_date=None):
    data=load_ticket(confirmation,'manual');metadata=E.metadata_values(name,comment,manual_date)
    params={'proof':data,'metadata':{**metadata,'manual_date':metadata['manual_date'].isoformat() if metadata['manual_date'] else None}}
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        previous=E.replay(operation_id,'create_manual',actor,page,expected_generation,params)
        if previous:return previous
        source=E.revision(page,data['source'])
        if data['binding']!=_binding(actor,page,expected_generation) or state.current_revision_id!=source.pk or data['stamp']!=E.stamp(page,source):raise ValidationError('VERSIONS_CURRENT_CONFLICT')
        # Copy the actual immutable source/ledger; do not copy a draft or body from the request.
        row=PageRevision.objects.create(page=page,sequence=state.sequence+1,schema_version=source.schema_version,payload=source.payload,
            payload_hash=source.payload_hash,kind='manual',created_at=E.now(),author_id=actor.pk,source_revision_id=source.pk)
        RevisionMetadata.objects.create(revision=row,**metadata)
        E.raw(type(state)).filter(pk=state.pk).update(sequence=row.sequence)
        source_kind='stable_version' if RevisionProtection.objects.filter(revision=source).exists() else 'ordinary_version'
        from media_library.models import AssetUsage
        from media_library import services as media
        for usage in AssetUsage.objects.filter(kind=source_kind,consumer_id=source.pk).order_by('slot'):
            media.attach(asset_id=usage.asset_id,kind='ordinary_version',consumer_id=row.pk,slot=usage.slot)
        E.prune(page,state.current_revision_id,actor,operation_id,retained_ids=(row.pk,))
        return E.finish(operation_id,'create_manual',actor,page,expected_generation,params,row.pk,source=source.pk)


def edit_manual_metadata(*,actor,page_id,version_id,metadata_generation,expected_generation,operation_id,name='',comment='',manual_date=None):
    metadata=E.metadata_values(name,comment,manual_date)
    params={'target':str(E.uid(version_id)),'metadata_generation':metadata_generation,
        'metadata':{**metadata,'manual_date':metadata['manual_date'].isoformat() if metadata['manual_date'] else None}}
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        previous=E.replay(operation_id,'edit_manual',actor,page,expected_generation,params)
        if previous:return previous
        row=E.revision(page,version_id);meta=RevisionMetadata.objects.get(revision=row)
        if row.kind!='manual' or type(metadata_generation) is not int or meta.generation!=metadata_generation:raise ValidationError('VERSIONS_METADATA_CONFLICT')
        E.raw(RevisionMetadata).filter(pk=meta.pk).update(**metadata,generation=meta.generation+1)
        return E.finish(operation_id,'edit_manual',actor,page,expected_generation,params,row.pk,target=row.pk)


def set_stable(*,actor,page_id,version_id,view_receipt,expected_generation,operation_id):
    data=load_ticket(view_receipt,'view');params={'target':str(E.uid(version_id)),'view':data}
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        previous=E.replay(operation_id,'set_stable',actor,page,expected_generation,params)
        if previous:return previous
        row=E.revision(page,version_id)
        if data!={'action':'view','binding':_binding(actor,page,expected_generation),'stamp':E.stamp(page,row)}:raise ValidationError('VERSIONS_VIEW_CHANGED')
        if not RevisionProtection.objects.filter(revision=row).exists():
            RevisionProtection.objects.create(revision=row,marked_by_id=actor.pk,marked_at=E.now())
            E.move_usage(row,'ordinary_version','stable_version')
        # No schema restore validator, payload reinterpretation, current move or ordinary refill.
        return E.finish(operation_id,'set_stable',actor,page,expected_generation,params,row.pk,target=row.pk)


def composition(page,state):
    return {'current':str(state.current_revision_id),'versions':[
        {'id':str(row.pk),'created':row.created_at.isoformat(),'sequence':row.sequence,'stamp':E.stamp(page,row),
         'pins':sorted((pin.holder_kind,str(pin.holder_id)) for pin in row.base_pins.all()),
         'draft_base':OwnerDraft.objects.filter(base_revision=row).exists()}
        for row in PageRevision.objects.filter(page=page).defer('payload').order_by('id')]}


def prepare_demote(*,actor,page_id,version_id,expected_generation):
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        row=E.revision(page,version_id)
        if not RevisionProtection.objects.filter(revision=row).exists():raise ValidationError('VERSIONS_NOT_STABLE')
        data={'binding':_binding(actor,page,expected_generation),'target':str(row.pk),'composition':E.S.digest(composition(page,state)),'stamp':E.stamp(page,row)}
        return {'revision':row,'confirmation':ticket('demote',data)}


def demote_stable(*,actor,page_id,confirmation,password,expected_generation,operation_id):
    data=load_ticket(confirmation,'demote');params={'confirmation':data}
    # Expensive current-password hash verification outside content/auth transaction locks.
    user=get_user_model().objects.get(pk=actor.pk)
    if type(password) is not str or not 0<len(password)<=4096 or not check_password(password,user.password):raise PermissionDenied('VERSIONS_CURRENT_PASSWORD_REQUIRED')
    verified_password_hash=user.password
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        if profile.user.password!=verified_password_hash:raise PermissionDenied('VERSIONS_CURRENT_PASSWORD_CHANGED')
        previous=E.replay(operation_id,'demote_stable',actor,page,expected_generation,params)
        if previous:return previous
        row=E.revision(page,data['target'])
        if data['binding']!=_binding(actor,page,expected_generation) or data['stamp']!=E.stamp(page,row) or data['composition']!=E.S.digest(composition(page,state)):raise ValidationError('VERSIONS_CONFIRMATION_CHANGED')
        if not RevisionProtection.objects.filter(revision=row).exists():raise ValidationError('VERSIONS_NOT_STABLE')
        E.move_usage(row,'stable_version','ordinary_version');E.raw(RevisionProtection).filter(revision=row).delete()
        E.prune(page,state.current_revision_id,actor,operation_id)
        return E.finish(operation_id,'demote_stable',actor,page,expected_generation,params,row.pk,target=row.pk)


def prepare_delete(*,actor,page_id,version_id,expected_generation):
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        row=E.revision(page,version_id);_deletable(page,row,state)
        return {'revision':row,'metadata':RevisionMetadata.objects.get(revision=row),'confirmation':ticket('delete',{'binding':_binding(actor,page,expected_generation),'target':str(row.pk),'stamp':E.stamp(page,row)})}


def _deletable(page,row,state):
    if row.page_id!=page.pk or state.current_revision_id==row.pk or RevisionProtection.objects.filter(revision=row).exists() or VersionBasePin.objects.filter(revision=row).exists() or OwnerDraft.objects.filter(base_revision=row).exists():
        raise ValidationError('VERSIONS_REVISION_PROTECTED')


def delete_revision(*,actor,page_id,confirmation,expected_generation,operation_id):
    data=load_ticket(confirmation,'delete');params={'confirmation':data}
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation,owner=True)
        previous=E.replay(operation_id,'delete_revision',actor,page,expected_generation,params)
        if previous:return previous
        row=E.revision(page,data['target']);_deletable(page,row,state)
        if data['binding']!=_binding(actor,page,expected_generation) or data['stamp']!=E.stamp(page,row):raise ValidationError('VERSIONS_CONFIRMATION_CHANGED')
        E.remove_usage('ordinary_version',row.pk);E.raw(PageRevision).filter(pk=row.pk).delete()
        return E.finish(operation_id,'delete_revision',actor,page,expected_generation,params,data['target'],code='deleted',target=data['target'])
