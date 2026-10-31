"""Closed PageInput validation used only by the resource-limited child."""
import hashlib
import json
import math
import unicodedata
from uuid import UUID

INPUT_KEYS = frozenset({'protocol', 'generation', 'baseRevisionId', 'editingFrom',
                       'draftBasis', 'stageId', 'changes'})
TEXT_FIELDS = frozenset({'intro_text', 'main_text', 'price'})
OWNER_FIELDS = TEXT_FIELDS | {'h1', 'title', 'description', 'indexing_allowed',
                             'main_image', 'preview_image'}
CONTEXT_KEYS = frozenset({'protocol', 'owner', 'fields', 'generation', 'page_id',
                         'base_revision_id', 'page_path', 'origin', 'protected_fields', 'policy_version'})


def identifier(value):
    if type(value) is not str:
        raise ValueError('EDITOR_INPUT_INVALID')
    if str(UUID(value)) != value:
        raise ValueError('EDITOR_INPUT_INVALID')
    return value


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('EDITOR_INPUT_INVALID')
        value[key] = item
    return value


def _no_constant(value):
    raise ValueError('EDITOR_INPUT_INVALID')


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('EDITOR_INPUT_INVALID')
    return result


def decode_input(raw, *, save=False):
    if type(raw) is not bytes:
        raise ValueError('EDITOR_INPUT_INVALID')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                       parse_constant=_no_constant, parse_float=_finite_float)
    expected = INPUT_KEYS | {'operationId', 'checkReceipt'} if save else INPUT_KEYS
    if type(value) is not dict or set(value) != expected or value['protocol'] != 'page-editor-v1':
        raise ValueError('EDITOR_INPUT_INVALID')
    if save:
        identifier(value['operationId'])
        if type(value['checkReceipt']) is not str or not 0 < len(value['checkReceipt']) <= 8192:
            raise ValueError('EDITOR_INPUT_INVALID')
    if type(value['generation']) is not int or value['generation'] <= 0:
        raise ValueError('EDITOR_INPUT_INVALID')
    identifier(value['baseRevisionId'])
    mode = value['editingFrom']
    if type(mode) is not str or mode not in ('current', 'owner-draft', 'restore-stage'):
        raise ValueError('EDITOR_INPUT_INVALID')
    basis = value['draftBasis']
    stage = value['stageId']
    if mode == 'owner-draft':
        if type(basis) is not dict or set(basis) != {'id', 'revision'} or stage is not None:
            raise ValueError('EDITOR_INPUT_INVALID')
        identifier(basis['id'])
        if type(basis['revision']) is not int or basis['revision'] <= 0:
            raise ValueError('EDITOR_INPUT_INVALID')
    elif mode == 'restore-stage':
        identifier(stage)
        if basis is not None:
            raise ValueError('EDITOR_INPUT_INVALID')
    elif basis is not None or stage is not None:
        raise ValueError('EDITOR_INPUT_INVALID')
    if type(value['changes']) is not dict or not value['changes']:
        raise ValueError('EDITOR_INPUT_INVALID')
    return value


def validate_context(value):
    # Only the server builds context. A malformed context is a server fault,
    # never permission data to repair from the submitted JSON.
    try:
        if (type(value) is not dict or set(value) not in (CONTEXT_KEYS, CONTEXT_KEYS | {'action'})
                or value['protocol'] != 'page-editor-context-v1'
                or type(value['owner']) is not bool
                or type(value['generation']) is not int or value['generation'] <= 0
                or type(value['fields']) is not list or not value['fields']
                or any(type(field) is not str for field in value['fields'])
                or len(set(value['fields'])) != len(value['fields'])
                or not set(value['fields']) <= (OWNER_FIELDS if value['owner'] else TEXT_FIELDS)
                or type(value['protected_fields']) is not list
                or any(type(field) is not str or field not in ('intro_text', 'main_text')
                       for field in value['protected_fields'])
                or type(value['page_path']) is not str or type(value['origin']) is not str
                or type(value['policy_version']) is not str):
            raise ValueError()
        if 'action' in value and value['action'] != 'save':
            raise ValueError()
        identifier(value['page_id'])
        identifier(value['base_revision_id'])
    except (ValueError, TypeError, KeyError):
        raise RuntimeError('EDITOR_CONTEXT_INVALID') from None
    return value


def plain(value, limit, *, multiline=False):
    if type(value) is not str:
        raise ValueError('EDITOR_INPUT_INVALID')
    value.encode('utf-8')
    if any(ord(char) < 32 and (not multiline or char not in '\n\r\t') for char in value):
        raise ValueError('EDITOR_INPUT_INVALID')
    value = unicodedata.normalize('NFC', value.replace('\r\n', '\n').replace('\r', '\n'))
    if not multiline:
        value = value.strip()
    if len(value) > limit:
        raise ValueError('EDITOR_INPUT_INVALID')
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()
