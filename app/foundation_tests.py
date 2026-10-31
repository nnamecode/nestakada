"""Security behavior of the local foundation, without implementing later flows."""
import os
import subprocess
import sys
from django.conf import settings
from django.test import Client, SimpleTestCase

class FoundationConfigurationTests(SimpleTestCase):
    def test_actual_framework_headers_and_unknown_host(self):
        client=Client()
        good=client.get('/',HTTP_HOST='localhost')
        self.assertEqual(good.status_code,404)
        self.assertEqual(good.headers['X-Frame-Options'],'DENY')
        self.assertEqual(good.headers['X-Content-Type-Options'],'nosniff')
        self.assertIn("default-src 'self'",good.headers['Content-Security-Policy-Report-Only'])
        self.assertEqual(client.get('/',HTTP_HOST='untrusted.invalid').status_code,400)

    def test_forwarded_input_does_not_change_framework_trust(self):
        response=Client().get('/',HTTP_HOST='localhost',HTTP_X_FORWARDED_PROTO='https',HTTP_X_FORWARDED_HOST='untrusted.invalid')
        self.assertEqual(response.status_code,404)
        self.assertFalse(response.wsgi_request.is_secure())
        self.assertEqual(response.wsgi_request.get_host(),'localhost')

    def test_missing_credentials_cannot_start_with_fallback(self):
        secrets=[settings.SECRET_KEY,settings.DATABASES['default']['PASSWORD']]
        for key in ['ESTAKADA_DJANGO_SECRET_FILE','ESTAKADA_DB_PASSWORD_FILE']:
            with self.subTest(key=key):
                env=os.environ.copy();env[key]='/run/secrets/credential-does-not-exist'
                result=subprocess.run([sys.executable,'manage.py','check'],env=env,capture_output=True,text=True,timeout=10)
                self.assertNotEqual(result.returncode,0)
                output=result.stdout+result.stderr
                self.assertIn('Required isolated credential unavailable',output)
                self.assertFalse(any(secret in output for secret in secrets),'credential appeared in startup diagnostics')

    def test_invalid_database_identity_fails_closed(self):
        env=os.environ.copy();env['ESTAKADA_DB_NAME']=''
        result=subprocess.run([sys.executable,'manage.py','check'],env=env,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Invalid isolated database identity',result.stdout+result.stderr)
