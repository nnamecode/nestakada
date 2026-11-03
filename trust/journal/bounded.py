"""Signed, bounded local admission. No HTTP policy activation or APP authority."""
import contextvars
import hashlib
import hmac
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError, connection, transaction

from . import auth, profile as P, services as S, state_v2 as V
from .models import AdmissionPolicy, Credential, Operation, RecoveryReceipt, RequestTombstone, RoutePolicy
from .protocol import Fault, MAX_INT, canonical, closed, digest, integer, parse, uid

SCOPE = 'LOCAL_TRUST_BOUNDED_WRITER'
ACTIVATION_SCOPE = 'LOCAL_TRUST_ADMISSION_ACTIVATION'
MAX_ENVELOPE = 65536
CAPS = {'logicalBytes': 67108864, 'completionBytes': 16777216,
    'maxOperations': 1000, 'maxHistoricalReferences': 4096, 'maxTombstones': 1024,
    'maxRecoveryActions': 4, 'maxCredentials': 20, 'maxPolicyRows': 16,
    'maxPolicyRowBytes': 32768, 'maxMessageBytes': 1048576, 'maxTargets': 256,
    'maxTargetBytes': 2048}
_unit_authority = contextvars.ContextVar('trust_bounded_unit_authority', default=False)


def _unit_database():
    # Metadata can be changed while a connection to another database survives.
    # Reject wrong metadata without SQL, then verify the actual server identity.
    if (os.environ.get('TRUST_TEST_EXECUTION') != '1'
        or connection.vendor != 'postgresql'
        or connection.settings_dict['NAME'] != 'test_estakada_trust'):
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database()')
            return cursor.fetchone() == ('test_estakada_trust',)
    except DatabaseError:
        return False


@contextmanager
def unit_calibration():
    """UNIT-only evidence bootstrap; never bypass caps, signing, binding or CAS."""
    if not _unit_database():
        raise Fault('TEST_SCOPE_REJECTED', 503)
    token = _unit_authority.set(True)
    try:
        yield
    finally:
        _unit_authority.reset(token)


def _hex(value):
    if not P._hex(value):
        raise Fault('BOUNDED_ADMISSION_REJECTED', 503)
    return value


def _read_file(path, maximum=MAX_ENVELOPE):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError()
        raw = os.read(fd, maximum + 1)
        if len(raw) > maximum:
            raise ValueError()
        return raw
    finally:
        os.close(fd)


def _configuration_sha():
    return hashlib.sha256(Path(settings.TRUST_CREDENTIALS_FILE).read_bytes()).hexdigest()


def _signed(envelope):
    if len(canonical(envelope)) > MAX_ENVELOPE:
        raise ValueError()
    closed(envelope, {'payload', 'signature'})
    _hex(envelope['signature'])
    recovery = [item for item in auth.configuration().values() if item['role'] == 'recovery']
    if len(recovery) != 1:
        raise ValueError()
    expected = hmac.new(bytes.fromhex(recovery[0]['secret']),
        canonical(envelope['payload']), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, envelope['signature']):
        raise ValueError()
    return envelope['payload'], recovery[0]


def _policy(policy):
    closed(policy, {'policyId', 'epoch', 'incarnation', 'dbName', 'protocolVersion',
        'sourceFiles', 'sourceFingerprint', 'schemaFingerprint', 'evidence', 'caps'})
    uid(policy['policyId']); uid(policy['incarnation'])
    if not 1 <= integer(policy['epoch']) <= CAPS['maxPolicyRows']:
        raise ValueError()
    if (policy['dbName'] != connection.settings_dict['NAME']
        or policy['dbName'] not in ('estakada_trust', 'test_estakada_trust')
        or policy['incarnation'] != auth.identity()
        or type(policy['protocolVersion']) is not int or policy['protocolVersion'] != 1):
        raise ValueError()
    closed(policy['caps'], CAPS)
    if policy['caps'] != CAPS or any(type(value) is not int for value in policy['caps'].values()):
        raise ValueError()
    _hex(policy['sourceFingerprint']); _hex(policy['schemaFingerprint'])
    rows = P.source_files()
    if policy['sourceFiles'] != rows or policy['sourceFingerprint'] != digest(rows):
        raise ValueError()
    closed(policy['evidence'], {'unit', 'calibration', 'review'})
    for value in policy['evidence'].values():
        _hex(value)


