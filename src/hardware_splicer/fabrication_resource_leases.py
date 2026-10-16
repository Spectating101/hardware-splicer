"""Plan-bound leases preventing concurrent agent claims on lab resources.

A lease reserves a scheduled resource for one exact workflow task. It is not a
physical execution grant and cannot start/energize/move a machine. The store is
thread-safe and expires stale leases so software agents cannot permanently lock
a resource after crashing.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError


@dataclass(frozen=True)
class ResourceLease:
    lease_id: str
    plan_id: str
    plan_sha256: str
    workflow_id: str
    task_id: str
    resource_id: str
    holder_id: str
    acquired_at: str
    expires_at: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema": "hardware_splicer.fabrication_resource_lease.v1",
            **asdict(self),
            "grants_physical_authority": False,
            "physical_execution_authorized": False,
        }


class WorkflowPlanRegistry:
    def __init__(self) -> None:
        self._plans: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(plan, Mapping) or plan.get("schema") != "hardware_splicer.fabrication_workflow_plan.v1":
            raise FabricationValidationError("workflow plan has unsupported schema")
        plan_id = _id(plan.get("plan_id"), "plan_id")
        digest = plan.get("plan_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise FabricationValidationError("workflow plan is missing SHA-256")
        normalized = _copy(plan)
        with self._lock:
            existing = self._plans.get(plan_id)
            if existing is not None and existing != normalized:
                raise FabricationValidationError("workflow plan id collision")
            self._plans[plan_id] = normalized
        return _copy(normalized)

    def get(self, plan_id: str) -> dict[str, Any]:
        key = _id(plan_id, "plan_id")
        with self._lock:
            try:
                return _copy(self._plans[key])
            except KeyError as exc:
                raise FabricationValidationError("unknown workflow plan id") from exc


class ResourceLeaseStore:
    def __init__(self, *, plans: WorkflowPlanRegistry) -> None:
        self.plans = plans
        self._leases: dict[str, ResourceLease] = {}
        self._lock = threading.RLock()

    def acquire(
        self,
        *,
        plan_id: str,
        task_id: str,
        holder_id: str,
        ttl_seconds: int = 900,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if type(ttl_seconds) is not int or not 30 <= ttl_seconds <= 24 * 3600:
            raise FabricationValidationError("resource lease ttl_seconds must be 30..86400")
        holder = _id(holder_id, "holder_id")
        task = _id(task_id, "task_id")
        plan = self.plans.get(plan_id)
        task_rows = [row for row in plan.get("tasks") or [] if row.get("task_id") == task]
        if len(task_rows) != 1:
            raise FabricationValidationError("task is not uniquely scheduled in workflow plan")
        row = task_rows[0]
        resource_id = _id(row.get("resource_id"), "resource_id")
        stamp = _utc(now or datetime.now(timezone.utc))
        with self._lock:
            self._prune(stamp)
            for lease in self._leases.values():
                if lease.resource_id == resource_id:
                    raise FabricationValidationError(
                        f"resource {resource_id!r} is already leased by another workflow task"
                    )
            lease = ResourceLease(
                lease_id=f"lease-{uuid.uuid4().hex}",
                plan_id=plan["plan_id"],
                plan_sha256=plan["plan_sha256"],
                workflow_id=plan["workflow_id"],
                task_id=task,
                resource_id=resource_id,
                holder_id=holder,
                acquired_at=stamp.isoformat(),
                expires_at=(stamp + timedelta(seconds=ttl_seconds)).isoformat(),
            )
            self._leases[lease.lease_id] = lease
            return lease.public_dict()

    def release(self, lease_id: str, *, holder_id: str) -> dict[str, Any]:
        key = _id(lease_id, "lease_id")
        holder = _id(holder_id, "holder_id")
        with self._lock:
            try:
                lease = self._leases[key]
            except KeyError as exc:
                raise FabricationValidationError("unknown resource lease") from exc
            if lease.holder_id != holder:
                raise FabricationValidationError("resource lease belongs to a different holder")
            del self._leases[key]
            return {"ok": True, "lease_id": key, "released": True, "grants_physical_authority": False}

    def list_public(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        stamp = _utc(now or datetime.now(timezone.utc))
        with self._lock:
            self._prune(stamp)
            return [lease.public_dict() for lease in sorted(self._leases.values(), key=lambda item: item.lease_id)]

    def _prune(self, now: datetime) -> None:
        expired = [
            lease_id
            for lease_id, lease in self._leases.items()
            if datetime.fromisoformat(lease.expires_at).astimezone(timezone.utc) <= now
        ]
        for lease_id in expired:
            del self._leases[lease_id]


def _copy(value: Mapping[str, Any]) -> dict[str, Any]:
    import json

    try:
        return json.loads(json.dumps(dict(value), sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("workflow plan must be canonical JSON") from exc


def _utc(value: datetime) -> datetime:
    return (value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
