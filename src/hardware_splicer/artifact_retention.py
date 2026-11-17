"""Content-addressed KiCad artifact retention for immutable project revisions.

Build directories stay path references in the snapshot and remain mutable. This
module copies ``.kicad_sch`` / ``.kicad_pcb`` bytes and their exact-stem
``.kicad_pro`` / ``.kicad_dru`` companions into a separate
content-addressed store and pins them to a revision. Pins and blobs never
rewrite a snapshot, revision envelope, or authority field.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .build_files_security import assert_build_dir_allowed, max_kicad_content_bytes
from .project_store import ProjectStore, validate_project_id

PIN_SCHEMA = "hardware_splicer.artifact_pins.v1"
RETENTION_BASES = frozenset({"at_save", "after_save"})
ARTIFACT_KINDS = ("schematic", "pcb")
ARTIFACT_SIDECARS = {"project": ".kicad_pro", "rules": ".kicad_dru"}
_KICAD_SUFFIXES = {".kicad_sch": "schematic", ".kicad_pcb": "pcb"}
_PIN_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_RETENTION_RESULTS = 256


class ArtifactRetentionError(RuntimeError):
    """Base error for retained KiCad artifacts."""


class ArtifactIntegrityError(ArtifactRetentionError):
    """Blob missing, corrupt, or hash mismatch."""


class ArtifactPinConflict(ArtifactRetentionError):
    """A revision is already pinned to different artifact bytes."""


def validate_kicad_rule_bytes(raw: bytes) -> None:
    """Validate bounded native rules without following includes or file paths.

    KiCad can silently ignore unknown top-level declarations. Check the file
    envelope before invoking it, while leaving rule expressions and exact bytes
    unchanged for native evaluation. This does not assert that DRC passed.
    """
    from .kicad_diff import KicadDiffError, parse_kicad_sexp

    if not isinstance(raw, bytes) or len(raw) > max_kicad_content_bytes():
        raise ValueError("KiCad custom rules exceed the supported input limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("KiCad custom rules must be UTF-8") from None
    cleaned = []
    quoted = escaped = comment = False
    for char in text:
        if comment:
            if char == "\n":
                comment = False
                cleaned.append(char)
            continue
        if not quoted and char == "#":
            comment = True
            continue
        cleaned.append(char)
        if quoted and escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
    try:
        tree = parse_kicad_sexp("(custom_rules\n" + "".join(cleaned) + "\n)")
    except KicadDiffError:
        raise ValueError("KiCad custom rule declarations are malformed") from None
    declarations = tree[1:]
    def reject_includes(node):
        if isinstance(node, list):
            if node and node[0] == "include":
                raise ValueError("KiCad custom rule includes are not supported")
            for child in node:
                reject_includes(child)
    reject_includes(tree)
    if not declarations or declarations[0] != ["version", "1"]:
        raise ValueError("Only KiCad version-1 custom rule files are supported")
    for declaration in declarations[1:]:
        if (not isinstance(declaration, list) or len(declaration) < 3
                or declaration[0] != "rule" or not isinstance(declaration[1], str)):
            raise ValueError("Unsupported KiCad custom rule declaration; includes are not supported")
        for clause in declaration[2:]:
            if (not isinstance(clause, list) or not clause or not isinstance(clause[0], str)
                    or clause[0] not in {"condition", "constraint", "layer", "severity"}):
                raise ValueError("Unsupported KiCad custom rule clause")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
    return None


def derive_snapshot_build_dir(snapshot: Mapping[str, Any] | None) -> str | None:
    """Mirror the UI snapshot lookup, then the last engineeringAiSessions entry."""

    if not isinstance(snapshot, Mapping):
        return None
    project_package = _as_mapping(snapshot.get("projectPackage") or snapshot.get("project_package"))
    compose = _as_mapping(snapshot.get("composeResult") or snapshot.get("compose_result"))
    found = _first_string(
        snapshot.get("buildDir"),
        snapshot.get("build_dir"),
        project_package.get("build_dir"),
        compose.get("out_dir"),
        compose.get("build_dir"),
    )
    if found:
        return found
    sessions = snapshot.get("engineeringAiSessions")
    if not isinstance(sessions, list) or not sessions:
        return None
    last = sessions[-1]
    if not isinstance(last, Mapping):
        return None
    session_package = _as_mapping(last.get("projectPackage") or last.get("project_package"))
    nested_package = _as_mapping(last.get("package"))
    return _first_string(
        last.get("buildDir"),
        last.get("build_dir"),
        session_package.get("build_dir"),
        nested_package.get("build_dir"),
    )


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path))))


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode)
    except OSError:
        return False


def _project_dir(store: ProjectStore, project_id: str) -> Path:
    return store._project_dir(validate_project_id(project_id))


def _pin_path(store: ProjectStore, project_id: str, revision: int) -> Path:
    return _project_dir(store, project_id) / "artifact_pins" / f"{int(revision):08d}.json"


def _blob_path(store: ProjectStore, project_id: str, digest_hex: str) -> Path:
    return _project_dir(store, project_id) / "artifacts" / "sha256" / digest_hex[:2] / digest_hex


def _read_regular_file(path: Path, *, limit: int) -> bytes:
    lexical = _lexical_absolute(path)
    if _is_symlink(lexical):
        raise ValueError("symlinked file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(os.fspath(lexical), flags)
    except OSError as exc:
        if getattr(exc, "errno", None) in {errno.ELOOP, errno.EMLINK}:
            raise ValueError("symlinked file") from None
        raise
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("not a regular file")
        if info.st_size > limit:
            raise ValueError("file exceeds size limit")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining > 0:
            piece = os.read(fd, remaining)
            if not piece:
                break
            chunks.append(piece)
            remaining -= len(piece)
    finally:
        os.close(fd)
    return b"".join(chunks)


def _write_create_only(target: Path, content: bytes) -> bool:
    """Link ``content`` onto ``target``. Return True if this call created it."""

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, target)
        except OSError as exc:
            if getattr(exc, "errno", None) != errno.EEXIST and not isinstance(exc, FileExistsError):
                raise
            return False
        return True
    finally:
        temp_path.unlink(missing_ok=True)


def _store_blob(store: ProjectStore, project_id: str, content: bytes) -> str:
    digest_hex = hashlib.sha256(content).hexdigest()
    target = _blob_path(store, project_id, digest_hex)
    created = _write_create_only(target, content)
    if not created:
        try:
            existing = _read_regular_file(target, limit=max_kicad_content_bytes())
        except (OSError, ValueError) as exc:
            raise ArtifactIntegrityError("retained artifact failed hash verification") from exc
        if hashlib.sha256(existing).hexdigest() != digest_hex or existing != content:
            raise ArtifactIntegrityError("retained artifact failed hash verification")
    return f"sha256:{digest_hex}"


def _read_blob(store: ProjectStore, project_id: str, digest_hex: str) -> bytes:
    target = _blob_path(store, project_id, digest_hex)
    if _is_symlink(target) or not target.is_file():
        raise ArtifactIntegrityError("retained artifact is missing")
    try:
        data = _read_regular_file(target, limit=max_kicad_content_bytes())
    except (OSError, ValueError) as exc:
        raise ArtifactIntegrityError("retained artifact is missing") from exc
    if hashlib.sha256(data).hexdigest() != digest_hex:
        raise ArtifactIntegrityError("retained artifact failed hash verification")
    return data


def _iter_kicad_files(root: Path) -> list[tuple[str, Path, str]]:
    rows: list[tuple[str, Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        if _is_symlink(current):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(name for name in dirnames if not _is_symlink(current / name))
        for name in filenames:
            path = current / name
            if _is_symlink(path):
                continue
            kind = _KICAD_SUFFIXES.get(path.suffix.lower())
            if kind is None:
                continue
            relative = path.relative_to(root).as_posix()
            rows.append((kind, path, relative))
    return rows


def _pick_kicad_files(root: Path) -> dict[str, tuple[Path, str]]:
    grouped: dict[str, list[tuple[Path, str]]] = {kind: [] for kind in ARTIFACT_KINDS}
    for kind, path, relative in _iter_kicad_files(root):
        grouped[kind].append((path, relative))
    chosen: dict[str, tuple[Path, str]] = {}
    for kind in ARTIFACT_KINDS:
        rows = grouped[kind]
        if not rows:
            continue
        preferred = [row for row in rows if row[1].startswith("build_compilation/")]
        pool = preferred or rows
        pool.sort(key=lambda row: row[1])
        chosen[kind] = pool[0]
    return chosen


def _usable_build_dir(raw: str) -> Path | None:
    path = _lexical_absolute(Path(raw).expanduser())
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return None
    try:
        assert_build_dir_allowed(path)
    except ValueError:
        return None
    return path


def _pin_payload(
    *,
    project_id: str,
    revision: int,
    basis: str,
    artifacts: dict[str, dict[str, Any] | None],
    sidecars: Mapping[str, Mapping[str, dict[str, Any]]] | None = None,
    retained_at: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": PIN_SCHEMA,
        "project_id": project_id,
        "revision": int(revision),
        "retained_at": retained_at or _utc_now(),
        "retention_basis": basis,
        "artifacts": {
            "schematic": artifacts.get("schematic"),
            "pcb": artifacts.get("pcb"),
        },
    }
    if sidecars:
        payload["sidecars"] = {kind: dict(entries) for kind, entries in sidecars.items() if entries}
    return payload


def _pin_bytes(pin: Mapping[str, Any]) -> bytes:
    return (json.dumps(pin, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _corrupt_pin() -> ArtifactIntegrityError:
    return ArtifactIntegrityError("artifact pin is corrupt")


def _pin_relative_ok(relative: str) -> bool:
    """Reject traversal and absolute paths on any platform."""

    if not relative or relative.strip() == "":
        return False
    if any(ord(char) < 32 for char in relative):
        return False
    if relative.startswith(("/", "\\")):
        return False
    if len(relative) >= 2 and relative[0].isalpha() and relative[1] == ":":
        return False
    segments = relative.replace("\\", "/").split("/")
    if any(segment == ".." for segment in segments):
        return False
    return True


def _validate_retained_at(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise _corrupt_pin()
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise _corrupt_pin() from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _corrupt_pin()
    if parsed.utcoffset() != timedelta(0):
        raise _corrupt_pin()
    return value


def _validate_pin_entry(entry: Any) -> dict[str, Any] | None:
    if entry is None:
        return None
    if not isinstance(entry, Mapping):
        raise _corrupt_pin()
    relative = entry.get("relative")
    digest = entry.get("sha256")
    size = entry.get("size_bytes")
    if not isinstance(relative, str) or not _pin_relative_ok(relative):
        raise _corrupt_pin()
    if not isinstance(digest, str) or not _PIN_SHA256_RE.fullmatch(digest):
        raise _corrupt_pin()
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise _corrupt_pin()
    return {"relative": relative, "sha256": digest, "size_bytes": size}


def _validate_pin(pin: Mapping[str, Any], *, project_id: str, revision: int) -> dict[str, Any]:
    if not isinstance(pin, Mapping):
        raise _corrupt_pin()
    if pin.get("schema_version") != PIN_SCHEMA:
        raise _corrupt_pin()
    if pin.get("project_id") != project_id:
        raise _corrupt_pin()
    raw_revision = pin.get("revision")
    if isinstance(raw_revision, bool) or not isinstance(raw_revision, int):
        raise _corrupt_pin()
    if raw_revision != revision:
        raise _corrupt_pin()
    if pin.get("retention_basis") not in RETENTION_BASES:
        raise _corrupt_pin()
    _validate_retained_at(pin.get("retained_at"))
    artifacts = pin.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != {"schematic", "pcb"}:
        raise _corrupt_pin()
    body = dict(pin)
    body["artifacts"] = {
        "schematic": _validate_pin_entry(artifacts.get("schematic")),
        "pcb": _validate_pin_entry(artifacts.get("pcb")),
    }
    if "sidecars" in pin:
        sidecars = pin["sidecars"]
        if not isinstance(sidecars, Mapping) or set(sidecars) - set(ARTIFACT_KINDS):
            raise _corrupt_pin()
        validated = {}
        for kind, entries in sidecars.items():
            primary = body["artifacts"].get(kind)
            if (primary is None or not isinstance(entries, Mapping)
                    or not entries or set(entries) - set(ARTIFACT_SIDECARS)):
                raise _corrupt_pin()
            validated[kind] = {}
            for role, raw in entries.items():
                entry = _validate_pin_entry(raw)
                expected = str(PurePosixPath(primary["relative"].replace("\\", "/")).with_suffix(ARTIFACT_SIDECARS[role]))
                if entry is None or entry["relative"] != expected:
                    raise _corrupt_pin()
                validated[kind][role] = entry
        body["sidecars"] = validated
    return body


def load_artifact_pin(store: ProjectStore, project_id: str, revision: int) -> dict[str, Any] | None:
    path = _pin_path(store, project_id, revision)
    if not path.is_file() or _is_symlink(path):
        return None
    try:
        payload = json.loads(_read_regular_file(path, limit=max_kicad_content_bytes()).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError("artifact pin is corrupt") from exc
    if not isinstance(payload, dict):
        raise ArtifactIntegrityError("artifact pin is corrupt")
    safe_id = validate_project_id(project_id)
    try:
        requested = int(revision)
        return _validate_pin(payload, project_id=safe_id, revision=requested)
    except ArtifactIntegrityError:
        raise
    except (TypeError, ValueError) as exc:
        raise ArtifactIntegrityError("artifact pin is corrupt") from exc


def _artifacts_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return (left.get("artifacts") == right.get("artifacts")
            and left.get("sidecars", {}) == right.get("sidecars", {}))


def _write_pin(store: ProjectStore, pin: Mapping[str, Any]) -> dict[str, Any]:
    project_id = str(pin["project_id"])
    revision = int(pin["revision"])
    path = _pin_path(store, project_id, revision)
    payload = _pin_bytes(pin)
    created = _write_create_only(path, payload)
    if created:
        return dict(pin)
    existing = load_artifact_pin(store, project_id, revision)
    if existing is None:
        raise ArtifactIntegrityError("artifact pin is corrupt")
    if _artifacts_equal(existing, pin):
        return existing
    raise ArtifactPinConflict("revision already pinned to different artifacts")


def retain_revision_artifacts(
    store: ProjectStore,
    project_id: str,
    revision: int,
    *,
    basis: str,
) -> dict[str, Any] | None:
    """Pin KiCad bytes currently reachable from a revision snapshot.

    Returns None when the snapshot has no usable build dir or no KiCad files.
    Never fabricates artifacts and never rewrites revision JSON.
    """

    if basis not in RETENTION_BASES:
        raise ValueError("retention_basis must be at_save or after_save")
    envelope = store.load(project_id, revision=int(revision))
    snapshot = envelope.get("snapshot")
    if not isinstance(snapshot, Mapping):
        return None
    raw_dir = derive_snapshot_build_dir(snapshot)
    if not raw_dir:
        return None
    root = _usable_build_dir(raw_dir)
    if root is None:
        return None
    chosen = _pick_kicad_files(root)
    if not chosen:
        return None

    limit = max_kicad_content_bytes()
    artifacts: dict[str, dict[str, Any] | None] = {"schematic": None, "pcb": None}
    sidecars: dict[str, dict[str, dict[str, Any]]] = {}
    stored_any = False
    for kind in ARTIFACT_KINDS:
        selected = chosen.get(kind)
        if selected is None:
            continue
        path, relative = selected
        try:
            content = _read_regular_file(path, limit=limit)
        except (OSError, ValueError):
            continue
        digest = _store_blob(store, envelope["project_id"], content)
        artifacts[kind] = {
            "relative": relative,
            "sha256": digest,
            "size_bytes": len(content),
        }
        for role, suffix in ARTIFACT_SIDECARS.items():
            companion = path.with_suffix(suffix)
            if not os.path.lexists(companion):
                continue
            try:
                companion_bytes = _read_regular_file(companion, limit=limit)
            except (OSError, ValueError) as exc:
                raise ArtifactRetentionError("matching KiCad rule sidecar is unreadable") from exc
            sidecars.setdefault(kind, {})[role] = {
                "relative": companion.relative_to(root).as_posix(),
                "sha256": _store_blob(store, envelope["project_id"], companion_bytes),
                "size_bytes": len(companion_bytes),
            }
        stored_any = True
    if not stored_any:
        return None
    return _write_pin(
        store,
        _pin_payload(
            project_id=str(envelope["project_id"]),
            revision=int(envelope["revision"]),
            basis=basis,
            artifacts=artifacts,
            sidecars=sidecars,
        ),
    )


def read_pinned_artifact_bytes(
    store: ProjectStore,
    project_id: str,
    revision: int,
    kind: str,
) -> tuple[bytes, dict[str, Any]] | None:
    """Return ``(exact_bytes, pin_entry)``, hash-verified, or None when the pin/entry is absent."""

    if kind not in ARTIFACT_KINDS:
        raise ValueError("kind must be schematic or pcb")
    pin = load_artifact_pin(store, project_id, revision)
    if pin is None:
        return None
    entry = pin.get("artifacts", {}).get(kind)
    if entry is None:
        return None
    if not isinstance(entry, Mapping):
        raise ArtifactIntegrityError("artifact pin is corrupt")
    digest = entry.get("sha256")
    if not isinstance(digest, str) or not _PIN_SHA256_RE.fullmatch(digest):
        raise ArtifactIntegrityError("artifact pin is corrupt")
    data = _read_blob(store, project_id, digest.split(":", 1)[1])
    public = dict(entry)
    public["retention_basis"] = pin.get("retention_basis")
    return data, public


def read_pinned_artifact_sidecars(
    store: ProjectStore,
    project_id: str,
    revision: int,
    kind: str,
) -> dict[str, tuple[bytes, dict[str, Any]]]:
    """Read only this artifact's exact-stem project/rules, never referenced files.

    Old revision pins have no companions and return an empty mapping. Every
    returned byte string is read from its immutable content-addressed blob.
    """
    if kind not in ARTIFACT_KINDS:
        raise ValueError("kind must be schematic or pcb")
    pin = load_artifact_pin(store, project_id, revision)
    if pin is None:
        return {}
    result = {}
    for role, entry in pin.get("sidecars", {}).get(kind, {}).items():
        data = _read_blob(store, project_id, entry["sha256"].split(":", 1)[1])
        if len(data) != entry["size_bytes"]:
            raise ArtifactIntegrityError("retained sidecar size differs from its pin")
        public = {**entry, "retention_basis": pin["retention_basis"]}
        result[role] = data, public
    return result


def read_pinned_artifact(
    store: ProjectStore,
    project_id: str,
    revision: int,
    kind: str,
) -> tuple[str, dict[str, Any]] | None:
    """Return ``(text, pin_entry)`` or None when the pin/entry is absent. The text is decoded leniently."""

    pinned = read_pinned_artifact_bytes(store, project_id, revision, kind)
    if pinned is None:
        return None
    data, public = pinned
    return data.decode("utf-8", errors="replace"), public


def _safe_reason(exc: BaseException) -> str:
    if isinstance(exc, (ArtifactPinConflict, ArtifactIntegrityError, ValueError, TypeError)):
        text = str(exc).strip() or exc.__class__.__name__
        if "/" in text or "\\" in text:
            return exc.__class__.__name__
        return text[:160]
    return exc.__class__.__name__


def best_effort_retain_revision_artifacts(
    store: ProjectStore,
    project_id: str,
    revision: int,
    *,
    basis: str = "at_save",
) -> dict[str, str]:
    """Retain after a successful save. Never raises; never alters the save."""

    try:
        pin = retain_revision_artifacts(store, project_id, revision, basis=basis)
    except Exception as exc:
        return {"status": "failed", "reason": _safe_reason(exc)}
    if pin is None:
        return {"status": "skipped", "reason": "no usable build dir or KiCad artifacts"}
    return {"status": "retained", "reason": "revision artifacts pinned"}


def _record_retention_result(
    store: ProjectStore,
    project_id: str,
    revision: int,
    result: Mapping[str, str],
) -> None:
    results = getattr(store, "_hs_retention_results", None)
    if results is None:
        results = {}
        store._hs_retention_results = results
    key = (str(project_id), int(revision))
    if key in results:
        results.pop(key)
    results[key] = dict(result)
    while len(results) > _MAX_RETENTION_RESULTS:
        results.pop(next(iter(results)))


def recorded_retention_result(
    store: ProjectStore,
    project_id: str,
    revision: int,
) -> dict[str, str] | None:
    results = getattr(store, "_hs_retention_results", None)
    if not isinstance(results, dict):
        return None
    found = results.get((str(project_id), int(revision)))
    return dict(found) if isinstance(found, Mapping) else None


def retention_after_save(
    store: ProjectStore,
    project_id: str,
    revision: int,
    *,
    basis: str = "at_save",
) -> dict[str, str]:
    """Use a wrapped save's recorded outcome, or retain when the store is bare."""

    if getattr(store, "_hs_artifact_retention_wrapped", False):
        recorded = recorded_retention_result(store, project_id, revision)
        if recorded is not None:
            return recorded
        return {"status": "skipped", "reason": "no usable build dir or KiCad artifacts"}
    return best_effort_retain_revision_artifacts(store, project_id, revision, basis=basis)


def install_at_save_retention(store: ProjectStore) -> ProjectStore:
    """Wrap ``store.save`` so every new product-API revision is retained."""

    if getattr(store, "_hs_artifact_retention_wrapped", False):
        return store
    original_save = store.save

    def save(*args: Any, **kwargs: Any) -> Any:
        envelope = original_save(*args, **kwargs)
        try:
            project_id = str(envelope["project_id"])
            revision = int(envelope["revision"])
            result = best_effort_retain_revision_artifacts(
                store,
                project_id,
                revision,
                basis="at_save",
            )
            _record_retention_result(store, project_id, revision, result)
        except Exception:
            pass
        return envelope

    store.save = save  # type: ignore[method-assign]
    store._hs_artifact_retention_wrapped = True
    if not hasattr(store, "_hs_retention_results"):
        store._hs_retention_results = {}
    return store
