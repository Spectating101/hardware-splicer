"""One-shot human authority for generic physical execution plans.

Printer-specific grants predate the generic physical-operator layer.  This
store is the general contract: the human approves one exact server-created
PhysicalExecutionPlan, not an agent-authored command or a vague machine name.
The grant is consumed before dispatch so ambiguous transport failures cannot be
automatically replayed.
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
except ImportError:  # pragma: no cover
    fcntl = None

from .fabrication_operator import FabricationAuthorityError, FabricationValidationError
from .physical_operator import PhysicalExecutionPlan, canonical_payload_sha256

_SCHEMA = "hardware_splicer.physical_plan_grant.v1"
_GRANT_ID_RE = re.compile(r"^pg-[0-9a-f]{32}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: Any) -> datetime:
    if not isinstance(value, str):
        raise FabricationAuthorityError("physical grant timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FabricationAuthorityError("physical grant timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise FabricationAuthorityError("physical grant timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def execution_plan_sha256(plan: PhysicalExecutionPlan) -> str:
    """Hash one internally consistent server-created execution plan.

    ``PhysicalExecutionPlan`` is frozen, but its nested payload is a mapping and
    could otherwise be mutated after construction.  Every authority/dispatch
    path that calls this helper therefore re-hashes the payload and refuses a
    plan whose stored payload digest no longer matches its actual contents.
    """

    if not isinstance(plan, PhysicalExecutionPlan):
        raise FabricationValidationError("physical authority requires a server-created execution plan")
    actual_payload_sha256 = canonical_payload_sha256(plan.payload)
    if actual_payload_sha256 != plan.payload_sha256:
        raise FabricationValidationError("physical execution plan payload hash does not match payload")
    return canonical_payload_sha256(plan.to_dict())


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


class PhysicalPlanGrantStore:
    """Persistent human approval for one exact actuation plan."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.root / ".physical-plan-grants.lock"

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
        if not isinstance(grant_id, str) or not _GRANT_ID_RE.fullmatch(grant_id):
            raise FabricationValidationError("physical plan grant id is invalid")
        return self.root / f"{grant_id}.json"

    def issue(
        self,
        plan: PhysicalExecutionPlan,
        *,
        author: Mapping[str, Any],
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan) or not plan.requires_human_grant:
            raise FabricationAuthorityError("only actuation plans receive physical authority")
        if not isinstance(author, Mapping) or author.get("kind") != "human":
            raise FabricationAuthorityError("only a human may authorize physical actuation")
        human_id = author.get("id")
        if not isinstance(human_id, str) or not human_id.strip():
            raise FabricationValidationError("human author id is required")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise FabricationValidationError("ttl_seconds must be an integer from 1 to 3600")

        plan_sha256 = execution_plan_sha256(plan)
        now = _utc_now()
        record = {
            "schema": _SCHEMA,
            "grant_id": f"pg-{uuid.uuid4().hex}",
            "project_id": plan.project_id,
            "mission_id": plan.mission_id,
            "operator_id": plan.operator_id,
            "operator_kind": plan.operator_kind,
            "action": plan.action,
            "execution_plan_sha256": plan_sha256,
            "payload_sha256": plan.payload_sha256,
            "issued_by": {"kind": "human", "id": human_id.strip()},
            "issued_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=ttl_seconds)),
            "consumed_at": None,
        }
        with self._locked():
            path = self._path(record["grant_id"])
            if path.exists():
                raise FabricationAuthorityError("physical grant id collision")
            _atomic_write(path, record)
        return json.loads(json.dumps(record))

    def get(self, grant_id: str) -> dict[str, Any]:
        path = self._path(grant_id)
        if not path.exists():
            raise FabricationAuthorityError("physical plan grant does not exist")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FabricationAuthorityError("cannot read physical plan grant") from exc
        if not isinstance(value, dict) or value.get("schema") != _SCHEMA:
            raise FabricationAuthorityError("physical plan grant record is invalid")
        return value

    def consume(self, grant_id: str, plan: PhysicalExecutionPlan) -> dict[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan) or not plan.requires_human_grant:
            raise FabricationAuthorityError("grant consumption requires an actuation plan")
        plan_sha256 = execution_plan_sha256(plan)
        expected = {
            "project_id": plan.project_id,
            "mission_id": plan.mission_id,
            "operator_id": plan.operator_id,
            "operator_kind": plan.operator_kind,
            "action": plan.action,
            "execution_plan_sha256": plan_sha256,
            "payload_sha256": plan.payload_sha256,
        }
        with self._locked():
            record = self.get(grant_id)
            if record.get("consumed_at") is not None:
                raise FabricationAuthorityError("physical plan grant has already been consumed")
            if _parse(record.get("expires_at")) <= _utc_now():
                raise FabricationAuthorityError("physical plan grant has expired")
            for key, value in expected.items():
                if record.get(key) != value:
                    raise FabricationAuthorityError(f"physical plan grant does not authorize this {key}")
            record["consumed_at"] = _iso(_utc_now())
            _atomic_write(self._path(grant_id), record)
            return json.loads(json.dumps(record))
