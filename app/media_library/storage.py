"""Linux no-follow working storage. No image decoding, publication or archive access."""
import hashlib
import os
from pathlib import Path
import stat
from contextlib import contextmanager
from django.conf import settings
from django.core.exceptions import ValidationError
from .paths import storage_key


class MediaParentUnavailable(OSError):
    """A missing root/parent cannot prove absence of the intended leaf."""


class MediaStorage:
    def __init__(self):
        self.root = Path(getattr(settings, 'MEDIA_LIBRARY_ROOT', '/var/lib/estakada/media'))
        if not self.root.is_absolute() or '..' in self.root.parts:
            raise ValidationError('MEDIA_INVALID_ROOT')

    @contextmanager
    def parent(self, key, create=False):
        parts = storage_key(key).split('/')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open('/', flags)
        try:
            # Root ancestors are also opened without following symlinks.
            for part in self.root.parts[1:]:
                try:
                    nxt = os.open(part, flags, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise MediaParentUnavailable('MEDIA_PARENT_UNAVAILABLE') from None
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                    os.fsync(fd)
                    nxt = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = nxt
            for part in parts[:-1]:
                try:
                    nxt = os.open(part, flags, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise MediaParentUnavailable('MEDIA_PARENT_UNAVAILABLE') from None
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                    os.fsync(fd)
                    nxt = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = nxt
            yield fd, parts[-1]
        finally:
            os.close(fd)

    @staticmethod
    def regular(fd):
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError('MEDIA_REGULAR_UNSHARED_FILE_REQUIRED')
        return info

    def write_new(self, key, chunks):
        """Trusted producers supply chunks; no MIME/type acceptance is implied."""
        digest, size = hashlib.sha256(), 0
        if isinstance(chunks, bytes):
            chunks = [chunks]
        with self.parent(key, create=True) as (parent, leaf):
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
            inode = os.fstat(fd).st_ino
            try:
                with os.fdopen(fd, 'wb') as output:
                    for chunk in chunks:
                        if not isinstance(chunk, bytes):
                            raise ValidationError('MEDIA_BYTES_REQUIRED')
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            except BaseException as primary:
                # Only our newly created inode may be removed on a write failure.
                try:
                    if os.stat(leaf, dir_fd=parent, follow_symlinks=False).st_ino == inode:
                        os.unlink(leaf, dir_fd=parent)
                        os.fsync(parent)
                    else:
                        primary.add_note('MEDIA_PARTIAL_WRITE_INODE_CHANGED')
                except FileNotFoundError:
                    pass
                except BaseException as cleanup:
                    primary.add_note('MEDIA_PARTIAL_WRITE_CLEANUP_FAILED:' + type(cleanup).__name__)
                raise
            os.fsync(parent)
        return {'sha256': digest.hexdigest(), 'byte_size': size}

    def manifest(self, key):
        with self.parent(key) as (parent, leaf):
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, 'rb') as source:
                before = self.regular(source.fileno())
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
                after = self.regular(source.fileno())
                if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                    raise ValidationError('MEDIA_FILE_CHANGED_DURING_READ')
                return {'sha256': digest, 'byte_size': after.st_size}

    def open_verified(self, key, expected):
        """Pinned owner-preview stream; caller/FileResponse owns its lifetime."""
        with self.parent(key) as (parent,leaf):
            fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=parent)
            source=os.fdopen(fd,'rb')
            try:
                before=self.regular(source.fileno())
                actual={'sha256':hashlib.file_digest(source,'sha256').hexdigest(),'byte_size':before.st_size}
                after=self.regular(source.fileno())
                if actual!=expected or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
                    raise ValidationError('MEDIA_PREVIEW_CHANGED')
                source.seek(0)
                return source
            except BaseException:
                source.close();raise

    def unlink(self, key, expected):
        with self.parent(key) as (parent, leaf):
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, 'rb') as source:
                before = self.regular(source.fileno())
                actual = {'sha256': hashlib.file_digest(source, 'sha256').hexdigest(), 'byte_size': before.st_size}
                after = self.regular(source.fileno())
                current = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                if actual != expected or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns) or current.st_ino != before.st_ino:
                    raise ValidationError('MEDIA_DELETE_MANIFEST_CHANGED')
                os.unlink(leaf, dir_fd=parent)
                os.fsync(parent)
                return before.st_size
