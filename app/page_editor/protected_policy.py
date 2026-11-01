"""Pure E1 placement facts. No asset admission, IO or HTTP capability."""
from dataclasses import replace
import hashlib
import json
import re
from uuid import UUID
from .policy_constants import FIELDS, FORMAT_ATTRS, PROTECTED_ATTRS, TAGS
from .types import (PolicyError, ControlledUnsupported, ProtectedBinding,
                    ProtectedAncestor, ProtectedParent, ProtectedContext, PendingAsset)

MARKER_REQUIRED = frozenset({'data-es-protected', 'data-es-image', 'data-es-asset',
                             'data-es-alt', 'data-es-image-align'})
MARKER_OPTIONAL = frozenset({'data-es-width', 'data-es-height'})
INLINE = frozenset({'span', 'a', 'br', 'strong', 'em', 'u', 's', 'sub', 'sup'})


def _fail(code):
    raise PolicyError(code)


def _id(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        _fail('PROTECTED_CONTEXT_INVALID')
    return value


def _sha(value):
    if type(value) is not str or re.fullmatch('[a-f0-9]{64}', value) is None:
        _fail('PROTECTED_CONTEXT_INVALID')


def _digest(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (ValueError, OverflowError):
        raise ControlledUnsupported('PROTECTED_DIMENSION_RESOURCE_UNSUPPORTED') from None
    return hashlib.sha256(encoded).hexdigest()


def _tag(node):
    from .html_policy import _tag as tag
    return tag(node)


def _reference(value, *, embedded=False):
    expected = {'asset_id', 'alt', 'alignment', 'width_px', 'height_px'} | ({'id'} if embedded else set())
    if type(value) is not dict or set(value) != expected:
        _fail('PROTECTED_REFERENCE_MISMATCH')
    _id(value['asset_id'])
    if embedded:
        _id(value['id'])
    from .html_policy import _string
    if type(value['alt']) is not str or len(value['alt']) > 300 or _string(value['alt']) != value['alt']:
        _fail('PROTECTED_REFERENCE_MISMATCH')
    if type(value['alignment']) is not str or value['alignment'] not in ('left', 'center', 'right'):
        _fail('PROTECTED_REFERENCE_MISMATCH')
    for key in ('width_px', 'height_px'):
        if value[key] is not None and (type(value[key]) is not int or value[key] <= 0):
            _fail('PROTECTED_REFERENCE_MISMATCH')


def _marker(node, parent, before, after):
    attrs = node.attrib
    if (_tag(node) != 'span' or not MARKER_REQUIRED <= set(attrs)
            or not set(attrs) <= MARKER_REQUIRED | MARKER_OPTIONAL or list(node) or node.text):
        _fail('PROTECTED_MARKER_INVALID')
    def dimension(key):
        value = attrs.get(key)
        if value is None:
            return None
        if type(value) is not str or re.fullmatch('[1-9][0-9]*', value) is None:
            _fail('PROTECTED_MARKER_INVALID')
        # Existing integer field/isolated worker limits apply. No new content cap.
        try:
            return int(value)
        except (ValueError, OverflowError):
            raise ControlledUnsupported('PROTECTED_DIMENSION_RESOURCE_UNSUPPORTED') from None
    binding = ProtectedBinding(_id(attrs['data-es-protected']), parent, before, after,
        _id(attrs['data-es-image']), _id(attrs['data-es-asset']), attrs['data-es-alt'],
        attrs['data-es-image-align'], dimension('data-es-width'), dimension('data-es-height'), '')
    _reference({'asset_id': binding.asset_id, 'alt': binding.alt, 'alignment': binding.alignment,
                'width_px': binding.width_px, 'height_px': binding.height_px})
    return binding


def _fingerprint(binding, parent, scope_id, field):
    return _digest({'protocol': 'es-protected-placement-v1', 'scope_id': scope_id, 'field': field,
        'layout_id': parent.layout_id, 'parent_id': parent.parent_id,
        'parent_path': list(parent.path),
        'ancestors': [{'tag': item.tag, 'attributes': [list(pair) for pair in item.attributes]}
                      for item in parent.ancestors],
        'sequence': [list(pair) for pair in parent.sequence],
        'marker': {'marker_id': binding.marker_id, 'image_id': binding.image_id,
                   'asset_id': binding.asset_id, 'alt': binding.alt, 'alignment': binding.alignment,
                   'width_px': binding.width_px, 'height_px': binding.height_px},
        'before_slot_id': binding.slot_before_id, 'after_slot_id': binding.slot_after_id})


def _extract(tree, ownership):
    """Walk actual elements, never a declared count or character offset."""
    parents, bindings, identities = [], [], set()
    role_nodes = {}
    stack = [(node, (index,), (), False) for index, node in reversed(list(enumerate(tree)))]
    while stack:
        node, path, chain, inside = stack.pop()
        attrs = node.attrib
        ancestor = ProtectedAncestor(_tag(node), tuple(sorted(attrs.items())))
        chain = chain + (ancestor,)
        roles = set(attrs) & {'data-es-parent', 'data-es-slot', 'data-es-protected'}
        if len(roles) > 1:
            _fail('PROTECTED_MARKER_INVALID')
        if set(attrs) & PROTECTED_ATTRS and not roles:
            _fail('PROTECTED_MARKER_INVALID')
        if roles:
            key = next(iter(roles))
            identity = _id(attrs[key])
            if identity in identities:
                _fail('PROTECTED_PLACEMENT_CHANGED')
            identities.add(identity)
            role_nodes[id(node)] = key
        if 'data-es-parent' in attrs:
            if inside or node.text:
                _fail('PROTECTED_PLACEMENT_CHANGED')
            children = list(node)
            if len(children) < 3 or len(children) % 2 != 1:
                _fail('PROTECTED_PLACEMENT_CHANGED')
            sequence, local, layout_ids = [], [], set()
            for index, child in enumerate(children):
                if child.tail:
                    _fail('PROTECTED_PLACEMENT_CHANGED')
                if index % 2 == 0:
                    if (_tag(child) != 'span' or 'data-es-slot' not in child.attrib
                            or not set(child.attrib) <= FORMAT_ATTRS | {'data-es-slot', 'data-es-anchor'}):
                        _fail('PROTECTED_PLACEMENT_CHANGED')
                    slot = _id(child.attrib['data-es-slot'])
                    for descendant in child.iter():
                        if _tag(descendant) not in INLINE:
                            _fail('PROTECTED_PLACEMENT_CHANGED')
                        special = set(descendant.attrib) & PROTECTED_ATTRS
                        if special and (descendant is not child or special != {'data-es-slot'}):
                            _fail('PROTECTED_PLACEMENT_CHANGED')
                    sequence.append(('slot', slot))
                else:
                    marker_id = child.attrib.get('data-es-protected')
                    if marker_id not in ownership:
                        _fail('PROTECTED_REFERENCE_MISMATCH')
                    layout_ids.add(ownership[marker_id])
                    before = _id(children[index - 1].attrib.get('data-es-slot'))
                    after = _id(children[index + 1].attrib.get('data-es-slot'))
                    binding = _marker(child, attrs['data-es-parent'], before, after)
                    local.append(binding);sequence.append(('marker', binding.marker_id))
            if len(layout_ids) != 1:
                _fail('PROTECTED_REFERENCE_MISMATCH')
            parents.append(ProtectedParent(attrs['data-es-parent'], next(iter(layout_ids)), path, chain, tuple(sequence)))
            bindings.extend(local)
        elif 'data-es-protected' in attrs and not inside:
            _fail('PROTECTED_PLACEMENT_CHANGED')
        elif 'data-es-slot' in attrs and not inside:
            _fail('PROTECTED_PLACEMENT_CHANGED')
        stack.extend((child, path + (index,), chain, inside or 'data-es-parent' in attrs)
                     for index, child in reversed(list(enumerate(node))))
    if set(ownership) != {item.marker_id for item in bindings}:
        _fail('PROTECTED_REFERENCE_MISMATCH')
    return tuple(parents), tuple(bindings)


def _source_context(tree, *, source_sha256, field, scope_id, layout, embedded_images):
    """Only called after whole source syntax/semantic admission."""
    if type(layout) is not list or type(embedded_images) is not list:
        _fail('PROTECTED_CONTEXT_INVALID')
    _id(scope_id)
    if type(field) is not str or field not in FIELDS:
        _fail('POLICY_CONTEXT_INVALID')
    images = {}
    for image in embedded_images:
        _reference(image, embedded=True)
        if image['id'] in images:
            _fail('PROTECTED_REFERENCE_MISMATCH')
        images[image['id']] = image
    ownership, descriptors, layout_ids = {}, {}, set()
    for node in layout:
        if type(node) is not dict or type(node.get('kind')) is not str:
            _fail('PROTECTED_CONTEXT_INVALID')
        layout_id = _id(node.get('id'))
        if layout_id in layout_ids:
            _fail('PROTECTED_CONTEXT_INVALID')
        layout_ids.add(layout_id)
        if node['kind'] == 'protected_ref':
            raise ControlledUnsupported('PROTECTED_SOURCE_AMBIGUOUS')
        if node['kind'] != 'text':
            if node['kind'] == 'price' and set(node) == {'id', 'kind'}:
                continue
            if node['kind'] == 'image' and set(node) == {'id', 'kind', 'image_id'}:
                if _id(node['image_id']) in images:
                    continue
            _fail('PROTECTED_CONTEXT_INVALID')
        if (set(node) != {'id', 'kind', 'field', 'protected_nodes'} or type(node['field']) is not str
                or node['field'] not in FIELDS or type(node['protected_nodes']) is not list):
            _fail('PROTECTED_CONTEXT_INVALID')
        for item in node['protected_nodes']:
            if type(item) is not dict or set(item) != {'id', 'reference_id', 'fingerprint'}:
                _fail('PROTECTED_CONTEXT_INVALID')
            marker_id, image_id = _id(item['id']), _id(item['reference_id'])
            _sha(item['fingerprint'])
            if image_id not in images:
                _fail('PROTECTED_REFERENCE_MISMATCH')
            if node['field'] == field:
                if marker_id in ownership:
                    _fail('PROTECTED_REFERENCE_MISMATCH')
                ownership[marker_id], descriptors[marker_id] = layout_id, item
    parents, bindings = _extract(tree, ownership)
    parent_map = {item.parent_id: item for item in parents}
    result, image_ids = [], set()
    for binding in bindings:
        descriptor = descriptors[binding.marker_id]
        image = images.get(binding.image_id)
        if (binding.image_id in image_ids or descriptor['reference_id'] != binding.image_id or image is None
                or any(getattr(binding, key) != image[key] for key in ('asset_id', 'alt', 'alignment', 'width_px', 'height_px'))):
            _fail('PROTECTED_REFERENCE_MISMATCH')
        image_ids.add(binding.image_id)
        digest = _fingerprint(binding, parent_map[binding.parent_id], scope_id, field)
        if digest != descriptor['fingerprint']:
            raise ControlledUnsupported('PROTECTED_SOURCE_AMBIGUOUS')
        result.append(replace(binding, fingerprint=digest))
    context = ProtectedContext(tuple(result), scope_id, field, source_sha256, parents) if result else ProtectedContext()
    validate_context(context, field=field, scope_id=scope_id)
    return context


def validate_context(context, *, field, scope_id):
    try:
        _validate_context(context, field=field, scope_id=scope_id)
    except ControlledUnsupported:
        raise
    except PolicyError as exc:
        if exc.code in {'POLICY_CONTEXT_INVALID', 'PROTECTED_SCOPE_MISMATCH'}:
            raise
        raise PolicyError('PROTECTED_CONTEXT_INVALID') from None
    except (ValueError, TypeError, UnicodeError, AttributeError):
        raise PolicyError('PROTECTED_CONTEXT_INVALID') from None


def _validate_context(context, *, field, scope_id):
    if type(context) is not ProtectedContext or type(context.nodes) is not tuple or type(context.parents) is not tuple:
        _fail('POLICY_CONTEXT_INVALID')
    if not context.nodes:
        if context.parents or any(value is not None for value in (context.scope_id, context.field, context.source_sha256)):
            _fail('PROTECTED_CONTEXT_INVALID')
        return
    if context.scope_id is None or context.field is None or context.source_sha256 is None or not context.parents:
        _fail('POLICY_CONTEXT_INVALID')
    _id(context.scope_id);_sha(context.source_sha256)
    if type(context.field) is not str or context.field not in FIELDS:
        _fail('PROTECTED_CONTEXT_INVALID')
    if context.scope_id != scope_id or context.field != field:
        _fail('PROTECTED_SCOPE_MISMATCH')
    parents, ids, sequence_ids, ordered = {}, set(), set(), []
    previous_path = None
    from .html_policy import _check_attributes, _string
    for parent in context.parents:
        if type(parent) is not ProtectedParent:
            _fail('PROTECTED_CONTEXT_INVALID')
        _id(parent.parent_id);_id(parent.layout_id)
        if (parent.parent_id in ids or type(parent.path) is not tuple or not parent.path
                or any(type(index) is not int or index < 0 for index in parent.path)
                or previous_path is not None and parent.path <= previous_path
                or type(parent.ancestors) is not tuple or len(parent.ancestors) != len(parent.path)
                or type(parent.sequence) is not tuple or len(parent.sequence) < 3 or len(parent.sequence) % 2 != 1):
            _fail('PROTECTED_CONTEXT_INVALID')
        ids.add(parent.parent_id);previous_path = parent.path
        for ancestor in parent.ancestors:
            if (type(ancestor) is not ProtectedAncestor or type(ancestor.tag) is not str or ancestor.tag not in TAGS
                    or type(ancestor.attributes) is not tuple
                    or any(type(pair) is not tuple or len(pair) != 2 or any(type(item) is not str for item in pair) for pair in ancestor.attributes)):
                _fail('PROTECTED_CONTEXT_INVALID')
            attrs = dict(ancestor.attributes)
            if len(attrs) != len(ancestor.attributes) or tuple(sorted(attrs.items())) != ancestor.attributes or 'style' in attrs:
                _fail('PROTECTED_CONTEXT_INVALID')
            _check_attributes(ancestor.tag, attrs)
            if tuple(sorted(attrs.items())) != ancestor.attributes or any(_string(value) != value for value in attrs.values()):
                _fail('PROTECTED_CONTEXT_INVALID')
        if dict(parent.ancestors[-1].attributes).get('data-es-parent') != parent.parent_id:
            _fail('PROTECTED_CONTEXT_INVALID')
        if (any(set(item.attributes and dict(item.attributes) or ()) & PROTECTED_ATTRS for item in parent.ancestors[:-1])
                or set(dict(parent.ancestors[-1].attributes)) & PROTECTED_ATTRS != {'data-es-parent'}):
            _fail('PROTECTED_CONTEXT_INVALID')
        for index, pair in enumerate(parent.sequence):
            if type(pair) is not tuple or len(pair) != 2 or pair[0] != ('slot' if index % 2 == 0 else 'marker'):
                _fail('PROTECTED_CONTEXT_INVALID')
            _id(pair[1])
            if pair[1] in sequence_ids:
                _fail('PROTECTED_CONTEXT_INVALID')
            sequence_ids.add(pair[1])
            if index % 2:
                ordered.append((parent, index, pair[1]))
        parents[parent.parent_id] = parent
    if ids & sequence_ids or len(ordered) != len(context.nodes):
        _fail('PROTECTED_CONTEXT_INVALID')
    image_ids = set()
    for binding, (parent, index, marker_id) in zip(context.nodes, ordered):
        if type(binding) is not ProtectedBinding:
            _fail('PROTECTED_CONTEXT_INVALID')
        for identity in (binding.marker_id, binding.parent_id, binding.slot_before_id, binding.slot_after_id, binding.image_id, binding.asset_id):
            _id(identity)
        _sha(binding.fingerprint)
        _reference({'asset_id': binding.asset_id, 'alt': binding.alt, 'alignment': binding.alignment,
                    'width_px': binding.width_px, 'height_px': binding.height_px})
        if (binding.marker_id != marker_id or binding.parent_id != parent.parent_id
                or binding.slot_before_id != parent.sequence[index - 1][1]
                or binding.slot_after_id != parent.sequence[index + 1][1]
                or binding.image_id in image_ids
                or _fingerprint(binding, parent, scope_id, field) != binding.fingerprint):
            _fail('PROTECTED_CONTEXT_INVALID')
        image_ids.add(binding.image_id)


def validate_tree(tree, *, context, field, scope_id, owner):
    validate_context(context, field=field, scope_id=scope_id)
    if not context.nodes:
        if any(set(node.attrib) & PROTECTED_ATTRS for node in tree.iter()):
            raise ControlledUnsupported('PROTECTED_INTEGRATION_UNSUPPORTED')
        return ()
    layout_ids = {item.parent_id: item.layout_id for item in context.parents}
    ownership = {item.marker_id: layout_ids[item.parent_id] for item in context.nodes}
    parents, bindings = _extract(tree, ownership)
    if [item.parent_id for item in parents] != [item.parent_id for item in context.parents]:
        _fail('PROTECTED_PLACEMENT_CHANGED')
    # A path-only shift needs a later structural-edit algorithm. Slot edits do
    # not change element paths; swapping parent identities is rejected above.
    for actual, expected in zip(parents, context.parents):
        if actual.sequence != expected.sequence or actual.layout_id != expected.layout_id:
            _fail('PROTECTED_PLACEMENT_CHANGED')
        if actual.ancestors != expected.ancestors:
            _fail('PROTECTED_PLACEMENT_CHANGED')
        if actual.path != expected.path:
            raise ControlledUnsupported('PROTECTED_STRUCTURE_EDIT_UNSUPPORTED')
    expected_bindings = tuple(replace(item, fingerprint='') for item in context.nodes)
    if bindings != expected_bindings:
        if owner:
            raise ControlledUnsupported('PROTECTED_INTEGRATION_UNSUPPORTED')
        _fail('PROTECTED_REFERENCE_MISMATCH')
    return tuple(PendingAsset(item.image_id, item.asset_id) for item in bindings)


def build_protected_context(source_html, *, field, scope_id, layout, embedded_images, url_context=None):
    from .html_policy import _build_protected_source
    return _build_protected_source(source_html, field=field, scope_id=scope_id,
                                   layout=layout, embedded_images=embedded_images, url_context=url_context)
