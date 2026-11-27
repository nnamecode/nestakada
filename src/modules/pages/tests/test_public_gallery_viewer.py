from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "static" / "pages" / "public_gallery.js"
TEMPLATE = ROOT / "templates" / "pages" / "public_gallery.html"


class PublicGalleryViewerStaticTests(SimpleTestCase):
    def test_viewer_is_local_dom_only_and_keeps_direct_album_fallback(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")
        template = TEMPLATE.read_text(encoding="utf-8")

        self.assertLessEqual(len(script.encode("utf-8")), 16 * 1024)
        for forbidden in (
            "fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
            "localStorage", "sessionStorage", "eval(", "import(",
            "innerHTML", "insertAdjacentHTML", "data-gallery-url",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, script)
        for required in (
            "data-gallery-open", "data-gallery-dialog", "data-gallery-photo",
            "data-gallery-thumb", "data-gallery-prev", "data-gallery-next",
            "data-gallery-close", "ArrowLeft", "ArrowRight", "cancel",
            "showModal", "trigger.focus()", "PUBLIC_GALLERY_STATE_INVALID",
        ):
            with self.subTest(required=required):
                self.assertIn(required, script + template)
        self.assertIn("{% for photo in document.photos %}", template)
        self.assertIn("pages/public_gallery.js", template)
        self.assertNotIn("<script>", template)
