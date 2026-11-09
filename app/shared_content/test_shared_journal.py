"""SJR-001–005: real immutable book IO, never authoritative admission."""
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
from unittest.mock import patch
from uuid import UUID, uuid4

from django.db import connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from .faults import SharedFault
from . import test_shared_storage as F
from . import test_shared_http as H


def book_fixture(**changes):
    value = {'bookSchema': 'shared-held-book-v1', 'profileId': 'shared-unvetted-v1',
        'operationId': str(uuid4()), 'blockId': '87654321-4321-8765-abcd-0123456789ef',
        'action': 'apply', 'actorId': 1, 'generation': 1,
        'inputFingerprint': 'a' * 64, 'sourceStamp': 'b' * 64,
        'reservedBytes': 17, 'snapshotIncrement': 1}
    value.update(changes)
    return value


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


# Fixed trusted code; only an own temporary media root/role and synthetic book
# are passed. No Django DB configuration, inherited secrets or shell commands.
CHILD = r'''
import json,os,resource,signal,sys
resource.setrlimit(resource.RLIMIT_AS,(384*1024*1024,384*1024*1024))
resource.setrlimit(resource.RLIMIT_CPU,(10,10))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
resource.setrlimit(resource.RLIMIT_FSIZE,(4096,4096))
signal.alarm(20)
sys.path.insert(0,'/app')
from django.conf import settings
settings.configure(MEDIA_LIBRARY_ROOT=sys.argv[1])
from shared_content.journal import SharedJournal
from shared_content.faults import SharedFault
value=json.loads(sys.stdin.readline())
original=os.write
stopped=False
if sys.argv[2]=='writer':
    def partial(fd,data):
        global stopped
        if not stopped:
            stopped=True
            count=original(fd,data[:5])
            print(json.dumps({'event':'LOCKED_PARTIAL'}),flush=True)
            if sys.stdin.readline().strip()!='GO':raise OSError('SJR_TEST_ABORT')
            return count
        return original(fd,data)
    os.write=partial
try:
    result=SharedJournal().create_or_replay(value)
    print(json.dumps({'event':'RESULT','sha256':result['sha256'],
        'durable':result['durable'],'replay':result['replay'],
        'profileAvailable':result['profileAvailable'],'heldAuthority':result['heldAuthority']}),flush=True)
except SharedFault as exc:
    print(json.dumps({'event':'REFUSED','code':exc.code}),flush=True)
except Exception:
    print(json.dumps({'event':'UNEXPECTED_ERROR'}),flush=True)
    raise SystemExit(2)
'''


