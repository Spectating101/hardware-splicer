"""A narrow HS-controlled remote engineering worker dispatcher over GitHub Actions.

Not a distributed compute cluster. Two fixed, previously reviewed tools,
fixed reference HS input designs, a single allowlisted GitHub workflow, and
no physical device/fabrication authority.

States persist locally; an ambiguous submission is never blindly retried.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .github_signal_pipeline import ADAPTERS, SignalEvaluationError, sha256_file
from .github_signal_task_router import select_task
from .github_signal_worker_registry import (
    WORKER_ID, allocation_lock, choose_worker,
)

SCHEMA = "hardware_splicer.github_signal_remote_job.v1"
REPO = "Spectating101/hardware-splicer"
WORKFLOW = "hs-github-signal-capability.yml"
DEFAULT_REF = "main"
TASKS = {
    "review_schematic": {
        "job_name": "native-reviewed-integration",
        "artifact_name": "HS-GITHUB-SIGNAL-PINNED-AKCLI-REAL-SCHEMATIC-REVIEW",
        "input_path": "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch",
        "source": "tipoLi5890/akcli",
    },
    "compare_board_revisions": {
        "job_name": "native-reviewed-kdif-task",
        "artifact_name": "HS-GITHUB-SIGNAL-KDIF-REAL-HS-BOARD-TASK-SELECTED",
        "input_path": "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb",
        "source": "0x12net/kdif",
    },
}
RID = re.compile(r"^hs-[0-9a-f]{16}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
HASH = re.compile(r"^[0-9a-f]{64}$")


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class WorkerStateError(SignalEvaluationError):
    pass


class GithubCLI:
    """Single approved GitHub account; arguments passed as argv, never a shell."""

    def __init__(self, *, run_fn: Any = subprocess.run):
        self.run_fn = run_fn

    def _call(self, argv: list[str], *, body: Any = None, timeout: int = 45) -> str:
        if body is not None:
            argv = [*argv, "--input", "-"]
        try:
            p = self.run_fn(
                argv, input=(json.dumps(body) if body is not None else None),
                capture_output=True, text=True, check=False, timeout=timeout,
                env={**os.environ, "GH_PROMPT_DISABLED": "1"},
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise WorkerStateError("GitHub CLI operation failed: " + str(exc)[-220:]) from exc
        if p.returncode:
            raise WorkerStateError(
                "GitHub API rejected operation: " + str(p.stderr or "")[-500:]
            )
        return str(p.stdout or "")

    def get(self, path: str) -> dict[str, Any]:
        if not path.startswith("repos/" + REPO + "/"):
            raise WorkerStateError("API route not allowlisted")
        raw = self._call(["gh", "api", "-X", "GET", path])
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise WorkerStateError("invalid GitHub response schema")
        return result

    def dispatch(self, *, task: str, request_id: str) -> None:
        if task not in TASKS or not RID.fullmatch(request_id):
            raise WorkerStateError("invalid remote dispatch task/id")
        self._call(
            ["gh", "api", "-X", "POST",
             f"repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"],
            body={"ref": DEFAULT_REF,
                  "inputs": {"hs_task": task, "request_id": request_id}},
        )

    def download(self, *, run_id: int, artifact: str, directory: Path) -> None:
        if artifact not in {task["artifact_name"] for task in TASKS.values()}:
            raise WorkerStateError("artifact not allowlisted")
        if type(run_id) is not int or run_id <= 0:
            raise WorkerStateError("invalid run id")
        self._call(
            ["gh", "run", "download", str(run_id), "-R", REPO,
             "-n", artifact, "-D", str(directory)],
            timeout=110,
        )


def _ledger_file(ledger: Path, request_id: str) -> Path:
    if not RID.fullmatch(request_id):
        raise WorkerStateError("invalid request ID")
    root = ledger.resolve()
    if ledger.is_symlink():
        raise WorkerStateError("ledger directory cannot be a symlink")
    return root / (request_id + ".json")


def _save(ledger: Path, job: dict[str, Any], *, overwrite: bool) -> Path:
    path = _ledger_file(ledger, job["request_id"])
    if path.exists() and not overwrite:
        raise WorkerStateError("job id already exists: refusing duplicate dispatch")
    if path.is_symlink():
        raise WorkerStateError("job ledger file cannot be a symlink")
    ledger.mkdir(parents=True, exist_ok=True)
    # Atomic replace, stable snapshots. No secrets or authorization token saved.
    fd, name = tempfile.mkstemp(prefix=".hs-job-", dir=str(ledger), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(job, file, sort_keys=True, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return path


def read_job(ledger: Path, request_id: str) -> dict[str, Any]:
    p = _ledger_file(ledger, request_id)
    if not p.is_file() or p.is_symlink():
        raise WorkerStateError("job record missing or invalid")
    data = json.loads(p.read_text())
    if data.get("schema_version") != SCHEMA:
        raise WorkerStateError("job record has unknown schema")
    if data.get("request_id") != request_id:
        raise WorkerStateError("job record ID mismatch")
    if data.get("task") not in TASKS or not SHA.fullmatch(data.get("ref_sha", "")):
        raise WorkerStateError("job record task or source pin invalid")
    if data.get("repository") != REPO or data.get("ref") != DEFAULT_REF:
        raise WorkerStateError("job record endpoint not approved")
    if data.get("worker_id", WORKER_ID) != WORKER_ID:
        raise WorkerStateError("job record references an unapproved worker transport")
    assignment = data.get("worker_assignment")
    if assignment is not None and (
        not isinstance(assignment, dict)
        or assignment.get("worker_id") != WORKER_ID
        or assignment.get("allowed_task") != data.get("task")
        or assignment.get("physical_authority") is not False
    ):
        raise WorkerStateError("job worker assignment is inconsistent")
    return data


def _source_at_ref(workspace: Path, sha: str, path: str) -> bytes:
    if not SHA.fullmatch(sha) or path not in {v["input_path"] for v in TASKS.values()}:
        raise WorkerStateError("remote input path/ref not allowed")
    try:
        p = subprocess.run(
            ["git", "-C", str(workspace), "show", f"{sha}:{path}"],
            capture_output=True, check=True, timeout=20,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise WorkerStateError("local checkout missing the approved remote input commit") from exc
    if not p.stdout or len(p.stdout) > 12 * 1024 * 1024:
        raise WorkerStateError("source file bytes absent/oversized")
    return p.stdout


def submit(
    objective: str,
    *,
    ledger: Path,
    workspace: Path,
    client: Any,
    request_id: str | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    choice = select_task(objective)
    task = choice["selected_task"]
    spec = TASKS[task]
    rid = request_id or ("hs-" + secrets.token_hex(8))
    if not RID.fullmatch(rid):
        raise WorkerStateError("request ID must be hs- plus exactly 16 lowercase hex digits")
    repo = client.get(f"repos/{REPO}/git/ref/heads/{DEFAULT_REF}")
    ref_sha = repo.get("object", {}).get("sha", "")
    if not SHA.fullmatch(ref_sha):
        raise WorkerStateError("GitHub main ref had invalid commit")
    content = _source_at_ref(workspace, ref_sha, spec["input_path"])
    manifest = {
        "schema_version": SCHEMA,
        "request_id": rid,
        "repository": REPO,
        "workflow": WORKFLOW,
        "ref": DEFAULT_REF,
        "ref_sha": ref_sha,
        "task": task,
        "objective": objective,
        "selection": choice,
        "approved_source_repository": spec["source"],
        "approved_source_revision": ADAPTERS[spec["source"]]["approved_commit_sha"],
        "expected_artifact": spec["artifact_name"],
        "input_path": spec["input_path"],
        "expected_input_sha256": hashlib.sha256(content).hexdigest(),
        "status": "prepared",
        "run_id": None,
        "created_utc": _utc(),
        "physical_authority": False,
        "mode": "fixed_example_worker_not_arbitrary_user_input",
    }
    if not execute:
        manifest["worker_assignment"] = choose_worker(ledger, task)
        manifest["worker_id"] = manifest["worker_assignment"]["worker_id"]
        return manifest
    # The lock is local-process/host scoped. Hold it across admission,
    # durable reservation and dispatch to avoid oversubscribing this ledger.
    with allocation_lock(ledger):
        manifest["worker_assignment"] = choose_worker(ledger, task)
        manifest["worker_id"] = manifest["worker_assignment"]["worker_id"]
        _save(ledger, manifest, overwrite=False)
        try:
            client.dispatch(task=task, request_id=rid)
        except Exception:
            manifest["status"] = "dispatch_unknown_check_remote_before_retry"
            _save(ledger, manifest, overwrite=True)
            raise
        manifest["status"] = "submitted"
        manifest["submitted_utc"] = _utc()
        _save(ledger, manifest, overwrite=True)
    return manifest


def _matching_run(job: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    title = f"HS GitHub Signal / {job['task']} / {job['request_id']}"
    matches = [r for r in runs if r.get("display_title") == title
               and r.get("event") == "workflow_dispatch"]
    if len(matches) > 1:
        raise WorkerStateError("multiple matching runs: possible duplicate request")
    if not matches:
        return None
    run = matches[0]
    if run.get("head_sha") != job["ref_sha"] or run.get("head_branch") != "main":
        raise WorkerStateError("worker run ref differs from approved source revision")
    if type(run.get("id")) is not int:
        raise WorkerStateError("worker run has no integer ID")
    return run


def status(
    *, ledger: Path, request_id: str, client: Any
) -> dict[str, Any]:
    job = read_job(ledger, request_id)
    if job["status"] == "collected":
        return job
    response = client.get(
        f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=100"
    )
    runs = response.get("workflow_runs")
    if not isinstance(runs, list):
        raise WorkerStateError("workflow listing missing runs")
    run = _matching_run(job, runs)
    if run is None:
        job["status"] = "awaiting_run_discovery"
        _save(ledger, job, overwrite=True)
        return job
    run_id = run["id"]
    if job["run_id"] is not None and job["run_id"] != run_id:
        raise WorkerStateError("associated run ID changed after first association")
    job["run_id"] = run_id
    job["run_url"] = run.get("html_url")
    job["remote_status"] = run.get("status")
    job["remote_conclusion"] = run.get("conclusion")
    if run.get("status") != "completed":
        job["status"] = "remote_running"
        _save(ledger, job, overwrite=True)
        return job
    jobs_response = client.get(f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100")
    remote_jobs = jobs_response.get("jobs")
    if not isinstance(remote_jobs, list):
        raise WorkerStateError("worker job listing invalid")
    status_map = {r.get("name"): r.get("conclusion") for r in remote_jobs}
    expected = TASKS[job["task"]]["job_name"]
    other = next(x["job_name"] for key,x in TASKS.items() if key != job["task"])
    if len(remote_jobs) != 3:
        raise WorkerStateError("unexpected remote job topology")
    job["worker_jobs"] = status_map
    if (
        run.get("conclusion") == "success"
        and status_map.get("intake-unit-gates") == "success"
        and status_map.get(expected) == "success"
        and status_map.get(other) == "skipped"
    ):
        job["status"] = "remote_succeeded"
    else:
        job["status"] = "remote_failed_or_unexpected_worker_topology"
    _save(ledger, job, overwrite=True)
    return job


def _read_json(p: Path) -> dict[str, Any]:
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 2 * 1024 * 1024:
        raise WorkerStateError("remote artifact missing, symlink or oversized")
    result = json.loads(p.read_text())
    if not isinstance(result, dict):
        raise WorkerStateError("remote artifact had unexpected schema")
    return result


def _inspect_downloads(base: Path, job: dict[str, Any]) -> dict[str, Any]:
    files = list(base.rglob("*"))
    if len(files) > 20 or any(p.is_symlink() for p in files):
        raise WorkerStateError("remote artifact contains unapproved entries")
    if sum(p.stat().st_size for p in files if p.is_file()) > 20 * 1024 * 1024:
        raise WorkerStateError("remote artifact exceeds size ceiling")
    if job["task"] == "review_schematic":
        verdict = _read_json(base / "HS_SIGNAL_CAPABILITY_VERDICT.json")
        cap = verdict.get("capability") or {}
        f = base / "akcli_schematic_findings.json"
        content = _read_json(f)
        if (
            verdict.get("ok") is not True
            or cap.get("repository") != "tipoLi5890/akcli"
            or cap.get("pinned_revision") != job["approved_source_revision"]
            or cap.get("input_sha256") != job["expected_input_sha256"]
            or cap.get("physical_device_connected") is not False
            or cap.get("fabrication_authorized") is not False
            or not isinstance(content.get("findings"), list)
            or cap.get("finding_count") != len(content["findings"])
            or cap.get("diagnostics_sha256") != sha256_file(f)
        ):
            raise WorkerStateError("remote akcli evidence is not approved or internally consistent")
        return {
            "tool": "akcli", "finding_count": cap["finding_count"],
            "artifact_sha256": sha256_file(f), "artifact": f.name,
        }
    root = base / "github_signals_kdif"
    cap = _read_json(root / "HS_SIGNAL_KDIF_CAPABILITY.json")
    task = _read_json(root / "HS_SIGNAL_TASK_RESULT.json")
    file = root / "HS_SIGNAL_KDIF_REVISIONS.html"
    if not file.is_file() or file.is_symlink() or file.stat().st_size > 15 * 1024 * 1024:
        raise WorkerStateError("HTML artifact missing or oversized")
    if (
        cap.get("repository") != "0x12net/kdif"
        or cap.get("pinned_revision") != job["approved_source_revision"]
        or cap.get("input", {}).get("revision_a_file_sha256") != job["expected_input_sha256"]
        or cap.get("physical_authority") is not False
        or cap.get("fab_approved") is not False
        or cap.get("artifact_sha256") != sha256_file(file)
        or task.get("ok") is not True
        or task.get("evidence", {}).get("artifact_sha256") != cap["artifact_sha256"]
        or task.get("selection", {}).get("selected_task") != job["task"]
        or file.stat().st_size != cap.get("artifact_bytes")
    ):
        raise WorkerStateError("remote kdif evidence is not approved or internally consistent")
    prefix = file.read_bytes()[:512].lower()
    if b"<!doctype html>" not in prefix or b"<title>kicad diff</title>" not in prefix:
        raise WorkerStateError("kdif HTML signature absent")
    return {
        "tool": "kdif", "artifact": "github_signals_kdif/" + file.name,
        "artifact_sha256": sha256_file(file), "bytes": file.stat().st_size,
        "controlled_test_revision": True,
    }


def collect(*, ledger: Path, request_id: str, client: Any) -> dict[str, Any]:
    job = status(ledger=ledger, request_id=request_id, client=client)
    if job["status"] == "collected":
        return job
    if job["status"] != "remote_succeeded":
        raise WorkerStateError("run has not completed approved worker job successfully")
    rid = job["run_id"]
    artifact = job["expected_artifact"]
    available = client.get(f"repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100")
    rows = [x for x in available.get("artifacts", [])
            if x.get("name") == artifact and not x.get("expired")]
    if len(rows) != 1:
        raise WorkerStateError("expected remote artifact missing or ambiguous")
    destination = ledger.resolve() / request_id / "artifact"
    if destination.exists():
        raise WorkerStateError("evidence already exists; refusing non-idempotent overwrite")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".remote-", dir=str(parent)) as temp:
        temporary = Path(temp)
        client.download(run_id=rid, artifact=artifact, directory=temporary)
        verified = _inspect_downloads(temporary, job)
        os.rename(temporary, destination)
    job["status"] = "collected"
    job["collected_utc"] = _utc()
    job["evidence"] = verified
    job["artifact_dir"] = str(destination)
    _save(ledger, job, overwrite=True)
    return job
