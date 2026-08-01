"""Read-only adapter for kicad-happy deterministic analyzers.

The upstream project is intentionally not vendored.  Operators point Hardware
Splicer at a checkout or installed analyzer root.  Results are imported as
observations with an explicit authority ceiling; they never authorize release.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


SUPPORTED_ANALYZERS = {
    "schematic": "analyze_schematic.py",
    "pcb": "analyze_pcb.py",
    "gerbers": "analyze_gerbers.py",
}
SUPPORTED_SCHEMA_MAJORS = {1}
SENSITIVE_ENV_MARKERS = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
    "OPENAI",
    "ANTHROPIC",
    "QWEN",
    "GEMINI",
    "MISTRAL",
    "DEEPSEEK",
    "DIGIKEY",
    "MOUSER",
)


@dataclass(frozen=True)
class KicadHappyRun:
    adapter_id: str
    adapter_version: str
    profile: str
    runtime: str
    started_at: str
    finished_at: str
    duration_s: float
    command: list[str]
    exit_code: int | None
    timed_out: bool
    skipped: bool
    skip_reason: str | None
    input_hashes: Dict[str, str]
    output_hashes: Dict[str, str]
    stdout_tail: str
    stderr_tail: str
    authority_ceiling: str
    artifacts: list[Dict[str, Any]]
    findings: list[Dict[str, Any]]
    assessments: list[Dict[str, Any]]
    trust_summary: Dict[str, Any]
    upstream_inputs: Dict[str, Any]
    compat: Dict[str, Any]
    casefile: Dict[str, Any] | None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_inputs(paths: Iterable[Path]) -> Dict[str, str]:
    return {str(path.resolve()): _sha256(path) for path in paths}


def _sanitized_environment(source: Mapping[str, str] | None = None) -> Dict[str, str]:
    source = source or os.environ
    safe: Dict[str, str] = {}
    allowed_exact = {
        "PATH",
        "HOME",
        "USERPROFILE",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "PYTHONPATH",
        "VIRTUAL_ENV",
    }
    for key, value in source.items():
        upper = key.upper()
        if key in allowed_exact and not any(marker in upper for marker in SENSITIVE_ENV_MARKERS):
            safe[key] = value
    safe["PYTHONUNBUFFERED"] = "1"
    return safe


def _tail(text: str, limit: int = 16_384) -> str:
    return text[-limit:]


def _schema_major(payload: Mapping[str, Any]) -> int | None:
    raw = str(payload.get("schema_version") or "").strip()
    if not raw:
        return None
    try:
        return int(raw.split(".", 1)[0])
    except ValueError:
        return None


def _resolve_script(analyzer_root: Path, profile: str) -> Path:
    filename = SUPPORTED_ANALYZERS.get(profile)
    if not filename:
        raise ValueError(f"unsupported kicad-happy profile: {profile}")
    candidates = [
        analyzer_root / filename,
        analyzer_root / "skills" / "kicad" / "scripts" / filename,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def _result(
    *,
    adapter_version: str,
    profile: str,
    started_at: str,
    start: float,
    command: list[str],
    input_hashes: Dict[str, str],
    exit_code: int | None = None,
    timed_out: bool = False,
    skipped: bool = False,
    skip_reason: str | None = None,
    stdout: str = "",
    stderr: str = "",
    payload: Mapping[str, Any] | None = None,
    output_path: Path | None = None,
    casefile: Dict[str, Any] | None = None,
) -> KicadHappyRun:
    payload = payload or {}
    output_hashes = {str(output_path.resolve()): _sha256(output_path)} if output_path and output_path.is_file() else {}
    artifacts = []
    if output_path and output_path.is_file():
        artifacts.append(
            {
                "kind": "kicad_happy_analysis",
                "path": str(output_path.resolve()),
                "sha256": output_hashes[str(output_path.resolve())],
            }
        )
    return KicadHappyRun(
        adapter_id="kicad-happy",
        adapter_version=adapter_version,
        profile=profile,
        runtime="bounded_subprocess",
        started_at=started_at,
        finished_at=_utc_now(),
        duration_s=round(time.monotonic() - start, 3),
        command=command,
        exit_code=exit_code,
        timed_out=timed_out,
        skipped=skipped,
        skip_reason=skip_reason,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        stdout_tail=_tail(stdout),
        stderr_tail=_tail(stderr),
        authority_ceiling="observed",
        artifacts=artifacts,
        findings=list(payload.get("findings") or []),
        assessments=list(payload.get("assessments") or []),
        trust_summary=dict(payload.get("trust_summary") or {}),
        upstream_inputs=dict(payload.get("inputs") or {}),
        compat=dict(payload.get("compat") or {}),
        casefile=casefile,
    )


def run_kicad_happy(
    *,
    analyzer_root: str | Path,
    profile: str,
    input_path: str | Path,
    output_dir: str | Path,
    adapter_version: str = "unversioned-checkout",
    python_executable: str | None = None,
    timeout_s: float = 180.0,
) -> Dict[str, Any]:
    """Run one deterministic analyzer and return an evidence envelope.

    Missing optional tooling returns a structured skipped result.  Any analyzer
    failure, input mutation, invalid output, or unsupported schema fails closed
    and carries a casefile.
    """

    started_at = _utc_now()
    start = time.monotonic()
    root = Path(analyzer_root).expanduser().resolve()
    source = Path(input_path).expanduser().resolve()
    output_root = Path(output_dir).expanduser().resolve()
    script = _resolve_script(root, profile)
    command: list[str] = []

    if not source.exists():
        raise FileNotFoundError(f"kicad-happy input not found: {source}")

    input_files = [source] if source.is_file() else sorted(path for path in source.rglob("*") if path.is_file())
    before = _hash_inputs(input_files)

    if not script.is_file():
        return _result(
            adapter_version=adapter_version,
            profile=profile,
            started_at=started_at,
            start=start,
            command=command,
            input_hashes=before,
            skipped=True,
            skip_reason=f"analyzer script not found: {script}",
        ).to_dict()

    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / f"kicad_happy_{profile}.json"
    executable = python_executable or sys.executable
    command = [executable, str(script), str(source), "--output", str(output_path)]

    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            env=_sanitized_environment(),
            capture_output=True,
            text=True,
            timeout=max(float(timeout_s), 0.1),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        casefile = {
            "kind": "adapter_timeout",
            "message": f"kicad-happy {profile} exceeded {timeout_s}s",
        }
        return _result(
            adapter_version=adapter_version,
            profile=profile,
            started_at=started_at,
            start=start,
            command=command,
            input_hashes=before,
            timed_out=True,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            casefile=casefile,
        ).to_dict()

    after = _hash_inputs(input_files)
    if after != before:
        casefile = {
            "kind": "input_mutation",
            "message": "read-only adapter input changed during analyzer execution",
            "before": before,
            "after": after,
        }
        return _result(
            adapter_version=adapter_version,
            profile=profile,
            started_at=started_at,
            start=start,
            command=command,
            input_hashes=before,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            casefile=casefile,
        ).to_dict()

    if completed.returncode != 0 or not output_path.is_file():
        casefile = {
            "kind": "adapter_failure",
            "message": "kicad-happy analyzer failed or produced no JSON output",
            "exit_code": completed.returncode,
        }
        return _result(
            adapter_version=adapter_version,
            profile=profile,
            started_at=started_at,
            start=start,
            command=command,
            input_hashes=before,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            casefile=casefile,
        ).to_dict()

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        casefile = {"kind": "invalid_output", "message": str(exc)}
        return _result(
            adapter_version=adapter_version,
            profile=profile,
            started_at=started_at,
            start=start,
            command=command,
            input_hashes=before,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            output_path=output_path,
            casefile=casefile,
        ).to_dict()

    major = _schema_major(payload)
    if major not in SUPPORTED_SCHEMA_MAJORS:
        casefile = {
            "kind": "unsupported_schema",
            "message": f"unsupported kicad-happy schema_version: {payload.get('schema_version')!r}",
        }
        return _result(
            adapter_version=adapter_version,
            profile=profile,
            started_at=started_at,
            start=start,
            command=command,
            input_hashes=before,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            output_path=output_path,
            casefile=casefile,
        ).to_dict()

    return _result(
        adapter_version=adapter_version,
        profile=profile,
        started_at=started_at,
        start=start,
        command=command,
        input_hashes=before,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        payload=payload,
        output_path=output_path,
    ).to_dict()
