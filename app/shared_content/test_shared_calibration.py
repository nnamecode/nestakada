"""Finite RC calibration, explicitly unvetted; dedicated existing state volume."""
import hashlib
import os
from pathlib import Path
import random
import threading
from unittest import skipUnless
from unittest.mock import patch
from uuid import UUID, uuid4

from django.conf import settings
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from . import test_shared_reservation as R


@skipUnless(os.environ.get('ESTAKADA_RUN_SHARED_CALIBRATION') == '1',
            'Finite large calibration runs only in its dedicated runner suite')
@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedCalibrationTests(R.ReservationFixture, TransactionTestCase):
    def max_html(self, kind, *, label='MAX', noisy=False, seed=1):
        from .policy import normalize_html
        marker = 'CALIBRATION_CONTENT_TOKEN'
        template = normalize_html(self.fixture(kind, marker), kind)['html']
        remaining = 1048576 - len(template.encode()) + len(marker) - len(label)
        if noisy:
            text = ''.join(random.Random(seed).choices(
                'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/', k=remaining))
        else:
            text = '🚀' * (remaining // 4) + 'A' * (remaining % 4)
        result = template.replace(marker, label + text)
        self.assertEqual(len(result.encode()), 1048576, 'CALIBRATION_MAX_FIXTURE_NOT_EXACT')
        return result

    def test_calibration_exact_mebibyte_both_blocks_and_32_real_draft_updates(self):
        from .models import SharedDraft, SharedRevision
        with self.candidate() as evidence:
            for kind in ('header', 'footer'):
                html = self.max_html(kind, label='MAX-' + kind)
                result = self.applied(kind, 'apply', self.intent(kind, html))
                row = SharedRevision.objects.get(pk=result['resultId'])
                self.assertTrue(hashlib.sha256(self.body(row).encode()).hexdigest() == hashlib.sha256(html.encode()).hexdigest(),
                                'CALIBRATION_MAX_BODY_CHANGED')
            context = self.context('header')
            identity = None
            for index in range(32):
                html = self.max_html('header', label='WARM-%02d' % index)
                result = self.applied('header', 'draft', self.intent('header', html, context=context))
                identity = result['resultId'] if identity is None else identity
                self.assertEqual(result['resultId'], identity)
                context = result['editorContext']
                self.assertEqual(context['draftBasis']['revision'], index + 1)
            self.assertEqual(SharedDraft.objects.count(), 1)
            self.assertEqual(SharedDraft.objects.get(pk=identity).revision, 32)
            self.report('FINITE_MAX_1MIB_AND_WARM32', evidence)

    def assert_large_guard(self):
        from .quota import measure
        from .storage import SharedStorage
        inventory = SharedStorage().inventory()
        actual = inventory['actualAllocatedBytes']
        # Cumulative across fill calls: reserve three worker fixture files and
        # the next blob, rather than treating each loop as a fresh allowance.
        self.assertLessEqual(inventory['blobCount'] + inventory['journalCount'] + 3 + 1,
                             512, 'CALIBRATION_CUMULATIVE_FILE_GUARD')
        self.assertLessEqual(actual, 384 * 1024 * 1024, 'CALIBRATION_OWN_FS_GUARD')
        self.assertLessEqual(measure()['usedBytes'], 384 * 1024 * 1024,
                             'CALIBRATION_ACCOUNTED_GUARD')

    def fill_to(self, target):
        from django.db.models import Max
        from media_library.services import attach
        from .models import SharedBlock, SharedRevision
        from .quota import measure
        from .storage import SharedStorage
        stat = os.statvfs(self.temp.name)
        self.assertGreaterEqual(stat.f_bavail * stat.f_frsize, 512 * 1024 * 1024,
                                'CALIBRATION_REQUIRES_512MIB_FREE')
        store = SharedStorage()
        block = SharedBlock.objects.get(kind='footer')
        count = 0
        while measure()['usedBytes'] < target:
            self.assertLess(count, 512, 'CALIBRATION_FILL_FILE_BOUND')
            self.assert_large_guard()
            html = self.max_html('footer', label='FILL-%04d' % count, noisy=True, seed=count + 19)
            descriptor = store.write_new(html)
            sequence = (SharedRevision.objects.filter(block=block).aggregate(value=Max('sequence'))['value'] or 0) + 1
            row = SharedRevision.objects.create(block=block, sequence=sequence, schema_version='footer-v1',
                html='', payload_hash=descriptor['file_sha256'], author_id=self.owner.pk, **descriptor)
            # Explicit historical fixture preparation, never a product Apply.
            attach(kind='shared_block', consumer_id=row.pk, slot='shared:footer:brand', asset_id=self.asset.pk)
            count += 1
            self.assert_large_guard()
        return measure()

    def padding_to_old_admission_edge(self, new_refs):
        from .quota import measure, admission_requirement
        from .storage import SharedStorage
        store, padding = SharedStorage(), []
        def add(size):
            self.assert_large_guard()
            self.assertLess(len(padding), 512, 'EDGE_PADDING_FILE_BOUND')
            identity = UUID('ee' + format(len(padding), '030x'))
            data = ''.join(random.Random(8000 + len(padding)).choices(
                'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/', k=size))
            descriptor = store.write_new(data, blob_id=identity)
            info = (store.root / descriptor['file_key']).lstat()
            padding.append((descriptor, info.st_dev, info.st_ino))
            self.assert_large_guard()
        # Reuse one known fanout; these are explicit unreferenced test padding,
        # not historical bodies or permission to delete product orphans.
        add(0)
        for _ in range(512):
            value = measure()
            quote = admission_requirement(value, new_refs)
            old_required = (quote['prospectiveUsageDeltaBytes'] + quote['coreGrowthHeadroomBytes']
                            + quote['reserveBytes'])
            remaining = 268435456 - value['usedBytes']
            if remaining <= old_required + 128 * 1024:
                self.assertGreater(remaining, old_required, 'EDGE_PADDING_OVERSHOT_OLD_BOUNDARY')
                self.assertLess(remaining, quote['requiredBytes'])
                return padding, value, quote
            needed = remaining - (old_required + 64 * 1024)
            add(max(4096, min(1048576, needed - 16 * 1024)))
        self.fail('EDGE_PADDING_DID_NOT_REACH_FINITE_TARGET')

    def release_only_own_padding_for_required_space(self, padding, new_refs):
        from .models import SharedRevision, SharedDraft
        from .quota import measure, admission_requirement
        from .storage import SharedStorage
        store = SharedStorage()
        while True:
            value = measure()
            quote = admission_requirement(value, new_refs)
            if 268435456 - value['usedBytes'] >= quote['requiredBytes'] + 64 * 1024:
                return value, quote
            self.assertTrue(bool(padding), 'OWN_PADDING_INSUFFICIENT_FOR_EDGE_RECOVERY')
            descriptor, expected_dev, expected_inode = padding.pop()
            key = descriptor['file_key']
            self.assertFalse(SharedRevision.objects.filter(file_key=key).exists())
            self.assertFalse(SharedDraft.objects.filter(file_key=key).exists())
            self.assertEqual(hashlib.sha256(store.read(descriptor).encode()).hexdigest(), descriptor['file_sha256'])
            with store._parent(key) as (parent, leaf):
                actual = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                self.assertEqual((actual.st_dev, actual.st_ino, actual.st_uid, actual.st_nlink),
                                 (expected_dev, expected_inode, os.geteuid(), 1))
                os.unlink(leaf, dir_fd=parent)
                os.fsync(parent)

    def test_calibration_actual_75percent_positive_and_insufficient_space_whole_refusal(self):
        from .models import SharedRevision, SharedDraft, SharedBudget, SharedReceipt
        from .storage import SharedStorage
        with self.candidate() as evidence:
            _, header = self.apply_text('header', 'HEADER-BASE')
            _, footer = self.apply_text('footer', 'FOOTER-BASE')
            for kind in ('header', 'footer'):
                self.applied(kind, 'draft', self.intent(kind, self.fixture(kind, 'PROTECTED-DRAFT-' + kind)))
            warning = self.fill_to(268435456 * 78 // 100)
            self.assertGreaterEqual(warning['usedBytes'], 201326592)
            self.assertLess(warning['usedBytes'], 268435456 * 9 // 10)
            self.assertTrue(warning['warning'])
            before_hashes = dict(SharedRevision.objects.values_list('pk', 'payload_hash'))
            for kind in ('header', 'footer'):
                shown = self.owner_client.get(self.path(kind))
                self.assertEqual(shown.status_code, 200)
                self.assertContains(shown, 'История занимает не менее 75% бюджета.')
                self.apply_text(kind, 'WARNING-VALID-' + kind)
            self.assertEqual(dict(SharedRevision.objects.filter(pk__in=list(before_hashes)).values_list('pk', 'payload_hash')),
                             before_hashes, 'WARNING_PRUNED_OR_CHANGED_HISTORY')
            # LC07/RSV-009: pre-maintenance admission would admit, but it
            # leaves no tested allowance for the owner cleanup protocol.
            from .quota import measure, admission_requirement
            padding, edge, quote = self.padding_to_old_admission_edge(new_refs=4)
            remaining = 268435456 - edge['usedBytes']
            self.assertGreater(remaining, quote['prospectiveUsageDeltaBytes']
                               + quote['coreGrowthHeadroomBytes'] + quote['reserveBytes'])
            self.assertLess(remaining, quote['requiredBytes'])
            self.assertEqual(quote['coreGrowthHeadroomBytes'], evidence['parameters']['core_growth_headroom'])
            maximum = self.max_html('header', label='RSV009-EDGE-MAX')
            edge_value = self.intent('header', maximum)
            edge_db, edge_fs = self.state(), SharedStorage().inventory()
            edge_budget = SharedBudget.objects.get()
            event_start = len(evidence['events'])
            edge_denial = self.send('header', 'apply', edge_value)
            self.assertEqual(edge_denial.status_code, 409)
            self.assertEqual(edge_denial.json()['code'], 'SHARED_HISTORY_BYTES_FULL')
            self.assertTrue(edge_denial.json()['operationNotStarted'])
            admissions = [entry['measurement'] for entry in evidence['events'][event_start:]
                          if entry['phase'] == 'reservation_admission']
            self.assertEqual(len(admissions), 1)
            admitted = admissions[0]
            self.assertGreater(268435456 - admitted['usedBytes'],
                               admitted['prospectiveUsageDeltaBytes'] + admitted['coreGrowthHeadroomBytes']
                               + admitted['reserveBytes'])
            self.assertLess(268435456 - admitted['usedBytes'], admitted['requiredBytes'])
            self.assertFalse(SharedReceipt.objects.filter(pk=edge_value['operationId']).exists())
            edge_after = SharedBudget.objects.get()
            self.assertEqual((edge_after.retained_debt_bytes, edge_after.accounting_version),
                             (edge_budget.retained_debt_bytes, edge_budget.accounting_version))
            self.assertNotEqual(edge_after.accounting_version, 'faulted')
            self.assertEqual(self.state(), edge_db)
            self.assertEqual(SharedStorage().inventory(), edge_fs)
            self.release_only_own_padding_for_required_space(padding, new_refs=4)
            available = measure()
            required = admission_requirement(available, new_refs=4)
            self.assertGreaterEqual(268435456 - available['usedBytes'], required['requiredBytes'] + 64 * 1024)
            # Same untouched pre-book intent can now succeed; no nonce/body
            # rewrite, fabricated budget or deleted historical snapshot.
            edge_success = self.applied('header', 'apply', edge_value)
            edge_row = SharedRevision.objects.get(pk=edge_success['resultId'])
            self.assertEqual(edge_row.byte_size, 1048576)
            self.assertTrue(hashlib.sha256(self.body(edge_row).encode()).hexdigest() == hashlib.sha256(maximum.encode()).hexdigest())
            self.within_cap()
            reserve = evidence['parameters']['reserve_bytes']
            near = self.fill_to(268435456 - reserve + 1)
            self.assertLessEqual(near['usedBytes'], 268435456, 'FIXTURE_OVERSHOT_PRODUCT_CAP')
            self.assertGreater(near['usedBytes'] + reserve, 268435456)
            value = self.intent('header', self.fixture('header', 'NO-ROOM-INPUT'))
            before_db, before_fs = self.state(), SharedStorage().inventory()
            debt = SharedBudget.objects.get().retained_debt_bytes
            refused = self.send('header', 'apply', value)
            self.assertEqual(refused.status_code, 409)
            self.assertEqual(refused.json()['code'], 'SHARED_HISTORY_BYTES_FULL')
            self.assertFalse(SharedReceipt.objects.filter(pk=value['operationId']).exists())
            restore_op = str(uuid4())
            refused_restore = self.send('footer', 'restore/prepare', {'protocol': 'shared-editor-v1',
                'generation': 1, 'baseRevisionId': self.context('footer')['baseRevisionId'],
                'sourceRevisionId': footer['resultId'], 'operationId': restore_op, 'confirmReplace': True},
                context=self.context('footer'))
            self.assertEqual(refused_restore.status_code, 409)
            self.assertEqual(refused_restore.json()['code'], 'SHARED_HISTORY_BYTES_FULL')
            self.assertFalse(SharedReceipt.objects.filter(pk=restore_op).exists())
            self.assertEqual(self.state(), before_db)
            self.assertEqual(SharedStorage().inventory(), before_fs)
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, debt)
            self.assertEqual(SharedDraft.objects.count(), 2)
            self.report('FINITE_REAL_75PERCENT_AND_BYTES_FULL', evidence)

    def seed_count_9999(self):
        from .models import SharedBlock, SharedRevision, SharedIdentityReservation
        from content.models import lock_content
        before = SharedRevision.objects.count()
        self.assertEqual(before, 2)
        identifiers = [str(uuid4()) for _ in range(9999 - before)]
        block = SharedBlock.objects.get(kind='header')
        text = '<p>LEGACY-COUNT-FIXTURE</p>'
        with transaction.atomic(), connection.cursor() as cursor:
            lock_content('default')
            cursor.execute('INSERT INTO ' + connection.ops.quote_name(SharedIdentityReservation._meta.db_table) +
                " (id,kind,block_id) SELECT id,'sharedrevision',%s FROM unnest(%s::uuid[]) AS ids(id)",
                [block.pk, identifiers])
            cursor.execute('INSERT INTO ' + connection.ops.quote_name(SharedRevision._meta.db_table) +
                ' (id,block_id,sequence,schema_version,html,payload_hash,author_id,created_at) '
                'SELECT id,%s,sequence+1,%s,%s,%s,%s,CURRENT_TIMESTAMP '
                'FROM unnest(%s::uuid[]) WITH ORDINALITY AS ids(id,sequence)',
                [block.pk, 'legacy-count-v1', text, hashlib.sha256(text.encode()).hexdigest(),
                 self.owner.pk, identifiers])
        self.assertEqual(SharedRevision.objects.count(), 9999)

    def test_calibration_actual_9999_last_reserve_two_owner_connections_then_10001_denied(self):
        from . import reservations
        from .models import SharedRevision, SharedReceipt
        from .storage import SharedStorage
        with self.candidate() as evidence:
            self.apply_text('header', 'COUNT-HEADER')
            self.apply_text('footer', 'COUNT-FOOTER')
            self.seed_count_9999()
            first = self.intent('header', self.fixture('header', 'RACE-A'))
            second = self.intent('header', self.fixture('header', 'RACE-B'))
            second_client = self.login('nesadmin', R.H.OWNER_PASSWORD)
        reached, release = threading.Event(), threading.Event()
        results, errors, pids = {}, [], {}
        original = reservations._fault_boundary

        def hold(phase):
            if phase == 'book_durable' and not reached.is_set():
                reached.set()
                if not release.wait(20):
                    raise RuntimeError('RC_CONCURRENT_TEST_RELEASE_TIMEOUT')
            return original(phase)

        def worker(name, client, value):
            try:
                with self.candidate() as own_evidence:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_backend_pid()')
                        pids[name] = cursor.fetchone()[0]
                    token = client.cookies[settings.CSRF_COOKIE_NAME].value
                    result = client.post(self.path('header', 'apply'), data=self.raw(value),
                        content_type='application/json', HTTP_X_CSRFTOKEN=token)
                    results[name] = (result.status_code, result.json())
                    self.report('FINITE_LAST_COUNT_' + name, own_evidence)
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections['default'].close()

        a = threading.Thread(target=worker, args=('A', self.owner_client, first))
        b = threading.Thread(target=worker, args=('B', second_client, second))
        try:
            with patch('shared_content.views.read_json_bytes', side_effect=lambda request, profile: request.body), \
                 patch('shared_content.reservations._fault_boundary', side_effect=hold):
                a.start()
                self.assertTrue(reached.wait(20), 'RC_CONCURRENT_FIRST_BOOK_NOT_REACHED')
                b.start()
                b.join(20)
                self.assertFalse(b.is_alive(), 'RC_CONCURRENT_CONTENDER_DID_NOT_FINISH')
                release.set()
                a.join(20)
                self.assertFalse(a.is_alive(), 'RC_CONCURRENT_WRITER_DID_NOT_FINISH')
            if errors:
                raise errors[0]
            self.assertEqual(results['A'][0], 200)
            self.assertIn(results['B'][0], (409, 503))
            self.assertNotEqual(pids['A'], pids['B'])
            self.assertEqual(SharedRevision.objects.count(), 10000)
            self.assertTrue(SharedReceipt.objects.filter(pk=first['operationId'], result_code='applied').exists())
            self.assertFalse(SharedReceipt.objects.filter(pk=second['operationId']).exists())
        finally:
            release.set()
            if a.ident is not None:
                a.join(20)
            if b.ident is not None:
                b.join(20)
        with self.candidate() as evidence:
            denied_value = self.intent('header', self.fixture('header', 'COUNT-10001'))
            before_db, before_fs = self.state(), SharedStorage().inventory()
            denied = self.send('header', 'apply', denied_value)
            self.assertEqual(denied.status_code, 409)
            self.assertEqual(denied.json()['code'], 'SHARED_HISTORY_COUNT_FULL')
            self.assertFalse(SharedReceipt.objects.filter(pk=denied_value['operationId']).exists())
            self.assertEqual(self.state(), before_db)
            self.assertEqual(SharedStorage().inventory(), before_fs)
            self.report('FINITE_ACTUAL_COUNT_10000', evidence)
