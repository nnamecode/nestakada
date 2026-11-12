from dataclasses import dataclass

from django.db import IntegrityError, transaction

from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from . import intents, policy
from .models import ServiceRequest


@dataclass(frozen=True)
class IntakeResult:
    request: ServiceRequest
    inserted: bool


def accept(*, intent, name, phone, car, comment, consent):
    payload = intents.verify(intent)
    normalized = policy.normalize(
        source=payload['source'], name=name, phone=phone, car=car,
        comment=comment, consent=consent,
        consent_version=payload['consent_version'])
    fingerprint = intents.digest(intent)
    with transaction.atomic():
        try:
            with transaction.atomic():
                row = ServiceRequest.objects.create(
                    source=normalized.source, name=normalized.name,
                    phone=normalized.phone, car=normalized.car,
                    comment=normalized.comment,
                    consent_version=normalized.consent_version,
                    intent_digest=fingerprint)
                record_event(
                    category=Category.USER_ACTIONS,
                    event_code='REQUEST_ACCEPTED', level=Level.INFO,
                    source=Source.APPLICATION, result=Result.SUCCESS)
            return IntakeResult(row, True)
        except IntegrityError:
            row = ServiceRequest.objects.filter(intent_digest=fingerprint).first()
            if row is None:
                raise
            return IntakeResult(row, False)
