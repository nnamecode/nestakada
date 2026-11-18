import uuid

from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("media", "0001_initial"),
        ("pages", "0002_sitesettings"),
    ]

    operations = [
        migrations.CreateModel(
            name="GalleryAlbum",
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
                ("generation", models.PositiveBigIntegerField(default=1)),
                ("position", models.PositiveIntegerField(unique=True)),
                (
                    "page",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="gallery_album",
                        to="pages.page",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(generation__gte=1),
                        name="gallery_album_generation_positive",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="GalleryPhoto",
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
                ("position", models.PositiveIntegerField()),
                ("alt", models.CharField(max_length=1000)),
                (
                    "album",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="gallery.galleryalbum",
                    ),
                ),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="gallery_photos",
                        to="media.asset",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("album", "position"),
                        name="gallery_photo_album_position_unique",
                    )
                ],
            },
        ),
    ]
