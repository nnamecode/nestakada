"""N2 fixed, run-owned, read-only account and receipt witness."""
import json
import os
import re
import sys
from uuid import UUID


class Boundary(ValueError):
    pass


def uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise Boundary()
    return value


def actor_id(value):
    if (type(value) is not str or re.fullmatch('[1-9][0-9]{0,18}', value) is None
            or int(value) > 9223372036854775807):
        raise Boundary()
    return value


def number(value, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= 2**53 - 1:
        raise Boundary()
    return value


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise Boundary()
        value[key] = item
    return value


def forbidden_constant(value):
    raise Boundary()


def execute(request):
    keys = {'operation', 'run', 'fixtureRun', 'ownerId', 'employeeId', 'pageId', 'operationIds'}
    if (type(request) is not dict or set(request) != keys or request['operation'] != 'network_late_read'
            or type(request['run']) is not str or re.fullmatch('[0-9a-f]{32}', request['run']) is None
            or request['run'] != os.environ.get('ESTAKADA_NETWORK_PROBE_RUN')
            or os.geteuid() != 10001 or os.environ.get('ESTAKADA_LOCAL_ENV') != 'test'
            or os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http'):
        raise Boundary()
    run, owner_id, employee_id, page_id = uuid(request['fixtureRun']), actor_id(request['ownerId']), actor_id(request['employeeId']), uuid(request['pageId'])
    if owner_id == employee_id or type(request['operationIds']) is not list or len(request['operationIds']) != 3:
        raise Boundary()
    operations = [uuid(value) for value in request['operationIds']]
    if len(set(operations)) != 3:
        raise Boundary()
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import connection, transaction
    from accounts.models import AuthSession, UserProfile, PageGrant
    from content.models import Page, Route
    from page_versions.models import OperationReceipt, PageRevision
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise Boundary()
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            users = {}
            for identifier, username, role in ((owner_id, 'nesadmin', 'owner'), (employee_id, 'editor-assigned', 'employee')):
                user = get_user_model().objects.filter(pk=identifier, first_name=run, username=username).values('id', 'is_active').first()
                profile = UserProfile.objects.filter(user_id=identifier, role=role).values('generation').first()
                if user is None or profile is None:
                    raise Boundary()
                sessions = AuthSession.objects.filter(user_id=identifier)
                users[role] = {'id': identifier, 'generation': number(profile['generation'], True),
                    'active': user['is_active'], 'authSessionCount': number(sessions.count()),
                    'linkedNativeSessionCount': number(Session.objects.filter(session_key__in=sessions.values('session_key')).count())}
            if not Page.objects.filter(pk=page_id, kind='article', name='EDITOR TEST ' + run + ' A').exists():
                raise Boundary()
            routes = list(Route.objects.filter(page_id=page_id, kind='primary').values_list('target', flat=True))
            if routes != ['/editor-fixture/' + run + '/a/']:
                raise Boundary()
            grant = PageGrant.objects.filter(user_id=employee_id, page_id=page_id).values('intro_text', 'main_text', 'price').first()
            users['employee'].update({'hasGrant': grant is not None,
                'allowedFields': sorted(key for key in ('intro_text', 'main_text', 'price') if grant is not None and grant[key] and users['employee']['active']),
                'currentGenerationSessionCount': number(AuthSession.objects.filter(user_id=employee_id, generation=users['employee']['generation']).count())})
            receipts = []
            for operation in operations:
                row = OperationReceipt.objects.filter(pk=operation).values('action', 'actor_id', 'page_id', 'actor_generation',
                    'editor_request_fingerprint', 'result_code', 'result_id').first()
                metadata = None
                if row is not None:
                    if (str(row['page_id']) != page_id or str(row['actor_id']) not in (owner_id, employee_id)
                            or row['action'] not in ('commit_owner', 'commit_employee') or row['result_code'] != 'applied'
                            or type(row['editor_request_fingerprint']) is not str
                            or re.fullmatch('[a-f0-9]{64}', row['editor_request_fingerprint']) is None):
                        raise Boundary()
                    result_id = str(row['result_id']) if row['result_id'] is not None else None
                    revision = PageRevision.objects.filter(pk=result_id).values('page_id').first() if result_id else None
                    if revision is not None and str(revision['page_id']) != page_id:
                        raise Boundary()
                    metadata = {'action': row['action'], 'actorId': str(row['actor_id']), 'pageId': page_id,
                        'actorGeneration': number(row['actor_generation'], True),
                        'editorFingerprint': row['editor_request_fingerprint'], 'resultCode': row['result_code'],
                        'resultId': result_id, 'resultExists': revision is not None}
                receipts.append({'operationId': operation, 'status': 'present' if metadata else 'absent', 'metadata': metadata})
            return {'version': 1, 'run': request['run'], 'fixtureRun': run, 'pageId': page_id,
                    'owner': users['owner'], 'employee': users['employee'], 'receipts': receipts}
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise Boundary()
        result = execute(json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=forbidden_constant))
        encoded = json.dumps(result, separators=(',', ':'), allow_nan=False)
        if len(encoded.encode()) > 8192:
            raise Boundary()
        print(encoded)
    except (Boundary, ValueError, TypeError, KeyError, UnicodeError):
        print(json.dumps({'code': 'NETWORK_LATE_BOUNDARY'}), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'code': 'NETWORK_LATE_UNAVAILABLE'}), file=sys.stderr)
        raise SystemExit(1)
