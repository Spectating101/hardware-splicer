"""Publish a sanitized, hash-accounted Codex/Astra observer proof bundle."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "hardware_splicer.codex_astra_public_proof_bundle.v1"

ROOT_FILES = (
    "CASE_MANIFEST.json",
    "CASE_SNAPSHOT.json",
    "CODEX_ASTRA_AUDIT.json",
    "CODEX_ASTRA_FINAL_REPORT_SCHEMA.json",
    "CODEX_ASTRA_RESOURCE_GUARD.json",
    "CODEX_ASTRA_RUN_RESULT.json",
    "CODEX_ASTRA_RUNTIME_PLAN.json",
    "CODEX_ASTRA_TRACE.jsonl",
    "DEVELOPER_INSTRUCTIONS.txt",
    "LIVE_EXECUTION_ATTEMPT.json",
)

OPTIONAL_ROOT_FILES = (
    "PRIMARY_SOURCE_ADJUDICATION.json",
)

_SECRET_PATTERNS = (
    re.compile(r"\b(?:gho|ghp|github_pat)_[A-Za-z0-9_]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
)


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _path_replacements(manifest: Mapping[str, Any]) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    configured = (
        ("backend_project_root", "$OBSERVER_DIR/BACKEND_STORE"),
        ("developer_instructions_file", "$OBSERVER_DIR/DEVELOPER_INSTRUCTIONS.txt"),
        ("snapshot_file", "$OBSERVER_DIR/CASE_SNAPSHOT.json"),
        ("observer_directory", "$OBSERVER_DIR"),
        ("hs_repo_root", "$HS_REPO_ROOT"),
        ("model_visible_workspace", "$MODEL_WORKSPACE"),
    )
    for key, replacement in configured:
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        path = Path(value)
        if key.endswith("_file") or key == "snapshot_file":
            value = str(path.parent)
            replacement = str(Path(replacement).parent)
        replacements.append((value.rstrip("/"), replacement))
    # Longest roots must win before their parents.
    return sorted(set(replacements), key=lambda row: len(row[0]), reverse=True)


def sanitize_text(value: str, replacements: list[tuple[str, str]]) -> str:
    result = value
    for source, replacement in replacements:
        result = result.replace(source, replacement)
    # Randomized launcher/Codex paths are operational noise and host-identifying data.
    result = re.sub(r"/tmp/hs-astra-budgeted-mcp-[^/\s\"']+", "$MCP_LAUNCHER_DIR", result)
    result = re.sub(r"/tmp/hs-astra-check\.[^/\s\"']+", "$CODEX_CAPTURE_DIR", result)
    result = re.sub(r"/tmp/hs-astra-[^/\s\"']+", "$EPHEMERAL_ASTRA_DIR", result)
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[REDACTED_SECRET]", result)
    return result


def _sanitize_json(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_json(child, replacements)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_json(child, replacements) for child in value]
    if isinstance(value, str):
        return sanitize_text(value, replacements)
    return value


def _sanitize_file(path: Path, replacements: list[tuple[str, str]]) -> bytes:
    if path.suffix == ".json":
        return _canonical_json(
            _sanitize_json(json.loads(path.read_text(encoding="utf-8")), replacements)
        )
    if path.suffix == ".jsonl":
        rows = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            rows.append(
                json.dumps(
                    _sanitize_json(json.loads(raw), replacements),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        return (("\n".join(rows) + "\n") if rows else "").encode("utf-8")
    return sanitize_text(path.read_text(encoding="utf-8"), replacements).encode("utf-8")


def _engineering_package_files(observer: Path) -> list[Path]:
    package_root = observer / "BACKEND_STORE"
    packages = sorted(package_root.glob("*/engineering_packages/*/MANIFEST.json"))
    if len(packages) != 1:
        raise ValueError(
            "observer must contain exactly one expanded engineering package manifest"
        )
    return sorted(packages[0].parent.glob("*"))


def publish_proof_bundle(
    *,
    observer: Path,
    destination: Path,
    run_id: str,
    repository_commit: str,
) -> dict[str, Any]:
    """Publish selected proof artifacts with original and public byte hashes."""

    observer = observer.resolve()
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("proof bundle destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)

    manifest_path = observer / "CASE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replacements = _path_replacements(manifest)
    sources = [observer / name for name in ROOT_FILES]
    sources.extend(
        path for name in OPTIONAL_ROOT_FILES if (path := observer / name).is_file()
    )
    capture_manifest = observer / "PRIMARY_SOURCES" / "CAPTURE_MANIFEST.json"
    if capture_manifest.is_file():
        sources.append(capture_manifest)
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing observer artifacts: " + ", ".join(missing))

    package_files = [path for path in _engineering_package_files(observer) if path.is_file()]
    artifact_rows: list[dict[str, Any]] = []
    for source in [*sources, *package_files]:
        if source in package_files:
            relative = Path("ENGINEERING_PACKAGE") / source.name
        elif source == capture_manifest:
            relative = Path("PRIMARY_SOURCES") / source.name
        else:
            relative = Path(source.name)
        published = _sanitize_file(source, replacements)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(published)
        original = source.read_bytes()
        artifact_rows.append(
            {
                "path": relative.as_posix(),
                "original_sha256": _sha256_bytes(original),
                "original_size_bytes": len(original),
                "published_sha256": _sha256_bytes(published),
                "published_size_bytes": len(published),
                "sanitized": original != published,
            }
        )

    audit = json.loads((observer / "CODEX_ASTRA_AUDIT.json").read_text(encoding="utf-8"))
    run_result = json.loads(
        (observer / "CODEX_ASTRA_RUN_RESULT.json").read_text(encoding="utf-8")
    )
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "repository_commit": repository_commit,
        "case_id": manifest.get("case_id"),
        "experiment_project_id": manifest.get("experiment_project_id"),
        "result": run_result.get("status"),
        "contracts": {
            key: audit.get(key)
            for key in (
                "codex_hard_truth_contract_pass",
                "codex_mission_progress_contract_pass",
                "codex_progress_provenance_contract_pass",
                "codex_final_report_contract_pass",
            )
        },
        "usage": audit.get("codex_usage"),
        "mcp_call_count": audit.get("mcp_call_count"),
        "failed_mcp_call_count": audit.get("failed_mcp_call_count"),
        "nonclaims": {
            "physical_correctness": audit.get("physical_correctness"),
            "physical_authority_granted": audit.get("physical_authority_granted"),
            "live_unseen_competence": audit.get("live_unseen_competence"),
            "source_truth_independently_validated": False,
        },
        "path_placeholders": sorted({replacement for _, replacement in replacements}),
        "artifacts": sorted(artifact_rows, key=lambda row: row["path"]),
    }
    manifest_bytes = _canonical_json(bundle)
    (destination / "PROOF_BUNDLE.json").write_bytes(manifest_bytes)

    readme = f"""# Codex/Astra proof bundle: {run_id}

This directory is a sanitized publication of one live clean-room run. The original and
published SHA-256 values are recorded in `PROOF_BUNDLE.json`; changed hashes are expected
where absolute ephemeral paths were replaced with placeholders.

The run demonstrated bounded MCP operation, revision-linked substantive project progress,
provenance, and a constrained terminal report. It did **not** prove source truth,
engineering correctness, physical correctness, fabrication readiness, or physical authority.

- repository commit: `{repository_commit}`
- case: `{manifest.get('case_id')}`
- physical correctness: `{audit.get('physical_correctness')}`
- physical authority granted: `{audit.get('physical_authority_granted')}`
- unseen competence adjudication: `{audit.get('live_unseen_competence')}`
"""
    (destination / "README.md").write_text(readme, encoding="utf-8")
    return bundle
