"""Parent-only issuance and authorization. No signing key crosses into child."""
import copy
from uuid import uuid4
from django.core import signing
from django.core.exceptions import ValidationError
from page_versions import schema as S
from .checks import CheckFault
from .input_policy import fingerprint, identifier, image_reference
from .embedded_policy import layout_id

SALT = 'estakada.editor.embedded.issue.v1'
FIELDS = ('intro_text', 'main_text')
ID_KEYS = {'layoutId', 'parentId', 'markerId', 'imageId', 'slotBeforeId', 'slotAfterId'}
CLAIM_KEYS = {'v', 'action', 'actorId', 'generation', 'pageId', 'sourceStamp', 'field', 'ids',
              'image', 'sourceMarkerFingerprint', 'oldImageId'}


def _invalid():
    raise CheckFault('EDITOR_EMBEDDED_INVALID')


def load_permit(token, context):
    try:
        if type(token) is not str or not 0 < len(token) <= 8192:
            _invalid()
        value = signing.loads(token, salt=SALT)
        if type(value) is not dict or set(value) != CLAIM_KEYS or value['v'] != 'embedded-v1':
            _invalid()
        validate_binding(value)
        if (type(value['actorId']) is not int or value['actorId'] <= 0
                or type(value['generation']) is not int or value['generation'] <= 0
                or type(value['action']) is not str or value['action'] not in ('insert', 'replace')
                or type(value['sourceStamp']) is not str or len(value['sourceStamp']) != 64
                or any(char not in '0123456789abcdef' for char in value['sourceStamp'])):
            _invalid()
        identifier(value['pageId'])
    except (signing.BadSignature, ValueError, TypeError, ValidationError):
        raise CheckFault('EDITOR_EMBEDDED_INVALID') from None
    if (value['actorId'] != context.actor_id or value['generation'] != context.child['generation']
            or value['pageId'] != context.child['page_id'] or value['sourceStamp'] != context.stamp):
        raise CheckFault('EDITOR_EMBEDDED_STALE')
    return value


def validate_binding(value):
    if (type(value.get('field')) is not str or value['field'] not in FIELDS
            or type(value.get('ids')) is not dict or set(value['ids']) != ID_KEYS):
        _invalid()
    for item in value['ids'].values():
        identifier(item)
    if len(set(value['ids'].values())) != len(value['ids']):
        _invalid()
    if image_reference(value['image']) != value['image'] or value['image'] is None:
        _invalid()
    if value.get('sourceMarkerFingerprint') is not None:
        digest = value['sourceMarkerFingerprint']
        if type(digest) is not str or len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest):
            _invalid()
    if value.get('oldImageId') is not None:
        identifier(value['oldImageId'])


def source_marker(context, field, marker_id):
    matches = [item for node in context.payload['layout'] if node['kind'] == 'text' and node['field'] == field
               for item in node['protected_nodes'] if item['id'] == marker_id]
    if len(matches) != 1:
        raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
    row = matches[0]
    images = [item for item in context.payload['embedded_images'] if item['id'] == row['reference_id']]
    if len(images) != 1:
        _invalid()
    return row, images[0]


