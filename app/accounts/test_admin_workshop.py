import hashlib
import re
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse, resolve

from content.models import Page, Route
from page_versions import schema as version_schema
from page_versions.models import PageRevision, PageContentState
from shared_content.models import SharedBlock
from . import services

PASSWORD = "SYNTHETIC-admin-workshop-password"
FAST_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
APP_ROOT = Path(__file__).resolve().parents[1]
LOGO = Path(__file__).resolve().parent / "assets/brand-logo.png"
LOGO_SHA = "39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5"


class FormClient(Client):
    def post(self, path, data=None, content_type=None, **kwargs):
        if content_type == "application/x-www-form-urlencoded" and isinstance(data, dict):
            data = urlencode(data)
        if content_type is None:
            return super().post(path, data=data, **kwargs)
        return super().post(path, data=data, content_type=content_type, **kwargs)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, AUTH_TRUSTED_PROXY_HOST=None,
                   ENVIRONMENT="dev")
class AdminWorkshopTests(TransactionTestCase):
    def setUp(self):
        cls = self
        cls.owner = services.bootstrap_owner(PASSWORD)
        cls.employee = services.create_employee(
            actor=cls.owner, username="workshop-employee", password=PASSWORD)
        cls.other_employee = services.create_employee(
            actor=cls.owner, username="workshop-other", password=PASSWORD)
        SharedBlock.objects.create(kind="header")
        SharedBlock.objects.create(kind="footer")
        cls.page = Page.objects.create(name="Workshop page", kind=Page.Kind.SERVICE)
        Route.objects.create(page=cls.page, kind=Route.Kind.PRIMARY, target="/workshop/")
        services.set_grant(actor=cls.owner, employee=cls.employee, page=cls.page,
                           intro_text=True, main_text=False, price=False)
        payload = version_schema.snapshot_v1(
            cls.page.kind, intro_text="<p>Вводный текст</p>",
            main_text="<p>Основной текст</p>", h1="Workshop page").data()
        revision = PageRevision.objects.create(
            page=cls.page, sequence=1, schema_version="page-content-v1",
            payload=payload, payload_hash=version_schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=cls.owner.pk)
        PageContentState.objects.create(page=cls.page, current_revision=revision)
        cls.parent_a = Page.objects.create(name="Повтор", kind=Page.Kind.SERVICE_SECTION)
        cls.parent_b = Page.objects.create(name="Повтор", kind=Page.Kind.SERVICE_SECTION)
        cls.root_collision = Page.objects.create(
            name="Основные страницы", kind=Page.Kind.SERVICE_SECTION)
        cls.child_a = Page.objects.create(
            name="Дочерняя A", kind=Page.Kind.ARTICLE, parent=cls.parent_a)
        cls.child_b = Page.objects.create(
            name="Дочерняя B", kind=Page.Kind.ARTICLE, parent=cls.parent_b)
        cls.collision_child = Page.objects.create(
            name="Дочерняя корня", kind=Page.Kind.ARTICLE, parent=cls.root_collision)
        Route.objects.create(page=cls.child_a, kind=Route.Kind.PRIMARY, target="/repeat/a/")
        Route.objects.create(page=cls.child_b, kind=Route.Kind.PRIMARY, target="/repeat/b/")
        Route.objects.create(page=cls.collision_child, kind=Route.Kind.PRIMARY,
                             target="/root-collision/")
        services.set_grant(actor=cls.owner, employee=cls.employee, page=cls.child_a,
                           intro_text=True, main_text=True, price=False)
        services.set_grant(actor=cls.owner, employee=cls.other_employee, page=cls.child_b,
                           intro_text=True, main_text=True, price=False)

    def signed(self, username):
        browser = FormClient(HTTP_HOST="localhost")
        response = browser.post(
            "/manage/login/", {"username": username, "password": PASSWORD},
            content_type="application/x-www-form-urlencoded",
            REMOTE_ADDR="192.0.2.71")
        self.assertEqual(response.status_code, 303)
        return browser

    def test_admw_001_anonymous_login_shell_and_no_password_value(self):
        response = FormClient(HTTP_HOST="localhost").get("/manage/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-admin-workshop")
        self.assertContains(response, reverse("accounts:brand-logo"))
        self.assertContains(response, "Панель администрирования сайта")
        self.assertNotContains(response, reverse("accounts:employees"))
        password = re.search(rb'<input[^>]+name="password"[^>]*>', response.content)
        self.assertIsNotNone(password)
        self.assertNotIn(b"value=", password.group(0))

    def test_admw_002_logo_transport_and_exact_bytes(self):
        url = reverse("accounts:brand-logo")
        expected = LOGO.read_bytes()
        self.assertEqual(len(expected), 30190)
        self.assertEqual(hashlib.sha256(expected).hexdigest(), LOGO_SHA)
        for browser in (FormClient(HTTP_HOST="localhost"), self.signed("nesadmin")):
            get = browser.get(url)
            head = browser.head(url)
            self.assertEqual(get.status_code, 200)
            self.assertEqual(get["Content-Type"], "image/png")
            self.assertEqual(get.content, expected)
            self.assertEqual(get["Content-Length"], "30190")
            self.assertEqual(head.status_code, 200)
            self.assertEqual(head.content, b"")
            self.assertEqual(head["Content-Length"], "30190")
            self.assertEqual(get["Cache-Control"], "private, no-store")
            self.assertIn("Cookie", get["Vary"])
            self.assertEqual(get["X-Content-Type-Options"], "nosniff")
            for header in ("Cache-Control", "Vary", "X-Content-Type-Options",
                           "X-Frame-Options", "Content-Security-Policy-Report-Only"):
                self.assertEqual(head[header], get[header])
        anonymous = FormClient(HTTP_HOST="localhost")
        self.assertEqual(anonymous.post(url).status_code, 405)
        self.assertIn(anonymous.get("/manage/assets/brand-logo-copy.png").status_code,
                      (401, 404))
        with TemporaryDirectory() as directory:
            candidate = Path(directory) / "brand-logo.png"
            for payload in (b"short", b"0" * 30190):
                candidate.write_bytes(payload)
                with patch("accounts.views.BRAND_LOGO_PATH", candidate):
                    failed = anonymous.get(url)
                self.assertEqual(failed.status_code, 404)
                self.assertNotIn(str(candidate).encode(), failed.content)
        with patch("accounts.views.os.open", side_effect=OSError("private failure")):
            failed = anonymous.get(url)
        self.assertEqual(failed.status_code, 404)
        self.assertNotContains(failed, "private failure", status_code=404)

    def test_admw_003_owner_navigation_and_dashboard_contract(self):
        browser = self.signed("nesadmin")
        response = browser.get("/manage/")
        self.assertEqual(response.status_code, 200)
        for marker in ("data-admin-workshop", "data-pages-workspace", "Структура сайта",
                       "Найти страницу", "Категория", "Редактировать",
                       "Повтор (раздел 1)", "Повтор (раздел 2)",
                       "Основные страницы (раздел 1)",
                       "Общих блоков: 2"):
            self.assertContains(response, marker)
        self.assertNotContains(response, "/workshop/")
        dashboard_template = (
            APP_ROOT / "accounts/templates/accounts/dashboard.html"
        ).read_text()
        self.assertNotIn("row.category_label", dashboard_template)
        self.assertNotIn("row.primary_target", dashboard_template)
        self.assertEqual(response.context["shared_count"], SharedBlock.objects.count())
        for name in ("accounts:dashboard", "accounts:page-tree", "accounts:employees",
                     "media_library:catalog", "service_requests:list",
                     "accounts:html-reserve", "accounts:audit-events"):
            exact_href = f'href="{reverse(name)}"'.encode()
            self.assertEqual(response.content.count(exact_href), 1)
        self.assertContains(response, "nesadmin")
        self.assertContains(response, reverse("accounts:logout"))
        editor_href = f'href="{reverse("page_editor:editor", args=[self.page.pk])}"'.encode()
        access_href = f'href="{reverse("accounts:page-access", args=[self.page.pk])}"'.encode()
        self.assertIn(editor_href, response.content)
        self.assertNotIn(access_href, response.content)
        search = browser.get("/manage/?" + urlencode({
            "q": "REPEAT/A", "category": f"parent:{self.parent_a.pk}"}))
        self.assertEqual(search.status_code, 200)
        self.assertContains(search, "Дочерняя A")
        self.assertEqual([row.page.pk for row in search.context["listing"]["rows"]],
                         [self.child_a.pk])
        category_only = browser.get(
            "/manage/?" + urlencode({"category": f"parent:{self.parent_b.pk}"}))
        self.assertEqual([row.page.pk for row in category_only.context["listing"]["rows"]],
                         [self.child_b.pk])
        for index in range(1, 14):
            Page.objects.create(name=f"Needle + {index:02d}", kind=Page.Kind.ARTICLE,
                                parent=self.parent_a, position=index)
        token = f"parent:{self.parent_a.pk}"
        needle = urlencode({"q": "Needle +", "category": token})
        first = browser.get("/manage/?" + needle)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.context["listing"]["found"], 13)
        self.assertEqual(len(first.context["listing"]["rows"]), 12)
        self.assertEqual(first.context["listing"]["next_query"],
                         "?q=Needle+%2B&category=" + urlencode({"v": token})[2:] + "&p=2")
        second = browser.get("/manage/?" + needle + "&p=2")
        self.assertEqual(len(second.context["listing"]["rows"]), 1)
        self.assertEqual(second.context["listing"]["previous_query"],
                         "?q=Needle+%2B&category=" + urlencode({"v": token})[2:] + "&p=1")
        for query in ("?q=a&q=b", "?category=unknown", "?p=01", "?p=9999",
                      "?extra=1", "?q=bad%00value"):
            self.assertEqual(browser.get("/manage/" + query).status_code, 400, query)
        while Page.objects.count() < 512:
            index = Page.objects.count()
            Page.objects.create(name=f"Boundary {index:03d}", kind=Page.Kind.EMPTY,
                                position=1000 + index)
        boundary = browser.get("/manage/")
        self.assertEqual(boundary.status_code, 200)
        self.assertContains(boundary, "Страниц: 512")
        Page.objects.create(name="Boundary overflow", kind=Page.Kind.EMPTY, position=9999)
        overflow = browser.get("/manage/")
        self.assertEqual(overflow.status_code, 503)
        self.assertNotContains(overflow, "Boundary 511", status_code=503)

    def test_admw_004_employee_navigation_and_editor_contract(self):
        browser = self.signed("workshop-employee")
        response = browser.get("/manage/")
        self.assertEqual(response.status_code, 200)
        editor_href = f'href="{reverse("page_editor:editor", args=[self.page.pk])}"'.encode()
        access_href = f'href="{reverse("accounts:page-access", args=[self.page.pk])}"'.encode()
        self.assertIn(editor_href, response.content)
        self.assertNotIn(access_href, response.content)
        self.assertContains(response, "Другой раздел")
        self.assertContains(response, reverse("service_requests:list"))
        self.assertNotContains(response, "Повтор")
        self.assertNotContains(response, str(self.parent_a.pk))
        for name in ("accounts:page-tree", "accounts:employees", "media_library:catalog",
                     "accounts:html-reserve", "accounts:audit-events"):
            exact_href = f'href="{reverse(name)}"'.encode()
            self.assertNotIn(exact_href, response.content)
        editor = (APP_ROOT / "page_editor/templates/page_editor/editor.html").read_text()
        for marker in ("data-editor-page", "name=\"csrfmiddlewaretoken\"",
                       "editor-bridge.mjs", "data-editor-source-link"):
            self.assertIn(marker, editor)
        rendered = browser.get(reverse("page_editor:editor", args=[self.page.pk]))
        self.assertEqual(rendered.status_code, 200)
        for marker in ("editor-workspace", "Структура сайта", "Основные страницы",
                       "Содержимое", "Версии", "data-editor-page"):
            self.assertContains(rendered, marker)
        self.assertNotContains(rendered, "Дочерняя B")
        self.assertNotIn(f'href="{reverse("accounts:page-tree")}"'.encode(),
                         rendered.content)
        self.assertEqual([field["name"] for field in rendered.context["initial_state"]["fields"]],
                         ["intro_text"])
        self.assertContains(rendered, 'href="/workshop/"')

    def test_admw_005_representative_screen_and_form_hook_inventory(self):
        routes = {
            "accounts:login": reverse("accounts:login"),
            "accounts:dashboard": reverse("accounts:dashboard"),
            "accounts:page-tree": reverse("accounts:page-tree"),
            "page_editor:editor": reverse("page_editor:editor", args=[self.page.pk]),
            "page_versions:history": reverse("page_versions:history", args=[self.page.pk]),
            "shared_content:editor": reverse("shared_content:editor", args=["header"]),
            "media_library:catalog": reverse("media_library:catalog"),
            "service_requests:list": reverse("service_requests:list"),
            "accounts:audit-events": reverse("accounts:audit-events"),
            "accounts:employees": reverse("accounts:employees"),
            "accounts:html-reserve": reverse("accounts:html-reserve"),
        }
        for name, path in routes.items():
            self.assertEqual(resolve(path).view_name, name)
        owner = self.signed("nesadmin")
        rendered = {}
        for name in ("accounts:dashboard", "accounts:page-tree", "media_library:catalog",
                     "service_requests:list", "accounts:audit-events"):
            rendered[name] = owner.get(routes[name])
            self.assertEqual(rendered[name].status_code, 200, name)
            self.assertEqual(owner.post(routes[name]).status_code, 405, name)
        editor_href = f'href="{routes["page_editor:editor"]}"'.encode()
        access_url = reverse("accounts:page-access", args=[self.page.pk])
        access_href = f'href="{access_url}"'.encode()
        tree = rendered["accounts:page-tree"]
        self.assertIn(editor_href, tree.content)
        self.assertNotIn(access_href, tree.content)
        compatibility = owner.get(access_url)
        self.assertEqual(compatibility.status_code, 200)
        self.assertIn(editor_href, compatibility.content)
        editor_page = owner.get(routes["page_editor:editor"])
        self.assertEqual(editor_page.status_code, 200)
        for marker in ("editor-workspace", "editor-metadata", "editor-tabs",
                       "data-editor-page", "data-editor-status", "data-editor-dirty",
                       "data-editor-field", "editor-initial-state", "editor-bridge.mjs",
                       "/workshop/", "Скрыто"):
            self.assertContains(editor_page, marker)
        self.assertContains(editor_page, routes["page_versions:history"])
        main_only_page = Page.objects.create(
            name="Main-only workshop page", kind=Page.Kind.ARTICLE)
        Route.objects.create(
            page=main_only_page, kind=Route.Kind.PRIMARY,
            target="/main-only-workshop/")
        main_only_payload = version_schema.snapshot_v1(
            main_only_page.kind, intro_text="",
            main_text="<p>Существующий основной текст страницы</p>",
            h1="Main-only workshop page").data()
        main_only_revision = PageRevision.objects.create(
            page=main_only_page, sequence=1, schema_version="page-content-v1",
            payload=main_only_payload,
            payload_hash=version_schema.digest(main_only_payload),
            kind=PageRevision.Kind.INITIAL, author_id=self.owner.pk)
        PageContentState.objects.create(
            page=main_only_page, current_revision=main_only_revision)
        main_first = owner.get(reverse(
            "page_editor:editor", args=[main_only_page.pk]))
        self.assertEqual(main_first.status_code, 200)
        self.assertEqual(
            [field["name"] for field in main_first.context["initial_state"]["fields"]],
            ["main_text", "intro_text"])
        self.assertLess(
            main_first.content.index(b'data-editor-field="main_text"'),
            main_first.content.index(b'data-editor-field="intro_text"'))
        post_only = (
            reverse("page_editor:check", args=[self.page.pk]),
            reverse("page_versions:manual_create", args=[self.page.pk]),
            reverse("shared_content:check", args=["header"]),
        )
        for path in post_only:
            self.assertEqual(owner.get(path).status_code, 405, path)
        sources = {
            "accounts/templates/accounts/login.html": ("{% extends 'accounts/base.html' %}", "method=\"post\"", "name=\"username\"", "name=\"password\""),
            "accounts/templates/accounts/tree.html": ("{% extends 'accounts/base.html' %}", "page_editor:editor", "accounts:tree-command", "accounts:page-publication", "accounts:page-delete"),
            "accounts/templates/accounts/page_access.html": ("{% extends 'accounts/base.html' %}", "page_editor:editor", "page_versions:history"),
            "page_editor/templates/page_editor/editor.html": ("{% extends 'accounts/base.html' %}", "data-editor-page", "editor-bridge.mjs"),
            "page_versions/templates/page_versions/history.html": ("{% extends 'accounts/base.html' %}", "data-version-history", "page_versions:compare"),
            "shared_content/templates/shared_content/editor.html": ("{% extends 'accounts/base.html' %}", "data-shared-editor", "data-editor-form", "editor.js"),
            "media_library/templates/media_library/catalog.html": ("{% extends 'accounts/base.html' %}", "multipart/form-data", "data-media-upload"),
            "service_requests/templates/service_requests/list.html": ("{% extends 'accounts/base.html' %}", "requests-table-wrap", "service_requests:detail"),
            "audit/templates/audit/events.html": ("{% extends 'accounts/base.html' %}", "audit-filters", "audit-table-wrap"),
        }
        for relative, markers in sources.items():
            text = (APP_ROOT / relative).read_text(encoding="utf-8")
            for marker in markers:
                self.assertIn(marker, text, relative)

    def test_admw_006_css_scope_and_source_manifest_admission(self):
        css = (Path(__file__).resolve().parent / "assets/manage.css").read_text()
        for marker in ("--workshop-brand:#f4ac40", ".admin-workshop",
                       ".admin-topbar", ".admin-primary-nav", ".pages-workspace",
                       ".site-structure", ".registry-row", ".editor-metadata",
                       "@media(max-width:800px)", "@media(max-width:560px)"):
            self.assertIn(marker, css)
        self.assertIn(".registry-row{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:8px 0", css)
        self.assertIn(".registry-edit{flex:0 0 auto;min-height:34px;margin:0;padding:6px 12px}", css)
        self.assertRegex(css, r"\.pages-workspace\{[^}]*grid-template-columns:190px")
        self.assertIn("main nav:not(.admin-nav):not(.site-structure-nav)", css)
        self.assertRegex(css, r"@media\(max-width:800px\)\{[^}]*\.admin-topbar\{[^}]*flex-wrap:wrap")
        self.assertNotRegex(css, r"url\(['\"]?https?://")
        self.assertNotIn("javascript:", css.lower())
        editor_css = (APP_ROOT / "page_editor/assets/editor.css").read_text()
        for marker in (".es-toolbar", ".es-toolbar-primary", ".es-toolbar-secondary",
                       ".es-toolbar-more", ".es-toolbar-more-body", ".es-editor-surface",
                       ".es-page-actions", "[data-editor-action=check]",
                       "@media(max-width:600px)"):
            self.assertIn(marker, editor_css)
        self.assertNotRegex(editor_css, r"url\(['\"]?https?://")
        for relative in ("page_editor/assets/editor.mjs",
                         "page_editor/assets/editor.bundle.js"):
            editor_js = (APP_ROOT / relative).read_text(encoding="utf-8")
            for marker in ("es-toolbar-primary", "es-toolbar-secondary",
                           "es-toolbar-more", "Дополнительно"):
                self.assertIn(marker, editor_js, relative)
        info = LOGO.stat(follow_symlinks=False)
        self.assertEqual(info.st_nlink, 1)
        self.assertEqual(info.st_size, 30190)
