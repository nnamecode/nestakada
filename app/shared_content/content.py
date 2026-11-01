"""Explicit legacy-inline/file descriptors. A missing blob never falls back."""
import hashlib
from django.core.exceptions import ValidationError
from django.db import connection
from .faults import SharedFault
from .storage import SharedStorage, checked_descriptor


def descriptor_for(record):
    if type(record) is dict:
        return dict(record)
    return {key: getattr(record, key) for key in
        ('storage_kind', 'html', 'file_key', 'byte_size', 'file_sha256', 'payload_hash')}


def validate_metadata(descriptor):
    value = descriptor_for(descriptor)
    if set(value) - {'storage_kind', 'html', 'file_key', 'byte_size', 'file_sha256', 'payload_hash'}:
        raise ValueError('SHARED_DESCRIPTOR_FIELD_INVALID')
    if value.get('storage_kind') == 'inline':
        if (type(value.get('html')) is not str or value.get('file_key', '') != ''
                or value.get('byte_size') is not None or value.get('file_sha256', '') != ''):
            raise ValueError('SHARED_INLINE_DESCRIPTOR_INVALID')
        if value.get('payload_hash') != hashlib.sha256(value['html'].encode('utf-8')).hexdigest():
            raise ValueError('SHARED_INLINE_HASH_MISMATCH')
    elif value.get('storage_kind') == 'file':
        checked_descriptor({key: value.get(key) for key in
            ('storage_kind', 'file_key', 'byte_size', 'file_sha256')})
        if value.get('html', '') != '' or value.get('payload_hash', value['file_sha256']) != value['file_sha256']:
            raise ValueError('SHARED_FILE_DESCRIPTOR_INVALID')
    else:
        raise ValueError('SHARED_STORAGE_KIND_INVALID')
    return value


def clean_record(record):
    try:
        validate_metadata(record)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('SHARED_STORAGE_DESCRIPTOR_INVALID') from None


def content_html(record_or_descriptor, storage=None):
    try:
        value = validate_metadata(record_or_descriptor)
        if value['storage_kind'] == 'inline':
            return value['html']
        if connection.in_atomic_block:
            raise SharedFault('SHARED_CONTENT_READ_IN_TRANSACTION', 503)
        return (storage or SharedStorage()).read({key: value[key] for key in
            ('storage_kind', 'file_key', 'byte_size', 'file_sha256')})
    except (ValueError, TypeError, AttributeError):
        raise SharedFault('SHARED_CONTENT_UNAVAILABLE', 503) from None
