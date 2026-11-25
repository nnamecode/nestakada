from __future__ import annotations

import os


if os.environ.get("ESTAKADA_CORE18_SYNTHETIC_RUNTIME") != "1":
    raise RuntimeError("The explicit CORE-18 synthetic runtime marker is required.")

from .test import *  # noqa: E402,F403


# This disposable Docker-only profile uses an internal isolated network and no
# published database port. Production and restore profiles retain verified TLS.
DATABASES["default"]["OPTIONS"] = {"sslmode": "disable"}
