"""Versioned, bounded full-state reconciliation; never a public snapshot.

The caller holds the shared Head lock throughout this calculation. Each frame
is an eight-byte big-endian length followed by canonical JSON. Table names,
field lists, rows and counts are separate frames, including empty tables.
Verifiers participate in the hash only, never in the returned value.
"""
import hashlib
import uuid

from django.db import connection

from .models import (AdmissionPolicy, Credential, Head, Operation,
                     RecoveryReceipt, RequestTombstone, RoutePolicy)
from .protocol import Fault, canonical

VERSION = 2
DOMAIN = b'ESTAKADA-TRUST-FULL-STATE\x00v2\x00'
MAX_ROW_BYTES = 3 * 1024 * 1024
TABLES = ((Credential, 20), (Operation, 1000), (RoutePolicy, 4096),
          (RequestTombstone, 1024), (RecoveryReceipt, 4), (AdmissionPolicy, 16))


def persistent_values(instance):
    """Every concrete field, including FK IDs, with UUIDs in canonical form."""
    return {field.attname: str(value) if isinstance(value, uuid.UUID) else value
            for field in instance._meta.concrete_fields
            for value in (getattr(instance, field.attname),)}


def _frame(hasher, value):
    raw = canonical(value)
    if len(raw) > MAX_ROW_BYTES:
        raise Fault('RECONCILIATION_UNAVAILABLE', 503)
    hasher.update(len(raw).to_bytes(8, 'big'))
    hasher.update(raw)


def state_digest(head):
    """Digest v2 under the same lock used by all journal mutations.

    A server-side cursor fetches one row at a time: operation payloads are not
    accumulated into a full ORM list. This is a new format; legacy v1 recovery
    proofs must not be compared to this value without an explicit version.
    """
    if connection.vendor != 'postgresql' or not connection.in_atomic_block:
        raise Fault('RECONCILIATION_LOCK_REQUIRED', 503)
    current = Head.objects.select_for_update().get(pk=1)
    if persistent_values(current) != persistent_values(head):
        raise Fault('RECONCILIATION_HEAD_CHANGED', 503)
    hasher = hashlib.sha256(DOMAIN)
    _frame(hasher, {'stateDigestVersion': VERSION, 'head': persistent_values(current)})
    for model, limit in TABLES:
        fields = [field.attname for field in model._meta.concrete_fields]
        _frame(hasher, {'table': model._meta.db_table, 'fields': fields})
        count = 0
        for row in model.objects.order_by(model._meta.pk.attname).iterator(chunk_size=1):
            count += 1
            if count > limit:
                raise Fault('RECONCILIATION_UNAVAILABLE', 503)
            _frame(hasher, persistent_values(row))
        _frame(hasher, {'count': count})
    return hasher.hexdigest()
