"""Closed shared component structure; never a template or script interpreter."""
import hashlib
from html import escape
import re
import unicodedata
from urllib.parse import unquote, urlsplit
from uuid import UUID

POLICY = 'shared-policy-v1'
PROTOCOL = 'shared-editor-v1'
MAX_HTML = 1048576


def canonical_uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError('SHARED_INVALID_ID')
    return value


def safe_url(value, schemes, *, allow_relative=True):
    if type(value) is not str or not value or value != value.strip():
        raise ValueError('SHARED_LINK_INVALID')
    decoded = value
    for _ in range(3):
        decoded = unquote(decoded)
        if any(ord(c) < 33 or ord(c) == 127 for c in decoded) or '\\' in decoded:
            raise ValueError('SHARED_LINK_INVALID')
    parts = urlsplit(decoded)
    if parts.scheme:
        if parts.scheme.lower() not in schemes or parts.username or parts.password:
            raise ValueError('SHARED_LINK_INVALID')
        if parts.scheme.lower() in ('http', 'https') and not parts.netloc:
            raise ValueError('SHARED_LINK_INVALID')
        if parts.scheme.lower() == 'tel' and not re.fullmatch(r'\+?[0-9()-]+', parts.path):
            raise ValueError('SHARED_LINK_INVALID')
    else:
        if not allow_relative or (not (decoded.startswith('/') and not decoded.startswith('//'))
                                  and not decoded.startswith('#')):
            raise ValueError('SHARED_LINK_INVALID')
    return value


def normalize_html(source, kind):
    # Native/parser dependencies belong to the approved short-lived child image.
    # Parent URL/model imports use only this module's closed protocol constants.
    import html5lib

    if kind not in ('header', 'footer') or type(source) is not str or len(source.encode('utf-8')) > MAX_HTML:
        raise ValueError('SHARED_HTML_LIMIT')
    source = unicodedata.normalize('NFC', source.replace('\r\n', '\n').replace('\r', '\n'))
    if any(token in source for token in ('{{', '{%', '{#')) or any(ord(c) < 32 and c not in '\t\n' for c in source):
        raise ValueError('SHARED_ACTIVE_CONTENT')
    try:
        parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder('etree'),
                                    namespaceHTMLElements=False, strict=True)
        tree = parser.parseFragment(source, container='div', scripting=False)
    except html5lib.html5parser.ParseError:
        raise ValueError('SHARED_HTML_INVALID') from None
    return validate_tree(tree, kind)


