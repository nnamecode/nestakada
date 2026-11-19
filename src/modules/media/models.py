from __future__ import annotations

import re
import unicodedata
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import CharField, F, Q, Value
from django.db.models.functions import Cast, Concat


SHA256_VALIDATOR = RegexValidator(r"\A[0-9a-f]{64}\Z", "Expected lowercase SHA-256.")
SLOT_VALIDATOR = RegexValidator(
    r"\A[a-z][a-z0-9_]{0,99}\Z",
    "Expected a canonical media slot.",
)


class AssetPurpose(models.TextChoices):
    CONTENT = "CONTENT"
    SITE_ASSET = "SITE_ASSET"
    GALLERY_ORIGINAL = "GALLERY_ORIGINAL"


class AssetState(models.TextChoices):
    STAGED = "STAGED"
    READY = "READY"


class FileKind(models.TextChoices):
    PRIVATE_SOURCE = "PRIVATE_SOURCE"
    MAIN = "MAIN"
    PREVIEW = "PREVIEW"
    LEGACY_PUBLIC = "LEGACY_PUBLIC"


class MediaType(models.TextChoices):
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"
    SVG = "image/svg+xml"


class UsageScope(models.TextChoices):
    PAGE_CURRENT = "PAGE_CURRENT"
    PAGE_PREVIOUS = "PAGE_PREVIOUS"
    SITE_SETTINGS = "SITE_SETTINGS"


_EXTENSIONS = {
    MediaType.JPEG: frozenset({"jpg", "jpeg"}),
    MediaType.PNG: frozenset({"png"}),
    MediaType.WEBP: frozenset({"webp"}),
    MediaType.SVG: frozenset({"svg"}),
}
_PUBLIC_SEGMENTS = {
    FileKind.MAIN: "main",
    FileKind.PREVIEW: "preview",
    FileKind.LEGACY_PUBLIC: "legacy-public",
}
_UUID_KEY_PART = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=24, choices=AssetPurpose.choices)
    source_sha256 = models.CharField(max_length=64, validators=(SHA256_VALIDATOR,))
    state = models.CharField(max_length=16, choices=AssetState.choices, default=AssetState.STAGED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(purpose__in=AssetPurpose.values),
                name="media_asset_purpose_closed",
            ),
            models.CheckConstraint(
                condition=Q(state__in=AssetState.values),
                name="media_asset_state_closed",
            ),
            models.CheckConstraint(
                condition=Q(source_sha256__regex=r"^[0-9a-f]{64}$"),
                name="media_asset_source_sha256_shape",
            ),
        ]


class AssetFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="files")
    kind = models.CharField(max_length=24, choices=FileKind.choices)
    storage_key = models.CharField(max_length=1024, unique=True)
    sha256 = models.CharField(max_length=64, validators=(SHA256_VALIDATOR,))
    byte_size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=32, choices=MediaType.choices)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("asset", "kind"),
                name="media_file_asset_kind_unique",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=FileKind.values),
                name="media_file_kind_closed",
            ),
            models.CheckConstraint(
                condition=Q(mime_type__in=MediaType.values),
                name="media_file_mime_closed",
            ),
            models.CheckConstraint(
                condition=Q(byte_size__gte=1),
                name="media_file_byte_size_positive",
            ),
            models.CheckConstraint(
                condition=Q(sha256__regex=r"^[0-9a-f]{64}$"),
                name="media_file_sha256_shape",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind=FileKind.PRIVATE_SOURCE,
                        storage_key__regex=(
                            rf"^private/sources/{_UUID_KEY_PART}/source\.(jpg|jpeg|png|webp)$"
                        ),
                    )
                    | Q(
                        kind=FileKind.MAIN,
                        storage_key__regex=rf"^img/{_UUID_KEY_PART}/main\.(jpg|jpeg|png|webp|svg)$",
                    )
                    | Q(
                        kind=FileKind.PREVIEW,
                        storage_key__regex=rf"^img/{_UUID_KEY_PART}/preview\.(jpg|jpeg|png|webp|svg)$",
                    )
                    | Q(
                        kind=FileKind.LEGACY_PUBLIC,
                        storage_key__regex=(
                            rf"^img/{_UUID_KEY_PART}/legacy-public\.(jpg|jpeg|png|webp|svg)$"
                        ),
                    )
                ),
                name="media_file_storage_key_shape",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind=FileKind.PRIVATE_SOURCE, storage_key__startswith=Concat(
                        Value("private/sources/"), Cast(F("asset_id"), CharField()), Value("/source."),
                    ))
                    | Q(kind=FileKind.MAIN, storage_key__startswith=Concat(
                        Value("img/"), Cast(F("asset_id"), CharField()), Value("/main."),
                    ))
                    | Q(kind=FileKind.PREVIEW, storage_key__startswith=Concat(
                        Value("img/"), Cast(F("asset_id"), CharField()), Value("/preview."),
                    ))
                    | Q(kind=FileKind.LEGACY_PUBLIC, storage_key__startswith=Concat(
                        Value("img/"), Cast(F("asset_id"), CharField()), Value("/legacy-public."),
                    ))
                ),
                name="media_file_storage_asset_coherent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(mime_type=MediaType.JPEG, storage_key__regex=r"\.(jpg|jpeg)$")
                    | Q(mime_type=MediaType.PNG, storage_key__regex=r"\.png$")
                    | Q(mime_type=MediaType.WEBP, storage_key__regex=r"\.webp$")
                    | Q(mime_type=MediaType.SVG, storage_key__regex=r"\.svg$")
                ),
                name="media_file_storage_mime_coherent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(mime_type=MediaType.SVG, width__isnull=True, height__isnull=True)
                    | Q(
                        mime_type__in=(MediaType.JPEG, MediaType.PNG, MediaType.WEBP),
                        width__isnull=True,
                        height__isnull=True,
                    )
                    | Q(
                        mime_type__in=(MediaType.JPEG, MediaType.PNG, MediaType.WEBP),
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

    def clean_fields(self, exclude=None) -> None:
        excluded = set(exclude or ())
        boolean_dimensions = {
            field_name: "Boolean is not an integer dimension."
            for field_name in ("width", "height")
            if field_name not in excluded and type(getattr(self, field_name)) is bool
        }
        if boolean_dimensions:
            raise ValidationError(boolean_dimensions)
        super().clean_fields(exclude=exclude)

    def clean(self) -> None:
        super().clean()
        if self.asset_id is None:
            raise ValidationError({"asset": "Asset is required."})
        key = unicodedata.normalize("NFC", self.storage_key)
        if key != self.storage_key or "\\" in key or any(char.isspace() for char in key):
            raise ValidationError({"storage_key": "Storage key is not canonical."})
        extension = key.rsplit(".", 1)[-1] if "." in key else ""
        if extension not in _EXTENSIONS.get(self.mime_type, frozenset()):
            raise ValidationError({"storage_key": "Storage extension does not match MIME."})
        dimensions = (self.width, self.height)
        if self.mime_type == MediaType.SVG:
            if dimensions != (None, None):
                raise ValidationError({"width": "SVG dimensions must be null."})
        elif dimensions != (None, None) and not all(
            type(value) is int and 1 <= value <= 10_000
            for value in dimensions
        ):
            raise ValidationError({"width": "Raster dimensions must be both null or both bounded."})
        asset_id = str(self.asset_id).lower()
        if self.kind == FileKind.PRIVATE_SOURCE:
            expected = rf"private/sources/{re.escape(asset_id)}/source\.(?:jpg|jpeg|png|webp)"
        else:
            segment = _PUBLIC_SEGMENTS.get(self.kind)
            if segment is None:
                raise ValidationError({"kind": "Unknown public file kind."})
            expected = rf"img/{re.escape(asset_id)}/{segment}\.(?:jpg|jpeg|png|webp|svg)"
        if re.fullmatch(expected, key) is None:
            raise ValidationError({"storage_key": "Storage key does not match its identity."})
        if self.mime_type == MediaType.SVG and self.kind == FileKind.PRIVATE_SOURCE:
            raise ValidationError({"mime_type": "SVG cannot be a private upload source."})


class AssetUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="usages")
    scope = models.CharField(max_length=24, choices=UsageScope.choices)
    target_uuid = models.UUIDField()
    slot = models.CharField(max_length=100, validators=(SLOT_VALIDATOR,))
    position = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(scope__in=UsageScope.values),
                name="media_usage_scope_closed",
            ),
            models.CheckConstraint(
                condition=~Q(scope=UsageScope.SITE_SETTINGS) | Q(position=0),
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

    def clean(self) -> None:
        super().clean()
        if self.scope == UsageScope.SITE_SETTINGS and (
            self.slot != "logo" or self.position != 0
        ):
            raise ValidationError("Site settings permits only the scalar logo slot.")
        asset_state = getattr(self.asset, "state", None)
        if asset_state is not None and asset_state != AssetState.READY:
            raise ValidationError({"asset": "Only a READY asset can be referenced."})
