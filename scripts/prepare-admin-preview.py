"""Restore the accepted admin preview from its template and local source assets."""
import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1]
text = (root / 'docs/design/admin-workshop-template.html').read_text(encoding='utf-8')
for digest in (
    '455bce33abe531d1a9188e8df5e9c7ef610c0529b2bfc3b3b4484e91f7db58e8',
    'e813268acfacc547fc086e13dc9366e480b1fcdc0d85939575c64ea0f458642b',
    'c74acc09517dba9328e7188de6f0ecd0b0b10e5f73f89a73ced36c1c53c36a4e',
):
    image = root / 'media/source-site/assets' / (digest + '.jpg')
    text = text.replace('__LOCAL_PHOTO_' + digest + '__', 'data:image/jpeg;base64,' + base64.b64encode(image.read_bytes()).decode('ascii'))
output = root / 'docs/design/admin-workshop.html'
output.write_text(text, encoding='utf-8')
print(output)
