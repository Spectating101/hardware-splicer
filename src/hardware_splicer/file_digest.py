"""SHA-256 of a file, remembered while the file is unchanged.

Digital study reads re-verify every artifact against its sealed hash. The check itself never
changes: a file's bytes must hash to the sealed value. What this module avoids is re-reading
bytes that cannot have changed.

How an entry stays honest:
- The file is opened once; its identity (device, inode, size, mtime, ctime) is taken from that open
  file before and after the read, and the bytes come from the same open file. Renaming or swapping
  the path, its directories or a symlink mid-read cannot pair one file's bytes with another's
  identity, and a path that later names a different file gives a new key.
- An entry is remembered only when the file did not change during the read, and when its last change
  was at least ``RACY_WINDOW_NS`` before the read *started* (git's racy-index rule). A filesystem with
  coarse timestamps could let a second write inside the same tick keep the same times; such a write
  could only have happened before the read began, so the bytes read already include it. The window
  must exceed the filesystem's timestamp granularity (2 s on FAT, sub-second on ext4, xfs, btrfs, tmpfs).

Known limits, by design: writes through a shared memory map that do not update mtime/ctime, and a
wall clock stepped backwards onto an earlier file timestamp, are not detected until the file is
otherwise modified or the process restarts. Windows reports creation time as ctime. Anyone who can
write study files can also rewrite the seal beside them, so this guards against accidental change,
not against a writer on the host.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict

RACY_WINDOW_NS = 3_000_000_000
CAPACITY = 8192
_CHUNK = 1 << 20

_entries: OrderedDict[tuple, str] = OrderedDict()
_lock = threading.Lock()


def _key(path: str, stat: os.stat_result) -> tuple:
    return (path, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def sha256_file(path: str | os.PathLike) -> str:
    """Hex SHA-256 of the file's bytes; raises OSError as reading the file would."""
    name = os.path.abspath(os.fspath(path))
    started = time.time_ns()
    # O_BINARY: on Windows a plain os.open is text mode, which rewrites CRLF and stops at 0x1A.
    fd = os.open(name, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        before = os.fstat(fd)
        key = _key(name, before)
        with _lock:
            cached = _entries.get(key)
            if cached is not None:
                _entries.move_to_end(key)
                return cached
        digest = hashlib.sha256()
        while chunk := os.read(fd, _CHUNK):
            digest.update(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    value = digest.hexdigest()
    settled = started - max(after.st_mtime_ns, after.st_ctime_ns) >= RACY_WINDOW_NS
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
