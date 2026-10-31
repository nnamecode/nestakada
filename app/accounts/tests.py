from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier, Event, current_thread
from urllib.parse import urlencode
from unittest.mock import patch
import re
import subprocess
import sys
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, close_old_connections, transaction
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from audit.models import AuditEvent
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from content.models import Page, Route
from . import services
from .models import UserProfile, PageGrant, AuthSession, LoginThrottle, AuthResourceState

FAST_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher','django.contrib.auth.hashers.PBKDF2PasswordHasher']
PASSWORD='SYNTHETIC-password-only-for-tests'
OTHER='SYNTHETIC-changed-password-only'

class FormClient(Client):
    def post(self,path,data=None,content_type=None,**kwargs):
        if content_type is None:
            return super().post(path,data=data,**kwargs)
        if content_type=='application/x-www-form-urlencoded' and isinstance(data,dict):
            data=urlencode(data,doseq=True)
        return super().post(path,data=data,content_type=content_type,**kwargs)

def client(csrf=False):
    return FormClient(enforce_csrf_checks=csrf,HTTP_HOST='localhost')

def login(browser, username='auth-employee', password=PASSWORD, ip='192.0.2.10', **headers):
    return browser.post('/manage/login/',{'username':username,'password':password},content_type='application/x-www-form-urlencoded',REMOTE_ADDR=ip,**headers)

