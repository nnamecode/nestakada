"""Instance-local text batching for the fixed html5lib 1.1 fragment parser.

This is not input admission. The producer still scans and validates the entire
source before parsing. Non-body/table/foreign contexts retain stock tokens.
"""
import html5lib
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from html5lib.constants import namespaces, tokenTypes
from .policy_constants import MAX_SOURCE_BYTES, MAX_NODES, MAX_DEPTH

TEXT_BATCH_CHARS = 8192  # Work granularity, never a content/refusal limit.
_TEXT = frozenset((tokenTypes['Characters'], tokenTypes['SpaceCharacters']))
_STOCK_CONTEXTS = frozenset((
    'table', 'caption', 'colgroup', 'col', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th',
    'pre', 'listing', 'textarea', 'select', 'option', 'optgroup', 'script', 'style',
    'xmp', 'iframe', 'noembed', 'noframes', 'plaintext', 'noscript'))


class _ParseMemo:
    def __init__(self):
        self.source = None
        self.tree = None

    def clear(self):
        self.source = None
        self.tree = None


_ACTIVE_SESSION = ContextVar('page_editor_parse_session', default=None)


@contextmanager
def _parse_session():
    """One entry for one normalize invocation; never retain request data after it."""
    if _ACTIVE_SESSION.get() is not None:
        raise RuntimeError('HTML_PARSER_SESSION_NESTED')
    memo = _ParseMemo()
    token = _ACTIVE_SESSION.set(memo)
    try:
        yield
    finally:
        memo.clear()
        _ACTIVE_SESSION.reset(token)


def _memo_admissible(value, tree):
    # These are cache eligibility bounds, not additional parse refusals.
    if len(value) > MAX_SOURCE_BYTES:
        return False
    try:
        if len(value.encode('utf-8')) > MAX_SOURCE_BYTES:
            return False
    except UnicodeError:
        return False
    count = 0
    stack = [(iter(tree), 1)]
    while stack:
        children, depth = stack[-1]
        node = next(children, None)
        if node is None:
            stack.pop()
            continue
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            return False
        if len(node):
            stack.append((iter(node), depth + 1))
    return True


class _PositionStream:
    """Parser-visible logical position; the tokenizer keeps its real stream."""
    def __init__(self, stream):
        object.__setattr__(self, '_stream', stream)
        object.__setattr__(self, '_position', None)

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __setattr__(self, name, value):
        if name == '_position':
            object.__setattr__(self, name, value)
        else:
            setattr(self._stream, name, value)

    def position(self):
        return self._stream.position() if self._position is None else self._position


class _TextBatchTokenizer:
    def __init__(self, tokenizer, parser):
        object.__setattr__(self, '_tokenizer', tokenizer)
        object.__setattr__(self, '_parser', parser)
        object.__setattr__(self, '_stream', _PositionStream(tokenizer.stream))

    @property
    def stream(self):
        return self._stream

    def __getattr__(self, name):
        return getattr(self._tokenizer, name)

    def __setattr__(self, name, value):
        # In particular, state writes must reach the real tokenizer: its bound
        # state functions continue to execute against that original instance.
        setattr(self._tokenizer, name, value)

    def _eligible(self):
        parser = self._parser
        if parser.phase is not parser.phases['inBody']:
            return False
        if self._tokenizer.state != self._tokenizer.dataState:
            return False
        return bool(parser.tree.openElements) and all(
            node.namespace == namespaces['html'] and node.name not in _STOCK_CONTEXTS
            for node in parser.tree.openElements)

    def __iter__(self):
        chunks, size, kind, last_position = [], 0, None, None
        for token in self._tokenizer:
            position = self._tokenizer.stream.position()
            data = token.get('data')
            text = token['type'] in _TEXT and type(data) is str and bool(data) and '\x00' not in data
            if chunks and (not text or token['type'] != kind or size + len(data) > TEXT_BATCH_CHARS):
                self._stream._position = last_position
                yield {'type': kind, 'data': ''.join(chunks)}
                chunks, size, kind = [], 0, None
                # The current token is the single retained barrier/lookahead.
                # Do not request anything after it until it has been yielded.
            if text and (chunks or self._eligible()):
                if len(data) > TEXT_BATCH_CHARS:
                    # A stock large token is already one efficient insertion.
                    self._stream._position = position
                    yield token
                    continue
                chunks.append(data)
                size += len(data)
                kind, last_position = token['type'], position
                if size == TEXT_BATCH_CHARS:
                    self._stream._position = last_position
                    yield {'type': kind, 'data': ''.join(chunks)}
                    chunks, size, kind = [], 0, None
            else:
                self._stream._position = position
                yield token
        if chunks:
            self._stream._position = last_position
            yield {'type': kind, 'data': ''.join(chunks)}
        # EOF processing observes the real final stream position.
        self._stream._position = None


class _CoalescingParser(html5lib.HTMLParser):
    def __init__(self):
        super().__init__(tree=html5lib.getTreeBuilder('etree'), namespaceHTMLElements=True)

    def parseFragment(self, value):
        if type(value) is not str:
            raise TypeError('HTML_PARSER_INPUT_TYPE')
        return super().parseFragment(value, container='div', scripting=False)

    def mainLoop(self):
        original = self.tokenizer
        self.tokenizer = _TextBatchTokenizer(original, self)
        try:
            return super().mainLoop()
        finally:
            self.tokenizer = original


def parse_fragment(value: str):
    """Fixed etree/HTML-namespace/div/no-scripting parse, no caller options."""
    memo = _ACTIVE_SESSION.get()
    if memo is None:
        return _CoalescingParser().parseFragment(value)
    if type(value) is not str:
        memo.clear()
        raise TypeError('HTML_PARSER_INPUT_TYPE')
    if memo.tree is not None and memo.source == value:
        return deepcopy(memo.tree)
    # Release the former entry before allocating a different parse/tree.
    memo.clear()
    parser = _CoalescingParser()
    tree = parser.parseFragment(value)
    if parser.errors or not _memo_admissible(value, tree):
        return tree
    memo.source, memo.tree = value, tree
    # The stored raw tree is never returned, including on the first miss.
    return deepcopy(tree)
