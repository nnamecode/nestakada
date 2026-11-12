from django.conf import settings
from django.middleware.csrf import get_token

from . import intents


SOURCES = {'/': 'home', '/contacts': 'contacts'}


def disabled_form_for(target):
    """Static reserve projection; never issues intent or touches CSRF state."""
    source = SOURCES.get(target)
    return None if source is None else {'enabled': False, 'source': source}


def form_for(request, target):
    source = SOURCES.get(target)
    if source is None:
        return None
    enabled = settings.SERVICE_REQUEST_INTAKE_ENABLED is True
    version = settings.SERVICE_REQUEST_CONSENT_VERSION
    if not enabled:
        return {'enabled': False, 'source': source}
    profile = settings.SERVICE_REQUEST_TRANSPORT_PROFILE
    if (profile != 'synthetic'
            or type(version) is not str or not version):
        return {'enabled': False, 'source': source}
    return {
        'enabled': True,
        'source': source,
        'intent': intents.issue(source=source, consent_version=version),
        'csrf_token': get_token(request),
    }
