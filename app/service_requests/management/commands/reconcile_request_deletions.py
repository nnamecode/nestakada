from django.core.management.base import BaseCommand, CommandError

from service_requests import deletion, ledger


class Command(BaseCommand):
    help = 'Apply the external request deletion ledger before restored-site opening.'

    def handle(self, *args, **options):
        try:
            entries, deleted = deletion.reconcile()
        except ledger.LedgerError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(
            f'REQUEST_DELETION_RECONCILE_OK entries={entries} deleted={deleted}')
