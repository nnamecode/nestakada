"""Exclusive test DB seed/read helper; never implements login/logout or throttle decisions."""
import json
import os
import secrets
import sys
import uuid
from datetime import timedelta


def execute(request):
    if os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.auth_isolated':
        raise ValueError('Auth fixture requires explicit isolated settings')
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import transaction
    from accounts.clock import now
    from accounts.models import AuthSession, LoginThrottle, UserProfile, PageGrant
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise ValueError('Wrong fixture database')
    User = get_user_model()
    def clear_owned():
        previous = request.get('previousIds')
        if not isinstance(previous, list) or any(not isinstance(value, str) for value in previous):
            raise ValueError('Explicit fixture ownership required')
        current = list(User.objects.select_for_update().order_by('pk'))
        if sorted(str(user.pk) for user in current) != sorted(previous):
            raise ValueError('Current users differ from controller-owned fixture IDs; no reset performed')
        if any(user.username not in ['nesadmin','auth-employee'] or user.first_name not in
               ['AUTH-OWNER-PRIVATE-CANARY','AUTH-EMPLOYEE-PRIVATE-CANARY'] for user in current):
            raise ValueError('Registered fixture user identity changed')
        keys = list(AuthSession.objects.filter(user_id__in=previous).values_list('session_key', flat=True))
        AuthSession.objects.filter(user_id__in=previous).delete()
        Session.objects.filter(session_key__in=keys).delete()
        PageGrant.objects.filter(user_id__in=previous).delete()
        UserProfile.objects.filter(user_id__in=previous).delete()
        User.objects.filter(pk__in=previous).delete()
        LoginThrottle.objects.filter(ip_address__in=[request['sourceAIp'],request['sourceBIp']]).delete()
    if request['kind'] == 'close':
        with transaction.atomic():
            clear_owned()
        return {'closed': True}
    if request['kind'] == 'reset':
        from accounts.services import bootstrap_owner, create_employee
        options = request.get('options', {})
        allowed = [('five-failures-blocked',899),('five-failures-blocked',901),('four-failures-aged',599),('four-failures-aged',601)]
        if options and (set(options) != {'seed','ageSeconds'} or (options['seed'],options['ageSeconds']) not in allowed):
            raise ValueError('Unknown fixed seed')
        owner_password, employee_password = secrets.token_hex(48), secrets.token_hex(48)
        with transaction.atomic():
            clear_owned()
            owner = bootstrap_owner(owner_password)
            employee = create_employee(actor=owner,username='auth-employee',password=employee_password)
            owner.first_name='AUTH-OWNER-PRIVATE-CANARY';owner.save(update_fields=['first_name'])
            employee.first_name='AUTH-EMPLOYEE-PRIVATE-CANARY';employee.save(update_fields=['first_name'])
            if options:
                started=now()-timedelta(seconds=options['ageSeconds'])
                blocked=options['seed']=='five-failures-blocked'
                LoginThrottle.objects.create(ip_address=request['sourceAIp'],failure_times=[started.isoformat()]*(5 if blocked else 4),
                    failure_count_total=5 if blocked else 4,failure_count_lower_bound=False,
                    blocked_until=started+timedelta(minutes=15) if blocked else None,last_request_id=uuid.uuid4(),last_seen=now(),
                    expires_at=started+timedelta(seconds=900 if blocked else 600))
        actors={name:{'storageState':{'cookies':[],'origins':[]},'sourceOrigin':f'http://host.docker.internal:{8769 if name=="LOGIN-B" else 8768}'} for name in ['LOGIN-A','LOGIN-A2','LOGIN-B']}
        return {'ownedUserIds':[str(owner.pk),str(employee.pk)],'actors':actors,'secretRefs':{'OWNER-CURRENT-SECRET':owner_password,'EMPLOYEE-CURRENT-SECRET':employee_password,'WRONG-SYNTHETIC-SECRET':secrets.token_hex(48)},
                'accounts':{'OWNER':{'username':owner.username},'S-EDIT':{'username':employee.username}}}
    if request['view']=='auth-fixture-identifiers':
        return {'ownerUserId':str(User.objects.get(username='nesadmin').pk),'employeeUserId':str(User.objects.get(username='auth-employee').pk),
                'sourceAIp':request['sourceAIp'],'sourceBIp':request['sourceBIp']}
    if request['view']=='auth-source-state':
        actor=request.get('args',{}).get('actor')
        if actor not in ['LOGIN-A','LOGIN-A2','LOGIN-B']:
            raise ValueError('Unknown fixture actor')
        ip=request['sourceBIp'] if actor=='LOGIN-B' else request['sourceAIp']
        row=LoginThrottle.objects.get(ip_address=ip)
        expected=request.get('args',{}).get('expectedRequestId')
        if not expected or str(row.last_request_id).replace('-','')!=expected.replace('-',''):
            raise ValueError('Limiter state does not match the real HTTP response request ID')
        return {'sourceIp':str(row.ip_address),'observedFrom':'actual-ingress-and-limiter','lastRequestId':str(row.last_request_id),
                'failedCount':len(row.failure_times),'nowUtc':now().isoformat(),'blockedUntilUtc':row.blocked_until.isoformat() if row.blocked_until else None}
    raise ValueError('Unknown fixed observation')


if __name__=='__main__':
    try:
        result=execute(json.load(sys.stdin))
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({'errorClass':type(exc).__name__}),file=sys.stderr)
        sys.exit(1)
