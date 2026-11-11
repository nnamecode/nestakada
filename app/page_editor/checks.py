"""Read-only check context and signed proof; no revision/draft mutation."""
from dataclasses import dataclass
import hashlib
import re
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from page_versions import engine as E, schema as S
from page_versions.models import PageRevision
from content.models import Route
from editor_runtime.guards import EditorFault, input_profile
from .input_policy import OWNER_FIELDS, fingerprint
from . import policy_constants

CHECK_POLICY = 'page-editor-check-v1'
SALT = 'estakada.page-editor.check.v1'
_HOME_SOURCE_DEFAULT = object()
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
    'EDITOR_MEDIA_UNAVAILABLE': 409,
    'EDITOR_MEDIA_INVALID': 400,
    'EDITOR_EMBEDDED_INVALID': 400,
    'EDITOR_EMBEDDED_FORBIDDEN': 403,
    'EDITOR_EMBEDDED_STALE': 409,
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
    payload: dict | None = None
    home_source_digest: str | None = None

    @property
    def profile(self):
        return input_profile(owner=self.child['owner'], can_price='price' in self.child['fields'])


def restore_context(context, payload, source_revision_id):
    """Build a closed normalizer context for an already authorised restore candidate."""
    candidate = S.validate(payload, context.payload['page_kind'])
    child = dict(context.child)
    fields = set(child['fields'])
    if child['owner'] and candidate['page_kind'] == 'home' and 'home_profile' in candidate:
        fields.add('home_profile')
    else:
        fields.discard('home_profile')
    child['fields'] = sorted(fields)
    child['embedded_source'] = {
        key: candidate[key]
        for key in ('intro_text', 'main_text', 'layout', 'embedded_images')
    }
    stamp = fingerprint({
        'child': child,
        'sourceFacts': {
            'restoreSource': str(source_revision_id),
            'candidateHash': S.digest(candidate),
        },
        'permissions': context.permission_hash,
        'policy': CHECK_POLICY,
    })
    return CheckContext(
        context.actor_id, child, context.permission_hash, stamp, candidate,
        context.home_source_digest)


def inspect_admission(*, actor, page_id, generation):
    """Metadata-only admission: never touch source, route, layout or JSON."""
    E.outside()
    try:
        with transaction.atomic():
            page, profile, fields, owner, state = E.enter(actor, page_id, generation)
            fields = sorted(set(fields) & OWNER_FIELDS)
            if not fields:
                raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
            return {'owner': owner, 'fields': fields, 'generation': generation,
                    'page_id': str(page.pk), 'current_revision_id': str(state.current_revision_id)}
    except ValidationError:
        raise CheckFault('EDITOR_BASE_UNAVAILABLE') from None


def inspect_context(*, actor, page_id, generation, origin, selector=None, allow_unavailable=False):
    """Take and release domain locks before any body read or child execution."""
    E.outside()
    return _inspect_context_locked(actor=actor, page_id=page_id, generation=generation, origin=origin,
                                   selector=selector, allow_unavailable=allow_unavailable)


def _inspect_context_locked(*, actor, page_id, generation, origin, selector=None, allow_unavailable=False):
    """Internal shared final-check boundary; caller may retain the transaction."""
    try:
        with transaction.atomic():
            page, profile, fields, owner, state = E.enter(actor, page_id, generation)
            engine_fields = fields
            fields = sorted(set(fields) & OWNER_FIELDS)
            if not fields:
                raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
            target = Route.objects.filter(page=page, kind=Route.Kind.PRIMARY).values_list('target', flat=True).first()
            if type(target) is not str or not target.startswith('/'):
                raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE')
            from .source_context import current_selector, selected_source
            selector = current_selector() if selector is None else selector
            readable = True
            try:
                payload, base, source_facts = selected_source(page, profile, engine_fields, owner, state, selector)
            except ValidationError:
                if not allow_unavailable:
                    raise
                payload, base, source_facts, readable = None, str(state.current_revision_id), {}, False
            if not readable or page.kind != 'home' or 'home_profile' not in payload:
                fields = [field for field in fields if field != 'home_profile']
            home_source_digest = None
            if readable and page.kind == 'home' and 'home_profile' in payload:
                from .home_sources import capture
                _, home_source_digest = capture(payload['home_profile'])
                source_facts = {**source_facts, 'homeSourceDigest': home_source_digest}
            layout = payload['layout'] if readable else []
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
                     'base_revision_id': base,
                     'page_path': target, 'origin': origin, 'protected_fields': sorted(protected),
                     'policy_version': policy_constants.POLICY_VERSION,
                     'source': selector, 'can_read_source': readable,
                     'current_revision_id': str(state.current_revision_id)}
            if readable:
                child['embedded_source'] = {key: payload[key] for key in ('intro_text', 'main_text', 'layout', 'embedded_images')}
            permission_hash = E.permission_hash(profile, engine_fields)
            stamp = fingerprint({'child': child, 'sourceFacts': source_facts,
                                 'permissions': permission_hash, 'policy': CHECK_POLICY})
            return CheckContext(actor.pk, child, permission_hash, stamp, payload,
                                home_source_digest)
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
    if 'derived' in result or 'intentBindings' in result:
        expected |= {'derived', 'intentBindings'}
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


