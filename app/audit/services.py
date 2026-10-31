"""One structured insert. Failures propagate; no raw diagnostic fallback."""
from django.utils import timezone

from .constants import Category, Level, Result, Source
from .models import AuditEvent
from .safety import canonical_reference, canonical_uuid, code, positive_id, related_ip
from django.core.exceptions import ValidationError


def _choice(enum, value):
    try:
        return enum(value)
    except (ValueError, TypeError):
        raise ValidationError("AUDIT_INVALID_CHOICE") from None


def record_event(*, category, event_code, level, source, result, actor_id=None,
                 object_kind="", object_ref=None, request_id=None,
                 ip_address=None, ip_related=False, event_id=None,
                 occurrence_count=1, count_is_lower_bound=False):
    """Accept constants and internal IDs, never user text/body/headers/DSNs.

    Participates in the caller's transaction. Success means an INSERT succeeded,
    not that an enclosing transaction or a future file/Telegram layer committed.
    There is no retry, suppression, or second storage write here.
    """
    from .safety import object_kind as validate_object_kind
    if type(count_is_lower_bound) is not bool:
        raise ValidationError('AUDIT_INVALID_COUNT_BOUND')

    event = AuditEvent(
        category=_choice(Category, category), code=code(event_code), level=_choice(Level, level),
        source=_choice(Source, source), result=_choice(Result, result), occurred_at=timezone.now(),
        actor_id=None if actor_id is None else positive_id(actor_id),
        object_kind=validate_object_kind(object_kind), object_ref=canonical_reference(object_ref),
        request_id=canonical_uuid(request_id), ip_address=related_ip(ip_address, ip_related),
        occurrence_count=positive_id(occurrence_count), count_is_lower_bound=count_is_lower_bound,
    )
    if event_id is not None:
        event.event_id = canonical_uuid(event_id)
    event.save(force_insert=True)
    return event
