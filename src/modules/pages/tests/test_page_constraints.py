from django.db import IntegrityError, transaction
from django.test import TestCase

from modules.pages.models import Page, PageKind


class PageConstraintTests(TestCase):
    def test_page_cannot_parent_itself(self) -> None:
        page = Page.objects.create(
            name="Root",
            kind=PageKind.SERVICES_MASTER_CATALOG,
            position=0,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Page.objects.filter(pk=page.pk).update(parent_id=page.pk)
