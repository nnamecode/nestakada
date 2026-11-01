"""Single-child embedded derivation. Provisional owner output is NOT authority."""
import copy
from dataclasses import asdict, replace
import hashlib
from uuid import UUID, uuid5
from .html_parser import parse_fragment
from . import html_policy as H, protected_policy as P
from .types import ProtectedContext, PolicyError, ControlledUnsupported, URLContext
from .input_policy import fingerprint

FIELDS = ('intro_text', 'main_text')


def layout_id(parent_id):
    return str(uuid5(UUID(parent_id), 'es-embedded-layout-v1'))


def _image(binding):
    return {name: getattr(binding, name) for name in ('asset_id', 'alt', 'alignment', 'width_px', 'height_px')}


def _ids(binding, parent):
    return {'layoutId': parent.layout_id, 'parentId': binding.parent_id, 'markerId': binding.marker_id,
        'imageId': binding.image_id, 'slotBeforeId': binding.slot_before_id, 'slotAfterId': binding.slot_after_id}


def source_maps(context):
    source = context['embedded_source']
    url = URLContext(context['page_path'], context['origin'])
    result = {}
    for field in FIELDS:
        protected = any(node.get('kind') == 'text' and node.get('field') == field and node.get('protected_nodes')
                        for node in source['layout'])
        if protected or 'data-es-' in source[field] and any(name in source[field] for name in ('data-es-parent', 'data-es-protected', 'data-es-slot')):
            result[field] = P.build_protected_context(source[field], field=field, scope_id=context['page_id'],
                layout=source['layout'], embedded_images=source['embedded_images'], url_context=url)
        else:
            result[field] = ProtectedContext()
    return result


def source_bindings(context, maps=None):
    maps = source_maps(context) if maps is None else maps
    result = []
    for field in FIELDS:
        parents = {item.parent_id: item for item in maps[field].parents}
        for binding in maps[field].nodes:
            result.append({'field': field, 'ids': _ids(binding, parents[binding.parent_id]), 'image': _image(binding),
                'sourceMarkerFingerprint': binding.fingerprint, 'oldImageId': binding.image_id})
    return result


def _candidate(tree, source_map, *, field, scope_id, owner):
    if not owner:
        P.validate_tree(tree, context=source_map, field=field, scope_id=scope_id, owner=False)
        return source_map
    existing = {item.parent_id: item.layout_id for item in source_map.parents}
    ownership = {item.marker_id: existing[item.parent_id] for item in source_map.nodes}
    new = set()
    for node in tree.iter():
        parent_id = node.attrib.get('data-es-parent')
        if parent_id and parent_id not in existing:
            P._id(parent_id)
            if node not in list(tree) or H._tag(node) != 'p' or len(list(node)) != 3:
                raise ControlledUnsupported('PROTECTED_STRUCTURE_EDIT_UNSUPPORTED')
            new.add(parent_id)
            for child in node:
                marker_id = child.attrib.get('data-es-protected')
                if marker_id:
                    if marker_id in ownership:
                        raise PolicyError('PROTECTED_PLACEMENT_CHANGED')
                    ownership[marker_id] = layout_id(parent_id)
    parents, bindings = P._extract(tree, ownership)
    projected = copy.deepcopy(tree)
    for child in list(projected):
        if child.attrib.get('data-es-parent') in new:
            projected.remove(child)
    old_ownership = {item.marker_id: existing[item.parent_id] for item in source_map.nodes}
    old_parents, _ = P._extract(projected, old_ownership)
    if old_parents != source_map.parents:
        raise ControlledUnsupported('PROTECTED_STRUCTURE_EDIT_UNSUPPORTED')
    parent_map = {item.parent_id: item for item in parents}
    nodes = tuple(replace(item, fingerprint=P._fingerprint(item, parent_map[item.parent_id], scope_id, field)) for item in bindings)
    if not nodes:
        return ProtectedContext()
    result = ProtectedContext(nodes, scope_id, field, hashlib.sha256(H._serialize(tree).encode()).hexdigest(), parents)
    P.validate_context(result, field=field, scope_id=scope_id)
    return result