def canonicalize_home_change(context, result):
    """Protect fixed composition and replace bound fallbacks with DB facts."""
    if 'home_profile' not in result['changes']:
        return result, context.home_source_digest
    if (context.payload is None or 'home_profile' not in context.payload
            or context.payload.get('page_kind') != 'home'):
        raise CheckFault('EDITOR_INPUT_REJECTED')
    from content.models import lock_content
    from page_versions.home_profile import validate_edit
    from .home_sources import capture, synchronize
    embedded = context.payload['embedded_images']
    try:
        candidate = validate_edit(
            context.payload['home_profile'], result['changes']['home_profile'],
            embedded)
    except (ValueError, TypeError, AttributeError):
        raise CheckFault('EDITOR_INPUT_REJECTED') from None
    try:
        with transaction.atomic():
            lock_content('default')
            facts, source_digest = capture(candidate)
        canonical = synchronize(context.payload['home_profile'], candidate, facts)
        canonical = validate_edit(context.payload['home_profile'], canonical,
                                  embedded)
    except ValidationError:
        raise CheckFault('EDITOR_CAPABILITY_UNAVAILABLE') from None
    changed = canonical != result['changes']['home_profile']
    if not changed:
        return result, source_digest
    value = dict(result)
    value['changes'] = {**result['changes'], 'home_profile': canonical}
    value['normalized_fingerprint'] = fingerprint(value['changes'])
    value['changed'] = True
    warning = {'field': 'home_profile',
               'code': 'NORMALIZATION_REVIEW_REQUIRED'}
    value['warnings'] = [*result['warnings']]
    if warning not in value['warnings']:
        value['warnings'].append(warning)
    return value, source_digest


def issue_check_receipt(*, context, result, media_evidence=None,
                        derived_map_hash=None,
                        home_source_digest=_HOME_SOURCE_DEFAULT):
    if (context.child['policy_version'] != policy_constants.POLICY_VERSION
            or result['policy_version'] != policy_constants.POLICY_VERSION):
        raise CheckFault('EDITOR_CONTEXT_CHANGED')
    data = {'protocol': CHECK_POLICY, 'actorId': context.actor_id,
        'semanticPolicy': context.child['policy_version'],
        'generation': context.child['generation'], 'pageId': context.child['page_id'],
        'baseRevisionId': context.child['base_revision_id'], 'contextStamp': context.stamp,
        'permissionHash': context.permission_hash, 'editingFrom': context.child.get('source', {}).get('editingFrom', 'current'),
        'source': context.child.get('source'),
        'inputFingerprint': result['input_fingerprint'],
        'normalizedFingerprint': result['normalized_fingerprint']}
    if media_evidence is not None:
        data['mediaEvidence'] = media_evidence
    if derived_map_hash is not None:
        data['derivedMapHash'] = derived_map_hash
    home_digest = (context.home_source_digest
                   if home_source_digest is _HOME_SOURCE_DEFAULT
                   else home_source_digest)
    if home_digest is not None:
        data['homeSourceDigest'] = home_digest
    return signing.dumps(data, salt=SALT, compress=False)


def verify_check_receipt(token, *, context, changes, media_evidence=None,
                         derived_map_hash=None, _before_fs=False,
                         home_source_digest=_HOME_SOURCE_DEFAULT):
    """Proof only; future writes must still reparse and recheck actual context."""
    if type(token) is not str or len(token) > 8192:
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID')
    try:
        value = signing.loads(token, salt=SALT)  # No new business TTL.
    except (signing.BadSignature, ValueError, TypeError):
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID') from None
    expected = {'protocol', 'semanticPolicy', 'actorId', 'generation', 'pageId', 'baseRevisionId', 'contextStamp',
                'permissionHash', 'editingFrom', 'source', 'inputFingerprint', 'normalizedFingerprint'}
    if media_evidence is not None:
        expected.add('mediaEvidence')
    elif _before_fs and type(value) is dict and 'mediaEvidence' in value:
        expected.add('mediaEvidence')
    if derived_map_hash is not None:
        expected.add('derivedMapHash')
    home_digest = (context.home_source_digest
                   if home_source_digest is _HOME_SOURCE_DEFAULT
                   else home_source_digest)
    if home_digest is not None:
        expected.add('homeSourceDigest')
    if (type(value) is not dict or set(value) != expected
            or value['protocol'] != CHECK_POLICY or value['actorId'] != context.actor_id
            or value['semanticPolicy'] != policy_constants.POLICY_VERSION
            or value['semanticPolicy'] != context.child['policy_version']
            or value['generation'] != context.child['generation']
            or value['pageId'] != context.child['page_id']
            or value['baseRevisionId'] != context.child['base_revision_id']
            or value['contextStamp'] != context.stamp or value['permissionHash'] != context.permission_hash
            or value.get('homeSourceDigest') != home_digest
            or value['source'] != context.child.get('source')
            or value['editingFrom'] != context.child.get('source', {}).get('editingFrom', 'current')
            or type(value['inputFingerprint']) is not str
            or re.fullmatch('[a-f0-9]{64}', value['inputFingerprint']) is None
            or value['normalizedFingerprint'] != fingerprint(changes)):
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID')
    if media_evidence is not None and value.get('mediaEvidence') != media_evidence:
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID')
    if derived_map_hash is not None and value.get('derivedMapHash') != derived_map_hash:
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID')
    if _before_fs and 'mediaEvidence' in value and (type(value['mediaEvidence']) is not str or re.fullmatch('[a-f0-9]{64}', value['mediaEvidence']) is None):
        raise CheckFault('EDITOR_CHECK_RECEIPT_INVALID')
    return value
