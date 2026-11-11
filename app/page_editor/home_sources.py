"""Bounded server facts for selected home sources; no writes or fallback mutation."""
from django.core.exceptions import ValidationError
import copy
from decimal import Decimal, InvalidOperation

from django.db import connection
from django.db.models.expressions import RawSQL
from content.models import Page, Route
from page_versions import schema as S
from page_versions.models import PageContentState, PageRevision


MAX_SOURCES = 64


def _invalid(code='EDITOR_HOME_SOURCES_INVALID'):
    raise ValidationError(code)


def _bindings(profile):
    sources = {}

    def add(page_id, row_id=None):
        if page_id is None:
            return
        rows = sources.setdefault(page_id, set())
        if row_id is not None:
            rows.add(row_id)

    for item in profile['services']:
        add(item['source_page_id'])
    for group in profile['prices']:
        add(group['source_page_id'])
        for row in group['rows']:
            add(row['source_page_id'], row['source_row_id'])
    for item in profile['works']:
        add(item['source_page_id'])
    if len(sources) > MAX_SOURCES:
        _invalid('EDITOR_HOME_SOURCES_CAP')
    return {page_id: sorted(row_ids) for page_id, row_ids in sorted(sources.items())}


def _query(model, lock, table):
    rows = model.objects
    if lock:
        rows = rows.select_for_update()
    return rows.annotate(row_version=RawSQL(f'"{table}"."xmin"::text', []))


def format_amount(amount, is_from):
    try:
        value = Decimal(amount)
    except (InvalidOperation, TypeError, ValueError):
        _invalid()
    if not value.is_finite() or value < 0 or type(is_from) is not bool:
        _invalid()
    text = format(value.normalize(), 'f')
    whole, dot, fraction = text.partition('.')
    grouped = ' '.join([
        whole[max(0, len(whole) - offset - 3):len(whole) - offset]
        for offset in range(0, len(whole), 3)
    ][::-1])
    return ('от ' if is_from else '') + grouped + (dot + fraction if fraction else '') + ' ₽'


def _price_facts(payload, row_ids):
    wanted = set(row_ids)
    result = {row_id: {'row_id': row_id, 'amount': None, 'from': None} for row_id in row_ids}
    price = payload.get('price')
    if price is None:
        return [result[row_id] for row_id in row_ids]
    for row in price['rows']:
        if row['id'] not in wanted:
            continue
        amounts = [cell for cell in row['cells'] if cell['kind'] == 'amount']
        if len(amounts) != 1:
            _invalid()
        result[row['id']] = {'row_id': row['id'], 'amount': amounts[0]['amount'],
                             'from': amounts[0]['from']}
    return [result[row_id] for row_id in row_ids]


def capture(profile, *, lock=True):
    """Return deterministic facts and digest while the caller retains content lock."""
    if not connection.in_atomic_block:
        _invalid('EDITOR_HOME_SOURCES_LOCK_REQUIRED')
    bindings = _bindings(profile)
    ids = list(bindings)
    pages = {str(row.pk): row for row in _query(Page, lock, 'content_page').filter(pk__in=ids).order_by('pk')}
    routes = {str(row.page_id): row for row in _query(Route, lock, 'content_route').filter(
        page_id__in=ids, kind=Route.Kind.PRIMARY).order_by('page_id', 'pk')}
    states = {str(row.page_id): row for row in _query(
        PageContentState, lock, 'page_versions_pagecontentstate').filter(
        page_id__in=ids).order_by('page_id', 'pk')}
    revision_ids = [row.current_revision_id for row in states.values()]
    revisions = {str(row.pk): row for row in _query(
        PageRevision, lock, 'page_versions_pagerevision').filter(
        pk__in=revision_ids).order_by('pk')}

    facts = []
    for page_id, row_ids in bindings.items():
        page = pages.get(page_id)
        route = routes.get(page_id)
        state = states.get(page_id)
        revision = revisions.get(str(state.current_revision_id)) if state is not None else None
        if page is not None and (route is None or state is None or revision is None):
            _invalid()
        if state is not None and (revision is None or str(revision.page_id) != page_id):
            _invalid()
        payload_hash = None
        price_rows = [{'row_id': row_id, 'amount': None, 'from': None} for row_id in row_ids]
        if revision is not None:
            payload = S.validate(revision.payload, page.kind if page is not None else None)
            payload_hash = S.digest(payload)
            if payload_hash != revision.payload_hash:
                _invalid()
            price_rows = _price_facts(payload, row_ids)
        primary = route.target if route is not None else None
        visible = bool(page is not None and page.is_published and primary is not None
                       and state is not None and revision is not None)
        facts.append({'page_id': page_id, 'present': page is not None, 'visible': visible,
                      'primary': primary, 'current_revision_id': str(revision.pk) if revision else None,
                      'payload_hash': payload_hash, 'price_rows': price_rows})
    value = {'schema': 'home-source-facts-v1', 'sources': facts}
    evidence = {
        'schema': 'home-source-capture-v1',
        'facts': value,
        'row_versions': {
            'pages': [[str(row.pk), str(row.row_version)]
                      for row in sorted(pages.values(), key=lambda item: item.pk)],
            'routes': [[str(row.pk), str(row.row_version)]
                       for row in sorted(routes.values(), key=lambda item: item.pk)],
            'states': [[str(row.pk), str(row.row_version)]
                       for row in sorted(states.values(), key=lambda item: item.pk)],
            'revisions': [[str(row.pk), str(row.row_version)]
                          for row in sorted(revisions.values(), key=lambda item: item.pk)],
        },
    }
    return value, S.digest(evidence)


def synchronize(base, candidate, facts):
    """Derive bound fallback facts; static owner fields remain untouched."""
    if (type(facts) is not dict or set(facts) != {'schema', 'sources'}
            or facts['schema'] != 'home-source-facts-v1'):
        _invalid()
    sources = {row.get('page_id'): row for row in facts['sources']
               if type(row) is dict}
    if len(sources) != len(facts['sources']):
        _invalid()
    result = copy.deepcopy(candidate)

    def source_for(current, previous):
        source_id = current['source_page_id']
        if source_id is None:
            return None
        source = sources.get(source_id)
        if source is None:
            _invalid()
        if not source['present'] and previous['source_page_id'] != source_id:
            _invalid('EDITOR_HOME_SOURCE_UNAVAILABLE')
        return source

    for index, item in enumerate(result['services']):
        source = source_for(item, base['services'][index])
        if source is not None and source['present']:
            item['fallback_visible'] = source['visible']
    for group_index, group in enumerate(result['prices']):
        source_for(group, base['prices'][group_index])
        for row_index, row in enumerate(group['rows']):
            source = source_for(row, base['prices'][group_index]['rows'][row_index])
            if source is None or not source['present']:
                continue
            price = next((item for item in source['price_rows']
                          if item['row_id'] == row['source_row_id']), None)
            available = price is not None and price['amount'] is not None
            row['fallback_visible'] = bool(source['visible'] and available)
            if available:
                row['price_text'] = format_amount(price['amount'], price['from'])
    for index, item in enumerate(result['works']):
        source = source_for(item, base['works'][index])
        if source is not None and source['present']:
            item['fallback_visible'] = source['visible']
    return result
