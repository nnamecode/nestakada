"""Read projections only: no HTTP renderer, permission bypass or mutation command."""
from dataclasses import dataclass
from django.core.exceptions import ValidationError
from .models import Page, Route
from .validators import exact_target


@dataclass(frozen=True)
class RouteMatch:
    state: str
    page_id: object = None
    destination: str | None = None


def resolve_target(target):
    exact_target(target)
    route = Route.objects.select_related('page').filter(target=target).first()
    if route is None:
        return RouteMatch('unknown')
    if route.kind == Route.Kind.SYSTEM:
        return RouteMatch('system')
    if route.kind == Route.Kind.REDIRECT:
        primary = Route.objects.filter(page_id=route.page_id, kind=Route.Kind.PRIMARY).first()
        if primary is None:
            raise ValidationError('ROUTE_PRIMARY_MISSING')
        return RouteMatch('redirect', route.page_id, primary.target)
    return RouteMatch('published' if route.page.is_published else 'hidden', route.page_id)


def public_tree():
    """Project published nodes under the nearest published ancestor; no links/HTML."""
    children = {}
    pages = list(Page.objects.all())
    for page in pages:
        children.setdefault(page.parent_id, []).append(page)
    stack = [(node, None) for node in reversed(children.get(None, []))]
    result, seen = [], set()
    while stack:
        node, visible_parent = stack.pop()
        if node.pk in seen:
            raise ValidationError('PAGE_TREE_CYCLE')
        seen.add(node.pk)
        if node.is_published:
            result.append({'id': node.pk, 'parent_id': visible_parent, 'name': node.name})
            visible_parent = node.pk
        stack.extend((child, visible_parent) for child in reversed(children.get(node.pk, [])))
    if len(seen) != len(pages):
        raise ValidationError('PAGE_TREE_DISCONNECTED')
    return result
