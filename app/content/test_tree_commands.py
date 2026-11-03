"""CMD29 rules, real PostgreSQL races, atomic failures and actual Django forms."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from time import sleep
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, close_old_connections, DatabaseError, transaction
from django.test import TransactionTestCase, override_settings
from accounts import services as auth, clock
from accounts.models import UserProfile, PageGrant
from accounts.tests import FAST_HASHERS, PASSWORD, client, login
from audit.models import AuditEvent
from media_library.models import AssetUsage
from page_versions import services as versions, schema
from page_versions.models import (OperationReceipt, IdentityReservation, PageRevision,
                                 PageContentState, RevisionProtection)
from .models import Page, Route, lock_content
from .reads import public_tree
from . import tree_commands as commands


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, AUTH_TRUSTED_PROXY_HOST=None)
class TreeCommandTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(actor=self.owner, username='auth-employee', password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(user=self.owner).generation
        self.p = Page.objects.create(name='Раздел 1', kind='service_catalog', is_published=True)
        self.q = Page.objects.create(name='Раздел 2', kind='service_catalog', is_published=False)
        self.a = Page.objects.create(name='А', kind='article', parent=self.p, is_published=True)
        self.b = Page.objects.create(name='Б', kind='article', parent=self.p, is_published=True)
        self.child = Page.objects.create(name='Ребёнок', kind='article', parent=self.a, is_published=True)
        self.d = Page.objects.create(name='Д', kind='article', parent=self.q, is_published=True)
        Route.objects.create(page=self.a, target='/Legacy?Case=X', kind='primary', is_legacy=True)
        Route.objects.create(page=self.a, target='/alias/', kind='alias')
        Route.objects.create(page=self.a, target='/prior/', kind='redirect')
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        override = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name)
        override.enable(); self.addCleanup(override.disable)

    def prep(self, action='rename', page=None, **extra):
        return commands.prepare(actor=self.owner, page_id=(page or self.a).pk, action=action,
            generation=self.generation, session_key=self.key, **extra)

    def apply(self, proof, **values):
        kwargs = {'name': 'Новое название'} if proof['action'] == 'rename' else {
            'parent_id': proof['destination'], 'before_id': ''}
        kwargs.update(values)
        return commands.apply(actor=self.owner, page_id=proof['page'].pk, action=proof['action'],
            generation=self.generation, session_key=self.key, token=proof['token'],
            operation_id=proof['operation_id'], **kwargs)

    def state(self):
        return {model._meta.db_table: list(model.objects.order_by('pk').values()) for model in
                (Page, Route, PageRevision, PageContentState, RevisionProtection, AssetUsage,
                 OperationReceipt, IdentityReservation, AuditEvent)}

    def tree_receipts(self):
        return OperationReceipt.objects.filter(action__in=commands.RECEIPT_ACTIONS).count()

    def fault(self, code, call):
        with self.assertRaises(commands.TreeFault) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_rename_preserves_structure_routes_revisions_and_exact_replay(self):
        initial = versions.initialize(actor=self.owner, page_id=self.a.pk,
            snapshot=schema.snapshot_v1(self.a.kind, main_text='<p>Original</p>', h1='H1', title='SEO'),
            expected_generation=1, operation_id=uuid4())
        viewed = versions.view_version(actor=self.owner, page_id=self.a.pk, version_id=initial['result_id'], expected_generation=1)
        versions.set_stable(actor=self.owner, page_id=self.a.pk, version_id=initial['result_id'],
            view_receipt=viewed['view_receipt'], expected_generation=1, operation_id=uuid4())
        proof = self.prep()
        before = self.state()
        result = self.apply(proof)
        self.a.refresh_from_db()
        self.assertEqual(self.a.name, 'Новое название')
        self.assertEqual((self.a.parent_id, self.a.position, self.a.is_published), (self.p.pk, 0, True))
        after = self.state()
        for model in (Route, PageRevision, PageContentState, RevisionProtection, AssetUsage):
            self.assertEqual(after[model._meta.db_table], before[model._meta.db_table])
        replay = self.apply(proof)
        self.assertFalse(result['replay']); self.assertTrue(replay['replay'])
        self.assertEqual(replay['operation_id'], result['operation_id'])
        self.assertEqual(self.state(), after)
        self.assertEqual(self.tree_receipts(), 1)

    def test_move_and_reorder_normalize_only_affected_siblings(self):
        before_routes = list(Route.objects.order_by('pk').values())
        proof = self.prep('move', destination=str(self.q.pk))
        self.apply(proof, before_id=str(self.d.pk))
        self.a.refresh_from_db(); self.b.refresh_from_db(); self.d.refresh_from_db(); self.child.refresh_from_db()
        self.assertEqual((self.a.parent_id, self.a.position, self.b.position, self.d.position), (self.q.pk, 0, 0, 1))
        self.assertEqual((self.child.parent_id, self.child.is_published), (self.a.pk, True))
        self.apply(self.prep('reorder'))
        self.a.refresh_from_db(); self.d.refresh_from_db()
        self.assertEqual((self.a.position, self.d.position), (1, 0))
        self.assertEqual(list(Route.objects.order_by('pk').values()), before_routes)

    def test_move_to_root_preserves_child_identity_and_publication(self):
        self.apply(self.prep('move', destination=None))
        self.a.refresh_from_db(); self.child.refresh_from_db()
        self.assertIsNone(self.a.parent_id)
        self.assertEqual(self.child.parent_id, self.a.pk)
        self.assertTrue(self.a.is_published)

    def test_reorder_changes_projection_and_rename_does_not_reorder(self):
        self.apply(self.prep('reorder', page=self.b), before_id=str(self.a.pk))
        entries = [p['id'] for p in public_tree()]
        self.assertLess(entries.index(self.b.pk), entries.index(self.a.pk))
        positions = dict(Page.objects.values_list('id', 'position'))
        self.apply(self.prep(), name='Я после Б по алфавиту')
        self.assertEqual(dict(Page.objects.values_list('id', 'position')), positions)

    def test_invalid_names_leave_no_receipt(self):
        proof = self.prep(); before = self.state()
        for name in ['', '   ', 'x' * 201, 'bad\nname', '\ud800']:
            with self.subTest(name=repr(name)):
                self.fault('TREE_INVALID_NAME', lambda: self.apply(proof, name=name))
                self.assertEqual(self.state(), before)

    def test_cycles_and_foreign_neighbour_refused(self):
        before = self.state()
        for parent in [self.a.pk, self.child.pk, uuid4()]:
            with self.subTest(parent=parent):
                self.fault('TREE_PARENT_CONFLICT', lambda: self.prep('move', destination=str(parent)))
        proof = self.prep('move', destination=str(self.q.pk))
        self.fault('TREE_NEIGHBOUR_CONFLICT', lambda: self.apply(proof, before_id=str(self.b.pk)))
        self.assertEqual(self.state(), before)

    def test_destination_cannot_change_without_new_preview(self):
        proof = self.prep('move', destination=str(self.q.pk)); before = self.state()
        self.fault('TREE_DESTINATION_CHANGED', lambda: self.apply(proof, parent_id=''))
        self.assertEqual(self.state(), before)

    def test_changed_payload_or_signed_token_cannot_reuse_receipt(self):
        proof = self.prep(); self.apply(proof); before = self.state()
        self.fault('TREE_OPERATION_CONFLICT', lambda: self.apply(proof, name='Другой ввод'))
        broken = {**proof, 'token': proof['token'] + 'x'}
        self.fault('TREE_INVALID_CONFIRMATION', lambda: self.apply(broken))
        self.assertEqual(self.state(), before)

    def test_old_basis_not_revived_by_a_to_b_to_a(self):
        stale = self.prep()
        self.apply(self.prep(), name='Было Б')
        self.apply(self.prep(), name='А')
        before = self.state()
        self.fault('TREE_BASIS_CHANGED', lambda: self.apply(stale))
        self.assertEqual(self.state(), before)

    def test_later_success_not_undone_by_old_exact_replay(self):
        old = self.prep(); self.apply(old)
        self.apply(self.prep(), name='Более позднее название')
        before = self.state(); replay = self.apply(old)
        self.assertTrue(replay['replay']); self.assertEqual(self.state(), before)

    def test_cross_domain_reserved_uuid_refused(self):
        proof = self.prep()
        IdentityReservation.objects.create(id=proof['operation_id'], kind='pagerevision')
        before = self.state()
        self.fault('TREE_OPERATION_CONFLICT', lambda: self.apply(proof))
        self.assertEqual(self.state(), before)

    def test_signed_binding_fields_are_closed(self):
        proof = self.prep(); before = self.state()
        original = signing.loads(proof['token'], salt=commands.SALT)
        for change in [{'actor': self.employee.pk}, {'action': 'move'}, {'page': str(self.b.pk)},
                       {'generation': True}, {'extra': 1}, {'operation': str(uuid4())}]:
            altered = {**proof, 'token': signing.dumps({**original, **change}, salt=commands.SALT)}
            self.fault('TREE_INVALID_CONFIRMATION', lambda: self.apply(altered))
        self.assertEqual(self.state(), before)

    def test_expired_session_cannot_apply_or_replay(self):
        proof = self.prep(); self.apply(proof); before = self.state()
        with patch('accounts.clock.now', return_value=clock.now() + timedelta(minutes=31)):
            self.fault('TREE_SESSION_ENDED', lambda: self.apply(proof))
        self.assertEqual(self.state(), before)

    def test_real_sql_failure_after_partial_page_save_rolls_back_and_retries(self):
        proof = self.prep('move', destination=str(self.q.pk)); before = self.state(); saved = Page.save; witness = []
        def failed(page, *args, **kwargs):
            saved(page, *args, **kwargs)
            witness.append(list(Page.objects.order_by('pk').values()))
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1/0')
        with patch.object(Page, 'save', failed), self.assertRaises(DatabaseError):
            self.apply(proof)
        self.assertTrue(witness); self.assertNotEqual(witness[0], before[Page._meta.db_table])
        self.assertEqual(self.state(), before)
        self.assertFalse(self.apply(proof)['replay'])

    def test_receipt_disk_exception_rolls_back_uuid_and_page(self):
        proof = self.prep(); before = self.state(); saved = OperationReceipt.save; witness = []
        def failed(receipt, *args, **kwargs):
            saved(receipt, *args, **kwargs)
            witness.append(IdentityReservation.objects.filter(pk=receipt.pk).exists())
            raise OSError(28, 'SYNTHETIC ENOSPC')
        with patch.object(OperationReceipt, 'save', failed), self.assertRaises(OSError):
            self.apply(proof)
        self.assertEqual(witness, [True]); self.assertEqual(self.state(), before)
        self.assertFalse(self.apply(proof)['replay'])

    def test_audit_exception_rolls_back_whole_command(self):
        proof = self.prep(); before = self.state(); saved = commands.record_event
        def failed(**kwargs):
            saved(**kwargs)
            raise OSError(28, 'SYNTHETIC audit failure')
        with patch.object(commands, 'record_event', failed), self.assertRaises(OSError):
            self.apply(proof)
        self.assertEqual(self.state(), before)
        self.assertFalse(self.apply(proof)['replay'])

    def test_two_real_connections_have_one_winner(self):
        first, second = self.prep(), self.prep(page=self.b)
        barrier = Barrier(2)
        def run(proof):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()'); pid = cursor.fetchone()[0]
                barrier.wait(timeout=5)
                try:
                    self.apply(proof)
                    return ('applied', pid)
                except commands.TreeFault as error:
                    return (error.code, pid)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(run, [first, second]))
        self.assertEqual(sorted(code for code, _ in values), ['TREE_BASIS_CHANGED', 'applied'])
        self.assertNotEqual(values[0][1], values[1][1]); self.assertEqual(self.tree_receipts(), 1)

    def test_reset_while_waiting_for_content_lock_is_rechecked(self):
        proof = self.prep(); ready = Event(); facts = {}; real_lock = commands.lock_content
        def wait_lock(using):
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid()'); facts['pid'] = cursor.fetchone()[0]
            ready.set(); real_lock(using)
        def run():
            close_old_connections()
            try:
                try:
                    self.apply(proof)
                except PermissionDenied:
                    return 'denied'
                return 'applied'
            finally:
                close_old_connections()
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            with patch.object(commands, 'lock_content', wait_lock):
                with transaction.atomic():
                    real_lock('default')
                    future = pool.submit(run)
                    self.assertTrue(ready.wait(5))
                    waiting = False
                    for _ in range(100):
                        with connection.cursor() as cursor:
                            cursor.execute('SELECT wait_event FROM pg_stat_activity WHERE pid=%s', [facts['pid']])
                            waiting = cursor.fetchone() == ('advisory',)
                        if waiting: break
                        sleep(.01)
                    self.assertTrue(waiting)
                    auth.recover_owner(PASSWORD)
                self.assertEqual(future.result(timeout=5), 'denied')
        finally:
            pool.shutdown(wait=True)
        self.assertEqual(self.tree_receipts(), 0)
        self.a.refresh_from_db(); self.assertEqual(self.a.name, 'А')

    def test_grant_and_tree_command_both_preserved(self):
        proof = self.prep(); barrier = Barrier(2)
        def run(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                if kind == 'grant':
                    auth.set_grant(actor=self.owner, employee=self.employee, page=self.a, main_text=True)
                else:
                    self.apply(proof)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(run, ['grant', 'tree']))
        self.assertTrue(PageGrant.objects.get(page=self.a, user=self.employee).main_text)
        self.a.refresh_from_db(); self.assertEqual(self.a.name, 'Новое название')

    def test_real_content_commit_race_preserves_content_and_protected_structure(self):
        initial = versions.initialize(actor=self.owner, page_id=self.a.pk,
            snapshot=schema.snapshot_v1(self.a.kind, main_text='<p>Before</p>'),
            expected_generation=1, operation_id=uuid4())
        proof = self.prep(); barrier = Barrier(2)
        def run(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                if kind == 'content':
                    versions.commit_owner(actor=self.owner, page_id=self.a.pk,
                        base_revision=initial['result_id'], snapshot=schema.snapshot_v1(self.a.kind, main_text='<p>After</p>'),
                        expected_generation=1, operation_id=uuid4())
                    return 'content'
                try:
                    self.apply(proof)
                    return 'tree'
                except commands.TreeFault as error:
                    self.assertEqual(error.code, 'TREE_BASIS_CHANGED')
                    return 'stale'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(run, ['content', 'tree']))
        current = PageContentState.objects.select_related('current_revision').get(page=self.a)
        self.assertEqual(current.current_revision.payload['main_text'], '<p>After</p>')
        self.a.refresh_from_db()
        self.assertEqual(self.a.name, 'Новое название' if 'tree' in values else 'А')
        self.assertEqual(self.a.parent_id, self.p.pk)

    def test_real_stable_race_keeps_protection_or_refuses_changed_view(self):
        initial = versions.initialize(actor=self.owner, page_id=self.a.pk,
            snapshot=schema.snapshot_v1(self.a.kind, main_text='<p>Stable source</p>'),
            expected_generation=1, operation_id=uuid4())
        viewed = versions.view_version(actor=self.owner, page_id=self.a.pk,
            version_id=initial['result_id'], expected_generation=1)
        proof = self.prep(); barrier = Barrier(2)
        def run(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                if kind == 'stable':
                    try:
                        versions.set_stable(actor=self.owner, page_id=self.a.pk, version_id=initial['result_id'],
                            view_receipt=viewed['view_receipt'], expected_generation=1, operation_id=uuid4())
                        return 'stable'
                    except ValidationError as error:
                        self.assertIn('VERSIONS_VIEW_CHANGED', str(error))
                        return 'stale-view'
                self.apply(proof)
                return 'tree'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(run, ['stable', 'tree']))
        self.assertIn('tree', values)
        self.assertEqual(RevisionProtection.objects.filter(revision_id=initial['result_id']).exists(), 'stable' in values)
        self.assertEqual(str(PageContentState.objects.get(page=self.a).current_revision_id), initial['result_id'])

    def test_receipt_relation_growth_is_measured_without_new_storage(self):
        import json
        tables = [OperationReceipt._meta.db_table, IdentityReservation._meta.db_table, AuditEvent._meta.db_table]
        def measure():
            with connection.cursor() as cursor:
                cursor.execute('SELECT name,pg_total_relation_size(name::regclass) FROM unnest(%s::text[]) AS name', [tables])
                return {name: int(size) for name, size in cursor.fetchall()}
        before = measure()
        for index in range(5):
            self.apply(self.prep(), name='Измерение ' + str(index))
        after = measure()
        self.assertEqual(self.tree_receipts(), 5)
        self.assertTrue(all(after[name] >= before[name] for name in tables))
        print('CMD29_STORAGE=' + json.dumps({'scope': 'five synthetic UNIT commands, relation totals include indexes/TOAST',
            'before': before, 'after': after, 'delta': {name: after[name] - before[name] for name in tables}}, sort_keys=True))

    def test_http_forms_success_replay_and_stale_input(self):
        path = f'/manage/pages/{self.a.pk}/structure/rename/'
        before = self.state()
        response = self.browser.get(path)
        self.assertEqual(response.status_code, 200); self.assertEqual(self.state(), before)
        proof = response.context['prepared']
        data = {'operation_id': proof['operation_id'], 'token': proof['token'], 'name': 'HTTP новое'}
        first = self.browser.post(path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(first.status_code, 303); self.assertEqual(first['X-Tree-Result'], 'applied')
        snapshot = self.state()
        replay = self.browser.post(path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(replay.status_code, 303); self.assertEqual(replay['X-Tree-Result'], 'replay')
        self.assertEqual(self.state()[Page._meta.db_table], snapshot[Page._meta.db_table])
        fresh = self.browser.get(path).context['prepared']
        self.apply(self.prep(page=self.b))
        stale = self.browser.post(path, {'operation_id': fresh['operation_id'], 'token': fresh['token'],
            'name': '<b>Несохранённый ввод</b>'}, content_type='application/x-www-form-urlencoded')
        self.assertEqual(stale.status_code, 409)
        self.assertContains(stale, '&lt;b&gt;Несохранённый ввод&lt;/b&gt;', status_code=409)
        self.assertEqual(stale['Cache-Control'], 'private, no-store')

    def test_http_move_preview_and_reorder_forms(self):
        path = f'/manage/pages/{self.a.pk}/structure/move/'
        response = self.browser.get(path, {'parent': str(self.q.pk)})
        self.assertEqual(response.status_code, 200)
        proof = response.context['prepared']
        response = self.browser.post(path, {'operation_id': proof['operation_id'], 'token': proof['token'],
            'parent_id': str(self.q.pk), 'before_id': str(self.d.pk)}, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.browser.get(f'/manage/pages/{self.a.pk}/structure/reorder/').status_code, 200)

    def test_http_lost_confirmation_after_real_commit_retries_exact_receipt(self):
        path = f'/manage/pages/{self.a.pk}/structure/rename/'
        proof = self.browser.get(path).context['prepared']
        data = {'operation_id': proof['operation_id'], 'token': proof['token'], 'name': 'Уже сохранено'}
        original = commands.apply
        observations = []
        def independent():
            close_old_connections()
            try:
                return {'name': Page.objects.get(pk=self.a.pk).name,
                    'receipt': OperationReceipt.objects.filter(pk=proof['operation_id']).exists(),
                    'reservation': IdentityReservation.objects.filter(pk=proof['operation_id']).exists(),
                    'audit': AuditEvent.objects.filter(code='TREE_RENAME', object_ref='uuid:' + str(self.a.pk)).count()}
            finally:
                close_old_connections()
        def lost(**kwargs):
            value = original(**kwargs)
            self.assertFalse(connection.in_atomic_block)
            self.assertFalse(value['replay'])
            with ThreadPoolExecutor(max_workers=1) as pool:
                observations.append(pool.submit(independent).result(timeout=5))
            raise DatabaseError('SYNTHETIC confirmation lost after COMMIT')
        with patch.object(commands, 'apply', lost):
            response = self.browser.post(path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, proof['operation_id'], status_code=503)
        self.assertContains(response, proof['token'], status_code=503)
        self.assertContains(response, 'Уже сохранено', status_code=503)
        self.assertEqual(observations, [{'name': 'Уже сохранено', 'receipt': True, 'reservation': True, 'audit': 1}])
        committed = self.state()
        replay = self.browser.post(path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(replay.status_code, 303)
        self.assertEqual(replay['X-Tree-Result'], 'replay')
        self.assertEqual(self.state(), committed)

    def test_http_auth_csrf_closed_fields_and_error_retry_preserves_id(self):
        path = f'/manage/pages/{self.a.pk}/structure/rename/'
        self.assertEqual(client().get(path).status_code, 401)
        employee = client(); self.assertEqual(login(employee).status_code, 303)
        self.assertEqual(employee.get(path).status_code, 403)
        self.assertEqual(employee.post(path, {}).status_code, 403)
        strict = client(csrf=True)
        strict.get('/manage/login/')
        self.assertEqual(login(strict, 'nesadmin', HTTP_X_CSRFTOKEN=strict.cookies[settings.CSRF_COOKIE_NAME].value).status_code, 303)
        proof = strict.get(path).context['prepared']
        data = {'operation_id': proof['operation_id'], 'token': proof['token'], 'name': 'Без CSRF'}
        before = self.tree_receipts()
        self.assertEqual(strict.post(path, data, content_type='application/x-www-form-urlencoded').status_code, 403)
        self.assertEqual(self.tree_receipts(), before)
        with patch('content.tree_commands.record_event', side_effect=OSError(28, 'SYNTHETIC')):
            failed = self.browser.post(path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(failed.status_code, 503)
        self.assertContains(failed, proof['operation_id'], status_code=503)
        retried = self.browser.post(path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(retried.status_code, 303)
        self.assertEqual(self.tree_receipts(), before + 1)
