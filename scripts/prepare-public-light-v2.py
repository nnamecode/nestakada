"""Prepare the light design preview using project-local generated assets."""
import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1]
text = (root / "docs/design/public-light-v2-template.html").read_text(encoding="utf-8")
assets = {
    "__LOGO_DATA__": ("image/png", root / "media/source-site/assets/1c7de03c1bd80ebbde8258aca12b3d4ac68bf699085fd8a7923c4b880f41af8a.png"),
    "__HERO_DATA__": ("image/jpeg", root / "media/design-concepts/public-light-hero-v2-web.jpg"),
}
for token, (mime, path) in assets.items():
    text = text.replace(token, "data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode("ascii"))
destination = root / "work/public-light-v2.html"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(text, encoding="utf-8")
print(destination)
