"""Offline Unix-socket image job; no Django, database, HTTP or arbitrary path input."""
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import socket
import stat
import subprocess
import sys
import time
from uuid import UUID

ROOT = Path('/exchange/jobs')
SOCKET = Path('/exchange/media-worker.sock')
MAX_INPUT = 1_000_000
MAX_PIXELS = 40_000_000
MAX_SIDE = 10_000
BUDGET = 15.0
MAX_JSON = 4096
FORMATS = {'.jpg':('JPEG','image/jpeg'),'.jpeg':('JPEG','image/jpeg'),'.png':('PNG','image/png'),'.webp':('WEBP','image/webp')}


class Rejected(Exception):
    def __init__(self, code='IMAGE_REJECTED'):
        self.code = code


def unique_pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise Rejected('BAD_PROTOCOL')
        result[key] = value
    return result


def request_from(raw):
    if len(raw)>MAX_JSON:
        raise Rejected('BAD_PROTOCOL')
    try:
        request = json.loads(raw,object_pairs_hook=unique_pairs)
        if not isinstance(request,dict) or set(request)!={'version','job_id','extension','mime','input_sha256','input_bytes'}:
            raise Rejected('BAD_PROTOCOL')
        if type(request['version']) is not int or request['version']!=1 or type(request['input_bytes']) is not int or not 0<request['input_bytes']<=MAX_INPUT:
            raise Rejected('BAD_PROTOCOL')
        job_id=request['job_id']
        if not isinstance(job_id,str) or str(UUID(job_id))!=job_id:
            raise Rejected('BAD_PROTOCOL')
        if not isinstance(request['extension'],str) or request['extension'] not in FORMATS or request['mime']!=FORMATS[request['extension']][1]:
            raise Rejected('BAD_PROTOCOL')
        digest=request['input_sha256']
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise Rejected('BAD_PROTOCOL')
        return request
    except (ValueError,TypeError,KeyError,UnicodeError):
        raise Rejected('BAD_PROTOCOL') from None


def directory(path):
    """All absolute ancestors are opened no-follow, not resolved through symlinks."""
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise Rejected('UNSAFE_STORAGE')
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
    fd=os.open('/',flags)
    try:
        for part in path.parts[1:]:
            nxt=os.open(part,flags,dir_fd=fd);os.close(fd);fd=nxt
        return fd
    except BaseException:
        os.close(fd);raise


def job_directory(root, job_id):
    parent=directory(root)
    try:return os.open(job_id,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
    finally:os.close(parent)


def read_regular(parent,name,limit):
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=parent)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>limit:
            raise Rejected('UNSAFE_STORAGE')
        data=stream.read(limit+1)
        after=os.fstat(stream.fileno())
        if len(data)>limit or (info.st_ino,info.st_size,info.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise Rejected('SOURCE_CHANGED')
        return data


def write_exclusive(parent,name,data):
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o640,dir_fd=parent)
    with os.fdopen(fd,'wb') as output:
        output.write(data);output.flush();os.fsync(output.fileno())
    os.fsync(parent)


def verified_input(parent,request):
    data=read_regular(parent,'input.bin',MAX_INPUT)
    if len(data)!=request['input_bytes'] or hashlib.sha256(data).hexdigest()!=request['input_sha256']:
        raise Rejected('SOURCE_CHANGED')
    expected=FORMATS[request['extension']][0]
    signature = ('PNG' if data.startswith(b'\x89PNG\r\n\x1a\n') else
                 'JPEG' if data.startswith(b'\xff\xd8\xff') else
                 'WEBP' if len(data)>=12 and data[:4]==b'RIFF' and data[8:12]==b'WEBP' else None)
    if signature!=expected:
        raise Rejected('FORMAT_MISMATCH')
    reject_animation_container(data,expected)
    return data,expected


