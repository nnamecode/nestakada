import uuid

from django.core.validators import RegexValidator
from django.db import migrations, models
from django.db.models import CharField, F, Q, Value
from django.db.models.functions import Cast, Concat
import django.db.models.deletion


SHA256_VALIDATOR = RegexValidator(
    "\\A[0-9a-f]{64}\\Z",
    "Expected lowercase SHA-256.",
)
SLOT_VALIDATOR = RegexValidator(
    "\\A[a-z][a-z0-9_]{0,99}\\Z",
    "Expected a canonical media slot.",
)


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Asset",
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
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("CONTENT", "Content"),
                            ("SITE_ASSET", "Site Asset"),
                            ("GALLERY_ORIGINAL", "Gallery Original"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "source_sha256",
                    models.CharField(max_length=64, validators=(SHA256_VALIDATOR,)),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[("STAGED", "Staged"), ("READY", "Ready")],
                        default="STAGED",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(purpose__in=("CONTENT", "SITE_ASSET", "GALLERY_ORIGINAL")),
                        name="media_asset_purpose_closed",
                    ),
                    models.CheckConstraint(
                        condition=Q(state__in=("STAGED", "READY")),
                        name="media_asset_state_closed",
                    ),
                    models.CheckConstraint(
                        condition=Q(source_sha256__regex="^[0-9a-f]{64}$"),
                        name="media_asset_source_sha256_shape",
                    ),
                ]
            },
        ),
        migrations.CreateModel(
            name="AssetFile",
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
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("PRIVATE_SOURCE", "Private Source"),
                            ("MAIN", "Main"),
                            ("PREVIEW", "Preview"),
                            ("LEGACY_PUBLIC", "Legacy Public"),
                        ],
                        max_length=24,
                    ),
                ),
                ("storage_key", models.CharField(max_length=1024, unique=True)),
                (
                    "sha256",
                    models.CharField(max_length=64, validators=(SHA256_VALIDATOR,)),
                ),
                ("byte_size", models.PositiveBigIntegerField()),
                (
                    "mime_type",
                    models.CharField(
                        choices=[
                            ("image/jpeg", "Jpeg"),
                            ("image/png", "Png"),
                            ("image/webp", "Webp"),
                            ("image/svg+xml", "Svg"),
                        ],
                        max_length=32,
                    ),
                ),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="media.asset",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("asset", "kind"),
                        name="media_file_asset_kind_unique",
                    ),
                    models.CheckConstraint(
                        condition=Q(kind__in=("PRIVATE_SOURCE", "MAIN", "PREVIEW", "LEGACY_PUBLIC")),
                        name="media_file_kind_closed",
                    ),
                    models.CheckConstraint(
                        condition=Q(mime_type__in=("image/jpeg", "image/png", "image/webp", "image/svg+xml")),
                        name="media_file_mime_closed",
                    ),
                    models.CheckConstraint(
                        condition=Q(byte_size__gte=1),
                        name="media_file_byte_size_positive",
                    ),
                    models.CheckConstraint(
                        condition=Q(sha256__regex="^[0-9a-f]{64}$"),
                        name="media_file_sha256_shape",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(
                                kind="PRIVATE_SOURCE",
                                storage_key__regex=(
                                    "^private/sources/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                                    "[0-9a-f]{4}-[0-9a-f]{12}/source\\.(jpg|jpeg|png|webp)$"
                                ),
                            )
                            | Q(
                                kind="MAIN",
                                storage_key__regex=(
                                    "^img/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                                    "[0-9a-f]{12}/main\\.(jpg|jpeg|png|webp|svg)$"
                                ),
                            )
                            | Q(
                                kind="PREVIEW",
                                storage_key__regex=(
                                    "^img/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                                    "[0-9a-f]{12}/preview\\.(jpg|jpeg|png|webp|svg)$"
                                ),
                            )
                            | Q(
                                kind="LEGACY_PUBLIC",
                                storage_key__regex=(
                                    "^img/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                                    "[0-9a-f]{12}/legacy-public\\.(jpg|jpeg|png|webp|svg)$"
                                ),
                            )
                        ),
                        name="media_file_storage_key_shape",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(kind="PRIVATE_SOURCE", storage_key__startswith=Concat(
                                Value("private/sources/"), Cast(F("asset_id"), CharField()), Value("/source."),
                            ))
                            | Q(kind="MAIN", storage_key__startswith=Concat(
                                Value("img/"), Cast(F("asset_id"), CharField()), Value("/main."),
                            ))
                            | Q(kind="PREVIEW", storage_key__startswith=Concat(
                                Value("img/"), Cast(F("asset_id"), CharField()), Value("/preview."),
                            ))
                            | Q(kind="LEGACY_PUBLIC", storage_key__startswith=Concat(
                                Value("img/"), Cast(F("asset_id"), CharField()), Value("/legacy-public."),
                            ))
                        ),
                        name="media_file_storage_asset_coherent",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(mime_type="image/jpeg", storage_key__regex="\\.(jpg|jpeg)$")
                            | Q(mime_type="image/png", storage_key__regex="\\.png$")
                            | Q(mime_type="image/webp", storage_key__regex="\\.webp$")
                            | Q(mime_type="image/svg+xml", storage_key__regex="\\.svg$")
                        ),
                        name="media_file_storage_mime_coherent",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(mime_type="image/svg+xml", width__isnull=True, height__isnull=True)
                            | Q(
                                mime_type__in=("image/jpeg", "image/png", "image/webp"),
                                width__isnull=True,
                                height__isnull=True,
                            )
                            | Q(
                                mime_type__in=("image/jpeg", "image/png", "image/webp"),
                                width__isnull=False,
                                height__isnull=False,
                                width__gte=1,
                                width__lte=10_000,
                                height__gte=1,
                                height__lte=10_000,
                            )
                        ),
                        name="media_file_dimensions_shape",
                    ),
                ]
            },
        ),
        migrations.CreateModel(
            name="AssetUsage",
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
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("PAGE_CURRENT", "Page Current"),
                            ("PAGE_PREVIOUS", "Page Previous"),
                            ("SITE_SETTINGS", "Site Settings"),
                        ],
                        max_length=24,
                    ),
                ),
                ("target_uuid", models.UUIDField()),
                ("slot", models.CharField(max_length=100, validators=(SLOT_VALIDATOR,))),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="usages",
                        to="media.asset",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(scope__in=("PAGE_CURRENT", "PAGE_PREVIOUS", "SITE_SETTINGS")),
                        name="media_usage_scope_closed",
                    ),
                    models.CheckConstraint(
                        condition=~Q(scope="SITE_SETTINGS") | Q(position=0),
                        name="media_usage_settings_position_zero",
                    ),
                    models.UniqueConstraint(
                        fields=("scope", "target_uuid", "slot", "position"),
                        name="media_usage_target_slot_position_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("scope", "target_uuid", "slot", "asset"),
                        name="media_usage_target_slot_asset_unique",
                    ),
                ]
            },
        ),
    ]
