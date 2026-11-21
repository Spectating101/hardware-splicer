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
    original = os.read

    def counting(fd, n):
        data = original(fd, n)
        if data:
            reads.append(fd)
        return data

    monkeypatch.setattr(file_digest.os, "read", counting)
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


def test_the_racy_window_counts_from_when_the_read_started(tmp_path, monkeypatch):
    # The clock jumps 60 s once a read has happened. Timing taken before the read sees a fresh file
    # and does not remember it; timing taken after the read (the old code) would.
    target = tmp_path / "a.bin"
    target.write_bytes(b"one")
    reads = _count_reads(monkeypatch)
    real = file_digest.time.time_ns
    monkeypatch.setattr(file_digest.time, "time_ns", lambda: real() + (60_000_000_000 if reads else 0))
    file_digest.sha256_file(target)
    assert len(reads) == 1
    file_digest.sha256_file(target)
    assert len(reads) == 2  # not remembered: it was fresh when the first read started


def test_a_path_swapped_mid_read_never_pairs_bytes_with_another_files_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(file_digest, "RACY_WINDOW_NS", 0)
    target, other = tmp_path / "a.bin", tmp_path / "b.bin"
    target.write_bytes(b"original")
    other.write_bytes(b"replaced")
    original_read = os.read
    swapped = []

    def read_then_swap(fd, n):
        data = original_read(fd, n)
        if data and not swapped:
            os.replace(other, target)  # the path now names a different file
            swapped.append(True)
        return data

    monkeypatch.setattr(file_digest.os, "read", read_then_swap)
    # The open file is still the original: its bytes and its identity agree.
    assert file_digest.sha256_file(target) == hashlib.sha256(b"original").hexdigest()
    monkeypatch.setattr(file_digest.os, "read", original_read)
    # The path's new file has a new identity, so it is hashed, not served from the cache.
    assert file_digest.sha256_file(target) == hashlib.sha256(b"replaced").hexdigest()


def test_bytes_that_text_mode_would_change_hash_exactly(tmp_path):
    target = tmp_path / "a.png"
    data = b"\x89PNG\r\n\x1a\nrest\r\nmore\x1a"
    target.write_bytes(data)
    assert file_digest.sha256_file(target) == hashlib.sha256(data).hexdigest()


def test_a_retargeted_symlink_hashes_the_new_target(tmp_path, monkeypatch):
    monkeypatch.setattr(file_digest, "RACY_WINDOW_NS", 0)
    first, second, link = tmp_path / "first.bin", tmp_path / "second.bin", tmp_path / "link.bin"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    link.symlink_to(first)
    assert file_digest.sha256_file(link) == hashlib.sha256(b"one").hexdigest()
    link.unlink()
    link.symlink_to(second)
    assert file_digest.sha256_file(link) == hashlib.sha256(b"two").hexdigest()


def test_a_directory_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        file_digest.sha256_file(tmp_path)
