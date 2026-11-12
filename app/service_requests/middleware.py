from django.http import HttpResponse


SUBMIT_PATH = '/request/submit/'
BODY_LIMIT = 8192


def _closed(status):
    response = HttpResponse(
        'Запрос не принят.', status=status,
        content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


class RequestBodyLimitMiddleware:
    """Exact public-form cap before CsrfViewMiddleware parses request.POST."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == SUBMIT_PATH and request.method == 'POST':
            raw_length = request.META.get('CONTENT_LENGTH')
            if (type(raw_length) is not str or not raw_length.isascii()
                    or not raw_length.isdigit() or raw_length.startswith('0')
                    or len(raw_length) > 4
                    or request.content_type != 'application/x-www-form-urlencoded'):
                return _closed(400)
            try:
                length = int(raw_length)
            except ValueError:
                return _closed(400)
            if not 1 <= length <= BODY_LIMIT:
                return _closed(400)
            try:
                body = request.body
            except Exception:
                return _closed(400)
            if len(body) != length:
                return _closed(400)
        return self.get_response(request)
