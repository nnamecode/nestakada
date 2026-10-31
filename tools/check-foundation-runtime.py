"""Run by stdin in the isolated app container; no persistent probe endpoint."""
import json
import os
from uuid import uuid4

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estakada.settings.local_http')
import django
django.setup()
from django.db import connection, transaction, ProgrammingError
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event

try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_user')
        runtime = cursor.fetchone()[0] == 'app_runtime'
        cursor.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
        tls = cursor.fetchone()[0]
    ddl_state = None
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('CREATE TABLE app.foundation_forbidden_probe(id integer)')
            transaction.set_rollback(True)
    except ProgrammingError as exc:
        ddl_state = getattr(exc.__cause__, 'sqlstate', None)
    event_id = uuid4()
    with transaction.atomic():
        record_event(category=Category.ENVIRONMENT, event_code='RUNTIME_AUDIT_PROBE',
                     level=Level.INFO, source=Source.APPLICATION, result=Result.SUCCESS,
                     event_id=event_id)
        inserted = AuditEvent.objects.filter(event_id=event_id).count() == 1
        transaction.set_rollback(True)
    rolled_back = not AuditEvent.objects.filter(event_id=event_id).exists()
    result = dict(runtimeIdentity=runtime, tls=tls, ddlDenied=ddl_state == '42501',
                  auditInsertRead=inserted, enclosingRollback=rolled_back)
    if not all(value is True for value in result.values()):
        raise RuntimeError('capability-check')
    print(json.dumps(result))
except Exception as exc:
    raise SystemExit('Foundation runtime check failed: ' + type(exc).__name__) from None
