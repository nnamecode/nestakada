"""Independent TRUST. No imports from the site's application."""
import os
from pathlib import Path
def secret(name):
    return Path(os.environ[name]).read_text(encoding='ascii').strip()
SECRET_KEY = secret('TRUST_DJANGO_SECRET_FILE')
DEBUG = False
ALLOWED_HOSTS = os.environ.get('TRUST_ALLOWED_HOSTS', 'trust-api,trust-ingress').split(',')
INSTALLED_APPS = ['journal']
MIDDLEWARE = []
ROOT_URLCONF = 'trust_service.urls'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.environ.get('TRUST_DB_NAME', 'estakada_trust'),
    'HOST': os.environ.get('TRUST_DB_HOST', 'trust-db'), 'PORT': os.environ.get('TRUST_DB_PORT', '5432'),
    'USER': os.environ.get('TRUST_DB_USER', 'trust_runtime'), 'PASSWORD': secret('TRUST_DB_PASSWORD_FILE'),
    'CONN_MAX_AGE': 0, 'OPTIONS': {'sslmode': 'verify-full', 'sslrootcert': os.environ['TRUST_DB_CA'],
    'options': '-c lock_timeout=500ms -c statement_timeout=2s -c idle_in_transaction_session_timeout=3s'},
    'TEST': {'NAME': 'test_estakada_trust'}}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 1048576
TRUST_CREDENTIALS_FILE = os.environ['TRUST_CREDENTIALS_FILE']
TRUST_IDENTITY_FILE = os.environ['TRUST_IDENTITY_FILE']
TRUST_WRITE_PROFILE = os.environ.get('TRUST_WRITE_PROFILE', 'disabled')
TRUST_WRITE_PERMIT_FILE = os.environ.get('TRUST_WRITE_PERMIT_FILE','/run/secrets/write-profile.json')
TRUST_RUNTIME_ID = os.environ.get('TRUST_RUNTIME_ID','')
LOGGING = {'version': 1, 'disable_existing_loggers': True,
    'formatters': {'safe': {'()': 'journal.safe_logging.SafeFormatter'}},
    'handlers': {'safe': {'class': 'logging.StreamHandler', 'stream': 'ext://sys.stderr', 'formatter':'safe'}},
    'root': {'handlers':['safe'],'level':'WARNING'},
    'loggers': {'trust.endpoint': {'handlers':['safe'],'level':'ERROR','propagate':False},
        'django': {'handlers':['safe'],'level':'WARNING','propagate':False},
        'django.request': {'handlers':['safe'],'level':'WARNING','propagate':False},
        'django.server': {'handlers':['safe'],'level':'INFO','propagate':False}}}
