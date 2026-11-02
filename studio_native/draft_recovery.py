"""Crash-recovery journal for unsaved source drafts (not a source authority).

A recovery record is never published as Python. It is only offered to the user,
then copied into the existing revisioned SourceDocumentSession after an exact
source preimage check. Separate random record IDs avoid process-to-process
journal overwrites. There is deliberately no automatic merge or recovery.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from uuid import uuid4

VERSION = 1
MAX_RECORD_BYTES = 4 * 1024 * 1024
_TOKEN = re.compile(r'[0-9a-f]{32}\Z')


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def default_recovery_dir() -> Path:
    explicit = os.environ.get('SMI_RECOVERY_DIR')
    if explicit:
        return Path(explicit).expanduser().absolute()
    base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
    return (base / 'superior-mi-studio' / 'recovery').expanduser().absolute()


@dataclass(frozen=True)
class RecoveryRecord:
    path: Path
    base_sha256: str
    text: str
    revision: int
    token: str
    created_at: float


class DraftRecoveryStore:
    """Best-effort durable snapshots; never overwrites or executes project files."""

    def __init__(self, root: Path | None = None):
        self.root = (root if root is not None else default_recovery_dir()).expanduser().absolute()

    def _root(self, *, create: bool) -> bool:
        if create:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            info = self.root.lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise OSError('Recovery directory is not a real directory')
        if info.st_mode & 0o077:
            raise OSError('Recovery directory permits access to other users')
        return True

    @staticmethod
    def _identity(path: str | Path) -> Path:
        result = Path(path).expanduser().absolute()
        if not result.is_absolute():
            raise ValueError('Expected absolute source document path')
        return result

    def _record_path(self, path: Path, token: str) -> Path:
        if not _TOKEN.fullmatch(token):
            raise ValueError('Invalid recovery record identifier')
        return self.root / (hashlib.sha256(os.fsencode(path)).hexdigest() + '-' + token + '.json')

    def write(self, path: str | Path, base: bytes, text: str, revision: int, *, token: str) -> None:
        identity = self._identity(path)
        if not isinstance(text, str) or not isinstance(revision, int) or revision < 0:
            raise ValueError('Invalid draft snapshot')
        destination = self._record_path(identity, token)
        record = {
            'format': 'smi.source-recovery', 'version': VERSION,
            'path': str(identity), 'base_sha256': _digest(base),
            'text': text, 'text_sha256': _digest(text.encode('utf-8')),
            'revision': revision, 'token': token,
            'created_at': time.time(),
        }
        data = json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(data) > MAX_RECORD_BYTES:
            raise ValueError('Source recovery snapshot exceeds size limit')
        self._root(create=True)
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=self.root)
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            temporary = None
            # Record rename durability, not just data durability.
            # Some platforms cannot open/fsync a directory. The file itself
            # is already synced; use directory sync where the OS supports it.
            try:
                folder = os.open(self.root, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            except OSError:
                folder = None
            if folder is not None:
                try:
                    os.fsync(folder)
                except OSError:
                    pass
                finally:
                    os.close(folder)
        finally:
            if temporary is not None:
                try: os.unlink(temporary)
                except FileNotFoundError: pass

    def _read(self, filename: Path, expected_path: Path) -> RecoveryRecord | None:
        try:
            fd = os.open(filename, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RECORD_BYTES:
                    return None
                raw = stream.read(MAX_RECORD_BYTES + 1)
            if len(raw) > MAX_RECORD_BYTES:
                return None
            data = json.loads(raw.decode('utf-8'))
            if (not isinstance(data, dict) or data.get('format') != 'smi.source-recovery'
                    or type(data.get('version')) is not int or data['version'] != VERSION
                    or data.get('path') != str(expected_path)
                    or not isinstance(data.get('text'), str)
                    or data.get('text_sha256') != _digest(data['text'].encode('utf-8'))
                    or type(data.get('revision')) is not int or data['revision'] < 0
                    or not isinstance(data.get('base_sha256'), str)
                    or not re.fullmatch('[0-9a-f]{64}', data['base_sha256'])
                    or not isinstance(data.get('created_at'), (int, float))):
                return None
            token = data.get('token')
            if not isinstance(token, str) or filename != self._record_path(expected_path, token):
                return None
            return RecoveryRecord(expected_path, data['base_sha256'], data['text'],
                                  data['revision'], token, data['created_at'])
        except (OSError, ValueError, UnicodeError, TypeError, KeyError, OverflowError):
            # Corrupt/incomplete records remain untouched for manual inspection.
            return None

    def latest(self, path: str | Path) -> RecoveryRecord | None:
        identity = self._identity(path)
        if not self._root(create=False):
            return None
        prefix = hashlib.sha256(os.fsencode(identity)).hexdigest()
        records = []
        for candidate in self.root.glob(prefix + '-*.json'):
            record = self._read(candidate, identity)
            if record is not None:
                records.append(record)
        return max(records, key=lambda record: (record.created_at, record.token), default=None)

    def discard(self, path: str | Path, token: str) -> None:
        if not self._root(create=False):
            return
        filename = self._record_path(self._identity(path), token)
        try:
            filename.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def new_token() -> str:
        return uuid4().hex
