"""Build a local design preview without adding original gallery photos to Git."""
import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "docs/design/public-concepts-template.html").read_text(encoding="utf-8")
assets = {
    "__LOGO_DATA__": ("image/png", "1c7de03c1bd80ebbde8258aca12b3d4ac68bf699085fd8a7923c4b880f41af8a.png"),
    "__PHOTO_DATA__": ("image/jpeg", "b6ba835146d5c1bf991f54a2cc5210699dd974da60b347815aeca99d663d63d2.jpg"),
}
for token, (mime, filename) in assets.items():
    data = (root / "media/source-site/assets" / filename).read_bytes()
    source = source.replace(token, f"data:{mime};base64," + base64.b64encode(data).decode("ascii"))
destination = root / "work/public-concepts.html"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8")
print(destination)
