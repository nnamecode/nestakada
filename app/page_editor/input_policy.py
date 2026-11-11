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
                             'main_image', 'preview_image', 'home_profile'}
CONTEXT_KEYS = frozenset({'protocol', 'owner', 'fields', 'generation', 'page_id',
                         'base_revision_id', 'page_path', 'origin', 'protected_fields', 'policy_version'})


def identifier(value):
    if type(value) is not str:
        raise ValueError('EDITOR_INPUT_INVALID')
    if str(UUID(value)) != value:
        raise ValueError('EDITOR_INPUT_INVALID')
    return value


def validate_source(source):
    if (type(source) is not dict or set(source) != {'editingFrom', 'draftBasis', 'stageId', 'rebase', 'targetCurrentId'}
            or type(source['rebase']) is not bool):
        raise ValueError('EDITOR_INPUT_INVALID')
    mode = source['editingFrom']
    if type(mode) is not str or mode not in ('current', 'owner-draft', 'restore-stage'):
        raise ValueError('EDITOR_INPUT_INVALID')
    if mode == 'owner-draft':
        basis = source['draftBasis']
        if (type(basis) is not dict or set(basis) != {'id', 'revision'}
                or type(basis['revision']) is not int or basis['revision'] <= 0 or source['stageId'] is not None):
            raise ValueError('EDITOR_INPUT_INVALID')
        identifier(basis['id'])
        if source['rebase']:
            identifier(source['targetCurrentId'])
        elif source['targetCurrentId'] is not None:
            raise ValueError('EDITOR_INPUT_INVALID')
    elif (source['draftBasis'] is not None or source['rebase'] or source['targetCurrentId'] is not None):
        raise ValueError('EDITOR_INPUT_INVALID')
    elif mode == 'restore-stage':
        identifier(source['stageId'])
    elif source['stageId'] is not None:
        raise ValueError('EDITOR_INPUT_INVALID')
    return source


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


def decode_input(raw, *, save=False, draft=False):
    if type(raw) is not bytes:
        raise ValueError('EDITOR_INPUT_INVALID')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                       parse_constant=_no_constant, parse_float=_finite_float)
    expected = INPUT_KEYS | {'operationId', 'checkReceipt'} if save else INPUT_KEYS
    if draft:
        expected = expected | {'rebase'}
    if type(value) is not dict or set(value) != expected or value['protocol'] != 'page-editor-v1':
        raise ValueError('EDITOR_INPUT_INVALID')
    if save:
        identifier(value['operationId'])
        if type(value['checkReceipt']) is not str or not 0 < len(value['checkReceipt']) <= 8192:
            raise ValueError('EDITOR_INPUT_INVALID')
    if draft and type(value['rebase']) is not bool:
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
        extra = {'source', 'can_read_source', 'current_revision_id'}
        allowed = (CONTEXT_KEYS, CONTEXT_KEYS | {'action'}, CONTEXT_KEYS | extra, CONTEXT_KEYS | extra | {'action'})
        if (type(value) is not dict or set(value) not in (*allowed, *(keys | {'embedded_source'} for keys in allowed))
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
        if 'action' in value and value['action'] not in ('save', 'draft', 'embedded-issue'):
            raise ValueError()
        if 'embedded_source' in value:
            embedded = value['embedded_source']
            if (type(embedded) is not dict or set(embedded) != {'intro_text', 'main_text', 'layout', 'embedded_images'}
                    or any(type(embedded[field]) is not str for field in ('intro_text', 'main_text'))
                    or type(embedded['layout']) is not list or type(embedded['embedded_images']) is not list):
                raise ValueError()
        if 'source' in value:
            validate_source(value['source'])
            if type(value['can_read_source']) is not bool:
                raise ValueError()
            identifier(value['current_revision_id'])
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


def image_reference(value):
    if value is None:
        return None
    if type(value) is not dict or set(value) != {'asset_id', 'alt', 'alignment', 'width_px', 'height_px'}:
        raise ValueError('EDITOR_MEDIA_INVALID')
    identifier(value['asset_id'])
    if type(value['alt']) is not str or any(ord(char) < 32 or ord(char) == 127 for char in value['alt']):
        raise ValueError('EDITOR_MEDIA_INVALID')
    alt = unicodedata.normalize('NFC', value['alt'])
    alt.encode('utf-8')
    if len(alt) > 300 or type(value['alignment']) is not str or value['alignment'] not in ('left', 'center', 'right'):
        raise ValueError('EDITOR_MEDIA_INVALID')
    for key in ('width_px', 'height_px'):
        if value[key] is not None and (type(value[key]) is not int or value[key] <= 0):
            raise ValueError('EDITOR_MEDIA_INVALID')
    return {**value, 'alt': alt}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()
