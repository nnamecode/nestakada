"""Read-only validation of the actual local evidence package, never admission."""
import copy
import hashlib
import json
import re
import signal
import sys
import tempfile
from pathlib import Path

SOURCE = '014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672'
SCHEMA = '4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7'


class ValidationFailure(Exception):
    pass


def require(value, code):
    if not value:
        raise ValidationFailure(code)


def main():
    result = {'status': 'FAIL', 'scope': 'actual-evidence-file-validation-not-activation',
              'writeAdmission': False, 'unitBypass': False, 'databaseConfigured': False,
              'positive': None, 'negative': []}
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(ValidationFailure('EVIDENCE_VALIDATION_DEADLINE')))
    signal.alarm(20)
    try:
        sys.path.insert(0, '/trust')
        from django.conf import settings
        require(not settings.configured, 'VALIDATOR_SETTINGS_ALREADY_CONFIGURED')
        settings.configure(INSTALLED_APPS=['journal'], DATABASES={'default': {'ENGINE': 'django.db.backends.dummy'}},
                           SECRET_KEY='metadata-only-evidence-validator', USE_TZ=True)
        import django
        django.setup()
        from journal import bounded as B, profile as P
        from journal.protocol import Fault, canonical
        require(not B._unit_authority.get(), 'VALIDATOR_UNIT_BYPASS')
        require(B.connection.connection is None, 'VALIDATOR_CONNECTION_EXISTS')
        require(P.source_fingerprint() == SOURCE and len(P.source_files()) == 30, 'VALIDATOR_SOURCE')
        paths = {kind: Path('/evidence', kind + '.json') for kind in ('unit', 'calibration', 'review')}
        original = {kind: B._read_file(path, 1048576) for kind, path in paths.items()}
        sha = lambda raw: hashlib.sha256(raw).hexdigest()
        hashes = {kind: sha(raw) for kind, raw in original.items()}
        policy = {'sourceFingerprint': SOURCE, 'schemaFingerprint': SCHEMA,
                  'caps': copy.deepcopy(B.CAPS), 'evidence': hashes.copy()}
        require(B._completed_evidence(policy, paths) is None, 'VALIDATOR_POSITIVE_RESULT')
        result['positive'] = {'status': 'PASS', 'manifestSha256': hashes,
                              'function': 'journal.bounded._completed_evidence'}
        cases = [('changed-raw-sha', 'unit'), ('status', 'unit'), ('source', 'unit'),
                 ('schema', 'unit'), ('caps', 'unit'), ('extra-field', 'unit'),
                 ('unit-coverage', 'unit'), ('calibration-coverage', 'calibration'),
                 ('review-coverage', 'review'), ('duplicate-check', 'calibration')]
        for name, kind in cases:
            with tempfile.TemporaryDirectory(prefix='trust-evidence-', dir='/tmp') as temp:
                candidate_paths = {key: Path(temp, key + '.json') for key in paths}
                for key, path in candidate_paths.items():
                    path.write_bytes(original[key])
                candidate = copy.deepcopy(policy)
                changed = json.loads(original[kind])
                if name == 'changed-raw-sha':
                    raw = original[kind] + b' '
                else:
                    if name == 'status':
                        changed['status'] = 'IN_PROGRESS'
                    elif name == 'source':
                        changed['sourceFingerprint'] = '0' * 64
                    elif name == 'schema':
                        changed['schemaFingerprint'] = '0' * 64
                    elif name == 'caps':
                        changed['caps']['maxOperations'] = 1001
                    elif name == 'extra-field':
                        changed['extra'] = True
                    elif name.endswith('-coverage'):
                        changed['checks'] = changed['checks'][:-1]
                    elif name == 'duplicate-check':
                        changed['checks'][-1] = changed['checks'][0]
                    raw = canonical(changed)
                    # Matching the hash of invalid content must not authorize it.
                    candidate['evidence'][kind] = sha(raw)
                candidate_paths[kind].write_bytes(raw)
                try:
                    B._completed_evidence(candidate, candidate_paths)
                except Fault as error:
                    require(error.code in ('ADMISSION_EVIDENCE_REJECTED', 'INPUT_REJECTED'),
                            'VALIDATOR_UNEXPECTED_FAULT')
                    result['negative'].append({'case': name, 'kind': kind, 'status': 'PASS',
                                               'rejection': error.code,
                                               'testPolicyHashRecomputed': name != 'changed-raw-sha'})
                else:
                    raise ValidationFailure('VALIDATOR_ACCEPTED_BAD_EVIDENCE')
                require(not B._unit_authority.get() and B.connection.connection is None,
                        'VALIDATOR_BYPASS_OR_CONNECTION')
        require(len(result['negative']) == 10, 'VALIDATOR_CASE_COUNT')
        require(all(B._read_file(paths[kind], 1048576) == raw for kind, raw in original.items()),
                'VALIDATOR_CHANGED_PACKAGE')
        require(P.source_fingerprint() == SOURCE, 'VALIDATOR_SOURCE_CHANGED')
        cg = Path('/sys/fs/cgroup')
        pairs = lambda name: {key: int(value) for key, value in
                              (line.split() for line in (cg / name).read_text().splitlines())}
        events = pairs('memory.events')
        require(events['oom'] == 0 and events['oom_kill'] == 0, 'VALIDATOR_OOM')
        result.update(status='PASS', sourceFingerprint=SOURCE, schemaFingerprint=SCHEMA,
                      packageUnchanged=True, connectionOpened=False,
                      resources={'memoryPeak': int((cg / 'memory.peak').read_text()),
                                 'memoryMax': int((cg / 'memory.max').read_text()),
                                 'memoryEvents': events, 'cpu': pairs('cpu.stat'),
                                 'period': 'validator-before-final-json-and-process-exit'})
    except Exception as error:
        code = str(error) if isinstance(error, ValidationFailure) else 'EVIDENCE_VALIDATION_FAILED'
        result.update(status='FAIL', errorClass=type(error).__name__,
                      errorCode=code if re.fullmatch('[A-Z0-9_]{1,80}', code) else 'EVIDENCE_VALIDATION_FAILED')
    finally:
        signal.alarm(0)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
