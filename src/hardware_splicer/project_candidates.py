"""Candidate proposals: apply KiCad edits to a retained revision and open review.

A candidate is a proposal. The service never writes a revision, pin, thread, or
review decision. Authority is never implicitly upgraded.
"""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import tempfile
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .artifact_retention import (
    ARTIFACT_KINDS,
    _is_symlink,
    _lexical_absolute,
    _read_regular_file,
    derive_snapshot_build_dir,
    read_pinned_artifact,
)
from .bounded_process import BoundedProcessError, run_bounded
from .build_files_security import assert_build_dir_allowed, max_kicad_content_bytes, output_roots
from .kicad_diff import KicadDiffError, diff_kicad_text
from .kicad_edit import KicadEditError, apply_edit_ops
from .model3d import capability_probe, resolve_kicad_cli
from .project_review_store import ProjectReviewStore
from .project_store import ProjectStore, validate_project_id

CANDIDATE_SCHEMA = "hardware_splicer.candidate.v1"
CANDIDATE_ID_RE = re.compile(r"^cand-[0-9a-f]{12}$")
MAX_CANDIDATES_PER_PROJECT = 50
MAX_LISTED_CANDIDATES = 100
MAX_AUTHOR_LEN = 80
MAX_NOTE_LEN = 500
MAX_OPS = 200
MAX_OP_STRING = 4096
MAX_REQUEST_BYTES = 256 * 1024
MAX_RECORD_BYTES = 512 * 1024
MAX_APPLIED_DETAIL = 200
MAX_DIFF_CHANGES = 500
MAX_FILENAME = 120
ORPHAN_MAX_AGE_S = 3600
MKDIR_RETRIES = 5
LOCK_TABLE_MAX = 256
AUTHORITY_NOTE = (
    "A candidate is a proposal. Accepting its review does not mark anything "
    "verified, fabrication-ready or release-ready."
)
AUTHORITY = {"state": "proposal", "note": AUTHORITY_NOTE}
REASON_UNAVAILABLE = "kicad-cli is not available"
REASON_TIMEOUT = "kicad-cli timed out"
REASON_FAILED = "kicad-cli failed"
REASON_REPORT_UNREADABLE = "report could not be read"
REASON_REPORT_TOO_LARGE = "report was too large"
_CHECK_TIMEOUT_S = 60.0
_SAFE_FILE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)

_PROPOSAL_LOCKS_GUARD = threading.Lock()


class _LockEntry:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.refs = 0


_PROPOSAL_LOCKS: OrderedDict[str, _LockEntry] = OrderedDict()


class CandidateError(RuntimeError):
    """Base error for candidate proposals."""


class CandidateNotFound(CandidateError, FileNotFoundError):
    """Unknown candidate, or a candidate_id that is not allowed."""


class ArtifactNotRetained(CandidateError):
    """The base revision has no retained artifact of the requested kind."""


class InvalidEdit(CandidateError):
    """KiCad edit operations were rejected. Message never includes file bytes."""


class NoEffectiveChange(CandidateError):
    """The edit produced an empty structural diff."""


class TooManyCandidates(CandidateError):
    """This project already has the maximum number of candidate records."""


class CandidateIntegrityError(CandidateError):
    """Candidate record or bytes failed hash verification."""


class CandidateValidationError(CandidateError, ValueError):
    """Request fields are not usable."""


class RequestTooLarge(CandidateError):
    """JSON body exceeded MAX_REQUEST_BYTES."""


class ArtifactTooLarge(CandidateError):
    """Edited or copied KiCad bytes exceeded max_kicad_content_bytes."""


