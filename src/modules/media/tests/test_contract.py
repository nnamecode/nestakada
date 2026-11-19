import uuid
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import PROTECT
from django.test import SimpleTestCase, TestCase

from modules.media.models import (
    Asset,
    AssetFile,
    AssetPurpose,
    AssetState,
    AssetUsage,
    FileKind,
    MediaType,
    UsageScope,
)


class MediaContractTests(SimpleTestCase):
    def _asset(self, *, state=AssetState.READY) -> Asset:
        return Asset(
            id=uuid.uuid4(),
            purpose=AssetPurpose.CONTENT,
            source_sha256="a" * 64,
            state=state,
        )

    def _validate_file(self, file: AssetFile) -> None:
        file.clean_fields(exclude=("asset",))
        file.clean()

    def test_public_file_key_dimensions_and_mime_are_coherent(self) -> None:
        asset = self._asset()
        file = AssetFile(
            asset=asset,
            kind=FileKind.MAIN,
            storage_key=f"img/{asset.id}/main.webp",
            sha256="b" * 64,
            byte_size=100,
            mime_type=MediaType.WEBP,
            width=100,
            height=80,
        )
        self._validate_file(file)

        file.width = None
        file.height = None
        self._validate_file(file)

    def test_raster_dimensions_are_all_or_nothing_and_bounded(self) -> None:
        asset = self._asset()
        file = AssetFile(
            asset=asset,
            kind=FileKind.MAIN,
            storage_key=f"img/{asset.id}/main.png",
            sha256="b" * 64,
            byte_size=100,
            mime_type=MediaType.PNG,
            width=None,
            height=80,
        )
        for dimensions in ((None, 80), (100, None), (0, 80), (100, 10_001), (True, 80)):
            with self.subTest(dimensions=dimensions), self.assertRaises(ValidationError):
                file.width, file.height = dimensions
                self._validate_file(file)

    def test_noncanonical_or_mismatched_key_is_rejected(self) -> None:
        asset = self._asset()
        for key in ("../main.webp", f"img/{asset.id}/preview.webp", f"img\\{asset.id}\\main.webp"):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                candidate = AssetFile(
                    asset=asset,
                    kind=FileKind.MAIN,
                    storage_key=key,
                    sha256="b" * 64,
                    byte_size=100,
                    mime_type=MediaType.WEBP,
                    width=100,
                    height=80,
                )
                self._validate_file(candidate)

    def test_svg_has_no_raster_dimensions_and_is_never_private_source(self) -> None:
        asset = self._asset()
        svg = AssetFile(
            asset=asset,
            kind=FileKind.MAIN,
            storage_key=f"img/{asset.id}/main.svg",
            sha256="c" * 64,
            byte_size=50,
            mime_type=MediaType.SVG,
        )
        self._validate_file(svg)
        svg.width = 50
        svg.height = 50
        with self.assertRaises(ValidationError):
            self._validate_file(svg)
        svg.width = None
        svg.height = None
        svg.kind = FileKind.PRIVATE_SOURCE
        svg.storage_key = f"private/sources/{asset.id}/source.svg"
        with self.assertRaises(ValidationError):
            self._validate_file(svg)

    def test_usage_requires_ready_asset_and_exact_settings_slot(self) -> None:
        usage = AssetUsage(
            asset=self._asset(state=AssetState.STAGED),
            scope=UsageScope.SITE_SETTINGS,
            target_uuid=uuid.uuid4(),
            slot="logo",
            position=0,
        )
        with self.assertRaises(ValidationError):
            usage.clean()
        usage.asset.state = AssetState.READY
        usage.slot = "hero"
        with self.assertRaises(ValidationError):
            usage.clean()

    def test_usage_blocks_asset_deletion_by_contract(self) -> None:
        field = AssetUsage._meta.get_field("asset")
        self.assertIs(field.remote_field.on_delete, PROTECT)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL constraint semantics required.")
class MediaDatabaseConstraintTests(TestCase):
    def _file(self, *, width, height) -> AssetFile:
        asset = Asset.objects.create(
            purpose=AssetPurpose.CONTENT,
            source_sha256="a" * 64,
            state=AssetState.READY,
        )
        return AssetFile(
            asset=asset,
            kind=FileKind.MAIN,
            storage_key=f"img/{asset.id}/main.png",
            sha256="b" * 64,
            byte_size=100,
            mime_type=MediaType.PNG,
            width=width,
            height=height,
        )

    def test_database_rejects_partial_raster_dimensions(self) -> None:
        for dimensions in ((None, 80), (100, None)):
            with self.subTest(dimensions=dimensions), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self._file(width=dimensions[0], height=dimensions[1]).save(force_insert=True)

    def test_database_accepts_null_or_bounded_raster_dimensions(self) -> None:
        for dimensions in ((None, None), (100, 80)):
            with self.subTest(dimensions=dimensions):
                self._file(width=dimensions[0], height=dimensions[1]).save(force_insert=True)
