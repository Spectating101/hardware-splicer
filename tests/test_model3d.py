from __future__ import annotations

import hashlib
import os
import stat
import struct
import subprocess
import threading
import time
from pathlib import Path

import pytest

from hardware_splicer.bounded_process import BoundedProcessError, BoundedProcessResult

from hardware_splicer.model3d import (
    DEFAULT_MAX_BYTES,
    ERROR_OUTPUT_LIMIT,
    LOCK_TABLE_MAX,
    Model3DError,
    Model3DUnavailable,
    _GENERATE_LOCKS,
    _lock_for,
    _run_kicad_cli,
    _try_read_cache,
    capability_probe,
    generate_glb,
    load_or_build_cached_glb,
    model_cache_paths,
    options_fingerprint,
)
from hardware_splicer.project_store import ProjectStore

REPO = Path(__file__).resolve().parents[1]
PCB = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1" / "spi_flash_adapter_v1.kicad_pcb"


@pytest.fixture(autouse=True)
def isolated_capability_cache(monkeypatch):
    monkeypatch.setattr("hardware_splicer.model3d._PROBE_CACHE", None)


def _require_kicad() -> None:
    probe = capability_probe()
    if not probe["available"]:
        pytest.skip(probe["reason"] or "kicad-cli missing")


def _pcb_text() -> str:
    return PCB.read_text(encoding="utf-8")


def _pcb_hex(text: str | None = None) -> str:
    payload = (text if text is not None else _pcb_text()).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _minimal_glb(*, size: int = 16) -> bytes:
    if size < 12:
        return b"\x00" * size
    return b"glTF" + struct.pack("<II", 2, size) + (b"\x00" * (size - 12))


def _validate_header(data: bytes) -> None:
    assert data[:4] == b"glTF"
    version, length = struct.unpack_from("<II", data, 4)
    assert version == 2
    assert length == len(data)


def _cache_files(store: ProjectStore, project_id: str = "robot") -> list[Path]:
    root = store.root / project_id / "models"
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


def _runner_from(handler):
    """Fake for model3d's bounded runner. ``handler(cmd, timeout)`` behaves as the tests always wrote it."""

    def fake_run_bounded(cmd, *, timeout_s, cwd=None, env=None, tail_bytes=8192):
        if "--version" in cmd:
            return BoundedProcessResult(0, b"9.0.2\n", b"", False)
        try:
            result = handler(list(cmd), timeout_s)
        except subprocess.TimeoutExpired:
            raise BoundedProcessError(f"timed out after {timeout_s}s", timed_out=True) from None
        if result is None:
            result = subprocess.CompletedProcess(list(cmd), 0, b"", b"")
        return BoundedProcessResult(int(result.returncode), result.stdout or b"", result.stderr or b"", False)

    return fake_run_bounded


def _install_popen(monkeypatch: pytest.MonkeyPatch, handler):
    # Fake runner tests must not depend on a real CLI being installed.
    monkeypatch.setattr("hardware_splicer.model3d.resolve_kicad_cli", lambda: "fixture-kicad-cli")
    monkeypatch.setattr("hardware_splicer.model3d.run_bounded", _runner_from(handler))


def _write_output(cmd: list[str], data: bytes) -> None:
    output = Path(cmd[cmd.index("--output") + 1])
    output.write_bytes(data)