def normalize_fields(changes, context):
    """Return normalized rich fields plus closed derived metadata, no crypto."""
    maps = source_maps(context)
    source = context['embedded_source']
    output, warnings, tokens, final_maps, comparison = {}, [], {}, {}, {}
    remaining = 20000
    for field in FIELDS:
        value = changes.get(field, source[field])
        if field not in changes:
            final_maps[field] = maps[field]
            continue
        if type(value) is not str:
            raise PolicyError('INPUT_TYPE_INVALID')
        try:
            original_bytes = value.encode('utf-8')
        except UnicodeError:
            raise PolicyError('UTF8_INVALID') from None
        if len(original_bytes) > H.MAX_SOURCE_BYTES:
            raise PolicyError('SOURCE_BYTE_LIMIT')
        candidate = H._string(value.replace('\r\n', '\n').replace('\r', '\n'), multiline=True)
        allow = context['owner'] and context.get('action') not in ('save', 'draft', 'embedded-issue')
        H._scan(candidate, context['owner'], allow_media_intent=allow)
        tree = parse_fragment(candidate)
        H._metrics(tree, len(original_bytes))
        for node in tree.iter():
            if 'data-es-media-intent' in node.attrib:
                marker_id = node.attrib.get('data-es-protected')
                if not allow or not marker_id or (field, marker_id) in tokens:
                    raise PolicyError('PROTECTED_MARKER_INVALID')
                tokens[field, marker_id] = node.attrib.pop('data-es-media-intent')
        cleaned_source = H._serialize(tree)
        comparison[field] = value if candidate != value else (
            cleaned_source if any(key[0] == field for key in tokens) else value)
        built = []
        def builder(normalized_tree):
            candidate = _candidate(normalized_tree, maps[field], field=field, scope_id=context['page_id'], owner=context['owner'])
            built.append(candidate)
            return candidate
        result, final_map = H._normalize_html(cleaned_source, owner=context['owner'], field=field,
            scope_id=context['page_id'], protected_context=maps[field], url_context=URLContext(context['page_path'], context['origin']),
            table_budget_remaining=remaining, map_builder=builder)
        remaining -= result.ui_table_slots_used
        output[field], final_maps[field] = result.html, final_map
        warnings.extend({'field': field, 'code': item.code} for item in result.warnings)
        if result.html != comparison[field] and {'field': field, 'code': 'NORMALIZATION_REVIEW_REQUIRED'} not in warnings:
            warnings.append({'field': field, 'code': 'NORMALIZATION_REVIEW_REQUIRED'})
    layout = copy.deepcopy(source['layout'])
    images = {item['id']: copy.deepcopy(item) for item in source['embedded_images']}
    by_layout = {item['id']: item for item in layout}
    intents, active_refs, replaced_refs = [], set(), set()
    for field in FIELDS:
        known = {item.marker_id: item for item in maps[field].nodes}
        parents = {item.parent_id: item for item in final_maps[field].parents}
        wanted = {}
        for binding in final_maps[field].nodes:
            parent = parents[binding.parent_id]
            image = {'id': binding.image_id, **_image(binding)}
            if binding.image_id in images and images[binding.image_id] != image:
                raise PolicyError('PROTECTED_REFERENCE_MISMATCH')
            images[binding.image_id] = image
            active_refs.add(binding.image_id)
            wanted.setdefault(parent.layout_id, []).append({'id': binding.marker_id,
                'reference_id': binding.image_id, 'fingerprint': binding.fingerprint})
            old = known.get(binding.marker_id)
            if old is not None and old.image_id != binding.image_id:
                replaced_refs.add(old.image_id)
            intents.append({'field': field, 'token': tokens.get((field, binding.marker_id)),
                'ids': _ids(binding, parent), 'image': _image(binding),
                'sourceMarkerFingerprint': old.fingerprint if old else None,
                'oldImageId': old.image_id if old else None})
        for identifier, nodes in wanted.items():
            if identifier in by_layout:
                row = by_layout[identifier]
                if row.get('kind') != 'text' or row.get('field') != field:
                    raise PolicyError('PROTECTED_REFERENCE_MISMATCH')
                row['protected_nodes'] = nodes
            else:
                row = {'id': identifier, 'kind': 'text', 'field': field, 'protected_nodes': nodes}
                layout.append(row);by_layout[identifier] = row
    active_refs.update(node['image_id'] for node in layout if node.get('kind') == 'image')
    embedded = [image for identifier, image in images.items() if identifier not in replaced_refs or identifier in active_refs]
    derived = {'embedded_images': embedded, 'layout': layout}
    derived['mapHash'] = fingerprint(derived)
    return output, warnings, derived, intents, comparison
