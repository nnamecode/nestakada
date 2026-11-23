from __future__ import annotations

import os
from pathlib import Path


if os.environ.get("ESTAKADA_LOCAL_RESTORE") != "1":
    raise RuntimeError("The explicit local-restore marker is required.")
password_path = Path(os.environ.pop("ESTAKADA_DB_PASSWORD_FILE", ""))
if password_path.as_posix() != "/run/secrets/db-password" or not password_path.is_file():
    raise RuntimeError("The exact database password mount is required.")
os.environ["ESTAKADA_DB_PASSWORD"] = password_path.read_text(encoding="utf-8").strip()

from .base import *  # noqa: E402,F403


DEBUG = False
SERVICE_REQUESTS_ENABLED = False
transaction_mode = (
    "off" if os.environ.get("ESTAKADA_RESTORE_VERIFY_WRITE") == "1" else "on"
)
DATABASES["default"]["OPTIONS"]["options"] = (
    f"-c search_path=app,pg_catalog -c default_transaction_read_only={transaction_mode}"
)
