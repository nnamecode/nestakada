"""Bounded reader/startup primitive. No Django, write access or HTML admission."""
import http.client
import json
import re
import ssl
import sys

MAX_RESPONSE=1048576
MAX_SNAPSHOT=64*1024*1024
MAX_BIGINT=9223372036854775807
WHOLE_SECONDS=30
REQUEST_SECONDS=6

class SnapshotRejected(Exception):
    def __init__(self,code='SNAPSHOT_REJECTED'):
        self.code=code
        super().__init__(code)

def reject(condition,code='SNAPSHOT_REJECTED'):
    if not condition: raise SnapshotRejected(code)

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def closed(value,keys): reject(type(value) is dict and set(value)==set(keys))
def sha(value): return hashlib.sha256(value).hexdigest()
def uuid_value(value):
    reject(type(value) is str)
    try: reject(str(uuid.UUID(value))==value)
    except ValueError: raise SnapshotRejected() from None
    return value
def bigint(value,minimum=0):
    reject(type(value) is str and re.fullmatch(r'0|[1-9][0-9]{0,18}',value) is not None)
    number=int(value);reject(minimum<=number<=MAX_BIGINT)
    return number
def hex_digest(value): reject(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None)
def exact_target(value):
    reject(type(value) is str and value.startswith('/') and not value.startswith('//') and '#' not in value and '\\' not in value)
    reject(not any(ord(char)<32 or ord(char)==127 for char in value))
    reject(len(value.encode('utf-8'))<=2048)
def head_value(value,expected_incarnation):
    closed(value,{'incarnation','generation','writerEpoch','mode','digest'})
    uuid_value(value['incarnation']);bigint(value['generation']);bigint(value['writerEpoch'],1);hex_digest(value['digest'])
    reject(value['incarnation']==expected_incarnation and value['mode']=='ACTIVE','SNAPSHOT_COHORT_REJECTED')
    return value
def _pairs(pairs):
    result={}
    for key,value in pairs:
        reject(key not in result)
        result[key]=value
    return result
def parse(raw):
    reject(type(raw) is bytes and len(raw)<=MAX_RESPONSE+128)
    try:
        return json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(SnapshotRejected()))
    except (ValueError,UnicodeError,RecursionError): raise SnapshotRejected() from None

def allowed_target(target):
    reject(type(target) is str and len(target)<=128)
    reject(target in ('/v1/head','/v1/snapshot-manifest') or
        re.fullmatch(r'/v1/snapshot\?generation=(0|[1-9][0-9]{0,18})&cursor=(0|[1-9][0-9]{0,4})',target) is not None)

def _worker_command():
    return [sys.executable,'-I',str(Path(__file__).resolve()),'--trust-snapshot-http-worker']

