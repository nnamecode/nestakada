import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import migrations, models
from django.db.models import F, Q
import django.db.models.deletion


PAGE_KINDS = [
    ("home", "Home"),
    ("services_master_catalog", "Services Master Catalog"),
    ("service_catalog", "Service Catalog"),
    ("service_section_overview", "Service Section Overview"),
    ("service_detail", "Service Detail"),
    ("articles_catalog", "Articles Catalog"),
    ("article", "Article"),
    ("contacts", "Contacts"),
    ("reviews", "Reviews"),
    ("actions", "Actions"),
    ("gallery_catalog", "Gallery Catalog"),
    ("gallery_album", "Gallery Album"),
    ("legacy_partner_links", "Legacy Partner Links"),
    ("legacy_director_message", "Legacy Director Message"),
    ("legacy_news_article", "Legacy News Article"),
    ("legacy_empty_main", "Legacy Empty Main"),
    ("legacy_news_catalog", "Legacy News Catalog"),
    ("legacy_under_construction", "Legacy Under Construction"),
    ("legacy_camera_schedule_text", "Legacy Camera Schedule Text"),
]

ROUTE_OUTCOMES = PAGE_KINDS[:17] + [
    ("service_wash_legacy_alias", "Service Wash Legacy Alias"),
    *PAGE_KINDS[17:],
]

SHA256_VALIDATOR = RegexValidator(
    "\\A[0-9a-f]{64}\\Z",
    "Expected lowercase SHA-256.",
)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Page",
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
                ("name", models.CharField(max_length=500)),
                ("kind", models.CharField(choices=PAGE_KINDS, max_length=48)),
                ("position", models.PositiveIntegerField()),
                ("is_published", models.BooleanField(default=False)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="pages.page",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("parent", "position"),
                        name="pages_sibling_position_unique",
                        nulls_distinct=False,
                    ),
                    models.CheckConstraint(
                        condition=~Q(parent=F("id")),
                        name="pages_parent_not_self",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Route",
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
                ("target", models.CharField(max_length=2048, unique=True)),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("PRIMARY", "Primary"),
                            ("ALIAS", "Alias"),
                            ("REDIRECT", "Redirect"),
                        ],
                        max_length=16,
                    ),
                ),
                ("outcome", models.CharField(choices=ROUTE_OUTCOMES, max_length=48)),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="routes",
                        to="pages.page",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        condition=Q(mode="PRIMARY"),
                        fields=("page",),
                        name="pages_one_primary_route",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="PageContent",
            fields=[
                (
                    "page",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="content",
                        serialize=False,
                        to="pages.page",
                    ),
                ),
                ("generation", models.PositiveBigIntegerField(default=1)),
                ("current_payload", models.JSONField()),
                (
                    "current_hash",
                    models.CharField(max_length=64, validators=(SHA256_VALIDATOR,)),
                ),
                ("current_created_at", models.DateTimeField()),
                ("previous_payload", models.JSONField(blank=True, null=True)),
                (
                    "previous_hash",
                    models.CharField(
                        blank=True,
                        max_length=64,
                        null=True,
                        validators=(SHA256_VALIDATOR,),
                    ),
                ),
                ("previous_created_at", models.DateTimeField(blank=True, null=True)),
                ("last_operation_id", models.UUIDField(blank=True, null=True)),
                (
                    "last_operation_action",
                    models.CharField(
                        blank=True,
                        choices=[("SAVE", "Save"), ("UNDO", "Undo")],
                        max_length=8,
                        null=True,
                    ),
                ),
                (
                    "last_result_generation",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                (
                    "last_result_hash",
                    models.CharField(
                        blank=True,
                        max_length=64,
                        null=True,
                        validators=(SHA256_VALIDATOR,),
                    ),
                ),
                (
                    "current_author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="current_page_contents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "previous_author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="previous_page_contents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
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
                        condition=(
                            Q(last_result_generation__isnull=True)
                            | Q(last_result_generation=F("generation"))
                        ),
                        name="pages_last_result_generation_coherent",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(last_result_hash__isnull=True)
                            | Q(last_result_hash=F("current_hash"))
                        ),
                        name="pages_last_result_hash_coherent",
                    ),
                ]
            },
        ),
        migrations.CreateModel(
            name="PageGrant",
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
                ("groups", models.JSONField()),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grants",
                        to="pages.page",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="page_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("staff", "page"),
                        name="pages_grant_staff_page_unique",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(groups=["prices"])
                            | Q(groups=["text"])
                            | Q(groups=["text", "prices"])
                        ),
                        name="pages_grant_groups_closed",
                    ),
                ]
            },
        ),
    ]
