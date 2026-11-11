"""Static resource-limited PageInput producer. No Django, DB or filesystem IO."""
import hashlib
from .input_policy import decode_input, validate_context, plain, fingerprint, image_reference
from .price_policy import normalize_price


def rejected(code):
    return {'accepted': False, 'code': code}


def normalize(raw, context):
    from .html_parser import _parse_session
    with _parse_session():
        return _normalize(raw, context)


def _normalize(raw, context):
    context = validate_context(context)
    from .policy_constants import POLICY_VERSION
    if context['policy_version'] != POLICY_VERSION:
        raise RuntimeError('EDITOR_POLICY_CHANGED')
    if context.get('action') == 'embedded-issue':
        from .embedded_policy import source_bindings
        return {'sourceBindings': source_bindings(context)}
    save = context.get('action') in ('save', 'draft')
    draft = context.get('action') == 'draft'
    value = decode_input(raw, save=save, draft=draft)
    source = context.get('source', {'editingFrom': 'current', 'draftBasis': None, 'stageId': None,
                                    'rebase': False, 'targetCurrentId': None})
    source_matches = (all(value[key] == source[key] for key in ('editingFrom', 'draftBasis', 'stageId'))
                      and (not draft or value['rebase'] == source['rebase']))
    if save:
        metadata = {'operationId': value['operationId'], 'checkReceipt': value['checkReceipt'],
                    'baseRevisionId': value['baseRevisionId'], 'generation': value['generation'],
                    'fields': sorted(value['changes']), 'editingFrom': value['editingFrom'],
                    # Permanent current receipts predate source selectors. Their
                    # exact-request fingerprint must survive this extension.
                    'fingerprint': fingerprint(value) if source == {
                        'editingFrom': 'current', 'draftBasis': None, 'stageId': None,
                        'rebase': False, 'targetCurrentId': None
                    } else fingerprint({'input': value, 'source': source}),
                    'source': source, 'action': 'draft' if draft else 'save'}
        if not source_matches:
            return {**rejected('EDITOR_INPUT_REJECTED'), 'save_request': metadata}
        if context.get('can_read_source') is False:
            return {**rejected('EDITOR_BASE_UNAVAILABLE'), 'save_request': metadata}
        candidate_context = dict(context, base_revision_id=value['baseRevisionId'])
        try:
            result = _normalize_value(value, candidate_context, raw, POLICY_VERSION)
        except (ValueError, UnicodeError):
            result = rejected('EDITOR_INPUT_REJECTED')
        result['save_request'] = metadata
        return result
    if not source_matches:
        return rejected('EDITOR_INPUT_REJECTED')
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

    # Lazy imports keep this native dependency boundary entirely in the child.
    from .html_policy import normalize_html
    from .types import ProtectedContext, ControlledUnsupported, URLContext
    url_context = URLContext(page_path=context['page_path'], origin=context['origin'])
    normalized = {}
    warnings = []
    comparison = changes
    derived = intents = None
    if 'embedded_source' in context:
        from .embedded_policy import normalize_fields
        from .types import ControlledUnsupported
        try:
            rich, rich_warnings, derived, intents, projection = normalize_fields(changes, context)
        except ControlledUnsupported:
            return rejected('EDITOR_CAPABILITY_UNAVAILABLE')
        normalized.update(rich);warnings.extend(rich_warnings)
        comparison = {**changes, **projection}
    remaining = 20000
    for field in ('intro_text', 'main_text'):
        if field not in changes or 'embedded_source' in context:
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
    for field in ('main_image', 'preview_image'):
        if field in changes:
            normalized[field] = image_reference(changes[field])
    if 'home_profile' in changes:
        if not context['owner'] or 'embedded_source' not in context:
            raise ValueError('EDITOR_INPUT_INVALID')
        from page_versions.home_profile import validate as validate_home_profile
        normalized['home_profile'] = validate_home_profile(
            changes['home_profile'], context['embedded_source']['embedded_images'])
    if normalized != comparison:
        for field in normalized:
            item = {'field': field, 'code': 'NORMALIZATION_REVIEW_REQUIRED'}
            if normalized[field] != comparison[field] and item not in warnings:
                warnings.append(item)
    result = {'accepted': True, 'changes': normalized, 'warnings': warnings,
            'policy_version': POLICY_VERSION,
            'changed': normalized != comparison,
            'input_fingerprint': hashlib.sha256(raw).hexdigest(),
            'normalized_fingerprint': fingerprint(normalized)}
    if derived is not None:
        result.update(derived=derived, intentBindings=intents)
    return result
