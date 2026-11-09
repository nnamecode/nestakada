"""Strict canonical AST reader; hydration never evaluates stored HTML."""
from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET
from .policy import MAX_HTML, safe_url, validate_tree, serialize_tree


def local_url(value):
    if (type(value) is not str or len(value) > 2048 or not value.startswith('/')
            or value.startswith('//') or '#' in value or any(c in value for c in '<>"\'')
            or any(part in value.lower() for part in ('/manage/', '/private/'))):
        raise ValueError('SHARED_PUBLIC_URL_INVALID')
    decoded = value
    for _ in range(3):
        decoded = unquote(decoded)
    path = decoded.split('?', 1)[0].lower()
    if (not path.startswith('/') or path.startswith('//') or any(c in decoded for c in '<>"\'')
            or path == '/manage' or path.startswith('/manage/')
            or path == '/private' or '/private/' in path):
        raise ValueError('SHARED_PUBLIC_URL_INVALID')
    return safe_url(value, (), allow_relative=True)


class ClosedParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tree = ET.Element('div')
        self.stack = [self.tree]
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if len(dict(attrs)) != len(attrs) or any(value is None for _, value in attrs):
            raise ValueError('SHARED_PUBLIC_DUPLICATE_ATTRIBUTE')
        if not re.fullmatch(r'[a-z][a-z0-9-]*', tag):
            raise ValueError('SHARED_PUBLIC_TOKEN_INVALID')
        self.count += 1
        if self.count > 20000 or len(self.stack) > 32:
            raise ValueError('SHARED_DOM_LIMIT')
        child = ET.SubElement(self.stack[-1], tag, dict(attrs))
        if tag != 'img':
            self.stack.append(child)

    def handle_endtag(self, tag):
        if len(self.stack) < 2 or self.stack[-1].tag != tag or tag == 'img':
            raise ValueError('SHARED_PUBLIC_TOKEN_INVALID')
        self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        raise ValueError('SHARED_PUBLIC_TOKEN_INVALID')

    def handle_data(self, data):
        parent = self.stack[-1]
        if len(parent):
            child = parent[-1]
            child.tail = (child.tail or '') + data
        else:
            parent.text = (parent.text or '') + data

    def handle_comment(self, data): raise ValueError('SHARED_PUBLIC_TOKEN_INVALID')
    def handle_decl(self, decl): raise ValueError('SHARED_PUBLIC_TOKEN_INVALID')
    def handle_pi(self, data): raise ValueError('SHARED_PUBLIC_TOKEN_INVALID')
    def unknown_decl(self, data): raise ValueError('SHARED_PUBLIC_TOKEN_INVALID')


def parse_component(source, kind):
    if (type(source) is not str or len(source.encode('utf-8')) > MAX_HTML
            or any(token in source for token in ('{{', '{%', '{#'))
            or any(ord(c) < 32 and c not in '\t\n' for c in source)):
        raise ValueError('SHARED_HTML_LIMIT')
    parser = ClosedParser()
    parser.feed(source)
    parser.close()
    if len(parser.stack) != 1 or parser.rawdata:
        raise ValueError('SHARED_PUBLIC_INCOMPLETE')
    result = validate_tree(parser.tree, kind)
    if result['html'] != source:
        raise ValueError('SHARED_PUBLIC_NONCANONICAL')
    return parser.tree[0], result


def navigation_html(navigation):
    from .public import NavItem
    if type(navigation) is not tuple or len(navigation) > 20000:
        raise ValueError('SHARED_PUBLIC_NAV_INVALID')
    output, size = [], 0
    for item in navigation:
        if (type(item) is not NavItem or type(item.label) is not str or not item.label
                or any(ord(c) < 32 or ord(c) == 127 for c in item.label)):
            raise ValueError('SHARED_PUBLIC_NAV_INVALID')
        safe_url(item.url, ('http', 'https'))
        current = ' aria-current="page"' if item.current else ''
        node = '<a href="' + escape(item.url, quote=True) + '"' + current + '>' + escape(item.label) + '</a>'
        size += len(node.encode('utf-8'))
        if size > MAX_HTML:
            raise ValueError('SHARED_PUBLIC_NAV_LIMIT')
        output.append(node)
    return ''.join(output)


def hydrate(source, kind, navigation, media_urls):
    root, checked = parse_component(source, kind)
    expected = {binding['assetId'] for binding in checked['bindings']}
    if type(media_urls) is not dict or set(media_urls) != expected:
        raise ValueError('SHARED_PUBLIC_ASSET_BINDINGS')
    nav = navigation_html(navigation)
    hydration_allowance = 0
    for node in root.iter('img'):
        identity = node.attrib.pop('data-es-shared-asset')
        url = local_url(media_urls[identity])
        # Count each emitted node, including repeated use of the same Asset.
        # Escaping expands ampersands and Unicode consumes UTF-8 bytes; a raw
        # character count or unique URL count cannot bound the emitted markup.
        old_attribute = ' data-es-shared-asset="' + escape(identity, quote=True) + '"'
        new_attribute = ' src="' + escape(url, quote=True) + '"'
        hydration_allowance += max(0, len(new_attribute.encode('utf-8')) - len(old_attribute.encode('utf-8')))
        node.set('src', url)
    if kind == 'header':
        # The shared grammar already proved this exact fixed node, zero
        # children, and whitespace-only text. Preserve its attributes and
        # replace only that empty content, including legitimate pretty spacing.
        nav_node = root[2]
        nav_node.text = None
        for item in navigation:
            attributes = {'href': item.url}
            if item.current:
                attributes['aria-current'] = 'page'
            child = ET.SubElement(nav_node, 'a', attributes)
            child.text = item.label
    rendered = serialize_tree(root)
    # Each source keeps its own full legal budget; hydration has an explicitly
    # derived allowance for navigation plus actual escaped image replacements.
    if len(rendered.encode('utf-8')) > MAX_HTML + len(nav.encode('utf-8')) + hydration_allowance:
        raise ValueError('SHARED_PUBLIC_OUTPUT_LIMIT')
    return rendered
