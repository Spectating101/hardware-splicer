"""Human-scoped authority records for physical fabrication operators.

Mission acceptance authorizes Hardware Splicer's software-only checks. It does
not authorize a machine to move, heat, cut, print, flash, or energise anything.
A physical operator gets a separate, short-lived, one-shot grant bound to the
exact mission, operator, action and artifact hash it may act on.

The grant id is a reference, not a secret. Authentication of the human who
requests a grant belongs at the API/operator boundary; this store deliberately
has no agent-facing mint path.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

try:
    import fcntl
except ImportError:  # pragma: no cover - production deployment is POSIX today.
    fcntl = None

_GRANT_SCHEMA = "hardware_splicer.fabrication_grant.v1"
_PHYSICAL_ACTIONS = frozenset({"start", "resume"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class FabricationAuthorityError(RuntimeError):
    """The requested physical action does not have valid human authority."""


class FabricationGrantNotFound(FabricationAuthorityError, FileNotFoundError):
    pass


class FabricationValidationError(FabricationAuthorityError, ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise FabricationAuthorityError("fabrication grant has an invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise FabricationAuthorityError("fabrication grant timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value.strip()):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return value.strip()


def _artifact_sha(value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value.lower().strip()):
        raise FabricationValidationError("artifact_sha256 must be a lowercase SHA-256 digest")
    return value.lower().strip()


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class FabricationGrantStore:
    """Persistent one-shot authority for physical start/resume operations.

    The store is intentionally separate from FabricationMission acceptance.
    Only a caller already authenticated as a human operator should be allowed
    to invoke :meth:`issue`. Agent/MCP surfaces should expose grant *use*, not
    grant minting.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.root / ".fabrication-grants.lock"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._lock_path.touch(exist_ok=True)
        with self._lock_path.open("r+") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _path(self, grant_id: str) -> Path:
        return self.root / f"{_identifier(grant_id, field='grant_id')}.json"

    def issue(
        self,
        *,
        project_id: str,
        mission_id: str,
        operator_id: str,
        action: str,
        artifact_sha256: str,
        author: Mapping[str, Any],
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        """Mint one bounded physical grant for an authenticated human.

        Fifteen minutes is the default approval window. Callers may choose a
        shorter window; one hour is the hard ceiling so old browser approvals
        cannot silently remain live for a later fabrication session.
        """

        if not isinstance(author, Mapping) or author.get("kind") != "human":
            raise FabricationAuthorityError("only a human operator may issue physical fabrication authority")
        human_id = _identifier(author.get("id"), field="author.id")
        if action not in _PHYSICAL_ACTIONS:
            raise FabricationValidationError("physical grant action must be 'start' or 'resume'")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise FabricationValidationError("ttl_seconds must be an integer from 1 to 3600")

        now = _utc_now()
        record = {
            "schema": _GRANT_SCHEMA,
            "grant_id": f"fg-{uuid.uuid4().hex}",
            "project_id": _identifier(project_id, field="project_id"),
            "mission_id": _identifier(mission_id, field="mission_id"),
            "operator_id": _identifier(operator_id, field="operator_id"),
            "action": action,
            "artifact_sha256": _artifact_sha(artifact_sha256),
            "issued_by": {"kind": "human", "id": human_id},
            "issued_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=ttl_seconds)),
            "consumed_at": None,
        }
        with self._locked():
            path = self._path(record["grant_id"])
            if path.exists():  # UUID collision: fail closed instead of replacing authority.
                raise FabricationAuthorityError("fabrication grant id collision")
            _atomic_write(path, record)
        return json.loads(json.dumps(record))

    def get(self, grant_id: str) -> dict[str, Any]:
        path = self._path(grant_id)
        if not path.exists():
            raise FabricationGrantNotFound(f"fabrication grant {grant_id!r} does not exist")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FabricationAuthorityError("cannot read fabrication grant") from exc
        if not isinstance(value, dict) or value.get("schema") != _GRANT_SCHEMA:
            raise FabricationAuthorityError("fabrication grant record is invalid")
        return value

    def consume(
        self,
        grant_id: str,
        *,
        project_id: str,
        mission_id: str,
        operator_id: str,
        action: str,
        artifact_sha256: str,
    ) -> dict[str, Any]:
        """Consume authority before issuing the physical command.

        A failed or ambiguous network request therefore leaves the grant spent.
        Retrying a physical start always requires a fresh human decision rather
        than risking a duplicate start after the machine acted but the response
        was lost.
        """

        expected = {
            "project_id": _identifier(project_id, field="project_id"),
            "mission_id": _identifier(mission_id, field="mission_id"),
            "operator_id": _identifier(operator_id, field="operator_id"),
            "action": action,
            "artifact_sha256": _artifact_sha(artifact_sha256),
        }
        if action not in _PHYSICAL_ACTIONS:
            raise FabricationValidationError("physical grant action must be 'start' or 'resume'")

        with self._locked():
            record = self.get(grant_id)
            if record.get("consumed_at") is not None:
                raise FabricationAuthorityError("fabrication grant has already been consumed")
            if _parse_time(record.get("expires_at")) <= _utc_now():
                raise FabricationAuthorityError("fabrication grant has expired")
            for key, value in expected.items():
                if record.get(key) != value:
                    raise FabricationAuthorityError(f"fabrication grant does not authorize this {key}")
            record["consumed_at"] = _iso(_utc_now())
            _atomic_write(self._path(grant_id), record)
            return json.loads(json.dumps(record))
