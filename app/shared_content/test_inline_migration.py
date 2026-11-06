"""Synthetic safety checks for the resumable legacy file-to-inline migration."""
import base64
import hashlib
import json
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings

from audit.models import AuditEvent
from media_library.models import AssetUsage
from media_library.services import attach
from media_library.uploads import upload
from page_editor import test_check_http as H
from page_editor.test_media_http import PNG
from shared_content.models import (SharedBasePin, SharedBlock, SharedBudget,
                                   SharedReceipt, SharedRevision)
from shared_content.storage import SharedStorage


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class InlineMigrationTests(TransactionTestCase):
    login = H.EditorCheckHttpTests.login

    def setUp(self):
        H.EditorCheckHttpTests.setUp(self)
        for kind in ('header', 'footer'):
            SharedBlock.objects.get_or_create(kind=kind)
        SharedBudget.objects.get_or_create(singleton=True)
        data = base64.b64decode(PNG, validate=True)
        self.asset = upload(
            actor=self.owner, page_id=self.page.pk,
            upload=SimpleUploadedFile('migration-synthetic.png', data, content_type='image/png'),
            expected_generation=1)

    def legacy_revision(self):
        html = '<header>INLINE-MIGRATION-SYNTHETIC</header>'
        store = SharedStorage()
        descriptor = store.write_new(html)
        block = SharedBlock.objects.get(kind='header')
        row = SharedRevision.objects.create(
            block=block, sequence=1, schema_version='header-v1', html='',
            payload_hash=descriptor['file_sha256'], author_id=self.owner.pk, **descriptor)
        with transaction.atomic(), connection.cursor() as cursor:
            from content.models import lock_content
            lock_content('default')
            cursor.execute(
                'UPDATE ' + connection.ops.quote_name(SharedBlock._meta.db_table) +
                ' SET current_revision_id=%s WHERE id=%s', [row.pk, block.pk])
        return store, descriptor, row, html

    @staticmethod
    def run_command(*args):
        output = StringIO()
        call_command('migrate_shared_inline', *args, stdout=output)
        return output.getvalue().strip()

    def test_dry_apply_and_repeat_preserve_references_and_blob(self):
        store, descriptor, row, html = self.legacy_revision()
        attach(asset_id=self.asset.pk, kind='shared_block', consumer_id=row.pk,
               slot='migration:synthetic')
        receipt = SharedReceipt.objects.create(
            action='apply', actor_id=self.owner.pk, actor_generation=1, block=row.block,
            fingerprint='a' * 64, result_code='noop')
        path = store.root / descriptor['file_key']
        blob = path.read_bytes()
        current = SharedBlock.objects.get(pk=row.block_id).current_revision_id
        usage = list(AssetUsage.objects.filter(consumer_id=row.pk).values())
        receipt_state = list(SharedReceipt.objects.filter(pk=receipt.pk).values())
        audit_before = AuditEvent.objects.count()

        dry = self.run_command()
        self.assertEqual(json.loads(dry), {
            'status': 'VERIFIED', 'verified': 1, 'migrated': 0,
            'remainingFileRows': 1, 'blobsDeleted': 0})
        self.assertEqual(SharedRevision.objects.get(pk=row.pk).storage_kind, 'file')
        self.assertEqual(path.read_bytes(), blob)

        applied = self.run_command('--apply')
        self.assertEqual(json.loads(applied), {
            'status': 'APPLIED', 'verified': 1, 'migrated': 1,
            'remainingFileRows': 0, 'blobsDeleted': 0})
        migrated = SharedRevision.objects.get(pk=row.pk)
        self.assertEqual((migrated.storage_kind, migrated.html, migrated.file_key,
                          migrated.byte_size, migrated.file_sha256),
                         ('inline', html, '', None, ''))
        self.assertEqual(migrated.payload_hash, hashlib.sha256(html.encode()).hexdigest())
        self.assertEqual(SharedBlock.objects.get(pk=row.block_id).current_revision_id, current)
        self.assertEqual(list(AssetUsage.objects.filter(consumer_id=row.pk).values()), usage)
        self.assertEqual(list(SharedReceipt.objects.filter(pk=receipt.pk).values()), receipt_state)
        self.assertEqual(path.read_bytes(), blob)
        self.assertEqual(AuditEvent.objects.filter(
            code='SHARED_INLINE_MIGRATE_ROW',
            object_ref='uuid:' + str(row.block_id)).count(), 1)
        self.assertEqual(AuditEvent.objects.count(), audit_before + 1)
        for secret in (html, str(row.pk), descriptor['file_key'], str(path)):
            self.assertNotIn(secret, applied)

        audit_after = AuditEvent.objects.count()
        repeated = self.run_command('--apply')
        self.assertEqual(json.loads(repeated), {
            'status': 'APPLIED', 'verified': 0, 'migrated': 0,
            'remainingFileRows': 0, 'blobsDeleted': 0})
        self.assertEqual(AuditEvent.objects.count(), audit_after)
        self.assertEqual(path.read_bytes(), blob)

    def test_audit_failure_rolls_back_row_and_retains_blob(self):
        store, descriptor, row, _html = self.legacy_revision()
        path = store.root / descriptor['file_key']
        blob = path.read_bytes()
        with patch(
                'shared_content.management.commands.migrate_shared_inline.record_event',
                side_effect=RuntimeError('SYNTHETIC_AUDIT_FAILURE')):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_AUDIT_FAILURE'):
                self.run_command('--apply')
        unchanged = SharedRevision.objects.get(pk=row.pk)
        self.assertEqual((unchanged.storage_kind, unchanged.html, unchanged.file_key),
                         ('file', '', descriptor['file_key']))
        self.assertEqual(path.read_bytes(), blob)

    def test_blocker_created_after_preflight_prevents_update_and_audit(self):
        store, descriptor, row, _html = self.legacy_revision()
        path = store.root / descriptor['file_key']
        blob = path.read_bytes()
        from shared_content.management.commands import migrate_shared_inline as command
        actual_candidates = command.candidates

        def race():
            rows = actual_candidates()
            SharedBasePin.objects.create(
                revision=row, holder_kind='migration-test', holder_id=uuid4())
            return rows

        audit_before = AuditEvent.objects.count()
        with patch.object(command, 'candidates', side_effect=race):
            with self.assertRaisesRegex(CommandError, 'SHARED_INLINE_MIGRATION_BLOCKED'):
                self.run_command('--apply')
        unchanged = SharedRevision.objects.get(pk=row.pk)
        self.assertEqual((unchanged.storage_kind, unchanged.html, unchanged.file_key),
                         ('file', '', descriptor['file_key']))
        self.assertEqual(AuditEvent.objects.count(), audit_before)
        self.assertEqual(path.read_bytes(), blob)
