"""Durable restriction primitive. No gate acknowledgement or site commit."""
import contextvars
import hashlib
import os
from contextlib import contextmanager
from django.db import connection, transaction
from . import auth
from .models import Head, Credential, Operation, RoutePolicy, RequestTombstone, RecoveryReceipt
from .protocol import Fault, MAX_INT, canonical, digest, validate

LOGICAL_CAP=64*1024*1024
COMPLETION_CAP=16*1024*1024
_test_mode=contextvars.ContextVar('trust_test_mode', default=False)

@contextmanager
def calibration_mode():
    """Explicit test-process scope, never an HTTP/environment write switch."""
    if os.environ.get('TRUST_TEST_EXECUTION')!='1' or connection.settings_dict['NAME']!='test_estakada_trust' or connection.vendor!='postgresql':
        raise Fault('TEST_SCOPE_REJECTED',503)
    token=_test_mode.set(True)
    try: yield
    finally: _test_mode.reset(token)

def write_gate(actor,body,phase,fingerprint):
    if _test_mode.get() and connection.settings_dict['NAME']=='test_estakada_trust': return None
    from .profile import check
    return check(actor,body,phase,fingerprint)

def head_dict(row):
    return {'incarnation':str(row.incarnation),'generation':str(row.generation),
        'writerEpoch':str(row.writer_epoch),'mode':row.mode,'digest':row.digest}

def locked(actor, incarnation=None, epoch=None):
    expected=auth.identity()
    try: row=Head.objects.select_for_update().get(pk=1)
    except Head.DoesNotExist: raise Fault('IDENTITY_UNAVAILABLE',503) from None
    if str(row.incarnation)!=expected or (incarnation is not None and incarnation!=expected): raise Fault('IDENTITY_MISMATCH',503)
    credential=Credential.objects.filter(pk=actor['id'],active=True).first()
    if not credential or credential.principal!=actor['principal'] or credential.role!=actor['role'] or credential.verifier!=actor['verifier']:
        raise Fault('CREDENTIAL_REVOKED',403)
    if actor['role']=='writer' and (credential.writer_epoch!=row.writer_epoch or (epoch is not None and int(epoch)!=row.writer_epoch)):
        raise Fault('WRITER_FENCED',403)
    return row

def durability():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('fsync'),current_setting('synchronous_commit'),current_setting('full_page_writes')")
        if cursor.fetchone()!=('on','on','on'): raise Fault('DURABILITY_UNAVAILABLE',503)

def bootstrap(incarnation):
    """Explicit initialization only; refuses every existing identity/record."""
    if incarnation!=auth.identity(): raise Fault('IDENTITY_MISMATCH',503)
    config=auth.configuration()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(374001)')
        if any(model.objects.exists() for model in (Head,Credential,Operation,RoutePolicy,RequestTombstone,RecoveryReceipt)):
            raise Fault('BOOTSTRAP_NOT_EMPTY',409)
        durability()
        Head.objects.create(incarnation=incarnation,digest=digest({'incarnation':incarnation,'generation':'0'}))
        for item in config.values():
            Credential.objects.create(id=item['id'],principal=item['principal'],role=item['role'],writer_epoch=1,
                verifier=hashlib.sha256(item['secret'].encode('ascii')).hexdigest())

def semantic(body, actor):
    return digest({'principal':actor['principal'],'credential':actor['id'],
        **{key:value for key,value in body.items() if key!='expectedGeneration'}})

def advance(head, body, fingerprint):
    if head.mode!='ACTIVE': raise Fault('TRUST_FROZEN',503)
    if head.generation!=int(body['expectedGeneration']): raise Fault('CAS_CONFLICT')
    if head.generation>=MAX_INT: raise Fault('GENERATION_EXHAUSTED',503)
    head.generation+=1
    head.digest=digest({'previous':head.digest,'generation':str(head.generation),'phase':fingerprint})

def result(op, head, phase, replay):
    return {'ok':True,'operationId':str(op.pk),'stage':op.stage,'replay':replay,
        'phaseReceipt':op.phases[phase]['receipt'],'head':head_dict(head),'workflowComplete':False}

