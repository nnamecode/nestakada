"""Local synthetic writer fencing. Does not reconcile APP or remove a deny."""
import hashlib
import re
import uuid
from django.conf import settings
from django.db import transaction
from . import auth, services as S
from .models import Credential, Operation, RoutePolicy, RequestTombstone, RecoveryReceipt
from .protocol import Fault, MAX_INT, canonical, closed, digest, integer, uid

def receipt_digest(receipt): return digest(receipt)

def state_digest(head):
    # Only the admitted finite plan can use this function in runtime recovery.
    # At most 16 bootstrap bindings plus four admitted actions can add bindings.
    if Credential.objects.count()>20 or Operation.objects.count()>16 or RecoveryReceipt.objects.count()>4 or RoutePolicy.objects.count()>4096 or RequestTombstone.objects.count()>4096:
        raise Fault('RECONCILIATION_UNAVAILABLE',503)
    def rows(model,fields,order):
        values=list(model.objects.order_by(order).values(*fields))
        for row in values:
            for key,value in row.items():
                if isinstance(value,uuid.UUID): row[key]=str(value)
        return values
    persistent_head={field.attname:getattr(head,field.attname) for field in head._meta.concrete_fields}
    persistent_head={key:str(value) if isinstance(value,uuid.UUID) else value for key,value in persistent_head.items()}
    return digest({'head':persistent_head,
        # Verifiers participate only inside this digest, never the wire response.
        'credentials':rows(Credential,['id','principal','role','verifier','writer_epoch','active'],'id'),
        'operations':rows(Operation,['id','credential_id','principal','writer_epoch','kind','object_id','prepare_fingerprint','payload','stage','terminal_fingerprint','phases','logical_bytes','reserve_bytes'],'id'),
        'routes':rows(RoutePolicy,['key','target','object_id','operation_id','generation','policy','redirect_target'],'key'),
        'tombstones':rows(RequestTombstone,['request_id','tombstone_id','operation_id','generation'],'request_id'),
        'recovery':rows(RecoveryReceipt,['id','credential_id','principal','action','fingerprint','receipt','logical_bytes'],'id')})

def validate(body,action):
    closed(body,{'actionId','incarnation','expectedGeneration','writerEpoch','scope','previousCredentialId','newCredentialId','fenceActionId','reconciliationDigest'})
    uid(body['actionId']); uid(body['incarnation']); integer(body['expectedGeneration']); integer(body['writerEpoch'])
    if body['scope'] not in ('LOCAL_TRUST_TEST_ONLY','LOCAL_TRUST_BOUNDED_WRITER'): raise Fault('INPUT_REJECTED',400)
    if type(body['previousCredentialId']) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,64}',body['previousCredentialId']): raise Fault('INPUT_REJECTED',400)
    if action=='fence':
        if any(body[key] is not None for key in ('newCredentialId','fenceActionId','reconciliationDigest')): raise Fault('INPUT_REJECTED',400)
    else:
        uid(body['fenceActionId'])
        if type(body['newCredentialId']) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,64}',body['newCredentialId']) or type(body['reconciliationDigest']) is not str or not re.fullmatch('[0-9a-f]{64}',body['reconciliationDigest']): raise Fault('INPUT_REJECTED',400)
    return body

