"""Source-pinned GitHub-signal discovery -> sandboxed HS capability proof.

An external repository is never executed merely because GitHub discovery
returned it. Unknown repositories enter the *discovered_only* registry state.
Only a reviewer-approved, exact repository/adapter pair can be run, from an
exact 40-hex commit, with source license verified against the checkout.

First supported adapter: tipoLi5890/akcli -- read-only schematic diagnostics.
No installers, arbitrary command execution, device access, firmware flashing,
network from the tool sandbox, or authorization to fabricate are supported.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "hardware_splicer.github_signal_capability.v1"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ADAPTERS = {
    "tipoLi5890/akcli": {
        # Exact approved source revision, not arbitrary future upstream HEAD.
        # Upgrades need a fresh engineering/security review and new tests.
        "approved_commit_sha": "2126c328402fa77f8f6bf2114f052595f86f14aa",
        "capability_id": "signal-akcli-schematic-review",
        "name": "akcli external schematic analysis",
        "layer": "electrical",
        "adapter": "akcli_readonly_schematic_check",
        "license": "MIT",
        "input_suffix": ".kicad_sch",
        "command": ["python3", "-m", "akcli", "check", "/input.kicad_sch", "--format", "json", "--fail-on", "never"],
    }
}


class SignalEvaluationError(ValueError):
    """Fail-closed candidate admission or adapter errors."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def normalize_feed(feed: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Read a normalized exported signal; it is NOT a live Github Signals API."""
    if feed.get("schema_version") != "hardware_splicer.github_signal_feed.v1":
        raise SignalEvaluationError("unknown signal feed schema")
    source = feed.get("source")
    if source not in {"github_repository_search", "github_signals_export"}:
        raise SignalEvaluationError("unknown provenance provider")
    raw = feed.get("candidates")
    if not isinstance(raw, list) or not raw or len(raw) > 100:
        raise SignalEvaluationError("expected 1-100 candidate records")
    out = []
    seen = set()
    for record in raw:
        if not isinstance(record, Mapping):
            raise SignalEvaluationError("invalid candidate record")
        repo = str(record.get("repository", ""))
        revision = str(record.get("commit_sha", ""))
        if not ID_PATTERN.fullmatch(repo) or not SHA_PATTERN.fullmatch(revision):
            raise SignalEvaluationError("invalid owner/repo or non-full source pin")
        if repo.lower() in seen:
            raise SignalEvaluationError("duplicate repository entries")
        seen.add(repo.lower())
        # Feed-provided licenses are metadata, NOT permission to run. Both
        # the reviewed repository and its *exact* approved commit are required.
        # Any newer upstream revision stays discovery-only until reviewed.
        adapter = ADAPTERS.get(repo)
        admitted = bool(adapter and revision == adapter["approved_commit_sha"])
        out.append({
            "repository": repo, "commit_sha": revision,
            "license_claim": str(record.get("license_spdx_id", "UNKNOWN")),
            "url": "https://github.com/" + repo,
            "discovery_source": source,
            "discovered_only": not admitted,
            "adapter_id": adapter.get("capability_id") if admitted else None,
        })
    return out


def acquire_pinned_repo(candidate: Mapping[str, Any], checkout: Path, *, fetch: bool) -> Path:
    repo = str(candidate["repository"])
    revision = str(candidate["commit_sha"])
    if repo not in ADAPTERS:
        raise SignalEvaluationError("no reviewed adapter for this repository")
    if revision != ADAPTERS[repo]["approved_commit_sha"]:
        raise SignalEvaluationError("source revision not approved for this adapter")
    if not SHA_PATTERN.fullmatch(revision):
        raise SignalEvaluationError("invalid source revision")
    if fetch:
        if checkout.exists():
            raise SignalEvaluationError("refusing fetch into an existing checkout")
        checkout.parent.mkdir(parents=True, exist_ok=True)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(checkout.parent),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        # Only a hard-coded, approved GitHub owner/repo is reachable. No hooks,
        # recursively initialized submodules, pip installs or upstream scripts.
        subprocess.run(
            ["git", "-c", "protocol.file.allow=never",
             "-c", "core.hooksPath=/dev/null", "clone", "--quiet",
             "--filter=blob:none", "--no-checkout", "--depth=1",
             "https://github.com/" + repo + ".git", str(checkout)],
            env=env, check=True, timeout=90,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "-C", str(checkout), "-c", "core.hooksPath=/dev/null",
             "fetch", "--quiet", "--depth=1", "origin", revision],
            env=env, check=True, timeout=90,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "-C", str(checkout), "-c", "core.hooksPath=/dev/null",
             "checkout", "--quiet", "--detach", revision],
            env=env, check=True, timeout=50,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise SignalEvaluationError("source checkout absent or not a Git repo")
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=5,
    )
    if result.stdout.strip() != revision:
        raise SignalEvaluationError("source checkout SHA differs from pinned candidate")
    # Reject modified tracked source and injected untracked files. A correct
    # commit hash does not by itself prove the on-disk Python is unmodified.
    status = subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain",
         "--untracked-files=all"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    if status.stdout.strip():
        raise SignalEvaluationError(
            "source checkout dirty; executed bytes do not match pinned commit"
        )
    license_file = checkout / "LICENSE"
    if not license_file.is_file() or not license_file.read_text(
        encoding="utf-8", errors="replace"
    ).startswith("MIT License\n"):
        raise SignalEvaluationError("MIT license not independently verified")
    if candidate["license_claim"] != "MIT":
        raise SignalEvaluationError("feed license metadata inconsistent with checkout")
    if not (checkout / "src" / "akcli" / "__main__.py").is_file():
        raise SignalEvaluationError("reviewed akcli module entrypoint missing")
    return checkout


