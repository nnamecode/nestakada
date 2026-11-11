"""Owner-only bounded source search for the fixed home-profile editor."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from content.models import Page, Route
from page_versions import engine as E, schema as S
from page_versions.models import PageContentState, PageRevision


LIMIT = 20


def query_text(value):
    if (type(value) is not str or not value or len(value) > 100 or value != value.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError('EDITOR_SOURCE_QUERY_INVALID')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise ValueError('EDITOR_SOURCE_QUERY_INVALID') from None
    return value


def search(*, actor, page_id, generation, query):
    E.outside()
    query = query_text(query)
    with transaction.atomic():
        home, _profile, _fields, owner, state = E.enter(
            actor, page_id, generation, owner=True)
        if not owner or home.kind != Page.Kind.HOME:
            raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
        current = E.revision(home, state.current_revision_id)
        payload = S.validate(current.payload, home.kind)
        if 'home_profile' not in payload:
            raise ValidationError('EDITOR_HOME_PROFILE_UNAVAILABLE')

        routes = list(Route.objects.select_for_update().select_related('page').filter(
            kind=Route.Kind.PRIMARY, page__content_state__isnull=False).exclude(
            page_id=home.pk).filter(Q(target__icontains=query) | Q(page__name__icontains=query)).order_by(
            'target', 'page_id')[:LIMIT + 1])
        page_ids = [route.page_id for route in routes]
        states = {row.page_id: row for row in PageContentState.objects.select_for_update().filter(
            page_id__in=page_ids).order_by('page_id')}
        revision_ids = [row.current_revision_id for row in states.values()]
        revisions = {row.pk: row for row in PageRevision.objects.select_for_update().filter(
            pk__in=revision_ids).order_by('pk')}

        results = []
        for route in routes:
            source_state = states.get(route.page_id)
            source = revisions.get(source_state.current_revision_id) if source_state else None
            if source is None or source.page_id != route.page_id:
                raise ValidationError('EDITOR_SOURCE_UNAVAILABLE')
            verified = S.validate(source.payload, route.page.kind)
            if S.digest(verified) != source.payload_hash:
                raise ValidationError('EDITOR_SOURCE_UNAVAILABLE')
            results.append({'pageId': str(route.page_id), 'path': route.target,
                            'name': route.page.name, 'kind': route.page.kind,
                            'published': route.page.is_published,
                            'currentRevisionId': str(source.pk)})
        return {'protocol': 'home-source-candidates-v1',
                'results': results[:LIMIT], 'hasNext': len(results) > LIMIT}
