from __future__ import annotations

import os


if os.environ.get("ESTAKADA_CORE19_SYNTHETIC_RUNTIME") != "1":
    raise RuntimeError("The explicit CORE-19 synthetic runtime marker is required.")

from .test import *  # noqa: E402,F403


SERVICE_REQUESTS_ENABLED = False
DATABASES["default"]["OPTIONS"] = {"sslmode": "disable"}
