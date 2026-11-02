"""Suppress only the two proven Django expected-scanner-404 log shapes."""
import logging
import re

from django.http import HttpRequest

from .paths import MAX_PATH_CHARACTERS, SIGNATURES, classify_path

_METHOD = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


class ExpectedScanner404Filter(logging.Filter):
    def filter(self, record):
        data = vars(record)
        if type(data.get('status_code')) is not int or data['status_code'] != 404:
            return True
        if record.name == 'django.request':
            request = data.get('request')
            signature = vars(request).get('_scanner_signature') if isinstance(request, HttpRequest) else None
            return not (type(signature) is str and signature in SIGNATURES[:8])
        if record.name == 'django.server':
            args = data.get('args')
            if (type(data.get('msg')) is not str or data['msg'] != '"%s" %s %s' or type(args) is not tuple or len(args) != 3
                    or any(type(value) is not str for value in args)
                    or args[1] != '404' or not 1 <= len(args[2]) <= 20 or not args[2].isdecimal()):
                return True
            # The HTTP server already parsed this line. Inspect only bounded
            # method/path plus a fixed version suffix; never copy/scan the query.
            line = args[0]
            method_end = line.find(' ', 0, 65536)
            if method_end < 0 or _METHOD.fullmatch(line, 0, method_end) is None:
                return True
            if not (line.endswith(' HTTP/1.0') or line.endswith(' HTTP/1.1')):
                return True
            start, end = method_end + 1, len(line) - 9
            if end <= start or line[start] != '/':
                return True
            query = line.find('?', start, min(end, start + MAX_PATH_CHARACTERS + 1))
            path_end = query if query >= 0 else end
            if path_end - start > MAX_PATH_CHARACTERS:
                return True
            path = line[start:path_end]
            if ' ' in path:
                return True
            return classify_path(path) not in SIGNATURES[:8]
        return True
