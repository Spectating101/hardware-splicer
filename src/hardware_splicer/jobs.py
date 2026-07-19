from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .compiler import compile_hardware_bundle
from .schemas import HardwareCompileSpec


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}

# Wall-clock cap for a single job worker run. Prevents Quick-demo "Building…" forever
# when an LLM call or KiCad subprocess stalls.
DEFAULT_JOB_TIMEOUT_S = 180.0


def _job_timeout_s() -> float:
    raw = os.getenv("HARDWARE_SPLICER_JOB_TIMEOUT_S", "").strip()
    if not raw:
        return DEFAULT_JOB_TIMEOUT_S
    try:
        return max(30.0, float(raw))
    except ValueError:
        return DEFAULT_JOB_TIMEOUT_S


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(data: Any) -> str:
    return json.dumps(data, sort_keys=True)


def _loads(data: str | None, default: Any) -> Any:
    if not data:
        return default
    try:
        return json.loads(data)
    except Exception:
        return default


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    request_id: str
    project_name: str
    status: str
    created_at: str
    updated_at: str
    output_dir: str
    spec: Dict[str, Any]
    options: Dict[str, Any]
    started_at: str | None = None
    finished_at: str | None = None
    result: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    def to_dict(self, *, include_spec: bool = False, include_result: bool = True) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "job_id": self.job_id,
            "request_id": self.request_id,
            "project_name": self.project_name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "output_dir": self.output_dir,
            "options": self.options,
            "links": {
                "self": f"/v1/jobs/{self.job_id}",
                "result": f"/v1/jobs/{self.job_id}/result",
                "artifacts": f"/v1/jobs/{self.job_id}/artifacts",
                "bundle": f"/v1/jobs/{self.job_id}/bundle",
                "retry": f"/v1/jobs/{self.job_id}/retry",
            },
        }
        if include_spec:
            row["spec"] = self.spec
        if self.error:
            row["error"] = self.error
        if include_result and self.result:
            row["result"] = self.result
        return row


class JobStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    project_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    output_dir TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    result_json TEXT,
                    error_json TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)")

    def _record_from_row(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=str(row["job_id"]),
            request_id=str(row["request_id"]),
            project_name=str(row["project_name"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            output_dir=str(row["output_dir"]),
            spec=_loads(row["spec_json"], {}),
            options=_loads(row["options_json"], {}),
            result=_loads(row["result_json"], None),
            error=_loads(row["error_json"], None),
        )

    def create_job(
        self,
        *,
        job_id: str,
        request_id: str,
        project_name: str,
        output_dir: str,
        spec: Dict[str, Any],
        options: Dict[str, Any],
    ) -> JobRecord:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT * FROM jobs WHERE request_id = ?", (request_id,)).fetchone()
            if existing:
                return self._record_from_row(existing)
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, request_id, project_name, status, created_at, updated_at,
                    output_dir, spec_json, options_json
                ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?)
                """,
                (job_id, request_id, project_name, now, now, output_dir, _json(spec), _json(options)),
            )
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._record_from_row(row)

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return self._record_from_row(row) if row else None

    def list_jobs(self, *, status: str | None = None, limit: int = 100) -> List[JobRecord]:
        limit = max(1, min(int(limit or 100), 500))
        with self._lock, self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._record_from_row(row) for row in rows]

    def stats(self) -> Dict[str, Any]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
        counts = {str(row["status"]): int(row["count"]) for row in rows}
        return {
            "total": sum(counts.values()),
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "succeeded": counts.get("succeeded", 0),
            "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
        }

    def recover_interrupted_running(self, *, requeue: bool = False) -> int:
        now = _utc_now()
        status = "queued" if requeue else "failed"
        error = None if requeue else _json({"type": "WorkerInterrupted", "message": "Job was running when the backend restarted."})
        finished_at = None if requeue else now
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, finished_at = ?, error_json = ?
                WHERE status = 'running'
                """,
                (status, now, finished_at, error),
            )
            return int(cursor.rowcount or 0)

    def claim_next(self) -> JobRecord | None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                conn.execute("COMMIT")
                return None
            conn.execute(
                """
                UPDATE jobs
                SET status = 'running', started_at = ?, updated_at = ?, error_json = NULL
                WHERE job_id = ? AND status = 'queued'
                """,
                (now, now, row["job_id"]),
            )
            conn.execute("COMMIT")
            updated = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
            return self._record_from_row(updated)

    def complete_job(self, job_id: str, result: Dict[str, Any]) -> None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            # Only transition running → succeeded (ignore late completes after timeout/fail).
            conn.execute(
                """
                UPDATE jobs
                SET status = 'succeeded', finished_at = ?, updated_at = ?, result_json = ?, error_json = NULL
                WHERE job_id = ? AND status = 'running'
                """,
                (now, now, _json(result), job_id),
            )

    def fail_job(self, job_id: str, error: Dict[str, Any]) -> None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', finished_at = ?, updated_at = ?, error_json = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (now, now, _json(error), job_id),
            )

    def cancel_job(self, job_id: str) -> bool:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = 'cancelled', finished_at = ?, updated_at = ?
                WHERE job_id = ? AND status = 'queued'
                """,
                (now, now, job_id),
            )
            return cursor.rowcount > 0

    def retry_job(self, job_id: str) -> bool:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = 'queued',
                    started_at = NULL,
                    finished_at = NULL,
                    updated_at = ?,
                    result_json = NULL,
                    error_json = NULL
                WHERE job_id = ? AND status IN ('succeeded', 'failed', 'cancelled')
                """,
                (now, job_id),
            )
            return cursor.rowcount > 0


