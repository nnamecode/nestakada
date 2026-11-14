"""Closed one-shot writer for the disposable TEST-10A database."""
import json
import os
from pathlib import Path
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from page_editor.test10_fixture import SCHEMA, prepare


PRIVATE_ROOT = Path("/run/test10-private")


class Command(BaseCommand):
    help = "Prepare the fixed TEST-10A fixture in a fresh disposable database"

    def add_arguments(self, parser):
        parser.add_argument("--prepare", action="store_true", required=True)

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != "test" or os.environ.get("TEST10_FIXTURE_ADMISSION") != "D-1040":
            raise CommandError("T10_FIXTURE_ADMISSION_REQUIRED")
        if not PRIVATE_ROOT.is_dir() or PRIVATE_ROOT.is_symlink():
            raise CommandError("T10_FIXTURE_PRIVATE_ROOT_REJECTED")
        private_path = PRIVATE_ROOT / "actors.json"
        if private_path.exists() or private_path.is_symlink():
            raise CommandError("T10_FIXTURE_PRIVATE_FILE_EXISTS")
        secret_values = {
            "owner": secrets.token_urlsafe(48),
            "s_edit": secrets.token_urlsafe(48),
            "s_other": secrets.token_urlsafe(48),
            "canary": secrets.token_hex(32),
        }
        summary, private = prepare(
            database_name=settings.DATABASES["default"]["NAME"],
            secrets=secret_values)
        try:
            descriptor = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(private, stream, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise CommandError("T10_FIXTURE_PRIVATE_FILE_EXISTS") from error
        if summary["schema"] != SCHEMA:
            raise CommandError("T10_FIXTURE_SUMMARY_REJECTED")
        self.stdout.write(json.dumps(summary, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")))