@override_settings(PASSWORD_HASHERS=FAST_HASHERS,AUTH_TRUSTED_PROXY_HOST=None)
class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=services.bootstrap_owner(PASSWORD)
        cls.employee=services.create_employee(actor=cls.owner,username='auth-employee',password=PASSWORD)
    def setUp(self):
        self.now=timezone.now()
        patcher=patch('accounts.clock.now',return_value=self.now)
        self.frozen=patcher.start();self.addCleanup(patcher.stop)
    def signed(self, owner=False):
        browser=client();self.assertEqual(login(browser,'nesadmin' if owner else 'auth-employee').status_code,303)
        return browser

    def test_anonymous_login_get_has_no_db_session_or_throttle(self):
        browser=client();response=browser.get('/manage/login/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'name="csrfmiddlewaretoken"')
        self.assertEqual(Session.objects.count(),0);self.assertEqual(LoginThrottle.objects.count(),0)
        self.assertEqual(browser.get('/manage/').status_code,401)

    def test_both_roles_login_identity_logout_and_private_headers(self):
        for username in ['nesadmin','auth-employee']:
            browser=client();self.assertEqual(login(browser,username).status_code,303)
            response=browser.get('/manage/')
            self.assertContains(response,username)
            self.assertEqual(response['Cache-Control'],'private, no-store')
            self.assertIn('Cookie',response['Vary'])
            self.assertEqual(browser.post('/manage/logout/',{},content_type='application/x-www-form-urlencoded').status_code,303)
            self.assertEqual(browser.get('/manage/').status_code,401)

    def test_unknown_wrong_disabled_and_blocked_have_one_safe_failure(self):
        browser=client()
        unknown=login(browser,'absent','bad')
        wrong=login(browser,password='bad')
        services.set_active(actor=self.owner,employee=self.employee,active=False)
        disabled=login(browser)
        for response in [unknown,wrong,disabled]:
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'data-login-error')
            self.assertNotContains(response,PASSWORD)
            self.assertNotContains(response,'SYNTHETIC')
        self.assertEqual(AuthSession.objects.count(),0)

    def test_five_failures_are_per_ip_across_accounts_and_not_global_login(self):
        a,b=client(),client()
        for username in ['auth-employee']*3+['nesadmin']*2:login(a,username,'bad')
        row=LoginThrottle.objects.get(pk='192.0.2.10')
        self.assertEqual(row.failed_count,5);self.assertEqual(row.blocked_until,self.now+timedelta(seconds=900))
        self.assertEqual(login(a).status_code,200)
        self.assertEqual(login(b,ip='192.0.2.11').status_code,303)
        self.assertEqual(a.get('/manage/').status_code,401)
        self.assertEqual(b.get('/manage/').status_code,200)

    def test_four_then_success_clears_only_its_source(self):
        browser=client()
        for _ in range(4):login(browser,password='bad')
        login(client(),password='bad',ip='192.0.2.11')
        self.assertEqual(login(browser).status_code,303)
        self.assertEqual(LoginThrottle.objects.get(pk='192.0.2.10').failed_count,0)
        self.assertEqual(LoginThrottle.objects.get(pk='192.0.2.11').failed_count,1)
        aggregate=AuditEvent.objects.get(code='AUTH_LOGIN_FAILED_AGGREGATE',ip_address='192.0.2.10')
        self.assertEqual(aggregate.occurrence_count,3)

    def test_rolling_window_and_block_expiry(self):
        for age,blocked in [(599,True),(601,False)]:
            LoginThrottle.objects.all().delete()
            LoginThrottle.objects.create(ip_address='192.0.2.10',failure_times=[(self.now-timedelta(seconds=age)).isoformat()]*4,last_seen=self.now-timedelta(seconds=age),expires_at=self.now+timedelta(seconds=1000))
            login(client(),password='bad')
            row=LoginThrottle.objects.get(pk='192.0.2.10')
            self.assertEqual(row.blocked_until is not None,blocked)
        for age,accepted in [(899,False),(901,True)]:
            LoginThrottle.objects.all().delete()
            stamp=self.now-timedelta(seconds=age)
            LoginThrottle.objects.create(ip_address='192.0.2.10',failure_times=[stamp.isoformat()]*5,last_seen=stamp,blocked_until=stamp+timedelta(seconds=900),expires_at=stamp+timedelta(seconds=900))
            self.assertEqual(login(client()).status_code==303,accepted)

    def test_forwarded_input_from_untrusted_peer_cannot_change_source(self):
        login(client(),password='bad',HTTP_X_REAL_IP='203.0.113.1',HTTP_X_FORWARDED_FOR='203.0.113.2')
        self.assertTrue(LoginThrottle.objects.filter(pk='192.0.2.10').exists())
        self.assertFalse(LoginThrottle.objects.filter(pk='203.0.113.1').exists())

    @override_settings(AUTH_TRUSTED_PROXY_HOST='ingress')
    def test_only_verified_proxy_peer_can_supply_single_ip(self):
        addr=[(2,1,6,'',('192.0.2.10',0))]
        with patch('accounts.services.socket.getaddrinfo',return_value=addr):
            self.assertEqual(login(client(),HTTP_X_REAL_IP='203.0.113.1').status_code,303)
        self.assertTrue(LoginThrottle.objects.filter(pk='203.0.113.1').exists())
        with patch('accounts.services.socket.getaddrinfo',return_value=addr):
            self.assertEqual(login(client(),HTTP_X_REAL_IP='fe80::1%SECRET').status_code,200)
        self.assertFalse(LoginThrottle.objects.filter(pk='fe80::1').exists())

    def test_idle_boundaries_and_passive_status_does_not_keep_session_alive(self):
        browser=self.signed();state=AuthSession.objects.get(user=self.employee)
        self.frozen.return_value=self.now+timedelta(seconds=1799)
        self.assertEqual(browser.get('/manage/session/').status_code,200)
        state.refresh_from_db();self.assertEqual(state.last_seen,self.now)
        self.frozen.return_value=self.now+timedelta(seconds=1801)
        self.assertEqual(browser.get('/manage/').status_code,401)
        self.assertEqual(AuthSession.objects.filter(user=self.employee).count(),0)
        self.assertEqual(AuditEvent.objects.filter(code='AUTH_SESSION_EXPIRED').count(),1)
        browser.get('/manage/');self.assertEqual(AuditEvent.objects.filter(code='AUTH_SESSION_EXPIRED').count(),1)

    def test_absolute_limit_survives_regular_activity(self):
        browser=self.signed()
        AuthSession.objects.filter(user=self.employee).update(last_seen=self.now+timedelta(seconds=43150))
        self.frozen.return_value=self.now+timedelta(seconds=43199)
        self.assertEqual(browser.get('/manage/').status_code,200)
        self.frozen.return_value=self.now+timedelta(seconds=43201)
        self.assertEqual(browser.get('/manage/').status_code,401)

    def test_password_reset_revokes_old_sessions_and_old_password(self):
        browser=self.signed()
        services.reset_password(actor=self.owner,employee=self.employee,password=OTHER)
        self.assertEqual(browser.get('/manage/').status_code,401)
        self.assertEqual(login(client(),password=PASSWORD).status_code,200)
        self.assertEqual(login(client(),password=OTHER).status_code,303)
        self.assertEqual(AuditEvent.objects.filter(code='AUTH_EMPLOYEE_PASSWORD_RESET').count(),1)

    def test_disable_and_reenable_do_not_revive_old_session(self):
        browser=self.signed();services.set_active(actor=self.owner,employee=self.employee,active=False)
        self.assertEqual(browser.get('/manage/').status_code,401)
        self.assertEqual(login(client()).status_code,200)
        services.set_active(actor=self.owner,employee=self.employee,active=True)
        self.assertEqual(browser.get('/manage/').status_code,401)
        self.assertEqual(login(client()).status_code,303)

    def test_native_superuser_flag_is_not_owner_authority(self):
        self.employee.is_superuser=True;self.employee.is_staff=True;self.employee.save()
        browser=self.signed()
        self.assertEqual(browser.get('/manage/employees/').status_code,403)
        with self.assertRaises(PermissionDenied):services.create_employee(actor=self.employee,username='bad',password=OTHER)

    def test_employee_cannot_self_reset_or_manage_users_by_direct_post(self):
        browser=self.signed();before=get_user_model().objects.get(pk=self.employee.pk).password
        self.assertEqual(browser.post('/manage/employees/'+str(self.employee.pk)+'/password/',{'password':OTHER},content_type='application/x-www-form-urlencoded').status_code,403)
        self.assertEqual(browser.post('/manage/password/',{'password':OTHER}).status_code,404)
        self.assertEqual(get_user_model().objects.get(pk=self.employee.pk).password,before)

    def test_grants_are_page_scoped_default_price_off_and_immediately_revoked(self):
        a=Page.objects.create(name='Статья',kind=Page.Kind.ARTICLE)
        b=Page.objects.create(name='Услуга',kind=Page.Kind.SERVICE)
        services.set_grant(actor=self.owner,employee=self.employee,page=a,intro_text=True)
        self.assertEqual(services.allowed_fields(self.employee,a),('intro_text',))
        browser=self.signed();self.assertEqual(browser.get('/manage/pages/'+str(a.pk)+'/').status_code,200)
        self.assertEqual(browser.get('/manage/pages/'+str(b.pk)+'/').status_code,403)
        services.set_grant(actor=self.owner,employee=self.employee,page=a,revoke=True)
        self.assertEqual(browser.get('/manage/pages/'+str(a.pk)+'/').status_code,403)
        self.assertFalse(PageGrant.objects.filter(user=self.employee,page=a).exists())

    def test_grants_reject_home_protected_fields_and_forged_types(self):
        home=Page.objects.create(name='Главная',kind=Page.Kind.HOME)
        with self.assertRaises(ValidationError):services.set_grant(actor=self.owner,employee=self.employee,page=home,main_text=True)
        self.assertEqual(PageGrant.objects.count(),0)
        with self.assertRaises(TypeError):services.set_grant(actor=self.owner,employee=self.employee,page=home,seo=True)
        with self.assertRaises(ValidationError):services.set_grant(actor=self.owner,employee=self.employee,page=home,main_text='on')

    def test_stale_owner_generation_cannot_manage_employee(self):
        generation=UserProfile.objects.get(user=self.owner).generation
        services.recover_owner(OTHER)
        with self.assertRaises(PermissionDenied):services.create_employee(actor=self.owner,username='new-user',password=OTHER,expected_generation=generation)

    def test_login_csrf_and_unsupported_multipart_fail_without_state_change(self):
        browser=client(csrf=True)
        self.assertEqual(browser.post('/manage/login/',{'username':'nesadmin','password':PASSWORD}).status_code,403)
        response=browser.get('/manage/login/')
        token=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',response.content.decode()).group(1)
        response=browser.post('/manage/login/',{'username':'nesadmin','password':PASSWORD,'csrfmiddlewaretoken':token})
        self.assertEqual(response.status_code,200);self.assertContains(response,'data-login-error')
        self.assertEqual(LoginThrottle.objects.count(),0)
        self.assertEqual(AuthSession.objects.count(),0)

    def test_duplicate_or_unexpected_form_fields_do_not_authenticate(self):
        browser=client()
        response=browser.post('/manage/login/','username=nesadmin&username=other&password=anything',content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code,200);self.assertEqual(AuthSession.objects.count(),0)
        response=browser.post('/manage/login/',{'username':'nesadmin','password':PASSWORD,'role':'owner'},content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code,200);self.assertEqual(AuthSession.objects.count(),0)

    def test_failed_login_audit_is_bounded_and_has_aggregate_counts(self):
        browser=client()
        for _ in range(5):login(browser,password='SYNTHETIC-RAW-SECRET')
        self.assertEqual(AuditEvent.objects.filter(code='AUTH_LOGIN_FAILED').count(),1)
        self.assertEqual(AuditEvent.objects.filter(code='AUTH_IP_LIMITED').count(),1)
        before=AuditEvent.objects.count()
        for _ in range(3):login(browser,password=PASSWORD)
        self.assertEqual(AuditEvent.objects.count(),before)
        self.assertEqual(LoginThrottle.objects.get().blocked_repeats,3)
        self.frozen.return_value=self.now+timedelta(seconds=901)
        self.assertEqual(login(browser).status_code,303)
        aggregate=AuditEvent.objects.get(code='AUTH_BLOCKED_AGGREGATE')
        self.assertEqual(aggregate.occurrence_count,3)
        self.assertFalse(aggregate.count_is_lower_bound)
        self.assertNotIn('SYNTHETIC',str(list(AuditEvent.objects.values())))

    def test_permission_denials_are_grouped_without_logging_anonymous_gets(self):
        before=AuditEvent.objects.count()
        for _ in range(3):client().get('/manage/employees/')
        self.assertEqual(AuditEvent.objects.count(),before)
        browser=self.signed()
        for _ in range(3):self.assertEqual(browser.get('/manage/employees/').status_code,403)
        self.assertEqual(AuditEvent.objects.filter(code='SEC_PERMISSION_DENIED').count(),1)
        browser.post('/manage/logout/',{},content_type='application/x-www-form-urlencoded')
        self.assertEqual(AuditEvent.objects.get(code='SEC_PERMISSION_DENIED_AGGREGATE').occurrence_count,2)

    @override_settings(AUTH_SESSION_CAP=1)
    def test_session_capacity_preserves_existing_session_and_recovers_after_logout(self):
        first=self.signed(owner=True)
        self.assertEqual(login(client()).status_code,200)
        self.assertEqual(AuthSession.objects.count(),1)
        self.assertEqual(first.get('/manage/').status_code,200)
        first.post('/manage/logout/',{},content_type='application/x-www-form-urlencoded')
        self.assertEqual(login(client()).status_code,303)
        self.assertEqual(AuditEvent.objects.filter(code='AUTH_CAPACITY_REACHED').count(),1)

    @override_settings(AUTH_THROTTLE_CAP=1)
    def test_throttle_capacity_never_evicts_live_key_and_expiry_recovers(self):
        login(client(),password='bad')
        self.assertEqual(login(client(),ip='192.0.2.11').status_code,200)
        self.assertEqual(LoginThrottle.objects.count(),1)
        self.assertTrue(LoginThrottle.objects.filter(pk='192.0.2.10').exists())
        self.frozen.return_value=self.now+timedelta(seconds=601)
        self.assertEqual(login(client(),ip='192.0.2.11').status_code,303)
        self.assertFalse(LoginThrottle.objects.filter(pk='192.0.2.10').exists())

    def test_audit_failure_rolls_back_login_and_cannot_be_saved_by_middleware(self):
        browser=client()
        with patch('accounts.services.event',side_effect=DatabaseError('SYNTHETIC-PRIVATE-DB')):
            response=login(browser)
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'SYNTHETIC-PRIVATE-DB')
        self.assertEqual(AuthSession.objects.count(),0)
        self.assertEqual(Session.objects.count(),0)
        self.assertEqual(browser.get('/manage/').status_code,401)

    def test_login_calls_password_verification_even_for_blocked_source(self):
        browser=client()
        for _ in range(5):login(browser,password='bad')
        with patch('accounts.services.check_password',return_value=False) as check:
            login(browser,'absent',PASSWORD);login(browser,'nesadmin',PASSWORD)
        self.assertEqual(check.call_count,2)

    def test_reserved_private_namespace_cannot_be_public_page(self):
        obj=Page.objects.create(name='Статья',kind=Page.Kind.ARTICLE)
        for target in ['/manage','/manage/login/','/manage/employees/']:
            with self.assertRaises(ValidationError):Route.objects.create(page=obj,target=target,kind=Route.Kind.PRIMARY,is_legacy=True)

    def test_private_errors_and_get_mutations_have_no_cache_or_side_effects(self):
        browser=self.signed(owner=True);before=get_user_model().objects.count()
        for url in ['/manage/no-such-route/','/manage/logout/','/manage/employees/'+str(self.employee.pk)+'/active/']:
            response=browser.get(url)
            self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual(get_user_model().objects.count(),before)
        self.employee.refresh_from_db();self.assertTrue(self.employee.is_active)

    def test_mistaken_console_password_argument_is_not_echoed(self):
        canary='SYNTHETIC-CLI-ARG-CANARY'
        for command in ['create_owner','recover_owner']:
            process=subprocess.run([sys.executable,'manage.py',command,canary],capture_output=True,text=True,timeout=15)
            self.assertNotEqual(process.returncode,0)
            self.assertNotIn(canary,process.stdout+process.stderr)
            with self.assertRaises(CommandError) as failure:
                call_command(command,canary,stdout=StringIO(),stderr=StringIO())
            self.assertNotIn(canary,str(failure.exception))

    def test_local_owner_recovery_is_interactive_hides_password_and_revokes_sessions(self):
        browser=self.signed(owner=True);output=StringIO()
        with patch('sys.stdin.isatty',return_value=False),self.assertRaises(CommandError):call_command('recover_owner',stdout=output)
        with patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',side_effect=[OTHER,OTHER]):
            call_command('recover_owner',stdout=output)
        self.assertNotIn(OTHER,output.getvalue())
        self.assertEqual(browser.get('/manage/').status_code,401)
        self.owner.refresh_from_db();self.assertTrue(self.owner.check_password(OTHER))
        with self.assertRaises(CommandError):call_command('recover_owner','nesadmin',OTHER,stdout=output)

    def test_trusted_compromise_restore_hook_invalidates_all(self):
        a,b=self.signed(owner=True),self.signed()
        services.invalidate_all_sessions()
        self.assertEqual(a.get('/manage/').status_code,401);self.assertEqual(b.get('/manage/').status_code,401)
        self.assertEqual(AuthSession.objects.count(),0)

    def test_audit_occurrence_counter_is_strict_typed_and_database_bounded(self):
        values=dict(category=Category.ACCESS,event_code='AUTH_TEST',level=Level.INFO,source=Source.APPLICATION,result=Result.DENIED)
        for count in [True,0,-1,2**63,'3']:
            with self.assertRaises(ValidationError):record_event(**values,occurrence_count=count)
        self.assertEqual(record_event(**values,occurrence_count=3,count_is_lower_bound=True).occurrence_count,3)

