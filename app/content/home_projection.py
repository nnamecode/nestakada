"""Pure bounded home projection from coherent exact source facts; no writes."""
import copy

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models.expressions import RawSQL

from page_editor import home_sources
from page_versions import schema
from page_versions.models import PageContentState, PageRevision

from .models import Page, Route


def _fault(code='HOME_PROJECTION_INVALID'):
    raise ValidationError(code)


def _index(profile, facts):
    bindings = home_sources._bindings(profile)
    if (type(facts) is not dict or set(facts) != {'schema', 'sources'}
            or facts['schema'] != 'home-source-facts-v1'
            or type(facts['sources']) is not list):
        _fault()
    rows = {}
    for row in facts['sources']:
        if type(row) is not dict or set(row) != {
                'page_id', 'present', 'visible', 'primary',
                'current_revision_id', 'payload_hash', 'price_rows'}:
            _fault()
        page_id = row['page_id']
        if page_id in rows or page_id not in bindings:
            _fault()
        rows[page_id] = row
    if set(rows) != set(bindings):
        _fault()
    return rows


def _visibility(item, sources):
    page_id = item.get('source_page_id')
    if page_id is None:
        return item['fallback_visible'], 'unbound'
    source = sources[page_id]
    if not source['present']:
        return item['fallback_visible'], 'missing'
    return source['visible'], 'visible' if source['visible'] else 'hidden'


def project(profile, facts):
    """Return an isolated render DTO; source facts never mutate the revision."""
    sources = _index(profile, facts)
    value = copy.deepcopy(profile)
    services = []
    for item in value['services']:
        visible, state = _visibility(item, sources)
        item['source_state'] = state
        if visible:
            services.append(item)
    value['services'] = services

    groups = []
    for group in value['prices']:
        group_source = (sources[group['source_page_id']]
                        if group['source_page_id'] is not None else None)
        group_visible = not (group_source is not None
                             and group_source['present']
                             and not group_source['visible'])
        projected_rows = []
        for row in group['rows']:
            visible, state = _visibility(row, sources)
            row['source_state'] = state
            if row['source_page_id'] is not None:
                source = sources[row['source_page_id']]
                price = {item['row_id']:item for item in source['price_rows']}.get(
                    row['source_row_id'])
                if source['present'] and source['visible']:
                    if price is None or price['amount'] is None:
                        visible = False
                        row['source_state'] = 'row-missing'
                    else:
                        row['price_text'] = home_sources.format_amount(
                            price['amount'], price['from'])
            if visible and group_visible:
                projected_rows.append(row)
        group['rows'] = projected_rows
        if projected_rows:
            groups.append(group)
    value['prices'] = groups

    works = []
    for item in value['works']:
        visible, state = _visibility(item, sources)
        item['source_state'] = state
        if visible:
            works.append(item)
    value['works'] = works
    return {'schema':'home-projection-v1', 'profile':value,
            'source_digest':schema.digest(facts)}


def _version_rows(model, table, **filters):
    return list(model.objects.filter(**filters).annotate(
        row_version=RawSQL(f'"{table}"."xmin"::text', [])
    ).order_by('pk').values_list('pk', 'row_version'))


def capture_once(profile, *, lock=False):
    if not connection.in_atomic_block:
        _fault('HOME_PROJECTION_TRANSACTION_REQUIRED')
    facts, _digest = home_sources.capture(profile, lock=lock)
    page_ids = [row['page_id'] for row in facts['sources']]
    revision_ids = [row['current_revision_id'] for row in facts['sources']
                    if row['current_revision_id'] is not None]
    versions = {
        'pages': _version_rows(Page, 'content_page', pk__in=page_ids),
        'routes': _version_rows(Route, 'content_route', page_id__in=page_ids,
                                kind=Route.Kind.PRIMARY),
        'states': _version_rows(PageContentState,
                               'page_versions_pagecontentstate',
                               page_id__in=page_ids),
        'revisions': _version_rows(PageRevision,
                                  'page_versions_pagerevision',
                                  pk__in=revision_ids),
    }
    evidence = {'schema':'home-source-capture-v1', 'facts':facts,
                'row_versions':{key:[[str(pk), str(rv)] for pk, rv in rows]
                                for key, rows in versions.items()}}
    return evidence, schema.digest(evidence)


def capture_coherent(profile):
    first, first_digest = capture_once(profile)
    second, second_digest = capture_once(profile)
    if first_digest != second_digest or first != second:
        _fault('HOME_PROJECTION_STALE')
    return first['facts'], first_digest


def _dependency_matches(profile, source):
    page_id = source['page_id']
    for item in [*profile['services'], *profile['works']]:
        if item['source_page_id'] == page_id:
            if item['fallback_visible'] is not source['visible']:
                return False
    for group in profile['prices']:
        if (group['source_page_id'] == page_id and source['present']
                and not source['visible']):
            # A group has no fallback_visible bit: owner must unbind it first.
            return False
        prices = {row['row_id']:row for row in source['price_rows']}
        for item in group['rows']:
            if item['source_page_id'] != page_id:
                continue
            price = prices.get(item['source_row_id'])
            visible = bool(source['visible'] and price is not None
                           and price['amount'] is not None)
            if item['fallback_visible'] is not visible:
                return False
            if visible and item['price_text'] != home_sources.format_amount(
                    price['amount'], price['from']):
                return False
    return True


def delete_dependency_guard(page_id):
    """Lock and verify current home fallbacks before one source Page deletion."""
    if not connection.in_atomic_block:
        _fault('HOME_DELETE_GUARD_TRANSACTION_REQUIRED')
    states = list(PageContentState.objects.select_for_update().filter(
        page__kind=Page.Kind.HOME).select_related('page').order_by('page_id')[:66])
    if len(states) > 64:
        _fault('HOME_DELETE_GUARD_CAP')
    revision_ids = [state.current_revision_id for state in states]
    revisions = {row.pk:row for row in PageRevision.objects.select_for_update().filter(
        pk__in=revision_ids).order_by('pk')}
    evidence = []
    target = str(page_id)
    for state in states:
        revision = revisions.get(state.current_revision_id)
        if revision is None or revision.page_id != state.page_id:
            _fault('HOME_DELETE_GUARD_INVALID')
        payload = schema.validate(revision.payload, state.page.kind)
        if schema.digest(payload) != revision.payload_hash:
            _fault('HOME_DELETE_GUARD_INVALID')
        profile = payload.get('home_profile')
        if profile is None or target not in home_sources._bindings(profile):
            continue
        facts, digest = home_sources.capture(profile, lock=True)
        source = next((row for row in facts['sources']
                       if row['page_id'] == target), None)
        if source is None or not source['present']:
            _fault('HOME_DELETE_GUARD_INVALID')
        if not _dependency_matches(profile, source):
            _fault('HOME_DELETE_DEPENDENCY_REQUIRES_SYNC')
        evidence.append({'home_page_id':str(state.page_id),
                         'revision_id':str(revision.pk),
                         'payload_hash':revision.payload_hash,
                         'source_digest':digest})
    value = {'schema':'home-delete-dependencies-v1', 'target':target,
             'homes':evidence}
    return value, schema.digest(value)
