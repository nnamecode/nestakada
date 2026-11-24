from __future__ import annotations

import os

from config.local_cutover_identity import (
    PROBE_HOST,
    reject_restore_write_escape,
    validate_identity_environment,
)


reject_restore_write_escape(os.environ)

from .local_restore import *  # noqa: E402,F403


database_options = DATABASES["default"]["OPTIONS"].get("options")  # noqa: F405
if database_options != "-c search_path=app,pg_catalog -c default_transaction_read_only=on":
    raise RuntimeError("Local cutover database connection must be read-only.")

R7C_ROLE, R7C_GENERATION_SHA256, R7C_STORAGE_BINDING_SHA256 = (
    validate_identity_environment(os.environ)
)
ROOT_URLCONF = "config.urls_local_cutover"
ALLOWED_HOSTS = tuple(dict.fromkeys((*ALLOWED_HOSTS, PROBE_HOST)))  # noqa: F405
