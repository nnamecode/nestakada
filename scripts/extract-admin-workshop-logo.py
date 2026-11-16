"""Extract the one approved workshop logo without image transformation."""
import base64
import hashlib
import os
import re
import stat
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/design/admin-workshop.html"
TARGET = ROOT / "app/accounts/assets/brand-logo.png"
EXPECTED_SHA = "39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5"
EXPECTED_SIZE = 30190
EXPECTED_DIMENSIONS = (212, 126)

text = SOURCE.read_text(encoding="utf-8")
matches = re.findall(r'var brandLogo="data:image/png;base64,([A-Za-z0-9+/=]+)";', text)
if len(matches) != 1:
    raise SystemExit("ADMIN_LOGO_AUTHORITY_MISMATCH")
try:
    payload = base64.b64decode(matches[0], validate=True)
except ValueError as error:
    raise SystemExit("ADMIN_LOGO_BASE64_REJECTED") from error
if payload[:8] != b"\x89PNG\r\n\x1a\n" or len(payload) < 24:
    raise SystemExit("ADMIN_LOGO_PNG_REJECTED")
dimensions = struct.unpack(">II", payload[16:24])
if (len(payload) != EXPECTED_SIZE or dimensions != EXPECTED_DIMENSIONS
        or hashlib.sha256(payload).hexdigest() != EXPECTED_SHA):
    raise SystemExit("ADMIN_LOGO_IDENTITY_MISMATCH")
TARGET.parent.mkdir(parents=True, exist_ok=True)
temporary = TARGET.with_suffix(".png.tmp")
if temporary.exists() or temporary.is_symlink():
    raise SystemExit("ADMIN_LOGO_TEMP_REJECTED")
with temporary.open("xb") as output:
    output.write(payload)
os.replace(temporary, TARGET)
info = TARGET.stat(follow_symlinks=False)
if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
        or info.st_size != EXPECTED_SIZE):
    raise SystemExit("ADMIN_LOGO_TARGET_REJECTED")
print(f"ADMIN_WORKSHOP_LOGO_PASS bytes={EXPECTED_SIZE} sha256={EXPECTED_SHA}")
