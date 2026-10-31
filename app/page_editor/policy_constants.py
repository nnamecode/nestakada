"""D-301 carrier constants; not configurable by the HTTP caller."""
POLICY_VERSION = 'es-format-v1'
MAX_SOURCE_BYTES = 1024 * 1024
MAX_TEXT_CODEPOINTS = 200000
MAX_NODES = 20000
MAX_DEPTH = 32
MAX_UI_TABLE_SLOTS = 20000  # Aggregate visual capability, never a content cap.
FIELDS = frozenset({'intro_text', 'main_text'})
FONTS = frozenset({'inter', 'oswald', 'arial', 'georgia', 'times-new-roman', 'courier-new'})
FONT_FAMILIES = {
    'inter': ('inter', 'arial', 'sans-serif'),
    'oswald': ('oswald', 'arial', 'sans-serif'),
    'arial': ('arial', 'sans-serif'),
    'georgia': ('georgia', 'serif'),
    'times-new-roman': ('times new roman', 'serif'),
    'courier-new': ('courier new', 'monospace'),
}
ALIGNMENTS = frozenset({'left', 'center', 'right', 'justify'})
TAGS = frozenset({'p', 'br', 'h1', 'h2', 'h3', 'blockquote', 'ul', 'ol', 'li',
                  'strong', 'em', 'u', 's', 'sub', 'sup', 'span', 'a',
                  'table', 'caption', 'thead', 'tbody', 'tr', 'th', 'td'})
ALIASES = {'b': 'strong', 'i': 'em'}
TABLE_TAGS = frozenset({'table', 'caption', 'thead', 'tbody', 'tr', 'th', 'td'})
BLOCK_FORMAT_TAGS = frozenset({'p', 'h1', 'h2', 'h3', 'blockquote'})
MARGIN_TAGS = BLOCK_FORMAT_TAGS | {'ul', 'ol', 'table'}
FORMAT_ATTRS = frozenset({'data-es-font', 'data-es-size', 'data-es-fg', 'data-es-bg'})
MARGIN_ATTRS = frozenset({'data-es-mt', 'data-es-mr', 'data-es-mb', 'data-es-ml'})
PROTECTED_ATTRS = frozenset({'data-es-protected', 'data-es-image', 'data-es-asset',
                           'data-es-alt', 'data-es-image-align', 'data-es-width',
                           'data-es-height', 'data-es-parent', 'data-es-slot'})


def attributes_for(tag):
    attributes = set()
    if tag == 'span':
        attributes.update(FORMAT_ATTRS | PROTECTED_ATTRS | {'data-es-anchor'})
    if tag in BLOCK_FORMAT_TAGS:
        attributes.update({'data-es-align', 'data-es-anchor', 'data-es-parent'})
    if tag in MARGIN_TAGS:
        attributes.update(MARGIN_ATTRS)
    if tag == 'a':
        attributes.update({'href', 'title', 'target', 'rel', 'data-es-target-field', 'data-es-target-anchor'})
    if tag == 'table':
        attributes.add('data-es-cellpad')
    if tag in {'th', 'td'}:
        attributes.update({'rowspan', 'colspan', 'data-es-align'})
    if tag == 'th':
        attributes.add('scope')
    return frozenset(attributes)
