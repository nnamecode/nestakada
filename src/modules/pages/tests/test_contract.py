import uuid

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from modules.pages.models import Page, PageGrant, PageKind, Route, RouteMode, RouteOutcome


class RouteAndGrantContractTests(SimpleTestCase):
    def test_route_target_is_local_and_outcome_matches_page(self) -> None:
        page = Page(id=uuid.uuid4(), name="Service", kind=PageKind.SERVICE_DETAIL, position=0)
        route = Route(
            page=page,
            target="/services/example/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.SERVICE_DETAIL,
        )
        route.clean()

    def test_external_or_mismatched_route_is_rejected(self) -> None:
        page = Page(id=uuid.uuid4(), name="Article", kind=PageKind.ARTICLE, position=0)
        route = Route(
            page=page,
            target="https://example.invalid/",
            mode=RouteMode.PRIMARY,
            outcome=RouteOutcome.SERVICE_DETAIL,
        )
        with self.assertRaises(ValidationError):
            route.clean()

    def test_ambiguous_local_targets_are_rejected(self) -> None:
        page = Page(id=uuid.uuid4(), name="Article", kind=PageKind.ARTICLE, position=0)
        for target in (
            "//host/path",
            "/a/../b",
            "/a/%2e%2e/b",
            "/a\\b",
            "/a/%5c/b",
            "/a#fragment",
            "/a\x00",
            "/a/%00",
            "/a?value=%0a",
            "/a/%",
            "/a/%0",
            "/a/%GG",
        ):
            with self.subTest(target=target):
                route = Route(
                    page=page,
                    target=target,
                    mode=RouteMode.PRIMARY,
                    outcome=RouteOutcome.ARTICLE,
                )
                with self.assertRaises(ValidationError):
                    route.clean()

    def test_grant_groups_are_canonical(self) -> None:
        grant = PageGrant(groups=["prices", "text"])
        with self.assertRaises(ValidationError):
            grant.clean()
