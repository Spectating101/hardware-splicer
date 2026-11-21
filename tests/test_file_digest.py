import hashlib
import os
import time
from pathlib import Path

import pytest

from hardware_splicer import file_digest


@pytest.fixture(autouse=True)
def _fresh_cache():
    file_digest.clear()
    yield
    file_digest.clear()


def _age(path: Path, seconds: int = 3600) -> None:
    # Old modification time; the status-change time is still "now", so tests that want a cache
    # hit also shrink the racy window.
    stamp = os.stat(path).st_mtime_ns - seconds * 1_000_000_000
    os.utime(path, ns=(stamp, stamp))


def _count_reads(monkeypatch):
    reads = []
    original = Path.read_bytes

    def counting(self):
        reads.append(self)
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    return reads


def test_matches_hashlib(tmp_path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"fielddeck")
    assert file_digest.sha256_file(target) == hashlib.sha256(b"fielddeck").hexdigest()


def test_settled_file_is_read_once(tmp_path, monkeypatch):
    monkeypatch.setattr(file_digest, "RACY_WINDOW_NS", 0)
    target = tmp_path / "a.bin"
    target.write_bytes(b"one")
    reads = _count_reads(monkeypatch)
    first = file_digest.sha256_file(target)
    assert file_digest.sha256_file(target) == first
    assert len(reads) == 1


def test_any_rewrite_is_rehashed_even_with_the_same_size_and_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(file_digest, "RACY_WINDOW_NS", 0)
    target = tmp_path / "a.bin"
    target.write_bytes(b"one")
    _age(target)
    before = os.stat(target)
    assert file_digest.sha256_file(target) == hashlib.sha256(b"one").hexdigest()
    # In use, a remembered hash is at least RACY_WINDOW_NS past its file's last change; here the
    # window is 0, so step past one coarse kernel timestamp tick (≤ 10 ms) before rewriting.
    time.sleep(0.05)
    target.write_bytes(b"two")  # same size
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))  # forged mtime; ctime still moves
    assert file_digest.sha256_file(target) == hashlib.sha256(b"two").hexdigest()


def test_replacement_by_rename_is_rehashed(tmp_path, monkeypatch):
    monkeypatch.setattr(file_digest, "RACY_WINDOW_NS", 0)
    target = tmp_path / "a.bin"
    target.write_bytes(b"one")
    file_digest.sha256_file(target)
    other = tmp_path / "b.bin"
    other.write_bytes(b"two")
    os.replace(other, target)
    assert file_digest.sha256_file(target) == hashlib.sha256(b"two").hexdigest()


def test_racy_files_are_never_remembered(tmp_path, monkeypatch):
    target = tmp_path / "a.bin"
    target.write_bytes(b"one")
    reads = _count_reads(monkeypatch)
    file_digest.sha256_file(target)
    file_digest.sha256_file(target)
    assert len(reads) == 2


def test_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        file_digest.sha256_file(tmp_path / "missing.bin")
