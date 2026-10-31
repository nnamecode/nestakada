"""Normal runtime uses UTC. Only the explicitly isolated test profile reads a clock."""
import json
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

def now():
    if not getattr(settings, 'AUTH_ISOLATED_TEST', False):
        return timezone.now()
    if settings.ENVIRONMENT != 'test':
        raise RuntimeError('AUTH_TEST_PROFILE_REQUIRES_ISOLATION')
    path = Path('/run/auth-fixture/clock.json')
    if path.stat().st_size > 256:
        raise RuntimeError('AUTH_TEST_CLOCK_INVALID')
    value = parse_datetime(json.loads(path.read_text(encoding='utf-8'))['now'])
    if value is None or timezone.is_naive(value):
        raise RuntimeError('AUTH_TEST_CLOCK_INVALID')
    return value
