"""Fail-closed shared foundation; production infrastructure is not selected."""
import os
import re
import stat
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
DEBUG = False

def credential(variable, purpose, default):
    """Read only bounded own mounted credentials; never echo contents or paths."""
    path = Path(os.environ.get(variable, default))
    if path.parent != Path('/run/secrets') or not path.name or path.name in ('.', '..'):
        raise ImproperlyConfigured(f'Invalid isolated credential reference ({purpose})')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 32 <= info.st_size <= 4096:
                raise ValueError('size/type')
            value = stream.read(4097).decode('ascii').strip()
        if len(value) < 32 or any(ord(char) < 33 or ord(char) > 126 for char in value):
            raise ValueError('format')
        return value
    except (OSError, UnicodeError, ValueError):
        raise ImproperlyConfigured(f'Required isolated credential unavailable ({purpose})') from None

INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','audit.apps.AuditConfig','content.apps.ContentConfig','accounts.apps.AccountsConfig','media_library.apps.MediaLibraryConfig','page_versions.apps.PageVersionsConfig']
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
    'accounts.middleware.PrivateCacheMiddleware',
    'accounts.middleware.PrivateAccessMiddleware',
    'media_library.middleware.MediaBodyLimitMiddleware',
]
ROOT_URLCONF = 'estakada.urls'
WSGI_APPLICATION = 'estakada.wsgi.application'
ASGI_APPLICATION = 'estakada.asgi.application'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[], 'APP_DIRS':True,
    'OPTIONS':{'autoescape':True,'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth']}}]
DB_NAME = os.environ.get('ESTAKADA_DB_NAME','estakada_foundation')
DB_USER = os.environ.get('ESTAKADA_DB_USER','app_runtime')
if not re.fullmatch(r'estakada_[a-z0-9_]{1,48}',DB_NAME) or DB_USER not in ('app_runtime','app_migrator'):
    raise ImproperlyConfigured('Invalid isolated database identity')
DATABASES = {'default':{
    'ENGINE':'django.db.backends.postgresql',
    'NAME':DB_NAME,
    'USER':DB_USER,
    'PASSWORD':credential('ESTAKADA_DB_PASSWORD_FILE','database-password','/run/secrets/database-password'),
    'HOST':'db','PORT':'5432','CONN_MAX_AGE':0,
    'OPTIONS':{'connect_timeout':5,'sslmode':'verify-full','sslrootcert':'/run/secrets/database-ca'},
    'TEST':{'NAME':'estakada_foundation_unit'},
}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'ru-ru'
USE_I18N = True
STATIC_URL = '/static/'
STATIC_ROOT = '/var/lib/estakada/static'
MEDIA_ROOT = '/var/lib/estakada/media'
MEDIA_URL = '/media/'
# D-324/D-325: the envelope is separate from the strict per-file worker limit.
DATA_UPLOAD_MAX_MEMORY_SIZE = 11 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1_000_000
DATA_UPLOAD_MAX_NUMBER_FILES = 1
SESSION_COOKIE_AGE = 43200
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_DOMAIN = None
CSRF_TRUSTED_ORIGINS = []
USE_X_FORWARDED_HOST = False
SECURE_PROXY_SSL_HEADER = None
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = 'DENY'
CONTENT_SECURITY_POLICY_REPORT_ONLY = {'DIRECTIVES':{
    'default-src':["'self'"],'script-src':["'self'"],'object-src':["'none'"],
    'base-uri':["'self'"],'frame-ancestors':["'none'"],'form-action':["'self'"],
}}
LOGGING = {'version':1,'disable_existing_loggers':False,
    'formatters':{'safe':{'()':'audit.formatters.SafeJsonFormatter'}},
    'handlers':{'safe':{'class':'logging.StreamHandler','formatter':'safe'}},
    'root':{'handlers':['safe'],'level':'INFO'},
    'loggers':{'django':{'handlers':['safe'],'level':'WARNING','propagate':False},
               'django.server':{'handlers':['safe'],'level':'WARNING','propagate':False}}}

# D-321: local, independently tested profile; not a measured VPS capacity.
AUTH_THROTTLE_CAP = 10000
AUTH_SESSION_CAP = 1000
AUTH_TRUSTED_PROXY_HOST = None
AUTH_ISOLATED_TEST = False
PRIVATE_ROUTE_PREFIX = "/manage/"
