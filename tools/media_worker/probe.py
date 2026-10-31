"""Fixed integration probes against the real daemon; never a product uploader."""
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import time
from uuid import uuid4
from PIL import Image

ROOT=Path('/exchange/jobs')
SOCKET='/exchange/media-worker.sock'


def exchange(request):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(20);connection.connect(SOCKET)
        connection.sendall(json.dumps(request,separators=(',',':')).encode()+b'\n')
        data=b''
        while not data.endswith(b'\n'):
            chunk=connection.recv(4097-len(data))
            if not chunk:raise RuntimeError('Daemon closed without reply')
            data+=chunk
            if len(data)>4096:raise RuntimeError('Oversized daemon reply')
        return json.loads(data)


def input_bytes(mode='RGBA',format='PNG',size=(8000,5000)):
    image=Image.new(mode,size,(100,150,200,128) if mode=='RGBA' else (100,150,200))
    try:
        output=io.BytesIO();exif=Image.Exif();exif[274]=6
        image.save(output,format=format,exif=exif,**({'quality':75} if format=='JPEG' else {}))
        return output.getvalue()
    finally:image.close()


def prepare(data,extension,mime):
    job_id=str(uuid4());directory=ROOT/job_id;directory.mkdir(mode=0o770)
    fd=os.open(directory/'input.bin',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o640)
    with os.fdopen(fd,'wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
    return directory,{'version':1,'job_id':job_id,'extension':extension,'mime':mime,'input_bytes':len(data),'input_sha256':hashlib.sha256(data).hexdigest()}


def cleanup(directory):
    for name in ['input.bin','job.lock','main.webp','preview.webp','receipt.json','space-probe.bin']:
        (directory/name).unlink(missing_ok=True)
    directory.rmdir()


def positive():
    rows=[]
    for mode,format,extension,mime in [('RGBA','PNG','.png','image/png'),('RGB','JPEG','.jpg','image/jpeg')]:
        data=input_bytes(mode,format)
        if len(data)>1_000_000:raise RuntimeError('Positive fixture exceeded the independent 1MB limit')
        directory,request=prepare(data,extension,mime)
        try:
            start=time.monotonic();reply=exchange(request);elapsed=round((time.monotonic()-start)*1000)
            if reply.get('status')!='ok' or reply.get('job_id')!=request['job_id']:raise RuntimeError('Real positive decode rejected')
            receipt=reply['receipt']
            for name,expected in [('main',(1200,1920)),('preview',(300,480))]:
                encoded=(directory/(name+'.webp')).read_bytes()
                if hashlib.sha256(encoded).hexdigest()!=receipt['outputs'][name]['sha256']:raise RuntimeError('Actual output hash mismatch')
                with Image.open(io.BytesIO(encoded)) as result:
                    result.load()
                    if result.format!='WEBP' or result.size!=expected or result.getexif() or {'exif','icc_profile','xmp'}&set(result.info):raise RuntimeError('Independent positive image oracle mismatch')
                    if mode=='RGBA' and result.getpixel((100,100))[3]!=128:raise RuntimeError('Actual alpha changed')
            if (directory/'input.bin').read_bytes()!=data:raise RuntimeError('Private input changed')
            replay=exchange(request)
            if replay.get('status')!='rejected' or replay.get('code')!='JOB_ALREADY_USED':raise RuntimeError('Repeated command was not rejected')
            rows.append({'case':mode+'-40MP-EXIF6','elapsed_wall_ms':elapsed,'receipt':receipt,'replay_rejected':True})
        finally:cleanup(directory)
    print(json.dumps({'positive':rows}))


def full_exchange():
    directory,request=prepare(input_bytes(size=(20,10)),'.png','image/png')
    filled=0;saw_enospc=False
    try:
        with (directory/'space-probe.bin').open('xb',buffering=0) as output:
            try:
                for _ in range(129):
                    filled+=output.write(b'Z'*(1024*1024));output.flush()
                os.fsync(output.fileno())
            except OSError as exc:
                if exc.errno!=errno.ENOSPC:raise
                saw_enospc=True
        if not saw_enospc:raise RuntimeError('128MiB exchange did not physically report ENOSPC within bounded 129MiB probe')
        reply=exchange(request)
        if reply.get('status')!='rejected' or (directory/'receipt.json').exists():raise RuntimeError('Full exchange falsely reported successful decode')
        print(json.dumps({'actual_enospc':True,'written_before_error':filled,'controlled_reply':reply,'success_receipt_exists':False}))
    finally:cleanup(directory)


if __name__=='__main__':
    os.umask(0o007)
    if sys.argv[1:]==['--positive']:positive()
    elif sys.argv[1:]==['--full']:full_exchange()
    else:sys.exit(2)
