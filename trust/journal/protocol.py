"""Closed wire protocol; validation does not open a database connection."""
import hashlib
import json
import re
import uuid

MAX_BODY = 1048576
MAX_INT = 9223372036854775807
class Fault(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def closed(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise Fault('INPUT_REJECTED', 400)
def uid(value):
    if type(value) is not str:
        raise Fault('INPUT_REJECTED', 400)
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise Fault('INPUT_REJECTED', 400) from None
    return value
def integer(value):
    if type(value) is not str or not re.fullmatch(r'0|[1-9][0-9]{0,18}', value) or int(value) > MAX_INT:
        raise Fault('INPUT_REJECTED', 400)
    return int(value)
def target(value):
    if type(value) is not str or not value.startswith('/') or value.startswith('//') or '#' in value or '\\' in value or any(ord(c)<32 or ord(c)==127 for c in value) or len(value.encode('utf-8'))>2048:
        raise Fault('INPUT_REJECTED', 400)
    return value
def no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError()
        value[key] = item
    return value
def parse(raw):
    if len(raw)>MAX_BODY:
        raise Fault('BODY_TOO_LARGE', 413)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise Fault('INPUT_REJECTED', 400) from None
def validate(value, phase):
    common = {'operationId','incarnation','expectedGeneration','writerEpoch'}
    closed(value, common | ({'kind','objectId','basis','policies','requestIds'} if phase=='prepare' else {'outcome','mainIncarnation','mainReceipt','policies'}))
    uid(value['operationId']); uid(value['incarnation'])
    integer(value['expectedGeneration']); integer(value['writerEpoch'])
    policies = value['policies']
    if type(policies) is not list or len(policies)>256:
        raise Fault('INPUT_REJECTED',400)
    seen = set()
    for item in policies:
        closed(item, {'target','objectId','policy','redirectTarget'})
        key = target(item['target']); uid(item['objectId'])
        if key in seen or item['policy'] not in ('HIDDEN','DELETED','REDIRECT','LIVE_NO_SET'):
            raise Fault('INPUT_REJECTED',400)
        seen.add(key)
        if item['policy']=='REDIRECT': target(item['redirectTarget'])
        elif item['redirectTarget'] is not None: raise Fault('INPUT_REJECTED',400)
    if phase=='prepare':
        uid(value['objectId'])
        if value['kind'] not in ('route_restriction','request_tombstone','route_publication') or type(value['basis']) is not str or not re.fullmatch('[0-9a-f]{64}',value['basis']):
            raise Fault('INPUT_REJECTED',400)
        ids=value['requestIds']
        if type(ids) is not list or len(ids)>256 or len(ids)!=len(set(map(str,ids))): raise Fault('INPUT_REJECTED',400)
        for item in ids: uid(item)
        if value['kind']=='request_tombstone' and (not ids or policies): raise Fault('INPUT_REJECTED',400)
        if value['kind']=='route_restriction' and (not policies or ids): raise Fault('INPUT_REJECTED',400)
        if value['kind']=='route_restriction' and any(item['policy']=='LIVE_NO_SET' for item in policies):
            raise Fault('INPUT_REJECTED',400)
        if value['kind']=='route_publication' and (len(policies)!=1 or ids
            or policies[0]['objectId']!=value['objectId']
            or policies[0]['policy'] not in ('HIDDEN','LIVE_NO_SET')):
            raise Fault('INPUT_REJECTED',400)
    else:
        if value['outcome'] not in ('unknown','committed','aborted'): raise Fault('INPUT_REJECTED',400)
        if value['outcome']=='unknown':
            if value['mainIncarnation'] is not None or value['mainReceipt'] is not None or policies: raise Fault('INPUT_REJECTED',400)
        else:
            uid(value['mainIncarnation'])
            if type(value['mainReceipt']) is not str or not re.fullmatch('[0-9a-f]{64}',value['mainReceipt']): raise Fault('INPUT_REJECTED',400)
            if value['outcome']=='aborted' and policies: raise Fault('INPUT_REJECTED',400)
    return value
