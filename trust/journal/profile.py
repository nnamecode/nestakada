"""A finite, operator-signed local experiment, never a general write profile."""
import hashlib
import hmac
import os
import stat
from pathlib import Path
from django.conf import settings
from django.db import connection
from . import auth
from .models import AdmissionPolicy, Operation, RoutePolicy, RequestTombstone, RecoveryReceipt
from .protocol import Fault, canonical, closed, digest, integer, parse, uid

CAPS={'logicalBytes':67108864,'completionBytes':16777216,'maxOperations':16,
    'maxRecoveryActions':4,'maxMessageBytes':1048576,'maxTargets':256}
ROOT=Path(__file__).resolve().parent.parent
CGROUP_ROOT=Path('/sys/fs/cgroup')
DEPLOYMENT={'api':{'memoryBytes':268435456,'nanoCpus':500000000,'pids':64},
    'db':{'memoryBytes':536870912,'nanoCpus':500000000,'pids':128},
    'ingress':{'memoryBytes':134217728,'nanoCpus':250000000,'pids':64}}
TABLES=('journal_head','journal_credential','journal_operation','journal_routepolicy',
    'journal_requesttombstone','journal_recoveryreceipt','journal_admissionpolicy')

def source_files():
    rows=[]
    for path in sorted(ROOT.rglob('*.py')):
        if path.is_symlink(): raise Fault('PERMIT_SOURCE_MISMATCH',503)
        rows.append({'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return sorted(rows,key=lambda row:row['path'])

def source_fingerprint(): return digest(source_files())

def runtime_resource_facts():
    """Own cgroup only; DB/ingress configuration is operator-attested."""
    try:
        memory=(CGROUP_ROOT/'memory.max').read_text(encoding='ascii').strip()
        cpu=(CGROUP_ROOT/'cpu.max').read_text(encoding='ascii').split()
        pids=(CGROUP_ROOT/'pids.max').read_text(encoding='ascii').strip()
        if not memory.isdecimal() or not pids.isdecimal() or len(cpu)!=2 or not all(value.isdecimal() for value in cpu): raise ValueError()
        quota,period=map(int,cpu)
        if quota<=0 or period<=0 or quota*1000000000 % period: raise ValueError()
        facts={'memoryBytes':int(memory),'nanoCpus':quota*1000000000//period,'pids':int(pids)}
        if facts!=DEPLOYMENT['api']: raise ValueError()
        return facts
    except (OSError,UnicodeError,ValueError): raise Fault('WRITE_PROFILE_RESOURCE_MISMATCH',503) from None

def schema_fingerprint():
    """Full named catalog, trigger function bodies and migration ledger."""
    with connection.cursor() as cursor:
        cursor.execute('''SELECT c.relname,n.nspname,a.attnum,a.attname,
            format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_get_expr(d.adbin,d.adrelid)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
            LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
            WHERE c.oid=ANY(ARRAY(SELECT x::regclass FROM unnest(%s::text[]) x))
            ORDER BY c.relname,a.attnum''',[list(TABLES)])
        columns=cursor.fetchall()
        cursor.execute('''SELECT c.relname,k.conname,pg_get_constraintdef(k.oid,true)
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            WHERE c.oid=ANY(ARRAY(SELECT x::regclass FROM unnest(%s::text[]) x))
            ORDER BY c.relname,k.conname''',[list(TABLES)])
        constraints=cursor.fetchall()
        cursor.execute('''SELECT c.relname,i.relname,pg_get_indexdef(i.oid)
            FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid
            WHERE c.oid=ANY(ARRAY(SELECT x::regclass FROM unnest(%s::text[]) x))
            ORDER BY c.relname,i.relname''',[list(TABLES)])
        indexes=cursor.fetchall()
        cursor.execute('''SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid,true),pg_get_functiondef(t.tgfoid)
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            WHERE NOT t.tgisinternal AND c.oid=ANY(ARRAY(SELECT x::regclass FROM unnest(%s::text[]) x))
            ORDER BY c.relname,t.tgname''',[list(TABLES)])
        triggers=cursor.fetchall()
        cursor.execute("SELECT app,name FROM django_migrations ORDER BY app,name")
        migrations=cursor.fetchall()
    if {row[0] for row in columns}!=set(TABLES) or migrations!=[('journal','0001_initial'),('journal','0002_local_test_recovery'),('journal','0003_admission_policy')]:
        raise Fault('PERMIT_SCHEMA_MISMATCH',503)
    return digest({'columns':columns,'constraints':constraints,'indexes':indexes,'triggers':triggers,'migrations':migrations})

def _hex(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value) and value!='0'*64

def _unique_ids(values,maximum):
    if type(values) is not list or len(values)>maximum: raise Fault('PERMIT_INVALID',503)
    for value in values: uid(value)
    if len(set(values))!=len(values): raise Fault('PERMIT_INVALID',503)

def _read():
    try:
        path=settings.TRUST_WRITE_PERMIT_FILE
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size>65536: raise ValueError()
            raw=os.read(fd,65537)
            if len(raw)>65536: raise ValueError()
        finally: os.close(fd)
        envelope=parse(raw); closed(envelope,{'payload','signature'})
        payload=envelope['payload']
        closed(payload,{'schemaVersion','scope','planId','dbName','incarnation','protocolVersion','sourceFiles',
            'sourceFingerprint','schemaFingerprint','evidence','caps','operationIds','recoveryActionIds','requests',
            'runtimeId','credentialConfigSha256','reconciliation','deployment'})
        recovery=[item for item in auth.configuration().values() if item['role']=='recovery']
        if len(recovery)!=1 or not _hex(envelope['signature']): raise ValueError()
        signature=hmac.new(bytes.fromhex(recovery[0]['secret']),canonical(payload),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,envelope['signature']): raise ValueError()
        if type(payload['schemaVersion']) is not int or payload['schemaVersion']!=1 or type(payload['protocolVersion']) is not int or payload['protocolVersion']!=1 or payload['scope']!='LOCAL_TRUST_TEST_ONLY': raise ValueError()
        uid(payload['planId']); uid(payload['incarnation']); uid(payload['runtimeId'])
        if payload['dbName']!=connection.settings_dict['NAME'] or payload['dbName'] not in ('estakada_trust','test_estakada_trust'): raise ValueError()
        if payload['runtimeId']!=settings.TRUST_RUNTIME_ID or payload['incarnation']!=auth.identity(): raise ValueError()
        if payload['caps']!=CAPS or any(type(value) is not int for value in payload['caps'].values()): raise ValueError()
        deployment=payload['deployment']; closed(deployment,{'api','db','ingress','configFingerprint','evidence'})
        for component,limits in DEPLOYMENT.items():
            closed(deployment[component],{'memoryBytes','nanoCpus','pids'})
            if deployment[component]!=limits or any(type(value) is not int for value in deployment[component].values()): raise ValueError()
        if not _hex(deployment['configFingerprint']) or not _hex(deployment['evidence']): raise ValueError()
        runtime_resource_facts()
        closed(payload['evidence'],{'unit','calibration','review'})
        if not all(_hex(value) for value in payload['evidence'].values()) or not _hex(payload['schemaFingerprint']): raise ValueError()
        rows=source_files()
        if payload['sourceFiles']!=rows or payload['sourceFingerprint']!=digest(rows): raise ValueError()
        if payload['credentialConfigSha256']!=hashlib.sha256(Path(settings.TRUST_CREDENTIALS_FILE).read_bytes()).hexdigest(): raise ValueError()
        proof=payload['reconciliation']
        if proof is not None:
            closed(proof,{'fenceActionId','fenceReceiptDigest','head','stateDigest','runtimeId','credentialConfigSha256','exclusion'})
            uid(proof['fenceActionId']); uid(proof['runtimeId'])
            if not all(_hex(proof[key]) for key in ('fenceReceiptDigest','stateDigest','credentialConfigSha256')): raise ValueError()
            closed(proof['head'],{'incarnation','generation','writerEpoch','mode','digest'})
            uid(proof['head']['incarnation']); integer(proof['head']['generation']); integer(proof['head']['writerEpoch'])
            if proof['head']['mode'] not in ('ACTIVE','FROZEN') or not _hex(proof['head']['digest']): raise ValueError()
            exclusion=proof['exclusion']
            closed(exclusion,{'previousRuntimeId','previousContainerId','newRuntimeId','newContainerId','evidenceSha256'})
            uid(exclusion['previousRuntimeId']); uid(exclusion['newRuntimeId'])
            if not all(_hex(exclusion[key]) for key in ('previousContainerId','newContainerId','evidenceSha256')): raise ValueError()
            if exclusion['previousRuntimeId']==exclusion['newRuntimeId'] or exclusion['previousContainerId']==exclusion['newContainerId'] or exclusion['newRuntimeId']!=payload['runtimeId']: raise ValueError()
        _unique_ids(payload['operationIds'],16); _unique_ids(payload['recoveryActionIds'],4)
        if set(payload['operationIds']) & set(payload['recoveryActionIds']): raise ValueError()
        if type(payload['requests']) is not list or len(payload['requests'])>128: raise ValueError()
        seen=set()
        for request in payload['requests']:
            closed(request,{'id','credentialId','writerEpoch','phase','fingerprint'})
            uid(request['id']); integer(request['writerEpoch'])
            if type(request['credentialId']) is not str or request['credentialId'] not in auth.configuration() or not _hex(request['fingerprint']): raise ValueError()
            phase=request['phase']
            if type(phase) is not str or phase not in ('prepare','unknown','committed','aborted','fence','activate'): raise ValueError()
            ids=payload['recoveryActionIds'] if phase in ('fence','activate') else payload['operationIds']
            if request['id'] not in ids: raise ValueError()
            key=tuple(request[k] for k in ('id','credentialId','writerEpoch','phase','fingerprint'))
            if key in seen: raise ValueError()
            seen.add(key)
        return envelope
    except (OSError,ValueError,TypeError,AttributeError,Fault,RecursionError):
        raise Fault('WRITE_PERMIT_REJECTED',503) from None

def check(actor,body,phase,fingerprint):
    if settings.TRUST_WRITE_PROFILE=='local-bounded-writer':
        from .bounded import check as bounded_check
        return bounded_check(actor,body,phase,fingerprint)
    if settings.TRUST_WRITE_PROFILE!='local-test-permit': raise Fault('WRITE_PROFILE_DISABLED',503)
    envelope=_read(); payload=envelope['payload']
    operation_id=body.get('operationId',body.get('actionId'))
    candidate={'id':operation_id,'credentialId':actor['id'],'writerEpoch':body['writerEpoch'],'phase':phase,'fingerprint':fingerprint}
    if candidate not in payload['requests']: raise Fault('WRITE_PERMIT_SCOPE_REJECTED',403)
    return envelope

def check_locked(envelope,actor,body,phase,fingerprint,head):
    if settings.TRUST_WRITE_PROFILE=='local-bounded-writer':
        from .bounded import check_locked as bounded_check_locked
        return bounded_check_locked(envelope,actor,body,phase,fingerprint,head)
    # The caller already holds Head: no mode/file downgrade revives the trial.
    if AdmissionPolicy.objects.exists(): raise Fault('WRITE_TRIAL_RETIRED',503)
    fresh=check(actor,body,phase,fingerprint)
    if canonical(fresh)!=canonical(envelope): raise Fault('WRITE_PERMIT_CHANGED',503)
    payload=fresh['payload']
    if str(head.incarnation)!=payload['incarnation'] or schema_fingerprint()!=payload['schemaFingerprint']: raise Fault('PERMIT_SCHEMA_MISMATCH',503)
    operations=sorted(payload['operationIds']); actions=sorted(payload['recoveryActionIds'])
    if head.plan_id is None:
        if Operation.objects.exists() or RoutePolicy.objects.exists() or RequestTombstone.objects.exists() or RecoveryReceipt.objects.exists(): raise Fault('PERMIT_DATABASE_NOT_EMPTY',503)
        head.plan_id=payload['planId']; head.permitted_operations=operations; head.permitted_recovery_actions=actions
    elif str(head.plan_id)!=payload['planId'] or head.permitted_operations!=operations or head.permitted_recovery_actions!=actions:
        raise Fault('PERMIT_PLAN_MISMATCH',503)
    if Operation.objects.exclude(pk__in=operations).exists() or RecoveryReceipt.objects.exclude(pk__in=actions).exists(): raise Fault('PERMIT_STATE_MISMATCH',503)
    return payload
