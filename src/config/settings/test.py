import re

from . import base as _base
from .base import *  # noqa: F403


DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]

if _base._required("ESTAKADA_TEST_RUNTIME") != "1":
    raise RuntimeError("The explicit test-runtime marker is required.")
_test_name = _base._required("ESTAKADA_TEST_DB_NAME")
_test_host = _base._required("ESTAKADA_TEST_DB_HOST")
_test_user = _base._required("ESTAKADA_TEST_DB_USER")
if _test_name == DATABASES["default"]["NAME"] or not re.fullmatch(
    r"estakada_[a-z0-9_]+_test", _test_name
):
    raise RuntimeError("The isolated test database name is invalid.")
DATABASES["default"]["HOST"] = _test_host
DATABASES["default"]["USER"] = _test_user
DATABASES["default"]["TEST"] = {"NAME": _test_name}
