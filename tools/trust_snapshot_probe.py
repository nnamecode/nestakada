"""SS15 native readonly witness, run in the existing isolated API container."""
import json
import signal
from pathlib import Path
import django

def require(value,code):
    if not value: raise RuntimeError(code)

def execute(arg):
    from django.db import connection,transaction
    from journal import auth,recovery,services,profile
    from journal.consumer import HTTPSReader,read_snapshot,startup_check
    from journal.protocol import closed
    closed(arg,{'phase','oldHead'})
    require(arg['phase'] in ('read','blocked','restart'),'PHASE_REJECTED')
    require(connection.settings_dict['NAME']=='estakada_trust' and connection.settings_dict['USER']=='trust_runtime','DATABASE_SCOPE')
    key=next(item for item in auth.configuration().values() if item['role']=='reader')
    actor=auth.authenticate('Bearer '+key['id']+':'+key['secret'],'reader')
    def state():
        with transaction.atomic():
            head=services.locked(actor)
            return services.head_dict(head),recovery.state_digest(head)
    before,before_digest=state()
    reader=HTTPSReader(ca_file='/run/secrets/ingress-ca',credential_id=key['id'],secret=key['secret'])
    calls=[]
    def fetch(target,timeout):
        calls.append(target.split('?',1)[0])
        return reader(target,timeout)
    if arg['phase']=='blocked':
        result=startup_check(fetch,auth.identity(),before)
        require(not result.snapshot_ready and not result.html_admission and not result.workflow_complete,'UNAVAILABLE_OPENED_STARTUP')
        groups=['SS008_REAL_TLS_UNAVAILABLE_CLOSED']
        full_digest=None
    else:
        snapshot=read_snapshot(fetch,auth.identity())
        require(dict(snapshot.head)==before,'HEAD_COHORT_MISMATCH')
        rows=json.loads(snapshot.items_bytes)
        require(len(rows)==4 and snapshot.total_routes==3 and snapshot.total_tombstones==1,'NATIVE_COUNTS_MISMATCH')
        require(any(row.get('policy')=='PENDING_DENY' for row in rows),'PENDING_DENY_LOST')
        require(any(row.get('policy')=='DELETED' for row in rows),'TERMINAL_DENY_LOST')
        require(sum(row['type']=='tombstone' for row in rows)==1,'TOMBSTONE_LOST')
        ready=startup_check(fetch,auth.identity(),before)
        require(ready.snapshot_ready and not ready.html_admission and not ready.workflow_complete,'FALSE_STARTUP_AUTHORITY')
        stale=startup_check(fetch,auth.identity(),arg['oldHead'])
        require(not stale.snapshot_ready and not stale.html_admission and not stale.workflow_complete,'OLD_COHORT_OPENED')
        groups=['SS008_TLS_FULL_SNAPSHOT','SS005_CURRENT_COHORT_NO_HTML_AUTHORITY','SS004_OLD_COHORT_CLOSED']
        full_digest=snapshot.digest
    after,after_digest=state()
    require(before==after and before_digest==after_digest,'READONLY_STATE_CHANGED')
    return {'status':'PASS','phase':arg['phase'],'groups':groups,'head':after,'snapshotDigest':full_digest,
        'stateDigest':after_digest,'requests':len(calls),'paths':sorted(set(calls)),
        'ownResources':profile.runtime_resource_facts(),'htmlAdmission':False,'workflowComplete':False}

if __name__=='__main__':
    try:
        signal.alarm(45)
        django.setup()
        value=execute(ARG)
        print(json.dumps(value,separators=(',',':')))
    except Exception as error:
        code=str(error) if type(error) is RuntimeError else 'SNAPSHOT_PROBE_FAILED'
        if not code.replace('_','').isalnum() or not code.isupper(): code='SNAPSHOT_PROBE_FAILED'
        print(json.dumps({'status':'FAIL','code':code,'dataPreserved':True}))
        raise SystemExit(1) from None
