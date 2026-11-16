"""Exact disposable TEST-08 fixture; no product URL or runtime surface."""
import base64
import csv
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import models
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.models import PageGrant, UserProfile
from accounts.test_support import editor_session
from audit.models import AuditEvent
from media_library import services as media_services
from media_library.models import (
    Asset, AssetFile, AssetUsage, FileKeyReservation,
    IdentityReservation as MediaIdentityReservation, MediaFolder,
)
from media_library.storage import MediaStorage
from page_versions.models import (
    IdentityReservation, OwnerDraft, PageContentState, PageRevision,
    RevisionMetadata, RevisionProtection, VersionBasePin,
)
from service_requests.models import ServiceRequest
from shared_content import policy as shared_policy
from shared_content.models import (
    SharedBlock, SharedBudget, SharedIdentityReservation, SharedRevision,
)
from shared_content.simple_commands import commit_normalized_current

from . import dev09_migration_apply as migration
from . import dev10_gallery_apply as gallery
from . import dev12_home_apply as home
from .models import Page, Route
from .public_gallery import ROOT_TARGET, page1_redirect_target


def _raw(model):
    return models.QuerySet(model=model, using="default")


def _sha_json(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def _counts():
    return {
        "assets": Asset.objects.count(), "files": AssetFile.objects.count(),
        "auditEvents": AuditEvent.objects.count(),
        "fileKeyReservations": FileKeyReservation.objects.count(),
        "grants": PageGrant.objects.count(), "ownerDrafts": OwnerDraft.objects.count(),
        "identityReservations": IdentityReservation.objects.count(),
        "mediaFolders": MediaFolder.objects.count(),
        "mediaIdentityReservations": MediaIdentityReservation.objects.count(),
        "pageStates": PageContentState.objects.count(), "pages": Page.objects.count(),
        "profiles": UserProfile.objects.count(), "requests": ServiceRequest.objects.count(),
        "revisionMetadata": RevisionMetadata.objects.count(),
        "revisionProtections": RevisionProtection.objects.count(),
        "revisions": PageRevision.objects.count(), "routes": Route.objects.count(),
        "sessions": Session.objects.count(),
        "sharedBlocks": SharedBlock.objects.count(),
        "sharedBudgets": SharedBudget.objects.count(),
        "sharedIdentityReservations": SharedIdentityReservation.objects.count(),
        "sharedRevisions": SharedRevision.objects.count(),
        "usages": AssetUsage.objects.count(), "users": get_user_model().objects.count(),
        "versionBasePins": VersionBasePin.objects.count(),
    }


def _shared_html(kind, asset_id):
    marker = str(asset_id)
    image = '<img data-es-shared-asset="%s" alt="Synthetic brand">' % marker
    brand = ('<a class="es-brand" href="https://estakada-service.ru/">'
             + image + '</a>')
    if kind == "footer":
        return ('<footer class="es-footer"><div class="es-footer-left">'
                + brand + '<p>TEST-08</p></div><div class="es-footer-legal">'
                '<span>Политика конфиденциальности</span>'
                '<span>Условия использования файлов cookie</span>'
                '<span class="es-footer-credit">Сделано в <b>noname</b></span>'
                '</div></footer>')
    socials = "".join(
        '<a href="%s" aria-label="%s"><img data-es-shared-asset="%s" alt=""></a>'
        % (href, label, marker)
        for href, label in (
            ("https://t.me/synthetic", "Telegram"),
            ("https://max.ru/synthetic", "MAX"),
            ("https://www.instagram.com/synthetic", "Instagram"),
        )
    )
    return ('<header class="es-header">' + brand
            + '<button class="es-menu-button" type="button" aria-expanded="false" '
              'aria-controls="es-nav"><span></span><span></span><span></span>'
              '<b>Меню</b></button>'
            + '<nav id="es-nav" aria-label="Основное меню"></nav>'
            + '<div class="es-header-contacts"><div class="es-header-socials">'
            + socials + '</div>'
              '<a class="es-header-address" href="https://yandex.ru/maps/org/57771430682">'
              '<b>Москва</b><span>TEST-08</span></a>'
              '<a class="es-header-phone" href="tel:+70000000001">'
              '<strong>+70000000001</strong><span>Ежедневно с 9:00 до 21:00</span>'
              '</a></div></header>')


def _seed_gallery(source_root, storage):
    package = gallery._read_package()
    folder = MediaFolder.objects.create(path="legacy/gallery")
    for photo in gallery._photo_rows(package):
        data = Path(source_root, photo["local_file"]).read_bytes()
        if len(data) != photo["bytes"] or sha256(data).hexdigest() != photo["sha256"]:
            raise AssertionError("TEST08_GALLERY_SOURCE_MISMATCH")
        asset = Asset.objects.create(
            id=UUID(photo["asset_id"]), folder=folder,
            provenance="TEST08 exact gallery fixture", is_legacy=True,
            source_url=photo["source_url"], source_sha256=photo["sha256"])
        media_services.write_file(
            asset_id=asset.pk, file_id=photo["file_id"],
            kind=AssetFile.Kind.LEGACY_PUBLIC, key=photo["storage_key"],
            chunks=data, storage=storage)
        media_services.mark_ready(asset_id=asset.pk, storage=storage)
    return package


def _route_contract(path):
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != os.environ["ESTAKADA_TEST08_ROUTE_SHA256"]:
        raise AssertionError("TEST08_ROUTE_MAP_HASH_MISMATCH")
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    targets = [row["requested_path"] for row in rows]
    if len(rows) != 115 or len(set(targets)) != 115:
        raise AssertionError("TEST08_ROUTE_MAP_SET_MISMATCH")
    return sorted(targets)


@contextmanager
def build_test08_fixture(case, credentials=None):
    """Build the one admitted fixture and keep it alive for caller HTTP checks."""
    if credentials is None:
        credentials = {
            "owner": secrets.token_urlsafe(32),
            "employee": secrets.token_urlsafe(32),
        }
    if (type(credentials) is not dict
            or set(credentials) != {"owner", "employee"}
            or any(type(value) is not str or not 20 <= len(value) <= 200
                   for value in credentials.values())
            or credentials["owner"] == credentials["employee"]):
        raise AssertionError("TEST08_CREDENTIALS_INVALID")
    source_root = os.environ["ESTAKADA_TEST08_SOURCE_ROOT"]
    route_map = os.environ["ESTAKADA_TEST08_ROUTE_MAP"]
    before = _counts()
    case.assertTrue(all(value == 0 for value in before.values()), before)
    with override_settings(
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
            ENVIRONMENT="test", DEV09_MIGRATION_APPLY_ENABLED=True,
            DEV10_GALLERY_APPLY_ENABLED=True, DEV12_HOME_APPLY_ENABLED=True,
            SERVICE_REQUEST_INTAKE_ENABLED=False,
            SERVICE_REQUEST_TRANSPORT_PROFILE="disabled"):
        with TemporaryDirectory(prefix="test08-media-", dir="/tmp") as media_root:
            with override_settings(MEDIA_LIBRARY_ROOT=media_root):
                storage = MediaStorage()
                owner = auth.bootstrap_owner(credentials["owner"])
                employee = auth.create_employee(
                    actor=owner, username="test08-employee",
                    password=credentials["employee"])

                migration.import_combined_infographic_media(
                    source_root=source_root, storage=storage)
                migration.import_remaining_media(source_root=source_root, storage=storage)
                home.import_home_media(source_root=source_root, storage=storage)
                gallery_package = _seed_gallery(source_root, storage)
                case.assertEqual(Asset.objects.filter(status=Asset.Status.READY).count(), 237)
                case.assertEqual(AssetFile.objects.aggregate(
                    total=models.Sum("byte_size"))["total"], 45064743)

                for kind in ("header", "footer"):
                    SharedBlock.objects.create(kind=kind)
                SharedBudget.objects.create(singleton=True)
                session_key = editor_session(owner)
                shared_asset = gallery._photo_rows(gallery_package)[0]["asset_id"]
                for kind in ("header", "footer"):
                    normalized = shared_policy.normalize_html(_shared_html(kind, shared_asset), kind)
                    commit_normalized_current(
                        actor=owner, kind=kind, expected_generation=1,
                        session_key=session_key, expected_current_id=None,
                        html=normalized["html"], bindings=normalized["bindings"])

                migration.apply_articles_slice()
                migration.apply_services_catalog()
                migration.apply_service_roots()
                migration.apply_service_details()
                migration.apply_leading_price_details()
                migration.apply_diagnostics_branch()
                migration.apply_planned_maintenance()
                migration.apply_combined_services(storage=storage)
                migration.apply_remaining_content(storage=storage)
                gallery_result = gallery.apply_gallery(storage=storage)
                home_result = home.apply_home(storage=storage)

                case.assertEqual((gallery_result["pages"], gallery_result["routes"]), (18, 19))
                case.assertEqual(home_result["assets"], 21)
                auth.set_grant(
                    actor=owner, employee=employee,
                    page=Page.objects.get(
                        routes__target="/articles/zamena-masla-v-dvigatele"),
                    intro_text=True, expected_generation=1)

                expected_routes = _route_contract(route_map)
                page1_target = ROOT_TARGET + "?page=1"
                case.assertEqual(page1_redirect_target(page1_target), ROOT_TARGET)
                expected_db_routes = [target for target in expected_routes
                                      if target != page1_target]
                case.assertEqual(
                    sorted(Route.objects.values_list("target", flat=True)),
                    expected_db_routes)
                case.assertEqual((Page.objects.count(), Route.objects.count()), (112, 114))
                case.assertEqual(PageGrant.objects.count(), 1)
                case.assertEqual(ServiceRequest.objects.count(), 0)
                case.assertEqual(_raw(Page).update(is_published=True), 112)
                case.assertEqual(Page.objects.filter(is_published=True).count(), 112)

                assembled = _counts()
                case.assertEqual((assembled["assets"], assembled["files"]), (237, 237))
                case.assertEqual((assembled["pages"], assembled["routes"]), (112, 114))
                case.assertEqual((assembled["sharedBlocks"], assembled["sharedRevisions"]), (2, 2))
                receipt = {
                    "after": None, "assembled": assembled, "before": before,
                    "defaultOff": {"serviceRequestIntake": False,
                                   "serviceRequestRows": 0,
                                   "transportProfile": "disabled"},
                    "fixtureReady": True,
                    "inputManifestSha256": os.environ["ESTAKADA_TEST08_INPUT_MANIFEST_SHA256"],
                    "media": {"bytes": 45064743, "count": 237},
                    "routeMapSha256": os.environ["ESTAKADA_TEST08_ROUTE_SHA256"],
                    "routeSetSha256": _sha_json(expected_routes),
                    "runId": os.environ["ESTAKADA_TEST08_RUN_ID"],
                    "schema": "test08-fixture-result-v1",
                    "sourceManifestSha256": os.environ["ESTAKADA_TEST08_SOURCE_MANIFEST_SHA256"],
                }
                yield {
                    "assembled": assembled, "before": before,
                    "employee": employee, "mediaRoot": media_root,
                    "owner": owner, "publicRoutes": expected_routes,
                    "receipt": receipt,
                }


class Test08FixtureContractTests(TransactionTestCase):
    reset_sequences = True
    receipt = None
    media_root = None

    def test_f08_fx_001_assemble_exact_fixture(self):
        with build_test08_fixture(self) as fixture:
            type(self).receipt = fixture["receipt"]
            type(self).media_root = fixture["mediaRoot"]
            self.assertTrue(Path(type(self).media_root).is_dir())
        self.assertFalse(Path(type(self).media_root).exists())

    def test_f08_fx_002_verify_teardown_and_emit_receipt(self):
        self.assertIsNotNone(type(self).receipt)
        after = _counts()
        self.assertTrue(all(value == 0 for value in after.values()), after)
        self.assertFalse(Path(type(self).media_root).exists())
        result = dict(type(self).receipt)
        result["after"] = after
        encoded = base64.urlsafe_b64encode(
            json.dumps(result, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        print("TEST08_FIXTURE_RESULT=" + encoded, flush=True)
