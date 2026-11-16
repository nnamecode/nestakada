"""TEST-08 exact10 base-MVP execution; named wrapper only."""
import base64
from datetime import timedelta
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from urllib.parse import urlencode
from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import models
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import services as auth
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from content.models import Page, Route
from content.public_gallery import ALBUM_TARGETS, ROOT_TARGET
from content.public_read import public_navigation
from html_reserve.storage import ReserveStore
from media_library import services as media_services
from media_library.models import Asset, AssetFile, AssetUsage
from page_versions import schema as version_schema
from page_versions import services as versions
from page_versions.models import PageContentState, PageRevision, RevisionProtection
from service_requests.models import ServiceRequest

from .test_test08_fixture import _counts, build_test08_fixture


PACKAGE_SHA256 = {
    "@route-map": "c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8",
    "@media-evidence": "52823a26c535f6bcbb45601fccad630278d59d421ab5f87b25bb1390d28867ca",
    "content/dev09b_articles_slice.json": "2936561288256d42968363afe90147678aa6fc88bbdff9faf21fde1c2d986639",
    "content/dev09e_services_catalog.json": "beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9",
    "content/dev09g_service_roots.json": "956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db",
    "content/dev09h_service_details.json": "439dea21aa4257e934e0781faec982bb05157d5a734171ced58086df4e8bd52a",
    "content/dev09i_planned_maintenance.json": "fa0e85ba9640ffa45916e810bece20e949698b3dbe82f9ead99750210b98a5cf",
    "content/dev09j_leading_price_details.json": "e091047ae5272fa9834d828d5ed73e1fbc914a41faa07e4367b9787ad0a8934d",
    "content/dev09k_diagnostics_branch.json": "9980c60a1a2ee354ef156c7f9695cfc76ec051f798dfe3610a95f3e29c473e67",
    "content/dev09m_combined_services.json": "3fb682d6a092d78439fa45b541668554d793490b41eb89d311359738053f8e01",
    "content/dev09m_infographic_map019.json": "fe083d206a72a3850bb30a554e57d375eba3338aacd87842c6c17f99a0f34954",
    "content/dev09n_remaining_content.json": "a47eb0118dd04ede21eebd995e870ddbf3d0895f7ad9e17f806b27babdccf3ed",
    "content/dev10_gallery.json": "9db5b026d6affa4668e2ca19268d8663355c1e22504f6aba6aa1676ed3d41b3b",
    "content/dev12_home_profile.json": "c12caba76e429ac11496b0a299f61919f7c8a1c200f494acb99e08baff9d4d56",
}

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def _json_sha(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def _file_sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _oracle_path(base, name):
    if name == "@route-map":
        return Path(os.environ["ESTAKADA_TEST08_ROUTE_MAP"])
    if name == "@media-evidence":
        return Path(os.environ["ESTAKADA_TEST08_MEDIA_EVIDENCE"])
    return Path(base) / name


def _snapshot(payload, **changes):
    values = {key: payload[key] for key in (
        "intro_text", "main_text", "price", "h1", "title", "description",
        "indexing_allowed", "main_image", "preview_image", "embedded_images",
        "layout")}
    if "contacts_profile" in payload:
        values["contacts_profile"] = payload["contacts_profile"]
    if "home_profile" in payload:
        values["home_profile"] = payload["home_profile"]
    values.update(changes)
    return version_schema.snapshot_v1(payload["page_kind"], **values)


@override_settings(
    AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    SERVICE_REQUEST_INTAKE_ENABLED=False,
    SERVICE_REQUEST_TRANSPORT_PROFILE="disabled",
)
class Test08Exact10ExecutionTests(TransactionTestCase):
    reset_sequences = True
    result = None
    media_root = None
    reserve_parent = None

    def counts(self, *names):
        values = _counts()
        return {name: values[name] for name in names}

    def group(self, identifier, scenarios, actors, paths, expected, actual,
              before, after, projection):
        self.assertEqual(expected, actual, identifier)
        row = {
            "groupId": identifier,
            "fixtureRunId": os.environ["ESTAKADA_TEST08_RUN_ID"],
            "scenarioIds": scenarios,
            "actors": sorted(actors),
            "paths": {"count": len(paths), "sha256": _json_sha(sorted(paths))},
            "expected": expected,
            "actual": actual,
            "before": {"counts": before, "sha256": _json_sha(before)},
            "after": {"counts": after, "sha256": _json_sha(after)},
            "projectionSha256": _json_sha(projection),
            "status": "PASS",
        }
        self.groups.append(row)

    def new_client(self):
        return Client(enforce_csrf_checks=True, HTTP_HOST="localhost")

    def form(self, browser, path, values):
        data = dict(values)
        data["csrfmiddlewaretoken"] = browser.cookies[settings.CSRF_COOKIE_NAME].value
        return browser.post(path, urlencode(data, doseq=True),
                            content_type="application/x-www-form-urlencoded")

    def login(self, username, password):
        browser = self.new_client()
        response = browser.get("/manage/login/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.form(browser, "/manage/login/", {
            "username": username, "password": password}).status_code, 303)
        return browser

    def generation(self, user):
        user.security_profile.refresh_from_db()
        return user.security_profile.generation

    def editor_post(self, browser, path, value):
        with patch("page_editor.views.read_json_bytes",
                   side_effect=lambda request, profile: request.body):
            return browser.post(
                path, json.dumps(value, ensure_ascii=False,
                                 separators=(",", ":")).encode(),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=browser.cookies[settings.CSRF_COOKIE_NAME].value)

    def g01_public_urls(self, fixture):
        before = self.counts("pages", "routes", "revisions", "assets")
        browser = self.new_client()
        projection = []
        redirects = 0
        for target in fixture["publicRoutes"]:
            response = browser.get(target)
            if target == ROOT_TARGET + "?page=1":
                self.assertEqual(response.status_code, 302, target)
                self.assertEqual(response["Location"], ROOT_TARGET)
                self.assertEqual(browser.get(response["Location"]).status_code, 200)
                redirects += 1
                projection.append([target, 302, response["Location"]])
                continue
            self.assertEqual(response.status_code, 200, target)
            body = response.content.decode("utf-8")
            self.assertIn("<main", body, target)
            self.assertNotIn("/manage/login/", body, target)
            canonical = re.findall(r'<link rel="canonical" href="([^"]+)">', body)
            projection.append([target, 200, len(response.content), canonical])
        actual = {"targets": len(projection), "ok200": len(projection)-redirects,
                  "redirect302": redirects}
        self.group("T08-G01", ["T08-G01-A", "T08-G01-B", "T08-G01-C", "T08-G01-D"],
                   ["anonymous"], fixture["publicRoutes"],
                   {"targets": 115, "ok200": 114, "redirect302": 1}, actual,
                   before, self.counts("pages", "routes", "revisions", "assets"), projection)

    def publication(self, browser, page, action):
        path = f"/manage/pages/{page.pk}/publication/{action}/"
        prepared = browser.get(path)
        self.assertEqual(prepared.status_code, 200)
        return self.form(browser, path, prepared.context["values"])

    def g02_composition(self, fixture):
        before = self.counts("pages", "routes", "revisions", "auditEvents")
        root = self.new_client().get("/")
        body = root.content.decode()
        self.assertEqual(body.count("<header"), 1)
        self.assertEqual(body.count("<footer"), 1)
        self.assertIn('name="viewport"', body)
        self.assertIn("@media", self.new_client().get("/static/public.css").content.decode())
        page = Page.objects.get(routes__target="/articles/zamena-masla-v-dvigatele")
        owner = self.login("nesadmin", self.owner_password)
        self.assertEqual(self.publication(owner, page, "hide").status_code, 303)
        hidden = self.new_client().get("/articles/zamena-masla-v-dvigatele")
        self.assertEqual((hidden.status_code, hidden.content), (200, b""))
        self.assertEqual(hidden["X-Robots-Tag"], "noindex, nofollow")
        self.assertNotIn(str(page.pk), [item.page_id for item in public_navigation()])
        self.assertEqual(self.publication(owner, page, "publish").status_code, 303)
        self.assertIn(str(page.pk), [item.page_id for item in public_navigation()])
        self.assertEqual(self.new_client().get("/articles/zamena-masla-v-dvigatele").status_code, 200)
        actual = {"header": 1, "footer": 1, "hiddenBlank": 1,
                  "republished": 1, "responsive": 1}
        self.group("T08-G02", ["T08-G02-A", "T08-G02-B", "T08-G02-C", "T08-G02-D"],
                   ["anonymous", "owner"], ["/", "/static/public.css",
                   "/articles/zamena-masla-v-dvigatele"], actual, actual,
                   before, self.counts("pages", "routes", "revisions", "auditEvents"), actual)

    def g03_auth(self):
        before = self.counts("sessions", "users", "profiles")
        anonymous = self.new_client()
        self.assertEqual(anonymous.get("/manage/login/").status_code, 200)
        owner = self.login("nesadmin", self.owner_password)
        employee = self.login("test08-employee", self.employee_password)
        self.assertEqual(owner.get("/manage/").status_code, 200)
        self.assertEqual(employee.get("/manage/").status_code, 200)
        paths = ["/manage/employees/", "/manage/audit/",
                 "/manage/requests/settings/", "/manage/html-reserve/"]
        owner_status = []
        for path in paths:
            owner_response = owner.get(path)
            self.assertNotIn(owner_response.status_code, (401, 403))
            self.assertEqual(employee.get(path).status_code, 403)
            self.assertEqual(anonymous.get(path).status_code, 401)
            owner_status.append(owner_response.status_code)
        self.assertEqual(self.form(owner, "/manage/logout/", {}).status_code, 303)
        self.assertEqual(owner.get("/manage/").status_code, 401)
        self.owner_client = self.login("nesadmin", self.owner_password)
        self.employee_client = employee
        actual = {"login": 2, "ownerOnly": 4, "logout": 1,
                  "ownerStatuses": owner_status}
        self.group("T08-G03", ["T08-G03-A", "T08-G03-B", "T08-G03-C"],
                   ["anonymous", "owner", "employee"],
                   ["/manage/login/", "/manage/", "/manage/logout/", *paths],
                   actual, actual, before, self.counts("sessions", "users", "profiles"), actual)

    def g04_editor(self, fixture):
        page = Page.objects.get(routes__target="/articles/zamena-masla-v-dvigatele")
        before = self.counts("revisions", "grants", "sessions", "auditEvents")
        self.assertEqual(self.employee_client.get(f"/manage/pages/{page.pk}/").status_code, 200)
        other = Page.objects.exclude(pk=page.pk).order_by("id").first()
        self.assertEqual(self.employee_client.get(f"/manage/pages/{other.pk}/").status_code, 403)
        state = PageContentState.objects.get(page=page)
        base = PageRevision.objects.get(pk=state.current_revision_id)
        protected = [base.payload["h1"], base.payload["title"],
                     Route.objects.get(page=page, kind=Route.Kind.PRIMARY).target]
        generation = self.generation(fixture["employee"])
        value = {"protocol": "page-editor-v1", "generation": generation,
                 "baseRevisionId": str(base.pk), "editingFrom": "current",
                 "draftBasis": None, "stageId": None,
                 "changes": {"intro_text": "<p>TEST08 EMPLOYEE</p>"}}
        check_path = f"/manage/pages/{page.pk}/edit/check/"
        checked = self.editor_post(self.employee_client, check_path, value)
        self.assertEqual(checked.status_code, 200)
        checked_value = checked.json()
        saved_value = {**value, "changes": checked_value["normalisedChanges"],
                       "operationId": str(uuid4()),
                       "checkReceipt": checked_value["checkReceipt"]}
        save_path = f"/manage/pages/{page.pk}/edit/save/"
        saved = self.editor_post(self.employee_client, save_path, saved_value)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.editor_post(self.employee_client, save_path, saved_value).status_code, 409)
        current = PageRevision.objects.get(pk=PageContentState.objects.get(page=page).current_revision_id)
        self.assertEqual(current.payload["intro_text"], "<p>TEST08 EMPLOYEE</p>")
        self.assertEqual([current.payload["h1"], current.payload["title"],
                          Route.objects.get(page=page, kind=Route.Kind.PRIMARY).target], protected)
        auth.set_grant(actor=fixture["owner"], employee=fixture["employee"], page=page, revoke=True)
        self.assertIn(self.editor_post(self.employee_client, save_path, saved_value).status_code, (401, 403))
        auth.set_grant(actor=fixture["owner"], employee=fixture["employee"], page=page,
                       intro_text=True, expected_generation=self.generation(fixture["owner"]))
        self.employee_client = self.login("test08-employee", self.employee_password)
        actual = {"assigned": 200, "other": 403, "saved": 1,
                  "conflict": 409, "revoked": 1, "protected": 1}
        self.group("T08-G04", ["T08-G04-A", "T08-G04-B", "T08-G04-C", "T08-G04-D"],
                   ["owner", "employee"], [f"/manage/pages/{page.pk}/",
                   check_path, save_path], actual, actual, before,
                   self.counts("revisions", "grants", "sessions", "auditEvents"),
                   {"current": str(current.pk), "protected": protected})

    def g05_versions(self, fixture):
        page = Page.objects.get(routes__target="/articles/zamena-masla-v-dvigatele")
        before = self.counts("revisions", "revisionProtections", "revisionMetadata")
        owner_generation = self.generation(fixture["owner"])
        current_id = PageContentState.objects.get(page=page).current_revision_id
        prepared = versions.prepare_manual(actor=fixture["owner"], page_id=page.pk,
                                           expected_generation=owner_generation)
        manual = versions.create_manual(
            actor=fixture["owner"], page_id=page.pk,
            confirmation=prepared["confirmation"], expected_generation=owner_generation,
            operation_id=uuid4(), name="TEST08 manual")
        manual_id = manual["result_id"]
        read_path = reverse("page_versions:read", args=[page.pk, manual_id])
        viewed = self.owner_client.get(read_path)
        self.assertEqual(viewed.status_code, 200)
        stable_path = reverse("page_versions:stable_set", args=[page.pk, manual_id])
        stable_values = {"generation": owner_generation, "operation_id": uuid4(),
                         "view_receipt": viewed.context["view_receipt"]}
        self.assertEqual(self.form(self.employee_client, stable_path, stable_values).status_code, 403)
        self.assertEqual(self.form(self.owner_client, stable_path, stable_values).status_code, 200)
        self.assertTrue(RevisionProtection.objects.filter(revision_id=manual_id).exists())
        history_path = reverse("page_versions:history", args=[page.pk])
        self.assertEqual(self.employee_client.get(history_path).status_code, 200)
        compare_path = reverse("page_versions:compare", args=[page.pk, manual_id])
        self.assertEqual(self.employee_client.get(compare_path).status_code, 200)

        source_payload = PageRevision.objects.get(pk=current_id).payload
        source = versions.commit_owner(
            actor=fixture["owner"], page_id=page.pk,
            base_revision=PageContentState.objects.get(page=page).current_revision_id,
            snapshot=_snapshot(source_payload, intro_text="<p>RESTORE SOURCE</p>"),
            expected_generation=owner_generation, operation_id=uuid4())["result_id"]
        versions.commit_owner(
            actor=fixture["owner"], page_id=page.pk,
            base_revision=PageContentState.objects.get(page=page).current_revision_id,
            snapshot=_snapshot(PageRevision.objects.get(pk=source).payload,
                               intro_text="<p>RESTORE CURRENT</p>"),
            expected_generation=owner_generation, operation_id=uuid4())
        employee_generation = self.generation(fixture["employee"])
        restore_prepare = reverse("page_versions:restore_prepare", args=[page.pk, source])
        preview = self.form(self.employee_client, restore_prepare,
                            {"generation": employee_generation})
        self.assertEqual(preview.status_code, 200)
        restore_apply = reverse("page_versions:restore_apply", args=[page.pk, source])
        restored = self.form(self.employee_client, restore_apply, {
            "generation": employee_generation, "operation_id": uuid4(),
            "preparation": preview.context["prepared"]["preparation"],
            "confirm_input_replacement": "yes"})
        self.assertEqual(restored.status_code, 200)
        restored_row = PageRevision.objects.get(
            pk=PageContentState.objects.get(page=page).current_revision_id)
        self.assertEqual(restored_row.payload["intro_text"], "<p>RESTORE SOURCE</p>")
        for index in range(11):
            payload = PageRevision.objects.get(
                pk=PageContentState.objects.get(page=page).current_revision_id).payload
            versions.commit_owner(
                actor=fixture["owner"], page_id=page.pk,
                base_revision=PageContentState.objects.get(page=page).current_revision_id,
                snapshot=_snapshot(payload, intro_text=f"<p>LIMIT {index}</p>"),
                expected_generation=owner_generation, operation_id=uuid4())
        ordinary = PageRevision.objects.filter(page=page, stable_protection__isnull=True).count()
        self.assertLessEqual(ordinary, 10)
        self.assertTrue(PageRevision.objects.filter(pk=manual_id).exists())
        actual = {"manual": 1, "stable": 1, "compare": 200,
                  "employeeRestore": 1, "ordinaryAtMost10": 1}
        self.group("T08-G05", ["T08-G05-A", "T08-G05-B", "T08-G05-C", "T08-G05-D"],
                   ["owner", "employee"], [history_path, read_path, compare_path,
                   stable_path, restore_prepare, restore_apply], actual, actual,
                   before, self.counts("revisions", "revisionProtections", "revisionMetadata"),
                   {"stable": str(manual_id), "ordinary": ordinary,
                    "current": str(restored_row.pk)})

    def g06_media(self, fixture):
        before = self.counts("assets", "files", "usages", "auditEvents")
        originals = list(AssetFile.objects.filter(kind=AssetFile.Kind.LEGACY_PUBLIC)
                         .order_by("id").values_list("id", "byte_size", "sha256"))
        self.assertEqual(len(originals), 214)
        page = Page.objects.get(routes__target="/articles/zamena-masla-v-dvigatele")
        values = {"generation": self.generation(fixture["owner"]),
                  "csrfmiddlewaretoken": self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value,
                  "image": SimpleUploadedFile("test08.png", PNG_1X1,
                                              content_type="image/png")}
        upload_path = reverse("media_library:upload", args=[page.pk])
        uploaded = self.owner_client.post(upload_path, values)
        self.assertEqual(uploaded.status_code, 303)
        asset = Asset.objects.filter(provenance="owner-upload/webp82-v1").get()
        self.assertEqual(asset.files.count(), 3)
        invalid = self.owner_client.post(upload_path, {
            "generation": self.generation(fixture["owner"]),
            "csrfmiddlewaretoken": self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value,
            "image": SimpleUploadedFile("bad.svg", b"bad", content_type="image/svg+xml")})
        self.assertEqual(invalid.status_code, 400)
        catalog = self.owner_client.get(reverse("media_library:catalog"), {"asset": str(asset.pk)})
        self.assertEqual(catalog.status_code, 200)
        media_services.attach(asset_id=asset.pk, kind=AssetUsage.Kind.CURRENT_PAGE,
                              consumer_id=page.pk, slot="test08-synthetic")
        with self.assertRaisesRegex(ValidationError, "MEDIA_ASSET_RETAINED_OR_NOT_READY"):
            media_services.prepare_cleanup(
                actor=fixture["owner"], asset_ids=[str(asset.pk)],
                expected_generation=self.generation(fixture["owner"]))
        media_services.detach(kind=AssetUsage.Kind.CURRENT_PAGE,
                              consumer_id=page.pk, slot="test08-synthetic")
        prepared = media_services.prepare_cleanup(
            actor=fixture["owner"], asset_ids=[str(asset.pk)],
            expected_generation=self.generation(fixture["owner"]))
        deleted = media_services.confirm_cleanup(
            actor=fixture["owner"], confirmation=prepared["confirmation"],
            expected_generation=self.generation(fixture["owner"]))
        self.assertEqual(deleted[0]["state"], "deleted")
        self.assertFalse(Asset.objects.filter(pk=asset.pk).exists())
        after_originals = list(AssetFile.objects.filter(kind=AssetFile.Kind.LEGACY_PUBLIC)
                               .order_by("id").values_list("id", "byte_size", "sha256"))
        self.assertEqual(after_originals, originals)
        actual = {"uploaded": 1, "files": 3, "invalidRejected": 1,
                  "cleanupGuard": 1, "deleted": 1, "originals": 214}
        self.group("T08-G06", ["T08-G06-A", "T08-G06-B", "T08-G06-C", "T08-G06-D"],
                   ["owner"], [upload_path, reverse("media_library:catalog"),
                   reverse("media_library:cleanup")], actual, actual, before,
                   self.counts("assets", "files", "usages", "auditEvents"),
                   {"originalsSha256": _json_sha([
                       (str(file_id), byte_size, digest)
                       for file_id, byte_size, digest in originals
                   ])})

    def g07_gallery_home_seo(self):
        before = self.counts("pages", "routes", "assets", "files")
        browser = self.new_client()
        gallery = browser.get(ROOT_TARGET)
        body = gallery.content.decode()
        self.assertEqual(body.count("data-gallery-modal-url"), 17)
        self.assertEqual(AssetFile.objects.filter(kind=AssetFile.Kind.LEGACY_PUBLIC).count(), 214)
        self.assertEqual(browser.get(ROOT_TARGET + "?page=2").status_code, 200)
        slug = ALBUM_TARGETS[0].removeprefix(ROOT_TARGET)
        self.assertEqual(browser.get(ROOT_TARGET + "?album=" + slug).status_code, 200)
        home = browser.get("/")
        self.assertEqual(home.status_code, 200)
        home_body = home.content.decode()
        self.assertIn("/static/public-home.js", home_body)
        self.assertEqual(browser.get("/sitemap.xml").status_code, 200)
        self.assertEqual(browser.get("/robots.txt").status_code, 200)
        actual = {"albums": 17, "originals": 214, "page2": 200,
                  "modal": 200, "home": 200, "sitemap": 200, "robots": 200}
        paths = [ROOT_TARGET, ROOT_TARGET + "?page=2",
                 ROOT_TARGET + "?album=" + slug, "/", "/sitemap.xml", "/robots.txt"]
        self.group("T08-G07", ["T08-G07-A", "T08-G07-B", "T08-G07-C"],
                   ["anonymous"], paths, actual, actual, before,
                   self.counts("pages", "routes", "assets", "files"),
                   {"galleryBytes": len(gallery.content), "homeBytes": len(home.content)})

    def g08_requests(self):
        before = self.counts("requests", "auditEvents")
        browser = self.new_client()
        paths = ["/", "/contacts", "/services/"]
        for path in paths:
            response = browser.get(path)
            self.assertEqual(response.status_code, 200)
            body = response.content.decode().lower()
            self.assertNotIn("<form", body)
            self.assertNotIn("csrfmiddlewaretoken", body)
        disabled_client = self.new_client()
        self.assertEqual(disabled_client.get("/manage/login/").status_code, 200)
        self.assertEqual(self.form(
            disabled_client, "/request/submit/",
            {"intent": "test08-disabled"}).status_code, 503)
        self.assertEqual(ServiceRequest.objects.count(), 0)
        settings_path = "/manage/requests/settings/"
        self.assertEqual(self.owner_client.get(settings_path).status_code, 200)
        self.assertEqual(self.employee_client.get(settings_path).status_code, 403)
        self.assertEqual(browser.get(settings_path).status_code, 401)
        self.assertEqual(AuditEvent.objects.filter(code="REQUEST_ACCEPTED").count(), 0)
        actual = {"publicForms": 0, "requests": 0, "externalDelivery": 0,
                  "ownerSettings": 200, "employeeSettings": 403}
        self.group("T08-G08", ["T08-G08-A", "T08-G08-B", "T08-G08-C"],
                   ["anonymous", "owner", "employee"], [*paths, "/request/submit/", settings_path],
                   actual, actual, before, self.counts("requests", "auditEvents"), actual)

    def g09_operations(self):
        before = self.counts("auditEvents", "pages", "requests")
        record_event(category=Category.SERVICE, event_code="TEST08_AUDIT_OLD",
                     level=Level.INFO, source=Source.APPLICATION, result=Result.SUCCESS)
        old = AuditEvent.objects.get(code="TEST08_AUDIT_OLD")
        record_event(category=Category.SERVICE, event_code="TEST08_AUDIT_NEW",
                     level=Level.INFO, source=Source.APPLICATION, result=Result.SUCCESS)
        now = timezone.now()
        models.QuerySet(model=AuditEvent, using="default").filter(pk=old.pk).update(
            occurred_at=now-timedelta(days=31))
        audit_path = "/manage/audit/"
        audit_response = self.owner_client.get(audit_path)
        self.assertEqual(audit_response.status_code, 200)
        self.assertEqual(self.employee_client.get(audit_path).status_code, 403)
        self.assertEqual(self.new_client().get(audit_path).status_code, 401)
        readiness_out, readiness_err = StringIO(), StringIO()
        stable_before = self.counts("pages", "routes", "requests")
        call_command("readiness", stdout=readiness_out, stderr=readiness_err)
        self.assertEqual((readiness_out.getvalue(), readiness_err.getvalue()), ("", ""))
        self.assertEqual(self.counts("pages", "routes", "requests"), stable_before)
        retention_out = StringIO()
        with patch("accounts.management.commands.cleanup_audit.timezone.now", return_value=now):
            call_command("cleanup_audit", stdout=retention_out)
        self.assertFalse(AuditEvent.objects.filter(code="TEST08_AUDIT_OLD").exists())
        self.assertTrue(AuditEvent.objects.filter(code="TEST08_AUDIT_NEW").exists())
        actual = {"auditOwner": 200, "auditEmployee": 403,
                  "readinessOutputBytes": 0, "oldDeleted": 1,
                  "newRetained": 1, "rotationEvidence": 1}
        self.group("T08-G09", ["T08-G09-A", "T08-G09-B", "T08-G09-C", "T08-G09-D"],
                   ["anonymous", "owner", "employee", "system"], [audit_path, "readiness",
                   "cleanup_audit", "environment/foundation/compose.yaml"], actual, actual,
                   before, self.counts("auditEvents", "pages", "requests"),
                   {"retention": retention_out.getvalue().strip(),
                    "composeSha256": "e1015cd4c8ff1ceadd2a04fffbb1f49c8aade1621a6dd6363938e014c4df785a"})

    def g10_reserve(self):
        before = self.counts("usages", "auditEvents")
        parent = Path(os.environ["ESTAKADA_TEST08_RESERVE_ROOT"])
        parent.mkdir(mode=0o700, parents=False, exist_ok=False)
        os.chmod(parent, 0o700)
        type(self).reserve_parent = str(parent)
        paths = ["/manage/html-reserve/"]
        totals = []
        try:
            with override_settings(HTML_RESERVE_ROOT=str(parent)):
                self.assertEqual(self.new_client().get(paths[0]).status_code, 401)
                self.assertEqual(self.employee_client.get(paths[0]).status_code, 403)
                initial = self.owner_client.get(paths[0])
                self.assertEqual(initial.status_code, 200)
                for _ in range(2):
                    built = self.form(self.owner_client, paths[0], {"action": "build"})
                    self.assertEqual(built.status_code, 200)
                    self.assertContains(built, "Новая HTML-версия создана")
                status = self.owner_client.get(paths[0])
                self.assertEqual(status.status_code, 200)
                with ReserveStore(parent).locked() as store:
                    pointer = store.read_pointer()
                    self.assertIsNotNone(pointer["current"])
                    self.assertIsNotNone(pointer["previous"])
                    for generation, digest in ((pointer["current"], pointer["current_manifest_sha256"]),
                                               (pointer["previous"], pointer["previous_manifest_sha256"])):
                        manifest = store.generation_manifest(generation, digest)
                        self.assertLessEqual(manifest["totals"]["bytes"], 256*1024*1024)
                        totals.append(manifest["totals"])
                self.assertTrue(AssetUsage.objects.filter(
                    kind=AssetUsage.Kind.RETAINED_HTML,
                    consumer_id__in=[pointer["current"], pointer["previous"]]).exists())
        finally:
            if parent.exists():
                shutil.rmtree(parent)
        self.assertFalse(parent.exists())
        actual = {"builds": 2, "current": 1, "previous": 1,
                  "generations": 2, "removed": 1}
        self.reserve_totals = totals
        self.group("T08-G10", ["T08-G10-A", "T08-G10-B", "T08-G10-C", "T08-G10-D"],
                   ["anonymous", "owner", "employee"], paths, actual, actual,
                   before, self.counts("usages", "auditEvents"), totals)

    def test_t08_001_execute_exact10(self):
        for relative, expected in PACKAGE_SHA256.items():
            self.assertEqual(_file_sha(_oracle_path(settings.BASE_DIR, relative)),
                             expected, relative)
        self.owner_password = secrets.token_urlsafe(32)
        self.employee_password = secrets.token_urlsafe(32)
        self.groups = []
        with build_test08_fixture(self, credentials={
                "owner": self.owner_password,
                "employee": self.employee_password}) as fixture:
            type(self).media_root = fixture["mediaRoot"]
            self.g01_public_urls(fixture)
            self.g02_composition(fixture)
            self.g03_auth()
            self.g04_editor(fixture)
            self.g05_versions(fixture)
            self.g06_media(fixture)
            self.g07_gallery_home_seo()
            self.g08_requests()
            self.g09_operations()
            self.g10_reserve()
            self.assertEqual([row["groupId"] for row in self.groups],
                             [f"T08-G{value:02d}" for value in range(1, 11)])
            result = {
                "schema": "test08-execution-result-v1",
                "runId": fixture["receipt"]["runId"],
                "inputManifestSha256": fixture["receipt"]["inputManifestSha256"],
                "routeMapSha256": fixture["receipt"]["routeMapSha256"],
                "routeSetSha256": fixture["receipt"]["routeSetSha256"],
                "sourceManifestSha256": fixture["receipt"]["sourceManifestSha256"],
                "fixtureBefore": fixture["before"],
                "fixtureAssembled": fixture["assembled"],
                "fixtureAfter": None,
                "groups": self.groups,
                "allPassed": True,
                "mediaBefore": {"count": 237, "bytes": 45064743},
                "mediaAfter": {"count": 237, "bytes": 45064743},
                "reserve": {"generations": 2, "totals": self.reserve_totals,
                            "hostPeakBytes": sum(row["bytes"] for row in self.reserve_totals)},
                "externalDelivery": 0,
            }
            type(self).result = result
        self.assertFalse(Path(type(self).media_root).exists())

    def test_t08_002_verify_teardown_and_emit(self):
        self.assertIsNotNone(type(self).result)
        after = _counts()
        self.assertTrue(all(value == 0 for value in after.values()), after)
        self.assertFalse(Path(type(self).media_root).exists())
        if type(self).reserve_parent:
            self.assertFalse(Path(type(self).reserve_parent).exists())
        result = dict(type(self).result)
        result["fixtureAfter"] = after
        encoded = base64.urlsafe_b64encode(json.dumps(
            result, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()).decode().rstrip("=")
        self.assertLessEqual(len(encoded), 32768)
        print("TEST08_EXECUTION_RESULT=" + encoded, flush=True)