def validate_tree(tree, kind):
    """One closed component grammar shared by child and public AST readers."""
    if kind not in ('header', 'footer'):
        raise ValueError('SHARED_ROOT_INVALID')
    if len(tree) != 1 or (tree.text or '').strip() or (tree[0].tail or '').strip():
        raise ValueError('SHARED_ROOT_INVALID')
    stack, count = [(tree[0], 1)], 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > 20000 or depth > 32 or type(node.tag) is not str:
            raise ValueError('SHARED_DOM_LIMIT')
        stack.extend((child, depth + 1) for child in node)
    bindings = []

    def element(node, tag, cls=None, *, attrs=(), fixed=None, children=None, text=False):
        allowed = set(attrs) | ({'class'} if cls else set()) | set(fixed or {})
        if node.tag != tag or set(node.attrib) - allowed:
            raise ValueError('SHARED_STRUCTURE_INVALID')
        if cls is not None and node.attrib.get('class') != cls:
            raise ValueError('SHARED_CLASS_INVALID')
        if any(node.attrib.get(key) != value for key, value in (fixed or {}).items()):
            raise ValueError('SHARED_FIXED_ATTRIBUTE')
        if children is not None and len(node) != children:
            raise ValueError('SHARED_STRUCTURE_INVALID')
        if not text and (node.text or '').strip():
            raise ValueError('SHARED_STRUCTURE_TEXT')
        if any((child.tail or '').strip() for child in node) and not text:
            raise ValueError('SHARED_STRUCTURE_TEXT')
        return node

    def leaf(node, tag):
        return element(node, tag, children=0, text=True)

    def link(node, cls=None, *, schemes=('http', 'https'), label=False, relative=True):
        element(node, 'a', cls, attrs=('href', 'aria-label') if label else ('href',))
        safe_url(node.attrib.get('href'), schemes, allow_relative=relative)

    def image(node, slot):
        element(node, 'img', attrs=('data-es-shared-asset', 'alt', 'width', 'height'), children=0)
        asset = canonical_uuid(node.attrib.get('data-es-shared-asset'))
        if 'alt' not in node.attrib:
            raise ValueError('SHARED_IMAGE_ALT_REQUIRED')
        for key in ('width', 'height'):
            if key in node.attrib and not re.fullmatch(r'[1-9][0-9]{0,3}|10000', node.attrib[key]):
                raise ValueError('SHARED_IMAGE_DIMENSION')
        bindings.append({'assetId': asset, 'slot': slot})

    def brand(node, slot):
        link(node, 'es-brand', label=True)
        if len(node) != 1:
            raise ValueError('SHARED_BRAND_INVALID')
        image(node[0], slot)

    root = tree[0]
    if kind == 'header':
        element(root, 'header', 'es-header', children=4)
        brand(root[0], 'shared:header:brand')
        button = element(root[1], 'button', 'es-menu-button', fixed={
            'type': 'button', 'aria-expanded': 'false', 'aria-controls': 'es-nav'}, children=4)
        for child in button[:3]:
            element(child, 'span', children=0)
        leaf(button[3], 'b')
        if button[3].text != 'Меню':
            raise ValueError('SHARED_MENU_FIXED')
        element(root[2], 'nav', fixed={'id': 'es-nav', 'aria-label': 'Основное меню'}, children=0)
        contacts = element(root[3], 'div', 'es-header-contacts', children=3)
        socials = element(contacts[0], 'div', 'es-header-socials', children=3)
        for index, node in enumerate(socials):
            link(node, schemes=('https',), label=True, relative=False)
            if len(node) != 1:
                raise ValueError('SHARED_SOCIAL_INVALID')
            image(node[0], f'shared:header:social:{index}')
        link(contacts[1], 'es-header-address')
        if len(contacts[1]) != 2:
            raise ValueError('SHARED_ADDRESS_INVALID')
        leaf(contacts[1][0], 'b'); leaf(contacts[1][1], 'span')
        link(contacts[2], 'es-header-phone', schemes=('tel',), relative=False)
        if len(contacts[2]) != 2:
            raise ValueError('SHARED_PHONE_INVALID')
        leaf(contacts[2][0], 'strong'); leaf(contacts[2][1], 'span')
    else:
        element(root, 'footer', 'es-footer', children=2)
        left = element(root[0], 'div', 'es-footer-left', children=2)
        brand(left[0], 'shared:footer:brand'); leaf(left[1], 'p')
        legal = element(root[1], 'div', 'es-footer-legal', children=3)
        leaf(legal[0], 'span'); leaf(legal[1], 'span')
        credit = element(legal[2], 'span', 'es-footer-credit', children=1, text=True)
        leaf(credit[0], 'b')

    canonical = serialize_tree(root)
    if len(canonical.encode('utf-8')) > MAX_HTML:
        raise ValueError('SHARED_HTML_LIMIT')
    return {'html': canonical, 'bindings': bindings, 'schemaVersion': kind + '-v1',
            'payloadHash': hashlib.sha256(canonical.encode()).hexdigest()}


def serialize_tree(node):
    attrs = ''.join(f' {key}="{escape(value, quote=True)}"' for key, value in sorted(node.attrib.items()))
    if node.tag == 'img':
        return '<img' + attrs + '>'
    body = escape(node.text or '')
    for child in node:
        body += serialize_tree(child) + escape(child.tail or '')
    return f'<{node.tag}{attrs}>' + body + f'</{node.tag}>'
