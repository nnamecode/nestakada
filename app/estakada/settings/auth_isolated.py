"""Test-only clock. The normal local/deployment profiles never read fixture state."""
from .local_http import *
if ENVIRONMENT != 'test':
    raise ImproperlyConfigured('AUTH_TEST_PROFILE_REQUIRES_ISOLATION')
AUTH_ISOLATED_TEST = True
