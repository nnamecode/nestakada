"""Independent byte/geometry/protocol oracles. Run in the reviewed Pillow image only."""
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import socket
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
import zlib
from PIL import Image, ImageDraw, PngImagePlugin, UnidentifiedImageError
import worker


def encoded(size=(100,50),mode='RGB',format='PNG',**options):
    image=Image.new(mode,size,(50,100,150,128) if mode=='RGBA' else (50,100,150))
    try:
        output=io.BytesIO();image.save(output,format=format,**options);return output.getvalue()
    finally:image.close()


def png_chunk(tag,data):
    return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)


def riff_chunk(tag,data):
    return tag+struct.pack('<I',len(data))+data+(b'\0' if len(data)&1 else b'')


def single_frame_apng():
    base=encoded(size=(30,20))
    control=struct.pack('>IIIIIHHBB',0,30,20,0,0,1,10,0,0)
    return base[:33]+png_chunk(b'acTL',struct.pack('>II',1,0))+png_chunk(b'fcTL',control)+base[33:]


def single_frame_animated_webp():
    base=encoded(size=(30,20),format='WEBP')
    # A valid ANMF payload contains the original static encoded frame chunk(s).
    frame_chunks=b'';position=12
    while position<len(base):
        length=int.from_bytes(base[position+4:position+8],'little');end=position+8+length+(length&1)
        if base[position:position+4] in (b'ALPH',b'VP8 ',b'VP8L'):frame_chunks+=base[position:end]
        position=end
    u24=lambda value:value.to_bytes(3,'little')
    canvas=b'\x02\0\0\0'+u24(29)+u24(19)
    frame=u24(0)+u24(0)+u24(29)+u24(19)+u24(100)+b'\0'+frame_chunks
    body=b'WEBP'+riff_chunk(b'VP8X',canvas)+riff_chunk(b'ANIM',b'\0'*6)+riff_chunk(b'ANMF',frame)
    return b'RIFF'+struct.pack('<I',len(body))+body


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def job(self,data,extension='.png',mime='image/png'):
        job_id=str(uuid4());directory=self.root/job_id;directory.mkdir(mode=0o770)
        (directory/'input.bin').write_bytes(data)
        return {'version':1,'job_id':job_id,'extension':extension,'mime':mime,'input_sha256':hashlib.sha256(data).hexdigest(),'input_bytes':len(data)},directory

    def decode(self,data,extension='.png',mime='image/png'):
        request,directory=self.job(data,extension,mime)
        receipt=worker.process_job(worker.request_from(json.dumps(request).encode()),self.root)
        self.assertEqual((directory/'input.bin').read_bytes(),data)
        for name in ['main','preview']:
            content=(directory/(name+'.webp')).read_bytes()
            self.assertEqual(receipt['outputs'][name]['sha256'],hashlib.sha256(content).hexdigest())
            self.assertEqual(receipt['outputs'][name]['bytes'],len(content))
            with Image.open(io.BytesIO(content)) as image:
                self.assertEqual(image.format,'WEBP');image.load()
                self.assertEqual(image.size,(receipt['outputs'][name]['width'],receipt['outputs'][name]['height']))
        return receipt,directory

    def assert_rejected(self,data,extension='.png',mime='image/png'):
        request,directory=self.job(data,extension,mime)
        with self.assertRaises((worker.Rejected,OSError,SyntaxError,UnidentifiedImageError,Image.DecompressionBombWarning,Image.DecompressionBombError)):
            worker.process_job(worker.request_from(json.dumps(request).encode()),self.root)
        self.assertFalse((directory/'receipt.json').exists())
        self.assertFalse((directory/'main.webp').exists())

    def test_mw01_real_jpeg_png_webp(self):
        for format,extension,mime in [('JPEG','.jpeg','image/jpeg'),('PNG','.png','image/png'),('WEBP','.webp','image/webp')]:
            with self.subTest(format=format):
                receipt,_=self.decode(encoded(format=format),extension,mime)
                for output in receipt['outputs'].values():self.assertEqual((output['width'],output['height']),(100,50))

    def test_mw02_exact_decimal_one_megabyte_is_valid_png_not_trailing_padding(self):
        small=encoded();target=1_000_000
        text=b'Comment\0'+b'A'*(target-len(small)-12-len(b'Comment\0'))
        chunk=struct.pack('>I',len(text))+b'tEXt'+text+struct.pack('>I',zlib.crc32(b'tEXt'+text)&0xffffffff)
        data=small[:-12]+chunk+small[-12:]
        self.assertEqual(len(data),target)
        receipt,directory=self.decode(data)
        self.assertEqual(receipt['input']['bytes'],1_000_000)
        self.assertNotIn(b'Comment', (directory/'main.webp').read_bytes())
        too_large=data[:-12]+b'X'+data[-12:]
        request,_=self.job(too_large)
        with self.assertRaises(worker.Rejected):worker.request_from(json.dumps(request).encode())

    def test_mw02_pixel_and_side_rejection_before_load(self):
        self.assert_rejected(encoded(size=(8001,5000)))
        self.assert_rejected(encoded(size=(10001,1)))

    def test_mw02_positive_side_ten_thousand(self):
        receipt,_=self.decode(encoded(size=(10000,2500)))
        self.assertEqual((receipt['outputs']['main']['width'],receipt['outputs']['main']['height']),(1920,480))
        self.assertEqual((receipt['outputs']['preview']['width'],receipt['outputs']['preview']['height']),(480,120))

    def test_mw02_positive_forty_megapixel_rgba_exif_rotation_budget(self):
        exif=Image.Exif();exif[274]=6
        data=encoded(size=(8000,5000),mode='RGBA',exif=exif)
        self.assertLessEqual(len(data),1_000_000)
        started=time.monotonic();receipt,directory=self.decode(data)
        self.assertLess(time.monotonic()-started,15)
        self.assertEqual((receipt['outputs']['main']['width'],receipt['outputs']['main']['height']),(1200,1920))
        self.assertEqual((receipt['outputs']['preview']['width'],receipt['outputs']['preview']['height']),(300,480))
        with Image.open(directory/'main.webp') as image:self.assertEqual(image.getpixel((100,100))[3],128)

    def test_mw03_known_exif_orientation_and_corner_colors(self):
        image=Image.new('RGB',(400,300));draw=ImageDraw.Draw(image)
        for box,color in [((0,0,199,149),'red'),((200,0,399,149),'green'),((0,150,199,299),'blue'),((200,150,399,299),'yellow')]:draw.rectangle(box,fill=color)
        exif=Image.Exif();exif[274]=6;exif[315]='PRIVATE-EXIF-ARTIST'
        output=io.BytesIO();image.save(output,'JPEG',quality=95,exif=exif,icc_profile=b'PRIVATE-ICC');image.close()
        receipt,directory=self.decode(output.getvalue(),'.jpg','image/jpeg')
        self.assertEqual((receipt['outputs']['main']['width'],receipt['outputs']['main']['height']),(300,400))
        with Image.open(directory/'main.webp') as result:
            self.assertEqual(dict(result.getexif()),{})
            self.assertNotIn('exif',result.info);self.assertNotIn('icc_profile',result.info);self.assertNotIn('xmp',result.info)
            red=result.getpixel((270,30));blue=result.getpixel((30,30));yellow=result.getpixel((30,370))
            self.assertGreater(red[0],180);self.assertLess(red[2],80)
            self.assertGreater(blue[2],180);self.assertLess(blue[0],80)
            self.assertGreater(yellow[0],180);self.assertGreater(yellow[1],180);self.assertLess(yellow[2],80)

    def test_mw04_alpha_and_metadata_without_upscale(self):
        image=Image.new('RGBA',(100,50),(100,150,200,0));image.putpixel((30,20),(20,40,60,128));image.putpixel((70,30),(70,80,90,255))
        metadata=PngImagePlugin.PngInfo();metadata.add_text('Comment','PRIVATE-TEXT');metadata.add_itxt('XML:com.adobe.xmp','PRIVATE-XMP')
        output=io.BytesIO();image.save(output,'PNG',pnginfo=metadata);image.close()
        _,directory=self.decode(output.getvalue())
        for name in ['main','preview']:
            with Image.open(directory/(name+'.webp')) as result:
                self.assertEqual(result.size,(100,50));self.assertEqual(result.getpixel((0,0))[3],0)
                self.assertEqual(result.getpixel((30,20))[3],128);self.assertEqual(result.getpixel((70,30))[3],255)
                self.assertFalse({'exif','icc_profile','xmp','Comment'}&set(result.info))

    def test_mw04_geometry_without_distortion(self):
        receipt,_=self.decode(encoded(size=(4000,2000)))
        self.assertEqual((receipt['outputs']['main']['width'],receipt['outputs']['main']['height']),(1920,960))
        self.assertEqual((receipt['outputs']['preview']['width'],receipt['outputs']['preview']['height']),(480,240))

    def test_mw05_mismatch_truncation_and_animation(self):
        self.assert_rejected(encoded(),'.jpg','image/jpeg')
        self.assert_rejected(encoded()[:40])
        self.assert_rejected(encoded(format='JPEG')[:-40],'.jpg','image/jpeg')
        for format,extension,mime in [('PNG','.png','image/png'),('WEBP','.webp','image/webp')]:
            first=Image.new('RGB',(30,20),'red');second=Image.new('RGB',(30,20),'blue');output=io.BytesIO()
            first.save(output,format,save_all=True,append_images=[second],duration=100,loop=0);first.close();second.close()
            self.assert_rejected(output.getvalue(),extension,mime)
        for data in [b'<svg xmlns="http://www.w3.org/2000/svg"/>',b'<html>active</html>',b'%PDF-1.7',b'%!PS',b'GIF89a',b'II*\x00']:
            self.assert_rejected(data)

    def test_mw05_valid_single_frame_animation_containers_are_rejected(self):
        for data,extension,mime in [(single_frame_apng(),'.png','image/png'),(single_frame_animated_webp(),'.webp','image/webp')]:
            with self.subTest(extension=extension):
                # Positive validity control: the actual codec can fully decode this one-frame fixture.
                with Image.open(io.BytesIO(data)) as image:
                    image.load();self.assertEqual(image.size,(30,20));self.assertEqual(image.n_frames,1)
                request,directory=self.job(data,extension,mime)
                with self.assertRaises(worker.Rejected) as caught:worker.process_job(request,self.root)
                self.assertEqual(caught.exception.code,'ANIMATION_REJECTED')
                self.assertFalse((directory/'receipt.json').exists())

    def test_mw05_static_metadata_animation_tag_text_is_not_a_false_positive(self):
        metadata=PngImagePlugin.PngInfo();metadata.add_text('Comment','ANIM acTL is ordinary text')
        png=encoded(pnginfo=metadata)
        webp=encoded(format='WEBP',xmp=b'<xmp>ANIM acTL is ordinary metadata</xmp>')
        for data,extension,mime in [(png,'.png','image/png'),(webp,'.webp','image/webp')]:
            self.assertIn(b'ANIM',data);self.assertIn(b'acTL',data)
            _,directory=self.decode(data,extension,mime)
            for name in ['main','preview']:
                with Image.open(directory/(name+'.webp')) as image:self.assertFalse({'xmp','Comment','exif','icc_profile'}&set(image.info))

    def test_mw05_structural_chunk_length_overflow_is_rejected(self):
        png=encoded();png=png[:8]+b'\xff\xff\xff\xff'+png[12:]
        webp=encoded(format='WEBP');webp=webp[:16]+b'\xff\xff\xff\xff'+webp[20:]
        self.assert_rejected(png);self.assert_rejected(webp,'.webp','image/webp')

    def test_mw06_protocol_closed_and_duplicate_keys_denied(self):
        request,_=self.job(encoded())
        variants=[{**request,'command':'sleep'},{**request,'path':'/etc/passwd'},{**request,'job_id':'../escape'},
            {**request,'job_id':request['job_id'].upper()},{**request,'version':True},{**request,'input_bytes':True},
            {**request,'extension':'.gif','mime':'image/gif'},{**request,'mime':'text/html'},{**request,'input_sha256':'x'*64}]
        for value in variants:
            with self.subTest(value=value),self.assertRaises(worker.Rejected):worker.request_from(json.dumps(value).encode())
        duplicate=json.dumps(request)[:-1]+',"version":1}'
        with self.assertRaises(worker.Rejected):worker.request_from(duplicate.encode())
        with self.assertRaises(worker.Rejected):worker.request_from(b' '*4097)

    def test_mw06_symlink_hardlink_and_repeat_are_not_overwritten(self):
        request,directory=self.job(encoded());original=(directory/'input.bin').read_bytes()
        (directory/'input.bin').unlink();outside=self.root/'outside';outside.write_bytes(original)
        (directory/'input.bin').symlink_to(outside)
        with self.assertRaises(OSError):worker.process_job(request,self.root)
        (directory/'input.bin').unlink();os.link(outside,directory/'input.bin')
        with self.assertRaises(worker.Rejected):worker.process_job(request,self.root)
        (directory/'input.bin').unlink();(directory/'input.bin').write_bytes(original)
        parent=worker.job_directory(self.root,request['job_id'])
        try:
            worker.write_exclusive(parent,'job.lock',b'first')
            with self.assertRaises(FileExistsError):worker.write_exclusive(parent,'job.lock',b'second')
        finally:os.close(parent)
        self.assertEqual((directory/'job.lock').read_bytes(),b'first')

    def test_mw07_real_subprocess_deadline_kills_and_reaps(self):
        request,_=self.job(encoded());pidfile=self.root/'child.pid'
        code=f'import os,time;open({str(pidfile)!r},"w").write(str(os.getpid()));time.sleep(60)'
        start=time.monotonic()
        with self.assertRaises(worker.Rejected) as caught:
            worker.run_child(request,time.monotonic()+0.5,self.root,command=[sys.executable,'-c',code])
        self.assertEqual(caught.exception.code,'JOB_TIMEOUT');self.assertLess(time.monotonic()-start,3)
        pid=int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):os.kill(pid,0)

    def test_mw07_slow_drip_uses_absolute_deadline_not_per_recv_progress(self):
        class SlowSocket:
            now=0.0
            timeout=None
            timeouts=[]
            def settimeout(self,value):self.timeout=value;self.timeouts.append(value)
            def recv(self,size):
                if self.timeout<0.9:
                    self.now+=self.timeout;raise socket.timeout()
                self.now+=0.9;return b' '
        connection=SlowSocket()
        with self.assertRaises(worker.Rejected) as caught:worker.receive(connection,15.0,clock=lambda:connection.now)
        self.assertEqual(caught.exception.code,'JOB_TIMEOUT')
        self.assertAlmostEqual(connection.now,15.0)
        self.assertTrue(all(value<=2 for value in connection.timeouts));self.assertLess(connection.timeouts[-1],0.9)

    def test_mw07_send_uses_remaining_deadline_or_sends_nothing(self):
        class Sender:
            timeout=None
            sends=[]
            def settimeout(self,value):self.timeout=value
            def sendall(self,data):self.sends.append(data)
        connection=Sender()
        self.assertTrue(worker.send_response(connection,{'status':'rejected'},15,clock=lambda:14.75))
        self.assertEqual(connection.timeout,0.25);self.assertEqual(len(connection.sends),1)
        self.assertFalse(worker.send_response(connection,{'status':'ok'},15,clock=lambda:15))
        self.assertEqual(len(connection.sends),1)

    def test_mw07_real_file_budget_failure_never_writes_success_receipt(self):
        request,directory=self.job(encoded());script=Path(worker.__file__).absolute()
        # OS file-size refusal in a separate real process; actual tmpfs ENOSPC is an integration probe below.
        code=f'import sys,json,resource;sys.path.insert(0,{str(script.parent)!r});import worker;resource.setrlimit(resource.RLIMIT_FSIZE,(1,1));worker.process_job(json.loads({json.dumps(request)!r}),{str(self.root)!r})'
        process=subprocess.run([sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
        self.assertNotEqual(process.returncode,0);self.assertFalse((directory/'receipt.json').exists())

    def test_mw08_source_hash_mismatch_rejected(self):
        request,directory=self.job(encoded());request['input_sha256']='0'*64
        with self.assertRaises(worker.Rejected):worker.process_job(request,self.root)
        self.assertFalse((directory/'main.webp').exists())

    def test_mw08_parent_rejects_corrupted_output_after_child_success(self):
        request,directory=self.job(encoded());worker.process_job(request,self.root)
        (directory/'main.webp').write_bytes(b'RIFFxxxxWEBPcorrupted')
        with self.assertRaises(worker.Rejected) as caught:
            worker.run_child(request,time.monotonic()+5,self.root,command=[sys.executable,'-c','pass'])
        self.assertEqual(caught.exception.code,'BAD_RECEIPT')

    def test_mw08_parent_cannot_return_ok_after_receipt_verification_deadline(self):
        request,_=self.job(encoded());worker.process_job(request,self.root)
        with patch('worker.time.monotonic',side_effect=[100.0,100.0,116.0]):
            with self.assertRaises(worker.Rejected) as caught:
                worker.run_child(request,115.0,self.root,command=[sys.executable,'-c','pass'])
        self.assertEqual(caught.exception.code,'JOB_TIMEOUT')


if __name__=='__main__':unittest.main()
