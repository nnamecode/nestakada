"""SC07 bounded cancel integration: real PG/files/journal, no quota success mocks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from uuid import UUID, uuid4

from django.conf import settings
from django.db import connection, connections, models
from django.test import TransactionTestCase, override_settings

from page_editor import test_check_http as H
from . import test_shared_reservation as R


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedCancelTests(R.ReservationFixture, TransactionTestCase):
    def prepare(self, kind='header', *, same=False, draft=True):
        from .models import SharedRestoreStage
        _, source = self.apply_text(kind, 'CANCEL-SOURCE-' + kind)
        if not same:
            self.apply_text(kind, 'CANCEL-CURRENT-' + kind)
        if draft:
            self.applied(kind, 'draft', self.intent(kind, self.fixture(kind, 'RETAIN-DRAFT-' + kind)))
        context = self.context(kind)
        response = self.send(kind, 'restore/prepare', {'protocol':'shared-editor-v1',
            'generation':1, 'baseRevisionId':context['baseRevisionId'],
            'sourceRevisionId':source['resultId'], 'operationId':str(uuid4()),
            'confirmReplace':True}, context=context)
        self.assertEqual(response.status_code, 200)
        stage = SharedRestoreStage.objects.get(pk=response.json()['resultId'])
        self.assertEqual(stage.status, 'held')
        return stage, response.json()['editorContext']

    def cancel_body(self, operation=None, **changes):
        return {'protocol':'shared-editor-v1', 'generation':1,
            'operationId':str(operation or uuid4()), 'confirmCancel':True, **changes}

    def cancel(self, kind, stage, value=None, *, client=None, csrf=True, query=''):
        client = self.owner_client if client is None else client
        path = '/manage/shared/%s/stages/%s/cancel/%s' % (kind, stage.pk if hasattr(stage, 'pk') else stage, query)
        headers = {'HTTP_X_CSRFTOKEN':client.cookies[settings.CSRF_COOKIE_NAME].value} if csrf and settings.CSRF_COOKIE_NAME in client.cookies else {}
        # Explicit framework reader seam; real normal socket is native SC07-007/008.
        with patch('shared_content.views.read_json_bytes', side_effect=lambda request, profile:request.body):
            return client.post(path, data=self.raw(value or self.cancel_body()), content_type='application/json', **headers)

    def ack(self, response, stage, operation, *, replay=False):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok':True, 'operationId':str(operation), 'resultId':None,
            'resultCode':'released', 'replay':replay, 'gone':False, 'editorContext':None,
            'stageId':str(stage.pk), 'outcomeKnown':True})

    def protected(self):
        excluded = {'shared_content.SharedBudget', 'shared_content.SharedReceipt',
            'shared_content.SharedIdentityReservation', 'shared_content.SharedRestoreStage',
            'shared_content.SharedBasePin'}
        return {key:value for key,value in self.state().items() if key not in excluded}

    def media_unchanged(self):
        from media_library.storage import MediaStorage
        self.assertEqual({str(file.pk):MediaStorage().manifest(file.key) for file in self.asset.files.all()}, self.files_before)

    def pins(self, stage):
        from .models import SharedBasePin
        return set(SharedBasePin.objects.filter(holder_kind='restore_stage', holder_id=stage.pk).values_list('revision_id', flat=True))

    def test_sc07_001_both_blocks_one_two_pins_metadata_only_no_content_mutation(self):
        from .models import SharedReceipt, SharedRestoreStage, SharedBasePin
        from .storage import SharedStorage
        from audit.models import AuditEvent
        with self.candidate() as evidence:
            for kind, same in (('header',True), ('footer',False)):
                with self.subTest(kind=kind):
                    stage, _ = self.prepare(kind, same=same)
                    expected = {stage.source_revision_id, stage.base_revision_id} - {None}
                    self.assertEqual(self.pins(stage), expected)
                    self.assertEqual(len(expected), 1 if same else 2)
                    before, audit, receipts = self.protected(), AuditEvent.objects.count(), SharedReceipt.objects.count()
                    other_pins = list(SharedBasePin.objects.exclude(holder_id=stage.pk).order_by('id').values())
                    other_stages = list(SharedRestoreStage.objects.exclude(pk=stage.pk).order_by('id').values())
                    blobs = [value for value in SharedStorage().inventory()['files'] if value['kind']=='blob']
                    value = self.cancel_body()
                    with patch('shared_content.services.content_html', side_effect=AssertionError('CANCEL_HTML_READ')) as reader, \
                            patch('shared_content.views.normalize_input', side_effect=AssertionError('CANCEL_CHILD')) as child:
                        response = self.cancel(kind, stage, value)
                    self.ack(response, stage, value['operationId'])
                    reader.assert_not_called(); child.assert_not_called()
                    stage.refresh_from_db()
                    self.assertEqual((stage.status, stage.terminal_actor_id, str(stage.terminal_operation_id)),
                        ('released', self.owner.pk, value['operationId']))
                    self.assertFalse(self.pins(stage))
                    self.assertEqual(self.protected(), before)
                    self.assertEqual(list(SharedBasePin.objects.exclude(holder_id=stage.pk).order_by('id').values()), other_pins)
                    self.assertEqual(list(SharedRestoreStage.objects.exclude(pk=stage.pk).order_by('id').values()), other_stages)
                    self.assertEqual([item for item in SharedStorage().inventory()['files'] if item['kind']=='blob'], blobs)
                    receipt = SharedReceipt.objects.get(pk=value['operationId'])
                    self.assertEqual((receipt.action, receipt.result_code, receipt.result_id, receipt.result_identity_kind),
                        ('restore_cancel','released',None,None))
                    self.assertRegex(receipt.reservation_book_sha256, r'^[a-f0-9]{64}$')
                    self.assertEqual(SharedReceipt.objects.count(), receipts+1)
                    self.assertEqual(AuditEvent.objects.count(), audit+1)
                    self.within_cap(); self.media_unchanged()
            self.report('SC07-001-real-cancel-both-blocks', evidence)

    def test_sc07_002_exact_replay_new_session_conflicts_and_result(self):
        from .models import SharedReceipt
        with self.candidate():
            stage, _ = self.prepare()
            other, _ = self.prepare('footer')
            value = self.cancel_body(); self.ack(self.cancel('header',stage,value),stage,value['operationId'])
            before = self.state()
            self.owner_client = self.login('nesadmin', H.OWNER_PASSWORD)
            with patch('shared_content.services.content_html', side_effect=AssertionError('REPLAY_HTML')):
                self.ack(self.cancel('header',stage,value),stage,value['operationId'],replay=True)
                result = self.owner_client.get('/manage/shared/header/result/%s/' % value['operationId'])
                self.ack(result,stage,value['operationId'],replay=True)
            for kind, target in (('footer',other), ('header',uuid4())):
                denied = self.cancel(kind,target,value)
                self.assertEqual((denied.status_code,denied.json()['code']), (409,'SHARED_OPERATION_CONFLICT'))
            self.assertEqual(self.state(),before)
            self.assertEqual(SharedReceipt.objects.filter(pk=value['operationId']).count(),1)
            foreign = self.employee_client.get('/manage/shared/header/result/%s/' % value['operationId'])
            self.assertEqual(foreign.status_code,403)

    def test_sc07_003_roles_csrf_and_closed_dto_preserve_stage(self):
        from django.contrib.sessions.models import Session
        with self.candidate():
            stage, _ = self.prepare()
            value = self.cancel_body(); before = self.state()
            for client, csrf, status in ((self.visitor,False,401),(self.employee_client,True,403),(self.owner_client,False,403)):
                with self.subTest(status=status,csrf=csrf):
                    self.assertEqual(self.cancel('header',stage,value,client=client,csrf=csrf).status_code,status)
                    self.assertEqual(self.state(),before)
            for changed in ({'generation':True},{'confirmCancel':False},{'extra':1},{'protocol':'other'}):
                denied = self.cancel('header',stage,{**value,**changed})
                self.assertEqual((denied.status_code,denied.json()['code']),(400,'SHARED_INPUT_REJECTED'))
                self.assertEqual(self.state(),before)
            denied = self.cancel('header',stage,value,query='?extra=1')
            self.assertEqual((denied.status_code,denied.json()['code']),(400,'SHARED_INPUT_REJECTED'))
            path = '/manage/shared/header/stages/%s/cancel/' % stage.pk
            self.assertEqual(self.owner_client.get(path).status_code,405)
            self.assertEqual(self.state(),before)
            session_key=self.owner_client.cookies[settings.SESSION_COOKIE_NAME].value
            Session.objects.filter(session_key=session_key).delete()
            self.assertEqual(self.cancel('header',stage,value).status_code,401)
            self.assertEqual(self.state(),before)
            self.owner_client=self.login('nesadmin',H.OWNER_PASSWORD)
            self.ack(self.cancel('header',stage,value),stage,value['operationId'])

    def test_sc07_004_stale_current_allowed_but_missing_terminal_wrongblock_pins_denied(self):
        from .models import SharedBasePin,SharedRestoreStage
        with self.candidate():
            stage, _ = self.prepare()
            self.apply_text('header','CURRENT-AFTER-STAGE')
            before = self.protected(); value = self.cancel_body()
            self.ack(self.cancel('header',stage,value),stage,value['operationId'])
            self.assertEqual(self.protected(),before)
            denied_before = self.state()
            for kind, target in (('header',stage),('header',uuid4()),('footer',stage)):
                denied = self.cancel(kind,target)
                self.assertEqual((denied.status_code,denied.json()['code']),(409,'SHARED_SOURCE_UNAVAILABLE'))
                self.assertEqual(self.state(),denied_before)
            held, _ = self.prepare('footer')
            pin = SharedBasePin.objects.filter(holder_id=held.pk).first()
            models.QuerySet(model=SharedBasePin,using='default').filter(pk=pin.pk).delete()
            corrupted = self.state()
            denied = self.cancel('footer',held)
            self.assertEqual((denied.status_code,denied.json()['code']),(409,'SHARED_SOURCE_UNAVAILABLE'))
            self.assertEqual(self.state(),corrupted)
            self.assertTrue(self.pins(held))
            # Typed metadata fixtures, not a fabricated owner role/session.
            for changes in ({'actor_id':self.employee.pk},{'actor_generation':2}):
                owned,_=self.prepare('header',draft=False)
                models.QuerySet(model=SharedRestoreStage,using='default').filter(pk=owned.pk).update(**changes)
                incompatible=self.state()
                refused=self.cancel('header',owned)
                self.assertEqual((refused.status_code,refused.json()['code']),(409,'SHARED_SOURCE_UNAVAILABLE'))
                self.assertEqual(self.state(),incompatible)

    def test_sc07_005_real_rollback_abort_and_postcommit_unknown_reconcile(self):
        from . import reservations
        from .models import SharedBudget,SharedReceipt
        with self.candidate() as evidence:
            stage, _ = self.prepare(); before,pins = self.protected(),self.pins(stage)
            value = self.cancel_body(); original = reservations._fault_boundary; hits=[]
            def fail_metadata(phase):
                if phase=='metadata_written':
                    hits.append(phase); self.assertTrue(connection.in_atomic_block)
                    raise OSError('SC07_METADATA_FAILURE')
                return original(phase)
            with patch('shared_content.reservations._fault_boundary',side_effect=fail_metadata):
                response=self.cancel('header',stage,value)
            self.assertEqual(hits,['metadata_written'])
            self.assertEqual((response.status_code,response.json()['code']),(409,'SHARED_OPERATION_ABORTED'))
            self.assertTrue(response.json()['outcomeKnown']); stage.refresh_from_db()
            self.assertEqual(stage.status,'held'); self.assertEqual(self.pins(stage),pins); self.assertEqual(self.protected(),before)
            debt=SharedBudget.objects.get(singleton=True).retained_debt_bytes
            self.assertGreater(debt,0); self.assertEqual(SharedReceipt.objects.get(pk=value['operationId']).result_code,'aborted')
            again=self.cancel('header',stage,value); self.assertEqual(again.status_code,409)
            self.assertEqual(SharedBudget.objects.get(singleton=True).retained_debt_bytes,debt)
            value=self.cancel_body(); hits.clear()
            def fail_ack(phase):
                if phase=='db_committed':
                    self.assertFalse(connection.in_atomic_block); hits.append(phase)
                    raise OSError('SC07_LOST_ACK')
                return original(phase)
            with patch('shared_content.reservations._fault_boundary',side_effect=fail_ack):
                unknown=self.cancel('header',stage,value)
            self.assertEqual(hits,['db_committed']); self.assertEqual((unknown.status_code,unknown.json()['code']),(503,'SHARED_RESERVATION_UNCERTAIN'))
            self.assertFalse(unknown.json()['outcomeKnown']); stage.refresh_from_db(); self.assertEqual(stage.status,'released')
            self.assertFalse(self.pins(stage)); self.assertTrue(SharedReceipt.objects.filter(pk=value['operationId'],result_code='released').exists())
            self.ack(self.cancel('header',stage,value),stage,value['operationId'],replay=True)
            self.assertEqual(self.protected(),before); self.assertEqual(SharedBudget.objects.get(singleton=True).retained_debt_bytes,debt)
            self.within_cap(); self.report('SC07-005-abort-debt-and-real-commit-unknown',evidence)

    def test_sc07_005_cancel_wins_real_cross_connection_apply_race(self):
        from . import reservations
        from .models import SharedRestoreStage
        reached, release = Event(),Event()
        with self.candidate():
            stage,selected=self.prepare(); apply=self.intent('header',self.fixture('header','RACE-MUST-NOT-PUBLISH'),context=selected)
            value=self.cancel_body(); before=self.protected(); original=reservations._fault_boundary
            token=self.owner_client.cookies[settings.SESSION_COOKIE_NAME].value
            def boundary(phase):
                if phase=='book_durable':
                    self.assertFalse(connection.in_atomic_block)
                    reached.set()
                    if not release.wait(10): raise RuntimeError('SC07_RACE_RELEASE_DEADLINE')
                return original(phase)
            def cancel_worker():
                from django.contrib.auth import get_user_model
                from .commands import cancel_restore_stage
                try:
                    with self.candidate():
                        actor=get_user_model().objects.get(pk=self.owner.pk)
                        # Real command/PG race, without taking the HTTP heavy
                        # slot first: the competing real handler reaches lease.
                        result=cancel_restore_stage(actor=actor,kind='header',generation=1,
                            stage_id=stage.pk,operation_id=value['operationId'],confirmed=True,session_key=token)
                        return result,connection.connection.info.backend_pid
                finally: connections.close_all()
            with patch('shared_content.reservations._fault_boundary',side_effect=boundary),ThreadPoolExecutor(max_workers=1) as executor:
                future=executor.submit(cancel_worker)
                try:
                    self.assertTrue(reached.wait(10))
                    loser=self.send('header','apply',apply,context=selected)
                    self.assertEqual((loser.status_code,loser.json()['code']),(503,'SHARED_RESERVATION_BUSY'))
                finally: release.set()
                result,pid=future.result(timeout=15)
            self.assertEqual(result['resultCode'],'released')
            self.assertNotEqual(pid,connection.connection.info.backend_pid)
            self.assertEqual(SharedRestoreStage.objects.get(pk=stage.pk).status,'released')
            self.assertFalse(self.pins(stage)); self.assertEqual(self.protected(),before)

    def test_sc07_006_unknown_book_held_and_profile_off_do_not_force_cancel(self):
        from . import profiles,services
        from .journal import SharedJournal
        from .models import SharedReceipt
        with self.candidate() as evidence:
            stage,_=self.prepare(); before=self.protected(); pins=self.pins(stage)
            book={'bookSchema':'shared-held-book-v1','profileId':evidence['profileId'],
                'operationId':str(uuid4()),'blockId':str(stage.block_id),'action':'restore_cancel',
                'actorId':self.owner.pk,'generation':1,'inputFingerprint':services.digest({'fixture':'SC07-UNKNOWN'}),
                'sourceStamp':'0'*64,'reservedBytes':4194304,'snapshotIncrement':0}
            SharedJournal().create_or_replay(book)
            self.assertFalse(SharedReceipt.objects.filter(pk=book['operationId']).exists())
            response=self.cancel('header',stage)
            self.assertEqual((response.status_code,response.json()['code']),(503,'SHARED_RESERVATION_UNCERTAIN'))
            self.assertEqual(self.protected(),before); self.assertEqual(self.pins(stage),pins)
            self.assertEqual(SharedJournal().read(book['operationId'])['book'],book)
            self.report('SC07-006-actual-held-unknown-no-bypass',evidence)
        self.assertIsNone(profiles.profile())
        outside=self.cancel('header',stage)
        self.assertEqual(outside.status_code,503)
        self.assertEqual(self.protected(),before); self.assertEqual(self.pins(stage),pins)
