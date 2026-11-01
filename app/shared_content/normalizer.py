"""Resource-limited shared child dispatcher, without Django or DB imports."""
import hashlib

from editor_runtime.processing import strict_json
from .policy import PROTOCOL, POLICY, canonical_uuid, normalize_html


def normalize(raw, context):
    if set(context) != {'processor', 'kind', 'generation', 'baseRevisionId', 'sourceMode', 'draftBasis', 'stageId', 'policy'}:
        raise ValueError('SHARED_CONTEXT_INVALID')
    if context['processor'] != PROTOCOL or context['policy'] != POLICY:
        raise ValueError('SHARED_CONTEXT_INVALID')
    value = strict_json(raw.decode('utf-8'))
    required = {'protocol', 'generation', 'baseRevisionId', 'sourceMode', 'draftBasis', 'stageId', 'html'}
    extra = set(value) - required if type(value) is dict else set()
    if (type(value) is not dict or not required <= set(value)
            or extra not in (set(), {'operationId', 'checkReceipt'}) or value['protocol'] != PROTOCOL):
        raise ValueError('SHARED_INPUT_INVALID')
    if type(value['generation']) is not int or value['generation'] < 1:
        raise ValueError('SHARED_INPUT_INVALID')
    for key in ('generation', 'baseRevisionId', 'sourceMode', 'draftBasis', 'stageId'):
        if value[key] != context[key]:
            raise ValueError('SHARED_CONTEXT_CONFLICT')
    if extra:
        canonical_uuid(value['operationId'])
        if type(value['checkReceipt']) is not str or len(value['checkReceipt']) > 16384:
            raise ValueError('SHARED_PROOF_INVALID')
    result = normalize_html(value['html'], context['kind'])
    result.update({'inputFingerprint': hashlib.sha256(raw).hexdigest(),
                   'changed': result['html'] != value['html']})
    return result