class JobBackend:
    def __init__(self, store: JobStore, *, worker_count: int = 1, poll_interval_s: float = 0.2):
        self.store = store
        self.worker_count = max(0, int(worker_count))
        self.poll_interval_s = max(0.05, float(poll_interval_s))
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []
        self._start_lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "JobBackend":
        state_dir = Path(os.getenv("HARDWARE_SPLICER_STATE_DIR", "/tmp/hardware_splicer_state"))
        db_path = Path(os.getenv("HARDWARE_SPLICER_JOB_DB", str(state_dir / "jobs.sqlite3")))
        worker_count = int(os.getenv("HARDWARE_SPLICER_JOB_WORKERS", "1"))
        poll_interval_s = float(os.getenv("HARDWARE_SPLICER_JOB_POLL_INTERVAL_S", "0.2"))
        store = JobStore(db_path)
        requeue = os.getenv("HARDWARE_SPLICER_REQUEUE_INTERRUPTED_JOBS", "").lower() in {"1", "true", "yes"}
        store.recover_interrupted_running(requeue=requeue)
        return cls(store, worker_count=worker_count, poll_interval_s=poll_interval_s)

    def start(self) -> None:
        if self.worker_count <= 0:
            return
        with self._start_lock:
            self._stop.clear()
            live = [thread for thread in self._threads if thread.is_alive()]
            self._threads = live
            missing = self.worker_count - len(live)
            for index in range(missing):
                thread = threading.Thread(target=self._worker_loop, name=f"hardware-splicer-worker-{index + 1}", daemon=True)
                thread.start()
                self._threads.append(thread)

    def stop(self, *, timeout_s: float = 5.0) -> None:
        self._stop.set()
        deadline = time.monotonic() + timeout_s
        for thread in list(self._threads):
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)
        self._threads = [thread for thread in self._threads if thread.is_alive()]

    def submit(
        self,
        *,
        job_id: str,
        request_id: str,
        spec: HardwareCompileSpec,
        output_dir: str | Path,
        start_splicer: bool = True,
        splicer_port: int = 0,
    ) -> JobRecord:
        options = {
            "job_type": "compile_bundle",
            "start_splicer": bool(start_splicer),
            "splicer_port": int(splicer_port or 0),
        }
        job = self.store.create_job(
            job_id=job_id,
            request_id=request_id,
            project_name=spec.project_name,
            output_dir=str(output_dir),
            spec=spec.to_dict(),
            options=options,
        )
        self.start()
        return job

    def submit_task(
        self,
        *,
        job_id: str,
        request_id: str,
        project_name: str,
        output_dir: str | Path,
        job_type: str,
        payload: Dict[str, Any],
        options: Dict[str, Any] | None = None,
    ) -> JobRecord:
        task_options = {"job_type": job_type, "payload": payload, **(options or {})}
        job = self.store.create_job(
            job_id=job_id,
            request_id=request_id,
            project_name=project_name,
            output_dir=str(output_dir),
            spec={"project_name": project_name, "job_type": job_type},
            options=task_options,
        )
        self.start()
        return job

    def wait_for_terminal(self, job_id: str, *, timeout_s: float = 30.0) -> JobRecord:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            job = self.store.get_job(job_id)
            if job and job.status in TERMINAL_STATUSES:
                return job
            time.sleep(self.poll_interval_s)
        raise TimeoutError(f"Job {job_id} did not reach terminal status within {timeout_s}s")

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            job = self.store.claim_next()
            if not job:
                self._stop.wait(self.poll_interval_s)
                continue
            self._run_job(job)

    def _run_job(self, job: JobRecord) -> None:
        timeout_s = _job_timeout_s()
        # Helper thread so a hung LLM/subprocess cannot leave the job "running" forever.
        error_box: list[BaseException] = []
        done = threading.Event()

        def _target() -> None:
            try:
                self._execute_job(job)
            except BaseException as exc:  # noqa: BLE001 — surface to outer fail_job
                error_box.append(exc)
            finally:
                done.set()

        worker = threading.Thread(
            target=_target,
            name=f"hs-job-{job.job_id[:8]}",
            daemon=True,
        )
        worker.start()
        if not done.wait(timeout_s):
            self.store.fail_job(
                job.job_id,
                {
                    "type": "JobTimeout",
                    "message": (
                        f"Job exceeded wall-clock timeout ({int(timeout_s)}s). "
                        "Likely a stalled LLM or compile step; retry with offline flags "
                        "(HARDWARE_SPLICER_OFFLINE_SALVAGE=1 / QWEN_DISABLED=1) or raise "
                        "HARDWARE_SPLICER_JOB_TIMEOUT_S."
                    ),
                    "timeout_s": timeout_s,
                },
            )
            return
        if error_box:
            exc = error_box[0]
            self.store.fail_job(
                job.job_id,
                {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "traceback": "".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__, limit=20)
                    ),
                },
            )

    def _execute_job(self, job: JobRecord) -> None:
        job_type = str(job.options.get("job_type") or "compile_bundle")
        try:
            if job_type == "compose":
                from .compose_dispatch import compose_dispatch
                from .sdk import finalize_compose_job_result

                payload = dict(job.options.get("payload") or {})
                allow_llm_first = bool(payload.pop("allow_llm_first", False))
                clarifier = payload.pop("clarifier", None)
                result = compose_dispatch(
                    out_dir=job.output_dir,
                    allow_llm_first=allow_llm_first,
                    request_id=job.request_id,
                    **payload,
                )
                final = finalize_compose_job_result(
                    result,
                    goal=str(payload.get("phrase") or ""),
                    project_name=job.project_name,
                    clarifier=clarifier if isinstance(clarifier, dict) else None,
                )
                self.store.complete_job(job.job_id, final)
                return
            if job_type == "compose_agent_loop":
                from .compose_agent_loop import compose_agent_loop

                payload = dict(job.options.get("payload") or {})
                max_manual_retries = int(payload.pop("max_manual_retries", 2))
                finalize_package = bool(payload.pop("finalize_package", False))
                project_name = payload.pop("project_name", None)
                goal = payload.pop("goal", None) or payload.get("phrase")
                allow_llm_first = bool(payload.pop("allow_llm_first", False))
                drc_fixup = payload.pop("drc_fixup", None)
                result = compose_agent_loop(
                    out_dir=job.output_dir,
                    allow_llm_first=allow_llm_first,
                    request_id=job.request_id,
                    max_manual_retries=max_manual_retries,
                    finalize_package=finalize_package,
                    goal=goal,
                    project_name=project_name or job.project_name,
                    drc_fixup=drc_fixup,
                    **payload,
                )
                self.store.complete_job(job.job_id, result)
                return
            if job_type == "splice_build":
                from .project_intake import splice_and_build_from_intake

                payload = dict(job.options.get("payload") or {})
                intake = payload.get("intake") or {}
                result = splice_and_build_from_intake(
                    intake,
                    out_dir=job.output_dir,
                    export_gerber=bool(payload.get("export_gerber")),
                    request_id=job.request_id,
                )
                self.store.complete_job(job.job_id, result)
                return

            spec = HardwareCompileSpec.from_dict(job.spec)
            result = compile_hardware_bundle(
                spec,
                out_dir=job.output_dir,
                start_splicer=bool(job.options.get("start_splicer", True)),
                splicer_port=int(job.options.get("splicer_port") or 0),
                request_id=job.request_id,
            )
            self.store.complete_job(job.job_id, result.to_dict())
        except Exception as exc:
            self.store.fail_job(
                job.job_id,
                {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(limit=20),
                },
            )


def artifact_manifest(job: JobRecord) -> Dict[str, Any]:
    if not job.result:
        return {"ok": False, "status": job.status, "message": "Job result is not available yet."}
    manifest_file = job.result.get("manifest_file")
    if not manifest_file:
        return {"ok": False, "status": job.status, "message": "Job result does not include a manifest_file."}
    path = Path(str(manifest_file))
    if not path.exists():
        return {"ok": False, "status": job.status, "message": f"Manifest file does not exist: {path}"}
    return json.loads(path.read_text(encoding="utf-8"))


def build_output_archive(job: JobRecord) -> Path:
    if job.status != "succeeded" or not job.result:
        raise FileNotFoundError("Job output is not available until the job has succeeded.")
    output_dir = Path(job.output_dir)
    if not output_dir.exists() or not output_dir.is_dir():
        raise FileNotFoundError(f"Job output directory does not exist: {output_dir}")
    archive = output_dir / "hardware_splicer_bundle.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in output_dir.rglob("*") if p.is_file()):
            if path.resolve() == archive.resolve():
                continue
            zf.write(path, path.relative_to(output_dir))
    return archive
