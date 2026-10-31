"""Fixed local decoder transport. No Pillow, arbitrary paths, URLs or commands."""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time
from uuid import UUID, uuid4
from django.conf import settings

MAX_INPUT = 1_000_000
MAX_EXCHANGE = 128*1024*1024
MAX_REPLY = 4096
FORMATS = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}
JOB_FILES = ('input.bin','job.lock','main.webp','preview.webp','receipt.json','pending.json')


class UploadRejected(Exception):
    """Known rejection; no usable Asset was registered."""


class UploadPending(Exception):
    """A writer/commit cannot be assumed complete. Do not discard its job."""


class WorkerUnavailable(Exception):
    """No request reached the worker; safe to discard our unsent input."""


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('MEDIA_DUPLICATE_JSON_KEY')
        result[key]=value
    return result


def _directory(path):
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts:raise ValueError('MEDIA_UNSAFE_EXCHANGE')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=nxt
        return fd
    except BaseException:
        os.close(fd);raise


def _regular(parent,name,limit):
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=parent)
    with os.fdopen(fd,'rb') as source:
        before=os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:raise ValueError('MEDIA_UNSAFE_EXCHANGE_FILE')
        data=source.read(limit+1);after=os.fstat(source.fileno())
        if len(data)>limit or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('MEDIA_EXCHANGE_CHANGED')
        return data


def _write(parent,name,data,mode=0o640):
    fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,mode,dir_fd=parent)
    with os.fdopen(fd,'wb') as target:
        target.write(data);target.flush();os.fsync(target.fileno())
    os.fsync(parent)


def webp_dimensions(data):
    """Bounded structural check; the isolated worker performs actual decoding."""
    if len(data)<20 or data[:4]!=b'RIFF' or data[8:12]!=b'WEBP' or int.from_bytes(data[4:8],'little')!=len(data)-8:
        raise ValueError('MEDIA_BAD_WEBP_CONTAINER')
    position=12;canvas=None;frame=None;payloads=0
    while position<len(data):
        if len(data)-position<8:raise ValueError('MEDIA_BAD_WEBP_CHUNK')
        tag=data[position:position+4];length=int.from_bytes(data[position+4:position+8],'little')
        end=position+8+length+(length&1)
        if end>len(data):raise ValueError('MEDIA_BAD_WEBP_CHUNK')
        chunk=data[position+8:position+8+length]
        if tag in (b'ANIM',b'ANMF',b'EXIF',b'XMP ',b'ICCP'):raise ValueError('MEDIA_UNEXPECTED_WEBP_METADATA')
        if tag==b'VP8X':
            if canvas is not None or length!=10 or chunk[0]&~0x10 or chunk[1:4]!=b'\0\0\0':raise ValueError('MEDIA_BAD_WEBP_CANVAS')
            canvas=(int.from_bytes(chunk[4:7],'little')+1,int.from_bytes(chunk[7:10],'little')+1)
        elif tag==b'VP8 ':
            if length<10 or chunk[3:6]!=b'\x9d\x01\x2a':raise ValueError('MEDIA_BAD_WEBP_FRAME')
            payloads+=1;frame=(int.from_bytes(chunk[6:8],'little')&0x3fff,int.from_bytes(chunk[8:10],'little')&0x3fff)
        elif tag==b'VP8L':
            if length<5 or chunk[0]!=0x2f:raise ValueError('MEDIA_BAD_WEBP_FRAME')
            bits=int.from_bytes(chunk[1:5],'little')
            if bits>>29:raise ValueError('MEDIA_BAD_WEBP_VERSION')
            payloads+=1;frame=((bits&0x3fff)+1,((bits>>14)&0x3fff)+1)
        elif tag!=b'ALPH':raise ValueError('MEDIA_UNEXPECTED_WEBP_CHUNK')
        position=end
    if payloads!=1 or frame is None or min(frame)<1 or (canvas is not None and canvas!=frame):raise ValueError('MEDIA_BAD_WEBP_DIMENSIONS')
    return frame


