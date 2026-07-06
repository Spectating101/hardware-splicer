#!/usr/bin/env python3
"""Live HTTP smoke for Splice Agent v1 — health, UI, async splice-build job.

Spawns local uvicorn unless VERIFY_LIVE_BASE_URL is set.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTAKE_PATH = ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json"
POLL_SEC = 2.0
JOB_TIMEOUT_SEC = 180.0


def _fetch(method: str, url: str, payload: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {"Accept": "*/*"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, resp.read().decode("utf-8")


def _fetch_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    status, text = _fetch(method, url, payload)
    return status, json.loads(text) if text else {}


def _wait_health(base: str, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, body = _fetch_json("GET", f"{base}/health")
            if status == 200 and body.get("ok"):
                return
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"health check failed for {base}/health: {last_error}")


def _run_smoke(base: str) -> None:
    print(f"==> live smoke: {base}")

    status, health = _fetch_json("GET", f"{base}/health")
    if status != 200 or not health.get("ok"):
        raise RuntimeError(f"health failed: {status} {health}")
    print(f"    health ok version={health.get('version')}")

    status, examples = _fetch_json("GET", f"{base}/v1/examples/splice-intakes")
    if status != 200 or not examples.get("ok") or not examples.get("examples"):
        raise RuntimeError(f"examples failed: {status} {examples}")
    print(f"    examples ok count={len(examples['examples'])}")

    status, html = _fetch("GET", f"{base}/")
    if status != 200 or "Splice Agent" not in html:
        raise RuntimeError(f"UI root failed: status={status}")
    print("    UI root ok")

    intake = json.loads(INTAKE_PATH.read_text(encoding="utf-8"))
    request_id = f"live-smoke-{int(time.time())}"
    status, submitted = _fetch_json(
        "POST",
        f"{base}/v1/jobs/splice-build",
        {"intake": intake, "export_gerber": False, "request_id": request_id},
    )
    if status not in {200, 202}:
        raise RuntimeError(f"job submit failed: {status} {submitted}")
    job_id = submitted.get("job_id") or request_id
    print(f"    job submitted id={job_id} status={submitted.get('status')}")

    deadline = time.time() + JOB_TIMEOUT_SEC
    terminal = None
    while time.time() < deadline:
        status, job = _fetch_json("GET", f"{base}/v1/jobs/{job_id}")
        if status != 200:
            raise RuntimeError(f"job poll failed: {status} {job}")
        job_status = job.get("status")
        if job_status in {"succeeded", "failed", "cancelled"}:
            terminal = job
            break
        time.sleep(POLL_SEC)

    if terminal is None:
        raise RuntimeError(f"job timed out after {JOB_TIMEOUT_SEC}s")

    if terminal.get("status") != "succeeded":
        raise RuntimeError(f"job failed: {terminal}")

    status, result_payload = _fetch_json("GET", f"{base}/v1/jobs/{job_id}/result")
    if status != 200 or not result_payload.get("ok") or not result_payload.get("result"):
        raise RuntimeError(f"job result missing: {status} {result_payload}")

    result = result_payload["result"]
    package = result.get("project_package") or {}
    gates = package.get("gates") or {}
    if not package.get("info"):
        raise RuntimeError("project_package.info missing")
    print(
        f"    job succeeded package={package.get('info', {}).get('project_name')} "
        f"gates_open={gates.get('open_gate_count')}"
    )
    print("verify_product_live_smoke: passed")


def main() -> int:
    base = os.environ.get("VERIFY_LIVE_BASE_URL", "").rstrip("/")
    proc: subprocess.Popen | None = None
    if not base:
        port = int(os.environ.get("VERIFY_LIVE_PORT", "8798"))
        base = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["HARDWARE_SPLICER_SERVE_UI"] = "1"
        env["HARDWARE_SPLICER_AUTOROUTE"] = "0"
        env["HARDWARE_SPLICER_DRC_FIX_LOOP"] = "1"
        env["HARDWARE_SPLICER_SKIP_VISION_LIVE"] = "1"
        env["HARDWARE_SPLICER_OFFLINE_SALVAGE"] = "1"
        venv_python = ROOT / ".venv" / "bin" / "python"
        python = str(venv_python if venv_python.is_file() else sys.executable)
        proc = subprocess.Popen(
            [
                python,
                "-m",
                "uvicorn",
                "hardware_splicer.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        def _terminate(*_args: object) -> None:
            if proc and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)

        signal.signal(signal.SIGTERM, _terminate)
        signal.signal(signal.SIGINT, _terminate)

    try:
        _wait_health(base)
        _run_smoke(base)
        return 0
    except Exception as exc:
        if proc and proc.stderr:
            err = proc.stderr.read().decode("utf-8", errors="replace")
            if err.strip():
                print(err, file=sys.stderr)
        print(f"verify_product_live_smoke: FAILED — {exc}", file=sys.stderr)
        return 1
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
