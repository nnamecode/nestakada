"""Read-only check context and signed proof; no revision/draft mutation."""
from dataclasses import dataclass
import hashlib
import re
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from page_versions import engine as E
from page_versions.models import PageRevision
from content.models import Route
from editor_runtime.guards import EditorFault, input_profile
from .input_policy import OWNER_FIELDS, fingerprint
from . import policy_constants

CHECK_POLICY = 'page-editor-check-v1'
SALT = 'estakada.page-editor.check.v1'
FAILURES = {
    'EDITOR_INPUT_REJECTED': 400,
    'EDITOR_OPERATION_CONFLICT': 409,
    'EDITOR_NORMALIZATION_REQUIRED': 409,
    'EDITOR_SESSION_ENDED': 401,
    'EDITOR_IDENTITY_CHANGED': 403,
    'EDITOR_FIELDS_FORBIDDEN': 403,
    'EDITOR_BASE_CONFLICT': 409,
    'EDITOR_CONTEXT_CHANGED': 409,
    'EDITOR_BASE_UNAVAILABLE': 409,
    'EDITOR_CAPABILITY_UNAVAILABLE': 409,
    'EDITOR_CHECK_RECEIPT_INVALID': 409,
    'EDITOR_WORKER_PROTOCOL': 503,
}


class CheckFault(EditorFault):
    def __init__(self, code):
        if code not in FAILURES:
            raise ValueError('Unknown fixed editor fault')
        self.code = code
        self.status = FAILURES[code]
        super().__init__()


@dataclass(frozen=True)
class CheckContext:
    actor_id: int
    child: dict
    permission_hash: str
    stamp: str

    @property
    def profile(self):
        return input_profile(owner=self.child['owner'], can_price='price' in self.child['fields'])


def inspect_context(*, actor, page_id, generation, origin):
    """Take and release domain locks before any body read or child execution."""
    E.outside()
    try:
        with transaction.atomic():
            page, profile, fields, owner, state = E.enter(actor, page_id, generation)
            fields = sorted(set(fields) & OWNER_FIELDS)
            if not fields:
                raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
            target = Route.objects.filter(page=page, kind=Route.Kind.PRIMARY).values_list('target', flat=True).first()
            if type(target) is not str or not target.startswith('/'):
                raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE')
            layout = PageRevision.objects.filter(pk=state.current_revision_id).values_list('payload__layout', flat=True).get()
            if type(layout) is not list:
                raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE')
            protected = set()
            for node in layout:
                if type(node) is not dict:
                    raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE')
                if node.get('kind') == 'text' and node.get('protected_nodes'):
                    field = node.get('field')
                    if field not in ('intro_text', 'main_text'):
                        raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE')
                    protected.add(field)
            child = {'protocol': 'page-editor-context-v1', 'owner': owner, 'fields': fields,
                     'generation': generation, 'page_id': str(page.pk),
                     'base_revision_id': str(state.current_revision_id),
                     'page_path': target, 'origin': origin, 'protected_fields': sorted(protected),
                     'policy_version': policy_constants.POLICY_VERSION}
            permission_hash = E.permission_hash(profile, fields)
            stamp = fingerprint({'child': child, 'permissions': permission_hash, 'policy': CHECK_POLICY})
            return CheckContext(actor.pk, child, permission_hash, stamp)
    except ValidationError:
        raise CheckFault('EDITOR_BASE_UNAVAILABLE') from None


def check_worker_result(result, *, raw, context):
    if type(result) is not dict or type(result.get('accepted')) is not bool:
        raise CheckFault('EDITOR_WORKER_PROTOCOL')
    if result['accepted'] is False:
        if (set(result) != {'accepted', 'code'} or type(result['code']) is not str
                or result['code'] not in FAILURES):
            raise CheckFault('EDITOR_WORKER_PROTOCOL')
        raise CheckFault(result['code'])
    expected = {'accepted', 'changes', 'warnings', 'changed', 'input_fingerprint', 'normalized_fingerprint', 'policy_version'}
    if (set(result) != expected or type(result['changes']) is not dict or not result['changes']
            or not set(result['changes']) <= set(context.child['fields'])
            or type(result['warnings']) is not list or type(result['changed']) is not bool
            or result['policy_version'] != context.child['policy_version']
            or result['policy_version'] != policy_constants.POLICY_VERSION
            or result['input_fingerprint'] != hashlib.sha256(raw).hexdigest()
            or result['normalized_fingerprint'] != fingerprint(result['changes'])):
        raise CheckFault('EDITOR_WORKER_PROTOCOL')
    for warning in result['warnings']:
        if (type(warning) is not dict or set(warning) != {'field', 'code'}
                or type(warning['field']) is not str or warning['field'] not in result['changes']
                or type(warning['code']) is not str
                or warning['code'] not in {'NORMALIZATION_REVIEW_REQUIRED', 'ANCHOR_TARGET_UNRESOLVED'}):
            raise CheckFault('EDITOR_WORKER_PROTOCOL')
    return result


def issue_check_receipt(*, context, result):
    if (context.child['policy_version'] != policy_constants.POLICY_VERSION
            or result['policy_version'] != policy_constants.POLICY_VERSION):
        raise CheckFault('EDITOR_CONTEXT_CHANGED')
    return signing.dumps({'protocol': CHECK_POLICY, 'actorId': context.actor_id,
        'semanticPolicy': context.child['policy_version'],
        'generation': context.child['generation'], 'pageId': context.child['page_id'],
        'baseRevisionId': context.child['base_revision_id'], 'contextStamp': context.stamp,
        'permissionHash': context.permission_hash, 'editingFrom': 'current',
        'inputFingerprint': result['input_fingerprint'],
        'normalizedFingerprint': result['normalized_fingerprint']}, salt=SALT, compress=False)


def verify_check_receipt(token, *, context, changes):
    """Proof only; future writes must still reparse and recheck actual context."""
    if type(token) is not str or len(token) > 8192:
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID')
    try:
        value = signing.loads(token, salt=SALT)  # No new business TTL.
    except (signing.BadSignature, ValueError, TypeError):
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID') from None
    expected = {'protocol', 'semanticPolicy', 'actorId', 'generation', 'pageId', 'baseRevisionId', 'contextStamp',
                'permissionHash', 'editingFrom', 'inputFingerprint', 'normalizedFingerprint'}
    if (type(value) is not dict or set(value) != expected
            or value['protocol'] != CHECK_POLICY or value['actorId'] != context.actor_id
            or value['semanticPolicy'] != policy_constants.POLICY_VERSION
            or value['semanticPolicy'] != context.child['policy_version']
            or value['generation'] != context.child['generation']
            or value['pageId'] != context.child['page_id']
            or value['baseRevisionId'] != context.child['base_revision_id']
            or value['contextStamp'] != context.stamp or value['permissionHash'] != context.permission_hash
            or value['editingFrom'] != 'current' or type(value['inputFingerprint']) is not str
            or re.fullmatch('[a-f0-9]{64}', value['inputFingerprint']) is None
            or value['normalizedFingerprint'] != fingerprint(changes)):
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID')
    return value
