"""Authentication and trusted owner commands; no public self-reset or content writes."""
from datetime import timedelta
import ipaddress
import secrets
import socket
from uuid import UUID, uuid4
from django.conf import settings
from django.contrib.auth import get_user_model, login as django_login
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, connection
from django.db.models import Q, F
from django.utils.dateparse import parse_datetime
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from content.models import Page, lock_content
from . import clock
from .models import UserProfile, PageGrant, AuthSession, LoginThrottle, AuthResourceState

AUTH_LOCK = 7342810301
DUMMY_HASH = make_password(secrets.token_hex(32))
IDLE = timedelta(minutes=30)
ABSOLUTE = timedelta(hours=12)

class AuthUnavailable(Exception):
    pass

def lock_auth():
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [AUTH_LOCK])

def event(code, actor=None, target=None, source_ip=None, request_id=None, result=Result.SUCCESS, count=1, lower_bound=False):
    return record_event(category=Category.SECURITY if code.startswith('SEC_') else Category.ACCESS, event_code=code, level=Level.INFO,
                        source=Source.APPLICATION, result=result, actor_id=actor.pk if actor else None,
                        object_kind='user' if target else '', object_ref=target.pk if target else None,
                        ip_address=source_ip, ip_related=source_ip is not None, request_id=request_id, occurrence_count=count, count_is_lower_bound=lower_bound)

def password_value(value):
    # Transport/DoS bound, not an invented complexity/minimum-length policy.
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValidationError('AUTH_INVALID_PASSWORD_INPUT')
    return value

