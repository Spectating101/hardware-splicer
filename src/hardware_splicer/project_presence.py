"""Ephemeral, information-only presence for a machine project.

Presence never changes a snapshot, revision, review, thread, or authority
field. Names are self-declared unless an operator token verifies them. The
``presence/`` directory is excluded from project byte-invariance.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .operator_identity import OperatorIdentity

MAX_PRESENCE_FILES = 200
MAX_LISTED_PARTICIPANTS = 100
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
PRESENCE_MODES = frozenset({"review", "compare", "verify", "bringup", "other"})
_ALLOWED_KEYS = frozenset({"client_id", "name", "object_id", "mode"})
_AUTHORITY_KEYS = frozenset(
    {"authority", "release", "fabrication", "power_on", "status", "revision_override"}
)
_TTL_ENV = "HARDWARE_SPLICER_PRESENCE_TTL_SECONDS"
_TTL_DEFAULT = 45
_TTL_MIN = 5
_TTL_MAX = 600
_MAX_NAME = 80
_MAX_OBJECT_ID = 200


class PresenceError(RuntimeError):
    pass


class PresenceValidationError(PresenceError, ValueError):
    pass


class PresenceLimitError(PresenceError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def presence_ttl_seconds() -> int:
    raw = os.environ.get(_TTL_ENV)
    try:
        value = _TTL_DEFAULT if raw is None or str(raw).strip() == "" else int(raw)
    except (TypeError, ValueError):
        value = _TTL_DEFAULT
    return min(_TTL_MAX, max(_TTL_MIN, value))


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def _is_forbidden_key(key: Any) -> bool:
    raw = str(key)
    lowered = raw.lower()
    return "authoriz" in lowered or lowered in _AUTHORITY_KEYS


def _reject_authority_keys(value: Mapping[str, Any], *, label: str) -> None:
    for key, nested in value.items():
        if _is_forbidden_key(key):
            raise PresenceValidationError(f"{label} must not contain authority field {key!r}")
        if isinstance(nested, Mapping):
            _reject_authority_keys(nested, label=f"{label}.{key}")


def _has_control_chars(value: str) -> bool:
    return any(unicodedata.category(ch).startswith("C") for ch in value)


def _json_payload(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    if _is_symlink(path) or _is_symlink(path.parent):
        raise PresenceError("presence path must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_payload(value)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _presence_dir(project_dir: str | Path) -> Path:
    return Path(project_dir) / "presence"


def validate_client_id(client_id: Any) -> str:
    if not isinstance(client_id, str) or not CLIENT_ID_RE.fullmatch(client_id):
        raise PresenceValidationError("client_id must match ^[A-Za-z0-9_-]{8,64}$")
    return client_id


def _optional_text(value: Any, *, field: str, max_len: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PresenceValidationError(f"{field} must be a string")
    if len(value) > max_len:
        raise PresenceValidationError(f"{field} must be at most {max_len} characters")
    if field == "name" and _has_control_chars(value):
        raise PresenceValidationError("name must not contain control characters")
    return value


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise PresenceValidationError("request must be an object")
    _reject_authority_keys(payload, label="request")
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise PresenceValidationError("request contains unknown fields")
    client_id = validate_client_id(payload.get("client_id"))
    name = _optional_text(payload.get("name"), field="name", max_len=_MAX_NAME)
    object_id = _optional_text(payload.get("object_id"), field="object_id", max_len=_MAX_OBJECT_ID)
    mode = payload.get("mode")
    if mode is None:
        normalized_mode = None
    elif mode not in PRESENCE_MODES:
        raise PresenceValidationError("mode must be review, compare, verify, bringup, or other")
    else:
        normalized_mode = str(mode)
    return {
        "client_id": client_id,
        "name": name,
        "object_id": object_id,
        "mode": normalized_mode,
    }


def _count_presence_files(directory: Path) -> int:
    count = 0
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entry.name.startswith("."):
                    continue
                try:
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if entry.name.endswith(".json"):
                    count += 1
    except OSError:
        return 0
    return count


def _parse_seen_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _read_record(path: Path) -> dict[str, Any] | None:
    if _is_symlink(path):
        return None
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        client_id = validate_client_id(payload.get("client_id"))
    except PresenceValidationError:
        return None
    seen_at = _parse_seen_at(payload.get("seen_at"))
    if seen_at is None:
        return None
    operator = payload.get("operator")
    if operator is not None:
        if not isinstance(operator, Mapping) or set(operator) - {"id", "kind"}:
            operator = None
        else:
            operator = {"id": operator.get("id"), "kind": operator.get("kind")}
    return {
        "client_id": client_id,
        "name": payload.get("name"),
        "object_id": payload.get("object_id"),
        "mode": payload.get("mode"),
        "seen_at": seen_at,
        "verified": bool(payload.get("verified")),
        "operator": operator,
        "path": path,
    }


def put_presence(
    project_dir: str | Path,
    payload: Mapping[str, Any],
    *,
    operator: OperatorIdentity | None = None,
) -> dict[str, Any]:
    normalized = _normalize_payload(payload)
    directory = _presence_dir(project_dir)
    if _is_symlink(directory):
        raise PresenceError("presence directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{normalized['client_id']}.json"
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise PresenceError("presence file must not be a symlink")
    replacing = path.is_file()
    if not replacing and _count_presence_files(directory) >= MAX_PRESENCE_FILES:
        raise PresenceLimitError("too many presence entries for this project")

    if operator is not None:
        name = operator.id
        verified = True
        operator_row: dict[str, str] | None = {"id": operator.id, "kind": operator.kind}
    else:
        name = normalized["name"]
        verified = False
        operator_row = None

    record = {
        "client_id": normalized["client_id"],
        "name": name,
        "object_id": normalized["object_id"],
        "mode": normalized["mode"],
        "seen_at": _utc_now().isoformat(),
        "verified": verified,
        "operator": operator_row,
    }
    _atomic_write_json(path, record)
    return {"ok": True, "ttl_seconds": presence_ttl_seconds()}


def list_presence(project_dir: str | Path) -> dict[str, Any]:
    directory = _presence_dir(project_dir)
    ttl = presence_ttl_seconds()
    now = _utc_now()
    participants: list[dict[str, Any]] = []
    if _is_symlink(directory) or not directory.is_dir():
        return {"ok": True, "participants": []}
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return {"ok": True, "participants": []}
    for entry in entries:
        path = Path(entry.path)
        if entry.is_symlink():
            continue
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
        except OSError:
            continue
        record = _read_record(path)
        if record is None:
            continue
        age = (now - record["seen_at"]).total_seconds()
        if age >= ttl * 10:
            try:
                if not path.is_symlink():
                    path.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        if age >= ttl:
            continue
        participants.append(
            {
                "client_id": record["client_id"],
                "name": record["name"],
                "object_id": record["object_id"],
                "mode": record["mode"],
                "verified": record["verified"],
                "operator": record["operator"],
                "seen_seconds_ago": max(0, int(age)),
            }
        )
    participants.sort(key=lambda row: str(row["client_id"]))
    return {"ok": True, "participants": participants[:MAX_LISTED_PARTICIPANTS]}


def delete_presence(project_dir: str | Path, client_id: str) -> dict[str, Any]:
    safe_id = validate_client_id(client_id)
    directory = _presence_dir(project_dir)
    if _is_symlink(directory):
        return {"ok": True}
    path = directory / f"{safe_id}.json"
    if path.is_symlink():
        path.unlink(missing_ok=True)
        return {"ok": True}
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return {"ok": True}
