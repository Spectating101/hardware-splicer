"""Persistent approval requests connecting agents to human physical authority.

Agents may request approval for an exact server-created actuation plan.  They
cannot approve the request.  A human-side API may approve it, which revalidates
the stored plan against the current server operator registry and then mints a
one-shot PhysicalPlanGrant.  Grant ids are references, not authentication
secrets; they authorize only the exact plan digest already approved.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from .fabrication_operator import FabricationAuthorityError, FabricationValidationError
from .physical_authority import PhysicalPlanGrantStore, execution_plan_sha256
from .physical_operator import PhysicalExecutionPlan, PhysicalOperatorRegistry

_SCHEMA = "hardware_splicer.physical_approval_request.v1"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class PhysicalApprovalStore:
    def __init__(
        self,
        root: str | Path,
        *,
        operators: PhysicalOperatorRegistry,
        grants: PhysicalPlanGrantStore,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.operators = operators
        self.grants = grants
        self._lock_path = self.root / ".physical-approvals.lock"

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

    def request(self, plan: PhysicalExecutionPlan, *, requested_by: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan) or not plan.requires_human_grant:
            raise FabricationValidationError("approval requests require a server-created actuation plan")
        if not isinstance(requested_by, Mapping) or requested_by.get("kind") not in {"agent", "system", "human"}:
            raise FabricationValidationError("approval requester kind is invalid")
        requester_id = requested_by.get("id")
        if not isinstance(requester_id, str) or not requester_id.strip():
            raise FabricationValidationError("approval requester id is required")

        canonical = self.operators.plan(
            operator_id=plan.operator_id,
            project_id=plan.project_id,
            mission_id=plan.mission_id,
            action=plan.action,
            payload=plan.payload,
        )
        if execution_plan_sha256(canonical) != execution_plan_sha256(plan):
            raise FabricationValidationError("approval plan does not match current operator registry")

        request_id = f"pa-{uuid.uuid4().hex}"
        record = {
            "schema": _SCHEMA,
            "request_id": request_id,
            "status": "pending",
            "requested_by": {"kind": requested_by["kind"], "id": requester_id.strip()},
            "requested_at": _iso_now(),
            "execution_plan": canonical.to_dict(),
            "execution_plan_sha256": execution_plan_sha256(canonical),
            "approved_by": None,
            "approved_at": None,
            "grant_id": None,
        }
        with self._locked():
            path = self._path(request_id)
            if path.exists():
                raise FabricationAuthorityError("physical approval request id collision")
            _atomic_write(path, record)
        return json.loads(json.dumps(record))

    def get(self, request_id: str) -> dict[str, Any]:
        path = self._path(request_id)
        if not path.exists():
            raise FabricationValidationError("physical approval request does not exist")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FabricationValidationError("cannot read physical approval request") from exc
        if not isinstance(value, dict) or value.get("schema") != _SCHEMA:
            raise FabricationValidationError("physical approval request is invalid")
        return value

    def list_pending(self) -> list[dict[str, Any]]:
        values = []
        for path in sorted(self.root.glob("pa-*.json")):
            try:
                value = self.get(path.stem)
            except FabricationValidationError:
                continue
            if value.get("status") == "pending":
                values.append(value)
        return values

    def approve(
        self,
        request_id: str,
        *,
        author: Mapping[str, Any],
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        if not isinstance(author, Mapping) or author.get("kind") != "human":
            raise FabricationAuthorityError("only a human may approve physical actuation")
        human_id = author.get("id")
        if not isinstance(human_id, str) or not human_id.strip():
            raise FabricationValidationError("human author id is required")

        with self._locked():
            record = self.get(request_id)
            if record.get("status") != "pending":
                raise FabricationAuthorityError("physical approval request is no longer pending")
            plan = self._revalidate_plan(record)
            grant = self.grants.issue(
                plan,
                author={"kind": "human", "id": human_id.strip()},
                ttl_seconds=ttl_seconds,
            )
            record["status"] = "approved"
            record["approved_by"] = {"kind": "human", "id": human_id.strip()}
            record["approved_at"] = _iso_now()
            record["grant_id"] = grant["grant_id"]
            _atomic_write(self._path(request_id), record)
        return json.loads(json.dumps(record))

    def reject(self, request_id: str, *, author: Mapping[str, Any], reason: str) -> dict[str, Any]:
        if not isinstance(author, Mapping) or author.get("kind") != "human":
            raise FabricationAuthorityError("only a human may reject physical actuation")
        human_id = author.get("id")
        if not isinstance(human_id, str) or not human_id.strip():
            raise FabricationValidationError("human author id is required")
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
            raise FabricationValidationError("rejection reason must be a bounded string")

        with self._locked():
            record = self.get(request_id)
            if record.get("status") != "pending":
                raise FabricationAuthorityError("physical approval request is no longer pending")
            record["status"] = "rejected"
            record["approved_by"] = {"kind": "human", "id": human_id.strip()}
            record["approved_at"] = _iso_now()
            record["rejection_reason"] = reason.strip()
            _atomic_write(self._path(request_id), record)
        return json.loads(json.dumps(record))

    def _revalidate_plan(self, record: Mapping[str, Any]) -> PhysicalExecutionPlan:
        value = record.get("execution_plan")
        if not isinstance(value, Mapping):
            raise FabricationValidationError("approval request has no execution plan")
        plan = self.operators.plan(
            operator_id=value.get("operator_id"),
            project_id=value.get("project_id"),
            mission_id=value.get("mission_id"),
            action=value.get("action"),
            payload=value.get("payload") or {},
        )
        if execution_plan_sha256(plan) != record.get("execution_plan_sha256"):
            raise FabricationValidationError("approval execution plan has changed or is corrupt")
        return plan

    def _path(self, request_id: str) -> Path:
        if not isinstance(request_id, str) or not request_id.startswith("pa-") or "/" in request_id or "\\" in request_id:
            raise FabricationValidationError("physical approval request id is invalid")
        return self.root / f"{request_id}.json"