def issue(context, value, source_bindings):
    if not context.child['owner']:
        raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
    field, action = value['field'], value['action']
    for binding in source_bindings:
        if type(binding) is not dict or set(binding) != {'field', 'ids', 'image', 'sourceMarkerFingerprint', 'oldImageId'}:
            raise CheckFault('EDITOR_WORKER_PROTOCOL')
        validate_binding(binding)
    if action == 'insert':
        parent = str(uuid4())
        ids = {key: str(uuid4()) for key in ID_KEYS}
        ids.update(parentId=parent, layoutId=layout_id(parent))
        source_fp = old_id = None
    elif value['priorPermit'] is not None:
        prior = load_permit(value['priorPermit'], context)
        if prior['field'] != field or prior['ids']['markerId'] != value['markerId']:
            raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
        ids = {**prior['ids'], 'imageId': str(uuid4())}
        source_fp, old_id = prior['sourceMarkerFingerprint'], prior['oldImageId'] or prior['ids']['imageId']
        if source_fp is not None:
            row, _ = source_marker(context, field, value['markerId'])
            if row['fingerprint'] != source_fp or row['reference_id'] != old_id:
                raise CheckFault('EDITOR_EMBEDDED_STALE')
    else:
        choices = [item for item in source_bindings if item['field'] == field and item['ids']['markerId'] == value['markerId']]
        if len(choices) != 1:
            raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
        existing = choices[0]
        row, image = source_marker(context, field, value['markerId'])
        if (existing['sourceMarkerFingerprint'] != row['fingerprint'] or existing['ids']['imageId'] != image['id']
                or existing['image'] != {key: image[key] for key in ('asset_id', 'alt', 'alignment', 'width_px', 'height_px')}):
            _invalid()
        ids = {**existing['ids'], 'imageId': str(uuid4())}
        source_fp, old_id = row['fingerprint'], image['id']
    claims = {'v': 'embedded-v1', 'action': action, 'actorId': context.actor_id,
        'generation': context.child['generation'], 'pageId': context.child['page_id'], 'sourceStamp': context.stamp,
        'field': field, 'ids': ids, 'image': value['image'], 'sourceMarkerFingerprint': source_fp, 'oldImageId': old_id}
    return claims


def sign_issue(claims):
    return {'permit': signing.dumps(claims, salt=SALT, compress=False),
            **{key: claims[key] for key in ('field', 'action', 'ids', 'image')}}