def _deployment(deployment):
    closed(deployment, {'api', 'db', 'ingress', 'configFingerprint', 'evidence'})
    for component, limits in P.DEPLOYMENT.items():
        closed(deployment[component], limits)
        if deployment[component] != limits or any(type(value) is not int for value in deployment[component].values()):
            raise ValueError()
    _hex(deployment['configFingerprint']); _hex(deployment['evidence'])
    P.runtime_resource_facts()


def _exclusion(exclusion, runtime):
    closed(exclusion, {'previousRuntimeId', 'previousContainerId', 'newRuntimeId',
        'newContainerId', 'evidenceSha256'})
    uid(exclusion['previousRuntimeId']); uid(exclusion['newRuntimeId'])
    for key in ('previousContainerId', 'newContainerId', 'evidenceSha256'):
        _hex(exclusion[key])
    if (exclusion['newRuntimeId'] != runtime
        or exclusion['previousRuntimeId'] == runtime
        or exclusion['previousContainerId'] == exclusion['newContainerId']):
        raise ValueError()


def _proof(proof, lease):
    if proof is None:
        return
    closed(proof, {'fenceActionId', 'fenceReceiptDigest', 'head', 'stateDigestVersion',
        'stateDigest', 'runtimeId', 'credentialConfigSha256', 'exclusion'})
    uid(proof['fenceActionId'])
    if type(proof['stateDigestVersion']) is not int or proof['stateDigestVersion'] != V.VERSION:
        raise ValueError()
    for key in ('fenceReceiptDigest', 'stateDigest', 'credentialConfigSha256'):
        _hex(proof[key])
    closed(proof['head'], {'incarnation', 'generation', 'writerEpoch', 'mode', 'digest'})
    uid(proof['head']['incarnation']); integer(proof['head']['generation']); integer(proof['head']['writerEpoch'])
    _hex(proof['head']['digest'])
    if (proof['head']['mode'] not in ('ACTIVE', 'FROZEN')
        or proof['runtimeId'] != lease['runtimeId']
        or proof['credentialConfigSha256'] != lease['credentialConfigSha256']
        or proof['exclusion'] != lease['exclusion']):
        raise ValueError()


def read_envelope():
    """All file/HMAC/source/config/runtime/cgroup failures occur before SQL."""
    try:
        envelope = parse(_read_file(settings.TRUST_WRITE_PERMIT_FILE))
        payload, _ = _signed(envelope)
        closed(payload, {'schemaVersion', 'scope', 'policy', 'lease'})
        if type(payload['schemaVersion']) is not int or payload['schemaVersion'] != 2 or payload['scope'] != SCOPE:
            raise ValueError()
        _policy(payload['policy'])
        lease = payload['lease']
        closed(lease, {'policyDigest', 'runtimeId', 'credentialConfigSha256', 'deployment',
            'exclusion', 'recoveryActions', 'reconciliation'})
        uid(lease['runtimeId']); _hex(lease['policyDigest']); _hex(lease['credentialConfigSha256'])
        if (lease['policyDigest'] != digest(payload['policy'])
            or lease['runtimeId'] != settings.TRUST_RUNTIME_ID
            or lease['credentialConfigSha256'] != _configuration_sha()):
            raise ValueError()
        _deployment(lease['deployment']); _exclusion(lease['exclusion'], lease['runtimeId'])
        _proof(lease['reconciliation'], lease)
        actions = lease['recoveryActions']
        if type(actions) is not list or len(actions) > CAPS['maxRecoveryActions']:
            raise ValueError()
        seen = set()
        for action in actions:
            closed(action, {'id', 'credentialId', 'writerEpoch', 'phase', 'fingerprint'})
            uid(action['id']); integer(action['writerEpoch']); _hex(action['fingerprint'])
            if action['phase'] not in ('fence', 'activate') or type(action['phase']) is not str:
                raise ValueError()
            item = auth.configuration().get(action['credentialId']) if type(action['credentialId']) is str else None
            if item is None or item['role'] != 'recovery':
                raise ValueError()
            key = (action['id'], action['phase'])
            if key in seen:
                raise ValueError()
            seen.add(key)
        return envelope
    except (OSError, ValueError, TypeError, KeyError, AttributeError, Fault, RecursionError):
        raise Fault('BOUNDED_ADMISSION_REJECTED', 503) from None