class DefaultHashTests(TestCase):
    def test_real_default_password_hash_is_django_pbkdf2_not_plaintext(self):
        owner=services.bootstrap_owner(PASSWORD)
        self.assertTrue(owner.password.startswith('pbkdf2_sha256$'))
        self.assertNotIn(PASSWORD,owner.password)
        self.assertTrue(owner.check_password(PASSWORD))

@override_settings(PASSWORD_HASHERS=FAST_HASHERS,AUTH_TRUSTED_PROXY_HOST=None)
class AccountConcurrencyTests(TransactionTestCase):
    def test_concurrent_session_touch_cannot_expire_an_earlier_request(self):
        from django.contrib.sessions.backends.db import SessionStore
        owner=services.bootstrap_owner(PASSWORD)
        employee=services.create_employee(actor=owner,username='auth-employee',password=PASSWORD)
        browser=client();self.assertEqual(login(browser).status_code,303)
        state=AuthSession.objects.get(user=employee)
        initial=state.last_seen
        times={'now':initial}
        entered,finished=Event(),Event()
        real_lock=services.lock_auth
        def controlled_lock():
            if current_thread().name=='session-A':
                entered.set()
                if not finished.wait(timeout=10):raise RuntimeError('session schedule timeout')
            real_lock()
        def request(label):
            close_old_connections();current_thread().name='session-'+label
            try:
                if label=='B':
                    if not entered.wait(timeout=10):raise RuntimeError('session schedule timeout')
                    times['now']=initial+timedelta(seconds=1)
                req=RequestFactory().get('/manage/')
                req.user=get_user_model().objects.get(pk=employee.pk)
                req.session=SessionStore(session_key=state.pk)
                result=services.require_session(req).pk
                return result
            finally:
                if label=='B':finished.set()
                close_old_connections()
        with patch('accounts.services.lock_auth',side_effect=controlled_lock),patch('accounts.clock.now',side_effect=lambda:times['now']):
            with ThreadPoolExecutor(max_workers=2) as pool:
                a,b=pool.submit(request,'A'),pool.submit(request,'B')
                self.assertEqual(a.result(),employee.pk);self.assertEqual(b.result(),employee.pk)
        self.assertEqual(AuthSession.objects.filter(pk=state.pk).count(),1)

    def test_parallel_failures_do_not_lose_the_fifth_attempt(self):
        owner=services.bootstrap_owner(PASSWORD)
        services.create_employee(actor=owner,username='auth-employee',password=PASSWORD)
        barrier=Barrier(5)
        def fail(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return login(client(),password='bad').status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(fail,range(5)))
        self.assertEqual(results,[200]*5)
        row=LoginThrottle.objects.get(pk='192.0.2.10')
        self.assertEqual(row.failed_count,5);self.assertIsNotNone(row.blocked_until)
        self.assertEqual(AuditEvent.objects.filter(code='AUTH_IP_LIMITED').count(),1)
