from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from modules.audit.api import ActorRef, append_event
from modules.audit.models import Action, AuditEvent, TargetType


AGE = timedelta(days=180)
BATCH_SIZE = 5_000
FAILURE = "AUDIT_RETENTION_UNAVAILABLE"


class Command(BaseCommand):
    help = "Delete at most 5000 AuditEvent rows strictly older than 180 days."

    def handle(self, *args, **options):
        cutoff = timezone.now() - AGE
        try:
            with transaction.atomic():
                event_ids = list(
                    AuditEvent.objects.select_for_update()
                    .filter(occurred_at__lt=cutoff)
                    .order_by("occurred_at", "id")
                    .values_list("id", flat=True)[:BATCH_SIZE]
                )
                deleted = 0
                if event_ids:
                    deleted, _breakdown = AuditEvent.objects.filter(id__in=event_ids).delete()
                    if deleted != len(event_ids):
                        raise RuntimeError("audit-retention-count")
                    append_event(
                        action=Action.AUDIT_RETENTION_BATCH,
                        actor=ActorRef.system(),
                        target_type=TargetType.AUDIT,
                        target_uuid=None,
                        detail={"reason": "RETENTION", "count": deleted},
                    )
        except (DatabaseError, RuntimeError, TypeError, ValueError, ValidationError):
            raise CommandError(FAILURE) from None
        self.stdout.write(f"AUDIT_RETENTION_OK deleted={deleted}")
