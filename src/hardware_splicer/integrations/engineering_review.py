"""Read-only external engineering review adapters.

The first supported adapter is kicad-happy. It is intentionally executed as an
optional sidecar: Hardware Splicer owns build identity, evidence, review policy,
and release authorization. External analyzer output can add observed evidence
or block a release policy, but it can never authorize fabrication by itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..build_files import resolve_build_dir

ADAPTER_ID = "kicad-happy"
ADAPTER_NAME = "kicad-happy"
AUTHORITY_CEILING = "observed"
SUPPORTED_SCHEMA_MAJOR = 1
DEFAULT_TIMEOUT_S = 180.0
MAX_CAPTURE_CHARS = 16_000

_SCRIPT_PATHS = {
    "schematic": Path("skills/kicad/scripts/analyze_schematic.py"),
    "pcb": Path("skills/kicad/scripts/analyze_pcb.py"),
    "gerber": Path("skills/kicad/scripts/analyze_gerbers.py"),
}

_SECRET_FRAGMENTS = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "ACCESS_KEY",
    "SESSION",
    "COOKIE",
    "CREDENTIAL",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _safe_relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _bounded_text(value: str | None) -> str:
    text = value or ""
    if len(text) <= MAX_CAPTURE_CHARS:
        return text
    return text[:MAX_CAPTURE_CHARS] + "\n...[truncated]"


def _sanitized_environment() -> dict[str, str]:
    keep = {
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
        "VIRTUAL_ENV",
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in keep and not any(fragment in key.upper() for fragment in _SECRET_FRAGMENTS)
    }
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _run_process(command: Sequence[str], *, cwd: Path, timeout_s: float) -> dict[str, Any]:
    started = time.monotonic()
    creationflags = 0
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(
        list(command),
        cwd=str(cwd),
        env=_sanitized_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        **popen_kwargs,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=max(0.1, float(timeout_s)))
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stdout, stderr = process.communicate()

    return {
        "command": list(command),
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - started, 3),
        "stdout": _bounded_text(stdout),
        "stderr": _bounded_text(stderr),
    }


def _candidate_roots(explicit_root: str | Path | None = None) -> Iterable[Path]:
    if explicit_root:
        yield Path(explicit_root).expanduser()
        return

    configured = os.getenv("HARDWARE_SPLICER_KICAD_HAPPY_ROOT", "").strip()
    if configured:
        yield Path(configured).expanduser()
        return

    repository_root = Path(__file__).resolve().parents[3]
    yield repository_root / "external" / "kicad-happy"
    yield Path.home() / ".local" / "share" / "hardware-splicer" / "adapters" / "kicad-happy"


def _git_revision(root: Path) -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    result = _run_process(
        [git, "-C", str(root), "rev-parse", "HEAD"],
        cwd=root,
        timeout_s=3.0,
    )
    if result["timed_out"] or result["exit_code"] != 0:
        return None
    revision = str(result["stdout"]).strip().splitlines()
    return revision[-1] if revision else None


def discover_kicad_happy(explicit_root: str | Path | None = None) -> dict[str, Any]:
    inspected: list[str] = []
    selected: Path | None = None
    scripts: dict[str, Path] = {}

    for candidate in _candidate_roots(explicit_root):
        resolved = candidate.resolve()
        inspected.append(str(resolved))
        if not resolved.is_dir():
            continue
        found = {
            analyzer_type: resolved / relative
            for analyzer_type, relative in _SCRIPT_PATHS.items()
            if (resolved / relative).is_file()
        }
        if found:
            selected = resolved
            scripts = found
            break

    available = selected is not None and bool(scripts)
    missing = [
        analyzer_type for analyzer_type in _SCRIPT_PATHS
        if analyzer_type not in scripts
    ]
    return {
        "id": ADAPTER_ID,
        "name": ADAPTER_NAME,
        "available": available,
        "status": "available" if available else "not_configured",
        "root": str(selected) if selected else None,
        "revision": _git_revision(selected) if selected else None,
        "license": "MIT",
        "authority_ceiling": AUTHORITY_CEILING,
        "capabilities": sorted(scripts),
        "missing_capabilities": missing,
        "inspected_roots": inspected,
        "setup": {
            "environment_variable": "HARDWARE_SPLICER_KICAD_HAPPY_ROOT",
            "instruction": (
                "Clone aklofas/kicad-happy locally, then set "
                "HARDWARE_SPLICER_KICAD_HAPPY_ROOT to that checkout."
            ),
        },
        "_scripts": {key: str(path) for key, path in scripts.items()},
    }


def _select_review_inputs(root: Path) -> dict[str, Path]:
    compilation = root / "build_compilation"
    search_root = compilation if compilation.is_dir() else root

    pcb_candidates = sorted(search_root.rglob("*.kicad_pcb"))
    schematic_candidates = sorted(search_root.rglob("*.kicad_sch"))

    gerber_candidates = [
        search_root / "gerber",
        search_root / "gerbers",
        root / "gerber",
        root / "gerbers",
    ]
    gerber_dir = next(
        (
            candidate
            for candidate in gerber_candidates
            if candidate.is_dir() and any(path.is_file() for path in candidate.rglob("*"))
        ),
        None,
    )

    selected: dict[str, Path] = {}
    if schematic_candidates:
        selected["schematic"] = schematic_candidates[0]
    if pcb_candidates:
        selected["pcb"] = pcb_candidates[0]
    if gerber_dir:
        selected["gerber"] = gerber_dir
    return selected


def _input_records(root: Path, selected: Mapping[str, Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for analyzer_type, path in selected.items():
        if path.is_dir():
            files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
            digest = hashlib.sha256()
            for candidate in files:
                digest.update(_safe_relative(path, candidate).encode("utf-8"))
                digest.update(_sha256_file(candidate).encode("ascii"))
            records.append(
                {
                    "analyzer_type": analyzer_type,
                    "path": _safe_relative(root, path),
                    "sha256": digest.hexdigest(),
                    "file_count": len(files),
                    "kind": "directory",
                }
            )
        else:
            records.append(
                {
                    "analyzer_type": analyzer_type,
                    "path": _safe_relative(root, path),
                    "sha256": _sha256_file(path),
                    "size_bytes": path.stat().st_size,
                    "kind": "file",
                }
            )
    return records


def _cache_key(adapter: Mapping[str, Any], inputs: Sequence[Mapping[str, Any]]) -> str:
    payload = {
        "adapter_id": adapter.get("id"),
        "adapter_revision": adapter.get("revision"),
        "inputs": [
            {
                "analyzer_type": row.get("analyzer_type"),
                "path": row.get("path"),
                "sha256": row.get("sha256"),
            }
            for row in inputs
        ],
        "schema": "hardware_splicer.engineering_review.v1",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _schema_major(payload: Mapping[str, Any]) -> int | None:
    value = str(payload.get("schema_version") or "").strip()
    if not value:
        return None
    head = value.split(".", 1)[0]
    return int(head) if head.isdigit() else None


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _finding_severity(value: Any) -> tuple[str, str]:
    original = str(value or "info").strip().lower().replace("-", "_")
    if original in {"critical", "error", "high", "blocker", "required"}:
        return original, "blocker"
    if original in {"warning", "warn", "medium"}:
        return original, "warning"
    if original in {"low", "advisory"}:
        return original, "advisory"
    return original, "info"


def _normalize_finding(payload: Mapping[str, Any], *, analyzer_type: str, index: int) -> dict[str, Any]:
    original_severity, product_severity = _finding_severity(payload.get("severity"))
    rule_id = (
        payload.get("rule_id")
        or payload.get("detector")
        or payload.get("code")
        or payload.get("id")
        or f"{analyzer_type}:{index + 1}"
    )
    title = (
        payload.get("summary")
        or payload.get("title")
        or payload.get("message")
        or payload.get("description")
        or str(rule_id).replace("_", " ")
    )
    recommendation = (
        payload.get("recommendation")
        or payload.get("remediation")
        or payload.get("suggestion")
        or payload.get("action")
    )

    evidence_source = payload.get("evidence_source") or payload.get("evidence_sources")
    if isinstance(evidence_source, list):
        evidence_sources = [str(item) for item in evidence_source]
    elif evidence_source:
        evidence_sources = [str(evidence_source)]
    else:
        evidence_sources = ["deterministic-analyzer"]

    components = payload.get("components") or payload.get("component_refs") or payload.get("component")
    nets = payload.get("nets") or payload.get("net_names") or payload.get("net")

    return {
        "finding_id": f"{analyzer_type}:{rule_id}:{index + 1}",
        "rule_id": str(rule_id),
        "analyzer_type": analyzer_type,
        "severity": product_severity,
        "source_severity": original_severity,
        "title": str(title),
        "recommendation": str(recommendation) if recommendation else None,
        "confidence": payload.get("confidence") or "unspecified",
        "evidence_sources": evidence_sources,
        "components": [str(item) for item in _coerce_list(components) if item not in {None, ""}],
        "nets": [str(item) for item in _coerce_list(nets) if item not in {None, ""}],
        "authority": AUTHORITY_CEILING,
        "raw": dict(payload),
    }


def _normalize_analysis(payload: Mapping[str, Any], *, analyzer_type: str) -> dict[str, Any]:
    declared_type = str(payload.get("analyzer_type") or analyzer_type)
    major = _schema_major(payload)
    if major is not None and major != SUPPORTED_SCHEMA_MAJOR:
        raise ValueError(
            f"unsupported {declared_type} schema major {major}; "
            f"supported major is {SUPPORTED_SCHEMA_MAJOR}"
        )

    findings = [
        _normalize_finding(row, analyzer_type=declared_type, index=index)
        for index, row in enumerate(payload.get("findings") or [])
        if isinstance(row, Mapping)
    ]
    assessments = [
        dict(row)
        for row in payload.get("assessments") or []
        if isinstance(row, Mapping)
    ]
    return {
        "analyzer_type": declared_type,
        "schema_version": payload.get("schema_version"),
        "summary": dict(payload.get("summary") or {}),
        "trust_summary": dict(payload.get("trust_summary") or {}),
        "inputs": dict(payload.get("inputs") or {}),
        "compat": dict(payload.get("compat") or {}),
        "findings": findings,
        "assessments": assessments,
    }


def _review_summary(
    findings: Sequence[Mapping[str, Any]],
    analyses: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    counts = {"blocker": 0, "warning": 0, "advisory": 0, "info": 0}
    for finding in findings:
        severity = str(finding.get("severity") or "info")
        counts[severity if severity in counts else "info"] += 1

    coverage_values: list[float] = []
    for analysis in analyses:
        value = (analysis.get("trust_summary") or {}).get("provenance_coverage_pct")
        try:
            if value is not None:
                coverage_values.append(float(value))
        except (TypeError, ValueError):
            pass

    if counts["blocker"]:
        status = "blocked"
        headline = f"{counts['blocker']} engineering blocker(s) require review before release."
    elif failures and analyses:
        status = "partial"
        headline = "Engineering review completed partially; one or more analyzers failed."
    elif failures:
        status = "failed"
        headline = "Engineering review could not produce trusted analyzer output."
    elif counts["warning"]:
        status = "review_required"
        headline = f"{counts['warning']} engineering warning(s) require disposition."
    else:
        status = "clear"
        headline = "No external engineering blockers were reported."

    return {
        "status": status,
        "headline": headline,
        "finding_count": len(findings),
        "blocker_count": counts["blocker"],
        "warning_count": counts["warning"],
        "advisory_count": counts["advisory"],
        "info_count": counts["info"],
        "analysis_count": len(analyses),
        "failed_analysis_count": len(failures),
        "provenance_coverage_pct": (
            round(sum(coverage_values) / len(coverage_values), 1)
            if coverage_values
            else None
        ),
    }


def _latest_review_path(root: Path) -> Path:
    return root / "build_compilation" / "ENGINEERING_REVIEW.json"


def read_latest_engineering_review(build_dir: str | Path) -> dict[str, Any] | None:
    root = resolve_build_dir(build_dir)
    path = _latest_review_path(root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(payload) if isinstance(payload, dict) else None


def engineering_review_status(build_dir: str | Path) -> dict[str, Any]:
    root = resolve_build_dir(build_dir)
    adapter = discover_kicad_happy()
    selected = _select_review_inputs(root)
    inputs = _input_records(root, selected)
    latest = read_latest_engineering_review(root)
    supported_inputs = sorted(set(adapter.get("capabilities") or []) & set(selected))
    can_run = bool(adapter.get("available")) and bool(supported_inputs)

    return {
        "ok": True,
        "build_dir": str(root),
        "schema_version": "hardware_splicer.engineering_review_status.v1",
        "can_run": can_run,
        "adapter": {key: value for key, value in adapter.items() if key != "_scripts"},
        "inputs": inputs,
        "supported_inputs": supported_inputs,
        "latest_review": latest,
    }


def run_engineering_review(
    build_dir: str | Path,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    force: bool = False,
    explicit_root: str | Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    root = resolve_build_dir(build_dir)
    adapter = discover_kicad_happy(explicit_root)
    adapter_public = {key: value for key, value in adapter.items() if key != "_scripts"}
    selected = _select_review_inputs(root)
    inputs_before = _input_records(root, selected)
    cache_key = _cache_key(adapter, inputs_before)

    latest = read_latest_engineering_review(root)
    if (
        not force
        and latest
        and latest.get("cache_key") == cache_key
        and latest.get("ok") is True
    ):
        return {**latest, "cached": True}

    if not adapter.get("available"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "kicad-happy is not configured",
            "build_dir": str(root),
            "adapter": adapter_public,
            "inputs": inputs_before,
            "authority": {
                "maximum": AUTHORITY_CEILING,
                "may_authorize_release": False,
            },
        }

    scripts = {
        key: Path(value)
        for key, value in (adapter.get("_scripts") or {}).items()
    }
    plan = [
        (analyzer_type, selected[analyzer_type], scripts[analyzer_type])
        for analyzer_type in ("schematic", "pcb", "gerber")
        if analyzer_type in selected and analyzer_type in scripts
    ]
    if not plan:
        return {
            "ok": False,
            "skipped": True,
            "reason": "no supported KiCad or Gerber input found",
            "build_dir": str(root),
            "adapter": adapter_public,
            "inputs": inputs_before,
            "authority": {
                "maximum": AUTHORITY_CEILING,
                "may_authorize_release": False,
            },
        }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_root = root / "build_compilation" / "reviews" / "kicad_happy" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    executable = python_executable or sys.executable

    analyses: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    invocations: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    for analyzer_type, input_path, script_path in plan:
        output_path = run_root / f"{analyzer_type}.json"
        command = [
            executable,
            str(script_path),
            str(input_path),
            "--output",
            str(output_path),
        ]
        invocation = _run_process(
            command,
            cwd=Path(str(adapter["root"])),
            timeout_s=timeout_s,
        )
        invocation["analyzer_type"] = analyzer_type
        invocation["input"] = _safe_relative(root, input_path)
        invocations.append(invocation)

        if invocation["timed_out"]:
            failures.append(
                {
                    "analyzer_type": analyzer_type,
                    "reason": "timeout",
                    "detail": f"Analyzer exceeded {timeout_s:g} seconds.",
                }
            )
            continue
        if invocation["exit_code"] != 0:
            failures.append(
                {
                    "analyzer_type": analyzer_type,
                    "reason": "nonzero_exit",
                    "detail": invocation["stderr"] or invocation["stdout"],
                }
            )
            continue

        try:
            if output_path.is_file():
                raw_payload = json.loads(output_path.read_text(encoding="utf-8"))
            else:
                raw_payload = json.loads(invocation["stdout"])
            if not isinstance(raw_payload, Mapping):
                raise ValueError("analyzer output must be a JSON object")
            normalized = _normalize_analysis(raw_payload, analyzer_type=analyzer_type)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failures.append(
                {
                    "analyzer_type": analyzer_type,
                    "reason": "invalid_output",
                    "detail": str(exc),
                }
            )
            continue

        analyses.append(normalized)
        findings.extend(normalized["findings"])
        if output_path.is_file():
            artifacts.append(
                {
                    "kind": "raw_analysis",
                    "analyzer_type": analyzer_type,
                    "relative": _safe_relative(root, output_path),
                    "sha256": _sha256_file(output_path),
                }
            )

    inputs_after = _input_records(root, selected)
    before_hashes = {
        (row["analyzer_type"], row["path"]): row["sha256"]
        for row in inputs_before
    }
    mutated = [
        row
        for row in inputs_after
        if before_hashes.get((row["analyzer_type"], row["path"])) != row["sha256"]
    ]
    if mutated:
        failures.append(
            {
                "analyzer_type": "adapter",
                "reason": "input_mutation_detected",
                "detail": "Read-only analyzer changed one or more source artifacts.",
                "mutated_inputs": mutated,
            }
        )
        analyses = []
        findings = []

    summary = _review_summary(findings, analyses, failures)
    ok = bool(analyses) and not mutated
    latest_path = _latest_review_path(root)
    artifacts.append(
        {
            "kind": "normalized_review",
            "relative": _safe_relative(root, latest_path),
        }
    )
    payload: dict[str, Any] = {
        "ok": ok,
        "cached": False,
        "schema_version": "hardware_splicer.engineering_review.v1",
        "run_id": run_id,
        "created_at": _utc_now(),
        "build_dir": str(root),
        "cache_key": cache_key,
        "adapter": adapter_public,
        "authority": {
            "maximum": AUTHORITY_CEILING,
            "may_block_release": True,
            "may_authorize_release": False,
            "statement": (
                "External analyzer output is observed evidence only. "
                "KiCad truth, bench evidence, and human authorization remain independent."
            ),
        },
        "release_effect": (
            "blocked"
            if summary["blocker_count"]
            else "review_required"
            if summary["warning_count"] or failures
            else "no_external_blockers"
        ),
        "summary": summary,
        "inputs": inputs_before,
        "analyses": analyses,
        "findings": findings,
        "failures": failures,
        "invocations": invocations,
        "artifacts": artifacts,
    }

    if failures:
        casefile = run_root / "CASEFILE.json"
        _atomic_json(
            casefile,
            {
                "schema_version": "hardware_splicer.engineering_review_casefile.v1",
                "run_id": run_id,
                "created_at": payload["created_at"],
                "adapter": adapter_public,
                "inputs": inputs_before,
                "failures": failures,
                "invocations": invocations,
            },
        )
        payload["artifacts"].append(
            {
                "kind": "casefile",
                "relative": _safe_relative(root, casefile),
                "sha256": _sha256_file(casefile),
            }
        )

    _atomic_json(latest_path, payload)
    return payload
