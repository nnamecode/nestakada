from django.core.management.base import BaseCommand, CommandError

from modules.service_requests.lifecycle import RequestLifecycleError, run_retention
from modules.service_requests.web import _request_authority


class Command(BaseCommand):
    help = "Apply one bounded service-request retention batch."

    def add_arguments(self, parser) -> None:
        # No user arguments by contract.
        return None

    def handle(self, *args, **options):
        del args, options
        authority = _request_authority()
        if authority is None:
            raise CommandError("RETENTION_UNAVAILABLE")
        try:
            result = run_retention(
                ledger=authority[0],
                independent=authority[1],
            )
        except RequestLifecycleError as exc:
            raise CommandError(exc.code) from None
        self.stdout.write(str(result.deleted_count))
