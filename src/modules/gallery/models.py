from __future__ import annotations

import unicodedata
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class GalleryAlbum(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.OneToOneField(
        "pages.Page",
        on_delete=models.PROTECT,
        related_name="gallery_album",
    )
    generation = models.PositiveBigIntegerField(default=1)
    position = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(generation__gte=1),
                name="gallery_album_generation_positive",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.generation < 1:
            raise ValidationError({"generation": "Generation must be positive."})


class GalleryPhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    album = models.ForeignKey(GalleryAlbum, on_delete=models.CASCADE, related_name="photos")
    asset = models.ForeignKey(
        "media.Asset",
        on_delete=models.PROTECT,
        related_name="gallery_photos",
    )
    position = models.PositiveIntegerField()
    alt = models.CharField(max_length=1000)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("album", "position"),
                name="gallery_photo_album_position_unique",
            )
        ]

    def clean(self) -> None:
        super().clean()
        normalized = unicodedata.normalize("NFC", self.alt)
        if normalized != self.alt or not self.alt or any(
            ord(char) < 32 or ord(char) == 127 for char in self.alt
        ):
            raise ValidationError({"alt": "Gallery alt text is not canonical plain text."})