def check(actor, body, phase, fingerprint):
    if settings.TRUST_WRITE_PROFILE != 'local-bounded-writer':
        raise Fault('WRITE_PROFILE_DISABLED', 503)
    envelope = read_envelope()
    if phase in ('fence', 'activate'):
        candidate = {'id': body['actionId'], 'credentialId': actor['id'],
            'writerEpoch': body['writerEpoch'], 'phase': phase, 'fingerprint': fingerprint}
        if (body.get('scope') != SCOPE or actor['role'] != 'recovery'
            or candidate not in envelope['payload']['lease']['recoveryActions']):
            raise Fault('WRITE_PERMIT_SCOPE_REJECTED', 403)
    elif phase not in ('prepare', 'unknown', 'committed', 'aborted') or actor['role'] != 'writer':
        raise Fault('WRITE_PERMIT_SCOPE_REJECTED', 403)
    return envelope


def latest_policy():
    """Caller holds Head; validate the full small append-only predecessor chain."""
    if not connection.in_atomic_block:
        raise Fault('ADMISSION_LOCK_REQUIRED', 503)
    rows = list(AdmissionPolicy.objects.order_by('epoch')[:CAPS['maxPolicyRows'] + 1])
    if len(rows) > CAPS['maxPolicyRows']:
        raise Fault('ADMISSION_CHAIN_REJECTED', 503)
    previous = None
    for epoch, row in enumerate(rows, 1):
        if (type(row.policy) is not dict or row.epoch != epoch or row.policy_digest != digest(row.policy)
            or row.policy.get('policyId') != str(row.id) or row.policy.get('epoch') != str(epoch)
            or row.state_digest_version != V.VERSION or not 1 <= row.logical_bytes <= CAPS['maxPolicyRowBytes']
            or (row.previous_digest != previous.policy_digest if previous else row.previous_digest is not None)
            or (row.legacy_seal is not None if previous else not P._hex(row.legacy_seal))):
            raise Fault('ADMISSION_CHAIN_REJECTED', 503)
        charge = len(canonical({**V.persistent_values(row),
            'logical_bytes': CAPS['maxPolicyRowBytes']})) + 4096
        if row.logical_bytes != charge:
            raise Fault('ADMISSION_CHAIN_REJECTED', 503)
        previous = row
    return previous


def check_locked(envelope, actor, body, phase, fingerprint, head):
    fresh = check(actor, body, phase, fingerprint)
    if canonical(fresh) != canonical(envelope):
        raise Fault('WRITE_PERMIT_CHANGED', 503)
    policy = fresh['payload']['policy']; lease = fresh['payload']['lease']
    current = latest_policy()
    if (current is None or current.policy != policy or current.policy_digest != lease['policyDigest']
        or str(head.incarnation) != policy['incarnation']
        or P.schema_fingerprint() != policy['schemaFingerprint']):
        raise Fault('ADMISSION_POLICY_MISMATCH', 503)
    # Repeat authoritative active binding/role/epoch validation under the same lock.
    S.locked(actor, policy['incarnation'], body.get('writerEpoch'))
    _counts(head)
    return {'policy': policy, 'lease': lease, 'caps': CAPS.copy(),
        'reconciliation': lease['reconciliation'],
        'credentialConfigSha256': lease['credentialConfigSha256']}


def legacy_seal(head):
    return digest({'planId': str(head.plan_id) if head.plan_id else None,
        'permittedOperations': head.permitted_operations,
        'permittedRecoveryActions': head.permitted_recovery_actions})


def _operator_role():
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_user, session_user')
        if cursor.fetchone() != ('trust_migrator', 'trust_migrator'):
            raise Fault('ADMISSION_OPERATOR_REQUIRED', 403)


