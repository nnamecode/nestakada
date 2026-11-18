import uuid

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
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
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("AUTH_LOGIN_SUCCEEDED", "Auth Login Succeeded"),
                            ("AUTH_LOGIN_FAILED", "Auth Login Failed"),
                            ("AUTH_LOGOUT", "Auth Logout"),
                            ("AUTH_PASSWORD_CHANGED", "Auth Password Changed"),
                            ("STAFF_CREATED", "Staff Created"),
                            ("STAFF_REACTIVATED", "Staff Reactivated"),
                            ("STAFF_DEACTIVATED", "Staff Deactivated"),
                            ("PAGE_GRANT_SET", "Page Grant Set"),
                            ("PAGE_GRANT_REVOKED", "Page Grant Revoked"),
                            ("PAGE_CREATED", "Page Created"),
                            ("PAGE_RENAMED", "Page Renamed"),
                            ("PAGE_MOVED", "Page Moved"),
                            ("PAGE_REORDERED", "Page Reordered"),
                            ("PAGE_PUBLICATION_CHANGED", "Page Publication Changed"),
                            ("PAGE_URL_CHANGED", "Page Url Changed"),
                            ("PAGE_CONTENT_SAVED", "Page Content Saved"),
                            ("PAGE_CONTENT_UNDONE", "Page Content Undone"),
                            ("PAGE_DELETED", "Page Deleted"),
                            ("SITE_SETTINGS_CHANGED", "Site Settings Changed"),
                            ("ASSET_UPLOADED", "Asset Uploaded"),
                            ("ASSET_REPLACED", "Asset Replaced"),
                            ("ASSET_DELETED", "Asset Deleted"),
                            ("GALLERY_CHANGED", "Gallery Changed"),
                            ("GALLERY_DELETED", "Gallery Deleted"),
                            ("SERVICE_REQUEST_ACCEPTED", "Service Request Accepted"),
                            ("SERVICE_REQUEST_DELETED", "Service Request Deleted"),
                            (
                                "SERVICE_REQUEST_RETENTION_BATCH",
                                "Service Request Retention Batch",
                            ),
                            ("AUDIT_RETENTION_BATCH", "Audit Retention Batch"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "actor_kind",
                    models.CharField(
                        choices=[
                            ("USER", "User"),
                            ("SYSTEM", "System"),
                            ("ANONYMOUS", "Anonymous"),
                        ],
                        max_length=16,
                    ),
                ),
                ("actor_uuid", models.UUIDField(blank=True, null=True)),
                (
                    "actor_role",
                    models.CharField(
                        blank=True,
                        choices=[("OWNER", "Owner"), ("EMPLOYEE", "Employee")],
                        max_length=16,
                        null=True,
                    ),
                ),
                (
                    "target_type",
                    models.CharField(
                        choices=[
                            ("USER", "User"),
                            ("PAGE", "Page"),
                            ("ASSET", "Asset"),
                            ("GALLERY", "Gallery"),
                            ("SERVICE_REQUEST", "Service Request"),
                            ("SITE_SETTINGS", "Site Settings"),
                            ("AUDIT", "Audit"),
                        ],
                        max_length=24,
                    ),
                ),
                ("target_uuid", models.UUIDField(blank=True, null=True)),
                ("secondary_uuid", models.UUIDField(blank=True, null=True)),
                ("detail", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ("-occurred_at", "-id"),
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            Q(
                                actor_kind="USER",
                                actor_uuid__isnull=False,
                                actor_role__isnull=False,
                            )
                            | Q(
                                actor_kind__in=("SYSTEM", "ANONYMOUS"),
                                actor_uuid__isnull=True,
                                actor_role__isnull=True,
                            )
                        ),
                        name="audit_actor_shape",
                    )
                ],
            },
        )
    ]
