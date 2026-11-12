import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ServiceRequest(models.Model):
    class Source(models.TextChoices):
        HOME = 'home', 'Главная'
        CONTACTS = 'contacts', 'Контакты'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    source = models.CharField(max_length=16, choices=Source.choices)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=12)
    car = models.CharField(max_length=300, blank=True)
    comment = models.CharField(max_length=4000, blank=True)
    consent_version = models.CharField(max_length=64)
    intent_digest = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['-created_at', '-id'], name='request_created_id_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(source__in=['home', 'contacts']),
                name='request_known_source'),
            models.CheckConstraint(
                condition=~Q(name=''), name='request_name_nonempty'),
            models.CheckConstraint(
                condition=Q(phone__regex=r'^\+7[0-9]{10}$'),
                name='request_phone_canonical'),
            models.CheckConstraint(
                condition=~Q(consent_version=''),
                name='request_consent_nonempty'),
            models.CheckConstraint(
                condition=Q(intent_digest__regex=r'^[0-9a-f]{64}$'),
                name='request_intent_digest'),
        ]


class RequestSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    recipient_email = models.EmailField(max_length=254, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name='request_settings_singleton'),
        ]

    def save(self, *args, **kwargs):
        if self.pk != 1:
            raise ValidationError('REQUEST_SETTINGS_SINGLETON_REQUIRED')
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)
