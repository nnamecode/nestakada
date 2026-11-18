import uuid

from django.core.validators import RegexValidator
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("media", "0001_initial"),
        ("pages", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("singleton_key", models.BooleanField(default=True, editable=False, unique=True)),
                ("structure_generation", models.PositiveBigIntegerField(default=1)),
                ("settings_generation", models.PositiveBigIntegerField(default=1)),
                ("organization_name", models.CharField(max_length=120)),
                ("legal_name", models.CharField(blank=True, max_length=160, null=True)),
                ("phone_display", models.CharField(max_length=64)),
                (
                    "phone_e164",
                    models.CharField(
                        max_length=16,
                        validators=(
                            RegexValidator(
                                "\\A\\+[1-9][0-9]{7,14}\\Z",
                                "Expected E.164 phone.",
                            ),
                        ),
                    ),
                ),
                ("address", models.CharField(max_length=255)),
                ("opening_hours", models.CharField(max_length=128)),
                ("contact_email", models.EmailField(max_length=254)),
                ("map_url", models.URLField(max_length=2048)),
                ("max_url", models.URLField(blank=True, max_length=2048, null=True)),
                ("telegram_url", models.URLField(blank=True, max_length=2048, null=True)),
                (
                    "logo_asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="site_settings_logos",
                        to="media.asset",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(singleton_key=True),
                        name="pages_site_settings_singleton_true",
                    ),
                    models.CheckConstraint(
                        condition=Q(structure_generation__gte=1),
                        name="pages_structure_generation_positive",
                    ),
                    models.CheckConstraint(
                        condition=Q(settings_generation__gte=1),
                        name="pages_settings_generation_positive",
                    ),
                ]
            },
        )
    ]
