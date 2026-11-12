import re
import unicodedata
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .models import ServiceRequest


NAME_MAX = 100
CAR_MAX = 300
COMMENT_MAX = 4000
CONSENT_VERSION_MAX = 64
_PHONE_ALLOWED = re.compile(r'^\+?[0-9()\- ]+$')
_PHONE_CANONICAL = re.compile(r'^\+7[0-9]{10}$')


@dataclass(frozen=True)
class NormalizedRequest:
    source: str
    name: str
    phone: str
    car: str
    comment: str
    consent_version: str


def _text(value, *, field, maximum, multiline=False, required=False):
    if type(value) is not str:
        raise ValidationError({field: 'REQUEST_INVALID_TEXT'})
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    for character in value:
        if unicodedata.category(character) == 'Cc' and character not in '\n\t':
            raise ValidationError({field: 'REQUEST_INVALID_CONTROL'})
    if multiline:
        value = value.replace('\t', '    ').strip()
    else:
        value = ' '.join(value.split())
    if required and not value:
        raise ValidationError({field: 'REQUEST_REQUIRED'})
    if len(value) > maximum:
        raise ValidationError({field: 'REQUEST_TOO_LONG'})
    return value


def normalize_phone(value):
    if type(value) is not str or not value or not _PHONE_ALLOWED.fullmatch(value):
        raise ValidationError({'phone': 'REQUEST_INVALID_PHONE'})
    compact = re.sub(r'[()\- ]', '', value)
    if re.fullmatch(r'8[0-9]{10}', compact):
        compact = '+7' + compact[1:]
    if not _PHONE_CANONICAL.fullmatch(compact):
        raise ValidationError({'phone': 'REQUEST_INVALID_PHONE'})
    return compact


def normalize(*, source, name, phone, car, comment, consent, consent_version):
    if source not in ServiceRequest.Source.values:
        raise ValidationError({'source': 'REQUEST_INVALID_SOURCE'})
    if consent != 'on':
        raise ValidationError({'consent': 'REQUEST_CONSENT_REQUIRED'})
    version = _text(
        consent_version, field='consent', maximum=CONSENT_VERSION_MAX,
        required=True)
    return NormalizedRequest(
        source=source,
        name=_text(name, field='name', maximum=NAME_MAX, required=True),
        phone=normalize_phone(phone),
        car=_text(car, field='car', maximum=CAR_MAX),
        comment=_text(comment, field='comment', maximum=COMMENT_MAX, multiline=True),
        consent_version=version,
    )