class _CheckFailed(CandidateError):
    """Internal: checks did not produce a usable report. ``reason`` is vocabulary-only."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_hex(value: str) -> str:
    text = value.split(":", 1)[1] if value.startswith("sha256:") else value
    return text.lower()


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _require_candidate_id(candidate_id: str) -> str:
    if not isinstance(candidate_id, str) or CANDIDATE_ID_RE.fullmatch(candidate_id) is None:
        raise CandidateNotFound("candidate not found")
    return candidate_id


def _record_dir(store: ProjectStore, project_id: str) -> Path:
    return store._project_dir(validate_project_id(project_id)) / "candidates"


def _record_path(store: ProjectStore, project_id: str, candidate_id: str) -> Path:
    return _record_dir(store, project_id) / f"{candidate_id}.json"


def _output_root() -> Path:
    roots = output_roots()
    if not roots:
        raise CandidateValidationError("no output root is configured")
    return roots[0]


def _candidate_build_dir(project_id: str, candidate_id: str) -> Path:
    safe_id = validate_project_id(project_id)
    return _output_root() / "candidates" / safe_id / candidate_id


def _refuse_symlink(path: Path, *, label: str = "candidate path") -> None:
    if _is_symlink(path):
        raise CandidateValidationError(f"{label} is a symlink")


def _validate_single_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise CandidateValidationError("artifact filename is not usable")
    return name


def _kind_suffix(kind: str) -> str:
    return ".kicad_sch" if kind == "schematic" else ".kicad_pcb"


def sanitise_filename(relative: str, kind: str) -> str:
    """Turn a pin relative path into a single safe basename, keeping the KiCad suffix."""

    expected = _kind_suffix(kind)
    if not isinstance(relative, str) or not relative.strip():
        raise CandidateValidationError("artifact filename is not usable")
    name = Path(relative.replace("\\", "/")).name
    _validate_single_name(name)
    if not name.lower().endswith(expected):
        raise CandidateValidationError("artifact filename is not usable")
    stem = name[: -len(expected)]
    cleaned = "".join(ch if ch in _SAFE_FILE_CHARS else "_" for ch in stem)
    cleaned = cleaned.strip("._") or "board"
    max_stem = MAX_FILENAME - len(expected)
    if max_stem < 1:
        raise CandidateValidationError("artifact filename is not usable")
    return cleaned[:max_stem] + expected


def unique_filenames(entries: Sequence[tuple[str, str]]) -> dict[str, str]:
    """Sanitise pin relatives and disambiguate if two kinds collapse to one name."""

    taken: set[str] = set()
    out: dict[str, str] = {}
    for kind, relative in entries:
        expected = _kind_suffix(kind)
        name = sanitise_filename(relative, kind)
        if name in taken:
            stem = name[: -len(expected)]
            index = 2
            while True:
                suffix = f"_{index}"
                room = MAX_FILENAME - len(expected) - len(suffix)
                candidate = (stem[: max(1, room)] + suffix + expected)
                if candidate not in taken:
                    name = candidate
                    break
                index += 1
        taken.add(name)
        out[kind] = name
    return out


def _rmtree_nofollow(path: Path | None) -> None:
    if path is None:
        return
    if _is_symlink(path):
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        return
    if path.is_file():
        path.unlink(missing_ok=True)


def _mkdir_component(parent: Path, name: str, *, exist_ok: bool) -> Path:
    _validate_single_name(name)
    _refuse_symlink(parent)
    nxt = parent / name
    try:
        info = os.lstat(nxt)
    except FileNotFoundError:
        os.mkdir(nxt, 0o700)
        os.chmod(nxt, 0o700)
        _refuse_symlink(nxt)
        return nxt
    if stat.S_ISLNK(info.st_mode):
        raise CandidateValidationError("candidate path is a symlink")
    if not stat.S_ISDIR(info.st_mode):
        raise CandidateError("candidate path is not a directory")
    if not exist_ok:
        raise FileExistsError(errno.EEXIST, "directory exists", str(nxt))
    return nxt


def _ensure_dir_chain(root: Path, parts: Sequence[str], *, last_exist_ok: bool) -> Path:
    """Create ``root/parts...`` one component at a time. Never ``parents=True``."""

    _refuse_symlink(root)
    current = root
    if not parts:
        return current
    for name in parts[:-1]:
        current = _mkdir_component(current, name, exist_ok=True)
    return _mkdir_component(current, parts[-1], exist_ok=last_exist_ok)


def _open_dir_nofollow(path: Path) -> int:
    _refuse_symlink(path)
    flags = os.O_RDONLY | _CLOEXEC | _NOFOLLOW | _O_DIRECTORY
    try:
        return os.open(os.fspath(path), flags)
    except OSError as exc:
        if getattr(exc, "errno", None) in {errno.ELOOP, errno.EMLINK}:
            raise CandidateValidationError("candidate path is a symlink") from None
        raise


def _write_named_create_only(dir_path: Path, name: str, content: bytes) -> None:
    """Create-only write of ``name`` under ``dir_path`` using ``O_NOFOLLOW`` + ``dir_fd``."""

    _validate_single_name(name)
    dir_fd = _open_dir_nofollow(dir_path)
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _CLOEXEC | _NOFOLLOW
        try:
            fd = os.open(name, flags, 0o600, dir_fd=dir_fd)
        except OSError as exc:
            if getattr(exc, "errno", None) in {errno.ELOOP, errno.EMLINK}:
                raise CandidateValidationError("candidate path is a symlink") from None
            if getattr(exc, "errno", None) == errno.EEXIST:
                raise CandidateError("candidate file already exists") from None
            raise
        remaining = memoryview(content)
        while remaining:
            written = os.write(fd, remaining)
            remaining = remaining[written:]
        os.fsync(fd)
        os.close(fd)
        fd = None
        try:
            os.chmod(name, 0o600, dir_fd=dir_fd, follow_symlinks=False)
        except (TypeError, NotImplementedError, OSError):
            os.chmod(name, 0o600, dir_fd=dir_fd)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dir_fd)


def _assert_existing_components_not_symlinks(root: Path, parts: Sequence[str]) -> None:
    """Refuse if any existing component from ``root`` down ``parts`` is a symlink."""

    _refuse_symlink(root)
    current = root
    for name in parts:
        _validate_single_name(name)
        current = current / name
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(info.st_mode):
            raise CandidateValidationError("candidate path is a symlink")


def _proposal_hook(stage: str, **_kwargs: Any) -> None:
    """No-op production hook. Tests monkeypatch this to inject failures."""

    del stage


def _read_named_nofollow(dir_path: Path, name: str, *, limit: int) -> bytes:
    _validate_single_name(name)
    dir_fd = _open_dir_nofollow(dir_path)
    fd = None
    try:
        flags = os.O_RDONLY | _CLOEXEC | _NOFOLLOW
        try:
            fd = os.open(name, flags, dir_fd=dir_fd)
        except OSError as exc:
            if getattr(exc, "errno", None) in {errno.ELOOP, errno.EMLINK}:
                raise CandidateIntegrityError("candidate file is a symlink") from None
            raise CandidateIntegrityError("candidate file is not readable") from exc
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise CandidateIntegrityError("candidate file is not readable")
        if info.st_size > limit:
            raise CandidateIntegrityError("candidate file is not readable")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining > 0:
            piece = os.read(fd, remaining)
            if not piece:
                break
            chunks.append(piece)
            remaining -= len(piece)
        return b"".join(chunks)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dir_fd)


def _entry_in_use(entry: _LockEntry) -> bool:
    return entry.refs > 0 or entry.lock.locked()


def _evict_idle_locks() -> None:
    overflow = len(_PROPOSAL_LOCKS) - LOCK_TABLE_MAX
    if overflow <= 0:
        return
    for key, entry in list(_PROPOSAL_LOCKS.items()):
        if overflow <= 0:
            return
        if _entry_in_use(entry):
            continue
        _PROPOSAL_LOCKS.pop(key, None)
        overflow -= 1


def _pin_lock(key: str) -> threading.Lock:
    with _PROPOSAL_LOCKS_GUARD:
        entry = _PROPOSAL_LOCKS.get(key)
        if entry is None:
            entry = _LockEntry()
            _PROPOSAL_LOCKS[key] = entry
        entry.refs += 1
        _PROPOSAL_LOCKS.move_to_end(key)
        _evict_idle_locks()
        return entry.lock


def _unpin_lock(key: str) -> None:
    with _PROPOSAL_LOCKS_GUARD:
        entry = _PROPOSAL_LOCKS.get(key)
        if entry is None:
            return
        entry.refs = max(0, entry.refs - 1)
        _evict_idle_locks()


@contextmanager
def _project_proposal_lock(project_id: str) -> Iterator[None]:
    lock = _pin_lock(project_id)
    acquired = False
    try:
        lock.acquire()
        acquired = True
        yield
    finally:
        if acquired:
            lock.release()
        _unpin_lock(project_id)


def _record_ids(store: ProjectStore, project_id: str) -> set[str]:
    folder = _record_dir(store, project_id)
    if not folder.is_dir() or _is_symlink(folder):
        return set()
    found: set[str] = set()
    for path in folder.iterdir():
        if path.suffix == ".json" and CANDIDATE_ID_RE.fullmatch(path.stem) and path.is_file() and not _is_symlink(path):
            found.add(path.stem)
    return found


def _orphan_dirs(project_id: str, referenced: set[str]) -> list[Path]:
    try:
        root = _output_root() / "candidates" / validate_project_id(project_id)
    except CandidateValidationError:
        return []
    if _is_symlink(root) or not root.is_dir():
        return []
    orphans: list[Path] = []
    for path in root.iterdir():
        if CANDIDATE_ID_RE.fullmatch(path.name) is None:
            continue
        if path.name in referenced:
            continue
        try:
            info = os.lstat(path)
        except OSError:
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            continue
        orphans.append(path)
    return orphans


def _sweep_stale_orphans(project_id: str, referenced: set[str]) -> None:
    """Delete orphan candidate dirs older than one hour and not named by any record."""

    now = time.time()
    for path in _orphan_dirs(project_id, referenced):
        try:
            age = now - os.lstat(path).st_mtime
        except OSError:
            continue
        if age > ORPHAN_MAX_AGE_S:
            _rmtree_nofollow(path)


def _count_towards_cap(store: ProjectStore, project_id: str) -> int:
    referenced = _record_ids(store, project_id)
    _sweep_stale_orphans(project_id, referenced)
    return len(referenced) + len(_orphan_dirs(project_id, referenced))


def _require_author(author: Any) -> str:
    if not isinstance(author, str):
        raise CandidateValidationError("author must be a string of 1 to 80 characters")
    text = author.strip()
    if not text or len(text) > MAX_AUTHOR_LEN:
        raise CandidateValidationError("author must be a string of 1 to 80 characters")
    return text


def _require_note(note: Any) -> str:
    if note is None:
        return ""
    if not isinstance(note, str) or len(note) > MAX_NOTE_LEN:
        raise CandidateValidationError("note must be a string of at most 500 characters")
    return note


def _require_kind(kind: Any) -> str:
    if kind not in ARTIFACT_KINDS:
        raise CandidateValidationError("kind must be schematic or pcb")
    return str(kind)


def _require_ops(ops: Any) -> Sequence[Mapping[str, Any]]:
    if isinstance(ops, (str, bytes)) or not isinstance(ops, Sequence):
        raise CandidateValidationError("ops must be a sequence")
    if len(ops) < 1 or len(ops) > MAX_OPS:
        raise CandidateValidationError("ops must contain between 1 and 200 operations")
    for index, raw in enumerate(ops):
        if not isinstance(raw, Mapping):
            raise CandidateValidationError(f"op {index} is not a mapping")
        for value in raw.values():
            if isinstance(value, str) and len(value) > MAX_OP_STRING:
                raise CandidateValidationError("op string value exceeds 4096 characters")
    return ops


def _require_base_revision(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CandidateValidationError("base_revision must be a positive integer or null")
    return value


def _set_if_present(mapping: dict[str, Any], key: str, value: str) -> None:
    if key in mapping:
        mapping[key] = value


def rewrite_snapshot_build_dirs(snapshot: Mapping[str, Any], new_dir: str) -> dict[str, Any]:
    """Deep-copy a snapshot and point every present build-dir key at ``new_dir``."""

    out = copy.deepcopy(dict(snapshot))
    out["buildDir"] = new_dir
    out["build_dir"] = new_dir
    for pkg_key in ("projectPackage", "project_package"):
        pkg = out.get(pkg_key)
        if isinstance(pkg, dict):
            _set_if_present(pkg, "build_dir", new_dir)
    for compose_key in ("composeResult", "compose_result"):
        compose = out.get(compose_key)
        if isinstance(compose, dict):
            _set_if_present(compose, "out_dir", new_dir)
            _set_if_present(compose, "build_dir", new_dir)
    sessions = out.get("engineeringAiSessions")
    if isinstance(sessions, list) and sessions:
        last = sessions[-1]
        if isinstance(last, dict):
            _set_if_present(last, "buildDir", new_dir)
            _set_if_present(last, "build_dir", new_dir)
            for pkg_key in ("projectPackage", "project_package"):
                pkg = last.get(pkg_key)
                if isinstance(pkg, dict):
                    _set_if_present(pkg, "build_dir", new_dir)
            nested = last.get("package")
            if isinstance(nested, dict):
                _set_if_present(nested, "build_dir", new_dir)
    return out


def _diff_empty(report: Mapping[str, Any]) -> bool:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    try:
        added = int(summary.get("added") or 0)
        removed = int(summary.get("removed") or 0)
        changed = int(summary.get("changed") or 0)
    except (TypeError, ValueError):
        return False
    return added == 0 and removed == 0 and changed == 0


def _extend_rows(rows: list[dict[str, Any]], items: Any, *, default_type: str) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        raw_type = row.get("type")
        if not isinstance(raw_type, str) or not raw_type:
            row["type"] = default_type
        rows.append(row)


def _iter_violation_rows(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    _extend_rows(rows, payload.get("violations"), default_type="unknown")
    sheets = payload.get("sheets")
    if isinstance(sheets, list):
        for sheet in sheets:
            if isinstance(sheet, Mapping):
                _extend_rows(rows, sheet.get("violations"), default_type="unknown")
    _extend_rows(rows, payload.get("unconnected_items"), default_type="unconnected_items")
    _extend_rows(rows, payload.get("schematic_parity"), default_type="schematic_parity")
    return rows


def summarize_check_report(payload: Any) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    errors = 0
    warnings = 0
    for row in _iter_violation_rows(payload):
        if bool(row.get("excluded")):
            continue
        raw_type = row.get("type")
        type_name = raw_type if isinstance(raw_type, str) and raw_type else "unknown"
        by_type[type_name] = by_type.get(type_name, 0) + 1
        severity = str(row.get("severity") or "").lower()
        if severity == "error":
            errors += 1
        elif severity == "warning":
            warnings += 1
    return {
        "errors": errors,
        "warnings": warnings,
        "total": sum(by_type.values()),
        "by_type": by_type,
    }


def new_violations(before: Mapping[str, Any], after: Mapping[str, Any]) -> int:
    before_types = before.get("by_type") if isinstance(before.get("by_type"), Mapping) else {}
    after_types = after.get("by_type") if isinstance(after.get("by_type"), Mapping) else {}
    names = set(before_types) | set(after_types)
    total = 0
    for name in names:
        try:
            before_n = int(before_types.get(name) or 0)
        except (TypeError, ValueError):
            before_n = 0
        try:
            after_n = int(after_types.get(name) or 0)
        except (TypeError, ValueError):
            after_n = 0
        total += max(0, after_n - before_n)
    return total


def _empty_checks(*, available: bool, version: str | None, reason: str | None) -> dict[str, Any]:
    return {
        "engine": "kicad-cli",
        "available": available,
        "version": version,
        "ran": False,
        "reason": reason,
        "before": {},
        "after": {},
        "new_violations": None,
    }


def _path_only_env(home: Path) -> dict[str, str]:
    parts = [part for part in os.environ.get("PATH", "").split(os.pathsep) if part]
    for extra in ("/usr/bin", "/bin"):
        if extra not in parts:
            parts.append(extra)
    return {"PATH": os.pathsep.join(parts) or "/usr/bin:/bin", "HOME": str(home)}


def _run_one_check(kind: str, text: str, *, timeout_s: float) -> dict[str, Any]:
    binary = resolve_kicad_cli()
    if not binary:
        raise _CheckFailed(REASON_UNAVAILABLE)
    work = Path(tempfile.mkdtemp(prefix="hs_candidate_check_"))
    os.chmod(work, 0o700)
    try:
        if kind == "pcb":
            src_name = "board.kicad_pcb"
            report_name = "drc.json"
            cmd_kind = ["pcb", "drc"]
        else:
            src_name = "board.kicad_sch"
            report_name = "erc.json"
            cmd_kind = ["sch", "erc"]
        src_path = work / src_name
        report_path = work / report_name
        src_path.write_text(text, encoding="utf-8")
        os.chmod(src_path, 0o600)
        try:
            result = run_bounded(
                [
                    binary,
                    *cmd_kind,
                    "--format",
                    "json",
                    "--output",
                    str(report_path),
                    str(src_path),
                ],
                timeout_s=timeout_s,
                cwd=work,
                env=_path_only_env(work),
            )
        except BoundedProcessError as exc:
            if exc.timed_out:
                raise _CheckFailed(REASON_TIMEOUT) from None
            raise _CheckFailed(REASON_FAILED) from None
        # --exit-code-violations is omitted, so a violations-found exit is not
        # expected. Any nonzero status is a tool failure even if a JSON file
        # is present (including a stale leftover report).
        if result.returncode != 0:
            raise _CheckFailed(f"{REASON_FAILED} (exit {result.returncode})")
        if _is_symlink(report_path) or not report_path.is_file():
            raise _CheckFailed(REASON_REPORT_UNREADABLE)
        try:
            raw = _read_regular_file(report_path, limit=max_kicad_content_bytes())
        except ValueError as exc:
            message = str(exc)
            if "exceeds size limit" in message or "too large" in message:
                raise _CheckFailed(REASON_REPORT_TOO_LARGE) from None
            raise _CheckFailed(REASON_REPORT_UNREADABLE) from None
        except OSError:
            raise _CheckFailed(REASON_REPORT_UNREADABLE) from None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise _CheckFailed(REASON_REPORT_UNREADABLE) from None
        return summarize_check_report(payload)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_candidate_checks(
    kind: str,
    before_text: str,
    after_text: str,
    *,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Optional DRC/ERC counts. Never decides whether a candidate may exist."""

    probe = capability_probe()
    version = probe.get("version") if isinstance(probe.get("version"), str) else None
    if not probe.get("available"):
        return _empty_checks(available=False, version=None, reason=REASON_UNAVAILABLE)
    limit = _CHECK_TIMEOUT_S if timeout_s is None else float(timeout_s)
    try:
        before = _run_one_check(kind, before_text, timeout_s=limit)
        after = _run_one_check(kind, after_text, timeout_s=limit)
    except _CheckFailed as exc:
        return _empty_checks(available=True, version=version, reason=exc.reason)
    except Exception:
        return _empty_checks(available=True, version=version, reason=REASON_FAILED)
    return {
        "engine": "kicad-cli",
        "available": True,
        "version": version,
        "ran": True,
        "reason": None,
        "before": before,
        "after": after,
        "new_violations": new_violations(before, after),
    }


