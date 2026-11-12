import json
import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from urllib import parse, request

from django.conf import settings
from django.core.mail import get_connection

from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from .models import RequestSettings


logger = logging.getLogger(__name__)
_CHAT = re.compile(r'^-?[1-9][0-9]{0,19}$')
_HOST = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$')
_TELEGRAM_TOKEN = re.compile(r'^[1-9][0-9]{5,19}:[A-Za-z0-9_-]{20,200}$')


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    success: bool


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _synthetic_email(payload):
    return None


def _synthetic_telegram(payload):
    return None


def _payload(row):
    return {
        'marker': 'synthetic-service-request-v1',
        'name': row.name,
        'phone': row.phone,
        'car': row.car,
        'comment': row.comment,
        'source': row.source,
    }


def _credential(variable, purpose, default):
    from estakada.settings.base import credential
    return credential(variable, purpose, default)


def _telegram_token():
    token = _credential(
        'ESTAKADA_TELEGRAM_TOKEN_FILE', 'telegram-token',
        '/run/secrets/telegram-token')
    if _TELEGRAM_TOKEN.fullmatch(token) is None:
        raise ValueError('REQUEST_TELEGRAM_TOKEN_INVALID')
    return token


def _live_configuration():
    recipient = RequestSettings.objects.filter(pk=1).values_list(
        'recipient_email', flat=True).first()
    host = settings.SERVICE_REQUEST_SMTP_HOST
    port = settings.SERVICE_REQUEST_SMTP_PORT
    user = settings.SERVICE_REQUEST_SMTP_USER
    security = settings.SERVICE_REQUEST_SMTP_SECURITY
    chat_id = settings.SERVICE_REQUEST_TELEGRAM_CHAT_ID
    if (settings.SERVICE_REQUEST_LEGAL_PROFILE != 'approved-v1'
            or not recipient or type(host) is not str
            or _HOST.fullmatch(host) is None or type(port) is not str
            or not port.isdigit() or not 1 <= int(port) <= 65535
            or type(user) is not str or not user or len(user) > 254
            or security not in ('tls', 'ssl') or type(chat_id) is not str
            or _CHAT.fullmatch(chat_id) is None):
        raise ValueError('REQUEST_NOTIFICATION_CONFIGURATION_INVALID')
    return {
        'recipient': recipient, 'host': host, 'port': int(port),
        'user': user, 'security': security, 'chat_id': chat_id,
    }


def live_ready():
    try:
        _live_configuration()
        _credential('ESTAKADA_SMTP_PASSWORD_FILE', 'smtp-password',
                    '/run/secrets/smtp-password')
        _telegram_token()
        return True
    except Exception:
        return False


def _text(payload):
    return ('Новая заявка\n'
            f"Имя: {payload['name']}\n"
            f"Телефон: {payload['phone']}\n"
            f"Автомобиль: {payload['car'] or 'не указан'}\n"
            f"Комментарий: {payload['comment'] or 'не указан'}\n"
            f"Источник: {payload['source']}")


def _live_email(payload):
    config = _live_configuration()
    password = _credential(
        'ESTAKADA_SMTP_PASSWORD_FILE', 'smtp-password',
        '/run/secrets/smtp-password')
    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=config['host'], port=config['port'], username=config['user'],
        password=password, use_tls=config['security'] == 'tls',
        use_ssl=config['security'] == 'ssl', timeout=5, fail_silently=False)
    from django.core.mail import EmailMessage
    message = EmailMessage(
        subject='Новая заявка с сайта', body=_text(payload),
        from_email=config['user'], to=[config['recipient']],
        connection=connection)
    if message.send(fail_silently=False) != 1:
        raise smtplib.SMTPException('REQUEST_EMAIL_NOT_SENT')


def _live_telegram(payload):
    config = _live_configuration()
    token = _telegram_token()
    url = 'https://api.telegram.org/bot' + token + '/sendMessage'
    body = parse.urlencode({
        'chat_id': config['chat_id'], 'text': _text(payload),
    }).encode('utf-8')
    opener = request.build_opener(
        request.ProxyHandler({}), _NoRedirect(),
        request.HTTPSHandler(context=ssl.create_default_context()))
    response = opener.open(request.Request(
        url, data=body, method='POST', headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }), timeout=5)
    try:
        if response.status != 200:
            raise OSError('REQUEST_TELEGRAM_STATUS')
        raw = response.read(4097)
        if len(raw) > 4096:
            raise OSError('REQUEST_TELEGRAM_RESPONSE_LIMIT')
        value = json.loads(raw.decode('utf-8'))
        if type(value) is not dict or value.get('ok') is not True:
            raise OSError('REQUEST_TELEGRAM_RESPONSE_INVALID')
    finally:
        response.close()


def _adapter(channel):
    profile = settings.SERVICE_REQUEST_TRANSPORT_PROFILE
    if profile == 'synthetic':
        return _synthetic_email if channel == 'email' else _synthetic_telegram
    if profile == 'live' and live_ready():
        return _live_email if channel == 'email' else _live_telegram
    raise ValueError('REQUEST_NOTIFICATION_PROFILE_DISABLED')


def _audit(result):
    record_event(
        category=Category.PERFORMANCE_INTEGRATIONS,
        event_code=('REQUEST_' + result.channel.upper()
                    + ('_SENT' if result.success else '_FAILED')),
        level=Level.INFO if result.success else Level.ERROR,
        source=Source.NOTIFICATION,
        result=Result.SUCCESS if result.success else Result.FAILURE)


def deliver(row):
    payload = _payload(row)
    results = []
    for channel in ('email', 'telegram'):
        try:
            _adapter(channel)(payload)
            outcome = DeliveryResult(channel, True)
        except Exception:
            outcome = DeliveryResult(channel, False)
        results.append(outcome)
    for outcome in results:
        try:
            _audit(outcome)
        except Exception:
            logger.error(
                '', extra={
                    'event_code': 'REQUEST_NOTIFICATION_AUDIT_FAILED',
                    'category': Category.SITE_ERRORS,
                    'source': Source.NOTIFICATION,
                    'result': Result.FAILURE,
                })
    return tuple(results)