def _completed_evidence(policy, paths):
    """Verify actual completed artifacts, not only claimed hashes in a signature.

    The closed evidence manifest accompanies the actual unit/capacity/review
    report; its hash is policy-bound. Review is supplied by the operator, not
    inferred from an ENV flag. UNIT bootstrap substitutes only this final gate.
    """
    if _unit_authority.get():
        if not _unit_database():
            raise Fault('TEST_SCOPE_REJECTED', 503)
        return
    closed(paths, {'unit', 'calibration', 'review'})
    required = {'unit': ['RP15-%03d' % n for n in range(1, 8)],
        'calibration': ['RP15-%03d' % n for n in range(8, 13)],
        'review': ['CODE', 'QA', 'CAPACITY']}
    for kind, path in paths.items():
        raw = _read_file(path, 1048576)
        if hashlib.sha256(raw).hexdigest() != policy['evidence'][kind]:
            raise Fault('ADMISSION_EVIDENCE_REJECTED', 503)
        report = parse(raw)
        closed(report, {'kind', 'status', 'sourceFingerprint', 'schemaFingerprint', 'caps', 'checks'})
        if (report['kind'] != kind or report['status'] != 'PASS'
            or report['sourceFingerprint'] != policy['sourceFingerprint']
            or report['schemaFingerprint'] != policy['schemaFingerprint']
            or report['caps'] != CAPS or report['checks'] != required[kind]):
            raise Fault('ADMISSION_EVIDENCE_REJECTED', 503)


def _intent(envelope):
    try:
        payload, recovery = _signed(envelope)
        closed(payload, {'schemaVersion', 'scope', 'actionId', 'credentialId', 'policy',
            'previousPolicy', 'legacySeal', 'expected', 'credentialConfigSha256', 'evidence', 'configFingerprint'})
        if type(payload['schemaVersion']) is not int or payload['schemaVersion'] != 2 or payload['scope'] != ACTIVATION_SCOPE:
            raise ValueError()
        uid(payload['actionId']); _policy(payload['policy'])
        if payload['credentialId'] != recovery['id'] or payload['credentialConfigSha256'] != _configuration_sha():
            raise ValueError()
        _hex(payload['credentialConfigSha256']); _hex(payload['configFingerprint'])
        if payload['evidence'] != payload['policy']['evidence']:
            raise ValueError()
        expected = payload['expected']
        closed(expected, {'head', 'stateDigestVersion', 'stateDigest'})
        _hex(expected['stateDigest'])
        if type(expected['stateDigestVersion']) is not int or expected['stateDigestVersion'] != V.VERSION:
            raise ValueError()
        # Full concrete-field equality is checked against locked Head below.
        closed(expected['head'], {'id', 'incarnation', 'generation', 'writer_epoch', 'mode', 'digest',
            'logical_bytes', 'reserved_bytes', 'plan_id', 'permitted_operations', 'permitted_recovery_actions'})
        expected_head = expected['head']
        uid(expected_head['incarnation']); _hex(expected_head['digest'])
        if (type(expected_head['id']) is not int or expected_head['id'] != 1
            or expected_head['mode'] not in ('ACTIVE', 'FROZEN')):
            raise ValueError()
        for field in ('generation', 'writer_epoch', 'logical_bytes', 'reserved_bytes'):
            value = expected_head[field]
            if type(value) is not int or value < (1 if field == 'writer_epoch' else 0) or value > MAX_INT:
                raise ValueError()
        if expected_head['plan_id'] is not None:
            uid(expected_head['plan_id'])
        for field, limit in (('permitted_operations', 16), ('permitted_recovery_actions', 4)):
            if expected_head[field] is not None:
                P._unique_ids(expected_head[field], limit)
        if payload['previousPolicy'] is None:
            _hex(payload['legacySeal'])
        else:
            closed(payload['previousPolicy'], {'epoch', 'digest'})
            integer(payload['previousPolicy']['epoch']); _hex(payload['previousPolicy']['digest'])
            if payload['legacySeal'] is not None:
                raise ValueError()
        actor = auth.authenticate('Bearer ' + recovery['id'] + ':' + recovery['secret'], 'recovery')
        return payload, actor
    except (OSError, ValueError, TypeError, KeyError, AttributeError, Fault, RecursionError):
        raise Fault('ADMISSION_INTENT_REJECTED', 503) from None


