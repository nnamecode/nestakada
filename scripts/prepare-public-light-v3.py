"""Prepare the review mockup; keep source photographs outside Git."""
import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1]
text = (root / "docs/design/public-light-v3-template.html").read_text(encoding="utf-8")
assets = {
    "__LOGO_DATA__": ("image/png", "media/source-site/assets/1c7de03c1bd80ebbde8258aca12b3d4ac68bf699085fd8a7923c4b880f41af8a.png"),
    "__HERO_DATA__": ("image/jpeg", "media/design-concepts/public-light-hero-v2-web.jpg"),
    "__PAINT_DATA__": ("image/jpeg", "media/source-site/assets/89581671eabdf5f6ca6ef2a8fa407cf21a6de383146f302d0a1d811a6ef98161.jpg"),
}
for token, (mime, name) in assets.items():
    text = text.replace(token, "data:" + mime + ";base64," + base64.b64encode((root / name).read_bytes()).decode("ascii"))
destination = root / "work/public-light-v3.html"
destination.write_text(text, encoding="utf-8")
assert destination.stat().st_size < 1_000_000
assert "__HERO_DATA__" not in text
print(destination)
