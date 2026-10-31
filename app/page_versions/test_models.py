from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from content.models import Page
from .models import PageRevision,PageContentState,OwnerDraft
from .schema import snapshot_v1,digest


class VersionPointerTests(TransactionTestCase):
    def test_current_and_owner_draft_base_are_page_scoped(self):
        first=Page.objects.create(kind=Page.Kind.ARTICLE,name='first')
        other=Page.objects.create(kind=Page.Kind.ARTICLE,name='other')
        payload=snapshot_v1(Page.Kind.ARTICLE,main_text='known fixture').data()
        def revision(page):
            return PageRevision.objects.create(page=page,sequence=1,schema_version='page-content-v1',payload=payload,
                payload_hash=digest(payload),kind='initial',author_id=1)
        own,foreign=revision(first),revision(other)
        with self.assertRaisesMessage(ValidationError,'VERSIONS_CURRENT_PAGE_MISMATCH'):
            PageContentState.objects.create(page=first,current_revision=foreign)
        with self.assertRaisesMessage(ValidationError,'VERSIONS_DRAFT_PAGE_MISMATCH'):
            OwnerDraft.objects.create(page=first,base_revision=foreign,payload=payload,payload_hash=digest(payload),author_id=1)
        current=PageContentState.objects.create(page=first,current_revision=own)
        draft=OwnerDraft.objects.create(page=first,base_revision=own,payload=payload,payload_hash=digest(payload),author_id=1)
        self.assertEqual(current.current_revision_id,own.pk)
        self.assertEqual(draft.base_revision_id,own.pk)
