from dataclasses import dataclass

from django.db import transaction

from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from . import ledger
from .models import ServiceRequest


@dataclass(frozen=True)
class DeleteResult:
    deleted: bool
    replay: bool


def delete(*, request_id, actor_id):
    with ledger.locked() as root_fd:
        with transaction.atomic():
            row = ServiceRequest.objects.select_for_update().filter(
                pk=request_id).first()
            if row is None:
                if ledger.get(request_id, root_fd=root_fd) is None:
                    raise ServiceRequest.DoesNotExist()
                return DeleteResult(deleted=True, replay=True)
            ledger.record(request_id, root_fd=root_fd)
            row.delete()
            record_event(
                category=Category.USER_ACTIONS,
                event_code='REQUEST_DELETED', level=Level.INFO,
                source=Source.APPLICATION, result=Result.SUCCESS,
                actor_id=actor_id)
            return DeleteResult(deleted=True, replay=False)


def reconcile():
    with ledger.locked() as root_fd:
        records = ledger.entries(root_fd=root_fd)
        deleted = 0
        ids = [item.request_id for item in records]
        for start in range(0, len(ids), ledger.BATCH_SIZE):
            with transaction.atomic():
                count, _ = ServiceRequest.objects.filter(
                    pk__in=ids[start:start + ledger.BATCH_SIZE]).delete()
                deleted += count
        return len(records), deleted