def _chmod_exec(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def test_real_reference_pcb_is_valid_glb() -> None:
    _require_kicad()
    data = generate_glb(_pcb_text())
    _validate_header(data)
    assert len(data) < DEFAULT_MAX_BYTES


def test_same_input_same_sha(tmp_path: Path) -> None:
    _require_kicad()
    store = ProjectStore(tmp_path)
    text = _pcb_text()
    pcb_hex = _pcb_hex(text)
    first = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    second = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    assert first["sha256"] == second["sha256"]
    assert first["bytes"] == second["bytes"]
    assert hashlib.sha256(first["bytes"]).hexdigest() == first["sha256"].split(":", 1)[1]


def test_fake_runner_same_input_same_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(cmd: list[str], _timeout) -> subprocess.CompletedProcess[bytes]:
        _write_output(cmd, _minimal_glb(size=24))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    _install_popen(monkeypatch, handler)
    text = "(kicad_pcb (version 20240108) (layers))\n"
    first = hashlib.sha256(generate_glb(text)).hexdigest()
    second = hashlib.sha256(generate_glb(text)).hexdigest()
    assert first == second


def test_cached_second_call_does_not_spawn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _require_kicad()
    capability_probe()
    store = ProjectStore(tmp_path)
    text = _pcb_text()
    pcb_hex = _pcb_hex(text)
    first = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    calls: list[list[str]] = []
    real = subprocess.Popen

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "export" in cmd and "glb" in cmd:
            calls.append(list(cmd))
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr("hardware_splicer.model3d.subprocess.Popen", spy)
    second = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    assert calls == []
    assert second["sha256"] == first["sha256"]
    assert second["bytes"] == first["bytes"]


@pytest.mark.parametrize(
    "kind",
    ["nonzero", "timeout", "truncated", "garbage", "oversize", "empty"],
)
def test_fake_runner_errors_are_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    store = ProjectStore(tmp_path)
    text = "(kicad_pcb (version 20240108) (layers))\n"
    pcb_hex = _pcb_hex(text)

    def handler(cmd: list[str], timeout) -> subprocess.CompletedProcess[bytes]:
        if kind == "nonzero":
            return subprocess.CompletedProcess(cmd, 3, b"", b"export failed")
        if kind == "timeout":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout or 1)
        if kind == "truncated":
            _write_output(cmd, b"glTF" + struct.pack("<II", 2, 1000) + b"\x00" * 8)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        if kind == "garbage":
            _write_output(cmd, b"not-a-glb-file!!!!")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        if kind == "oversize":
            _write_output(cmd, _minimal_glb(size=200))
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        _write_output(cmd, b"")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    _install_popen(monkeypatch, handler)
    max_bytes = 50 if kind == "oversize" else DEFAULT_MAX_BYTES
    with pytest.raises(Model3DError):
        generate_glb(text, max_bytes=max_bytes)
    with pytest.raises(Model3DError):
        load_or_build_cached_glb(store, "robot", text, pcb_hex, max_bytes=max_bytes)
    assert _cache_files(store) == []


def test_missing_kicad_cli_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-model3d-path")
    with pytest.raises(Model3DUnavailable):
        generate_glb("(kicad_pcb)")
    probe = capability_probe()
    assert probe["available"] is False
    assert probe["reason"]


def test_tampered_cache_is_regenerated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ProjectStore(tmp_path)
    text = "(kicad_pcb (version 20240108) (layers))\n"
    pcb_hex = _pcb_hex(text)
    writes = {"n": 0}

    def handler(cmd: list[str], _timeout) -> subprocess.CompletedProcess[bytes]:
        writes["n"] += 1
        _write_output(cmd, _minimal_glb(size=20 + writes["n"]))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    _install_popen(monkeypatch, handler)
    first = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    glb_path, _sidecar = model_cache_paths(store, "robot", pcb_hex)
    glb_path.write_bytes(glb_path.read_bytes() + b"tamper")
    second = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    assert writes["n"] == 2
    assert second["sha256"] != first["sha256"]
    assert hashlib.sha256(second["bytes"]).hexdigest() == second["sha256"].split(":", 1)[1]


def test_symlinked_cache_path_is_not_followed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ProjectStore(tmp_path)
    text = "(kicad_pcb (version 20240108) (layers))\n"
    pcb_hex = _pcb_hex(text)
    glb_path, sidecar = model_cache_paths(store, "robot", pcb_hex)
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = glb_path.parent / "dummy-target.glb"
    dummy.write_bytes(_minimal_glb())
    glb_path.symlink_to(dummy)
    sidecar.write_text('{"sha256":"sha256:' + "ab" * 32 + '"}\n', encoding="utf-8")

    def handler(cmd: list[str], _timeout) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError(f"kicad-cli should not run for a symlinked cache: {cmd}")

    _install_popen(monkeypatch, handler)
    with pytest.raises(Model3DError, match="symlink"):
        load_or_build_cached_glb(store, "robot", text, pcb_hex)
    assert glb_path.is_symlink()
    assert dummy.read_bytes() == _minimal_glb()


def test_concurrent_generation_spawns_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ProjectStore(tmp_path)
    text = "(kicad_pcb (version 20240108) (layers))\n"
    pcb_hex = _pcb_hex(text)
    started = threading.Event()
    release = threading.Event()
    calls: list[int] = []

    def handler(cmd: list[str], _timeout) -> subprocess.CompletedProcess[bytes]:
        if "export" not in cmd:
            return subprocess.CompletedProcess(cmd, 0, b"9.0.2\n", b"")
        calls.append(1)
        started.set()
        release.wait(2.0)
        _write_output(cmd, _minimal_glb())
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    _install_popen(monkeypatch, handler)
    results: list[str] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            built = load_or_build_cached_glb(store, "robot", text, pcb_hex)
            results.append(built["sha256"])
        except BaseException as exc:  # noqa: BLE001 — collect for the main thread
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    assert started.wait(2.0)
    release.set()
    for thread in threads:
        thread.join(2.0)
    assert errors == []
    assert calls == [1]
    assert len(set(results)) == 1
    assert options_fingerprint()


