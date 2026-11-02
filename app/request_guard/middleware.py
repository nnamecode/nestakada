"""First middleware: scanner refusals cannot touch session/auth/SQL/body."""
from django.http import HttpResponse

from .counters import COUNTERS
from .paths import classify_path


class ScannerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        signature = classify_path(request.path_info)
        if signature is None:
            return self.get_response(request)
        request._scanner_signature = signature
        try:
            COUNTERS.note(signature)
        except Exception:
            # Only optional noise accounting is best-effort. Never skip refusal.
            try:
                COUNTERS.mark_incomplete()
            except Exception:
                pass
        status = 414 if signature == 'oversize' else 400 if signature == 'malformed' else 404
        data = b'Not found.\n' if status == 404 else b'Request rejected.\n'
        response = HttpResponse(b'' if request.method == 'HEAD' else data,
                                status=status, content_type='text/plain; charset=utf-8')
        response['Content-Length'] = str(len(data))
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'same-origin'
        response['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return response
