"""Bounded, role-aware read projection for the workshop page screens."""
from dataclasses import dataclass
import re
import unicodedata
from urllib.parse import urlencode

from django.db.models import Prefetch, Q

from content.models import Page, Route
from . import services


MAX_PAGES = 512
PAGE_SIZE = 12
_CATEGORY = re.compile(r"(?:root|other|parent:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\Z")
_PAGE_NUMBER = re.compile(r"(?:[1-9][0-9]{0,3})\Z")


class ProjectionInput(ValueError):
    pass


class ProjectionOverflow(RuntimeError):
    pass


@dataclass(frozen=True)
class Category:
    token: str
    label: str


@dataclass(frozen=True)
class PageRow:
    page: Page
    primary_target: str
    category_token: str
    category_label: str


@dataclass(frozen=True)
class PageProjection:
    rows: tuple[PageRow, ...]
    categories: tuple[Category, ...]
    owner: bool

    def selected(self, page_id):
        key = str(page_id)
        return next((row for row in self.rows if str(row.page.pk) == key), None)


def _base_rows(user):
    owner = services.is_owner(user)
    primary = Route.objects.filter(kind=Route.Kind.PRIMARY).order_by("id")
    pages = Page.objects.select_related("parent").prefetch_related(
        Prefetch("routes", queryset=primary, to_attr="workshop_primary_routes"))
    if not owner:
        pages = pages.filter(employee_grants__user=user).distinct()
    pages = list(pages.order_by("parent__name", "name", "id")[:MAX_PAGES + 1])
    if len(pages) > MAX_PAGES:
        raise ProjectionOverflow("WORKSHOP_PAGE_LIMIT")
    return owner, pages


def workshop_pages(user):
    owner, pages = _base_rows(user)
    permitted = {page.pk for page in pages}
    identities = {}
    for page in pages:
        if page.parent_id is None:
            token, label = "root", "Основные страницы"
        elif owner or page.parent_id in permitted:
            token, label = f"parent:{page.parent_id}", page.parent.name
        else:
            token, label = "other", "Другой раздел"
        identities[token] = label

    labels = dict(identities)
    groups = {}
    for token, label in identities.items():
        if token.startswith("parent:"):
            groups.setdefault(label, []).append(token)
    for label, tokens in groups.items():
        tokens.sort()
        if len(tokens) > 1 or label == "Основные страницы":
            for number, token in enumerate(tokens, 1):
                labels[token] = f"{label} (раздел {number})"

    rows = []
    for page in pages:
        if page.parent_id is None:
            token = "root"
        elif owner or page.parent_id in permitted:
            token = f"parent:{page.parent_id}"
        else:
            token = "other"
        routes = page.workshop_primary_routes
        rows.append(PageRow(page=page, primary_target=routes[0].target if routes else "",
                            category_token=token, category_label=labels[token]))
    rows.sort(key=lambda row: (row.category_label.casefold(), row.page.name.casefold(), str(row.page.pk)))
    categories = tuple(Category(token, labels[token]) for token in sorted(
        labels, key=lambda token: (labels[token].casefold(), token)))
    return PageProjection(tuple(rows), categories, owner)


def _single(query, key, default=""):
    values = query.getlist(key)
    if not values:
        return default
    if len(values) != 1 or not isinstance(values[0], str):
        raise ProjectionInput("WORKSHOP_QUERY_INVALID")
    return values[0]


def dashboard_page(projection, query):
    if any(key not in {"q", "category", "p"} for key in query):
        raise ProjectionInput("WORKSHOP_QUERY_INVALID")
    search = _single(query, "q").strip()
    if len(search) > 200 or any(unicodedata.category(char) == "Cc" for char in search):
        raise ProjectionInput("WORKSHOP_QUERY_INVALID")
    category = _single(query, "category")
    if category:
        if len(category) > 43 or not category.isascii() or not _CATEGORY.fullmatch(category):
            raise ProjectionInput("WORKSHOP_QUERY_INVALID")
        if category not in {item.token for item in projection.categories}:
            raise ProjectionInput("WORKSHOP_QUERY_INVALID")
    raw_page = _single(query, "p", "1")
    if not _PAGE_NUMBER.fullmatch(raw_page):
        raise ProjectionInput("WORKSHOP_QUERY_INVALID")
    number = int(raw_page)

    rows = list(projection.rows)
    if search:
        candidate_ids = [row.page.pk for row in rows]
        matched = set(Page.objects.filter(pk__in=candidate_ids).filter(
            Q(name__icontains=search) |
            Q(routes__kind=Route.Kind.PRIMARY, routes__target__icontains=search)
        ).values_list("pk", flat=True).distinct())
        rows = [row for row in rows if row.page.pk in matched]
    if category:
        rows = [row for row in rows if row.category_token == category]
    total = len(rows)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if number > pages:
        raise ProjectionInput("WORKSHOP_QUERY_INVALID")
    start = (number - 1) * PAGE_SIZE
    visible = tuple(rows[start:start + PAGE_SIZE])

    canonical = {}
    if search:
        canonical["q"] = search
    if category:
        canonical["category"] = category
    def link(target):
        return "?" + urlencode({**canonical, "p": target})
    return {
        "rows": visible, "found": total, "total": len(projection.rows),
        "number": number, "pages": pages, "search": search, "category": category,
        "previous_query": link(number - 1) if number > 1 else "",
        "next_query": link(number + 1) if number < pages else "",
    }
