from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ServiceRequest",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("name", models.CharField(max_length=100)),
                ("phone", models.CharField(max_length=12)),
                ("vehicle_make", models.CharField(blank=True, max_length=100)),
                ("vehicle_model", models.CharField(blank=True, max_length=100)),
                ("vehicle_year", models.CharField(blank=True, max_length=4)),
                ("comment", models.CharField(blank=True, max_length=4000)),
                ("consent_text_version", models.CharField(max_length=64)),
                ("consent_text_sha256", models.CharField(max_length=64)),
                ("consented_at", models.DateTimeField()),
                (
                    "telegram_outcome",
                    models.CharField(
                        choices=[
                            ("NOT_ATTEMPTED", "Not Attempted"),
                            ("IN_PROGRESS", "In Progress"),
                            ("SENT", "Sent"),
                            ("FAILED", "Failed"),
                        ],
                        default="NOT_ATTEMPTED",
                        max_length=16,
                    ),
                ),
                ("telegram_attempted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [
                    models.Index(fields=("-created_at", "-id"), name="request_created_id_idx")
                ],
                "constraints": [
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
                                telegram_outcome="NOT_ATTEMPTED",
                                telegram_attempted_at__isnull=True,
                            )
                            | Q(
                                telegram_outcome__in=("IN_PROGRESS", "SENT", "FAILED"),
                                telegram_attempted_at__isnull=False,
                            )
                        ),
                        name="request_telegram_attempt_shape",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ServiceRequestDeletionProjection",
            fields=[
                ("sequence", models.PositiveBigIntegerField(primary_key=True, serialize=False)),
                ("request_id", models.UUIDField(unique=True)),
            ],
            options={
                "ordering": ("sequence",),
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(sequence__gte=1),
                        name="request_deletion_sequence_positive",
                    )
                ],
            },
        ),
    ]