def reject_animation_container(data,format):
    """Inspect bounded structural tags, never arbitrary metadata substrings."""
    if format=='PNG':
        position=8
        while position<len(data):
            if len(data)-position<12:raise Rejected('INVALID_CONTAINER')
            length=int.from_bytes(data[position:position+4],'big')
            if length>len(data)-position-12:raise Rejected('INVALID_CONTAINER')
            tag=data[position+4:position+8]
            if tag==b'acTL':raise Rejected('ANIMATION_REJECTED')
            position+=12+length
            if tag==b'IEND':
                if length or position!=len(data):raise Rejected('INVALID_CONTAINER')
                return
        raise Rejected('INVALID_CONTAINER')
    if format=='WEBP':
        if int.from_bytes(data[4:8],'little')!=len(data)-8:raise Rejected('INVALID_CONTAINER')
        position=12
        while position<len(data):
            if len(data)-position<8:raise Rejected('INVALID_CONTAINER')
            tag=data[position:position+4];length=int.from_bytes(data[position+4:position+8],'little')
            end=position+8+length+(length&1)
            if end>len(data):raise Rejected('INVALID_CONTAINER')
            if tag in (b'ANIM',b'ANMF'):raise Rejected('ANIMATION_REJECTED')
            if tag==b'VP8X':
                if length!=10:raise Rejected('INVALID_CONTAINER')
                if data[position+8]&0x02:raise Rejected('ANIMATION_REJECTED')
            position=end


def dimensions(image):
    width,height=image.size
    if width<1 or height<1 or width>MAX_SIDE or height>MAX_SIDE or width*height>MAX_PIXELS:
        raise Rejected('DIMENSIONS_REJECTED')
    if getattr(image,'is_animated',False) or getattr(image,'n_frames',1)!=1:
        raise Rejected('ANIMATION_REJECTED')


def process_job(request,root=ROOT):
    """Trusted internal entry; root is a test injection, never a protocol field."""
    from PIL import Image, ImageFile, ImageOps
    import warnings
    ImageFile.LOAD_TRUNCATED_IMAGES=False
    Image.MAX_IMAGE_PIXELS=MAX_PIXELS
    warnings.simplefilter('error',Image.DecompressionBombWarning)
    start=time.monotonic();parent=job_directory(root,request['job_id'])
    try:
        data,expected=verified_input(parent,request)
        with Image.open(io.BytesIO(data),formats=['JPEG','PNG','WEBP']) as verification:
            if verification.format!=expected:raise Rejected('FORMAT_MISMATCH')
            dimensions(verification);verification.verify()
        outputs={}
        with Image.open(io.BytesIO(data),formats=['JPEG','PNG','WEBP']) as image:
            dimensions(image);image.load()
            ImageOps.exif_transpose(image,in_place=True)
            alpha='A' in image.getbands() or 'transparency' in image.info
            # P/LA/etc must be converted before high-quality resampling; RGBA avoids a full-size copy.
            if image.mode not in ('RGB','RGBA'):
                converted=image.convert('RGBA' if alpha else 'RGB');image.close();image=converted
            image.thumbnail((1920,1920),Image.Resampling.LANCZOS,reducing_gap=2.0)
            clean=Image.new('RGBA' if alpha else 'RGB',image.size)
            clean.paste(image);image.close()
            try:
                for name,bound in [('main',1920),('preview',480)]:
                    if name=='preview':clean.thumbnail((bound,bound),Image.Resampling.LANCZOS,reducing_gap=2.0)
                    output=io.BytesIO();clean.save(output,format='WEBP',quality=82,method=4,lossless=False)
                    encoded=output.getvalue();write_exclusive(parent,name+'.webp',encoded)
                    outputs[name]={'sha256':hashlib.sha256(encoded).hexdigest(),'bytes':len(encoded),
                                   'width':clean.width,'height':clean.height,'mime':'image/webp'}
            finally:clean.close()
        verified_input(parent,request)
        receipt={'version':1,'job_id':request['job_id'],'status':'ok','input':{'sha256':request['input_sha256'],'bytes':len(data)},
                 'outputs':outputs,'elapsed_ms':round((time.monotonic()-start)*1000),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        encoded=json.dumps(receipt,separators=(',',':')).encode()
        if len(encoded)>MAX_JSON:raise Rejected('BAD_RECEIPT')
        write_exclusive(parent,'receipt.json',encoded)
        return receipt
    finally:os.close(parent)


def child():
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024*1024,128*1024*1024))
    try:
        request=request_from(sys.stdin.buffer.read(MAX_JSON+1))
        process_job(request)
        return 0
    except BaseException:
        # No raw decoder exception, user metadata, path or image bytes in logs/protocol.
        return 2