def validate_derived(context, result, *, save=False):
    """Independently compare signed claims and DB source, not a worker flag."""
    derived, bindings = result.get('derived'), result.get('intentBindings')
    if (type(derived) is not dict or set(derived) != {'embedded_images', 'layout', 'mapHash'}
            or type(bindings) is not list
            or derived['mapHash'] != fingerprint({key: derived[key] for key in ('embedded_images', 'layout')})):
        _invalid()
    try:
        payload = {**context.payload, **result['changes'],
                   'embedded_images': derived['embedded_images'], 'layout': derived['layout']}
        S.Snapshot.trusted(payload)
    except (ValidationError, ValueError, TypeError):
        _invalid()
    source_rows = {node['id']: node for node in context.payload['layout']}
    source_markers = {(node['field'], marker['id']): (node['id'], marker)
        for node in context.payload['layout'] if node['kind'] == 'text' for marker in node['protected_nodes']}
    image_rows = {item['id']: item for item in derived['embedded_images']}
    marker_rows = {}
    for node in derived['layout']:
        source = source_rows.get(node['id'])
        if source is not None:
            if {key: value for key, value in node.items() if key != 'protected_nodes'} != {key: value for key, value in source.items() if key != 'protected_nodes'}:
                _invalid()
            if node['kind'] == 'text' and {item['id'] for item in node['protected_nodes']} != {item['id'] for item in source['protected_nodes']}:
                _invalid()
        elif node['kind'] != 'text':
            _invalid()
        if node['kind'] == 'text':
            for marker in node['protected_nodes']:
                key = node['field'], marker['id']
                if key in marker_rows:
                    _invalid()
                marker_rows[key] = (node['id'], marker)
    if not set(source_rows) <= {node['id'] for node in derived['layout']}:
        _invalid()
    if not set(source_markers) <= set(marker_rows):
        _invalid()
    for key, (layout_id_value, _) in source_markers.items():
        if marker_rows[key][0] != layout_id_value:
            _invalid()
    seen = set()
    for binding in bindings:
        if type(binding) is not dict or set(binding) != {'field', 'token', 'ids', 'image', 'sourceMarkerFingerprint', 'oldImageId'}:
            _invalid()
        try:
            validate_binding(binding)
        except (ValueError, TypeError):
            _invalid()
        key = binding['field'], binding['ids']['markerId']
        if key in seen or key not in marker_rows:
            _invalid()
        seen.add(key)
        layout, marker = marker_rows[key]
        if (layout != binding['ids']['layoutId'] or marker['reference_id'] != binding['ids']['imageId']
                or image_rows.get(marker['reference_id']) != {'id': binding['ids']['imageId'], **binding['image']}):
            _invalid()
        old_matches = [item for node in context.payload['layout'] if node['kind'] == 'text' and node['field'] == key[0]
                       for item in node['protected_nodes'] if item['id'] == key[1]]
        old = old_matches[0] if len(old_matches) == 1 else None
        if (binding['sourceMarkerFingerprint'] != (old['fingerprint'] if old else None)
                or binding['oldImageId'] != (old['reference_id'] if old else None)):
            _invalid()
        changed = old is None or old['reference_id'] != marker['reference_id']
        if not context.child['owner']:
            if binding['token'] is not None or changed or derived['layout'] != context.payload['layout'] or derived['embedded_images'] != context.payload['embedded_images']:
                raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
        elif not save:
            if binding['token'] is None:
                if changed:
                    raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
            else:
                claims = load_permit(binding['token'], context)
                if any(claims[key] != binding[key] for key in ('field', 'ids', 'image')):
                    raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
                if old is None:
                    if claims['sourceMarkerFingerprint'] is not None or claims['ids']['layoutId'] != layout_id(claims['ids']['parentId']):
                        raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
                elif claims['action'] != 'replace' or claims['sourceMarkerFingerprint'] != old['fingerprint'] or claims['oldImageId'] != old['reference_id']:
                    raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
        elif binding['token'] is not None:
            _invalid()
    if seen != set(marker_rows):
        _invalid()
    # No unrelated ImageRef mutation/deletion through a derived child object.
    active = {row['reference_id'] for _, row in marker_rows.values()}
    active.update(node['image_id'] for node in derived['layout'] if node['kind'] == 'image')
    source_images = {item['id']: item for item in context.payload['embedded_images']}
    new_refs = {binding['ids']['imageId'] for binding in bindings if binding['ids']['imageId'] not in source_images}
    replaced = {old['reference_id'] for key, (_, old) in source_markers.items()
                if marker_rows[key][1]['reference_id'] != old['reference_id']}
    expected_images = (set(source_images) - (replaced - active)) | new_refs
    if set(image_rows) != expected_images:
        _invalid()
    new_layouts = {binding['ids']['layoutId'] for binding in bindings
                   if (binding['field'], binding['ids']['markerId']) not in source_markers}
    actual_new_layouts = {node['id'] for node in derived['layout']} - set(source_rows)
    if actual_new_layouts != new_layouts:
        _invalid()
    for node in derived['layout']:
        if node['id'] in actual_new_layouts and (node['kind'] != 'text' or len(node['protected_nodes']) != 1):
            _invalid()
    for identifier, image in source_images.items():
        if identifier in image_rows and image_rows[identifier] != image:
            _invalid()
        if identifier not in image_rows and identifier in active:
            _invalid()
    return payload, derived['mapHash'] if bindings or context.payload['embedded_images'] else None


def preview_mapping(context, payload, bindings):
    from .media import derivatives
    from .source_context import current_selector
    from .media import source_query
    result = {field: [] for field in FIELDS}
    original = {item['id'] for item in context.payload['embedded_images']}
    prefix = f"/manage/pages/{context.child['page_id']}/edit/media/"
    for binding in bindings:
        image_id = binding['ids']['imageId']
        files = derivatives(binding['image']['asset_id'])
        pending = image_id not in original
        if pending and not context.child['owner']:
            raise CheckFault('EDITOR_EMBEDDED_FORBIDDEN')
        root = prefix + ('picker-files/' if pending else 'files/')
        query = '' if pending else source_query(context.child['source'])
        result[binding['field']].append({'markerId': binding['ids']['markerId'], 'imageId': image_id,
            'reference': binding['image'], 'url': root + str(files['main'].pk) + '/' + query,
            'thumbnailUrl': root + str(files['preview'].pk) + '/' + query})
    return result
