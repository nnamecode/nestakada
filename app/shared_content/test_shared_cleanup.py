"""LC07 real HTTP/PG/private-file lifecycle checks; candidate remains unvetted."""
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch
from uuid import UUID, uuid4

from django.conf import settings
from django.db import connection, connections
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from page_editor.test_check_http import OWNER_PASSWORD
from . import test_shared_reservation as R
from .models import (SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage,
    SharedBasePin, SharedReceipt, SharedIdentityReservation, SharedCleanupJob, SharedBudget)
from .storage import SharedStorage
from media_library.models import AssetUsage
from media_library.storage import MediaStorage


class SharedCleanupStorageTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='lc-unlink-')
        self.addCleanup(self.temp.cleanup)
        override = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name)
        override.enable(); self.addCleanup(override.disable)
        self.store = SharedStorage()

    def refuse_unlink(self, descriptor):
        from .faults import SharedFault
        with self.assertRaises(SharedFault) as failure:
            self.store.unlink_verified(descriptor)
        self.assertEqual((failure.exception.code, failure.exception.status),
                         ('SHARED_CLEANUP_FILE_UNAVAILABLE', 503))

    def test_lc006_wrong_sha_symlink_and_hardlink_preserve_every_named_victim(self):
        other = self.store.write_new('LC-UNRELATED-VICTIM')
        other_path = self.store.root / other['file_key']
        for vector in ('wrong-sha', 'symlink', 'hardlink'):
            with self.subTest(vector=vector):
                descriptor = self.store.write_new('LC-SELECTED-VICTIM-' + vector)
                path = self.store.root / descriptor['file_key']
                before = path.read_bytes()
                if vector == 'wrong-sha':
                    descriptor = dict(descriptor, file_sha256='0' * 64)
                else:
                    path.unlink()  # Only this own fixture leaf is replaced.
                    if vector == 'symlink': path.symlink_to(other_path)
                    else: os.link(other_path, path)
                with patch('shared_content.storage.os.unlink', wraps=os.unlink) as unlink:
                    self.refuse_unlink(descriptor)
                self.assertEqual(unlink.call_count, 0)
                self.assertTrue(path.is_symlink() if vector == 'symlink' else path.is_file())
                self.assertEqual(path.read_bytes(), before if vector == 'wrong-sha' else b'LC-UNRELATED-VICTIM')
                self.assertEqual(other_path.read_bytes(), b'LC-UNRELATED-VICTIM')

    def test_lc006_inode_replacement_after_real_hash_read_does_not_unlink_either_file(self):
        descriptor = self.store.write_new('LC-HELD-ORIGINAL')
        path = self.store.root / descriptor['file_key']
        retained = path.with_name('own-retained-original')
        identity = path.stat()
        original, hits = os.read, []
        def replace_after_eof(fd, size):
            value = original(fd, size)
            info = os.fstat(fd)
            if not value and not hits and (info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino):
                hits.append('target-eof')
                path.rename(retained)
                path.write_bytes(b'LC-NEW-NAMED-VICTIM'); path.chmod(0o600)
            return value
        with patch('shared_content.storage.os.read', side_effect=replace_after_eof), \
             patch('shared_content.storage.os.unlink', wraps=os.unlink) as unlink:
            self.refuse_unlink(descriptor)
        self.assertEqual(hits, ['target-eof'])
        self.assertEqual(unlink.call_count, 0)
        self.assertEqual(retained.read_bytes(), b'LC-HELD-ORIGINAL')
        self.assertEqual(path.read_bytes(), b'LC-NEW-NAMED-VICTIM')

    def test_lc006_parent_rename_after_real_hash_read_preserves_held_and_replacement_leaves(self):
        descriptor = self.store.write_new('LC-HELD-PARENT-VICTIM')
        path = self.store.root / descriptor['file_key']
        parent = path.parent
        retained = parent.with_name(parent.name + '-own-retained')
        identity = path.stat()
        original, hits = os.read, []
        def rename_after_eof(fd, size):
            value = original(fd, size)
            info = os.fstat(fd)
            if not value and not hits and (info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino):
                hits.append('target-eof')
                parent.rename(retained)
                parent.mkdir(mode=0o700)
                path.write_bytes(b'LC-NEW-PARENT-VICTIM'); path.chmod(0o600)
            return value
        with patch('shared_content.storage.os.read', side_effect=rename_after_eof), \
             patch('shared_content.storage.os.unlink', wraps=os.unlink) as unlink:
            self.refuse_unlink(descriptor)
        self.assertEqual(hits, ['target-eof'])
        self.assertEqual(unlink.call_count, 0)
        self.assertEqual((retained / path.name).read_bytes(), b'LC-HELD-PARENT-VICTIM')
        self.assertEqual(path.read_bytes(), b'LC-NEW-PARENT-VICTIM')
        # The deliberately renamed tree stays intact; no scanner-health claim.


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedCleanupTests(R.ReservationFixture, TransactionTestCase):
    def cleanup_url(self, target, kind='header'):
        return '/manage/shared/%s/cleanup/%s/' % (kind, target)

    def job_url(self, operation, *, resume=False, kind='header'):
        return '/manage/shared/%s/cleanup/jobs/%s/%s' % (kind, operation, 'resume/' if resume else '')

    def old_version(self, kind='header'):
        value, first = self.apply_text(kind, 'LC07-OLD-' + kind)
        self.apply_text(kind, 'LC07-CURRENT-' + kind)
        return SharedRevision.objects.get(pk=first['resultId']), value

    def preview(self, target, *, kind='header', client=None):
        response = (client or self.owner_client).get(self.cleanup_url(target, kind))
        self.assertEqual(response.status_code, 200, 'LC_VALID_PREVIEW_REFUSED')
        self.assertIn('no-store', response.get('Cache-Control', ''))
        return response.context['preview']

    def form(self, preview, operation=None, *, password=OWNER_PASSWORD, client=None):
        client = client or self.owner_client
        return {'csrfmiddlewaretoken': client.cookies[settings.CSRF_COOKIE_NAME].value,
            'confirmation': preview['confirmationToken'], 'operationId': str(operation or uuid4()),
            'password': password, 'confirmed': 'yes'}

    def confirm(self, row, preview, operation=None, **kwargs):
        client = kwargs.pop('client', self.owner_client)
        return client.post(self.cleanup_url(row.pk, row.block.kind),
                           data=self.form(preview, operation, client=client, **kwargs))

    def resume(self, operation, kind='header', password=OWNER_PASSWORD):
        shown = self.owner_client.get(self.job_url(operation, kind=kind))
        self.assertEqual(shown.status_code, 200)
        return self.owner_client.post(self.job_url(operation, resume=True, kind=kind),
                                     data=self.form(shown.context['preview'], operation, password=password))

    def assert_complete(self, response, row, *, file_deleted=True):
        self.assertEqual(response.status_code, 200)
        state = response.context['state']
        self.assertEqual((state['targetId'], state['phase'], state['historyDeleted'],
                          state['fileDeleted'], state['complete']),
                         (str(row.pk), 'complete', True, file_deleted, True))
        self.assertFalse(SharedRevision.objects.filter(pk=row.pk).exists())
        self.assertTrue(SharedIdentityReservation.objects.filter(pk=row.pk, block=row.block).exists())
        self.within_cap()
        return state

    def test_lc001_preview_permissions_csrf_password_and_projection_without_mutation(self):
        with self.candidate():
            row, _ = self.old_version()
            before, fs = self.state(), SharedStorage().inventory()
            preview = self.preview(row.pk)
            self.assertEqual((preview['targetId'], preview['sequence'], preview['authorId'],
                              preview['byteSize'], preview['fileKey'], preview['reasons']),
                             (str(row.pk), row.sequence, row.author_id, row.byte_size, row.file_key, []))
            self.assertTrue(preview['canConfirm'])
            for client in (self.employee_client, self.visitor):
                self.assertNotEqual(client.get(self.cleanup_url(row.pk)).status_code, 200)
                denied = client.post(self.cleanup_url(row.pk), data=self.form(preview))
                self.assertIn(denied.status_code, (401, 403))
            bad_csrf = self.form(preview); bad_csrf['csrfmiddlewaretoken'] = 'x' * 64
            self.assertEqual(self.owner_client.post(self.cleanup_url(row.pk), data=bad_csrf).status_code, 403)
            self.assertEqual(self.confirm(row, preview, password='LC07-WRONG-PASSWORD').status_code, 403)
            forged = dict(preview, confirmationToken=preview['confirmationToken'] + 'x')
            self.assertEqual(self.confirm(row, forged).status_code, 409)
            self.assertEqual(self.state(), before)
            self.assertEqual(SharedStorage().inventory(), fs)

    def test_lc002_every_stage_status_current_draft_and_pin_are_protected(self):
        with self.candidate():
            old, _ = self.old_version()
            current = SharedBlock.objects.get(kind='header').current_revision_id
            self.assertIn('CURRENT', self.preview(current)['reasons'])
            draft = SharedDraft.objects.create(block=old.block, base_revision=old,
                html='legacy draft', payload_hash=hashlib.sha256(b'legacy draft').hexdigest(), author_id=self.owner.pk)
            self.assertIn('DRAFT_BASE', self.preview(old.pk)['reasons'])
            from .commands import raw
            raw(SharedDraft).filter(pk=draft.pk).delete()
            pin = SharedBasePin.objects.create(revision=old, holder_kind='lc-fixture', holder_id=uuid4())
            self.assertIn('PINNED', self.preview(old.pk)['reasons'])
            raw(SharedBasePin).filter(pk=pin.pk).delete()
            for status in ('held', 'consumed', 'released', 'invalidated'):
                with self.subTest(status=status):
                    stage = SharedRestoreStage.objects.create(block=old.block, actor_id=self.owner.pk,
                        actor_generation=1, source_revision=old, base_revision=old,
                        schema_version='header-v1', policy_version='shared-policy-v1', status=status)
                    before, fs = self.state(), SharedStorage().inventory()
                    preview = self.preview(old.pk)
                    self.assertIn('RESTORE_STAGE', preview['reasons'])
                    self.assertFalse(preview['canConfirm'])
                    self.assertEqual(self.confirm(old, preview).status_code, 409)
                    self.assertEqual(self.state(), before)
                    self.assertEqual(SharedStorage().inventory(), fs)
                    self.assertTrue(SharedRestoreStage.objects.filter(pk=stage.pk, status=status).exists())
                    raw(SharedRestoreStage).filter(pk=stage.pk).delete()

    def test_lc003_new_pin_after_preview_invalidates_confirmation_and_keeps_input(self):
        with self.candidate():
            row, _ = self.old_version()
            preview = self.preview(row.pk)
            SharedBasePin.objects.create(revision=row, holder_kind='lc-new-protection', holder_id=uuid4())
            before, fs = self.state(), SharedStorage().inventory()
            form = self.form(preview)
            original = dict(form)
            response = self.owner_client.post(self.cleanup_url(row.pk), data=form)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(form, original)  # Framework request data, not browser RAM proof.
            self.assertEqual(self.state(), before)
            self.assertEqual(SharedStorage().inventory(), fs)

    def test_lc002_legacy_unsupported_schema_and_unknown_protection_are_not_cleanup_candidates(self):
        with self.candidate():
            row, _ = self.old_version()
            inline = SharedRevision.objects.create(block=row.block, sequence=20, schema_version='header-v1',
                html='LC-LEGACY-INLINE', payload_hash=hashlib.sha256(b'LC-LEGACY-INLINE').hexdigest(), author_id=self.owner.pk)
            descriptor = SharedStorage().write_new('LC-UNSUPPORTED-SCHEMA')
            unsupported = SharedRevision.objects.create(block=row.block, sequence=21, schema_version='header-future',
                html='', payload_hash=descriptor['file_sha256'], author_id=self.owner.pk, **descriptor)
            AssetUsage.objects.create(asset=self.asset, kind=AssetUsage.Kind.RETAINED_HTML,
                                      consumer_id=row.pk, slot='lc-unknown-protection')
            for target, reason in ((inline, 'LEGACY_INLINE'), (unsupported, 'UNSUPPORTED_SCHEMA'),
                                   (row, 'UNKNOWN_PROTECTION')):
                with self.subTest(reason=reason):
                    before, fs = self.state(), SharedStorage().inventory()
                    preview = self.preview(target.pk)
                    self.assertIn(reason, preview['reasons'])
                    self.assertFalse(preview['canConfirm'])
                    self.assertEqual(self.confirm(target, preview).status_code, 409)
                    self.assertEqual(self.state(), before)
                    self.assertEqual(SharedStorage().inventory(), fs)

    def test_lc004_one_delete_preserves_other_refs_receipts_and_replay_gone_retired_key(self):
        from . import lifecycle
        with self.candidate():
            row, old_save = self.old_version()
            self.apply_text('footer', 'LC-OTHER-BLOCK')
            current = SharedBlock.objects.get(kind='header').current_revision_id
            other_rows = dict(SharedRevision.objects.exclude(pk=row.pk).values_list('pk', 'payload_hash'))
            receipts = list(SharedReceipt.objects.order_by('pk').values())
            preview, operation = self.preview(row.pk), uuid4()
            result = self.assert_complete(self.confirm(row, preview, operation), row)
            self.assertFalse((SharedStorage().root / row.file_key).exists())
            self.assertEqual(SharedBlock.objects.get(kind='header').current_revision_id, current)
            self.assertEqual(dict(SharedRevision.objects.values_list('pk', 'payload_hash')), other_rows)
            self.assertEqual(list(SharedReceipt.objects.order_by('pk').values()), receipts)
            self.assertFalse(AssetUsage.objects.filter(consumer_id=row.pk).exists())
            for file in self.asset.files.all():
                self.assertEqual(MediaStorage().manifest(file.key), self.files_before[str(file.pk)])
            replay = self.send('header', 'apply', old_save)
            self.assertEqual(replay.status_code, 200)
            self.assertTrue(replay.json()['gone'])
            self.assertTrue(replay.json()['replay'])
            # A producer UUID collision must not reuse the retired closed key.
            value = self.intent('header', self.fixture('header', 'LC-RETIRED-COLLISION'))
            identity = UUID(Path(row.file_key).stem)
            with patch.object(lifecycle, 'uuid4', return_value=identity) as collision:
                denied = self.send('header', 'apply', value)
            self.assertEqual(collision.call_count, 1)
            self.assertNotEqual(denied.status_code, 200)
            self.assertFalse((SharedStorage().root / row.file_key).exists())
            self.assertEqual(SharedCleanupJob.objects.get(pk=operation).target_id, row.pk)
            self.assertEqual(result['operationId'], str(operation))

    def test_lc005_exact_confirm_replay_and_changed_target_do_not_delete_next_version(self):
        with self.candidate():
            row, _ = self.old_version()
            preview, operation = self.preview(row.pk), uuid4()
            self.assert_complete(self.confirm(row, preview, operation), row)
            before, fs = self.state(), SharedStorage().inventory()
            self.assert_complete(self.confirm(row, preview, operation), row)
            current = SharedRevision.objects.get(pk=SharedBlock.objects.get(kind='header').current_revision_id)
            self.assertEqual(self.confirm(current, preview, operation).status_code, 409)
            self.assertEqual(self.state(), before)
            self.assertEqual(SharedStorage().inventory(), fs)
            self.assertEqual(SharedCleanupJob.objects.count(), 1)

    def test_lc006_real_unlink_failure_preserves_partial_job_then_same_job_resume(self):
        from . import storage
        with self.candidate():
            row, _ = self.old_version()
            preview, operation = self.preview(row.pk), uuid4()
            original, hits = storage.os.unlink, []
            def fail(path, *args, **kwargs):
                if path == Path(row.file_key).name:
                    hits.append(path)
                    self.assertFalse(connection.in_atomic_block)
                    raise OSError(errno.EIO, 'LC_TEST_UNLINK_FAILURE')
                return original(path, *args, **kwargs)
            with patch('shared_content.storage.os.unlink', side_effect=fail):
                partial = self.confirm(row, preview, operation)
            self.assertEqual(hits, [Path(row.file_key).name])
            self.assertEqual(partial.status_code, 200)
            self.assertEqual(partial.context['state']['phase'], 'metadata_deleted')
            self.assertFalse(partial.context['state']['complete'])
            self.assertFalse(partial.context['state']['fileDeleted'])
            job = SharedCleanupJob.objects.get(pk=operation)
            self.assertEqual((job.file_key, job.file_sha256, job.byte_size),
                             (row.file_key, row.file_sha256, row.byte_size))
            self.assertFalse(SharedRevision.objects.filter(pk=row.pk).exists())
            inventory = SharedStorage().inventory()
            self.assertTrue(any(item['key'] == row.file_key for item in inventory['files']))
            self.assertGreaterEqual(inventory['orphanCount'], 1)
            self.assert_complete(self.resume(operation), row)
            self.assertEqual(SharedCleanupJob.objects.count(), 1)

    def test_lc005_two_actual_connections_one_job_then_manual_exact_retry(self):
        from . import lifecycle
        with self.candidate():
            row, _ = self.old_version()
            second = self.login(self.owner.username, OWNER_PASSWORD)
            first_preview = self.preview(row.pk)
            second_preview = self.preview(row.pk, client=second)
            operation, reached, release = uuid4(), threading.Event(), threading.Event()
            result, errors = {}, []
            def hold(phase):
                if phase == 'job_durable':
                    reached.set()
                    if not release.wait(10): raise RuntimeError('LC_TEST_BARRIER_EXPIRED')
            def writer():
                try:
                    with self.candidate():
                        with connection.cursor() as cursor:
                            cursor.execute('SELECT pg_backend_pid()'); result['pid'] = cursor.fetchone()[0]
                        result['response'] = self.confirm(row, first_preview, operation)
                except Exception as error:
                    errors.append(type(error).__name__)
                finally:
                    connections.close_all()
            thread = threading.Thread(target=writer, name='lc-owner-confirm')
            with patch.object(lifecycle, '_fault_boundary', side_effect=hold):
                thread.start()
                try:
                    self.assertTrue(reached.wait(10), 'LC_REAL_JOB_BOUNDARY_NOT_REACHED')
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_backend_pid()'); parent_pid = cursor.fetchone()[0]
                    self.assertNotEqual(result['pid'], parent_pid)
                    denied = self.confirm(row, second_preview, operation, client=second)
                    self.assertIn(denied.status_code, (409, 503))
                    self.assertEqual(SharedCleanupJob.objects.filter(pk=operation).count(), 1)
                finally:
                    release.set(); thread.join(timeout=20)
            self.assertFalse(thread.is_alive(), 'LC_THREAD_NOT_REAPED')
            self.assertEqual(errors, [])
            self.assert_complete(result['response'], row)
            before, fs = self.state(), SharedStorage().inventory()
            self.assert_complete(self.confirm(row, second_preview, operation, client=second), row)
            self.assertEqual(SharedCleanupJob.objects.count(), 1)
            self.assertEqual(self.state(), before)
            self.assertEqual(SharedStorage().inventory(), fs)

    def test_lc006_shared_file_retained_if_another_verified_revision_still_references_it(self):
        from media_library.services import attach
        with self.candidate():
            row, _ = self.old_version()
            copy = SharedRevision.objects.create(block=row.block, sequence=10, schema_version=row.schema_version,
                html='', payload_hash=row.payload_hash, author_id=self.owner.pk, storage_kind='file',
                file_key=row.file_key, byte_size=row.byte_size, file_sha256=row.file_sha256)
            attach(kind='shared_block', consumer_id=copy.pk, slot='shared:header:brand', asset_id=self.asset.pk)
            before = self.body(copy)
            self.assert_complete(self.confirm(row, self.preview(row.pk)), row, file_deleted=False)
            self.assertEqual(self.body(SharedRevision.objects.get(pk=copy.pk)), before)

    def test_lc005_password_recovery_requires_new_session_and_fresh_job_confirmation(self):
        from accounts.services import recover_owner
        with self.candidate():
            row, _ = self.old_version()
            operation = uuid4()
            with patch.object(SharedStorage, 'unlink_verified', side_effect=OSError(errno.EIO, 'LC_PARTIAL')):
                partial = self.confirm(row, self.preview(row.pk), operation)
            self.assertEqual(partial.context['state']['phase'], 'metadata_deleted')
            prior = self.owner_client.get(self.job_url(operation)).context['preview']
            old_form = self.form(prior, operation)
            new_password = 'LC07-new-synthetic-owner-password'
            recover_owner(new_password)  # Only this isolated fixture owner's sessions.
            self.assertNotEqual(self.owner_client.post(self.job_url(operation, resume=True), data=old_form).status_code, 200)
            self.owner_client = self.login(self.owner.username, new_password)
            before, fs = self.state(), SharedStorage().inventory()
            stale = self.form(prior, operation, password=new_password)
            self.assertEqual(self.owner_client.post(self.job_url(operation, resume=True), data=stale).status_code, 409)
            self.assertEqual(self.state(), before)
            self.assertEqual(SharedStorage().inventory(), fs)
            self.assert_complete(self.resume(operation, password=new_password), row)

    def run_crashing_process(self, row, preview, operation, phase):
        data = {'root': self.temp.name, 'actor': self.owner.pk, 'session': self.owner_client.session.session_key,
            'target': str(row.pk), 'operation': str(operation), 'token': preview['confirmationToken'],
            'password': OWNER_PASSWORD, 'phase': phase}
        script = '''import json,os,sys
import django
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from shared_content.profiles import calibration_scope
from shared_content import lifecycle as L
data=json.load(sys.stdin)
settings.MEDIA_LIBRARY_ROOT=data['root']
actor=get_user_model().objects.get(pk=data['actor'])
def crash(phase):
    if phase==data['phase']: os._exit(79)
L._fault_boundary=crash
with override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']), calibration_scope():
    L.confirm(actor=actor,kind='header',generation=1,session_key=data['session'],
        operation_id=data['operation'],target_id=data['target'],
        confirmation_token=data['token'],password=data['password'])
sys.exit(80)
'''
        child = subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy())
        try:
            stdout, stderr = child.communicate(json.dumps(data).encode(), timeout=25)
        except subprocess.TimeoutExpired:
            child.kill(); child.communicate(timeout=5)
            self.fail('LC_PROCESS_DID_NOT_EXIT_WITHIN_BOUND')
        finally:
            if child.poll() is None:
                child.kill(); child.wait(timeout=5)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None: stream.close()
        self.assertEqual(child.returncode, 79, 'LC_REAL_PROCESS_BOUNDARY_NOT_REACHED')
        self.assertEqual(stdout, b'')
        self.assertEqual(stderr, b'')

    def test_lc007_actual_process_exit_after_metadata_commit_then_http_resume(self):
        with self.candidate():
            row, _ = self.old_version()
            operation = uuid4()
            self.run_crashing_process(row, self.preview(row.pk), operation, 'metadata_deleted')
            self.assertEqual(SharedCleanupJob.objects.get(pk=operation).phase, 'metadata_deleted')
            self.assertFalse(SharedRevision.objects.filter(pk=row.pk).exists())
            self.assertTrue((SharedStorage().root / row.file_key).exists())
            self.assert_complete(self.resume(operation), row)

    def test_lc007_actual_process_exit_after_unlink_then_missing_expected_file_resume(self):
        with self.candidate():
            row, _ = self.old_version()
            operation = uuid4()
            self.run_crashing_process(row, self.preview(row.pk), operation, 'file_unlinked')
            self.assertEqual(SharedCleanupJob.objects.get(pk=operation).phase, 'metadata_deleted')
            self.assertFalse((SharedStorage().root / row.file_key).exists())
            self.assert_complete(self.resume(operation), row)

    def test_lc010_historical_known_book_reconciles_but_missing_receipt_stays_held(self):
        from .journal import SharedJournal
        with self.candidate():
            row, _ = self.old_version()
            operation = uuid4()
            book = {'bookSchema': 'shared-held-book-v1', 'profileId': 'shared-local-v1',
                'operationId': str(operation), 'blockId': str(row.block_id), 'action': 'apply',
                'actorId': self.owner.pk, 'generation': 1, 'inputFingerprint': 'a' * 64,
                'sourceStamp': 'b' * 64, 'reservedBytes': 4194304, 'snapshotIncrement': 1}
            record = SharedJournal().create_or_replay(book)
            SharedReceipt.objects.create(id=operation, action='apply', actor_id=self.owner.pk,
                actor_generation=1, block=row.block, fingerprint=book['inputFingerprint'], result_code='applied',
                result_id=row.pk, source_stamp=book['sourceStamp'], reservation_profile=book['profileId'],
                reservation_book_sha256=record['sha256'])
            url = '/manage/shared/header/diagnostics/%s/' % operation
            before = self.state()
            diagnostic = self.owner_client.get(url)
            self.assertEqual(diagnostic.status_code, 200)
            self.assertTrue(diagnostic.context['diagnostic']['reconcileAvailable'])
            self.assertEqual(self.state(), before)
            result = self.owner_client.post(url + 'reconcile/', data={
                'csrfmiddlewaretoken': self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value,
                'password': OWNER_PASSWORD, 'confirmed': 'yes'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(SharedStorage().inventory()['journalCount'], 0)
            self.assertEqual(self.state(), before)
            unknown = uuid4(); book['operationId'] = str(unknown)
            SharedJournal().create_or_replay(book)
            state, fs = self.state(), SharedStorage().inventory()
            diagnostic = self.owner_client.get('/manage/shared/header/diagnostics/%s/' % unknown)
            self.assertEqual(diagnostic.status_code, 200)
            value = diagnostic.context['diagnostic']
            self.assertFalse(value['reconcileAvailable'])
            self.assertIsNone(value['receipt'])
            self.assertEqual(value['bookState'], 'verified')
            self.assertEqual(self.state(), state)
            self.assertEqual(SharedStorage().inventory(), fs)


@skipUnless(os.environ.get('ESTAKADA_RUN_SHARED_CALIBRATION') == '1',
            'Lifecycle maintenance calibration requires the dedicated existing-volume suite')
@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedCleanupCalibrationTests(R.ReservationFixture, TransactionTestCase):
    # Explicit helper reuse avoids collecting the functional tests twice.
    cleanup_url = SharedCleanupTests.cleanup_url
    job_url = SharedCleanupTests.job_url
    preview = SharedCleanupTests.preview
    form = SharedCleanupTests.form
    confirm = SharedCleanupTests.confirm
    assert_complete = SharedCleanupTests.assert_complete

    def test_lc008_actual_save_refused_but_large_and_small_cleanup_fit_maintenance_reserve(self):
        from . import test_shared_calibration as finite
        from .quota import measure, admission_requirement
        max_html = finite.SharedCalibrationTests.max_html.__get__(self)
        # Reuse the same bounded measured filling implementation, not a budget override.
        self.max_html = max_html
        self.assert_large_guard = finite.SharedCalibrationTests.assert_large_guard.__get__(self)
        fill_to = finite.SharedCalibrationTests.fill_to.__get__(self)
        with self.candidate() as evidence:
            result = self.applied('header', 'apply', self.intent('header', max_html('header', label='LC-MAX-OLD')))
            large = SharedRevision.objects.get(pk=result['resultId'])
            self.apply_text('header', 'LC-MAX-CURRENT')
            _, result = self.apply_text('footer', 'LC-SMALL-OLD')
            small = SharedRevision.objects.get(pk=result['resultId'])
            self.apply_text('footer', 'LC-SMALL-CURRENT')
            self.assertEqual(large.byte_size, 1048576)
            self.assertLess(small.byte_size, 4096)
            fill_to(268435456 - 4 * 1048576)
            before = measure()
            quote = admission_requirement(before, 4)
            self.assertLess(268435456 - before['usedBytes'], quote['requiredBytes'])
            self.assertGreater(268435456 - before['usedBytes'],
                               before['maintenanceReserveBytes'] + 131072)
            value = self.intent('header', self.fixture('header', 'LC-NO-SAVE-CAPACITY'))
            state, fs = self.state(), SharedStorage().inventory()
            denied = self.send('header', 'apply', value)
            self.assertEqual(denied.status_code, 409)
            self.assertTrue(denied.json()['operationNotStarted'])
            self.assertEqual(self.state(), state)
            self.assertEqual(SharedStorage().inventory(), fs)
            for row in (large, small):
                self.assert_complete(self.confirm(row, self.preview(row.pk, kind=row.block.kind)), row)
                self.within_cap()
            measured = measure()
            self.assertEqual(SharedCleanupJob.objects.filter(phase='complete').count(), 2)
            self.assertTrue(any(event['phase'] == 'cleanup_complete' for event in evidence['events']))
            self.assertGreater(measured['actualPgBytes'], 0)
            self.report('LC07-MAINTENANCE-REAL-SAVE-REFUSAL-LARGE-SMALL-CLEANUP', evidence)
