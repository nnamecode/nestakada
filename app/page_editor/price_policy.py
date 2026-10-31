"""Pure typed price normalization. No persistence, authorization or float money."""
from decimal import Decimal, InvalidOperation, localcontext
from uuid import UUID

MAX_ROWS = 500
MAX_COLUMNS = 32
MAX_CELLS = 10000
MAX_AMOUNT = Decimal('999999999.99')


class PricePolicyError(ValueError):
    def __init__(self):
        super().__init__('PRICE_INVALID')


def _fail():
    raise PricePolicyError()


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        _fail()


def _identifier(value):
    if type(value) is not str:
        _fail()
    try:
        if str(UUID(value)) != value:
            _fail()
    except (ValueError, AttributeError):
        _fail()
    return value


def _text(value, limit, multiline=False):
    if type(value) is not str:
        _fail()
    try:
        value.encode('utf-8')
    except UnicodeError:
        _fail()
    if any(ord(char) < 32 and (not multiline or char not in '\t\n\r') for char in value):
        _fail()
    normalized = value.replace('\r\n', '\n').replace('\r', '\n') if multiline else value
    if len(normalized) > limit:
        _fail()
    return normalized


def normalize_amount(value):
    """Exact Decimal input, including exponent syntax; never round a fraction."""
    if type(value) is not str:
        _fail()
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT:
            _fail()
        if amount.is_zero():
            return '0'
        parts = amount.as_tuple()
        # Remove coefficient trailing zeros without building a giant fixed-point
        # string for tiny/large exponents. The accepted value has exact pennies.
        end = len(parts.digits)
        while end and parts.digits[end - 1] == 0:
            end -= 1
        exponent = parts.exponent + len(parts.digits) - end
        if exponent < -2:
            _fail()
        with localcontext() as context:
            context.prec = 16
            canonical = format(amount.quantize(Decimal('0.01')), 'f')
        return canonical.rstrip('0').rstrip('.')
    except (InvalidOperation, ValueError, OverflowError):
        _fail()


def normalize_price(value):
    """Return a new canonical PriceV1, preserving IDs, order and text semantics."""
    if value is None:
        return None
    _keys(value, {'columns', 'rows'})
    if (type(value['columns']) is not list or type(value['rows']) is not list
            or len(value['columns']) > MAX_COLUMNS or len(value['rows']) > MAX_ROWS):
        _fail()
    columns = []
    column_ids = set()
    for source in value['columns']:
        _keys(source, {'id', 'label'})
        identity = _identifier(source['id'])
        if identity in column_ids:
            _fail()
        column_ids.add(identity)
        columns.append({'id': identity, 'label': _text(source['label'], 500)})
    rows = []
    row_ids = set()
    count = 0
    for source in value['rows']:
        _keys(source, {'id', 'label', 'cells'})
        identity = _identifier(source['id'])
        if identity in row_ids or type(source['cells']) is not list:
            _fail()
        row_ids.add(identity)
        label = _text(source['label'], 500)
        cells = []
        seen = set()
        for cell in source['cells']:
            if type(cell) is not dict:
                _fail()
            kind = cell.get('kind')
            if kind == 'text':
                _keys(cell, {'column_id', 'kind', 'text'})
                result = {'column_id': _identifier(cell['column_id']), 'kind': kind,
                          'text': _text(cell['text'], 1000, multiline=True)}
            elif kind == 'amount':
                _keys(cell, {'column_id', 'kind', 'amount', 'from'})
                if type(cell['from']) is not bool:
                    _fail()
                result = {'column_id': _identifier(cell['column_id']), 'kind': kind,
                          'amount': normalize_amount(cell['amount']), 'from': cell['from']}
            else:
                _fail()
            column = result['column_id']
            if column not in column_ids or column in seen:
                _fail()
            seen.add(column)
            count += 1
            if count > MAX_CELLS:
                _fail()
            cells.append(result)
        rows.append({'id': identity, 'label': label, 'cells': cells})
    return {'columns': columns, 'rows': rows}
