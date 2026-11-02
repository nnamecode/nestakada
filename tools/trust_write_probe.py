"""Closed synthetic TRUST observer/TLS probe, executed in the existing API role.

The caller supplies ACTION and ARG through its closed stdin launcher. No raw
credential, verifier, request payload, SQL text or exception is returned.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import ssl
import time
import uuid
from urllib.parse import parse_qs, urlsplit

import django

ORIGIN_HOST='trust-ingress'
ORIGIN_PORT=8443
MAX_BYTES=1048576

def ensure(condition,code):
    if not condition: raise RuntimeError(code)

def setup():
    ensure(os.environ.get('TRUST_DB_HOST')=='trust-db' and os.environ.get('TRUST_DB_NAME')=='estakada_trust'
        and os.environ.get('TRUST_DB_USER')=='trust_runtime','PROBE_DATABASE_SCOPE')
    ensure(os.environ.get('DJANGO_SETTINGS_MODULE')=='trust_service.settings','PROBE_SETTINGS_SCOPE')
    django.setup()

def typed(value):
    if isinstance(value,uuid.UUID): return str(value)
    if isinstance(value,dict): return {key:typed(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)): return [typed(item) for item in value]
    return value

def configuration():
    from journal.auth import configuration as load
    return load()

def actor_for(credential_id,role):
    from journal.auth import authenticate
    item=configuration().get(credential_id)
    ensure(item is not None,'PROBE_CREDENTIAL_UNKNOWN')
    return authenticate('Bearer '+item['id']+':'+item['secret'],role)

def facts():
    from django.db import connection,transaction
    from journal import profile as P,recovery as R,services as S
    from journal.models import Head,Credential,Operation,RoutePolicy,RequestTombstone,RecoveryReceipt
    rows=P.source_files()
    config=configuration()
    readers=[item for item in config.values() if item['role']=='reader']
    ensure(len(readers)==1,'PROBE_READER_SCOPE')
    reader=actor_for(readers[0]['id'],'reader')
    config_sha=hashlib.sha256(Path('/run/secrets/credentials.json').read_bytes()).hexdigest()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(),current_user')
            ensure(cursor.fetchone()==('estakada_trust','trust_runtime'),'PROBE_SQL_IDENTITY')
        head=S.locked(reader)
        counts={name:model.objects.count() for name,model in (
            ('head',Head),('credentials',Credential),('operations',Operation),('policies',RoutePolicy),
            ('tombstones',RequestTombstone),('recoveryReceipts',RecoveryReceipt))}
        ensure(counts['head']==1 and counts['credentials']<=20 and counts['operations']<=16
            and counts['policies']<=4096 and counts['tombstones']<=4096 and counts['recoveryReceipts']<=4,'PROBE_FINITE_PLAN_SCOPE')
        persistent_head=typed({field.attname:getattr(head,field.attname) for field in head._meta.concrete_fields})
        operations=[]
        for row in Operation.objects.order_by('id').values('id','credential_id','writer_epoch','kind','object_id',
                'prepare_fingerprint','stage','terminal_fingerprint','phases','logical_bytes','reserve_bytes'):
            row=typed(row);row['writer_epoch']=str(row['writer_epoch']);operations.append(row)
        receipts=[]
        for row in RecoveryReceipt.objects.order_by('id'):
            receipts.append({'actionId':str(row.pk),'action':row.action,'fingerprint':row.fingerprint,
                'receipt':row.receipt,'receiptDigest':R.receipt_digest(row.receipt),'logicalBytes':row.logical_bytes})
        result={'status':'PASS','scope':'LOCAL_TRUST_TEST_ONLY','head':S.head_dict(head),
            'persistentHead':persistent_head,'counts':counts,'stateDigest':R.state_digest(head),
            'sourceFiles':rows,'sourceFingerprint':P.digest(rows),'schemaFingerprint':P.schema_fingerprint(),
            'credentialConfigSha256':config_sha,'runtimeId':os.environ.get('TRUST_RUNTIME_ID'),
            'credentials':list(Credential.objects.order_by('id').values('id','principal','role','writer_epoch','active')),
            'operations':operations,'recoveryReceipts':receipts,'physical':S.physical_facts(),
            'ownResources':P.runtime_resource_facts(),'workflowComplete':False}
    # All bigints on the wire remain strings even for future larger counters.
    for field in ('generation','writer_epoch','logical_bytes','reserved_bytes'):
        result['persistentHead'][field]=str(result['persistentHead'][field])
    for credential in result['credentials']: credential['writer_epoch']=str(credential['writer_epoch'])
    result['counts']={'operations':counts['operations'],'routes':counts['policies'],
        'tombstones':counts['tombstones'],'recovery':counts['recoveryReceipts']}
    result['logicalBytes']=head.logical_bytes;result['reservedBytes']=head.reserved_bytes
    for row in result['operations']: row['operationId']=row.pop('id')
    return result

def target(path,method):
    ensure(type(path) is str and len(path)<=512,'PROBE_TARGET_BOUND')
    parsed=urlsplit(path)
    ensure(not parsed.scheme and not parsed.netloc and not parsed.fragment and parsed.path.startswith('/v1/'),'PROBE_TARGET_SCOPE')
    reads=('/v1/head','/v1/snapshot')
    writes=('/v1/prepare','/v1/report-result','/v1/recovery/fence','/v1/recovery/activate')
    operation=re.fullmatch(r'/v1/operations/([0-9a-f-]{36})',parsed.path)
    if operation: ensure(str(uuid.UUID(operation.group(1)))==operation.group(1),'PROBE_UUID_SCOPE')
    ensure((method=='GET' and (parsed.path in reads or operation)) or (method=='POST' and parsed.path in writes),'PROBE_METHOD_TARGET_SCOPE')
    if parsed.query:
        ensure(parsed.path=='/v1/snapshot' and method=='GET','PROBE_QUERY_SCOPE')
        values=parse_qs(parsed.query,strict_parsing=True,max_num_fields=2)
        ensure(set(values)<={'generation','cursor'} and all(len(items)==1 and re.fullmatch('0|[1-9][0-9]{0,18}',items[0]) for items in values.values()),'PROBE_QUERY_SCOPE')
    return path

def independent(body):
    from django.db import connection
    from journal.models import Operation,RecoveryReceipt
    if type(body) is not dict: return {'status':'NOT_APPLICABLE'}
    identifier=body.get('operationId',body.get('actionId'))
    try: ensure(str(uuid.UUID(identifier))==identifier,'PROBE_UUID_SCOPE')
    except (TypeError,ValueError,RuntimeError): return {'status':'NOT_APPLICABLE'}
    deadline=time.monotonic()+5
    while True:
        try:
            if 'operationId' in body:
                row=Operation.objects.filter(pk=identifier).values('id','stage','prepare_fingerprint','terminal_fingerprint','phases').first()
                record=typed(row)
            else:
                row=RecoveryReceipt.objects.filter(pk=identifier).values('id','action','fingerprint','receipt').first()
                record=typed(row)
            if record is not None: return {'status':'OBSERVED_RECORD','record':record}
        except Exception:
            connection.close()
            return {'status':'DATABASE_UNAVAILABLE','outcomeKnown':False}
        if time.monotonic()>=deadline: return {'status':'NOT_OBSERVED','outcomeKnown':False}
        time.sleep(0.1)

def request(arg):
    from journal.protocol import canonical,closed,parse
    closed(arg,{'credentialId','path','body','dropBody'})
    ensure(type(arg['dropBody']) is bool,'PROBE_REQUEST_SCHEMA')
    body=arg['body'];method='GET' if body is None else 'POST'
    url=target(arg['path'],method)
    ensure((method=='GET' and not arg['dropBody']) or (method=='POST' and type(body) is dict),'PROBE_REQUEST_BODY_SCOPE')
    item=configuration().get(arg['credentialId']);ensure(item is not None,'PROBE_CREDENTIAL_UNKNOWN')
    data=canonical(body) if body is not None else None
    ensure(data is None or len(data)<=MAX_BYTES,'PROBE_BODY_BOUND')
    context=ssl.create_default_context(cafile='/run/secrets/ingress-ca')
    connection=http.client.HTTPSConnection(ORIGIN_HOST,ORIGIN_PORT,timeout=2,context=context)
    sent=False;status=None;parsed=None;headers=None;transport='RESPONSE_RECEIVED'
    try:
        connection.connect()
        # Two seconds for connect was enforced explicitly; response phase is six.
        connection.sock.settimeout(6)
        connection.request(method,url,body=data,headers={'Authorization':'Bearer '+item['id']+':'+item['secret'],
            'Content-Type':'application/json','Connection':'close'})
        sent=True
        response=connection.getresponse();status=response.status
        headers={'noStore':'no-store' in response.getheader('Cache-Control',''),
            'cookiePresent':response.getheader('Set-Cookie') is not None}
        if not arg['dropBody']:
            raw=response.read(MAX_BYTES+1);ensure(len(raw)<=MAX_BYTES,'PROBE_RESPONSE_BOUND')
            parsed=parse(raw)
    except (OSError,ssl.SSLError,http.client.HTTPException):
        transport='TRANSPORT_UNAVAILABLE'
    finally: connection.close()
    observed=independent(body) if sent and method=='POST' else {'status':'NOT_APPLICABLE'}
    code=parsed.get('code') if type(parsed) is dict else None
    if status is not None: ensure(headers['noStore'] and not headers['cookiePresent'],'PROBE_PRIVATE_RESPONSE_HEADERS')
    return {'status':'PASS','transport':transport,'httpStatus':status,'code':code,
        'response':parsed,'fullRequestSent':sent,'bodyReceived':parsed is not None,'bodyConsumed':parsed is not None,
        'lostResponseBodyWitness':bool(arg['dropBody'] and sent and status is not None),
        'independent':observed,'workflowComplete':False}

def execute(action,arg):
    from journal.protocol import closed
    ensure(action in ('facts','request'),'PROBE_ACTION_SCOPE')
    if action=='facts': closed(arg,set());return facts()
    return request(arg)

if __name__=='__main__':
    try:
        signal.alarm(25)
        setup()
        result=execute(ACTION,ARG)
    except Exception as error:
        code=str(error) if type(error) is RuntimeError else getattr(error,'code','PROBE_FAILED')
        if type(code) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{0,99}',code): code='PROBE_FAILED'
        print(json.dumps({'status':'FAIL','errorCode':code,'dataPreserved':True}))
        raise SystemExit(1) from None
    print(json.dumps(result,ensure_ascii=False,separators=(',',':')))
