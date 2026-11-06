"""Owner-only read projection; no tree mutation or TRUST admission."""
from uuid import UUID
from django.core.exceptions import ValidationError
from django.db.models import Count, OuterRef, Subquery
from .models import Page, Route


def parent_key(query):
    if set(query) - {'parent'} or any(len(query.getlist(key)) != 1 for key in query):
        raise ValueError('TREE_INVALID_QUERY')
    if 'parent' not in query:
        return None
    value = query['parent']
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError('TREE_INVALID_PARENT')
    return parsed


def branch(parent_id):
    parents = {row['id']: row for row in Page.objects.values('id', 'name', 'parent_id')}
    if parent_id is not None and parent_id not in parents:
        raise Page.DoesNotExist()
    ancestry, seen, current = [], set(), parent_id
    while current is not None:
        if current in seen or current not in parents:
            raise ValidationError('TREE_PARENT_CHAIN_UNAVAILABLE')
        seen.add(current)
        row = parents[current]
        ancestry.append(row)
        current = row['parent_id']
    primary_rows = Route.objects.filter(
        page_id=OuterRef('pk'), kind=Route.Kind.PRIMARY)
    primary = primary_rows.values('target')[:1]
    primary_legacy = primary_rows.values('is_legacy')[:1]
    pages = list(Page.objects.filter(parent_id=parent_id).annotate(
        child_count=Count('children'), primary_target=Subquery(primary),
        primary_is_legacy=Subquery(primary_legacy)).order_by('name', 'id'))
    return {'pages': pages, 'ancestry': list(reversed(ancestry)), 'parent_id': parent_id}
