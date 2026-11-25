from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath


BASE_DIR = Path(__file__).resolve().parents[2]


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(f"Required configuration is absent: {name}")
    return value


SECRET_KEY = _required("ESTAKADA_DJANGO_SECRET")
DEBUG = False
ALLOWED_HOSTS = tuple(filter(None, _required("ESTAKADA_ALLOWED_HOSTS").split(",")))
PUBLIC_ORIGIN = os.environ.get("ESTAKADA_PUBLIC_ORIGIN")
SEO_ROBOTS_PROFILE = os.environ.get("ESTAKADA_SEO_ROBOTS_PROFILE")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "modules.audit.apps.AuditConfig",
    "modules.accounts.apps.AccountsConfig",
    "modules.media.apps.MediaConfig",
    "modules.pages.apps.PagesConfig",
    "modules.gallery.apps.GalleryConfig",
    "modules.service_requests.apps.ServiceRequestsConfig",
]

def _service_requests_enabled() -> bool:
    return os.environ.get("ESTAKADA_SERVICE_REQUESTS_ENABLED") == "true"


SERVICE_REQUESTS_ENABLED = _service_requests_enabled()
SERVICE_REQUEST_FORM_VERSION = os.environ.get("ESTAKADA_REQUEST_FORM_VERSION")
SERVICE_REQUEST_CONSENT_VERSION = os.environ.get("ESTAKADA_REQUEST_CONSENT_VERSION")
SERVICE_REQUEST_CONSENT_TEXT = os.environ.get("ESTAKADA_REQUEST_CONSENT_TEXT")
SERVICE_REQUEST_CONSENT_SHA256 = os.environ.get("ESTAKADA_REQUEST_CONSENT_SHA256")
SERVICE_REQUEST_PRIVACY_TEXT = os.environ.get("ESTAKADA_REQUEST_PRIVACY_TEXT")
SERVICE_REQUEST_PRIVACY_SHA256 = os.environ.get("ESTAKADA_REQUEST_PRIVACY_SHA256")
SERVICE_REQUEST_TELEGRAM_TOKEN_FILE = os.environ.get("ESTAKADA_REQUEST_TELEGRAM_TOKEN_FILE")
SERVICE_REQUEST_TELEGRAM_CHAT_ID = os.environ.get("ESTAKADA_REQUEST_TELEGRAM_CHAT_ID")
SERVICE_REQUEST_LEDGER_ROOT = os.environ.get("ESTAKADA_REQUEST_LEDGER_ROOT")
SERVICE_REQUEST_INDEPENDENT_ADAPTER = os.environ.get("ESTAKADA_REQUEST_INDEPENDENT_ADAPTER")


def _service_request_configuration_valid(values) -> bool:
    def bounded(name: str, maximum: int, *, ascii_only: bool = False):
        value = getattr(values, name, None)
        if type(value) is not str:
            return None
        try:
            encoded = value.encode("utf-8")
        except UnicodeError:
            return None
        if (
            not 1 <= len(encoded) <= maximum
            or (ascii_only and not value.isascii())
        ):
            return None
        return value

    if getattr(values, "SERVICE_REQUESTS_ENABLED", None) is not True:
        return False
    form_version = bounded("SERVICE_REQUEST_FORM_VERSION", 64, ascii_only=True)
    consent_version = bounded("SERVICE_REQUEST_CONSENT_VERSION", 64, ascii_only=True)
    consent_text = bounded("SERVICE_REQUEST_CONSENT_TEXT", 8192)
    privacy_text = bounded("SERVICE_REQUEST_PRIVACY_TEXT", 8192)
    consent_hash = getattr(values, "SERVICE_REQUEST_CONSENT_SHA256", None)
    privacy_hash = getattr(values, "SERVICE_REQUEST_PRIVACY_SHA256", None)
    token_file = getattr(values, "SERVICE_REQUEST_TELEGRAM_TOKEN_FILE", None)
    chat_id = getattr(values, "SERVICE_REQUEST_TELEGRAM_CHAT_ID", None)
    ledger_root = getattr(values, "SERVICE_REQUEST_LEDGER_ROOT", None)
    adapter = getattr(values, "SERVICE_REQUEST_INDEPENDENT_ADAPTER", None)
    token_path = PurePosixPath(token_file) if type(token_file) is str else None
    ledger_path = PurePosixPath(ledger_root) if type(ledger_root) is str else None
    return not (
        None in {form_version, consent_version, consent_text, privacy_text}
        or type(consent_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", consent_hash) is None
        or type(privacy_hash) is not str or re.fullmatch(r"[0-9a-f]{64}", privacy_hash) is None
        or hashlib.sha256(consent_text.encode("utf-8")).hexdigest() != consent_hash
        or hashlib.sha256(privacy_text.encode("utf-8")).hexdigest() != privacy_hash
        or token_path is None or "\x00" in token_file
        or not token_path.is_absolute() or ".." in token_path.parts
        or type(chat_id) is not str or re.fullmatch(r"-?[1-9][0-9]{0,19}", chat_id) is None
        or ledger_path is None or "\x00" in ledger_root
        or not ledger_path.is_absolute() or ".." in ledger_path.parts
        or adapter != "external-v1"
    )


SERVICE_REQUEST_CONFIGURATION_VALIDATOR = _service_request_configuration_valid

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "modules.accounts.middleware.PrivateIngressMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _required("ESTAKADA_DB_NAME"),
        "USER": _required("ESTAKADA_DB_USER"),
        "PASSWORD": _required("ESTAKADA_DB_PASSWORD"),
        "HOST": _required("ESTAKADA_DB_HOST"),
        "PORT": _required("ESTAKADA_DB_PORT"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "sslmode": "verify-full",
            "sslrootcert": _required("ESTAKADA_DB_SSLROOTCERT"),
        },
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10_600
DATA_UPLOAD_MAX_MEMORY_SIZE = 4_194_304

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "base-uri": ("'none'",),
        "frame-ancestors": ("'none'",),
        "object-src": ("'none'",),
    }
}
