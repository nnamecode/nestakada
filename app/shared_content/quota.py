"""Actual shared relation accounting. No unvetted reservation grants a write."""
import hashlib
import json
from uuid import UUID

from django.db import connection, transaction
from django.db.models import Q
from media_library.models import AssetUsage
from content.models import lock_content
from .faults import SharedFault
from .models import (SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage,
    SharedReceipt, SharedBasePin, SharedIdentityReservation, SharedBudget, SharedCleanupJob)
from .storage import SharedStorage

BYTE_LIMIT = 268435456
SNAPSHOT_LIMIT = 10000
WARNING_BYTES = 201326592
MODELS = (SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage,
          SharedReceipt, SharedBasePin, SharedIdentityReservation, SharedBudget, SharedCleanupJob)


def schema_signature():
    tables = sorted([model._meta.db_table for model in MODELS] + [AssetUsage._meta.db_table])
    with connection.cursor() as cursor:
        cursor.execute("""SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),
            a.attnotnull,pg_get_expr(d.adbin,d.adrelid) FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid
            LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
            WHERE n.nspname='app' AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped
            ORDER BY c.relname,a.attnum""", [tables])
        columns = cursor.fetchall()
        cursor.execute("""SELECT c.relname,pg_get_indexdef(i.indexrelid) FROM pg_index i
            JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='app' AND c.relname=ANY(%s) ORDER BY c.relname,i.indexrelid::regclass::text""", [tables])
        indexes = cursor.fetchall()
        cursor.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='app' AND c.relname=ANY(%s) ORDER BY c.relname,k.conname""", [tables])
        constraints = cursor.fetchall()
    return hashlib.sha256(json.dumps([columns, indexes, constraints], sort_keys=True).encode()).hexdigest()


def measure_locked(*, held_books=None, resolved=False):
    if not connection.in_atomic_block:
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
    from .reservations import assert_connection
    assert_connection()
    tables = sorted(model._meta.db_table for model in MODELS)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT c.oid,c.relname,c.relkind,c.relpersistence,
            pg_get_userbyid(c.relowner),c.reltoastrelid,pg_total_relation_size(c.oid),
            pg_table_size(c.oid),pg_indexes_size(c.oid)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='app' AND c.relname=ANY(%s) ORDER BY c.relname""", [tables])
        rows = cursor.fetchall()
    if (len(rows) != len(tables) or [row[1] for row in rows] != tables
            or any(row[2] != 'r' or row[3] != 'p' or row[4] != 'app_migrator'
                   or row[6] != row[7] + row[8] for row in rows)):
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
    pg_used = sum(row[6] for row in rows)
    referenced_keys = set(SharedRevision.objects.filter(storage_kind='file').values_list('file_key', flat=True))
    referenced_keys.update(SharedDraft.objects.filter(storage_kind='file').values_list('file_key', flat=True))
    fs = SharedStorage().inventory(referenced_keys=referenced_keys)
    from .profiles import profile, evidence
    active_profile = profile()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_total_relation_size(%s::regclass)", ['app.' + AssetUsage._meta.db_table])
        usage_physical = cursor.fetchone()[0]
    all_refs = AssetUsage.objects.count()
    valid_revisions = SharedIdentityReservation.objects.filter(kind='sharedrevision', block__isnull=False).values('id')
    valid_drafts = SharedIdentityReservation.objects.filter(kind='shareddraft', block__isnull=False).values('id')
    owned_condition = (Q(kind='shared_block', consumer_id__in=valid_revisions)
                       | Q(kind='draft', consumer_id__in=valid_drafts))
    from page_versions.models import IdentityReservation as PageIdentity, OwnerDraft as PageDraft
    valid_page_drafts = PageIdentity.objects.filter(kind='ownerdraft',
        pk__in=PageDraft.objects.values('id')).values('id')
    if (AssetUsage.objects.filter(kind='shared_block').exclude(consumer_id__in=valid_revisions).exists()
            or AssetUsage.objects.filter(consumer_id__in=SharedIdentityReservation.objects.values('id'))
                .exclude(owned_condition).exists()
            or AssetUsage.objects.filter(kind='draft').exclude(owned_condition)
                .exclude(consumer_id__in=valid_page_drafts).exists()):
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
    own_refs = AssetUsage.objects.filter(
        owned_condition).count()
    if own_refs > all_refs:
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
    assigned = (usage_physical * own_refs + all_refs - 1) // all_refs if own_refs else 0
    budget = SharedBudget.objects.get(singleton=True)
    debt = budget.retained_debt_bytes
    fs_charge = (len(fs['files']) * active_profile.fs_metadata_per_object) if active_profile else 0
    used = pg_used + fs['actualAllocatedBytes'] + assigned + fs_charge + debt
    held = None if fs['journalCount'] and held_books is None else 0
    if held_books is not None:
        expected_names = {'journal/' + UUID(record['book']['operationId']).hex + '.json' for record in held_books}
        actual_names = {row['key'] for row in fs['files'] if row['kind'] == 'journal'}
        if expected_names != actual_names or len(held_books) != len(actual_names):
            raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
        for record in held_books:
            from .profiles import ADMITTED_BOOK_RESERVES
            if (active_profile is None or ADMITTED_BOOK_RESERVES.get(record['book']['profileId'])
                    != record['book']['reservedBytes']):
                raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
            if resolved:
                from .reservations import _book_matches
                receipt = SharedReceipt.objects.filter(pk=record['book']['operationId']).first()
                if receipt is None or not _book_matches(receipt, record):
                    raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
            else:
                held += record['book']['reservedBytes']
    cleanup_held = sum(SharedCleanupJob.objects.exclude(phase='complete').values_list('reserved_bytes', flat=True))
    if held is not None:
        held += cleanup_held
    count = SharedRevision.objects.count()
    relations = [{'oid': row[0], 'table': row[1], 'toastOid': row[5],
                  'totalBytes': row[6], 'tableBytesIncludingToast': row[7],
                  'indexBytes': row[8]} for row in rows]
    available = active_profile is not None and budget.accounting_version != 'faulted' and held is not None
    return {'usedBytes': used, 'accountedBytes': used, 'heldBytes': held,
            'effectiveUsedBytes': used + held if held is not None else None,
            'cleanupHeldBytes': cleanup_held,
            'maintenanceReserveBytes': active_profile.maintenance_reserve if active_profile else None,
            'retainedDebtBytes': debt, 'usageRootBytes': usage_physical, 'allRefs': all_refs,
            'ownRefs': own_refs, 'assignedUsageBytes': assigned, 'fsMetadataChargeBytes': fs_charge,
            'actualCombinedBytes': pg_used + fs['actualAllocatedBytes'], 'actualPgBytes': pg_used,
            'actualOwnFsAllocatedBytes': fs['actualAllocatedBytes'], 'actualAllocatedBytes': fs['actualAllocatedBytes'],
            'fsMetadataReserveAvailable': active_profile is not None,
            'reserveBytes': active_profile.reserve_bytes if active_profile else None,
            'coreGrowthHeadroomBytes': active_profile.core_growth_headroom if active_profile else None,
            'reservationReadiness': available, 'calibrationMode': evidence() is not None,
            'filesystem': fs, 'snapshotCount': count, 'limitBytes': BYTE_LIMIT,
            'snapshotLimit': SNAPSHOT_LIMIT, 'warning': used >= WARNING_BYTES,
            'profileAvailable': available, 'relations': relations,
            'inventoryStamp': hashlib.sha256(json.dumps({'pg': relations, 'fs': fs['inventoryStamp']}, sort_keys=True).encode()).hexdigest()}


