"""Validate storage identities without rewriting legacy request targets."""
import re
import unicodedata
from django.core.exceptions import ValidationError


def exact_target(value):
    if not isinstance(value, str):
        raise ValidationError('ROUTE_INVALID_TARGET')
    try:
        byte_length = len(value.encode('utf-8'))
    except UnicodeError:
        raise ValidationError('ROUTE_INVALID_TARGET') from None
    if (not value.startswith('/') or value.startswith('//')
            or any(ord(c) < 33 or ord(c) == 127 for c in value)
            or '\\' in value or '#' in value or byte_length > 2048):
        raise ValidationError('ROUTE_INVALID_TARGET')


def new_target(value):
    exact_target(value)
    if value == '/':
        return
    if '?' in value or any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', part)
                           or len(part) > 80 for part in value[1:].removesuffix('/').split('/')):
        raise ValidationError('ROUTE_INVALID_NEW_PATH')


def suggest_segment(name):
    """PR-07 suggestion only; never run on an imported URL or mutate a name."""
    if not isinstance(name, str) or not 0 < len(name) <= 200:
        raise ValidationError('ROUTE_INVALID_NAME_FOR_SUGGESTION')
    letters = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
    outputs = ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n',
               'o','p','r','s','t','u','f','kh','ts','ch','sh','sch','','y','','e','yu','ya']
    mapping = dict(zip(letters, outputs))
    parts = []
    for char in unicodedata.normalize('NFC', name).lower():
        if char in mapping:
            parts.append(mapping[char])
        elif 'a' <= char <= 'z' or '0' <= char <= '9':
            parts.append(char)
        elif char.isspace() or char in '-/_':
            parts.append('-')
        else:
            raise ValidationError('ROUTE_UNSUPPORTED_NAME_CHARACTER')
    segment = re.sub('-+', '-', ''.join(parts)).strip('-')
    if not segment or len(segment) > 80:
        raise ValidationError('ROUTE_INVALID_SUGGESTED_SEGMENT')
    return segment
