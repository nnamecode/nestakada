"""RUI-001..006: private stage-read messages with real state and SQL controls."""
import re
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import TransactionTestCase, override_settings
from accounts.services import set_grant
from page_versions import services as V
from page_versions.models import PageRevision, VersionBasePin
from . import test_restore_terminal_http as R
from . import test_check_http as H, test_media_http as M

MESSAGES={
    'released':'Подготовка восстановления отменена. Данные для подстановки не выдаются. Текущая версия страницы не изменена этим просмотром.',
    'consumed':'Подготовка восстановления уже применена. Повторная подстановка недоступна. Текущая версия страницы не изменена этим просмотром.',
    'invalidated':'Подготовка восстановления утратила актуальность. Подготовьте восстановление заново из истории. Текущая версия страницы не изменена этим просмотром.',
}


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE,
    TEMPLATES=M.TEST_TEMPLATES, AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TerminalUiHttpTests(TransactionTestCase):
    setUp=R.RestoreTerminalHttpTests.setUp
    login=R.RestoreTerminalHttpTests.login
    payload=R.RestoreTerminalHttpTests.payload
    raw=R.RestoreTerminalHttpTests.raw
    post=R.RestoreTerminalHttpTests.post
    current=R.RestoreTerminalHttpTests.current
    draft=R.RestoreTerminalHttpTests.draft
    state=R.RestoreTerminalHttpTests.state
    selector=R.RestoreTerminalHttpTests.selector
    path=R.RestoreTerminalHttpTests.path
    send=R.RestoreTerminalHttpTests.send
    checked=R.RestoreTerminalHttpTests.checked
    commit=R.RestoreTerminalHttpTests.commit
    form_post=R.RestoreTerminalHttpTests.form_post
    make_stage=R.RestoreTerminalHttpTests.make_stage
    domain=R.RestoreTerminalHttpTests.domain
    canary=R.RestoreTerminalHttpTests.canary

    def stage_path(self, stage_id):
        return '/manage/pages/%s/versions/stages/%s/'%(self.page.pk,stage_id)

    def release(self, item):
        V.cancel_stage(actor=self.employee,page_id=self.page.pk,stage_id=item['stage'].pk,
            expected_generation=1,operation_id=uuid4())

    def no_candidate(self, response):
        for marker in ('data-stage-field','data-restore-staged','data-restore-editor','data-version-result'):
            self.assertNotIn(marker.encode(),response.content)
        self.assertNotIn(self.canary.encode(),response.content)
        self.assertNotIn(b'checkReceipt',response.content)

    def terminal(self, item, status):
        before=self.domain()
        for _ in range(2):
            response=item['client'].get(self.stage_path(item['stage'].pk))
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.context['message'],MESSAGES[status])
            self.assertContains(response,MESSAGES[status],status_code=409)
            self.no_candidate(response)
            with self.assertRaises(KeyError):response.context['prepared']
            with self.assertRaises(KeyError):response.context['result']
            self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(self.domain(),before)

    def test_rui001_released_exact_message_no_candidate_or_new_receipt(self):
        item=self.make_stage();self.release(item)
        self.terminal(item,'released')

    def test_rui002_consumed_exact_message_does_not_apply_again(self):
        item=self.make_stage();stage=item['stage']
        value,selector,_=self.checked({'intro_text':'','main_text':'<p>RUI-CONSUMED-EDIT</p>'},
                                     stage=stage,client=self.employee_client)
        self.assertEqual(self.send('save',value,selector=selector,client=self.employee_client).status_code,200)
        self.terminal(item,'consumed')

    def test_rui003_invalidated_exact_message_without_redirect_or_new_stage(self):
        item=self.make_stage();self.commit('RUI-ACTUAL-CURRENT-CHANGE')
        item['stage'].refresh_from_db();self.assertEqual(item['stage'].status,'invalidated')
        self.terminal(item,'invalidated')

    def test_rui004_held_grant_stale_read_keeps_pins_and_exact_restore_still_works(self):
        item=self.make_stage();stage=item['stage']
        pins=list(VersionBasePin.objects.filter(holder_id=stage.pk).order_by('id').values())
        set_grant(actor=self.owner,employee=self.employee,page=self.page,intro_text=True,main_text=False)
        self.terminal(item,'invalidated')  # Message only: status remains held.
        stage.refresh_from_db();self.assertEqual(stage.status,'held')
        self.assertEqual(list(VersionBasePin.objects.filter(holder_id=stage.pk).order_by('id').values()),pins)
        set_grant(actor=self.owner,employee=self.employee,page=self.page,intro_text=True,main_text=True)
        before=self.domain();restored=self.employee_client.get(self.stage_path(stage.pk))
        self.assertEqual(restored.status_code,200)
        self.assertContains(restored,self.canary)
        self.assertContains(restored,'data-restore-editor')
        self.assertEqual(self.domain(),before)

    def test_rui005_same_page_foreign_missing_rights_and_session_do_not_reveal_status(self):
        set_grant(actor=self.owner,employee=self.other,page=self.page,intro_text=True,main_text=True)
        item=self.make_stage();self.release(item)
        for actor,client in ((self.owner,self.owner_client),(self.other,self.other_client)):
            own=self.make_stage(actor=actor,client=client,source=item['source'])
            positive=client.get(self.stage_path(own['stage'].pk))
            self.assertEqual(positive.status_code,200);self.assertContains(positive,self.canary)
            before=self.domain()
            response=client.get(self.stage_path(item['stage'].pk))
            self.assertEqual(response.status_code,409);self.no_candidate(response)
            for message in MESSAGES.values():self.assertNotIn(message.encode(),response.content)
            self.assertEqual(self.domain(),before)
        before=self.domain();missing=self.employee_client.get(self.stage_path(uuid4()))
        self.assertEqual(missing.status_code,409);self.no_candidate(missing)
        for message in MESSAGES.values():self.assertNotIn(message.encode(),missing.content)
        self.assertEqual(self.domain(),before)
        set_grant(actor=self.owner,employee=self.employee,page=self.page,revoke=True)
        before=self.domain();denied=self.employee_client.get(self.stage_path(item['stage'].pk))
        self.assertEqual(denied.status_code,403);self.no_candidate(denied)
        for message in MESSAGES.values():self.assertNotIn(message.encode(),denied.content)
        self.assertEqual(self.domain(),before)
        set_grant(actor=self.owner,employee=self.employee,page=self.page,intro_text=True,main_text=True)
        Session.objects.filter(
            pk=self.employee_client.session.session_key).delete()
        before=self.domain();ended=self.employee_client.get(self.stage_path(item['stage'].pk))
        self.assertEqual(ended.status_code,401);self.no_candidate(ended)
        self.assertEqual(self.domain(),before)

    def test_rui006_metadata_only_actual_sql_detector_and_unrelated_preflight_error_not_masked(self):
        item=self.make_stage();self.release(item)
        relation=PageRevision._meta.db_table.lower();hits=[]
        def detector(execute,sql,params,many,context):
            text=sql.replace('"','').lower()
            if text.lstrip().startswith('select') and relation in text and re.search(r'\bpayload\b',text):
                hits.append('historical-payload-select')
                raise AssertionError('RUI_PAYLOAD_SQL_FORBIDDEN')
            return execute(sql,params,many,context)
        with connection.execute_wrapper(detector):
            with self.assertRaisesRegex(AssertionError,'^RUI_PAYLOAD_SQL_FORBIDDEN$'):
                PageRevision.objects.filter(pk=self.current()).values('payload').get()
        self.assertEqual(hits,['historical-payload-select']);hits.clear()
        before=self.domain()
        with connection.execute_wrapper(detector):
            response=self.employee_client.get(self.stage_path(item['stage'].pk))
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.context['message'],MESSAGES['released'])
        self.assertEqual(hits,[]);self.assertEqual(self.domain(),before)
        own=self.make_stage(source=item['source'])
        real=V.get_stage;called=[]
        def unrelated(**kwargs):
            result=real(**kwargs);self.assertIn('payload',result);called.append('actual-held-preflight')
            raise ValidationError('VERSIONS_MEDIA_UNAVAILABLE')
        before=self.domain()
        with patch('page_versions.views.V.get_stage',side_effect=unrelated):
            failure=self.employee_client.get(self.stage_path(own['stage'].pk))
        self.assertEqual(called,['actual-held-preflight'])
        self.assertEqual(failure.status_code,409)
        self.no_candidate(failure)
        self.assertContains(failure,'Версия несовместима.',status_code=409)
        for message in MESSAGES.values():self.assertNotIn(message.encode(),failure.content)
        self.assertEqual(self.domain(),before)