def mutate(actor, body, phase):
    validate(body,phase)
    fingerprint=semantic(body,actor)
    permit_phase='prepare' if phase=='prepare' else body['outcome']
    permit=write_gate(actor,body,permit_phase,fingerprint)
    with transaction.atomic():
        head=locked(actor,body['incarnation'],body['writerEpoch']); durability()
        if permit is not None:
            from .profile import check_locked
            check_locked(permit,actor,body,permit_phase,fingerprint,head)
        op=Operation.objects.filter(pk=body['operationId']).first()
        phase_key='prepare' if phase=='prepare' else body['outcome']
        if op:
            if op.credential_id!=actor['id'] or op.writer_epoch!=head.writer_epoch: raise Fault('OPERATION_CONFLICT')
            saved=op.phases.get(phase_key)
            if saved:
                if saved['fingerprint']!=fingerprint: raise Fault('PHASE_CONFLICT')
                return result(op,head,phase_key,True)
        if phase=='prepare':
            if op: raise Fault('PREPARE_CONFLICT')
            # An unresolved restriction owns every affected identity, even when
            # a later proposal uses entirely different request-target keys.
            object_ids=sorted({body['objectId'],*(item['objectId'] for item in body['policies'])})
            with connection.cursor() as cursor:
                cursor.execute("""SELECT EXISTS (
                    SELECT 1 FROM journal_operation AS pending
                    WHERE pending.stage = ANY(%s)
                    AND (pending.object_id = ANY(%s::uuid[])
                      OR EXISTS (SELECT 1 FROM jsonb_array_elements(pending.payload->'policies') AS item
                                 WHERE item->>'objectId' = ANY(%s::text[]))))""",
                    [['PENDING_DENY','MAIN_RESULT_UNKNOWN','RECONCILE_REQUIRED'],object_ids,object_ids])
                if cursor.fetchone()[0]: raise Fault('OBJECT_PENDING')
            targets=[hashlib.sha256(item['target'].encode('utf-8')).hexdigest() for item in body['policies']]
            existing=list(RoutePolicy.objects.filter(key__in=targets).select_related('operation'))
            if any(row.operation.stage in ('PENDING_DENY','MAIN_RESULT_UNKNOWN','RECONCILE_REQUIRED') for row in existing): raise Fault('POLICY_PENDING')
            for row in existing:
                if row.target not in {item['target'] for item in body['policies']}: raise Fault('TARGET_HASH_COLLISION',503)
            if RequestTombstone.objects.filter(request_id__in=body['requestIds']).exists(): raise Fault('REQUEST_ID_REUSED')
            size=len(canonical(body))+4096
            reserve=len(canonical(body['policies']))+8192
            with connection.cursor() as cursor:
                cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
                reference_count=int(cursor.fetchone()[0])
            if Operation.objects.count()>=10000 or RequestTombstone.objects.count()+len(body['requestIds'])>10000 or reference_count+len(targets)>50000:
                raise Fault('COUNT_CAP_REACHED',503)
            if head.logical_bytes+size>LOGICAL_CAP or head.reserved_bytes+reserve>COMPLETION_CAP: raise Fault('BUDGET_EXHAUSTED',503)
            advance(head,body,fingerprint)
            op=Operation.objects.create(id=body['operationId'],credential_id=actor['id'],principal=actor['principal'],
                writer_epoch=head.writer_epoch,kind=body['kind'],object_id=body['objectId'],prepare_fingerprint=fingerprint,
                payload=body,logical_bytes=size,reserve_bytes=reserve)
            for item,key in zip(body['policies'],targets):
                RoutePolicy.objects.update_or_create(key=key,defaults={'target':item['target'],'object_id':item['objectId'],
                    'operation':op,'generation':head.generation,'policy':'PENDING_DENY','redirect_target':None})
            for request_id in body['requestIds']:
                RequestTombstone.objects.create(request_id=request_id,operation=op,generation=head.generation)
            head.logical_bytes+=size; head.reserved_bytes+=reserve
        else:
            if not op: raise Fault('OPERATION_NOT_PREPARED')
            if op.terminal_fingerprint is not None: raise Fault('TERMINAL_IMMUTABLE')
            if body['outcome']=='committed' and body['policies']!=op.payload['policies']: raise Fault('POLICY_SET_MISMATCH')
            advance(head,body,fingerprint)
            if body['outcome']=='unknown': op.stage='MAIN_RESULT_UNKNOWN'
            else:
                op.stage='FINAL_RESTRICTION' if body['outcome']=='committed' else 'RECONCILE_REQUIRED'
                op.terminal_fingerprint=fingerprint
                if body['outcome']=='committed':
                    for item in body['policies']:
                        key=hashlib.sha256(item['target'].encode('utf-8')).hexdigest()
                        if RoutePolicy.objects.filter(pk=key,operation=op,target=item['target'],object_id=item['objectId']).update(
                            policy=item['policy'],redirect_target=item['redirectTarget'],generation=head.generation)!=1:
                            raise Fault('POLICY_BINDING_UNAVAILABLE',503)
                head.reserved_bytes-=op.reserve_bytes
                # Completion allocations remain charged permanently, not reclaimed by age.
                head.logical_bytes+=op.reserve_bytes
                op.logical_bytes+=op.reserve_bytes; op.reserve_bytes=0
        receipt={'generation':str(head.generation),'fingerprint':fingerprint,'stage':op.stage}
        op.phases={**op.phases,phase_key:{'fingerprint':fingerprint,'receipt':receipt}}
        op.save(); head.save()
        response=result(op,head,phase_key,False)
    return response

