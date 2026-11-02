import hashlib
import hmac
import re
from pathlib import Path
from django.conf import settings
from .protocol import Fault, closed, parse, uid

def configuration():
    try:
        raw=Path(settings.TRUST_CREDENTIALS_FILE).read_bytes()
        if len(raw)>16384: raise ValueError()
        data=parse(raw); closed(data, {'schemaVersion','credentials'})
        if data['schemaVersion']!=1 or type(data['credentials']) is not list or not 1<=len(data['credentials'])<=16: raise ValueError()
        result={}
        for item in data['credentials']:
            closed(item, {'id','principal','role','secret'})
            if any(type(item[k]) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,64}',item[k]) for k in ('id','principal')): raise ValueError()
            if item['id'] in result or item['role'] not in ('writer','reader','recovery') or not re.fullmatch('[0-9a-f]{64}',item['secret']): raise ValueError()
            result[item['id']]=item
        return result
    except (OSError, ValueError, TypeError, Fault):
        raise Fault('AUTH_CONFIGURATION_UNAVAILABLE',503) from None
def identity():
    try: return uid(Path(settings.TRUST_IDENTITY_FILE).read_text(encoding='ascii').strip())
    except (OSError, UnicodeError, Fault): raise Fault('IDENTITY_UNAVAILABLE',503) from None
def authenticate(header, role):
    if type(header) is not str or not re.fullmatch(r'Bearer [A-Za-z0-9_-]{1,64}:[0-9a-f]{64}',header): raise Fault('UNAUTHORIZED',401)
    ident, secret=header[7:].split(':')
    item=configuration().get(ident)
    expected=item['secret'] if item else '0'*64
    valid=hmac.compare_digest(secret,expected)
    if not item or not valid or item['role']!=role: raise Fault('UNAUTHORIZED',401)
    return {'id':ident,'principal':item['principal'],'role':item['role'], 'verifier':hashlib.sha256(secret.encode('ascii')).hexdigest()}
