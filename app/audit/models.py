import uuid
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .constants import CODE_PATTERN, KIND_PATTERN, REFERENCE_PATTERN, Category, Level, Result, Source


class AuditEvent(models.Model):
    # PK is an internal cursor; event_id is the one stable cross-source event ID.
    id = models.BigAutoField(primary_key=True)
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    category = models.CharField(max_length=32, choices=Category.choices)
    level = models.CharField(max_length=8, choices=Level.choices)
    code = models.CharField(max_length=64, validators=[RegexValidator(CODE_PATTERN, "AUDIT_INVALID_CODE")])
    source = models.CharField(max_length=32, choices=Source.choices)
    result = models.CharField(max_length=8, choices=Result.choices)
    actor_id = models.PositiveBigIntegerField(null=True, blank=True)
    object_kind = models.CharField(max_length=32, blank=True, default="", validators=[RegexValidator(KIND_PATTERN, "AUDIT_INVALID_OBJECT_KIND")])
    object_ref = models.CharField(max_length=41, blank=True, default="", validators=[RegexValidator(REFERENCE_PATTERN, "AUDIT_INVALID_REFERENCE")])
    request_id = models.UUIDField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, unpack_ipv4=True)
    occurrence_count = models.PositiveBigIntegerField(default=1)
    count_is_lower_bound = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["category", "id"], name="audit_category_id_idx"),
            models.Index(fields=["occurred_at", "id"], name="audit_time_id_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(occurrence_count__gte=1), name='audit_positive_occurrences'),
            models.CheckConstraint(condition=models.Q(category__in=Category.values), name="audit_known_category"),
            models.CheckConstraint(condition=models.Q(level__in=Level.values), name="audit_known_level"),
            models.CheckConstraint(condition=models.Q(source__in=Source.values), name="audit_known_source"),
            models.CheckConstraint(condition=models.Q(result__in=Result.values), name="audit_known_result"),
            models.CheckConstraint(condition=models.Q(actor_id__isnull=True) | models.Q(actor_id__gt=0), name="audit_positive_actor"),
            models.CheckConstraint(condition=models.Q(object_ref="") | ~models.Q(object_kind=""), name="audit_object_kind_required"),
        ]

    def clean(self):
        from .safety import positive_id
        positive_id(self.occurrence_count)
        if type(self.count_is_lower_bound) is not bool:
            raise ValidationError('AUDIT_INVALID_COUNT_BOUND')
        if self.object_ref and not self.object_kind:
            raise ValidationError("AUDIT_OBJECT_KIND_REQUIRED")
        if isinstance(self.occurred_at, datetime) and timezone.is_naive(self.occurred_at):
            raise ValidationError("AUDIT_TIMESTAMP_MUST_BE_AWARE")

    def save(self, *args, **kwargs):
        if (not self._state.adding or self.pk is not None or args
                or kwargs.get('force_update') or kwargs.get('update_fields') is not None):
            raise ValidationError("AUDIT_APPEND_ONLY")
        # Validate before the one INSERT; database constraints/unique event_id
        # resolve concurrent races. Do not issue validation SELECTs per event.
        self.full_clean(validate_unique=False, validate_constraints=False)
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def __str__(self):
        return str(self.event_id)
