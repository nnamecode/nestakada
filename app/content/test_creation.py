"""CP29 core checks: actual PostgreSQL transactions, races and rollback.

These tests do not establish HTTP, TRUST or public publication readiness.
Raw QuerySets below are deliberate test-only deletion/identity fixtures.
"""
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from time import sleep
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import UUID, uuid4

from django.apps import apps
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, close_old_connections, DatabaseError, models, transaction
from django.test import TransactionTestCase, override_settings
from accounts import services as auth
from accounts.models import AuthSession, UserProfile
from accounts.tests import FAST_HASHERS, PASSWORD, client, login
from page_versions import engine, schema
from page_versions.models import (PageRevision, RevisionMetadata, PageContentState, OwnerDraft,
                                  VersionBasePin, IdentityReservation, OperationReceipt)
from . import creation as create, tree_commands as tree
from .models import Page, Route


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, AUTH_TRUSTED_PROXY_HOST=None,
                   DEV29_LOCAL_CREATE_ENABLED=True, ENVIRONMENT='test')
class PageCreationTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(actor=self.owner, username='auth-employee', password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(user=self.owner).generation
        self.parent = Page.objects.create(name='Каталог', kind='service_catalog', is_published=True)
        Route.objects.create(page=self.parent, kind='primary', target='/services/')
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        media_root = override_settings(MEDIA_LIBRARY_ROOT=temporary.name)
        media_root.enable(); self.addCleanup(media_root.disable)

    def prepare(self, **extra):
        return create.prepare(actor=self.owner, generation=self.generation, session_key=self.key, **extra)

    def apply(self, proof, **extra):
        values = {'actor': self.owner, 'generation': self.generation, 'session_key': self.key,
            'token': proof['token'], 'operation_id': proof['operation_id'], 'page_id': proof['page_id'],
            'parent_id': proof['parent_id'], 'kind': proof['kind'], 'name': 'Новая страница',
            'url': '/new-' + proof['page_id'] + '/', 'h1': 'Отдельный H1', 'title': 'Отдельный title'}
        values.update(extra)
        return create.apply(**values)

    def state(self):
        # Include all durable version, usage and audit records, not just Page.
        return {model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in ('content', 'page_versions', 'media_library', 'audit')
            for model in apps.get_app_config(label).get_models()}

    def refused(self, call, code=None):
        with self.assertRaises(tree.TreeFault) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)

    def test_cp001_five_hidden_aggregates_and_editable_empty_snapshots(self):
        for kind in create.KINDS:
            with self.subTest(kind=kind):
                proof = self.prepare(kind=kind, parent_id=self.parent.pk)
                before_parent = Page.objects.filter(pk=self.parent.pk).values().get()
                result = self.apply(proof)
                page = Page.objects.get(pk=proof['page_id'])
                self.assertFalse(page.is_published)
                self.assertEqual((page.kind, page.parent_id), (kind, self.parent.pk))
                self.assertEqual(Page.objects.filter(pk=self.parent.pk).values().get(), before_parent)
                self.assertEqual(page.routes.get().target, '/new-' + proof['page_id'] + '/')
                revision = page.content_revisions.get()
                self.assertEqual((revision.kind, revision.sequence), ('initial', 1))
                self.assertEqual(RevisionMetadata.objects.get(revision=revision).generation, 1)
                self.assertEqual(PageContentState.objects.get(page=page).current_revision_id, revision.pk)
                draft = OwnerDraft.objects.get(page=page)
                self.assertEqual(draft.base_revision_id, revision.pk)
                self.assertEqual(draft.payload, revision.payload)
                self.assertEqual(draft.payload_hash, schema.digest(revision.payload))
                self.assertEqual(VersionBasePin.objects.get(holder_id=draft.pk).revision_id, revision.pk)
                payload = schema.Snapshot.trusted(draft.payload, kind).data(kind)
                for field in ('intro_text', 'main_text', 'description'):
                    self.assertEqual(payload[field], '')
                self.assertEqual((payload['price'], payload['main_image'], payload['preview_image']), (None, None, None))
                self.assertEqual(payload['embedded_images'], [])
                self.assertTrue(payload['indexing_allowed'])
                self.assertEqual({n['field'] for n in payload['layout'] if n['kind'] == 'text'},
                                 {'intro_text', 'main_text'})
                payload['main_text'] = '<p>Текст владельца</p>'
                engine.save_owner_draft(actor=self.owner, page_id=page.pk, base_revision=revision.pk,
                    snapshot=schema.Snapshot.trusted(payload, kind), expected_generation=self.generation,
                    operation_id=uuid4(), draft_revision=1)
                draft.refresh_from_db(); page.refresh_from_db()
                self.assertEqual(draft.payload['main_text'], '<p>Текст владельца</p>')
                self.assertFalse(page.is_published)
                receipt = OperationReceipt.objects.get(pk=proof['operation_id'])
                self.assertEqual((receipt.action, receipt.result_code, receipt.result_id),
                                 ('tree_create', 'created_hidden', page.pk))
                self.assertFalse(result['replayed'])

    def test_cp002_preview_readonly_suggestion_and_manual_parent_cases(self):
        before = self.state()
        self.assertEqual(create.preview(name='Замена масла')['url'], '/zamena-masla/')
        self.assertEqual(create.preview(name='Замена масла', parent_id=self.parent.pk)['url'],
                         '/services/zamena-masla/')
        for name in ('', '***', 'а' * 81):
            self.assertTrue(create.preview(name=name)['manual_required'])
        self.assertEqual(self.state(), before)
        for target in (None, '/Legacy/?Case=X', '/Legacy/'):
            parent = Page.objects.create(name='Старый раздел', kind='service_catalog')
            if target is not None:
                Route.objects.create(page=parent, kind='primary', target=target, is_legacy=True)
            before = self.state()
            result = create.preview(name='Название', parent_id=parent.pk)
            self.assertTrue(result['manual_required']); self.assertEqual(result['url'], '')
            self.assertEqual(self.state(), before)
            proof = self.prepare(parent_id=parent.pk)
            self.apply(proof, url='/manual-' + str(parent.pk) + '/')

    def test_cp003_all_route_kinds_and_reserved_paths_fail_atomically(self):
        for kind in Route.Kind.values:
            target = '/occupied-' + kind + '/'
            page = None if kind == 'system' else Page.objects.create(name=kind, kind='article')
            Route.objects.create(target=target, kind=kind, page=page)
            proof = self.prepare(); before = self.state()
            self.refused(lambda: self.apply(proof, url=target), 'CREATE_URL_CONFLICT')
            self.assertEqual(self.state(), before)
        for target in ('/manage/', '/manage/secret/', '/wp-admin/', '/.env', '//foreign/', '/bad?query=1'):
            proof = self.prepare(); before = self.state()
            with self.subTest(target=target), self.assertRaises((ValidationError, tree.TreeFault)):
                self.apply(proof, url=target)
            self.assertEqual(self.state(), before)

    def test_cp004_two_postgres_connections_one_basis_one_url_winner(self):
        proofs = [self.prepare(), self.prepare()]; barrier = Barrier(2)
        def run(proof):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()'); pid = cursor.fetchone()[0]
                barrier.wait(timeout=5)
                try:
                    self.apply(proof, url='/concurrent/')
                    return 'created', pid
                except tree.TreeFault as error:
                    return error.code, pid
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, proofs))
        self.assertNotEqual(results[0][1], results[1][1])
        self.assertEqual(sorted(code for code, _ in results), ['CREATE_BASIS_CHANGED', 'created'])
        self.assertEqual(Route.objects.filter(target='/concurrent/').count(), 1)
        self.assertEqual(OperationReceipt.objects.filter(action='tree_create').count(), 1)

    def test_cp005_exact_replay_and_changed_payload_or_nonce(self):
        proof = self.prepare(); result = self.apply(proof); after = self.state()
        self.assertTrue(result['exists'])
        self.assertTrue(self.apply(proof)['replayed']); self.assertEqual(self.state(), after)
        for changes in ({'name': 'Другое'}, {'h1': ''}, {'title': ''}, {'url': '/other/'},
                        {'operation_id': str(uuid4())}, {'page_id': str(uuid4())},
                        {'parent_id': str(self.parent.pk)}, {'kind': 'service_detail'}, {'session_key': 'other'}):
            with self.subTest(changes=changes):
                self.refused(lambda: self.apply(proof, **changes))
                self.assertEqual(self.state(), after)

    def test_cp005_cross_domain_uuid_and_signed_shape_refuse(self):
        for value in (self.parent.pk, Route.objects.get(page=self.parent).pk):
            proof = self.prepare(operation_id=value); before = self.state()
            self.refused(lambda: self.apply(proof), 'CREATE_ID_CONFLICT')
            self.assertEqual(self.state(), before)
        proof = self.prepare(); data = signing.loads(proof['token'], salt=create.SALT)
        for change in ({'actor': True}, {'generation': True}, {'extra': 1}, {'basis': 'bad'}):
            changed = {**data, **change}; before = self.state()
            token = signing.dumps(changed, salt=create.SALT, compress=True)
            self.refused(lambda: self.apply(proof, token=token), 'CREATE_INVALID_CONFIRMATION')
            self.assertEqual(self.state(), before)

    def test_cp005_deleted_historical_result_is_never_recreated(self):
        proof = self.prepare(); self.apply(proof); page_id = UUID(proof['page_id'])
        draft = OwnerDraft.objects.get(page_id=page_id)
        revision = PageRevision.objects.get(page_id=page_id)
        with transaction.atomic():
            # Test-only fixture of a later authorised aggregate deletion.
            engine.raw(VersionBasePin).filter(holder_id=draft.pk).delete()
            engine.raw(OwnerDraft).filter(pk=draft.pk).delete()
            engine.raw(PageContentState).filter(page_id=page_id).delete()
            engine.raw(RevisionMetadata).filter(revision=revision).delete()
            engine.raw(PageRevision).filter(pk=revision.pk).delete()
            models.QuerySet(model=Route).filter(page_id=page_id).delete()
            models.QuerySet(model=Page).filter(pk=page_id).delete()
        before = self.state(); replay = self.apply(proof)
        self.assertTrue(replay['replayed']); self.assertFalse(replay['exists'])
        self.assertEqual(self.state(), before)

    def test_cp007_sql_and_disk_failures_after_each_aggregate_boundary(self):
        for model in (PageRevision, OwnerDraft, VersionBasePin, OperationReceipt):
            for error_kind in ('sql', 'disk'):
                with self.subTest(model=model.__name__, failure=error_kind):
                    proof = self.prepare(); before = self.state(); saved = model.save; seen = []
                    def failed(row, *args, **kwargs):
                        value = saved(row, *args, **kwargs)
                        seen.append(row.pk)
                        self.assertTrue(model.objects.filter(pk=row.pk).exists())
                        if error_kind == 'sql':
                            with connection.cursor() as cursor:
                                cursor.execute('SELECT 1/0')
                        raise OSError(28, 'SYNTHETIC ENOSPC')
                    expected = DatabaseError if error_kind == 'sql' else OSError
                    with patch.object(model, 'save', failed), self.assertRaises(expected):
                        self.apply(proof)
                    self.assertTrue(seen); self.assertEqual(self.state(), before)
                    self.assertFalse(self.apply(proof)['replayed'])

    def test_cp007_audit_failure_rolls_back_receipt_and_reserved_ids(self):
        proof = self.prepare(); before = self.state(); original = create.record_event
        def failed(**kwargs):
            original(**kwargs)
            self.assertTrue(OperationReceipt.objects.filter(pk=proof['operation_id']).exists())
            raise OSError(28, 'SYNTHETIC audit failure')
        with patch.object(create, 'record_event', failed), self.assertRaises(OSError):
            self.apply(proof)
        self.assertEqual(self.state(), before)
        self.assertFalse(self.apply(proof)['replayed'])

    def test_cp008_creation_invalidates_old_tree_form_and_create_basis(self):
        old_tree = tree.prepare(actor=self.owner, page_id=self.parent.pk, action='rename',
            generation=self.generation, session_key=self.key)
        old_create = self.prepare(); self.apply(self.prepare())
        before = self.state()
        self.refused(lambda: self.apply(old_create), 'CREATE_BASIS_CHANGED')
        self.refused(lambda: tree.apply(actor=self.owner, page_id=self.parent.pk, action='rename',
            generation=self.generation, session_key=self.key, token=old_tree['token'],
            operation_id=old_tree['operation_id'], name='Новый каталог'), 'TREE_BASIS_CHANGED')
        self.assertEqual(self.state(), before)

    def test_cp008_parent_rename_aba_keeps_old_create_form_stale(self):
        proof = self.prepare(parent_id=self.parent.pk)
        for name in ('Временное имя', self.parent.name):
            ticket = tree.prepare(actor=self.owner, page_id=self.parent.pk, action='rename',
                generation=self.generation, session_key=self.key)
            tree.apply(actor=self.owner, page_id=self.parent.pk, action='rename', generation=self.generation,
                session_key=self.key, token=ticket['token'], operation_id=ticket['operation_id'], name=name)
        before = self.state()
        self.refused(lambda: self.apply(proof), 'CREATE_BASIS_CHANGED')
        self.assertEqual(self.state(), before)

    def test_cp009_explicit_empty_seo_survives_rename(self):
        proof = self.prepare(); self.apply(proof, h1='', title='')
        ticket = tree.prepare(actor=self.owner, page_id=proof['page_id'], action='rename',
            generation=self.generation, session_key=self.key)
        tree.apply(actor=self.owner, page_id=proof['page_id'], action='rename', generation=self.generation,
            session_key=self.key, token=ticket['token'], operation_id=ticket['operation_id'], name='Новое имя')
        payload = OwnerDraft.objects.get(page_id=proof['page_id']).payload
        self.assertEqual((payload['h1'], payload['title'], payload['description']), ('', '', ''))

    def test_cp010_combined_unicode_and_url_maxima_without_truncation(self):
        target = '/' + ('a' * 80 + '/') * 25 + 'b' * 21 + '/'
        self.assertEqual(len(target.encode()), 2048)
        proof = self.prepare(); name, h1, title = 'Я' * 200, 'Ж' * 255, 'Э' * 255
        transport = {**{k: proof[k] for k in ('token', 'page_id', 'operation_id', 'kind')},
            'parent_id': '', 'name': name, 'h1': h1, 'title': title, 'url': target}
        self.assertLessEqual(len(urlencode(transport).encode()), 16384)
        self.apply(proof, name=name, h1=h1, title=title, url=target)
        page = Page.objects.get(pk=proof['page_id']); payload = OwnerDraft.objects.get(page=page).payload
        self.assertEqual((page.name, payload['h1'], payload['title'], page.routes.get().target),
                         (name, h1, title, target))
        for changes in ({'name': name + 'я'}, {'h1': h1 + 'ж'}, {'title': title + 'э'}, {'url': target + 'x'}):
            proof = self.prepare(); before = self.state()
            with self.assertRaises((ValidationError, tree.TreeFault)):
                self.apply(proof, **changes)
            self.assertEqual(self.state(), before)

    def test_cp012_default_disabled_or_non_test_profile_cannot_prepare_or_apply(self):
        proof = self.prepare(); before = self.state()
        for flag, environment in ((False, 'test'), (1, 'test'), (True, 'production')):
            with override_settings(DEV29_LOCAL_CREATE_ENABLED=flag, ENVIRONMENT=environment):
                self.refused(self.prepare, 'CREATE_DISABLED')
                self.refused(lambda: self.apply(proof), 'CREATE_DISABLED')
            self.assertEqual(self.state(), before)

    def test_cp006_employee_and_missing_session_cannot_create(self):
        proof = self.prepare(); before = self.state()
        with self.assertRaises(PermissionDenied):
            self.apply(proof, actor=self.employee)
        self.refused(lambda: self.apply(proof, session_key=''), 'TREE_SESSION_ENDED')
        self.assertEqual(self.state(), before)

    def _revoked_while_waiting(self, mode):
        proof = self.prepare(); ready = Event(); facts = {}; actual_lock = tree.lock_content
        before = self.state()
        def waiting_lock(using):
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid()'); facts['pid'] = cursor.fetchone()[0]
            ready.set(); actual_lock(using)
        def run():
            close_old_connections()
            try:
                try:
                    self.apply(proof)
                    return 'created'
                except PermissionDenied:
                    return 'denied'
                except tree.TreeFault as error:
                    return error.code
            finally:
                close_old_connections()
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            with patch.object(tree, 'lock_content', waiting_lock):
                with transaction.atomic():
                    actual_lock('default'); future = pool.submit(run)
                    self.assertTrue(ready.wait(5)); waiting = False
                    for _ in range(100):
                        with connection.cursor() as cursor:
                            cursor.execute('SELECT wait_event FROM pg_stat_activity WHERE pid=%s', [facts['pid']])
                            waiting = cursor.fetchone() == ('advisory',)
                        if waiting:
                            break
                        sleep(.01)
                    self.assertTrue(waiting)
                    if mode == 'role':
                        UserProfile.objects.filter(user=self.owner).update(role='employee')
                    else:
                        AuthSession.objects.filter(pk=self.key).delete()
                self.assertEqual(future.result(timeout=5), 'denied' if mode == 'role' else 'TREE_SESSION_ENDED')
        finally:
            pool.shutdown(wait=True)
        self.assertEqual(self.state(), before)

    def test_cp006_role_revocation_is_rechecked_after_advisory_wait(self):
        self._revoked_while_waiting('role')

    def test_cp006_session_revocation_is_rechecked_after_advisory_wait(self):
        self._revoked_while_waiting('session')
