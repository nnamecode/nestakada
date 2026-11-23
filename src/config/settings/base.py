from __future__ import annotations

import os
from pathlib import Path


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
]

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