class HTTPSReader:
    """All DNS/TLS/drip I/O lives in a bounded, killable stdlib worker."""
    def __init__(self,ca_file,credential_id,secret):
        reject(type(ca_file) is str and len(ca_file)<=1024)
        reject(type(credential_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,64}',credential_id) is not None)
        reject(type(secret) is str and re.fullmatch('[0-9a-f]{64}',secret) is not None)
        self._ca_file=ca_file;self._credential_id=credential_id;self._secret=secret
    def __call__(self,target,timeout):
        allowed_target(target)
        reject(type(timeout) in (int,float) and 0<timeout<=REQUEST_SECONDS,'SNAPSHOT_DEADLINE')
        request=canonical({'ca':self._ca_file,'credential':self._credential_id,'secret':self._secret,'target':target})
        deadline=time.monotonic()+timeout
        try: child=subprocess.Popen(_worker_command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        except OSError: raise SnapshotRejected('SNAPSHOT_TRANSPORT_REJECTED') from None
        try:
            try:
                remaining=deadline-time.monotonic()
                if remaining<=0: raise subprocess.TimeoutExpired(_worker_command(),timeout)
                output,_=child.communicate(request,timeout=remaining)
            except subprocess.TimeoutExpired:
                child.kill()
                try: child.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    child.wait(timeout=1)
                raise SnapshotRejected('SNAPSHOT_DEADLINE') from None
            reject(child.returncode==0 and len(output)<=MAX_RESPONSE+128,'SNAPSHOT_TRANSPORT_REJECTED')
            envelope=parse(output);closed(envelope,{'ok','value'})
            reject(envelope['ok'] is True,'SNAPSHOT_TRANSPORT_REJECTED')
            return envelope['value']
        except (OSError,ValueError,subprocess.SubprocessError):
            raise SnapshotRejected('SNAPSHOT_TRANSPORT_REJECTED') from None
        finally:
            if child.poll() is None:
                child.kill();child.wait(timeout=1)
            for stream in (child.stdin,child.stdout):
                if stream is not None: stream.close()

def _http_worker(request):
    closed(request,{'ca','credential','secret','target'})
    reader=HTTPSReader(request['ca'],request['credential'],request['secret'])
    allowed_target(request['target'])
    context=ssl.create_default_context(cafile=reader._ca_file)
    connection=http.client.HTTPSConnection('trust-ingress',8443,timeout=REQUEST_SECONDS,context=context)
    try:
        connection.request('GET',request['target'],headers={'Authorization':'Bearer '+reader._credential_id+':'+reader._secret,
            'Accept':'application/json','Connection':'close'})
        response=connection.getresponse()
        reject(response.status==200,'SNAPSHOT_TRANSPORT_REJECTED')
        reject(response.getheader('Set-Cookie') is None and 'no-store' in response.getheader('Cache-Control','').lower(),'SNAPSHOT_TRANSPORT_REJECTED')
        reject(response.getheader('Content-Type','').split(';')[0].strip().lower()=='application/json','SNAPSHOT_TRANSPORT_REJECTED')
        raw=response.read(MAX_RESPONSE+1);reject(len(raw)<=MAX_RESPONSE,'SNAPSHOT_RESPONSE_BOUND')
        return parse(raw)
    finally: connection.close()

if __name__=='__main__':
    try:
        reject(sys.argv[1:]==['--trust-snapshot-http-worker'])
        raw=sys.stdin.buffer.read(16385);reject(len(raw)<=16384)
        value=_http_worker(parse(raw))
        encoded=canonical({'ok':True,'value':value})
        reject(len(encoded)<=MAX_RESPONSE+128,'SNAPSHOT_RESPONSE_BOUND')
        sys.stdout.buffer.write(encoded)
    except Exception:
        sys.stdout.buffer.write(b'{"ok":false,"value":null}')
        raise SystemExit(1) from None
    raise SystemExit(0)

import hashlib
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

@dataclass(frozen=True)
class VerifiedSnapshot:
    head: object
    items_bytes: bytes
    digest: str
    total_routes: int
    total_tombstones: int

@dataclass(frozen=True)
class StartupResult:
    snapshot_ready: bool
    html_admission: bool
    workflow_complete: bool
    code: str

def _item(item,head_generation):
    reject(type(item) is dict)
    if item.get('type')=='route':
        closed(item,{'type','key','target','object_id','generation','policy','redirect_target'})
        hex_digest(item['key']);exact_target(item['target']);uuid_value(item['object_id'])
        reject(sha(item['target'].encode('utf-8'))==item['key'])
        reject(type(item['policy']) is str and item['policy'] in ('PENDING_DENY','HIDDEN','DELETED','REDIRECT'))
        if item['policy']=='REDIRECT': exact_target(item['redirect_target'])
        else: reject(item['redirect_target'] is None)
        order=(0,item['key'])
    else:
        closed(item,{'type','request_id','tombstone_id','generation'})
        reject(item['type']=='tombstone');uuid_value(item['request_id']);uuid_value(item['tombstone_id'])
        order=(1,item['request_id'])
    reject(1<=bigint(item['generation'])<=head_generation)
    return order

def read_snapshot(transport,expected_incarnation):
    try:
        uuid_value(expected_incarnation)
        deadline=time.monotonic()+WHOLE_SECONDS
        def tick(): reject(time.monotonic()<deadline,'SNAPSHOT_DEADLINE')
        def fetch(target):
            tick();remaining=deadline-time.monotonic()
            value=transport(target,min(REQUEST_SECONDS,remaining));tick()
            reject(len(canonical(value))<=MAX_RESPONSE,'SNAPSHOT_RESPONSE_BOUND')
            return value
        manifest=fetch('/v1/snapshot-manifest')
        closed(manifest,{'ok','protocolVersion','head','counts','snapshotDigest'})
        reject(manifest['ok'] is True and type(manifest['protocolVersion']) is int and manifest['protocolVersion']==1)
        head=dict(head_value(manifest['head'],expected_incarnation));counts=manifest['counts']
        closed(counts,{'routes','tombstones','items'})
        reject(all(type(value) is int and value>=0 for value in counts.values()))
        reject(counts['routes']<=50000 and counts['tombstones']<=10000 and counts['items']==counts['routes']+counts['tombstones'])
        hex_digest(manifest['snapshotDigest'])
        output=bytearray(b'[');previous=None;route_count=0;tomb_count=0;count=0;tombstone_ids=set()
        for cursor in range(0,counts['items'],100):
            tick()
            page=fetch('/v1/snapshot?generation='+head['generation']+'&cursor='+str(cursor))
            closed(page,{'ok','head','cursor','items','pageDigest','nextCursor'})
            reject(page['ok'] is True and head_value(page['head'],expected_incarnation)==head)
            reject(type(page['cursor']) is int and page['cursor']==cursor and type(page['items']) is list)
            expected=min(100,counts['items']-cursor)
            reject(len(page['items'])==expected)
            next_cursor=cursor+100 if cursor+100<counts['items'] else None
            reject(page['nextCursor'] is None if next_cursor is None else type(page['nextCursor']) is int and page['nextCursor']==next_cursor)
            hex_digest(page['pageDigest']);reject(sha(canonical(page['items']))==page['pageDigest'])
            for item in page['items']:
                tick();order=_item(item,int(head['generation']))
                reject(previous is None or previous<order);previous=order
                if order[0]==0: route_count+=1
                else:
                    reject(item['tombstone_id'] not in tombstone_ids)
                    tombstone_ids.add(item['tombstone_id']);tomb_count+=1
                raw=canonical(item)
                reject(len(output)+len(raw)+(1 if count else 0)+1<=MAX_SNAPSHOT,'SNAPSHOT_BYTE_BOUND')
                if count: output.extend(b',')
                output.extend(raw);count+=1
        output.extend(b']');tick()
        reject(count==counts['items'] and route_count==counts['routes'] and tomb_count==counts['tombstones'])
        reject(sha(output)==manifest['snapshotDigest'])
        final=fetch('/v1/head');closed(final,{'ok','head'})
        reject(final['ok'] is True and head_value(final['head'],expected_incarnation)==head,'SNAPSHOT_COHORT_REJECTED')
        immutable=bytes(output);tick()
        return VerifiedSnapshot(MappingProxyType(dict(head)),immutable,manifest['snapshotDigest'],route_count,tomb_count)
    except SnapshotRejected: raise
    except Exception: raise SnapshotRejected() from None

def startup_check(transport,expected_incarnation,expected_head):
    try:
        expected=dict(expected_head)
        head_value(expected,expected_incarnation)
        snapshot=read_snapshot(transport,expected_incarnation)
        reject(dict(snapshot.head)==expected,'SNAPSHOT_COHORT_REJECTED')
        return StartupResult(True,False,False,'SNAPSHOT_READY')
    except Exception:
        return StartupResult(False,False,False,'SNAPSHOT_NOT_READY')