def _cleanup_proposal(
    store: ProjectStore,
    project_id: str,
    *,
    candidate_dir: Path | None,
    created_dir: bool,
    record_path: Path | None,
    review_id: str | None,
) -> None:
    if created_dir:
        _rmtree_nofollow(candidate_dir)
    if record_path is not None and record_path.exists():
        if _is_symlink(record_path):
            record_path.unlink(missing_ok=True)
        elif record_path.is_file():
            record_path.unlink(missing_ok=True)
    if review_id:
        review_dir = store._project_dir(project_id) / "reviews" / review_id
        _rmtree_nofollow(review_dir)


def _cap_stored_record(record: dict[str, Any]) -> dict[str, Any]:
    applied_out: list[Any] = []
    for row in record.get("applied") or []:
        if isinstance(row, dict) and isinstance(row.get("detail"), str) and len(row["detail"]) > MAX_APPLIED_DETAIL:
            row = dict(row)
            row["detail"] = row["detail"][:MAX_APPLIED_DETAIL]
        applied_out.append(row)
    record["applied"] = applied_out
    diff = record.get("diff")
    if isinstance(diff, dict):
        changes = diff.get("changes")
        if isinstance(changes, list) and len(changes) > MAX_DIFF_CHANGES:
            diff = dict(diff)
            diff["changes"] = changes[:MAX_DIFF_CHANGES]
            limits = dict(diff.get("limits") or {})
            limits["truncated"] = True
            diff["limits"] = limits
            record["diff"] = diff
    payload = _json_bytes(record)
    if len(payload) > MAX_RECORD_BYTES and isinstance(record.get("diff"), dict):
        diff = dict(record["diff"])
        diff["changes"] = []
        limits = dict(diff.get("limits") or {})
        limits["truncated"] = True
        diff["limits"] = limits
        record["diff"] = diff
    return record


