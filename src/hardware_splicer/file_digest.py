"""SHA-256 of a file, remembered while the file is unchanged.

Digital study reads re-verify every artifact against its sealed hash. The check itself never
changes: a file's bytes must hash to the sealed value. What this module avoids is re-reading
bytes that cannot have changed. An entry is keyed by the file's path, device, inode, size,
modification time and status-change time, so any write, truncate, replace or rename-over gives a
new key and a fresh hash. As in git's index ("racy git"), a file whose timestamps are within
``RACY_WINDOW_NS`` of the moment it was hashed is never remembered, because a filesystem with
coarse timestamps could let a second write inside the same tick keep the same times.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path

RACY_WINDOW_NS = 2_000_000_000
CAPACITY = 8192

_entries: OrderedDict[tuple, str] = OrderedDict()
_lock = threading.Lock()


def _key(path: str, stat: os.stat_result) -> tuple:
    return (path, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def sha256_file(path: str | os.PathLike) -> str:
    """Hex SHA-256 of the file's bytes; raises OSError as ``Path.read_bytes`` would."""
    name = os.path.abspath(os.fspath(path))
    before = os.stat(name)
    key = _key(name, before)
    with _lock:
        cached = _entries.get(key)
        if cached is not None:
            _entries.move_to_end(key)
            return cached
    data = Path(name).read_bytes()
    value = hashlib.sha256(data).hexdigest()
    after = os.stat(name)
    settled = time.time_ns() - max(after.st_mtime_ns, after.st_ctime_ns) >= RACY_WINDOW_NS
    # Remember the hash only when the file did not change while it was read, and is not racy.
    if settled and _key(name, after) == key:
        with _lock:
            _entries[key] = value
            _entries.move_to_end(key)
            while len(_entries) > CAPACITY:
                _entries.popitem(last=False)
    return value


def clear() -> None:
    with _lock:
        _entries.clear()
