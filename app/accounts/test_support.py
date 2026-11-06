"""Test-only helpers for the standard server-side Django session contract."""
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone

from . import services
from .models import UserProfile


def editor_session(user, generation=None, now=None):
    if generation is None:
        generation = UserProfile.objects.get(user=user).generation
    instant = now or timezone.now()
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store[services.SESSION_GENERATION] = generation
    store[services.SESSION_ISSUED_AT] = instant.isoformat()
    store[services.SESSION_LAST_SEEN] = instant.isoformat()
    store.set_expiry(int(services.IDLE.total_seconds()))
    store.create()
    return store.session_key