class SharedJournalTests(SimpleTestCase):
    actual = F.SharedStorageTests.actual
    assert_inventory = F.SharedStorageTests.assert_inventory

    def setUp(self):
        F.SharedStorageTests.setUp(self)
        from .journal import SharedJournal
        self.journal = SharedJournal(self.store)

    def path(self, book):
        return self.store.root / 'journal' / (UUID(book['operationId']).hex + '.json')

    def success(self, result, book, replay):
        self.assertEqual(result['book'], book)
        self.assertEqual(result['sha256'], hashlib.sha256(canonical(book)).hexdigest())
        self.assertEqual(result['replay'], replay)
        self.assertTrue(result['durable'])
        self.assertFalse(result['profileAvailable'])
        self.assertFalse(result['heldAuthority'])

    def observed_barriers(self, action, book, replay):
        original_fsync, original_open = os.fsync, os.open
        events, opened = [], []

        def observe_open(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            opened.append(fd)
            return fd

        def observe_sync(fd):
            info = os.fstat(fd)
            original_fsync(fd)
            events.append(('file' if stat.S_ISREG(info.st_mode) else 'directory',
                           info.st_dev, info.st_ino))

        with patch('shared_content.journal.os.fsync', side_effect=observe_sync), \
             patch('shared_content.journal.os.open', side_effect=observe_open):
            result = action()
        self.success(result, book, replay)
        expected_paths = [self.path(book), self.store.root / 'journal', self.store.root,
                          self.store.root.parent, Path(self.temp.name)]
        expected = [('file' if index == 0 else 'directory', path.stat().st_dev, path.stat().st_ino)
                    for index, path in enumerate(expected_paths)]
        self.assertEqual(events[-5:], expected, 'SJR_WRONG_DURABILITY_TARGET_OR_ORDER')
        self.assertTrue(bool(opened))
        for fd in set(opened):
            with self.assertRaises(OSError) as closed:
                os.fstat(fd)
            self.assertEqual(closed.exception.errno, errno.EBADF)
        return result

    def test_sjr001_actual_create_close_reopen_exact_bytes_and_full_chain(self):
        from .journal import SharedJournal
        book = book_fixture(actorId=9223372036854775807, reservedBytes=268435456)
        self.observed_barriers(lambda: self.journal.create_or_replay(book), book, False)
        self.assertEqual(self.path(book).read_bytes(), canonical(book))
        info = self.path(book).lstat()
        self.assertEqual((stat.S_IMODE(info.st_mode), info.st_uid, info.st_nlink),
                         (0o600, os.geteuid(), 1))
        self.observed_barriers(lambda: SharedJournal(self.store).read(book['operationId']), book, True)
        self.assertEqual(self.assert_inventory()['journalCount'], 1)

    def test_sjr001_strict_caller_fields_types_bounds_before_filesystem_changes(self):
        base = book_fixture()
        changes = ({'bookSchema': 'foreign'}, {'profileId': 'foreign'}, {'extra': 'NO'},
            {'actorId': True}, {'actorId': 0}, {'generation': 9223372036854775808},
            {'reservedBytes': -1}, {'reservedBytes': 268435457}, {'reservedBytes': 1.0},
            {'snapshotIncrement': True}, {'snapshotIncrement': 0}, {'action': 'foreign'},
            {'operationId': UUID(base['operationId'])}, {'blockId': 'NOT-UUID'},
            {'inputFingerprint': 'A' * 64}, {'sourceStamp': 'a' * 63})
        for change in changes:
            with self.subTest(fields=tuple(change)), self.assertRaises(SharedFault) as refusal:
                self.journal.create_or_replay({**base, **change})
            self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_INVALID')
            self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        for key in base:
            value = {name: item for name, item in base.items() if name != key}
            with self.assertRaises(SharedFault):
                self.journal.create_or_replay(value)
        for action, increment in (('draft', 0), ('restore_prepare', 0)):
            value = book_fixture(action=action, snapshotIncrement=increment, reservedBytes=0)
            self.success(self.journal.create_or_replay(value), value, False)

    def test_sjr001_raw_noncanonical_duplicate_utf8_size_and_filename_binding(self):
        book = book_fixture()
        self.journal.create_or_replay(book)
        path, raw = self.path(book), canonical(book)
        duplicate = raw.replace(b'"actorId":1,', b'"actorId":1,"actorId":1,')
        self.assertNotEqual(duplicate, raw, 'SJR_DUPLICATE_FIXTURE_NOT_CHANGED')
        vectors = (raw + b'\n', duplicate, b'{"actorId":NaN}', b'\xef\xbb\xbf' + raw,
                   b'\xff', b' ' * 4096, b' ' * 4097)
        for index, value in enumerate(vectors):
            path.write_bytes(value)
            with self.subTest(vector=index), self.assertRaises(SharedFault) as refusal:
                self.journal.read(book['operationId'])
            self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_INVALID')
            self.assertEqual(path.read_bytes(), value, 'SJR_INVALID_BOOK_REPAIRED_OR_DELETED')
        path.write_bytes(raw)
        other = book_fixture()
        path.rename(self.path(other))
        with self.assertRaises(SharedFault) as refusal:
            self.journal.read(other['operationId'])
        self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_INVALID')

    def test_sjr002_exact_replay_resyncs_same_inode_and_each_changed_binding_conflicts(self):
        book = book_fixture()
        self.journal.create_or_replay(book)
        inode = self.path(book).stat().st_ino
        self.observed_barriers(lambda: self.journal.create_or_replay(book), book, True)
        for changed in ({'blockId': str(uuid4())}, {'actorId': 2}, {'generation': 2},
                        {'inputFingerprint': 'c' * 64}, {'sourceStamp': 'd' * 64},
                        {'reservedBytes': 18}, {'action': 'draft', 'snapshotIncrement': 0}):
            with self.assertRaises(SharedFault) as refusal:
                self.journal.create_or_replay({**book, **changed})
            self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_CONFLICT')
            self.assertEqual(self.path(book).read_bytes(), canonical(book))
            self.assertEqual(self.path(book).stat().st_ino, inode)
        self.assertEqual(self.assert_inventory()['journalCount'], 1)
        with self.assertRaises(SharedFault) as refusal:
            self.journal.read(uuid4())
        self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_UNAVAILABLE')

    def test_sjr002_kernel_lock_survives_final_named_guards_then_releases(self):
        book = book_fixture()
        original_journal = self.store._journal_identity
        original_named = self.store._named_directory_identity
        for operation in ('create', 'read'):
            probes, contender = [], []

            def locked_at_guard(label):
                if not contender:
                    contender.append(os.open(self.path(book), os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC))
                fd = contender[0]
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    probes.append(label)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    self.fail('SJR_LOCK_RELEASED_BEFORE_FINAL_NAMED_GUARD')

            def journal_guard(root, held):
                locked_at_guard('journal')
                return original_journal(root, held)

            def named_guard(fd, suffix):
                locked_at_guard('named:' + '/'.join(suffix))
                return original_named(fd, suffix)

            try:
                with patch.object(self.store, '_journal_identity', side_effect=journal_guard), \
                     patch.object(self.store, '_named_directory_identity', side_effect=named_guard):
                    result = (self.journal.create_or_replay(book) if operation == 'create'
                              else self.journal.read(book['operationId']))
                self.success(result, book, operation == 'read')
                self.assertIn('journal', probes)
                self.assertIn('named:private/shared-content', probes)
                self.assertEqual(len(contender), 1)
                # The exact same second open-file-description can lock only
                # after every guard and the outer creator/reader finally exit.
                fcntl.flock(contender[0], fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(contender[0], fcntl.LOCK_UN)
            finally:
                if contender:
                    os.close(contender[0])

    def test_sjr004_symlink_hardlink_fifo_wrong_mode_never_authorize_or_follow(self):
        book = book_fixture()
        self.journal.create_or_replay(book)
        path, raw = self.path(book), canonical(book)
        target = Path(self.temp.name) / 'own-target'
        target.write_bytes(b'OWN-TARGET')
        path.unlink()
        os.symlink(target, path)
        with self.assertRaises(SharedFault):
            self.journal.read(book['operationId'])
        self.assertEqual(target.read_bytes(), b'OWN-TARGET')
        path.unlink()
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        extra = Path(self.temp.name) / 'own-hardlink'
        os.link(path, extra)
        with self.assertRaises(SharedFault):
            self.journal.read(book['operationId'])
        extra.unlink()
        os.chmod(path, 0o644)
        with self.assertRaises(SharedFault):
            self.journal.read(book['operationId'])
        os.chmod(path, 0o600)
        path.unlink()
        os.mkfifo(path, 0o600)
        with self.assertRaises(SharedFault):
            self.journal.read(book['operationId'])

    def test_sjr004_partial_write_and_file_fsync_failures_preserve_scanned_book(self):
        original_write, original_sync = os.write, os.fsync
        for fault in ('partial', 'file-fsync'):
            book, hits = book_fixture(), {'writes': 0, 'fault': 0}

            def write(fd, data):
                hits['writes'] += 1
                if fault == 'partial':
                    if hits['writes'] == 1:
                        return original_write(fd, data[:5])
                    hits['fault'] += 1
                    raise OSError(errno.EIO, 'SJR_TEST_WRITE_FAULT')
                return original_write(fd, data)

            def fsync(fd):
                if fault == 'file-fsync' and stat.S_ISREG(os.fstat(fd).st_mode):
                    hits['fault'] += 1
                    raise OSError(errno.EIO, 'SJR_TEST_FILE_FSYNC_FAULT')
                return original_sync(fd)

            with patch('shared_content.journal.os.write', side_effect=write), \
                 patch('shared_content.journal.os.fsync', side_effect=fsync):
                with self.assertRaises(SharedFault):
                    self.journal.create_or_replay(book)
            self.assertEqual(hits['fault'], 1, 'SJR_ACTUAL_FAULT_NOT_REACHED')
            self.assertTrue(self.path(book).exists())
            self.assertEqual(self.assert_inventory()['journalCount'], 1 if fault == 'partial' else 2)
            if fault == 'partial':
                self.assertEqual(self.path(book).read_bytes(), canonical(book)[:5])
                with self.assertRaises(SharedFault) as refusal:
                    self.journal.read(book['operationId'])
                self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_INVALID')
            else:
                self.assertEqual(self.path(book).read_bytes(), canonical(book))

    def test_sjr004_failed_ancestor_barrier_requires_new_complete_barriers_on_eexist(self):
        from .journal import SharedJournal
        book = book_fixture()
        original_sync = os.fsync
        media = Path(self.temp.name).stat()

        def fault_call(action):
            seen = {'file': False, 'fault': 0}
            def fsync(fd):
                info = os.fstat(fd)
                if stat.S_ISREG(info.st_mode):
                    seen['file'] = True
                if seen['file'] and (info.st_dev, info.st_ino) == (media.st_dev, media.st_ino):
                    seen['fault'] += 1
                    raise OSError(errno.EIO, 'SJR_TEST_ANCESTOR_FSYNC_FAULT')
                original_sync(fd)
            with patch('shared_content.journal.os.fsync', side_effect=fsync):
                with self.assertRaises(SharedFault) as refusal:
                    action()
            self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_UNAVAILABLE')
            self.assertEqual(seen['fault'], 1, 'SJR_ANCESTOR_FAULT_NOT_REACHED')

        fault_call(lambda: self.journal.create_or_replay(book))
        self.assertEqual(self.path(book).read_bytes(), canonical(book))
        fault_call(lambda: SharedJournal(self.store).read(book['operationId']))
        self.observed_barriers(lambda: SharedJournal(self.store).create_or_replay(book), book, True)
        self.assertEqual(self.assert_inventory()['journalCount'], 1)

    def rename_journal(self, mode):
        baseline = self.store.write_new('OUTSIDE-JOURNAL-BASELINE')
        book = book_fixture()
        if mode == 'read':
            self.journal.create_or_replay(book)
        original_read, original_write = os.read, os.write
        held = self.store.root / 'journal-held-renamed'
        hits = []

        def replace():
            if hits:
                return
            hits.append(True)
            (self.store.root / 'journal').rename(held)
            (self.store.root / 'journal').mkdir(mode=0o700)
            self.path(book).write_bytes(canonical({**book, 'reservedBytes': 18}))
            os.chmod(self.path(book), 0o600)

        def read(fd, size):
            data = original_read(fd, size)
            if data:
                replace()
            return data

        def write(fd, data):
            written = original_write(fd, data)
            if written:
                replace()
            return written

        target = 'shared_content.journal.os.' + ('read' if mode == 'read' else 'write')
        with patch(target, side_effect=read if mode == 'read' else write):
            with self.assertRaises(SharedFault) as refusal:
                if mode == 'read':
                    self.journal.read(book['operationId'])
                else:
                    self.journal.create_or_replay(book)
        self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_UNAVAILABLE')
        self.assertEqual(len(hits), 1)
        self.assertEqual((held / self.path(book).name).read_bytes(), canonical(book))
        self.assertEqual(self.path(book).read_bytes(), canonical({**book, 'reservedBytes': 18}))
        self.assertEqual(self.store.read(baseline), 'OUTSIDE-JOURNAL-BASELINE')
        with self.assertRaises(SharedFault):
            self.store.inventory()

    def test_sjr004_named_journal_replacement_during_read_refuses(self):
        self.rename_journal('read')

    def test_sjr004_named_journal_replacement_during_write_refuses(self):
        self.rename_journal('write')

    def test_sjr003_two_real_processes_partial_writer_busy_contender_then_fresh_replay(self):
        book, processes = book_fixture(), []
        environment = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}

        def start(role):
            child = subprocess.Popen((sys.executable, '-I', '-B', '-c', CHILD, self.temp.name, role),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, close_fds=True, env=environment)
            processes.append(child)
            return child

        try:
            writer = start('writer')
            writer.stdin.write(canonical(book).decode() + '\n')
            writer.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(writer.stdout, selectors.EVENT_READ)
                self.assertTrue(bool(selector.select(10)), 'SJR_WRITER_BARRIER_TIMEOUT')
                barrier = writer.stdout.readline(1024)
            self.assertEqual(json.loads(barrier), {'event': 'LOCKED_PARTIAL'})
            self.assertEqual(self.path(book).read_bytes(), canonical(book)[:5])
            contender = start('contender')
            stdout, stderr = contender.communicate(canonical(book).decode() + '\n', timeout=10)
            self.assertEqual(contender.returncode, 0, 'SJR_CONTENDER_PROCESS_FAILED')
            self.assertFalse(bool(stderr), 'SJR_CHILD_STDERR_NOT_EMPTY')
            self.assertEqual(json.loads(stdout), {'event': 'REFUSED', 'code': 'SHARED_JOURNAL_BUSY'})
            self.assertEqual(self.assert_inventory()['journalCount'], 1)
            stdout, stderr = writer.communicate('GO\n', timeout=10)
            self.assertEqual(writer.returncode, 0, 'SJR_WRITER_PROCESS_FAILED')
            self.assertFalse(bool(stderr), 'SJR_CHILD_STDERR_NOT_EMPTY')
            result = json.loads(stdout)
            self.assertEqual(result, {'event': 'RESULT', 'sha256': hashlib.sha256(canonical(book)).hexdigest(),
                'durable': True, 'replay': False, 'profileAvailable': False, 'heldAuthority': False})
            self.observed_barriers(lambda: self.journal.read(book['operationId']), book, True)
            self.assertEqual(self.path(book).read_bytes(), canonical(book))
            with self.assertRaises(SharedFault) as refusal:
                self.journal.create_or_replay({**book, 'reservedBytes': 18})
            self.assertEqual(refusal.exception.code, 'SHARED_JOURNAL_CONFLICT')
        finally:
            for child in processes:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
                for stream in (child.stdin, child.stdout, child.stderr):
                    if not stream.closed:
                        stream.close()
                with self.assertRaises(ChildProcessError):
                    os.waitpid(child.pid, os.WNOHANG)


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedJournalRollbackTests(TransactionTestCase):
    setUp = H.SharedHttpTests.setUp
    login = H.SharedHttpTests.login
    raw = H.SharedHttpTests.raw
    fixture = H.SharedHttpTests.fixture
    state = H.SharedHttpTests.state
    path = H.SharedHttpTests.path
    post_shared = H.SharedHttpTests.post_shared
    seed_revision = H.SharedHttpTests.seed_revision

    def test_sjr005_sql_rollback_does_not_remove_durable_book_or_create_business_receipt(self):
        from .journal import SharedJournal
        from .models import SharedBlock
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(),current_user')
            self.assertEqual(cursor.fetchone(), ('estakada_foundation_unit', 'app_migrator'))
        book = book_fixture(actorId=self.owner.pk, blockId=str(SharedBlock.objects.get(kind='header').pk))
        before = self.state()
        with transaction.atomic():
            self.seed_revision('header')
            created = SharedJournal().create_or_replay(book)
            self.assertTrue(created['durable'])
            self.assertFalse(created['heldAuthority'])
            transaction.set_rollback(True)
        self.assertEqual(self.state(), before)
        fresh = SharedJournal().read(book['operationId'])
        self.assertEqual(fresh['book'], book)
        self.assertTrue(fresh['durable'])
        self.assertFalse(fresh['heldAuthority'])

    def test_sjr005_legacy_book_does_not_block_simple_inline_writes_or_change_files(self):
        from .journal import SharedJournal
        from .models import SharedBlock, SharedDraft, SharedRevision
        from .storage import SharedStorage
        book = book_fixture(actorId=self.owner.pk, blockId=str(SharedBlock.objects.get(kind='header').pk))
        SharedJournal().create_or_replay(book)
        store = SharedStorage()
        for kind in ('header', 'footer'):
            payload = {'protocol': 'shared-editor-v1', 'generation': 1, 'baseRevisionId': None,
                'sourceMode': 'current', 'draftBasis': None, 'stageId': None, 'html': self.fixture(kind)}
            for _ in range(2):
                checked = self.post_shared(kind, 'check', payload)
                self.assertEqual(checked.status_code, 200)
                payload['html'] = checked.json()['normalisedHtml']
            payload.update(operationId=str(uuid4()), checkReceipt=checked.json()['checkReceipt'])
            for action in ('draft', 'apply'):
                payload['operationId'] = str(uuid4())
                before_fs = store.inventory()
                accepted = self.post_shared(kind, action, payload)
                self.assertEqual(accepted.status_code, 200)
                row_model = SharedDraft if action == 'draft' else SharedRevision
                self.assertEqual(row_model.objects.get(pk=accepted.json()['resultId']).storage_kind, 'inline')
                self.assertEqual(store.inventory(), before_fs)
