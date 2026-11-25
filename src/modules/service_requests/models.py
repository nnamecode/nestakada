from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_PHONE = re.compile(r"\A\+7[0-9]{10}\Z")
_YEAR = re.compile(r"\A[0-9]{4}\Z")


class TelegramOutcome(models.TextChoices):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    IN_PROGRESS = "IN_PROGRESS"
    SENT = "SENT"
    FAILED = "FAILED"


class ServiceRequest(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=12)
    vehicle_make = models.CharField(max_length=100, blank=True)
    vehicle_model = models.CharField(max_length=100, blank=True)
    vehicle_year = models.CharField(max_length=4, blank=True)
    comment = models.CharField(max_length=4000, blank=True)
    consent_text_version = models.CharField(max_length=64)
    consent_text_sha256 = models.CharField(max_length=64)
    consented_at = models.DateTimeField()
    telegram_outcome = models.CharField(
        max_length=16,
        choices=TelegramOutcome.choices,
        default=TelegramOutcome.NOT_ATTEMPTED,
    )
    telegram_attempted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("-created_at", "-id"), name="request_created_id_idx")]
        constraints = [
            models.CheckConstraint(condition=~Q(name=""), name="request_name_nonempty"),
            models.CheckConstraint(
                condition=Q(phone__regex=r"^\+7[0-9]{10}$"),
                name="request_phone_canonical",
            ),
            models.CheckConstraint(
                condition=Q(vehicle_year="") | Q(vehicle_year__regex=r"^[0-9]{4}$"),
                name="request_vehicle_year_shape",
            ),
            models.CheckConstraint(
                condition=~Q(consent_text_version=""),
                name="request_consent_version_nonempty",
            ),
            models.CheckConstraint(
                condition=Q(consent_text_sha256__regex=r"^[0-9a-f]{64}$"),
                name="request_consent_sha256_shape",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        telegram_outcome=TelegramOutcome.NOT_ATTEMPTED,
                        telegram_attempted_at__isnull=True,
                    )
                    | Q(
                        telegram_outcome__in=(
                            TelegramOutcome.IN_PROGRESS,
                            TelegramOutcome.SENT,
                            TelegramOutcome.FAILED,
                        ),
                        telegram_attempted_at__isnull=False,
                    )
                ),
                name="request_telegram_attempt_shape",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if _PHONE.fullmatch(self.phone) is None:
            raise ValidationError({"phone": "Phone must be canonical."})
        if self.vehicle_year and _YEAR.fullmatch(self.vehicle_year) is None:
            raise ValidationError({"vehicle_year": "Vehicle year must use four ASCII digits."})
        vehicle = " ".join(
            value for value in (self.vehicle_make, self.vehicle_model, self.vehicle_year) if value
        )
        if len(vehicle) > 300:
            raise ValidationError({"vehicle_make": "Canonical vehicle text exceeds the cap."})
        if _SHA256.fullmatch(self.consent_text_sha256) is None:
            raise ValidationError({"consent_text_sha256": "Consent hash must be lowercase SHA-256."})
        attempted = self.telegram_attempted_at is not None
        if (self.telegram_outcome == TelegramOutcome.NOT_ATTEMPTED) == attempted:
            raise ValidationError({"telegram_attempted_at": "Telegram attempt shape is invalid."})


class ServiceRequestDeletionProjection(models.Model):
    sequence = models.PositiveBigIntegerField(primary_key=True)
    request_id = models.UUIDField(unique=True)

    class Meta:
        ordering = ("sequence",)
        constraints = [
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="request_deletion_sequence_positive",
            )
        ]
