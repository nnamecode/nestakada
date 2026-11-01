"""Extension of the reviewed own-run shared fixture, composed by the host only."""
import json
import os
import sys


def execute_cleanup(request):
    import django
    django.setup()
    from django.conf import settings
    from shared_content.models import SharedCleanupJob, SharedRevision, SharedReceipt
    from shared_content.storage import SharedStorage
    from media_library.models import AssetFile, AssetUsage
    from media_library.storage import MediaStorage
    if (type(request) is not dict or request.get('kind') not in ('seed', 'observe', 'close')
            or os.environ.get('ESTAKADA_LOCAL_ENV') != 'test'
            or settings.ENVIRONMENT != 'test'
            or os.environ.get('DJANGO_SETTINGS_MODULE') != 'probe_settings'):
        raise ValueError('CLEANUP_HTTP_SCOPE')
    if request['kind'] == 'seed':
        if SharedCleanupJob.objects.exclude(phase='complete').exists():
            raise ValueError('CLEANUP_HTTP_UNFINISHED_JOB_PRESERVED')
        return base_execute(request)
    # The base observer validates the exact DB/role/root/owner and all own IDs.
    result = base_execute(dict(request, kind='observe'))
    owner_id = request['state']['ownerId']
    own_jobs = SharedCleanupJob.objects.filter(actor_id=owner_id)
    if request['kind'] == 'close':
        if own_jobs.exclude(phase='complete').exists():
            raise ValueError('CLEANUP_HTTP_OWN_PARTIAL_PRESERVED')
        closed = base_execute(request)
        closed['permanentCleanupJobs'] = own_jobs.count()
        return closed
    inventory = SharedStorage().inventory()
    actual_keys = {item['key'] for item in inventory['files'] if item['kind'] == 'blob'}
    result['cleanupJobs'] = [
        {'id': str(job.pk), 'target': str(job.target_id), 'phase': job.phase,
         'filePresent': job.file_key in actual_keys,
         'targetExists': SharedRevision.objects.filter(pk=job.target_id).exists(),
         'targetUsageCount': AssetUsage.objects.filter(consumer_id=job.target_id).count()}
        for job in own_jobs.order_by('created_at', 'pk')[:20]
    ]
    result['assetManifests'] = {
        str(file.pk): MediaStorage().manifest(file.key)
        for file in AssetFile.objects.filter(asset_id=request['state']['assetId']).order_by('pk')
    }
    result['receiptIds'] = [str(value) for value in SharedReceipt.objects.filter(
        actor_id=owner_id).order_by('-created_at', 'pk').values_list('pk', flat=True)[:20]]
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(execute_cleanup(json.load(sys.stdin)), default=str))
    except Exception as error:
        print(json.dumps({'errorClass': type(error).__name__, 'code': 'CLEANUP_HTTP_FIXTURE_FAILED'}), file=sys.stderr)
        raise SystemExit(1)