def measure():
    with transaction.atomic():
        lock_content('default')
        return measure_locked()


def reserve_locked(*, snapshot_increment):
    if type(snapshot_increment) is not int or snapshot_increment < 0:
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503)
    current = measure_locked()
    if current['snapshotCount'] + snapshot_increment > SNAPSHOT_LIMIT:
        raise SharedFault('SHARED_HISTORY_COUNT_FULL')
    if current['usedBytes'] >= BYTE_LIMIT:
        raise SharedFault('SHARED_HISTORY_BYTES_FULL')
    # No schema/index/AssetUsage/audit/transient upper bound has been vetted.
    # This is a code-owned closed gate; settings/HTTP cannot bypass it.
    raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503)


def fits(remaining_bytes, required_bytes):
    """Exact integer admission boundary; a negative remainder has no capacity."""
    if type(remaining_bytes) is not int or type(required_bytes) is not int or required_bytes < 0:
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503, operation_not_started=True)
    return remaining_bytes >= required_bytes


def admission_requirement(measurement, new_refs):
    from .profiles import profile
    active = profile()
    if active is None:
        raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503, operation_not_started=True)
    if type(new_refs) is not int or not 0 <= new_refs <= 4:
        raise SharedFault('SHARED_MEASUREMENT_UNAVAILABLE', 503, operation_not_started=True)
    total, own = measurement['allRefs'] + new_refs, measurement['ownRefs'] + new_refs
    prospective = ((measurement['usageRootBytes'] + active.usage_growth_allowance) * own + total - 1) // total if own else 0
    delta = max(0, prospective - measurement['assignedUsageBytes'])
    return {'requiredBytes': delta + active.core_growth_headroom + active.reserve_bytes + active.maintenance_reserve,
        'prospectiveAssignedUsageBytes': prospective, 'prospectiveUsageDeltaBytes': delta,
        'coreGrowthHeadroomBytes': active.core_growth_headroom, 'reserveBytes': active.reserve_bytes,
        'maintenanceReserveBytes': active.maintenance_reserve}


def admit_locked(*, snapshot_increment, new_refs):
    from .profiles import profile
    active = profile()
    value = measure_locked(held_books=[])
    if active is None or not value['profileAvailable']:
        raise SharedFault('SHARED_BUDGET_PROFILE_UNAVAILABLE', 503, operation_not_started=True)
    if value['snapshotCount'] + snapshot_increment > SNAPSHOT_LIMIT:
        raise SharedFault('SHARED_HISTORY_COUNT_FULL', operation_not_started=True)
    value.update(admission_requirement(value, new_refs))
    value['prospectiveEffectiveUsedBytes'] = value['usedBytes'] + value['requiredBytes']
    from .profiles import evidence
    report = evidence()
    if report is not None:
        report['events'].append({'phase': 'reservation_admission', 'measurement': value.copy()})
    if not fits(BYTE_LIMIT - value['usedBytes'], value['requiredBytes']):
        raise SharedFault('SHARED_HISTORY_BYTES_FULL', operation_not_started=True)
    return value
