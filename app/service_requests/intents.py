import hashlib
import re
import secrets

from django.core import signing
from django.core.exceptions import ValidationError

from .models import ServiceRequest


INTENT_SALT = 'estakada.service-request.intent.v1'
INTENT_MAX_AGE_SECONDS = 30 * 60
INTENT_MAX_LENGTH = 512
_NONCE = re.compile(r'^[0-9a-f]{32}$')


def issue(*, source, consent_version):
    if source not in ServiceRequest.Source.values:
        raise ValidationError('REQUEST_INTENT_SOURCE_INVALID')
    if (type(consent_version) is not str or not consent_version
            or len(consent_version) > 64):
        raise ValidationError('REQUEST_INTENT_CONSENT_INVALID')
    value = signing.dumps({
        'schema': 'service-request-intent-v1',
        'source': source,
        'consent_version': consent_version,
        'nonce': secrets.token_hex(16),
    }, salt=INTENT_SALT, compress=False)
    if len(value) > INTENT_MAX_LENGTH:
        raise ValidationError('REQUEST_INTENT_INVALID')
    return value


def verify(value):
    if type(value) is not str or not 1 <= len(value) <= INTENT_MAX_LENGTH:
        raise ValidationError('REQUEST_INTENT_INVALID')
    try:
        payload = signing.loads(
            value, salt=INTENT_SALT, max_age=INTENT_MAX_AGE_SECONDS)
    except signing.BadSignature:
        raise ValidationError('REQUEST_INTENT_INVALID') from None
    if (type(payload) is not dict
            or set(payload) != {'schema', 'source', 'consent_version', 'nonce'}
            or payload['schema'] != 'service-request-intent-v1'
            or payload['source'] not in ServiceRequest.Source.values
            or type(payload['consent_version']) is not str
            or not 1 <= len(payload['consent_version']) <= 64
            or type(payload['nonce']) is not str
            or _NONCE.fullmatch(payload['nonce']) is None):
        raise ValidationError('REQUEST_INTENT_INVALID')
    return payload


def digest(value):
    if type(value) is not str or not value.isascii():
        raise ValidationError('REQUEST_INTENT_INVALID')
    return hashlib.sha256(value.encode('ascii')).hexdigest()
