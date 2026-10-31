"""Offline configuration audit, not a production deployment plan."""
from .base import *
SECRET_KEY = credential('ESTAKADA_DJANGO_SECRET_FILE','django-secret-key','/run/secrets/deployment-django-secret')
SECRET_REFERENCE_ID = 'isolated:deployment-audit:django-secret'
ALLOWED_HOSTS = ['estakada.invalid']
SESSION_COOKIE_NAME = 'estakada_audit_session'
CSRF_COOKIE_NAME = 'estakada_audit_csrf'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