def test_timeout_kills_process_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent_pid = tmp_path / "parent.pid"
    child_pid = tmp_path / "child.pid"
    script = tmp_path / "fake-kicad-cli"
    script.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'if [ "${1:-}" = "--version" ]; then echo "9.0.2"; exit 0; fi\n'
        "sleep 30 &\n"
        f'echo $! > "{child_pid}"\n'
        f'echo $$ > "{parent_pid}"\n'
        "sleep 30\n",
        encoding="utf-8",
    )
    _chmod_exec(script)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(script))
    with pytest.raises(Model3DError, match="timed out"):
        generate_glb("(kicad_pcb (version 20240108) (layers))\n", timeout_s=0.6)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not (parent_pid.is_file() and child_pid.is_file()):
        time.sleep(0.05)
    parent = int(parent_pid.read_text(encoding="utf-8").strip())
    child = int(child_pid.read_text(encoding="utf-8").strip())
    time.sleep(0.2)
    assert not _process_alive(parent)
    assert not _process_alive(child)


def test_run_returns_output_and_clips_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ok_script = tmp_path / "ok-kicad-cli"
    ok_script.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "--version" ]; then echo "9.0.2"; exit 0; fi\n'
        "echo stdout-ok\n"
        "echo stderr-ok >&2\n"
        "exit 0\n",
        encoding="utf-8",
    )
    _chmod_exec(ok_script)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(ok_script))
    completed = _run_kicad_cli([str(ok_script), "pcb", "export", "glb"], timeout_s=5.0, cwd=tmp_path, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path)})
    assert completed.returncode == 0
    assert b"stdout-ok" in completed.stdout
    assert b"stderr-ok" in completed.stderr

    fail_script = tmp_path / "fail-kicad-cli"
    fail_script.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "--version" ]; then echo "9.0.2"; exit 0; fi\n'
        "python3 -c 'import sys; sys.stderr.write(\"E\"*8000); sys.exit(7)'\n",
        encoding="utf-8",
    )
    _chmod_exec(fail_script)
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_CLI", str(fail_script))
    with pytest.raises(Model3DError) as excinfo:
        generate_glb("(kicad_pcb)\n", timeout_s=5.0)
    message = str(excinfo.value)
    assert "exited 7" in message
    assert len(message.encode("utf-8")) <= ERROR_OUTPUT_LIMIT + 80


def test_sidecar_install_failure_keeps_or_regenerates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ProjectStore(tmp_path)
    text = "(kicad_pcb (version 20240108) (layers))\n"
    pcb_hex = _pcb_hex(text)
    writes = {"n": 0}

    def handler(cmd: list[str], _timeout) -> subprocess.CompletedProcess[bytes]:
        writes["n"] += 1
        _write_output(cmd, _minimal_glb(size=20 + writes["n"]))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    _install_popen(monkeypatch, handler)
    first = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    glb_path, sidecar_path = model_cache_paths(store, "robot", pcb_hex)
    previous = _try_read_cache(glb_path, sidecar_path, max_bytes=DEFAULT_MAX_BYTES)
    assert previous is not None
    glb_path.write_bytes(glb_path.read_bytes() + b"tamper")

    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("sidecar install failed")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr("hardware_splicer.model3d.os.replace", flaky_replace)
    recovered = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    assert recovered["bytes"][:4] == b"glTF"
    assert hashlib.sha256(recovered["bytes"]).hexdigest() == recovered["sha256"].split(":", 1)[1]
    cached = _try_read_cache(glb_path, sidecar_path, max_bytes=DEFAULT_MAX_BYTES)
    assert cached is None or hashlib.sha256(cached["bytes"]).hexdigest() == cached["sha256"].split(":", 1)[1]
    monkeypatch.setattr("hardware_splicer.model3d.os.replace", real_replace)
    later = load_or_build_cached_glb(store, "robot", text, pcb_hex)
    assert later["sha256"] != first["sha256"] or later["bytes"] == first["bytes"]
    assert hashlib.sha256(later["bytes"]).hexdigest() == later["sha256"].split(":", 1)[1]


