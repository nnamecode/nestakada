"""D-311 isolated local HTTP profile."""
import os
from .base import *
ENVIRONMENT = os.environ.get('ESTAKADA_LOCAL_ENV','test')
if ENVIRONMENT not in ('dev','test'):
    raise ImproperlyConfigured('Unknown isolated local environment')
SECRET_KEY = credential('ESTAKADA_DJANGO_SECRET_FILE','django-secret-key','/run/secrets/django-secret')
SECRET_REFERENCE_ID = f'{ENVIRONMENT}:local-http:django-secret'
ALLOWED_HOSTS = ['localhost','127.0.0.1','host.docker.internal']
SESSION_COOKIE_NAME = f'estakada_{ENVIRONMENT}_session'
CSRF_COOKIE_NAME = f'estakada_{ENVIRONMENT}_csrf'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

AUTH_TRUSTED_PROXY_HOST = "ingress"

# D-408: opt-in local preparation only. Publication/TRUST admission is separate.
if os.environ.get('ESTAKADA_DEV29_CREATE', '') == '1':
    if ENVIRONMENT != 'test':
        raise ImproperlyConfigured('Page creation is limited to the isolated test profile')
    DEV29_LOCAL_CREATE_ENABLED = True
