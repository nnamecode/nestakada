from __future__ import annotations

import re
import unicodedata
import uuid
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q


SHA256_VALIDATOR = RegexValidator(r"\A[0-9a-f]{64}\Z", "Expected lowercase SHA-256.")


class PageKind(models.TextChoices):
    HOME = "home"
    SERVICES_MASTER_CATALOG = "services_master_catalog"
    SERVICE_CATALOG = "service_catalog"
    SERVICE_SECTION_OVERVIEW = "service_section_overview"
    SERVICE_DETAIL = "service_detail"
    ARTICLES_CATALOG = "articles_catalog"
    ARTICLE = "article"
    CONTACTS = "contacts"
    REVIEWS = "reviews"
    ACTIONS = "actions"
    GALLERY_CATALOG = "gallery_catalog"
    GALLERY_ALBUM = "gallery_album"
    LEGACY_PARTNER_LINKS = "legacy_partner_links"
    LEGACY_DIRECTOR_MESSAGE = "legacy_director_message"
    LEGACY_NEWS_ARTICLE = "legacy_news_article"
    LEGACY_EMPTY_MAIN = "legacy_empty_main"
    LEGACY_NEWS_CATALOG = "legacy_news_catalog"
    LEGACY_UNDER_CONSTRUCTION = "legacy_under_construction"
    LEGACY_CAMERA_SCHEDULE_TEXT = "legacy_camera_schedule_text"


class RouteOutcome(models.TextChoices):
    HOME = "home"
    SERVICES_MASTER_CATALOG = "services_master_catalog"
    SERVICE_CATALOG = "service_catalog"
    SERVICE_SECTION_OVERVIEW = "service_section_overview"
    SERVICE_DETAIL = "service_detail"
    ARTICLES_CATALOG = "articles_catalog"
    ARTICLE = "article"
    CONTACTS = "contacts"
    REVIEWS = "reviews"
    ACTIONS = "actions"
    GALLERY_CATALOG = "gallery_catalog"
    GALLERY_ALBUM = "gallery_album"
    LEGACY_PARTNER_LINKS = "legacy_partner_links"
    LEGACY_DIRECTOR_MESSAGE = "legacy_director_message"
    LEGACY_NEWS_ARTICLE = "legacy_news_article"
    LEGACY_EMPTY_MAIN = "legacy_empty_main"
    LEGACY_NEWS_CATALOG = "legacy_news_catalog"
    SERVICE_WASH_LEGACY_ALIAS = "service_wash_legacy_alias"
    LEGACY_UNDER_CONSTRUCTION = "legacy_under_construction"
    LEGACY_CAMERA_SCHEDULE_TEXT = "legacy_camera_schedule_text"


class RouteMode(models.TextChoices):
    PRIMARY = "PRIMARY"
    ALIAS = "ALIAS"
    REDIRECT = "REDIRECT"


class LastOperationAction(models.TextChoices):
    SAVE = "SAVE"
    UNDO = "UNDO"


class Page(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=500)
    kind = models.CharField(max_length=48, choices=PageKind.choices)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    position = models.PositiveIntegerField()
    is_published = models.BooleanField(default=False)
    primary_url_mutable = models.BooleanField(default=False)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("parent", "position"),
                name="pages_sibling_position_unique",
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                condition=~Q(parent=F("id")),
                name="pages_parent_not_self",
            ),
        ]


class Route(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="routes")
    target = models.CharField(max_length=2048, unique=True)
    mode = models.CharField(max_length=16, choices=RouteMode.choices)
    outcome = models.CharField(max_length=48, choices=RouteOutcome.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("page",),
                condition=Q(mode=RouteMode.PRIMARY),
                name="pages_one_primary_route",
            )
        ]

    def clean(self) -> None:
        super().clean()
        parsed = urlsplit(self.target)
        if re.search(r"%(?![0-9A-Fa-f]{2})", self.target):
            raise ValidationError({"target": "Route target has a malformed percent escape."})
        try:
            decoded_path = unquote(parsed.path, errors="strict")
            decoded_query = unquote(parsed.query, errors="strict")
        except UnicodeDecodeError as exc:
            raise ValidationError({"target": "Route target encoding is invalid."}) from exc
        if (
            not self.target.startswith("/")
            or self.target.startswith("//")
            or not decoded_path.startswith("/")
            or decoded_path.startswith("//")
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or "\\" in self.target
            or "\\" in decoded_path
            or any(
                ord(char) < 32 or ord(char) == 127 or char.isspace()
                for char in self.target + decoded_path + decoded_query
            )
            or any(segment in {".", ".."} for segment in decoded_path.split("/"))
        ):
            raise ValidationError({"target": "Route target must be an exact local path/query."})
        page_kind = getattr(self.page, "kind", None)
        if self.outcome == RouteOutcome.SERVICE_WASH_LEGACY_ALIAS:
            if self.mode != RouteMode.ALIAS or page_kind != PageKind.SERVICE_DETAIL:
                raise ValidationError("Wash legacy outcome must alias a service detail page.")
        elif page_kind is not None and self.outcome != page_kind:
            raise ValidationError("Route outcome must match its page kind.")


