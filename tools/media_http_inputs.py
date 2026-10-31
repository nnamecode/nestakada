"""Synthetic fixtures only, generated in the approved isolated Pillow image."""
import hashlib
import io
import json
from pathlib import Path
import struct
import zlib
from PIL import Image

root=Path('/out')
manifest={}


def save(name,data,mime):
    path=root/name
    with path.open('xb') as stream:
        stream.write(data)
    manifest[name]={'name':name,'mime':mime,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def image_bytes(format,mode='RGB',size=(100,50)):
    image=Image.new(mode,size,(50,100,150,128) if mode=='RGBA' else (50,100,150))
    try:
        output=io.BytesIO();image.save(output,format);return output.getvalue()
    finally:image.close()


png=image_bytes('PNG','RGBA')
save('valid.png',png,'image/png')
save('valid.jpg',image_bytes('JPEG'),'image/jpeg')
save('valid.webp',image_bytes('WEBP'),'image/webp')
for limit,name in [(1_000_000,'boundary.png'),(1_000_001,'over.png')]:
    # A correctly framed/CRC'd ancillary chunk before IEND, not invalid trailing padding.
    data=b'Padding\0'+b'x'*(limit-len(png)-12-8)
    chunk=struct.pack('>I',len(data))+b'tEXt'+data+struct.pack('>I',zlib.crc32(b'tEXt'+data)&0xffffffff)
    result=png[:-12]+chunk+png[-12:]
    assert len(result)==limit
    with Image.open(io.BytesIO(result)) as control:control.verify()
    save(name,result,'image/png')
save('truncated.png',png[:40],'image/png')
save('active.svg',b'<svg xmlns="http://www.w3.org/2000/svg"><script>throw 1</script></svg>','image/svg+xml')
save('active.html',b'<!doctype html><script>throw 1</script>','text/html')
save('pixel-over.png',image_bytes('PNG',size=(8001,5000)),'image/png')
(root/'inputs.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'generated':len(manifest),'contains_real_photos':False}))