def run_child(request,deadline,root=ROOT,command=None):
    """command injection is test-only Python API; the wire protocol has no such field."""
    command=command or [sys.executable,'-I',str(Path(__file__).absolute()),'--child']
    if time.monotonic()>=deadline:raise Rejected('JOB_TIMEOUT')
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        start_new_session=True,env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
    try:
        process.communicate(json.dumps(request).encode(),timeout=max(0.001,deadline-time.monotonic()))
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=2)
        raise Rejected('JOB_TIMEOUT') from None
    if process.returncode!=0:raise Rejected('IMAGE_REJECTED')
    parent=job_directory(root,request['job_id'])
    try:
        receipt=json.loads(read_regular(parent,'receipt.json',MAX_JSON),object_pairs_hook=unique_pairs)
        if not isinstance(receipt,dict) or set(receipt)!={'version','job_id','status','input','outputs','elapsed_ms','peak_rss_kib'} or receipt['version']!=1 or receipt['job_id']!=request['job_id'] or receipt['status']!='ok':raise Rejected('BAD_RECEIPT')
        if receipt['input']!={'sha256':request['input_sha256'],'bytes':request['input_bytes']} or set(receipt['outputs'])!={'main','preview'}:raise Rejected('BAD_RECEIPT')
        verified_input(parent,request)
        for name,bound in [('main',1920),('preview',480)]:
            row=receipt['outputs'][name]
            if set(row)!={'sha256','bytes','width','height','mime'} or row['mime']!='image/webp' or any(type(row[key]) is not int or not 0<row[key]<=bound for key in ['width','height']):raise Rejected('BAD_RECEIPT')
            actual=read_regular(parent,name+'.webp',128*1024*1024)
            if row['bytes']!=len(actual) or row['sha256']!=hashlib.sha256(actual).hexdigest() or actual[:4]!=b'RIFF' or actual[8:12]!=b'WEBP':raise Rejected('BAD_RECEIPT')
        if time.monotonic()>=deadline:raise Rejected('JOB_TIMEOUT')
        return receipt
    finally:os.close(parent)


def receive(connection,deadline,clock=time.monotonic):
    raw=b''
    while b'\n' not in raw:
        remaining=deadline-clock()
        if remaining<=0:raise Rejected('JOB_TIMEOUT')
        connection.settimeout(min(2,remaining))
        try:chunk=connection.recv(min(1024,MAX_JSON+1-len(raw)))
        except socket.timeout:
            raise Rejected('JOB_TIMEOUT' if clock()>=deadline else 'BAD_PROTOCOL') from None
        if not chunk:raise Rejected('BAD_PROTOCOL')
        raw+=chunk
        if len(raw)>MAX_JSON:raise Rejected('BAD_PROTOCOL')
    if raw.count(b'\n')!=1 or not raw.endswith(b'\n'):raise Rejected('BAD_PROTOCOL')
    return request_from(raw[:-1])


def send_response(connection,response,deadline,clock=time.monotonic):
    remaining=deadline-clock()
    if remaining<=0:return False
    connection.settimeout(remaining)
    connection.sendall(json.dumps(response,separators=(',',':')).encode()+b'\n')
    return True


def serve():
    os.umask(0o007)
    # Socket path is never unlinked automatically: stale/live instances require explicit operator inspection.
    exchange=directory('/exchange')
    try:
        try:
            os.mkdir('jobs',0o770,dir_fd=exchange);os.fsync(exchange)
        except FileExistsError:pass
    finally:os.close(exchange)
    root=directory(ROOT);os.close(root)
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    server.bind(str(SOCKET));os.chmod(SOCKET,0o660);server.listen(1)
    while True:
        connection,_=server.accept();deadline=time.monotonic()+BUDGET
        with connection:
            try:
                request=receive(connection,deadline);parent=job_directory(ROOT,request['job_id'])
                try:write_exclusive(parent,'job.lock',b'one-shot\n')
                finally:os.close(parent)
                receipt=run_child(request,deadline)
                response={'version':1,'job_id':request['job_id'],'status':'ok','receipt':receipt}
            except Rejected as exc:response={'version':1,'status':'rejected','code':exc.code}
            except FileExistsError:response={'version':1,'status':'rejected','code':'JOB_ALREADY_USED'}
            except BaseException:response={'version':1,'status':'rejected','code':'WORKER_FAILURE'}
            try:send_response(connection,response,deadline)
            except OSError:pass


if __name__=='__main__':
    if sys.argv[1:]==['--child']:sys.exit(child())
    if sys.argv[1:]:sys.exit(2)
    serve()
