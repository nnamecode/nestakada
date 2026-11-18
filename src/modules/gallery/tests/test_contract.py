import uuid

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from modules.gallery.models import GalleryAlbum, GalleryPhoto


class GalleryContractTests(SimpleTestCase):
    def test_album_generation_is_positive_by_contract(self) -> None:
        album = GalleryAlbum(generation=0, position=0)
        with self.assertRaises(ValidationError):
            album.clean()

    def test_photo_alt_is_nonempty_normalized_plain_text(self) -> None:
        photo = GalleryPhoto(id=uuid.uuid4(), position=0, alt="")
        with self.assertRaises(ValidationError):
            photo.clean()
        photo.alt = "Photo\x00"
        with self.assertRaises(ValidationError):
            photo.clean()
