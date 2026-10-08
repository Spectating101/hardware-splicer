"""Server-side GLB views of retained PCB bytes.

A rendered model is a view of retained bytes. It carries no engineering
authority and never rewrites a snapshot, revision, pin, review, or thread.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import struct
import subprocess
import tempfile
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from .artifact_retention import (
    _is_symlink,
    _lexical_absolute,
    _read_regular_file,
)
from .bounded_process import BoundedProcessError, run_bounded
from .project_store import ProjectStore, validate_project_id

DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
ERROR_OUTPUT_LIMIT = 2048
PROBE_TTL_S = 60.0
SIDECAR_LIMIT = 16 * 1024
INSTALL_HINT = (
    "kicad-cli is not available; install KiCad 9 (provides kicad-cli) "
    "or set HARDWARE_SPLICER_KICAD_CLI to the binary"
)

# Defaults checked against `kicad-cli pcb export glb --help` (KiCad 9.0.2):
# --force, --subst-models, --include-tracks, --include-pads, --include-zones,
# --include-silkscreen, --include-soldermask. Origin/filter/board-only flags
# stay off so the view matches the retained board as KiCad exports it.
DEFAULT_GLB_FLAGS: tuple[str, ...] = (
    "--force",
    "--subst-models",
    "--include-tracks",
    "--include-pads",
    "--include-zones",
    "--include-silkscreen",
    "--include-soldermask",
)

LOCK_TABLE_MAX = 256

_PROBE_LOCK = threading.Lock()
_PROBE_CACHE: tuple[float, str, dict[str, Any]] | None = None
_GENERATE_LOCKS_GUARD = threading.Lock()


@dataclass
class _LockEntry:
    lock: threading.Lock
    refs: int = 0


_GENERATE_LOCKS: OrderedDict[str, _LockEntry] = OrderedDict()


class Model3DError(RuntimeError):
    """kicad-cli failed, timed out, or produced an invalid GLB."""


class Model3DUnavailable(RuntimeError):
    """kicad-cli is missing or not executable."""


# The bare board: outline, copper, pads, silkscreen and solder mask, with no component models. The build sequence draws its
# own stand-in parts on this, so a part's real model is never needed and never pretended.
BOARD_ONLY_GLB_FLAGS: tuple[str, ...] = ("--board-only",) + DEFAULT_GLB_FLAGS


def options_fingerprint(flags: tuple[str, ...] | None = None) -> str:
    """Eight-hex fingerprint of the export options (the documented defaults when none are given)."""

    payload = "\0".join(flags or DEFAULT_GLB_FLAGS).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:8]


def resolve_kicad_cli() -> str | None:
    raw = os.environ.get("HARDWARE_SPLICER_KICAD_CLI", "").strip()
    candidate = raw or shutil.which("kicad-cli")
    if not candidate:
        return None
    path = Path(candidate)
    if path.is_file() and os.access(path, os.X_OK):
        return str(path)
    found = shutil.which(candidate)
    return found


def _probe_cache_key() -> str:
    return f"{os.environ.get('HARDWARE_SPLICER_KICAD_CLI', '')}\0{os.environ.get('PATH', '')}"


def _clip_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace")
    else:
        text = data
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) > ERROR_OUTPUT_LIMIT:
        text = encoded[:ERROR_OUTPUT_LIMIT].decode("utf-8", errors="replace")
    return text


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _reap_process(proc: subprocess.Popen[bytes]) -> tuple[bytes, bytes]:
    try:
        stdout, stderr = proc.communicate()
    except Exception:
        try:
            proc.wait()
        except Exception:
            pass
        return b"", b""
    return stdout or b"", stderr or b""


def _run_kicad_cli(
    cmd: list[str],
    *,
    timeout_s: float,
    cwd: Path | None,
    env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[bytes]:
    """Run kicad-cli on the shared bounded runner: capped output, and the whole process group is killed afterwards."""

    try:
        result = run_bounded(cmd, timeout_s=timeout_s, cwd=cwd, env=env, tail_bytes=ERROR_OUTPUT_LIMIT)
    except BoundedProcessError as exc:
        if exc.timed_out:
            raise Model3DError(f"kicad-cli timed out after {timeout_s}s") from None
        raise Model3DUnavailable(INSTALL_HINT) from exc
    return subprocess.CompletedProcess(cmd, result.returncode, result.stdout_tail, result.stderr_tail)


def capability_probe() -> dict[str, Any]:
    """Return ``{available, version, reason}``. Caches one ``--version`` for 60s."""

    global _PROBE_CACHE
    now = time.monotonic()
    key = _probe_cache_key()
    with _PROBE_LOCK:
        cached = _PROBE_CACHE
        if cached is not None and cached[1] == key and now - cached[0] < PROBE_TTL_S:
            return dict(cached[2])
        result = _probe_uncached()
        _PROBE_CACHE = (now, key, result)
        return dict(result)


def _probe_uncached() -> dict[str, Any]:
    binary = resolve_kicad_cli()
    if not binary:
        return {"available": False, "version": None, "reason": INSTALL_HINT}
    try:
        completed = _run_kicad_cli(
            [binary, "--version"],
            timeout_s=10.0,
            cwd=None,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tempfile.gettempdir()},
        )
    except Model3DUnavailable:
        return {"available": False, "version": None, "reason": INSTALL_HINT}
    except Model3DError as exc:
        return {"available": False, "version": None, "reason": str(exc)}
    if completed.returncode != 0:
        return {
            "available": False,
            "version": None,
            "reason": f"kicad-cli --version failed: {_clip_output(completed.stderr) or _clip_output(completed.stdout) or completed.returncode}",
        }
    version = _clip_output(completed.stdout).splitlines()[0].strip() if completed.stdout else ""
    if not version:
        version = _clip_output(completed.stderr).splitlines()[0].strip() if completed.stderr else ""
    if not version:
        return {"available": False, "version": None, "reason": "kicad-cli --version produced no version"}
    return {"available": True, "version": version, "reason": None}


def _validate_glb(data: bytes, *, max_bytes: int) -> None:
    if not data:
        raise Model3DError("kicad-cli produced an empty GLB")
    if len(data) > max_bytes:
        raise Model3DError(f"GLB exceeds size limit ({len(data)} bytes; limit {max_bytes})")
    if len(data) < 12 or data[:4] != b"glTF":
        raise Model3DError("kicad-cli produced a GLB that is not a version-2 glTF binary")
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise Model3DError("kicad-cli produced a GLB that is not a version-2 glTF binary")
    if length != len(data):
        raise Model3DError("GLB header length does not match file size")


def generate_glb(
    pcb_text: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_BYTES,
    flags: tuple[str, ...] | None = None,
) -> bytes:
    """Export a GLB from PCB text via ``kicad-cli pcb export glb``.

    Writes ``board.kicad_pcb`` into a mode-700 temp directory, runs kicad-cli
    with PATH-only + HOME=temp so KiCad does not write the user home, and
    validates the GLB magic, version 2, and header length.
    """

    binary = resolve_kicad_cli()
    if not binary:
        raise Model3DUnavailable(INSTALL_HINT)
    work = Path(tempfile.mkdtemp(prefix="hs_model3d_"))
    os.chmod(work, 0o700)
    try:
        pcb_path = work / "board.kicad_pcb"
        glb_path = work / "board.glb"
        pcb_path.write_text(pcb_text, encoding="utf-8")
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(work),
        }
        completed = _run_kicad_cli(
            [
                binary,
                "pcb",
                "export",
                "glb",
                "--output",
                str(glb_path),
                *(flags or DEFAULT_GLB_FLAGS),
                "board.kicad_pcb",
            ],
            timeout_s=timeout_s,
            cwd=work,
            env=env,
        )
        if completed.returncode != 0:
            raise Model3DError(
                f"kicad-cli exited {completed.returncode}: "
                f"{_clip_output(completed.stderr) or _clip_output(completed.stdout) or 'no output'}"
            )
        if _is_symlink(glb_path) or not glb_path.is_file():
            raise Model3DError("kicad-cli produced no GLB output")
        try:
            data = _read_regular_file(glb_path, limit=max_bytes)
        except ValueError as exc:
            raise Model3DError(str(exc)) from exc
        _validate_glb(data, max_bytes=max_bytes)
        return data
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _project_dir(store: ProjectStore, project_id: str) -> Path:
    return store._project_dir(validate_project_id(project_id))


def model_cache_paths(store: ProjectStore, project_id: str, pcb_hex: str, flags: tuple[str, ...] | None = None) -> tuple[Path, Path]:
    safe_hex = pcb_hex.lower()
    optfp = options_fingerprint(flags)
    target = _project_dir(store, project_id) / "models" / safe_hex[:2] / f"{safe_hex}-{optfp}.glb"
    return target, target.with_suffix(".json")


def _assert_cache_not_symlinked(*paths: Path) -> None:
    roots = [_lexical_absolute(path) for path in paths]
    seen: set[Path] = set()
    for lexical in roots:
        current = lexical
        while True:
            if current in seen:
                break
            seen.add(current)
            if _is_symlink(current):
                raise Model3DError("model cache path is a symlink")
            if current.parent == current:
                break
            name = current.name
            current = current.parent
            if name == "models":
                break


def _sidecar_payload(data: bytes, *, generated_with: str) -> bytes:
    body = {
        "sha256": f"sha256:{hashlib.sha256(data).hexdigest()}",
        "size_bytes": len(data),
        "format": "glb",
        "generated_with": generated_with,
    }
    return (json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _try_read_cache(glb_path: Path, sidecar_path: Path, *, max_bytes: int) -> dict[str, Any] | None:
    if _is_symlink(glb_path) or _is_symlink(sidecar_path):
        raise Model3DError("model cache path is a symlink")
    if not glb_path.is_file() or not sidecar_path.is_file():
        return None
    try:
        data = _read_regular_file(glb_path, limit=max_bytes)
        raw = _read_regular_file(sidecar_path, limit=SIDECAR_LIMIT)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    digest = payload.get("sha256")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return None
    expected = digest.split(":", 1)[1]
    if hashlib.sha256(data).hexdigest() != expected:
        return None
    try:
        _validate_glb(data, max_bytes=max_bytes)
    except Model3DError:
        return None
    generated_with = payload.get("generated_with")
    if not isinstance(generated_with, str) or not generated_with:
        generated_with = "kicad-cli"
    return {
        "bytes": data,
        "sha256": digest,
        "size_bytes": len(data),
        "generated_with": generated_with,
    }


def _install_bytes(target: Path, content: bytes) -> None:
    """Write ``content`` via mkstemp+fsync and install with ``os.replace``. Never delete first."""

    _assert_cache_not_symlinked(target, target.parent)
    if _is_symlink(target):
        raise Model3DError("model cache path is a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    if _is_symlink(target.parent):
        raise Model3DError("model cache path is a symlink")
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if _is_symlink(target) or _is_symlink(target.parent):
            raise Model3DError("model cache path is a symlink")
        os.replace(os.fspath(temp_path), os.fspath(target))
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _replace_cache(glb_path: Path, sidecar_path: Path, data: bytes, *, generated_with: str) -> None:
    _assert_cache_not_symlinked(glb_path, sidecar_path, glb_path.parent)
    _install_bytes(glb_path, data)
    _install_bytes(sidecar_path, _sidecar_payload(data, generated_with=generated_with))


def _memory_model(data: bytes, *, pcb_hex: str, generated_with: str) -> dict[str, Any]:
    return {
        "bytes": data,
        "sha256": f"sha256:{hashlib.sha256(data).hexdigest()}",
        "size_bytes": len(data),
        "generated_with": generated_with,
        "pcb_sha256": f"sha256:{pcb_hex}",
    }


def _entry_in_use(entry: _LockEntry) -> bool:
    return entry.refs > 0 or entry.lock.locked()


def _evict_idle() -> None:
    """Drop oldest idle entries until at or under the soft cap.

    Live locks (refcount > 0 or currently held) are never evicted. If every
    entry is in use the table grows past ``LOCK_TABLE_MAX``.
    """

    overflow = len(_GENERATE_LOCKS) - LOCK_TABLE_MAX
    if overflow <= 0:
        return
    for key, entry in list(_GENERATE_LOCKS.items()):
        if overflow <= 0:
            return
        if _entry_in_use(entry):
            continue
        _GENERATE_LOCKS.pop(key, None)
        overflow -= 1


def _pin_lock(key: str) -> threading.Lock:
    with _GENERATE_LOCKS_GUARD:
        entry = _GENERATE_LOCKS.get(key)
        if entry is None:
            entry = _LockEntry(lock=threading.Lock())
            _GENERATE_LOCKS[key] = entry
        entry.refs += 1
        _GENERATE_LOCKS.move_to_end(key)
        _evict_idle()
        return entry.lock


def _unpin_lock(key: str) -> None:
    with _GENERATE_LOCKS_GUARD:
        entry = _GENERATE_LOCKS.get(key)
        if entry is None:
            return
        entry.refs = max(0, entry.refs - 1)
        _evict_idle()


def _lock_for(key: str) -> threading.Lock:
    """Return the lock for ``key`` without pinning (idle LRU helper)."""

    with _GENERATE_LOCKS_GUARD:
        entry = _GENERATE_LOCKS.get(key)
        if entry is None:
            entry = _LockEntry(lock=threading.Lock())
            _GENERATE_LOCKS[key] = entry
        _GENERATE_LOCKS.move_to_end(key)
        _evict_idle()
        return entry.lock


@contextmanager
def _generation_lock(key: str) -> Iterator[None]:
    lock = _pin_lock(key)
    acquired = False
    try:
        lock.acquire()
        acquired = True
        yield
    finally:
        if acquired:
            lock.release()
        _unpin_lock(key)


def load_or_build_cached_glb(
    store: ProjectStore,
    project_id: str,
    pcb_text: str,
    pcb_hex: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_BYTES,
    flags: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Return a cached GLB, generating once per PCB digest + options fingerprint."""

    safe_id = validate_project_id(project_id)
    safe_hex = pcb_hex.lower()
    glb_path, sidecar_path = model_cache_paths(store, safe_id, safe_hex, flags)
    key = f"{safe_id}:{safe_hex}:{options_fingerprint(flags)}"
    with _generation_lock(key):
        _assert_cache_not_symlinked(glb_path, sidecar_path, glb_path.parent)
        cached = _try_read_cache(glb_path, sidecar_path, max_bytes=max_bytes)
        if cached is not None:
            cached["pcb_sha256"] = f"sha256:{safe_hex}"
            return cached
        data = generate_glb(pcb_text, timeout_s=timeout_s, max_bytes=max_bytes, flags=flags)
        probe = capability_probe()
        version = probe.get("version") if isinstance(probe.get("version"), str) else None
        generated_with = f"kicad-cli {version}" if version else "kicad-cli"
        try:
            _replace_cache(glb_path, sidecar_path, data, generated_with=generated_with)
        except OSError:
            pass
        verified = _try_read_cache(glb_path, sidecar_path, max_bytes=max_bytes)
        if verified is None:
            return _memory_model(data, pcb_hex=safe_hex, generated_with=generated_with)
        verified["pcb_sha256"] = f"sha256:{safe_hex}"
        return verified
