"""Focused REF-4 tests for simple current-source page commits."""
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings

from accounts import services as auth_services
from accounts.services import bootstrap_owner, create_employee, set_grant
from accounts.models import UserProfile
from accounts.test_support import editor_session
from audit.models import AuditEvent
from content.models import Page, Route
from page_versions import (engine as E, schema as S, services as V,
                           simple_commands as C)
from page_versions.models import (OperationReceipt, OwnerDraft,
                                  PageContentState, PageRevision,
                                  RevisionProtection, VersionBasePin)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SimplePageCommitTests(TransactionTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        media = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name)
        media.enable()
        self.addCleanup(media.disable)
        self.owner = bootstrap_owner('Simple-page-owner-password')
        self.employee = create_employee(
            actor=self.owner, username='simple-page-employee',
            password='Simple-page-employee-password')
        self.page = Page.objects.create(kind=Page.Kind.ARTICLE, name='Simple page')
        Route.objects.create(
            page=self.page, kind=Route.Kind.PRIMARY, target='/simple-page/')
        set_grant(
            actor=self.owner, employee=self.employee,
            page=self.page, main_text=True)
        UserProfile.objects.filter(user=self.employee).update(generation=1)
        self.initial = V.initialize(
            actor=self.owner, page_id=self.page.pk,
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>initial</p>', h1='Protected'),
            expected_generation=1, operation_id=uuid4())['result_id']

    def current(self):
        return PageContentState.objects.get(page=self.page).current_revision_id

    @staticmethod
    def session(actor):
        return editor_session(actor, generation=1)

    def simple_manual(self, name='Simple manual'):
        prepared = V.prepare_manual(
            actor=self.owner, page_id=self.page.pk, expected_generation=1)
        operation = uuid4()
        C.create_manual(
            actor=self.owner, page_id=self.page.pk,
            confirmation=prepared['confirmation'], expected_generation=1,
            operation_id=operation, name=name)
        return PageRevision.objects.get(pk=operation)

    def delete_confirmation(self, row):
        from page_versions.operations import _binding, ticket
        return ticket('delete', {
            'binding': _binding(self.owner, self.page, 1),
            'target': str(row.pk), 'stamp': E.stamp(self.page, row),
        })

    def test_employee_commit_preserves_protected_fields_without_receipt(self):
        before_receipts = OperationReceipt.objects.count()
        result = C.commit_employee(
            actor=self.employee, page_id=self.page.pk,
            base_revision=self.current(),
            patch=S.TextPricePatch(main_text='<p>employee</p>'),
            expected_generation=1, operation_id=uuid4(),
            editor_request_fingerprint='a' * 64,
            editor_session_key=str(self.session(self.employee)))
        row = PageRevision.objects.get(pk=result['result_id'])
        self.assertEqual(row.payload['main_text'], '<p>employee</p>')
        self.assertEqual(row.payload['h1'], 'Protected')
        self.assertEqual(self.current(), row.pk)
        self.assertEqual(OperationReceipt.objects.count(), before_receipts)
        self.assertEqual(AuditEvent.objects.filter(
            code='VERSION_COMMIT_EMPLOYEE').count(), 1)

    def test_malformed_editor_session_is_rejected_before_commit(self):
        key=str(self.session(self.employee))
        data=Session.objects.get(pk=key).get_decoded()
        data[auth_services.SESSION_ISSUED_AT]=1
        Session.objects.filter(pk=key).update(
            session_data=SessionStore().encode(data))
        before=(self.current(),PageRevision.objects.count(),AuditEvent.objects.count())
        with self.assertRaisesMessage(ValidationError,'EDITOR_SESSION_ENDED'):
            C.commit_employee(
                actor=self.employee,page_id=self.page.pk,
                base_revision=self.current(),
                patch=S.TextPricePatch(main_text='<p>must not commit</p>'),
                expected_generation=1,operation_id=uuid4(),
                editor_request_fingerprint='f' * 64,
                editor_session_key=key)
        self.assertEqual(
            (self.current(),PageRevision.objects.count(),AuditEvent.objects.count()),
            before)

    def test_owner_commit_keeps_draft_pin_stable_and_limit_ten(self):
        base = self.current()
        draft_result = V.save_owner_draft(
            actor=self.owner, page_id=self.page.pk, base_revision=base,
            snapshot=S.snapshot_v1(self.page.kind, main_text='private draft'),
            expected_generation=1, operation_id=uuid4())
        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk, version_id=base,
            expected_generation=1)
        V.set_stable(
            actor=self.owner, page_id=self.page.pk, version_id=base,
            view_receipt=viewed['view_receipt'], expected_generation=1,
            operation_id=uuid4())
        session = str(self.session(self.owner))
        for number in range(11):
            C.commit_owner(
                actor=self.owner, page_id=self.page.pk,
                base_revision=self.current(),
                snapshot=S.snapshot_v1(
                    self.page.kind, main_text='<p>%s</p>' % number,
                    h1='Protected'), expected_generation=1,
                operation_id=uuid4(),
                editor_request_fingerprint=('%064x' % (number + 1)),
                editor_session_key=session)
        self.assertEqual(PageRevision.objects.filter(
            page=self.page, stable_protection__isnull=True).count(), 10)
        self.assertTrue(RevisionProtection.objects.filter(
            revision_id=base).exists())
        self.assertTrue(OwnerDraft.objects.filter(
            pk=draft_result['result_id']).exists())
        self.assertTrue(VersionBasePin.objects.filter(
            revision_id=base, holder_kind='owner_draft',
            holder_id=draft_result['result_id']).exists())

    def test_denied_and_audit_failure_leave_current_unchanged(self):
        before = (self.current(), PageRevision.objects.count(),
                  OperationReceipt.objects.count(), AuditEvent.objects.count())
        with self.assertRaises(PermissionDenied):
            C.commit_employee(
                actor=self.employee, page_id=self.page.pk,
                base_revision=self.current(),
                patch=S.TextPricePatch(price=[]),
                expected_generation=1, operation_id=uuid4(),
                editor_request_fingerprint='b' * 64,
                editor_session_key=str(self.session(self.employee)))
        self.assertEqual((self.current(), PageRevision.objects.count(),
                          OperationReceipt.objects.count(), AuditEvent.objects.count()), before)
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_AUDIT_FAILURE')):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_AUDIT_FAILURE'):
                C.commit_owner(
                    actor=self.owner, page_id=self.page.pk,
                    base_revision=self.current(),
                    snapshot=S.snapshot_v1(
                        self.page.kind, main_text='<p>rollback</p>', h1='Protected'),
                    expected_generation=1, operation_id=uuid4(),
                    editor_request_fingerprint='c' * 64,
                    editor_session_key=str(self.session(self.owner)))
        self.assertEqual((self.current(), PageRevision.objects.count(),
                          OperationReceipt.objects.count(), AuditEvent.objects.count()), before)

    def test_draft_create_rebase_cancel_without_receipt_or_pin(self):
        session = str(self.session(self.owner))
        receipts = OperationReceipt.objects.count()
        created = C.save_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>draft</p>', h1='Protected'),
            expected_generation=1, operation_id=uuid4(),
            editor_request_fingerprint='d' * 64,
            editor_session_key=session)
        draft = OwnerDraft.objects.get(pk=created['result_id'])
        self.assertEqual(draft.revision, 1)
        self.assertFalse(VersionBasePin.objects.filter(
            holder_kind='owner_draft', holder_id=draft.pk).exists())

        C.commit_owner(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>advanced</p>', h1='Protected'),
            expected_generation=1, operation_id=uuid4(),
            editor_request_fingerprint='e' * 64,
            editor_session_key=session)
        rebased = C.save_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>rebased</p>', h1='Protected'),
            expected_generation=1, operation_id=uuid4(),
            draft_revision=draft.revision, rebase=True, draft_id=draft.pk,
            expected_draft_hash=S.digest(draft.payload),
            expected_draft_base=draft.base_revision_id,
            editor_request_fingerprint='f' * 64,
            editor_session_key=session)
        draft.refresh_from_db()
        self.assertEqual(draft.revision, 2)
        self.assertEqual(draft.base_revision_id, self.current())
        self.assertEqual(rebased['draftBasis']['revision'], 2)
        self.assertFalse(VersionBasePin.objects.filter(
            holder_kind='owner_draft', holder_id=draft.pk).exists())

        cancelled = C.cancel_owner_draft(
            actor=self.owner, page_id=self.page.pk, draft_id=draft.pk,
            draft_revision=draft.revision, expected_generation=1,
            operation_id=uuid4(), editor_request_fingerprint='1' * 64,
            editor_session_key=session)
        self.assertTrue(cancelled['gone'])
        self.assertFalse(OwnerDraft.objects.filter(pk=draft.pk).exists())
        self.assertEqual(OperationReceipt.objects.count(), receipts)

    def test_legacy_cancel_receipt_still_replays(self):
        session = str(self.session(self.owner))
        created = V.save_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>legacy draft</p>'),
            expected_generation=1, operation_id=uuid4())
        draft = OwnerDraft.objects.get(pk=created['result_id'])
        operation = uuid4()
        fingerprint = '2' * 64
        original = V.cancel_owner_draft(
            actor=self.owner, page_id=self.page.pk, draft_id=draft.pk,
            draft_revision=draft.revision, expected_generation=1,
            operation_id=operation,
            editor_request_fingerprint=fingerprint,
            editor_session_key=session)
        replay = C.cancel_owner_draft(
            actor=self.owner, page_id=self.page.pk, draft_id=draft.pk,
            draft_revision=draft.revision, expected_generation=1,
            operation_id=operation,
            editor_request_fingerprint=fingerprint,
            editor_session_key=session)
        self.assertFalse(original['replay'])
        self.assertTrue(replay['replay'])
        self.assertEqual(replay['result_id'], original['result_id'])

    def test_publish_draft_and_restore_without_new_receipt_stage_or_pin(self):
        session = str(self.session(self.owner))
        receipts = OperationReceipt.objects.count()
        created = C.save_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>draft publish</p>',
                h1='Protected'), expected_generation=1,
            operation_id=uuid4(), editor_request_fingerprint='3' * 64,
            editor_session_key=session)
        draft = OwnerDraft.objects.get(pk=created['result_id'])
        published = C.publish_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>edited publish</p>',
                h1='Protected'), expected_generation=1,
            operation_id=uuid4(), draft_id=draft.pk,
            draft_revision=draft.revision,
            expected_draft_hash=S.digest(draft.payload),
            editor_request_fingerprint='4' * 64,
            editor_session_key=session)
        published_row = PageRevision.objects.get(pk=published['result_id'])
        self.assertEqual(published_row.payload['main_text'], '<p>edited publish</p>')
        self.assertFalse(OwnerDraft.objects.filter(pk=draft.pk).exists())
        self.assertFalse(VersionBasePin.objects.filter(holder_id=draft.pk).exists())

        source = published_row
        C.commit_owner(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>new current</p>', h1='Protected'),
            expected_generation=1, operation_id=uuid4(),
            editor_request_fingerprint='5' * 64,
            editor_session_key=session)
        prepared = V.prepare_restore(
            actor=self.employee, page_id=self.page.pk,
            version_id=source.pk, expected_generation=1)
        employee_session = str(self.session(self.employee))
        restored = C.restore_prepared(
            actor=self.employee, page_id=self.page.pk,
            preparation=prepared['preparation'],
            snapshot=S.Snapshot.trusted(prepared['payload'], self.page.kind),
            expected_generation=1, operation_id=uuid4(),
            expected_fields=prepared['fields'],
            editor_session_key=employee_session)
        restored_row = PageRevision.objects.get(pk=restored['result_id'])
        self.assertEqual(restored_row.source_revision_id, source.pk)
        self.assertEqual(restored_row.payload['main_text'], '<p>edited publish</p>')
        self.assertEqual(restored_row.payload['h1'], 'Protected')
        self.assertEqual(self.current(), restored_row.pk)
        self.assertEqual(OperationReceipt.objects.count(), receipts)

    def test_publish_audit_failure_rolls_back_revision_current_and_draft(self):
        session = str(self.session(self.owner))
        created = C.save_owner_draft(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>rollback draft</p>', h1='Protected'),
            expected_generation=1, operation_id=uuid4(),
            editor_request_fingerprint='6' * 64,
            editor_session_key=session)
        draft = OwnerDraft.objects.get(pk=created['result_id'])
        before = (self.current(), PageRevision.objects.count(),
                  OperationReceipt.objects.count(), AuditEvent.objects.count())
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_PUBLISH_AUDIT_FAILURE')):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_PUBLISH_AUDIT_FAILURE'):
                C.publish_owner_draft(
                    actor=self.owner, page_id=self.page.pk,
                    base_revision=self.current(),
                    snapshot=S.Snapshot.trusted(draft.payload, self.page.kind),
                    expected_generation=1, operation_id=uuid4(),
                    draft_id=draft.pk, draft_revision=draft.revision,
                    expected_draft_hash=S.digest(draft.payload),
                    editor_request_fingerprint='7' * 64,
                    editor_session_key=session)
        self.assertEqual((self.current(), PageRevision.objects.count(),
                          OperationReceipt.objects.count(), AuditEvent.objects.count()), before)
        self.assertTrue(OwnerDraft.objects.filter(pk=draft.pk).exists())

    def test_restore_audit_failure_rolls_back_revision_and_current(self):
        session = str(self.session(self.owner))
        source = self.current()
        C.commit_owner(
            actor=self.owner, page_id=self.page.pk,
            base_revision=self.current(),
            snapshot=S.snapshot_v1(
                self.page.kind, main_text='<p>later</p>', h1='Protected'),
            expected_generation=1, operation_id=uuid4(),
            editor_request_fingerprint='8' * 64,
            editor_session_key=session)
        prepared = V.prepare_restore(
            actor=self.owner, page_id=self.page.pk,
            version_id=source, expected_generation=1)
        before = (self.current(), PageRevision.objects.count(),
                  OperationReceipt.objects.count(), AuditEvent.objects.count())
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_RESTORE_AUDIT_FAILURE')):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_RESTORE_AUDIT_FAILURE'):
                C.restore_prepared(
                    actor=self.owner, page_id=self.page.pk,
                    preparation=prepared['preparation'],
                    snapshot=S.Snapshot.trusted(
                        prepared['payload'], self.page.kind),
                    expected_generation=1, operation_id=uuid4(),
                    expected_fields=prepared['fields'],
                    editor_session_key=session)
        self.assertEqual((self.current(), PageRevision.objects.count(),
                          OperationReceipt.objects.count(), AuditEvent.objects.count()), before)

    def test_manual_metadata_stable_demote_delete_without_receipts(self):
        receipts = OperationReceipt.objects.count()
        prepared = V.prepare_manual(
            actor=self.owner, page_id=self.page.pk, expected_generation=1)
        operation = uuid4()
        created = C.create_manual(
            actor=self.owner, page_id=self.page.pk,
            confirmation=prepared['confirmation'], expected_generation=1,
            operation_id=operation, name='Simple manual',
            comment='first', manual_date=None)
        self.assertEqual(created['result_id'], str(operation))
        row = PageRevision.objects.get(pk=operation)
        self.assertEqual(row.kind, 'manual')
        self.assertEqual(str(self.current()), self.initial)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        with self.assertRaises(ValidationError):
            C.create_manual(
                actor=self.owner, page_id=self.page.pk,
                confirmation=prepared['confirmation'], expected_generation=1,
                operation_id=operation, name='Simple manual')

        C.edit_manual_metadata(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            metadata_generation=1, expected_generation=1,
            operation_id=uuid4(), name='Edited', comment='second')
        row.refresh_from_db()
        self.assertEqual(row.metadata.name, 'Edited')
        self.assertEqual(row.metadata.generation, 2)

        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        C.set_stable(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            view_receipt=viewed['view_receipt'], expected_generation=1,
            operation_id=uuid4())
        self.assertTrue(RevisionProtection.objects.filter(
            revision=row).exists())
        demote = V.prepare_demote(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        C.demote_stable(
            actor=self.owner, page_id=self.page.pk,
            confirmation=demote['confirmation'],
            password='Simple-page-owner-password', expected_generation=1,
            operation_id=uuid4())
        self.assertFalse(RevisionProtection.objects.filter(
            revision=row).exists())
        deletion = V.prepare_delete(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        C.delete_revision(
            actor=self.owner, page_id=self.page.pk,
            confirmation=deletion['confirmation'], expected_generation=1,
            operation_id=uuid4())
        self.assertFalse(PageRevision.objects.filter(pk=row.pk).exists())
        self.assertEqual(OperationReceipt.objects.count(), receipts)

    def test_manual_and_stable_audit_faults_roll_back(self):
        receipts = OperationReceipt.objects.count()
        prepared = V.prepare_manual(
            actor=self.owner, page_id=self.page.pk, expected_generation=1)
        before = (PageRevision.objects.count(), AuditEvent.objects.count())
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_MANUAL_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_MANUAL_AUDIT_FAILURE'):
                C.create_manual(
                    actor=self.owner, page_id=self.page.pk,
                    confirmation=prepared['confirmation'],
                    expected_generation=1, operation_id=uuid4())
        self.assertEqual(
            (PageRevision.objects.count(), AuditEvent.objects.count()), before)

        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk,
            version_id=self.initial, expected_generation=1)
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_STABLE_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_STABLE_AUDIT_FAILURE'):
                C.set_stable(
                    actor=self.owner, page_id=self.page.pk,
                    version_id=self.initial,
                    view_receipt=viewed['view_receipt'],
                    expected_generation=1, operation_id=uuid4())
        self.assertFalse(RevisionProtection.objects.filter(
            revision_id=self.initial).exists())
        self.assertEqual(OperationReceipt.objects.count(), receipts)

    def test_concurrent_manual_double_submit_creates_one_revision(self):
        prepared = V.prepare_manual(
            actor=self.owner, page_id=self.page.pk, expected_generation=1)
        operation = uuid4()
        barrier = Barrier(2)

        def create():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return C.create_manual(
                    actor=self.owner, page_id=self.page.pk,
                    confirmation=prepared['confirmation'],
                    expected_generation=1, operation_id=operation,
                    name='Concurrent simple manual')
            except ValidationError as exc:
                return str(exc)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: create(), range(2)))
        successes = [result for result in results if isinstance(result, dict)]
        failures = [result for result in results if isinstance(result, str)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertIn('VERSIONS_OPERATION_ID_CONSUMED', failures[0])
        self.assertEqual(PageRevision.objects.filter(pk=operation).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='VERSION_CREATE_MANUAL').count(), 1)

    def test_metadata_cas_and_stale_view_preserve_content_current_stable(self):
        row = self.simple_manual()
        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        before_payload = row.payload
        before_current = self.current()
        C.edit_manual_metadata(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            metadata_generation=1, expected_generation=1,
            operation_id=uuid4(), name='Changed metadata')
        with self.assertRaises(ValidationError):
            C.edit_manual_metadata(
                actor=self.owner, page_id=self.page.pk, version_id=row.pk,
                metadata_generation=1, expected_generation=1,
                operation_id=uuid4(), name='Repeated stale metadata')
        with self.assertRaises(ValidationError):
            C.set_stable(
                actor=self.owner, page_id=self.page.pk, version_id=row.pk,
                view_receipt=viewed['view_receipt'], expected_generation=1,
                operation_id=uuid4())
        with self.assertRaises(ValidationError):
            C.set_stable(
                actor=self.owner, page_id=self.page.pk, version_id=row.pk,
                view_receipt=viewed['view_receipt'][:-1] + 'x',
                expected_generation=1, operation_id=uuid4())
        row.refresh_from_db()
        self.assertEqual(row.payload, before_payload)
        self.assertEqual(self.current(), before_current)
        self.assertFalse(RevisionProtection.objects.filter(
            revision=row).exists())

    def test_demote_rejects_stale_composition_stamp_generation_and_password_hash(self):
        row = self.simple_manual('Stable target')
        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        C.set_stable(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            view_receipt=viewed['view_receipt'], expected_generation=1,
            operation_id=uuid4())
        stale_composition = V.prepare_demote(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        self.simple_manual('Composition changed')
        with self.assertRaises(ValidationError):
            C.demote_stable(
                actor=self.owner, page_id=self.page.pk,
                confirmation=stale_composition['confirmation'],
                password='Simple-page-owner-password', expected_generation=1,
                operation_id=uuid4())

        stale_stamp = V.prepare_demote(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        C.edit_manual_metadata(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            metadata_generation=1, expected_generation=1,
            operation_id=uuid4(), name='Stamp changed')
        with self.assertRaises(ValidationError):
            C.demote_stable(
                actor=self.owner, page_id=self.page.pk,
                confirmation=stale_stamp['confirmation'],
                password='Simple-page-owner-password', expected_generation=1,
                operation_id=uuid4())

        current = V.prepare_demote(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        with self.assertRaises(PermissionDenied):
            C.demote_stable(
                actor=self.owner, page_id=self.page.pk,
                confirmation=current['confirmation'],
                password='Simple-page-owner-password', expected_generation=2,
                operation_id=uuid4())

        original_hash = get_user_model().objects.get(pk=self.owner.pk).password
        original_enter = E.enter

        def changed_password(*args, **kwargs):
            get_user_model().objects.filter(pk=self.owner.pk).update(
                password=make_password('Changed-between-check-and-lock'))
            return original_enter(*args, **kwargs)

        try:
            with patch('page_versions.simple_commands.E.enter',
                       side_effect=changed_password):
                with self.assertRaises(PermissionDenied):
                    C.demote_stable(
                        actor=self.owner, page_id=self.page.pk,
                        confirmation=current['confirmation'],
                        password='Simple-page-owner-password',
                        expected_generation=1, operation_id=uuid4())
        finally:
            get_user_model().objects.filter(pk=self.owner.pk).update(
                password=original_hash)
        self.assertTrue(RevisionProtection.objects.filter(
            revision=row).exists())

    def test_demote_limit_preserves_current_pin_and_draft_base(self):
        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk,
            version_id=self.initial, expected_generation=1)
        C.set_stable(
            actor=self.owner, page_id=self.page.pk,
            version_id=self.initial, view_receipt=viewed['view_receipt'],
            expected_generation=1, operation_id=uuid4())
        rows = [self.simple_manual('ordinary %s' % number)
                for number in range(10)]
        pin = VersionBasePin.objects.create(
            revision=rows[0], holder_kind='restore_stage',
            holder_id=uuid4())
        instant = E.now()
        draft = OwnerDraft.objects.create(
            page=self.page, base_revision=rows[1], payload=rows[1].payload,
            payload_hash=rows[1].payload_hash, author_id=self.owner.pk,
            created_at=instant, updated_at=instant)
        prepared = V.prepare_demote(
            actor=self.owner, page_id=self.page.pk,
            version_id=self.initial, expected_generation=1)
        result = C.demote_stable(
            actor=self.owner, page_id=self.page.pk,
            confirmation=prepared['confirmation'],
            password='Simple-page-owner-password', expected_generation=1,
            operation_id=uuid4())
        self.assertFalse(result['gone'])
        self.assertTrue(PageRevision.objects.filter(pk=self.initial).exists())
        self.assertTrue(PageRevision.objects.filter(pk=pin.revision_id).exists())
        self.assertTrue(PageRevision.objects.filter(
            pk=draft.base_revision_id).exists())
        self.assertFalse(PageRevision.objects.filter(pk=rows[2].pk).exists())
        self.assertEqual(PageRevision.objects.filter(
            page=self.page, stable_protection__isnull=True).count(), 10)

    def test_simple_delete_protects_current_stable_pin_and_draft_base(self):
        stable, pinned, drafted = [self.simple_manual(str(index))
                                   for index in range(3)]
        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk, version_id=stable.pk,
            expected_generation=1)
        C.set_stable(
            actor=self.owner, page_id=self.page.pk, version_id=stable.pk,
            view_receipt=viewed['view_receipt'], expected_generation=1,
            operation_id=uuid4())
        VersionBasePin.objects.create(
            revision=pinned, holder_kind='restore_stage', holder_id=uuid4())
        instant = E.now()
        OwnerDraft.objects.create(
            page=self.page, base_revision=drafted, payload=drafted.payload,
            payload_hash=drafted.payload_hash, author_id=self.owner.pk,
            created_at=instant, updated_at=instant)
        current = PageRevision.objects.get(pk=self.current())
        for row in (current, stable, pinned, drafted):
            with self.assertRaises(ValidationError):
                C.delete_revision(
                    actor=self.owner, page_id=self.page.pk,
                    confirmation=self.delete_confirmation(row),
                    expected_generation=1, operation_id=uuid4())
            self.assertTrue(PageRevision.objects.filter(pk=row.pk).exists())

    def test_audit_fault_rolls_back_metadata_demote_and_delete(self):
        row = self.simple_manual()
        before_meta = E.serial_meta(row.metadata)
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_METADATA_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_METADATA_AUDIT_FAILURE'):
                C.edit_manual_metadata(
                    actor=self.owner, page_id=self.page.pk,
                    version_id=row.pk, metadata_generation=1,
                    expected_generation=1, operation_id=uuid4(),
                    name='Must rollback')
        row.refresh_from_db()
        self.assertEqual(E.serial_meta(row.metadata), before_meta)

        viewed = V.view_version(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        C.set_stable(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            view_receipt=viewed['view_receipt'], expected_generation=1,
            operation_id=uuid4())
        prepared = V.prepare_demote(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_DEMOTE_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_DEMOTE_AUDIT_FAILURE'):
                C.demote_stable(
                    actor=self.owner, page_id=self.page.pk,
                    confirmation=prepared['confirmation'],
                    password='Simple-page-owner-password',
                    expected_generation=1, operation_id=uuid4())
        self.assertTrue(RevisionProtection.objects.filter(
            revision=row).exists())
        prepared = V.prepare_demote(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        C.demote_stable(
            actor=self.owner, page_id=self.page.pk,
            confirmation=prepared['confirmation'],
            password='Simple-page-owner-password', expected_generation=1,
            operation_id=uuid4())
        deletion = V.prepare_delete(
            actor=self.owner, page_id=self.page.pk, version_id=row.pk,
            expected_generation=1)
        with patch('page_versions.engine.record_event',
                   side_effect=RuntimeError('SYNTHETIC_DELETE_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_DELETE_AUDIT_FAILURE'):
                C.delete_revision(
                    actor=self.owner, page_id=self.page.pk,
                    confirmation=deletion['confirmation'],
                    expected_generation=1, operation_id=uuid4())
        self.assertTrue(PageRevision.objects.filter(pk=row.pk).exists())
