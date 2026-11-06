"""REF-3 acceptance slice for the v0.7 inline Header/Footer commands."""
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import models
from django.test import TransactionTestCase

from accounts.models import UserProfile
from accounts.test_support import editor_session
from audit.models import AuditEvent

from .models import SharedBlock, SharedDraft, SharedIdentityReservation, SharedRevision
from .content import descriptor_for
from .simple_commands import (commit_normalized_current, commit_normalized_draft,
                              restore_normalized_current, save_normalized_draft)


def raw(model):
    return models.QuerySet(model=model, using='default')


class SimpleSharedCommandsTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username='nesadmin', password='owner-password')
        UserProfile.objects.create(user=self.owner, role=UserProfile.Role.OWNER, generation=1)
        self.employee = user_model.objects.create_user(username='employee', password='employee-password')
        UserProfile.objects.create(user=self.employee, role=UserProfile.Role.EMPLOYEE, generation=1)
        self.owner_session = editor_session(self.owner)
        self.employee_session = editor_session(self.employee)
        self.block = SharedBlock(id=uuid4(), kind='header', generation=1)
        raw(SharedBlock).bulk_create([self.block])

    def commit(self, html, expected=None):
        return commit_normalized_current(
            actor=self.owner, kind='header', expected_generation=1,
            session_key=self.owner_session, expected_current_id=expected,
            html=html, bindings=[])

    def test_ref_ac_007_apply_and_restore_are_inline_atomic_revisions(self):
        first = self.commit('<header>first</header>')
        second = self.commit('<header>second</header>', first.pk)
        restored = restore_normalized_current(
            actor=self.owner, kind='header', expected_generation=1,
            session_key=self.owner_session, expected_current_id=second.pk,
            source_revision_id=first.pk, source_descriptor=descriptor_for(first),
            html=first.html, bindings=[])

        self.block.refresh_from_db()
        self.assertEqual(self.block.current_revision_id, restored.pk)
        self.assertEqual(restored.html, '<header>first</header>')
        self.assertEqual(restored.storage_kind, 'inline')
        self.assertEqual(restored.source_revision_id, first.pk)
        self.assertEqual(list(SharedRevision.objects.order_by('sequence').values_list('sequence', flat=True)), [1, 2, 3])
        self.assertEqual(SharedIdentityReservation.objects.filter(
            pk__in=[first.pk, second.pk, restored.pk], kind='sharedrevision').count(), 3)
        self.assertEqual(AuditEvent.objects.filter(code__in=['SHARED_APPLY', 'SHARED_RESTORE']).count(), 3)

    def test_failure_rolls_back_revision_current_and_audit(self):
        first = self.commit('<header>safe</header>')
        before_events = AuditEvent.objects.count()
        with patch('shared_content.simple_commands.record_event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.commit('<header>must-not-publish</header>', first.pk)

        self.block.refresh_from_db()
        self.assertEqual(self.block.current_revision_id, first.pk)
        self.assertEqual(SharedRevision.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), before_events)

    def test_employee_cannot_write_shared_content(self):
        with self.assertRaises(PermissionDenied):
            commit_normalized_current(
                actor=self.employee, kind='header', expected_generation=1,
                session_key=self.employee_session, expected_current_id=None,
                html='<header>forbidden</header>', bindings=[])
        self.assertFalse(SharedRevision.objects.exists())

    def test_inline_draft_create_update_and_publish(self):
        current = self.commit('<header>current</header>')
        first = save_normalized_draft(
            actor=self.owner, kind='header', expected_generation=1,
            session_key=self.owner_session, expected_current_id=current.pk,
            html='<header>draft-one</header>', bindings=[])
        second = save_normalized_draft(
            actor=self.owner, kind='header', expected_generation=1,
            session_key=self.owner_session, expected_current_id=current.pk,
            draft_id=first.pk, draft_revision=first.revision,
            html='<header>draft-two</header>', bindings=[])
        published = commit_normalized_draft(
            actor=self.owner, kind='header', expected_generation=1,
            session_key=self.owner_session, expected_current_id=current.pk,
            draft_id=second.pk, draft_revision=second.revision,
            html='<header>draft-two</header>', bindings=[])

        self.block.refresh_from_db()
        self.assertEqual(second.revision, 2)
        self.assertEqual(self.block.current_revision_id, published.pk)
        self.assertEqual(published.html, '<header>draft-two</header>')
        self.assertFalse(SharedDraft.objects.exists())
        self.assertTrue(SharedIdentityReservation.objects.filter(
            pk=first.pk, kind='shareddraft').exists())