def _review_summary(review: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: review.get(key)
        for key in (
            "review_id",
            "project_id",
            "base_revision",
            "created_at",
            "created_by",
            "note",
            "summary",
            "review_flags",
            "status",
            "decision",
        )
    }


def _validate_record(payload: Any, *, project_id: str, candidate_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CandidateIntegrityError("candidate record is corrupt")
    if payload.get("schema_version") != CANDIDATE_SCHEMA:
        raise CandidateIntegrityError("candidate record is corrupt")
    if payload.get("project_id") != project_id or payload.get("candidate_id") != candidate_id:
        raise CandidateIntegrityError("candidate record is corrupt")
    return payload


def _read_record(store: ProjectStore, project_id: str, candidate_id: str) -> dict[str, Any]:
    path = _record_path(store, project_id, candidate_id)
    if _is_symlink(path) or not path.is_file():
        raise CandidateNotFound("candidate not found")
    try:
        payload = json.loads(_read_regular_file(path, limit=max_kicad_content_bytes()).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateIntegrityError("candidate record is corrupt") from exc
    return _validate_record(payload, project_id=project_id, candidate_id=candidate_id)


def _assert_write_size(payload: bytes, *, label: str) -> None:
    del label
    if len(payload) > max_kicad_content_bytes():
        raise ArtifactTooLarge("artifact exceeds size limit")


def propose_candidate(
    store: ProjectStore,
    project_id: str,
    *,
    kind: str,
    ops: Sequence[Mapping[str, Any]],
    author: str,
    note: str = "",
    base_revision: int | None = None,
    created_by: str | None = None,
    verified: bool = False,
    review_store: ProjectReviewStore | None = None,
) -> dict[str, Any]:
    """Apply edit ops to a retained revision and open a staged review."""

    safe_id = validate_project_id(project_id)
    kind = _require_kind(kind)
    ops = _require_ops(ops)
    note = _require_note(note)
    base_revision = _require_base_revision(base_revision)
    declared_author = _require_author(author)
    if verified:
        actor = str(created_by or "").strip()
        if not actor:
            raise CandidateValidationError("created_by is required")
    else:
        actor = declared_author
    reviews = review_store or ProjectReviewStore(store)

    if base_revision is None:
        envelope = store.load_latest_with_recovery(safe_id)
    else:
        envelope = store.load(safe_id, revision=base_revision)
    resolved_revision = int(envelope["revision"])
    snapshot = envelope.get("snapshot")
    if not isinstance(snapshot, Mapping):
        raise CandidateValidationError("revision snapshot is not usable")

    pinned = read_pinned_artifact(store, safe_id, resolved_revision, kind)
    if pinned is None:
        raise ArtifactNotRetained(f"revision {resolved_revision} has no retained {kind} artifact")
    base_text, pin_entry = pinned
    base_bytes = base_text.encode("utf-8")

    try:
        edited = apply_edit_ops(kind, base_text, ops)
    except KicadEditError as exc:
        raise InvalidEdit(str(exc)) from None
    edited_text = str(edited.get("text") or "")
    edited_bytes = edited_text.encode("utf-8")
    _assert_write_size(edited_bytes, label="edited")

    try:
        diff = diff_kicad_text(kind, base_text, edited_text)
    except KicadDiffError as exc:
        raise InvalidEdit(str(exc)) from None
    if _diff_empty(diff):
        raise NoEffectiveChange("edit produced no structural change")

    other_kind = "pcb" if kind == "schematic" else "schematic"
    other_bytes: bytes | None = None
    other_entry: Mapping[str, Any] | None = None
    name_entries: list[tuple[str, str]] = [(kind, str(pin_entry.get("relative") or ""))]
    other_pinned = read_pinned_artifact(store, safe_id, resolved_revision, other_kind)
    if other_pinned is not None:
        other_text, other_entry = other_pinned
        other_bytes = other_text.encode("utf-8")
        _assert_write_size(other_bytes, label="copied")
        name_entries.append((other_kind, str(other_entry.get("relative") or "")))
    filenames = unique_filenames(name_entries)

    created_dir = False
    candidate_dir: Path | None = None
    record_path: Path | None = None
    review_id: str | None = None
    committed = False
    with _project_proposal_lock(safe_id):
        if _count_towards_cap(store, safe_id) >= MAX_CANDIDATES_PER_PROJECT:
            raise TooManyCandidates("too many candidates for this project")
        output_root = _output_root()
        try:
            try:
                assert_build_dir_allowed(output_root / "candidates" / safe_id / "cand-placeholder")
            except ValueError as exc:
                raise CandidateValidationError("candidate path is not allowed") from exc
            _assert_existing_components_not_symlinks(output_root, ("candidates", safe_id))
            for _attempt in range(MKDIR_RETRIES):
                candidate_id = "cand-" + secrets.token_hex(6)
                if _record_path(store, safe_id, candidate_id).exists():
                    continue
                candidate_dir = output_root / "candidates" / safe_id / candidate_id
                try:
                    assert_build_dir_allowed(candidate_dir)
                except ValueError as exc:
                    raise CandidateValidationError("candidate path is not allowed") from exc
                _assert_existing_components_not_symlinks(
                    output_root, ("candidates", safe_id, candidate_id)
                )
                try:
                    parent = _ensure_dir_chain(
                        output_root,
                        ("candidates", safe_id),
                        last_exist_ok=True,
                    )
                    _refuse_symlink(parent)
                    os.mkdir(candidate_dir, 0o700)
                    created_dir = True
                    os.chmod(candidate_dir, 0o700)
                    _refuse_symlink(candidate_dir)
                    _proposal_hook("after_mkdir", path=candidate_dir)
                    break
                except FileExistsError:
                    created_dir = False
                    candidate_dir = None
                    continue
            else:
                raise CandidateError("could not allocate a candidate id")
            assert candidate_dir is not None
            files: dict[str, dict[str, str] | None] = {"schematic": None, "pcb": None}
            _write_named_create_only(candidate_dir, filenames[kind], edited_bytes)
            files[kind] = {
                "relative": filenames[kind],
                "sha256": _sha256_bytes(edited_bytes),
                "role": "edited",
            }
            if other_bytes is not None and other_kind in filenames:
                _proposal_hook("before_second_file", path=candidate_dir)
                _write_named_create_only(candidate_dir, filenames[other_kind], other_bytes)
                files[other_kind] = {
                    "relative": filenames[other_kind],
                    "sha256": _sha256_bytes(other_bytes),
                    "role": "copied",
                }
            checks = run_candidate_checks(kind, base_text, edited_text)
            candidate_snapshot = rewrite_snapshot_build_dirs(snapshot, str(candidate_dir))
            if derive_snapshot_build_dir(candidate_snapshot) != str(candidate_dir):
                raise CandidateError("candidate snapshot did not retain the candidate build directory")
            _proposal_hook("before_review", path=candidate_dir)
            review = reviews.create(
                safe_id,
                candidate_snapshot,
                base_revision=resolved_revision,
                created_by=actor,
                note=note,
            )
            review_id = str(review.get("review_id") or "")
            record = _cap_stored_record(
                {
                    "schema_version": CANDIDATE_SCHEMA,
                    "candidate_id": candidate_id,
                    "project_id": safe_id,
                    "base_revision": resolved_revision,
                    "kind": kind,
                    "review_id": review_id,
                    "created_by": actor,
                    "verified": bool(verified),
                    "created_at": _utc_now(),
                    "applied": list(edited.get("applied") or []),
                    "warnings": list(edited.get("warnings") or []),
                    "edited_sha256": _sha256_bytes(edited_bytes),
                    "base_sha256": _sha256_bytes(base_bytes),
                    "diff": diff,
                    "checks": checks,
                    "authority": dict(AUTHORITY),
                    "files": files,
                }
            )
            record_path = _record_path(store, safe_id, candidate_id)
            _proposal_hook("before_record", path=record_path)
            _ensure_dir_chain(store._project_dir(safe_id), ("candidates",), last_exist_ok=True)
            _write_named_create_only(record_path.parent, record_path.name, _json_bytes(record))
            committed = True
            return {"candidate": record, "review": _review_summary(review)}
        finally:
            if not committed:
                _cleanup_proposal(
                    store,
                    safe_id,
                    candidate_dir=candidate_dir,
                    created_dir=created_dir,
                    record_path=record_path,
                    review_id=review_id,
                )


def list_candidates(store: ProjectStore, project_id: str) -> list[dict[str, Any]]:
    safe_id = validate_project_id(project_id)
    store.load_latest_with_recovery(safe_id)
    folder = _record_dir(store, safe_id)
    if not folder.is_dir() or _is_symlink(folder):
        return []
    rows: list[dict[str, Any]] = []
    for path in folder.iterdir():
        if path.suffix != ".json" or CANDIDATE_ID_RE.fullmatch(path.stem) is None:
            continue
        if _is_symlink(path) or not path.is_file():
            continue
        try:
            rows.append(_read_record(store, safe_id, path.stem))
        except (CandidateIntegrityError, CandidateNotFound, OSError, ValueError):
            continue
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("candidate_id") or "")), reverse=True)
    return rows[:MAX_LISTED_CANDIDATES]