def mutate(actor,body,action):
    from .profile import check, check_locked
    validate(body,action)
    expected_scope={'local-test-permit':'LOCAL_TRUST_TEST_ONLY',
        'local-bounded-writer':'LOCAL_TRUST_BOUNDED_WRITER'}.get(settings.TRUST_WRITE_PROFILE)
    if expected_scope is not None and body['scope']!=expected_scope:
        raise Fault('INPUT_REJECTED',400)
    fingerprint=S.semantic(body,actor)
    permit=check(actor,body,action,fingerprint)
    with transaction.atomic():
        head=S.locked(actor,body['incarnation']); S.durability()
        payload=check_locked(permit,actor,body,action,fingerprint,head)
        existing=RecoveryReceipt.objects.filter(pk=body['actionId']).first()
        if existing:
            if existing.credential_id!=actor['id'] or existing.principal!=actor['principal'] or existing.action!=action or existing.fingerprint!=fingerprint:
                raise Fault('RECOVERY_REPLAY_CONFLICT')
            return {'ok':True,'replay':True,'recoveryReceipt':existing.receipt,'head':S.head_dict(head),'workflowComplete':False}
        if head.generation!=integer(body['expectedGeneration']) or head.writer_epoch!=integer(body['writerEpoch']): raise Fault('CAS_CONFLICT')
        if head.generation==MAX_INT: raise Fault('GENERATION_EXHAUSTED',503)
        if RecoveryReceipt.objects.count()>=4: raise Fault('RECOVERY_COUNT_CAP',503)
        previous=Credential.objects.filter(pk=body['previousCredentialId'],role='writer').first()
        if previous is None: raise Fault('RECOVERY_PRECONDITION_FAILED')
        if action=='fence':
            if head.mode!='ACTIVE' or not previous.active or previous.writer_epoch!=head.writer_epoch or head.writer_epoch==MAX_INT: raise Fault('RECOVERY_PRECONDITION_FAILED')
            # Revoke every current writer: a second binding cannot survive fencing.
            Credential.objects.filter(role='writer',active=True).update(active=False)
            head.writer_epoch+=1; head.mode='FROZEN'
        else:
            proof=payload['reconciliation']
            if type(proof) is not dict: raise Fault('RECOVERY_PRECONDITION_FAILED')
            working=body['scope']=='LOCAL_TRUST_BOUNDED_WRITER'
            proof_fields={'fenceActionId','fenceReceiptDigest','head','stateDigest','runtimeId','credentialConfigSha256','exclusion'}
            closed(proof,proof_fields|({'stateDigestVersion'} if working else set()))
            if working and (type(proof['stateDigestVersion']) is not int or proof['stateDigestVersion']!=2):
                raise Fault('RECOVERY_PRECONDITION_FAILED')
            fence=RecoveryReceipt.objects.filter(pk=body['fenceActionId'],action='fence').first()
            if head.mode!='FROZEN' or previous.active or fence is None or fence.receipt['previousCredentialId']!=previous.pk:
                raise Fault('RECOVERY_PRECONDITION_FAILED')
            if Credential.objects.filter(role='writer',active=True).exists(): raise Fault('RECOVERY_PRECONDITION_FAILED')
            if working:
                from .state_v2 import state_digest as state_digest_v2
                actual=state_digest_v2(head)
            else: actual=state_digest(head)
            expected_proof={'fenceActionId':body['fenceActionId'],'fenceReceiptDigest':receipt_digest(fence.receipt),
                'head':S.head_dict(head),'stateDigest':actual,'runtimeId':settings.TRUST_RUNTIME_ID,
                'credentialConfigSha256':payload['credentialConfigSha256'],'exclusion':proof['exclusion']}
            if working: expected_proof['stateDigestVersion']=2
            if proof!=expected_proof or body['reconciliationDigest']!=actual:
                raise Fault('RECOVERY_PRECONDITION_FAILED')
            if proof['exclusion']['previousRuntimeId']!=fence.receipt['runtimeId'] or proof['exclusion']['newRuntimeId']!=settings.TRUST_RUNTIME_ID: raise Fault('RECOVERY_PRECONDITION_FAILED')
            if settings.TRUST_RUNTIME_ID==fence.receipt['runtimeId']: raise Fault('RECOVERY_PRECONDITION_FAILED')
            config=auth.configuration(); item=config.get(body['newCredentialId'])
            if item is None or item['role']!='writer' or Credential.objects.filter(pk=item['id']).exists(): raise Fault('RECOVERY_PRECONDITION_FAILED')
            verifier=hashlib.sha256(item['secret'].encode('ascii')).hexdigest()
            if verifier==previous.verifier: raise Fault('RECOVERY_PRECONDITION_FAILED')
            if working and Credential.objects.count()>=payload['caps']['maxCredentials']:
                raise Fault('CREDENTIAL_COUNT_CAP',503)
            Credential.objects.create(id=item['id'],principal=item['principal'],role='writer',verifier=verifier,writer_epoch=head.writer_epoch,active=True)
            head.mode='ACTIVE'
        head.generation+=1
        head.digest=digest({'previous':head.digest,'generation':str(head.generation),'phase':fingerprint})
        receipt={'actionId':body['actionId'],'action':action,'fingerprint':fingerprint,'head':S.head_dict(head),
            'previousCredentialId':body['previousCredentialId'],'newCredentialId':body['newCredentialId'],
            'runtimeId':settings.TRUST_RUNTIME_ID,'scope':body['scope'],'workflowComplete':False}
        size=len(canonical(receipt))+1024
        if size>16384 or head.logical_bytes+size>S.LOGICAL_CAP: raise Fault('BUDGET_EXHAUSTED',503)
        if body['scope']=='LOCAL_TRUST_BOUNDED_WRITER' and head.logical_bytes+head.reserved_bytes+size>S.LOGICAL_CAP:
            raise Fault('BUDGET_EXHAUSTED',503)
        RecoveryReceipt.objects.create(id=body['actionId'],credential_id=actor['id'],principal=actor['principal'],
            action=action,fingerprint=fingerprint,receipt=receipt,logical_bytes=size)
        head.logical_bytes+=size; head.save()
        response={'ok':True,'replay':False,'recoveryReceipt':receipt,'head':S.head_dict(head),'workflowComplete':False}
    return response
