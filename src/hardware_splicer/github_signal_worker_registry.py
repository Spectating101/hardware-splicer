"""Fail-closed local inventory and capacity scheduler for approved HS remote jobs.

This registers *execution pools*, not physical machines. Only the existing
GitHub Actions job topology has a dispatch transport. A future host runner
must receive a separately reviewed execution adapter before it can be enrolled.
"""
from __future__ import annotations

import contextlib
import copy
import fcntl
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterator

SCHEMA = "hardware_splicer.remote_worker_registry.v1"
WORKER_ID = "github-actions-ubuntu-24.04"
TASK_CAPABILITIES = {
    "review_schematic": "signal-akcli-schematic-review",
    "compare_board_revisions": "signal-kdif-board-revision-diff",
}
DEFAULT_WORKER = {
    "id": WORKER_ID,
    "executor": "github_actions",
    "workflow": "hs-github-signal-capability.yml",
    "runner_label": "ubuntu-24.04",
    "state": "approved",
    "allowed_tasks": sorted(TASK_CAPABILITIES),
    "max_inflight": 2,
    "physical_authority": False,
}
ACTIVE_STATES = frozenset({
    "prepared", "submitted", "awaiting_run_discovery", "remote_running",
    "dispatch_unknown_check_remote_before_retry",
})
JOB_ID = re.compile(r"^hs-[0-9a-f]{16}\.json$")


class RegistryError(ValueError):
    """Missing permissions, invalid inventory, or unavailable worker."""


def _path(ledger: Path) -> Path:
    if ledger.is_symlink():
        raise RegistryError("worker ledger directory cannot be a symlink")
    return ledger / "workers.json"


def _verify_worker(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise RegistryError("worker record is not an object")
    required = set(DEFAULT_WORKER)
    if set(row) != required:
        raise RegistryError("worker record has missing or unexpected fields")
    # This version authorizes only the pre-reviewed GitHub Actions pool.
    for field in ("id", "executor", "workflow", "runner_label"):
        if row[field] != DEFAULT_WORKER[field]:
            raise RegistryError("worker execution transport not approved")
    if row["physical_authority"] is not False:
        raise RegistryError("worker cannot have physical authority")
    if row["state"] not in ("approved", "paused"):
        raise RegistryError("invalid worker state")
    tasks = row["allowed_tasks"]
    if (not isinstance(tasks, list) or len(tasks) != len(set(map(str, tasks)))
            or any(not isinstance(t, str) or t not in TASK_CAPABILITIES for t in tasks)):
        raise RegistryError("unknown or duplicate worker capability")
    if type(row["max_inflight"]) is not int or not 1 <= row["max_inflight"] <= 4:
        raise RegistryError("worker capacity must be between 1 and 4")
    return row


def read_registry(ledger: Path) -> dict[str, Any]:
    path = _path(ledger)
    if path.is_symlink():
        raise RegistryError("worker registry file is unsafe")
    if not path.exists():
        # PR #283's approved backend remains usable without migrating ledgers.
        return {"schema_version": SCHEMA, "workers": [copy.deepcopy(DEFAULT_WORKER)],
                "source": "pr283_approved_github_actions_pool"}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
        raise RegistryError("worker registry file is unsafe")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RegistryError("worker registry JSON invalid") from exc
    if (not isinstance(data, dict) or data.get("schema_version") != SCHEMA
            or data.get("source") != "operator_managed"
            or not isinstance(data.get("workers"), list)
            or len(data["workers"]) != 1):
        raise RegistryError("worker registry schema or worker count invalid")
    _verify_worker(data["workers"][0])
    return data


def configure_worker(
    ledger: Path, *, approve: bool = False, state: str = "approved",
    allowed_tasks: list[str] | None = None, max_inflight: int = 2
) -> dict[str, Any]:
    """Persist an explicitly approved, limited GitHub Actions execution pool.

    This does not register, contact or authorize arbitrary lab equipment.
    """
    if approve is not True:
        raise RegistryError("explicit --approve is required to enroll/configure a worker")
    row = copy.deepcopy(DEFAULT_WORKER)
    row["state"] = state
    row["allowed_tasks"] = sorted(TASK_CAPABILITIES if allowed_tasks is None else allowed_tasks)
    row["max_inflight"] = max_inflight
    _verify_worker(row)
    # Guard every edit and allocation using the same local inter-process lock.
    with allocation_lock(ledger):
        old = read_registry(ledger)
        if old["source"] == "operator_managed":
            # No host identity or transport changes; only pause/capacity/capability narrowing.
            assert old["workers"][0]["id"] == row["id"]
        data = {"schema_version": SCHEMA, "source": "operator_managed",
                "workers": [row]}
        dest = _path(ledger)
        fd, tmp = tempfile.mkstemp(prefix=".workers-", dir=str(ledger), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(data, out, sort_keys=True, indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            if dest.is_symlink():
                raise RegistryError("worker registry symlink is forbidden")
            os.replace(tmp, dest)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return data


@contextlib.contextmanager
def allocation_lock(ledger: Path) -> Iterator[None]:
    """Serialize local configuration and allocation; not a cross-host lease."""
    if ledger.is_symlink():
        raise RegistryError("worker ledger directory cannot be a symlink")
    ledger.mkdir(parents=True, exist_ok=True)
    file = ledger / ".worker-allocation.lock"
    if file.is_symlink():
        raise RegistryError("worker lock symlink is forbidden")
    fd = os.open(str(file), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "r+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    except BaseException:
        raise


def _occupied(ledger: Path, worker_id: str) -> int:
    if not ledger.exists():
        return 0
    inflight = 0
    for path in ledger.iterdir():
        if not JOB_ID.fullmatch(path.name):
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000:
            raise RegistryError("unsafe worker job ledger entry")
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RegistryError("cannot schedule with unreadable job ledger") from exc
        if (not isinstance(job, dict)
                or not isinstance(job.get("request_id"), str)
                or job["request_id"] + ".json" != path.name
                or job.get("schema_version") != "hardware_splicer.github_signal_remote_job.v1"
                or job.get("task") not in TASK_CAPABILITIES):
            raise RegistryError("cannot schedule with unverified job ledger")
        assigned = job.get("worker_id", WORKER_ID)  # pre-registry jobs
        if assigned not in (WORKER_ID,):
            raise RegistryError("unknown worker in existing ledger")
        if assigned == worker_id and job.get("status") in ACTIVE_STATES:
            inflight += 1
    return inflight


def choose_worker(ledger: Path, task: str) -> dict[str, Any]:
    """Admission policy: exact task capability + approval + local capacity."""
    if task not in TASK_CAPABILITIES:
        raise RegistryError("unsupported engineering worker task")
    rows = read_registry(ledger)["workers"]
    eligible = [row for row in rows if
                row["state"] == "approved" and task in row["allowed_tasks"]]
    if not eligible:
        raise RegistryError("no approved worker offers this engineering capability")
    # One approved execution pool today. Explicit ordering makes eventual
    # multiple-pool selection deterministic rather than probabilistic.
    for worker in sorted(eligible, key=lambda x: x["id"]):
        occupied = _occupied(ledger, worker["id"])
        if occupied < worker["max_inflight"]:
            return {
                "schema_version": SCHEMA,
                "worker_id": worker["id"],
                "executor": worker["executor"],
                "capability": TASK_CAPABILITIES[task],
                "allowed_task": task,
                "max_inflight": worker["max_inflight"],
                "inflight_before_assignment": occupied,
                "physical_authority": False,
            }
    raise RegistryError("approved worker is at local in-flight capacity")