def source_ip(request):
    try:
        peer = str(ipaddress.ip_address(request.META.get('REMOTE_ADDR', '')))
        if '%' in peer:
            raise ValueError()
        trusted = set()
        host = getattr(settings, 'AUTH_TRUSTED_PROXY_HOST', None)
        if host:
            trusted = {str(ipaddress.ip_address(row[4][0])) for row in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
        if peer in trusted:
            raw = request.META.get('HTTP_X_REAL_IP', '')
            if '%' in raw:
                raise ValueError()
            return str(ipaddress.ip_address(raw))
        return peer
    except (ValueError, OSError):
        raise AuthUnavailable('AUTH_SOURCE_UNAVAILABLE') from None

def request_id(request):
    # The public header is not a capability. Always generate an application UUID.
    value = uuid4()
    request.auth_request_id = value
    return value

MAX_COUNT = 9_223_372_036_854_775_807

def flush_session_counts(state):
    for field in ('denied_owner_count','denied_page_count'):
        count=getattr(state,field)
        if count>1:
            event('SEC_PERMISSION_DENIED_AGGREGATE',actor=state.user,
                  result=Result.DENIED,count=count-1,lower_bound=state.denial_count_lower_bound)

def flush_throttle_counts(row):
    if row.failure_count_total>1:
        event('AUTH_LOGIN_FAILED_AGGREGATE',source_ip=row.ip_address,request_id=row.last_request_id,
              result=Result.DENIED,count=row.failure_count_total-1,lower_bound=row.failure_count_lower_bound)
    if row.blocked_repeats:
        event('AUTH_BLOCKED_AGGREGATE',source_ip=row.ip_address,request_id=row.last_request_id,
              result=Result.DENIED,count=row.blocked_repeats,lower_bound=row.repeat_count_lower_bound)

def capacity_state(kind, full):
    state,_=AuthResourceState.objects.get_or_create(kind=kind)
    if state.full != full:
        state.full=full;state.save(update_fields=['full'])
        event('AUTH_CAPACITY_REACHED' if full else 'AUTH_CAPACITY_RECOVERED',
              result=Result.FAILURE if full else Result.SUCCESS)

def cleanup(now):
    expired=AuthSession.objects.select_related('user').filter(
        Q(last_seen__lt=now-IDLE)|Q(issued_at__lt=now-ABSOLUTE)|
        Q(user__is_active=False)|~Q(generation=F('user__security_profile__generation')))
    keys=[]
    for state in expired:
        flush_session_counts(state)
        event('AUTH_SESSION_EXPIRED',actor=state.user)
        keys.append(state.pk)
    Session.objects.filter(session_key__in=keys).delete()
    AuthSession.objects.filter(session_key__in=keys).delete()
    Session.objects.filter(expire_date__lt=now).delete()
    for row in LoginThrottle.objects.filter(expires_at__lte=now):
        flush_throttle_counts(row)
        row.delete()
    capacity_state('throttle',LoginThrottle.objects.count()>=settings.AUTH_THROTTLE_CAP)
    capacity_state('sessions',AuthSession.objects.count()>=settings.AUTH_SESSION_CAP)

def _owner(actor, expected_generation=None):
    profile = UserProfile.objects.select_related('user').filter(user_id=actor.pk).first()
    if (profile is None or profile.role != 'owner' or profile.user.username != 'nesadmin'
            or not profile.user.is_active or (expected_generation is not None and profile.generation != expected_generation)):
        raise PermissionDenied('AUTH_OWNER_REQUIRED')
    return profile

def is_owner(user):
    return bool(user.is_authenticated and UserProfile.objects.filter(user_id=user.pk,
                role='owner', user__username='nesadmin', user__is_active=True).exists())

def bootstrap_owner(password):
    password_value(password)
    with transaction.atomic():
        lock_content('default'); lock_auth()
        User = get_user_model()
        if User.objects.filter(username='nesadmin').exists() or UserProfile.objects.filter(role='owner').exists():
            raise ValidationError('AUTH_OWNER_ALREADY_EXISTS')
        user = User(username='nesadmin', is_staff=False, is_superuser=False)
        user.set_password(password); user.full_clean(); user.save()
        UserProfile.objects.create(user=user, role='owner')
        event('AUTH_OWNER_CREATED', target=user)
        return user

def create_employee(*, actor, username, password, expected_generation=None):
    password_value(password)
    with transaction.atomic():
        lock_content('default'); lock_auth(); _owner(actor, expected_generation)
        User = get_user_model()
        if username == 'nesadmin':
            raise ValidationError('AUTH_RESERVED_USERNAME')
        user = User(username=username, is_staff=False, is_superuser=False)
        user.set_password(password); user.full_clean(); user.save()
        UserProfile.objects.create(user=user, role='employee')
        event('AUTH_EMPLOYEE_CREATED', actor=actor, target=user)
        return user

def reset_password(*, actor, employee, password, expected_generation=None):
    password_value(password)
    with transaction.atomic():
        lock_content('default'); lock_auth(); _owner(actor, expected_generation)
        target = UserProfile.objects.select_related('user').get(user_id=employee.pk)
        if target.role != 'employee':
            raise PermissionDenied('AUTH_EMPLOYEE_REQUIRED')
        target.user.set_password(password); target.user.save(update_fields=['password'])
        invalidate(target)
        event('AUTH_EMPLOYEE_PASSWORD_RESET', actor=actor, target=target.user)

def invalidate(profile):
    profile.generation += 1; profile.save(update_fields=['generation'])
    states=list(AuthSession.objects.select_related('user').filter(user_id=profile.user_id))
    for state in states:flush_session_counts(state)
    keys=[state.pk for state in states]
    Session.objects.filter(session_key__in=keys).delete()
    AuthSession.objects.filter(user_id=profile.user_id).delete()

def set_active(*, actor, employee, active, expected_generation=None):
    if type(active) is not bool:
        raise ValidationError('AUTH_INVALID_ACTIVE')
    with transaction.atomic():
        lock_content('default'); lock_auth(); _owner(actor, expected_generation)
        profile = UserProfile.objects.select_related('user').get(user_id=employee.pk)
        if profile.role != 'employee':
            raise PermissionDenied('AUTH_EMPLOYEE_REQUIRED')
        profile.user.is_active = active; profile.user.save(update_fields=['is_active'])
        invalidate(profile)
        event('AUTH_EMPLOYEE_ENABLED' if active else 'AUTH_EMPLOYEE_DISABLED', actor=actor, target=profile.user)

def set_grant(*, actor, employee, page, intro_text=False, main_text=False, price=False, revoke=False, expected_generation=None):
    if any(type(v) is not bool for v in [intro_text, main_text, price, revoke]):
        raise ValidationError('AUTH_INVALID_CAPABILITY')
    with transaction.atomic():
        lock_content('default'); lock_auth(); _owner(actor, expected_generation)
        if not UserProfile.objects.filter(user_id=employee.pk,role='employee').exists():
            raise PermissionDenied('AUTH_EMPLOYEE_REQUIRED')
        if revoke:
            PageGrant.objects.filter(user_id=employee.pk, page_id=page.pk).delete()
        else:
            grant, _ = PageGrant.objects.get_or_create(user_id=employee.pk,page_id=page.pk)
            grant.intro_text=intro_text;grant.main_text=main_text;grant.price=price;grant.save()
        event('AUTH_GRANT_REVOKED' if revoke else 'AUTH_GRANT_CHANGED', actor=actor, target=employee)

def allowed_fields(user, page):
    if is_owner(user):
        return ('intro_text','main_text','price')
    if not user.is_authenticated or not UserProfile.objects.filter(user_id=user.pk,user__is_active=True,role='employee').exists():
        raise PermissionDenied('AUTH_PAGE_DENIED')
    grant = PageGrant.objects.filter(user_id=user.pk,page_id=page.pk).first()
    if grant is None:
        raise PermissionDenied('AUTH_PAGE_DENIED')
    return tuple(field for field in ['intro_text','main_text','price'] if getattr(grant,field))

def _throttle(ip, now):
    row = LoginThrottle.objects.filter(pk=ip).first()
    if row is None:
        if LoginThrottle.objects.count() >= settings.AUTH_THROTTLE_CAP:
            return None
        row = LoginThrottle(ip_address=ip, expires_at=now+timedelta(seconds=600))
    return row

def _authenticate_request(request, username, password):
    ip = source_ip(request); rid = request_id(request)
    username = username if isinstance(username,str) and len(username) <= 150 else ''
    supplied = password if isinstance(password,str) and 0 < len(password) <= 4096 else ''
    user = get_user_model().objects.filter(username=username).first()
    profile = UserProfile.objects.filter(user=user).first() if user else None
    valid_identity = bool(user and profile and user.is_active and
                          (profile.role == 'employee' or (profile.role == 'owner' and user.username == 'nesadmin')))
    hashed = user.password if valid_identity and user.has_usable_password() else DUMMY_HASH
    matched = check_password(supplied, hashed)
    with transaction.atomic():
        lock_auth()
        now=clock.now()
        cleanup(now)
        row = _throttle(ip, now)
        if row is None:
            capacity_state('throttle',True)
            return False
        row.last_request_id=rid;row.last_seen=now
        if row.blocked_until and row.blocked_until > now:
            if row.blocked_repeats>=MAX_COUNT:row.repeat_count_lower_bound=True
            else:row.blocked_repeats+=1
            row.save();return False
        times=[]
        for raw in row.failure_times:
            stamp=parse_datetime(raw)
            if stamp is None or stamp.tzinfo is None:
                raise AuthUnavailable('AUTH_THROTTLE_INVALID')
            # A wall-clock rollback must not erase already confirmed failures.
            if now-stamp < timedelta(seconds=600):times.append(stamp)
        # Recheck identity and hash after serialized password/disable changes.
        current = UserProfile.objects.select_related('user').filter(user_id=user.pk).first() if user else None
        accepted = bool(matched and valid_identity and current and current.user.is_active and
                        current.generation==profile.generation and current.user.password==user.password)
        if not accepted:
            if not row.failure_count_total:event('AUTH_LOGIN_FAILED',source_ip=ip,request_id=rid,result=Result.DENIED)
            if row.failure_count_total>=MAX_COUNT:row.failure_count_lower_bound=True
            else:row.failure_count_total+=1
            times.append(now);row.failure_times=[t.isoformat() for t in times[-5:]]
            row.blocked_until=now+timedelta(seconds=900) if len(times)>=5 else None
            if row.blocked_until:event('AUTH_IP_LIMITED',source_ip=ip,request_id=rid,result=Result.DENIED)
            row.expires_at=row.blocked_until or now+timedelta(seconds=600)
            row.save()
            return False
        old_key=request.session.session_key
        replacement=1 if old_key and AuthSession.objects.filter(pk=old_key).exists() else 0
        if AuthSession.objects.count()-replacement >= settings.AUTH_SESSION_CAP:
            capacity_state('sessions',True)
            row.save()
            return False
        flush_throttle_counts(row)
        row.failure_count_total=0;row.failure_count_lower_bound=False
        row.blocked_repeats=0;row.repeat_count_lower_bound=False
        row.failure_times=[];row.blocked_until=None;row.expires_at=now+timedelta(seconds=600);row.save()
        request.session.flush()
        django_login(request,current.user,backend='django.contrib.auth.backends.ModelBackend')
        request.session.set_expiry(43200)
        request.session.save()
        if old_key:AuthSession.objects.filter(pk=old_key).delete()
        AuthSession.objects.create(session_key=request.session.session_key,user=current.user,
                                   generation=current.generation,issued_at=now,last_seen=now)
        event('AUTH_LOGIN_SUCCESS',actor=current.user,source_ip=ip,request_id=rid)
        return True

def authenticate_request(request, username, password):
    original_key=request.session.session_key
    original_user=request.user
    store_type=type(request.session)
    try:
        return _authenticate_request(request,username,password)
    except Exception:
        # A rolled-back login must not be re-saved by SessionMiddleware afterwards.
        request.session=store_type(session_key=original_key)
        request.user=original_user
        raise

def require_session(request, *, touch=True):
    key=request.session.session_key
    if not key or not request.user.is_authenticated:
        raise PermissionDenied('AUTH_SESSION_REQUIRED')
    expired=False
    with transaction.atomic():
        lock_auth()
        now=clock.now()
        state=AuthSession.objects.select_related('user__security_profile').filter(pk=key).first()
        profile=UserProfile.objects.filter(user_id=state.user_id).first() if state else None
        if (state is None or profile is None or state.user_id!=request.user.pk or not state.user.is_active
                or state.generation!=profile.generation or now-state.last_seen>IDLE
                or now-state.issued_at>ABSOLUTE or now<state.issued_at or now<state.last_seen):
            if state:
                flush_session_counts(state)
                event('AUTH_SESSION_EXPIRED',actor=state.user)
                state.delete();Session.objects.filter(pk=key).delete()
            expired=True
        else:
            if touch:
                state.last_seen=now;state.save(update_fields=['last_seen'])
            request.auth_generation=state.generation
    if expired:
        request.session.flush()
        raise PermissionDenied('AUTH_SESSION_EXPIRED')
    return state.user

def note_denial(request, scope):
    if scope not in ('owner','page'):
        raise ValueError('AUTH_UNKNOWN_PERMISSION_SCOPE')
    with transaction.atomic():
        lock_auth()
        state=AuthSession.objects.select_related('user').filter(pk=request.session.session_key).first()
        if state is None or state.user_id!=request.user.pk:
            return
        field='denied_'+scope+'_count'
        count=getattr(state,field)
        if count==0:event('SEC_PERMISSION_DENIED',actor=state.user,result=Result.DENIED)
        if count>=MAX_COUNT:state.denial_count_lower_bound=True
        else:setattr(state,field,count+1)
        state.save(update_fields=[field,'denial_count_lower_bound'])

def logout_request(request):
    with transaction.atomic():
        lock_auth()
        key=request.session.session_key
        if key:
            state=AuthSession.objects.select_related('user').filter(pk=key).first()
            if state:
                flush_session_counts(state);event('AUTH_LOGOUT',actor=state.user);state.delete()
        request.session.flush()


def recover_owner(password):
    password_value(password)
    with transaction.atomic():
        lock_content('default');lock_auth()
        profile=UserProfile.objects.select_related('user').get(role='owner',user__username='nesadmin')
        profile.user.set_password(password);profile.user.save(update_fields=['password'])
        invalidate(profile)
        event('AUTH_OWNER_PASSWORD_RECOVERED',target=profile.user)


def invalidate_all_sessions():
    """Trusted local recovery/compromise integration hook; never a public endpoint."""
    with transaction.atomic():
        lock_content('default');lock_auth()
        for profile in UserProfile.objects.select_related('user').all():invalidate(profile)
        event('AUTH_ALL_SESSIONS_REVOKED')