def _bwrap_args(checkout: Path, schematic: Path) -> list[str]:
    """No shell: fixed, read-only adapter in a network-isolated container."""
    executable = shutil.which("bwrap")
    if not executable:
        raise SignalEvaluationError("bubblewrap required; refusing unsandboxed run")
    # Never mount user home, Docker socket, SSH credentials, or real devices.
    # This does NOT assert protection against all hostile code/kernel exploits.
    return [
        executable, "--die-with-parent", "--new-session", "--unshare-net",
        "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "PYTHONPATH", "/opt/akcli/src",
        "--setenv", "HOME", "/tmp", "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64", "--ro-bind", "/etc", "/etc",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--ro-bind", str(checkout.resolve()), "/opt/akcli",
        "--ro-bind", str(schematic.resolve()), "/input.kicad_sch",
        "--chdir", "/opt/akcli",
        "/usr/bin/python3", "-m", "akcli", "check",
        "/input.kicad_sch", "--format", "json", "--fail-on", "never",
    ]


def evaluate_signals(
    feed: Mapping[str, Any],
    *,
    checkout: Path,
    schematic: Path,
    output_dir: Path,
    fetch: bool = False,
    run_fn: Any = None,
) -> dict[str, Any]:
    """Evaluate one known compatible candidate, inventory all other signals.

    The signal feed is untrusted; allowlisting, a real source pin and a verified
    license are required before the external program executes. Output rows
    distinguish diagnostic execution from an electrically correct or fabricated
    engineering design.
    """
    candidates = normalize_feed(feed)
    evaluations: list[dict[str, Any]] = []
    approved = [c for c in candidates if not c["discovered_only"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        if candidate["discovered_only"]:
            evaluations.append({
                **candidate, "state": "discovered_only",
                "executed": False, "reason": "No approved repo/adapter/revision pair",
            })
    if not approved:
        payload = {
            "ok": False, "schema_version": SCHEMA,
            "candidates": evaluations,
            "capability": None,
            "physical_authority": False,
        }
        (output_dir / "HS_SIGNAL_CAPABILITY_VERDICT.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return payload
    if len(approved) != 1:
        raise SignalEvaluationError("one reviewed candidate per evaluation required")
    candidate = approved[0]
    spec = ADAPTERS[candidate["repository"]]
    if schematic.suffix != spec["input_suffix"] or not schematic.is_file():
        raise SignalEvaluationError("only existing KiCad .kicad_sch inputs supported")
    if schematic.stat().st_size > 12 * 1024 * 1024:
        raise SignalEvaluationError("schematic larger than declared 12 MiB bound")
    pinned = acquire_pinned_repo(candidate, checkout, fetch=fetch)
    command = _bwrap_args(pinned, schematic)
    runner = run_fn or subprocess.run
    result = runner(
        command, check=False, capture_output=True, text=True,
        timeout=75, env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    if int(result.returncode) != 0:
        raise SignalEvaluationError(
            "sandboxed native tool failed (no success registered): " +
            str(result.stderr or "")[-500:]
        )
    if len(result.stdout) > 1024 * 1024:
        raise SignalEvaluationError("native tool output exceeds 1 MiB limit")
    try:
        output = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise SignalEvaluationError("native tool output not valid JSON") from exc
    if not isinstance(output, dict) or not isinstance(output.get("findings"), list):
        raise SignalEvaluationError("native tool diagnostics missing findings list")
    if len(output["findings"]) > 10000 or any(
        not isinstance(x, dict) or
        x.get("severity") not in {"info", "note", "warning", "error"} or
        not isinstance(x.get("code"), str)
        for x in output["findings"]
    ):
        raise SignalEvaluationError("native findings schema not safe to import")
    diagnostics = output_dir / "akcli_schematic_findings.json"
    diagnostics.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    counts = dict(sorted(Counter(
        x["severity"] for x in output["findings"]
    ).items()))
    capability = {
        "id": spec["capability_id"],
        "name": spec["name"],
        "layer": spec["layer"],
        "adapter": spec["adapter"],
        "repository": candidate["repository"],
        "repository_url": candidate["url"],
        "pinned_revision": candidate["commit_sha"],
        "license": "MIT",
        "source": candidate["discovery_source"],
        "input_sha256": sha256_file(schematic),
        "input_name": schematic.name,
        "diagnostics_file": diagnostics.name,
        "diagnostics_sha256": sha256_file(diagnostics),
        "findings": counts,
        "finding_count": len(output["findings"]),
        "discovered": True, "license_checked": True,
        "source_pin_checked": True, "compatible_input": True,
        "machine_tested": True, "project_used": True,
        "native_upstream_executed": True,
        "execution_isolated_from_network": True,
        "read_only_tool_invocation": True,
        "electrical_correctness_verified": False,
        "fabrication_authorized": False,
        "physical_device_connected": False,
        "next_action": "Human review of heuristic diagnostics; no automatic board changes.",
    }
    evaluations.append({
        **candidate, "state": "executed_native",
        "executed": True,
        "capability_id": capability["id"],
    })
    payload = {
        "ok": True, "schema_version": SCHEMA,
        "discovery_note": "Normalized GitHub search/signal input, not a live GitHub Signals API.",
        "candidates": evaluations,
        "capability": capability,
        "physical_authority": False,
    }
    (output_dir / "HS_SIGNAL_CAPABILITY_VERDICT.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def registry_row(build_dir: Path | str | None) -> dict[str, Any] | None:
    """Expose only measured, hash-matching signal adapters in the HS registry."""
    if build_dir is None:
        return None
    root = Path(build_dir)
    p = root / "HS_SIGNAL_CAPABILITY_VERDICT.json"
    if not p.is_file():
        return None
    try:
        row = json.loads(p.read_text())
        cap = row["capability"]
        if row.get("schema_version") != SCHEMA or row.get("ok") is not True:
            return None
        if cap["id"] != "signal-akcli-schematic-review":
            return None
        if (
            cap.get("repository") != "tipoLi5890/akcli"
            or cap.get("pinned_revision") != ADAPTERS["tipoLi5890/akcli"]["approved_commit_sha"]
            or cap.get("license") != "MIT"
            or cap.get("machine_tested") is not True
            or cap.get("native_upstream_executed") is not True
            or cap.get("fabrication_authorized") is not False
            or not re.fullmatch(r"[0-9a-f]{64}", str(cap.get("input_sha256", "")))
        ):
            return None
        file = root / cap["diagnostics_file"]
        if file.resolve().parent != root.resolve():
            return None
        if sha256_file(file) != cap["diagnostics_sha256"]:
            return None
        findings = json.loads(file.read_text())["findings"]
        if (
            len(findings) != cap["finding_count"]
            or dict(sorted(Counter(x["severity"] for x in findings).items()))
            != cap.get("findings")
        ):
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return {
        "id": cap["id"], "name": cap["name"], "layer": cap["layer"],
        "status": "opt_in", "priority": "P2", "license": cap["license"],
        "required": False,
        "implementation_available": True,
        "hook": "GitHub signal vetted native akcli diagnostic adapter",
        "claim": "Read-only external schematic heuristics; no physical authority",
        "runtime": {
            "discovered": True, "configured": True, "compatible": True,
            "path": cap["repository_url"],
            "revision": cap["pinned_revision"],
            "source": cap["source"],
        },
        "evidence": {
            "machine_tested": True,
            "project_used": True,
            "artifact_paths": [str(file)],
            "finding_count": cap["finding_count"],
            "input_sha256": cap["input_sha256"],
            "artifact_sha256": cap["diagnostics_sha256"],
        },
        "readiness": "project_used",
        "next_action": cap["next_action"],
    }
