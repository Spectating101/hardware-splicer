"""HS GitHub-source-native engineering task router, with two *reviewed* adapters.

The deterministic selection is transparent capability matching, NOT an LLM or
general-purpose automatic installation of discovered GitHub repositories.

Supported tasks:
- review an existing KiCad schematic with pinned akcli (reuse v1 integration)
- compare two committed versions of a KiCad PCB with pinned kdif, which drives
  the actual KiCad CLI and creates an interactive, source-based HTML diff.

No discovery result alone authorizes tool execution, hardware control,
electrical correctness or fabrication.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .github_signal_pipeline import (
    ADAPTERS,
    SignalEvaluationError,
    acquire_pinned_repo,
    evaluate_signals,
    normalize_feed,
    registry_row as akcli_registry_row,
    sha256_file,
)

TASK_SCHEMA = "hardware_splicer.github_signal_task.v1"
VERDICT_FILENAME = "HS_SIGNAL_TASK_RESULT.json"
KDIF_CAPABILITY_FILENAME = "HS_SIGNAL_KDIF_CAPABILITY.json"
KDIF_HTML_FILENAME = "HS_SIGNAL_KDIF_REVISIONS.html"
# Official KiCad kicad-cli container image, pre-pulled by CI/host.
# Docker is selected explicitly and never used as an implicit bwrap fallback.
KDIF_DOCKER_IMAGE = (
    "kicad/kicad@sha256:f36b185970d398b84c095ace896046798ff60d458ce59d49669c4633c304cfbd"
)

_SELECT_WORDS = {
    "review_schematic": re.compile(
        r"\b(review|inspect|check|lint|audit|diagnos\w*|validate)\b", re.I
    ),
    "compare_board_revisions": re.compile(
        r"\b(compare|comparisons?|diff|differences?|changed|changes|revisions?|"
        r"before[\s-]+after|version[\s-]+history)\b", re.I
    ),
}
_TARGET_REPOS = {
    "review_schematic": "tipoLi5890/akcli",
    "compare_board_revisions": "0x12net/kdif",
}
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def select_task(objective: str) -> dict[str, Any]:
    if not isinstance(objective, str) or len(objective) > 1000:
        raise SignalEvaluationError("objective must be plain text under 1000 characters")
    matched = {
        task: sorted({x.lower() for x in matcher.findall(objective)})
        for task, matcher in _SELECT_WORDS.items()
    }
    selected = [task for task, found in matched.items() if found]
    if len(selected) != 1:
        raise SignalEvaluationError(
            "ambiguous/unsupported objective; specify either design review OR "
            "two-revision comparison"
        )
    return {
        "selected_task": selected[0],
        "selected_repository": _TARGET_REPOS[selected[0]],
        "reason": "deterministic evidence-bounded keyword-to-capability matching",
        "matched_terms": matched[selected[0]],
        "selection_model": "rules_v1_not_an_llm",
    }


def _git(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    p = subprocess.run(
        ["git", "-C", str(repo), *args], check=True,
        capture_output=True, timeout=20, text=not binary,
    )
    return p.stdout


def _verify_board_history(
    board_repo: Path, board: Path, revision_a: str, revision_b: str
) -> dict[str, Any]:
    if not _HEX40.fullmatch(revision_a) or not _HEX40.fullmatch(revision_b):
        raise SignalEvaluationError("board history requires two full 40-hex commit SHAs")
    if revision_a == revision_b:
        raise SignalEvaluationError("board revision SHAs must be distinct")
    root = board_repo.resolve()
    file = board.resolve()
    if not file.is_relative_to(root) or file.suffix != ".kicad_pcb":
        raise SignalEvaluationError("board must be an existing .kicad_pcb inside its Git repo")
    if board.is_symlink() or board.stat().st_size > 12 * 1024 * 1024:
        raise SignalEvaluationError("board symlink or oversized board is not allowed")
    if not (root / ".git").is_dir():
        raise SignalEvaluationError("board source needs a local non-bare Git history")
    if str(_git(root, "rev-parse", "--show-toplevel")).strip() != str(root):
        raise SignalEvaluationError("board repo root does not match requested checkout")
    if str(_git(root, "status", "--porcelain", "--untracked-files=all")).strip():
        raise SignalEvaluationError("board source has uncommitted/untracked changes")
    rel = file.relative_to(root).as_posix()
    snapshots = []
    for rev in (revision_a, revision_b):
        try:
            verified = str(_git(root, "rev-parse", "--verify", rev + "^{commit}"))
            if verified.strip() != rev:
                raise SignalEvaluationError("requested commit is not a valid full revision")
            raw = _git(root, "show", f"{rev}:{rel}", binary=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise SignalEvaluationError(
                "requested commit or historical board file does not exist"
            ) from exc
        if len(raw) > 12 * 1024 * 1024:
            raise SignalEvaluationError("historical board larger than supported bound")
        snapshots.append(hashlib.sha256(raw).hexdigest())
    return {
        "file_name": board.name,
        "file_in_repo": rel,
        "revision_a": revision_a,
        "revision_b": revision_b,
        "revision_a_file_sha256": snapshots[0],
        "revision_b_file_sha256": snapshots[1],
        "working_tree_sha256": sha256_file(board),
        "revisions_have_distinct_bytes": snapshots[0] != snapshots[1],
    }


def _kdif_bwrap_args(
    checkout: Path, board_repo: Path, board_relative: str, revisions: tuple[str, str],
    output_dir: Path,
) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SignalEvaluationError("bubblewrap unavailable; never run kdif directly on host")
    return [
        bwrap, "--die-with-parent", "--new-session", "--unshare-net", "--clearenv",
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "PYTHONPATH", "/opt/kdif",
        "--setenv", "HOME", "/tmp",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/etc", "/etc",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--ro-bind", str(checkout.resolve()), "/opt/kdif",
        "--ro-bind", str(board_repo.resolve()), "/workspace",
        "--bind", str(output_dir.resolve()), "/output",
        "--chdir", "/workspace",
        "/usr/bin/python3", "-B", "-m", "kdif",
        "/workspace/" + board_relative,
        "-r", revisions[0], "-r", revisions[1],
        "-l", "F.SilkS", "-j", "1", "--workdir", "/tmp",
        "--kicad-cli", "/usr/bin/kicad-cli",
        "-o", "/output/" + KDIF_HTML_FILENAME,
    ]


def _kdif_docker_args(
    checkout: Path, board_repo: Path, board_relative: str, revisions: tuple[str, str],
    output_dir: Path,
) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise SignalEvaluationError("Docker absent; refusing non-isolated kdif execution")
    paths = [str(p.resolve()) for p in (checkout, board_repo, output_dir)]
    if any(":" in path for path in paths):
        raise SignalEvaluationError("Docker bind-mount paths containing colon are unsupported")
    return [
        docker, "run", "--rm", "--pull=never",
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit=64",
        "--memory=1500m", "--cpus=2",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--tmpfs", "/tmp:rw,nosuid,size=256m",
        "--volume", paths[0] + ":/opt/kdif:ro",
        "--volume", paths[1] + ":/workspace:ro",
        "--volume", paths[2] + ":/output:rw",
        "--workdir", "/workspace",
        "--env", "HOME=/tmp",
        "--env", "PYTHONPATH=/opt/kdif",
        "--env", "XDG_CONFIG_HOME=/tmp",
        "--entrypoint", "/usr/bin/python3",
        KDIF_DOCKER_IMAGE,
        "-B", "-m", "kdif",
        "/workspace/" + board_relative,
        "-r", revisions[0], "-r", revisions[1],
        "-l", "F.SilkS", "-j", "1", "--workdir", "/tmp",
        "--kicad-cli", "/usr/bin/kicad-cli",
        "-o", "/output/" + KDIF_HTML_FILENAME,
    ]


def _run_kdif(
    *,
    candidate: Mapping[str, Any],
    checkout: Path,
    board_repo: Path,
    board: Path,
    revision_a: str,
    revision_b: str,
    output_dir: Path,
    fetch: bool,
    run_fn: Any | None = None,
    sandbox_backend: str = "bwrap",
) -> dict[str, Any]:
    if sandbox_backend not in {"bwrap", "docker"}:
        raise SignalEvaluationError("unsupported execution sandbox")
    if candidate["repository"] != "0x12net/kdif" or candidate["discovered_only"]:
        raise SignalEvaluationError("kdif adapter not approved at this revision")
    if candidate["license_claim"] != "MIT":
        raise SignalEvaluationError("unverified/non-MIT source metadata")
    history = _verify_board_history(board_repo, board, revision_a, revision_b)
    if not history["revisions_have_distinct_bytes"]:
        raise SignalEvaluationError("revisions contain identical board contents")
    source = acquire_pinned_repo(candidate, checkout, fetch=fetch)
    if not output_dir.exists() or output_dir.is_symlink():
        raise SignalEvaluationError("output directory absent or is a symlink")
    if (output_dir / KDIF_HTML_FILENAME).exists():
        raise SignalEvaluationError("refusing to overwrite existing native diff evidence")
    args_builder = (
        _kdif_bwrap_args if sandbox_backend == "bwrap" else _kdif_docker_args
    )
    args = args_builder(
        source, board_repo, history["file_in_repo"],
        (revision_a, revision_b), output_dir,
    )
    run = run_fn or subprocess.run
    result = run(
        args, capture_output=True, text=True, timeout=170, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    if result.returncode != 0:
        raise SignalEvaluationError(
            "kdif isolated native invocation failed: " + str(result.stderr or "")[-500:]
        )
    artifact = output_dir / KDIF_HTML_FILENAME
    if not artifact.is_file() or not (2000 <= artifact.stat().st_size <= 15 * 1024 * 1024):
        raise SignalEvaluationError("native kdif HTML missing or outside size bounds")
    body = artifact.read_bytes()
    prefix = body[:4096].lower()
    if (
        b"<!doctype html>" not in prefix
        or b"<title>kicad diff</title>" not in prefix
        or b"</html>" not in body[-2048:].lower()
    ):
        raise SignalEvaluationError("native kdif HTML signature missing")
    return {
        "id": ADAPTERS["0x12net/kdif"]["capability_id"],
        "repository": candidate["repository"],
        "repository_url": candidate["url"],
        "pinned_revision": candidate["commit_sha"],
        "license": "MIT",
        "artifact": KDIF_HTML_FILENAME,
        "artifact_sha256": sha256_file(artifact),
        "artifact_bytes": artifact.stat().st_size,
        "input": history,
        "sandbox_backend": sandbox_backend,
        "network_isolated": True,
        "execution_proven": True,
        "project_used": True,
        "source_commit_verified": True,
        "source_license_verified": True,
        "physical_authority": False,
        "electrical_correctness_verified": False,
        "fab_approved": False,
        "evidence_label": "Controlled PCB Git revision comparison; not production redesign",
        "next_action": "Engineer reviews interactive diff against design intent",
    }


def run_task(
    *,
    objective: str,
    feed: Mapping[str, Any],
    output_dir: Path,
    checkout_base: Path,
    schematic: Path | None = None,
    board_repo: Path | None = None,
    board: Path | None = None,
    revision_a: str | None = None,
    revision_b: str | None = None,
    fetch: bool = False,
    run_fn: Any | None = None,
    sandbox_backend: str = "bwrap",
) -> dict[str, Any]:
    """Choose one approved specialist from objective + compatible input.

    This is *not* an LLM reasoning benchmark. The whole selection is explicit
    and deterministic, to establish a dependable execution substrate for a
    future engineering agent to call.
    """
    plan = select_task(objective)
    candidates = normalize_feed(feed)
    selected = [c for c in candidates if c["repository"] == plan["selected_repository"]]
    if len(selected) != 1 or selected[0]["discovered_only"]:
        raise SignalEvaluationError("selected specialist absent or revision unapproved")
    output_dir.mkdir(parents=True, exist_ok=True)
    checkout = checkout_base / selected[0]["repository"].replace("/", "__")
    if plan["selected_task"] == "review_schematic":
        if schematic is None or not schematic.is_file():
            raise SignalEvaluationError("schematic review requires an actual .kicad_sch")
        filtered = dict(feed)
        filtered["candidates"] = [{
            "repository": selected[0]["repository"],
            "commit_sha": selected[0]["commit_sha"],
            "license_spdx_id": selected[0]["license_claim"],
        }]
        result = evaluate_signals(
            filtered, checkout=checkout, schematic=schematic,
            output_dir=output_dir, fetch=fetch, run_fn=run_fn,
            sandbox_backend=sandbox_backend,
        )
        if result["ok"] is not True:
            raise SignalEvaluationError("akcli did not produce verified native evidence")
        cap = result["capability"]
        evidence = {
            "id": cap["id"], "artifact": cap["diagnostics_file"],
            "artifact_sha256": cap["diagnostics_sha256"],
            "native_result_kind": "schematic_findings",
            "finding_count": cap["finding_count"],
            "license": cap["license"], "source_commit": cap["pinned_revision"],
        }
    else:
        if board_repo is None or board is None or revision_a is None or revision_b is None:
            raise SignalEvaluationError("board diff requires Git repo, PCB, two full revisions")
        cap = _run_kdif(
            candidate=selected[0], checkout=checkout, board_repo=board_repo,
            board=board, revision_a=revision_a, revision_b=revision_b,
            output_dir=output_dir, fetch=fetch, run_fn=run_fn,
            sandbox_backend=sandbox_backend,
        )
        (output_dir / KDIF_CAPABILITY_FILENAME).write_text(
            json.dumps(cap, indent=2, sort_keys=True) + "\n"
        )
        evidence = {
            "id": cap["id"], "artifact": cap["artifact"],
            "artifact_sha256": cap["artifact_sha256"],
            "native_result_kind": "interactive_pcb_revision_diff",
            "license": cap["license"], "source_commit": cap["pinned_revision"],
            "input": cap["input"],
        }
    verdict = {
        "schema_version": TASK_SCHEMA,
        "ok": True,
        "objective": objective,
        "selection": plan,
        "source_type": feed.get("source"),
        "considered": [
            {"repository": c["repository"],
             "status": ("executed" if c["repository"] == plan["selected_repository"]
                        else ("discovered_only" if c["discovered_only"]
                              else "approved_not_selected"))}
            for c in candidates
        ],
        "evidence": evidence,
        "physical_authority": False,
        "verified_physical_device_operation": False,
        "tool_selection_authority": "rules_v1",
    }
    (output_dir / VERDICT_FILENAME).write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n"
    )
    return verdict


def kdif_registry_row(build_dir: Path | str | None) -> dict[str, Any] | None:
    if build_dir is None:
        return None
    root = Path(build_dir)
    verdict = root / KDIF_CAPABILITY_FILENAME
    task_result = root / VERDICT_FILENAME
    if not verdict.is_file() or not task_result.is_file():
        return None
    try:
        c = json.loads(verdict.read_text())
        t = json.loads(task_result.read_text())
        file_name = c["artifact"]
        p = (root / file_name).resolve()
        if p.parent != root.resolve() or not p.is_file():
            return None
        if (
            t["schema_version"] != TASK_SCHEMA or t["ok"] is not True
            or t["selection"]["selected_repository"] != "0x12net/kdif"
            or t["selection"]["selected_task"] != "compare_board_revisions"
            or t["evidence"]["artifact_sha256"] != c["artifact_sha256"]
            or c["id"] != ADAPTERS["0x12net/kdif"]["capability_id"]
            or c["repository"] != "0x12net/kdif"
            or c["pinned_revision"] != ADAPTERS["0x12net/kdif"]["approved_commit_sha"]
            or c["license"] != "MIT"
            or c["sandbox_backend"] not in {"bwrap", "docker"}
            or c["execution_proven"] is not True
            or c["physical_authority"] is not False
            or c["fab_approved"] is not False
            or c["electrical_correctness_verified"] is not False
            or not _HEX64.fullmatch(c["artifact_sha256"])
            or not _HEX64.fullmatch(c["input"]["revision_a_file_sha256"])
            or not _HEX64.fullmatch(c["input"]["revision_b_file_sha256"])
            or sha256_file(p) != c["artifact_sha256"]
            or p.stat().st_size != c["artifact_bytes"]
        ):
            return None
    except (OSError, KeyError, TypeError, ValueError):
        return None
    return {
        "id": c["id"],
        "name": "kdif source-pinned interactive PCB revision diff",
        "layer": "electrical",
        "status": "opt_in",
        "priority": "P2",
        "license": "MIT",
        "required": False,
        "implementation_available": True,
        "hook": "GitHub signal reviewed native kdif adapter",
        "claim": "Human-readable Git revision rendering, not physical validation",
        "runtime": {
            "discovered": True,
            "configured": True,
            "compatible": True,
            "path": c["repository_url"],
            "revision": c["pinned_revision"],
            "source": t["source_type"],
        },
        "evidence": {
            "machine_tested": True,
            "project_used": True,
            "artifact_paths": [str(p)],
            "artifact_sha256": c["artifact_sha256"],
            "revision_a": c["input"]["revision_a"],
            "revision_b": c["input"]["revision_b"],
        },
        "readiness": "project_used",
        "next_action": c["next_action"],
    }