def _counts(head):
    with connection.cursor() as cursor:
        cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
        references = int(cursor.fetchone()[0])
    if (Operation.objects.count() > CAPS['maxOperations'] or references > CAPS['maxHistoricalReferences']
        or RoutePolicy.objects.count() > CAPS['maxHistoricalReferences']
        or RequestTombstone.objects.count() > CAPS['maxTombstones']
        or RecoveryReceipt.objects.count() > CAPS['maxRecoveryActions']
        or Credential.objects.count() > CAPS['maxCredentials']
        or head.logical_bytes + head.reserved_bytes > CAPS['logicalBytes']
        or head.reserved_bytes > CAPS['completionBytes']):
        raise Fault('ADMISSION_CAPACITY_REJECTED', 503)


def activate(envelope, evidence_paths):
    """Closed operator transition; same signed intent gives one durable receipt."""
    payload, actor = _intent(envelope)
    policy = payload['policy']; fingerprint = digest(payload)
    try:
        _completed_evidence(policy, evidence_paths)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, Fault, RecursionError):
        raise Fault('ADMISSION_EVIDENCE_REJECTED', 503) from None
    with transaction.atomic():
        _operator_role()
        head = S.locked(actor, policy['incarnation']); S.durability()
        # Re-read source/config and all signed structures under Head lock too.
        again, fresh_actor = _intent(envelope)
        if again != payload or fresh_actor != actor or P.schema_fingerprint() != policy['schemaFingerprint']:
            raise Fault('ADMISSION_INTENT_CHANGED', 503)
        current = latest_policy()
        existing = AdmissionPolicy.objects.filter(action_id=payload['actionId']).first()
        if existing:
            if existing.intent_digest != fingerprint or existing.policy_digest != digest(policy):
                raise Fault('ADMISSION_REPLAY_CONFLICT')
            return {'ok': True, 'replay': True, 'receipt': existing.receipt, 'workflowComplete': False}
        expected = payload['expected']
        if expected['head'] != V.persistent_values(head) or expected['stateDigest'] != V.state_digest(head):
            raise Fault('ADMISSION_STATE_CONFLICT')
        if head.generation >= MAX_INT:
            raise Fault('GENERATION_EXHAUSTED', 503)
        epoch = int(policy['epoch'])
        if current is None:
            if (epoch != 1 or payload['previousPolicy'] is not None
                or head.plan_id is None or payload['legacySeal'] != legacy_seal(head)):
                raise Fault('ADMISSION_PREDECESSOR_CONFLICT')
        elif (epoch != current.epoch + 1
            or payload['previousPolicy'] != {'epoch': str(current.epoch), 'digest': current.policy_digest}
            or payload['legacySeal'] is not None):
            raise Fault('ADMISSION_PREDECESSOR_CONFLICT')
        if AdmissionPolicy.objects.count() >= CAPS['maxPolicyRows']:
            raise Fault('ADMISSION_POLICY_CAP', 503)
        _counts(head)
        prior = {**expected, 'credentialId': actor['id'],
            'credentialConfigSha256': payload['credentialConfigSha256'],
            'evidence': payload['evidence'], 'configFingerprint': payload['configFingerprint']}
        head.generation += 1
        head.digest = digest({'previous': head.digest, 'generation': str(head.generation), 'phase': fingerprint})
        receipt = {'actionId': payload['actionId'], 'intentDigest': fingerprint,
            'policyId': policy['policyId'], 'policyDigest': digest(policy), 'epoch': policy['epoch'],
            'head': S.head_dict(head), 'workflowComplete': False}
        fields = {'id': policy['policyId'], 'epoch': epoch,
            'previous_digest': current.policy_digest if current else None,
            'legacy_seal': payload['legacySeal'], 'policy': policy, 'policy_digest': digest(policy),
            'action_id': payload['actionId'], 'intent_digest': fingerprint,
            'state_digest_version': V.VERSION, 'prior_state': prior, 'receipt': receipt}
        # Charge the complete persisted canonical row plus conservative metadata;
        # max-width charge field avoids a self-referential serialized length.
        charge = len(canonical({**fields, 'logical_bytes': CAPS['maxPolicyRowBytes']})) + 4096
        if (charge > CAPS['maxPolicyRowBytes']
            or head.logical_bytes + head.reserved_bytes + charge > CAPS['logicalBytes']):
            raise Fault('ADMISSION_BUDGET_EXHAUSTED', 503)
        AdmissionPolicy.objects.create(**fields, logical_bytes=charge)
        head.logical_bytes += charge; head.save()
        return {'ok': True, 'replay': False, 'receipt': receipt, 'workflowComplete': False}