def read_head(actor):
    with transaction.atomic(): return head_dict(locked(actor))

def operation_status(actor, operation_id):
    with transaction.atomic():
        head=locked(actor)
        op=Operation.objects.filter(pk=operation_id).first()
        return {'head':head_dict(head),'operation':None if op is None else {'operationId':str(op.pk),'stage':op.stage,'phases':op.phases}}

def _snapshot_item(kind,row):
    item={'type':kind,**row}
    for key in ('object_id','request_id','tombstone_id','generation'):
        if key in item: item[key]=str(item[key])
    return item

def _snapshot_items():
    for row in RoutePolicy.objects.order_by('key').values('key','target','object_id','generation','policy','redirect_target').iterator(chunk_size=32):
        yield _snapshot_item('route',row)
    for row in RequestTombstone.objects.order_by('request_id').values('request_id','tombstone_id','generation').iterator(chunk_size=32):
        yield _snapshot_item('tombstone',row)

def snapshot_manifest(actor):
    with transaction.atomic():
        head=locked(actor)
        routes=RoutePolicy.objects.count();tombs=RequestTombstone.objects.count()
        if routes>50000 or tombs>10000: raise Fault('SNAPSHOT_BOUND_EXCEEDED',503)
        hasher=hashlib.sha256();hasher.update(b'[');size=2;count=0
        for item in _snapshot_items():
            raw=canonical(item)
            size+=len(raw)+(1 if count else 0)
            if size>64*1024*1024: raise Fault('SNAPSHOT_BOUND_EXCEEDED',503)
            if count: hasher.update(b',')
            hasher.update(raw);count+=1
        if count!=routes+tombs: raise Fault('SNAPSHOT_UNAVAILABLE',503)
        hasher.update(b']')
        return {'protocolVersion':1,'head':head_dict(head),
            'counts':{'routes':routes,'tombstones':tombs,'items':count},'snapshotDigest':hasher.hexdigest()}

def snapshot(actor, generation=None, cursor=0):
    with transaction.atomic():
        head=locked(actor)
        if generation is not None and generation!=str(head.generation): raise Fault('SNAPSHOT_CHANGED')
        # Stable typed ordering; never OFFSET across a changed generation.
        route_count=RoutePolicy.objects.count()
        total=route_count+RequestTombstone.objects.count()
        route_start=min(cursor,route_count)
        routes=list(RoutePolicy.objects.order_by('key').values('key','target','object_id','generation','policy','redirect_target')[route_start:min(cursor+100,route_count)]) if cursor<route_count else []
        remaining=100-len(routes)
        tomb_start=max(0,cursor-route_count)
        tombs=list(RequestTombstone.objects.order_by('request_id').values('request_id','tombstone_id','generation')[tomb_start:tomb_start+remaining]) if remaining else []
        page=[_snapshot_item('route',row) for row in routes]+[_snapshot_item('tombstone',row) for row in tombs]
        return {'head':head_dict(head),'cursor':cursor,'items':page,'pageDigest':digest(page),'nextCursor':cursor+100 if cursor+100<total else None}

def physical_facts():
    """Measured PG relations including indexes/TOAST; not logical-budget proof."""
    roots=[model._meta.db_table for model in (Head,Credential,Operation,RoutePolicy,RequestTombstone,RecoveryReceipt)]
    with connection.cursor() as cursor:
        cursor.execute('SELECT name,pg_total_relation_size(name::regclass) FROM unnest(%s::text[]) AS name',[roots])
        relations={name:int(size) for name,size in cursor.fetchall()}
        cursor.execute('SELECT pg_database_size(current_database())')
        total=cursor.fetchone()[0]
    return {'relations':relations,'relationBytes':sum(relations.values()),'databaseBytes':int(total),'profileVerified':False}
