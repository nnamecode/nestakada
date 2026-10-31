"""Bound complete multipart body before CSRF/multipart parsing of this one route."""
import re
from django.http import HttpResponse

UPLOAD_ROUTE=re.compile(r'\A/manage/media/pages/[0-9a-f-]{36}/upload/\Z')


class MediaBodyLimitMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        if request.method=='POST' and UPLOAD_ROUTE.fullmatch(request.path):
            try:length=int(request.META.get('CONTENT_LENGTH') or 0)
            except (ValueError,TypeError):length=-1
            if length<0 or length>11*1024*1024:
                response=HttpResponse('Файл не принят: размер запроса превышает допустимый.',status=413,content_type='text/plain; charset=utf-8')
                response['Cache-Control']='private, no-store';response['Vary']='Cookie'
                return response
        return self.get_response(request)
