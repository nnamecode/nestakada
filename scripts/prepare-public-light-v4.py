"""Prepare the local v4 review mockup; source photographs remain unchanged."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
text = (root / "docs/design/public-light-v4-template.html").read_text(encoding="utf-8")
# The source template opens directly from docs/design; the generated preview lives in work.
text = text.replace('src="../../media/', 'src="../media/')

destination = root / "work/public-light-v4.html"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(text, encoding="utf-8")
assert destination.stat().st_size < 250_000
print(destination)
