import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings

from accounts.models import UserProfile
from accounts.test_support import editor_session
from audit.models import AuditEvent
from django.conf import settings
from . import deletion, ledger
from .models import ServiceRequest


class DeletionTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        os.chmod(self.temporary.name, 0o700)
        self.ledger_root = Path(self.temporary.name) / 'ledger'
        self.ledger_root.mkdir(mode=0o700)
        self.override = override_settings(
            SERVICE_REQUEST_DELETION_LEDGER_ROOT=str(self.ledger_root))
        self.override.enable()
        users = get_user_model()
        self.owner = users.objects.create_user('nesadmin', password='owner-password-123')
        self.employee = users.objects.create_user('worker1', password='worker-password-123')
        UserProfile.objects.create(user=self.owner, role='owner')
        UserProfile.objects.create(user=self.employee, role='employee')
        self.row = self.create_request('d')

    def tearDown(self):
        self.override.disable()
        self.temporary.cleanup()

    def create_request(self, digit):
        return ServiceRequest.objects.create(
            source='home', name='Тестовый клиент', phone='+70000000000',
            car='', comment='', consent_version='synthetic-v1',
            intent_digest=digit * 64)

    def test_ledger_is_idempotent_bounded_and_contains_no_pii(self):
        first = ledger.record(self.row.pk)
        second = ledger.record(self.row.pk)
        self.assertEqual(first.request_id, second.request_id)
        path = Path(settings.SERVICE_REQUEST_DELETION_LEDGER_ROOT) / f'{self.row.pk}.deleted'
        body = path.read_text(encoding='ascii')
        self.assertLessEqual(len(body.encode('ascii')), ledger.ENTRY_MAX_BYTES)
        self.assertNotIn(self.row.name, body)
        self.assertNotIn(self.row.phone, body)
        self.assertEqual(ledger.get(self.row.pk).request_id, self.row.pk)

    def test_fault_after_ledger_rolls_back_db_and_retry_converges(self):
        with patch('service_requests.deletion.record_event',
                   side_effect=DatabaseError('private failure')):
            with self.assertRaises(DatabaseError):
                deletion.delete(request_id=self.row.pk, actor_id=self.owner.pk)
        self.assertTrue(ServiceRequest.objects.filter(pk=self.row.pk).exists())
        self.assertIsNotNone(ledger.get(self.row.pk))
        result = deletion.delete(request_id=self.row.pk, actor_id=self.owner.pk)
        self.assertFalse(result.replay)
        replay = deletion.delete(request_id=self.row.pk, actor_id=self.owner.pk)
        self.assertTrue(replay.replay)

    def test_reconcile_removes_restored_row(self):
        ledger.record(self.row.pk)
        entries, deleted = deletion.reconcile()
        self.assertEqual((entries, deleted), (1, 1))
        self.assertFalse(ServiceRequest.objects.filter(pk=self.row.pk).exists())
        call_command('reconcile_request_deletions', verbosity=0)

    def test_missing_root_blocks_restore_and_keeps_row(self):
        missing = Path(self.temporary.name) / 'missing-ledger'
        with override_settings(SERVICE_REQUEST_DELETION_LEDGER_ROOT=str(missing)):
            with self.assertRaises(CommandError):
                call_command('reconcile_request_deletions', verbosity=0)
        self.assertTrue(ServiceRequest.objects.filter(pk=self.row.pk).exists())
        self.assertFalse(missing.exists())

    def test_wrong_mode_unknown_and_symlink_entries_fail_closed(self):
        os.chmod(self.ledger_root, 0o755)
        with self.assertRaises(ledger.LedgerError):
            ledger.entries()
        os.chmod(self.ledger_root, 0o700)
        unknown = self.ledger_root / 'unexpected'
        unknown.write_text('x', encoding='ascii')
        with self.assertRaises(ledger.LedgerError):
            ledger.entries()
        unknown.unlink()
        target = self.ledger_root / 'target'
        target.write_text('x', encoding='ascii')
        link = self.ledger_root / f'{uuid4()}.deleted'
        link.symlink_to(target)
        with self.assertRaises(ledger.LedgerError):
            ledger.entries()

    def test_write_limit_refuses_before_second_entry(self):
        with patch.object(ledger, 'ENTRY_MAX_COUNT', 1):
            ledger.record(self.row.pk)
            with self.assertRaisesRegex(
                    ledger.LedgerError, 'REQUEST_LEDGER_COUNT_LIMIT'):
                ledger.record(uuid4())
        self.assertEqual(len(tuple(self.ledger_root.glob('*.deleted'))), 1)


class ConcurrentDeletionTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        os.chmod(self.temporary.name, 0o700)
        self.ledger_root = Path(self.temporary.name) / 'ledger'
        self.ledger_root.mkdir(mode=0o700)
        self.override = override_settings(
            SERVICE_REQUEST_DELETION_LEDGER_ROOT=str(self.ledger_root))
        self.override.enable()
        users = get_user_model()
        self.owner = users.objects.create_user(
            'nesadmin', password='owner-password-123')
        UserProfile.objects.create(user=self.owner, role='owner')
        self.row = ServiceRequest.objects.create(
            source='home', name='Тестовый клиент', phone='+70000000000',
            car='', comment='', consent_version='synthetic-v1',
            intent_digest='e' * 64)

    def tearDown(self):
        self.override.disable()
        self.temporary.cleanup()

    def test_two_concurrent_deletes_converge(self):
        barrier = threading.Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return deletion.delete(
                    request_id=self.row.pk, actor_id=self.owner.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(sorted(item.replay for item in results), [False, True])
        self.assertFalse(ServiceRequest.objects.filter(pk=self.row.pk).exists())
        self.assertEqual(
            AuditEvent.objects.filter(code='REQUEST_DELETED').count(), 1)

    def test_concurrent_ledger_cap_has_one_winner(self):
        barrier = threading.Barrier(2)
        request_ids = (uuid4(), uuid4())

        def run(request_id):
            barrier.wait(timeout=5)
            try:
                ledger.record(request_id)
                return 'created'
            except ledger.LedgerError as exc:
                return str(exc)

        with patch.object(ledger, 'ENTRY_MAX_COUNT', 1):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, request_ids))
        self.assertEqual(results.count('created'), 1)
        self.assertEqual(results.count('REQUEST_LEDGER_COUNT_LIMIT'), 1)
        self.assertEqual(len(tuple(self.ledger_root.glob('*.deleted'))), 1)
