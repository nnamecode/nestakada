import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from modules.pages.models import LastOperationAction, Page, PageContent, PageKind


User = get_user_model()


class PageContentShapeTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = User.objects.create_superuser(username="nesadmin", password=None)
        cls.page = Page.objects.create(
            name="Service",
            kind=PageKind.SERVICE_DETAIL,
            position=0,
        )

    def _content(self, **overrides) -> dict:
        values = {
            "page": self.page,
            "generation": 2,
            "current_payload": {},
            "current_hash": "a" * 64,
            "current_author": self.owner,
            "current_created_at": timezone.now(),
            "last_operation_id": uuid.uuid4(),
            "last_operation_action": LastOperationAction.SAVE,
            "last_result_generation": 2,
            "last_result_hash": "a" * 64,
        }
        values.update(overrides)
        return values

    def test_last_operation_slot_matches_current_result(self) -> None:
        content = PageContent.objects.create(**self._content())
        self.assertEqual(content.last_result_generation, content.generation)
        self.assertEqual(content.last_result_hash, content.current_hash)

    def test_stale_last_operation_result_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            PageContent.objects.create(**self._content(last_result_generation=1))

    def test_mismatched_last_operation_hash_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            PageContent.objects.create(**self._content(last_result_hash="b" * 64))

    def test_no_revision_history_relation_exists(self) -> None:
        field_names = {field.name for field in PageContent._meta.get_fields()}
        self.assertNotIn("revisions", field_names)
        self.assertNotIn("receipts", field_names)
