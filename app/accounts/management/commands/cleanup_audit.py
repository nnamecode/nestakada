from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from audit.models import AuditEvent


AGE = timedelta(days=30)
FAILURE = 'AUDIT_RETENTION_UNAVAILABLE'


class Command(BaseCommand):
    help = 'Delete AuditEvent rows strictly older than the fixed 30-day retention.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - AGE
        try:
            with transaction.atomic():
                deleted, _ = AuditEvent.objects.filter(
                    occurred_at__lt=cutoff).delete()
        except DatabaseError:
            raise CommandError(FAILURE) from None
        self.stdout.write(f'AUDIT_RETENTION_OK deleted={deleted}')