class WorkerResult:
    def __init__(self,client,job_id,outputs,receipt):
        self.client,self.job_id,self.outputs,self.receipt=client,job_id,outputs,receipt
    def cleanup(self):
        self.client.cleanup(self.job_id)
    def quarantine(self,code,asset_id=None):
        self.client.quarantine(self.job_id,code,asset_id)


class WorkerClient:
    def __init__(self):
        self.root=Path(getattr(settings,'MEDIA_EXCHANGE_ROOT','/exchange'))
        self.socket=self.root/'media-worker.sock'

    def _job(self,job_id):
        if str(UUID(str(job_id)))!=str(job_id):raise ValueError('MEDIA_INVALID_JOB_ID')
        jobs=_directory(self.root/'jobs')
        try:return os.open(str(job_id),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=jobs)
        finally:os.close(jobs)

    def quarantine(self,job_id,code,asset_id=None):
        parent=self._job(job_id)
        try:
            marker={'version':1,'job_id':str(job_id),'state':'pending','code':code,'asset_id':str(asset_id) if asset_id else None}
            try:_write(parent,'pending.json',json.dumps(marker,separators=(',',':')).encode())
            except FileExistsError:pass
        finally:os.close(parent)

    def cleanup(self,job_id):
        """Caller must have a proven terminal reply/no writer, never a socket timeout."""
        parent=self._job(job_id)
        try:
            for name in JOB_FILES:
                try:os.unlink(name,dir_fd=parent)
                except FileNotFoundError:pass
            os.fsync(parent)
            inode=os.fstat(parent).st_ino
        finally:os.close(parent)
        jobs=_directory(self.root/'jobs')
        try:
            current=os.stat(str(job_id),dir_fd=jobs,follow_symlinks=False)
            if current.st_ino!=inode or not stat.S_ISDIR(current.st_mode):raise ValueError('MEDIA_JOB_DIRECTORY_CHANGED')
            os.rmdir(str(job_id),dir_fd=jobs);os.fsync(jobs)
        finally:os.close(jobs)

    def pending(self):
        """Only fixed UUID marker files, not a filesystem media search."""
        try:jobs=_directory(self.root/'jobs')
        except OSError:return []
        result=[]
        try:
            for name in os.listdir(jobs):
                try:
                    if str(UUID(name))!=name:continue
                    parent=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=jobs)
                    try:
                        # Even a full exchange that could not allocate a marker remains visible.
                        marker={}
                        try:marker=json.loads(_regular(parent,'pending.json',MAX_REPLY),object_pairs_hook=_pairs)
                        except (OSError,ValueError,TypeError,RecursionError):pass
                        asset_id=marker.get('asset_id') if isinstance(marker,dict) else None
                        try:asset_id=str(UUID(asset_id)) if asset_id else None
                        except (ValueError,TypeError):asset_id=None
                        result.append({'job_id':name,'asset_id':asset_id})
                    finally:os.close(parent)
                except (OSError,ValueError,TypeError,RecursionError):continue
            return result
        finally:os.close(jobs)

    def process(self,data,extension,mime):
        if not 0<len(data)<=MAX_INPUT or extension not in FORMATS or mime!=FORMATS[extension]:raise UploadRejected('MEDIA_INVALID_IMAGE_INPUT')
        job_id=str(uuid4());root=None;parent=None;sent=False;terminal=False
        request={'version':1,'job_id':job_id,'extension':extension,'mime':mime,'input_sha256':hashlib.sha256(data).hexdigest(),'input_bytes':len(data)}
        try:
            root=_directory(self.root)
            try:os.mkdir('jobs',0o770,dir_fd=root);os.fsync(root)
            except FileExistsError:pass
            jobs=_directory(self.root/'jobs')
            try:
                os.mkdir(job_id,0o770,dir_fd=jobs);os.chmod(job_id,0o770,dir_fd=jobs,follow_symlinks=False);os.fsync(jobs)
                parent=os.open(job_id,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=jobs)
            finally:os.close(jobs)
            _write(parent,'input.bin',data)
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
                deadline=time.monotonic()+20
                def budget():
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('MEDIA_WORKER_DEADLINE')
                    connection.settimeout(remaining)
                budget()
                connection.connect(str(self.socket))
                # After this boundary even a partial send may have admitted the request.
                sent=True;budget();connection.sendall(json.dumps(request,separators=(',',':')).encode()+b'\n')
                response=b''
                while not response.endswith(b'\n'):
                    budget()
                    chunk=connection.recv(MAX_REPLY+1-len(response))
                    if not chunk:raise ValueError('MEDIA_WORKER_REPLY_MISSING')
                    response+=chunk
                    if len(response)>MAX_REPLY:raise ValueError('MEDIA_WORKER_REPLY_TOO_LARGE')
            reply=json.loads(response,object_pairs_hook=_pairs)
            if isinstance(reply,dict) and set(reply)=={'version','status','code'} and type(reply['version']) is int and reply=={'version':1,'status':'rejected','code':'IMAGE_REJECTED'}:
                terminal=True;raise UploadRejected('MEDIA_IMAGE_REJECTED')
            if not isinstance(reply,dict) or set(reply)!={'version','job_id','status','receipt'} or type(reply['version']) is not int or reply['version']!=1 or reply['job_id']!=job_id or reply['status']!='ok':raise ValueError('MEDIA_BAD_WORKER_REPLY')
            receipt=reply['receipt']
            if not isinstance(receipt,dict) or set(receipt)!={'version','job_id','status','input','outputs','elapsed_ms','peak_rss_kib'} or type(receipt['version']) is not int or receipt['version']!=1 or receipt['job_id']!=job_id or receipt['status']!='ok':raise ValueError('MEDIA_BAD_WORKER_RECEIPT')
            if receipt['input']!={'sha256':request['input_sha256'],'bytes':len(data)} or set(receipt['outputs'])!={'main','preview'}:raise ValueError('MEDIA_BAD_WORKER_RECEIPT')
            if any(type(receipt[key]) is not int or receipt[key]<0 for key in ['elapsed_ms','peak_rss_kib']):raise ValueError('MEDIA_BAD_WORKER_MEASUREMENT')
            if _regular(parent,'input.bin',MAX_INPUT)!=data:raise ValueError('MEDIA_SOURCE_CHANGED')
            actual_receipt=json.loads(_regular(parent,'receipt.json',MAX_REPLY),object_pairs_hook=_pairs)
            if actual_receipt!=receipt:raise ValueError('MEDIA_RECEIPT_FILE_CHANGED')
            outputs={}
            for name,bound in [('main',1920),('preview',480)]:
                row=receipt['outputs'][name]
                if not isinstance(row,dict) or set(row)!={'sha256','bytes','width','height','mime'} or row['mime']!='image/webp' or any(type(row[key]) is not int or not 0<row[key]<=bound for key in ['width','height']) or type(row['bytes']) is not int:raise ValueError('MEDIA_BAD_WORKER_OUTPUT')
                output=_regular(parent,name+'.webp',MAX_EXCHANGE)
                if row['bytes']!=len(output) or row['sha256']!=hashlib.sha256(output).hexdigest() or webp_dimensions(output)!=(row['width'],row['height']):raise ValueError('MEDIA_BAD_WORKER_OUTPUT')
                outputs[name]=output
            terminal=True
            return WorkerResult(self,job_id,outputs,receipt)
        except UploadRejected:
            if terminal:
                try:self.cleanup(job_id)
                except (OSError,ValueError):
                    try:self.quarantine(job_id,'TEMP_CLEANUP_PENDING')
                    except (OSError,ValueError):pass
            raise
        except (OSError,ValueError,TypeError,KeyError,RecursionError) as exc:
            if sent:
                try:self.quarantine(job_id,'WORKER_RESULT_UNKNOWN')
                except (OSError,ValueError):pass
                raise UploadPending('MEDIA_UPLOAD_PENDING') from None
            if parent is not None:
                try:self.cleanup(job_id)
                except (OSError,ValueError):pass
            raise WorkerUnavailable('MEDIA_WORKER_UNAVAILABLE') from None
        finally:
            if parent is not None:os.close(parent)
            if root is not None:os.close(root)