class PageContent(models.Model):
    page = models.OneToOneField(Page, primary_key=True, on_delete=models.CASCADE, related_name="content")
    generation = models.PositiveBigIntegerField(default=1)
    current_payload = models.JSONField()
    current_hash = models.CharField(max_length=64, validators=(SHA256_VALIDATOR,))
    current_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="current_page_contents",
    )
    current_created_at = models.DateTimeField()
    previous_payload = models.JSONField(null=True, blank=True)
    previous_hash = models.CharField(
        max_length=64,
        validators=(SHA256_VALIDATOR,),
        null=True,
        blank=True,
    )
    previous_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="previous_page_contents",
        null=True,
        blank=True,
    )
    previous_created_at = models.DateTimeField(null=True, blank=True)
    last_operation_id = models.UUIDField(null=True, blank=True)
    last_operation_action = models.CharField(
        max_length=8,
        choices=LastOperationAction.choices,
        null=True,
        blank=True,
    )
    last_result_generation = models.PositiveBigIntegerField(null=True, blank=True)
    last_result_hash = models.CharField(
        max_length=64,
        validators=(SHA256_VALIDATOR,),
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(generation__gte=1),
                name="pages_content_generation_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        previous_payload__isnull=True,
                        previous_hash__isnull=True,
                        previous_author__isnull=True,
                        previous_created_at__isnull=True,
                    )
                    | Q(
                        previous_payload__isnull=False,
                        previous_hash__isnull=False,
                        previous_author__isnull=False,
                        previous_created_at__isnull=False,
                    )
                ),
                name="pages_previous_all_or_none",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        last_operation_id__isnull=True,
                        last_operation_action__isnull=True,
                        last_result_generation__isnull=True,
                        last_result_hash__isnull=True,
                    )
                    | Q(
                        last_operation_id__isnull=False,
                        last_operation_action__isnull=False,
                        last_result_generation__isnull=False,
                        last_result_hash__isnull=False,
                    )
                ),
                name="pages_last_operation_all_or_none",
            ),
            models.CheckConstraint(
                condition=Q(last_result_generation__isnull=True)
                | Q(last_result_generation=F("generation")),
                name="pages_last_result_generation_coherent",
            ),
            models.CheckConstraint(
                condition=Q(last_result_hash__isnull=True) | Q(last_result_hash=F("current_hash")),
                name="pages_last_result_hash_coherent",
            ),
        ]


class PageGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="page_grants",
    )
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="grants")
    groups = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("staff", "page"),
                name="pages_grant_staff_page_unique",
            ),
            models.CheckConstraint(
                condition=Q(groups=["prices"]) | Q(groups=["text"]) | Q(groups=["text", "prices"]),
                name="pages_grant_groups_closed",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.groups not in (["prices"], ["text"], ["text", "prices"]):
            raise ValidationError({"groups": "Grant groups must be a canonical closed subset."})


class SiteSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    singleton_key = models.BooleanField(default=True, editable=False, unique=True)
    structure_generation = models.PositiveBigIntegerField(default=1)
    settings_generation = models.PositiveBigIntegerField(default=1)
    organization_name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=160, null=True, blank=True)
    phone_display = models.CharField(max_length=64)
    phone_e164 = models.CharField(
        max_length=16,
        validators=(RegexValidator(r"\A\+[1-9][0-9]{7,14}\Z", "Expected E.164 phone."),),
    )
    address = models.CharField(max_length=255)
    opening_hours = models.CharField(max_length=128)
    contact_email = models.EmailField(max_length=254)
    map_url = models.URLField(max_length=2048)
    max_url = models.URLField(max_length=2048, null=True, blank=True)
    telegram_url = models.URLField(max_length=2048, null=True, blank=True)
    logo_asset = models.ForeignKey(
        "media.Asset",
        on_delete=models.PROTECT,
        related_name="site_settings_logos",
    )

    class Meta:
        constraints = [
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

    def clean(self) -> None:
        super().clean()
        required_text_fields = (
            "organization_name",
            "phone_display",
            "address",
            "opening_hours",
        )
        for field_name in (*required_text_fields, "legal_name"):
            value = getattr(self, field_name)
            if value is None and field_name == "legal_name":
                continue
            if (
                not value
                or unicodedata.normalize("NFC", value) != value
                or any(ord(char) < 32 or ord(char) == 127 for char in value)
            ):
                raise ValidationError({field_name: "Expected canonical plain text."})
        if (
            not self.contact_email
            or not self.contact_email.isascii()
            or self.contact_email.strip() != self.contact_email
        ):
            raise ValidationError({"contact_email": "Expected canonical ASCII email text."})
        for field_name in ("map_url", "max_url", "telegram_url"):
            value = getattr(self, field_name)
            if value == "" and field_name != "map_url":
                raise ValidationError({field_name: "Expected an exact HTTPS URL or null."})
            if value:
                parsed = urlsplit(value)
                if (
                    parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.fragment
                    or any(ord(char) < 32 or ord(char) == 127 for char in value)
                ):
                    raise ValidationError({field_name: "Expected an exact HTTPS URL."})
        if getattr(self.logo_asset, "state", None) != "READY":
            raise ValidationError({"logo_asset": "Site logo must be READY."})
