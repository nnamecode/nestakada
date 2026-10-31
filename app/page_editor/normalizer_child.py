"""Static resource-limited PageInput producer. No Django, DB or filesystem IO."""
import hashlib
from .input_policy import decode_input, validate_context, plain, fingerprint
from .price_policy import normalize_price


def rejected(code):
    return {'accepted': False, 'code': code}


def normalize(raw, context):
    context = validate_context(context)
    from .policy_constants import POLICY_VERSION
    if context['policy_version'] != POLICY_VERSION:
        raise RuntimeError('EDITOR_POLICY_CHANGED')
    save = context.get('action') == 'save'
    value = decode_input(raw, save=save)
    if save:
        metadata = {'operationId': value['operationId'], 'checkReceipt': value['checkReceipt'],
                    'baseRevisionId': value['baseRevisionId'], 'generation': value['generation'],
                    'fields': sorted(value['changes']), 'editingFrom': value['editingFrom'],
                    'fingerprint': fingerprint(value)}
        candidate_context = dict(context, base_revision_id=value['baseRevisionId'])
        try:
            result = _normalize_value(value, candidate_context, raw, POLICY_VERSION)
        except (ValueError, UnicodeError):
            result = rejected('EDITOR_INPUT_REJECTED')
        result['save_request'] = metadata
        return result
    return _normalize_value(value, context, raw, POLICY_VERSION)


def _normalize_value(value, context, raw, POLICY_VERSION):
    if value['generation'] != context['generation']:
        return rejected('EDITOR_IDENTITY_CHANGED')
    if value['baseRevisionId'] != context['base_revision_id']:
        return rejected('EDITOR_BASE_CONFLICT')
    changes = value['changes']
    if not set(changes) <= set(context['fields']):
        return rejected('EDITOR_FIELDS_FORBIDDEN')
    if value['editingFrom'] == 'owner-draft' and not context['owner']:
        return rejected('EDITOR_FIELDS_FORBIDDEN')
    if value['editingFrom'] != 'current' or any(field in changes for field in ('main_image', 'preview_image')):
        return rejected('EDITOR_CAPABILITY_UNAVAILABLE')

    # Lazy imports keep this native dependency boundary entirely in the child.
    from .html_policy import normalize_html
    from .types import ProtectedContext, ControlledUnsupported, URLContext
    url_context = URLContext(page_path=context['page_path'], origin=context['origin'])
    normalized = {}
    warnings = []
    remaining = 20000
    for field in ('intro_text', 'main_text'):
        if field not in changes:
            continue
        try:
            result = normalize_html(changes[field], owner=context['owner'], field=field,
                scope_id=context['page_id'], protected_context=ProtectedContext(),
                url_context=url_context, table_budget_remaining=remaining)
        except ControlledUnsupported:
            return rejected('EDITOR_CAPABILITY_UNAVAILABLE')
        if field in context['protected_fields']:
            return rejected('EDITOR_CAPABILITY_UNAVAILABLE')
        remaining -= result.ui_table_slots_used
        normalized[field] = result.html
        warnings.extend({'field': item.field, 'code': item.code} for item in result.warnings)
    if 'price' in changes:
        normalized['price'] = normalize_price(changes['price'])
    for field, limit in (('h1', 255), ('title', 255), ('description', 1000)):
        if field in changes:
            normalized[field] = plain(changes[field], limit, multiline=field == 'description')
    if 'indexing_allowed' in changes:
        if type(changes['indexing_allowed']) is not bool:
            raise ValueError('EDITOR_INPUT_INVALID')
        normalized['indexing_allowed'] = changes['indexing_allowed']
    if normalized != changes:
        for field in normalized:
            item = {'field': field, 'code': 'NORMALIZATION_REVIEW_REQUIRED'}
            if normalized[field] != changes[field] and item not in warnings:
                warnings.append(item)
    return {'accepted': True, 'changes': normalized, 'warnings': warnings,
            'policy_version': POLICY_VERSION,
            'changed': normalized != changes,
            'input_fingerprint': hashlib.sha256(raw).hexdigest(),
            'normalized_fingerprint': fingerprint(normalized)}