def load_candidate(store: ProjectStore, project_id: str, candidate_id: str) -> dict[str, Any]:
    safe_candidate = _require_candidate_id(candidate_id)
    safe_id = validate_project_id(project_id)
    store.load_latest_with_recovery(safe_id)
    return _read_record(store, safe_id, safe_candidate)


def read_candidate_file(
    store: ProjectStore,
    project_id: str,
    candidate_id: str,
    kind: str,
) -> tuple[bytes, str]:
    """Return ``(bytes, sha256)`` of a candidate file. Never reads outside the candidate dir."""

    safe_candidate = _require_candidate_id(candidate_id)
    kind = _require_kind(kind)
    record = load_candidate(store, project_id, safe_candidate)
    files = record.get("files") if isinstance(record.get("files"), Mapping) else {}
    entry = files.get(kind) if isinstance(files, Mapping) else None
    if not isinstance(entry, Mapping):
        raise CandidateNotFound("candidate file not found")
    relative = entry.get("relative")
    expected = entry.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise CandidateIntegrityError("candidate file record is corrupt")
    name = sanitise_filename(relative, kind)
    candidate_dir = _candidate_build_dir(project_id, safe_candidate)
    if _is_symlink(candidate_dir) or not candidate_dir.is_dir():
        raise CandidateNotFound("candidate file not found")
    lexical = _lexical_absolute(candidate_dir / name)
    if lexical.parent != _lexical_absolute(candidate_dir):
        raise CandidateNotFound("candidate file not found")
    data = _read_named_nofollow(candidate_dir, name, limit=max_kicad_content_bytes())
    digest = _sha256_bytes(data)
    if _digest_hex(digest) != _digest_hex(expected):
        raise CandidateIntegrityError("candidate file failed hash verification")
    if kind == record.get("kind") and _digest_hex(digest) != _digest_hex(str(record.get("edited_sha256") or "")):
        raise CandidateIntegrityError("candidate file failed hash verification")
    return data, digest