def test_concurrent_reader_sees_only_none_or_valid_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ProjectStore(tmp_path)
    text = "(kicad_pcb (version 20240108) (layers))\n"
    pcb_hex = _pcb_hex(text)
    writes = {"n": 0}

    def handler(cmd: list[str], _timeout) -> subprocess.CompletedProcess[bytes]:
        writes["n"] += 1
        _write_output(cmd, _minimal_glb(size=24 + writes["n"]))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    _install_popen(monkeypatch, handler)
    load_or_build_cached_glb(store, "robot", text, pcb_hex)
    glb_path, sidecar_path = model_cache_paths(store, "robot", pcb_hex)
    glb_path.write_bytes(glb_path.read_bytes() + b"tamper")

    real_replace = os.replace

    def slow_replace(src, dst, *args, **kwargs):
        time.sleep(0.04)
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr("hardware_splicer.model3d.os.replace", slow_replace)
    seen: list[str] = []
    stop = threading.Event()
    errors: list[BaseException] = []

    def reader() -> None:
        while not stop.is_set():
            try:
                row = _try_read_cache(glb_path, sidecar_path, max_bytes=DEFAULT_MAX_BYTES)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
                return
            if row is None:
                seen.append("none")
            else:
                digest = hashlib.sha256(row["bytes"]).hexdigest()
                assert digest == row["sha256"].split(":", 1)[1]
                _validate_header(row["bytes"])
                seen.append("valid")
            time.sleep(0.005)

    thread = threading.Thread(target=reader)
    thread.start()
    load_or_build_cached_glb(store, "robot", text, pcb_hex)
    stop.set()
    thread.join(2.0)
    assert errors == []
    assert seen
    assert set(seen) <= {"none", "valid"}


def test_lock_table_is_bounded_lru() -> None:
    _GENERATE_LOCKS.clear()
    try:
        for index in range(LOCK_TABLE_MAX + 40):
            _lock_for(f"key-{index}")
        assert len(_GENERATE_LOCKS) == LOCK_TABLE_MAX
        assert "key-0" not in _GENERATE_LOCKS
        assert f"key-{LOCK_TABLE_MAX + 39}" in _GENERATE_LOCKS
        oldest_kept = f"key-{40}"
        assert oldest_kept in _GENERATE_LOCKS
        _lock_for(oldest_kept)
        _lock_for("key-new")
        assert oldest_kept in _GENERATE_LOCKS
        assert "key-41" not in _GENERATE_LOCKS
        assert "key-new" in _GENERATE_LOCKS
        assert len(_GENERATE_LOCKS) == LOCK_TABLE_MAX
    finally:
        _GENERATE_LOCKS.clear()


def test_live_lock_not_evicted_when_table_grows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("hardware_splicer.model3d.LOCK_TABLE_MAX", 2)
    _GENERATE_LOCKS.clear()
    store = ProjectStore(tmp_path)
    texts = [f"(kicad_pcb (version 20240108) (layers) (key {index}))\n" for index in range(3)]
    hexes = [_pcb_hex(text) for text in texts]
    started = {digest: threading.Event() for digest in hexes}
    release = threading.Event()
    exports: dict[str, int] = {digest: 0 for digest in hexes}

    def handler(cmd: list[str], _timeout) -> subprocess.CompletedProcess[bytes]:
        if "export" not in cmd:
            return subprocess.CompletedProcess(cmd, 0, b"9.0.2\n", b"")
        pcb = Path(cmd[cmd.index("--output") + 1]).with_name("board.kicad_pcb")
        digest = hashlib.sha256(pcb.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        exports[digest] = exports.get(digest, 0) + 1
        started[digest].set()
        release.wait(5.0)
        _write_output(cmd, _minimal_glb(size=16 + exports[digest]))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    _install_popen(monkeypatch, handler)
    results: list[str] = []
    errors: list[BaseException] = []

    def worker(text: str, digest: str) -> None:
        try:
            built = load_or_build_cached_glb(store, "robot", text, digest)
            results.append(built["sha256"])
        except BaseException as exc:  # noqa: BLE001 — collect for the main thread
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(texts[i], hexes[i])) for i in range(3)]
    for thread in threads:
        thread.start()
    assert all(started[digest].wait(2.0) for digest in hexes)
    assert len(_GENERATE_LOCKS) == 3
    assert exports[hexes[0]] == 1

    extra = threading.Thread(target=worker, args=(texts[0], hexes[0]))
    extra.start()
    time.sleep(0.2)
    assert exports[hexes[0]] == 1
    assert extra.is_alive()

    release.set()
    extra.join(2.0)
    for thread in threads:
        thread.join(2.0)
    assert errors == []
    assert extra.is_alive() is False
    assert exports[hexes[0]] == 1
    assert len(_GENERATE_LOCKS) <= 2
    _GENERATE_LOCKS.clear()
