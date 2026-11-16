"""Resumable *within-job* native KiCad proof for the fixed HS SPI reference.

No arbitrary commands, provider calls, or hardware authority. Native netlist,
ERC, and DRC are independently materialized before final HS verifier checks.
On restart, all completed report bytes and the original Git source identity
must match the frozen checkpoint before any stage may be reused.
"""
from __future__ import annotations

import contextlib
import csv
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Any

from .workshop_operator import (
    SPI_ID, SPI_ROOT, _base, _handoff, _machine_release, _registered_source_files,
    _source_path, _trace,
)

SCHEMA = "hardware_splicer.spi_native_checkpoint.v1"
STAGES = ("source", "netlist", "erc", "drc", "verification")
STAGE_OUTPUTS = {
    "netlist": ("native_reports/netlist.xml",),
    "erc": ("native_reports/erc.json", "native_reports/erc.stdout.txt"),
    "drc": ("native_reports/drc.json", "native_reports/drc.stdout.txt"),
    "verification": (
        "source_copy/verification.json", "HS_OPERATOR_RESULT.json",
        "ENGINEERING_HANDOFF.md",
    ),
}
MAX_REPORT_BYTES = 2 * 1024 * 1024
MIN_FREE_BYTES = 1024 ** 3
_SHA = re.compile(r"[a-f0-9]{64}")


class CheckpointError(ValueError):
    """Fail closed before accepting stale, partial, or mismatched evidence."""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".hs-checkpoint-", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), 0o600)
            json.dump(payload, file, sort_keys=True, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
        parent_fd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".hs-text-", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise CheckpointError("checkpoint missing, linked, or oversized")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CheckpointError("checkpoint JSON unreadable") from exc
    if not isinstance(value, dict):
        raise CheckpointError("checkpoint schema is not a JSON object")
    return value


def _safe_target(out: Path, rel: str) -> Path:
    """Reject symlink/output escapes BEFORE native KiCad is allowed to write."""
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise CheckpointError("unsafe native output path")
    target = out / rel
    if (target.is_symlink() or out.resolve() not in target.resolve().parents
            or any(parent.is_symlink() for parent in target.parents if parent != out)):
        raise CheckpointError("native output target or parent is linked or escaped")
    if target.exists() and not target.is_file():
        raise CheckpointError("native output target is not a regular file")
    return target


def _toolchain() -> dict[str, str]:
    """Pin actual native binaries across interruption, not just source bytes."""
    if not shutil.which("kicad-cli"):
        raise CheckpointError("native kicad-cli unavailable")
    try:
        result = subprocess.run(["kicad-cli", "--version"], check=True,
                                timeout=10, capture_output=True, text=True)
        import pcbnew
    except (OSError, subprocess.SubprocessError, ImportError) as exc:
        raise CheckpointError("native KiCad and pcbnew environment unavailable") from exc
    return {"kicad_cli": result.stdout.strip(), "pcbnew": pcbnew.Version()}


def _file(out: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel or ".." in Path(rel).parts or Path(rel).is_absolute():
        raise CheckpointError("unapproved report path")
    path = out / rel
    if (path.is_symlink() or out.resolve() not in path.resolve().parents
            or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES):
        raise CheckpointError("completed stage artifact missing, linked, escaped or oversized: " + rel)
    return path


def _source_inventory(root: Path) -> tuple[Path, str, dict[str, str], dict[str, str], str]:
    root = root.resolve(strict=True)
    source = _source_path(root, SPI_ROOT)
    git = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=12, check=True,
    ).stdout.strip()
    if not re.fullmatch(r"[a-f0-9]{40}", git):
        raise CheckpointError("cannot pin repository commit")
    # Retain identity parity with the existing workshop operator: its source
    # fingerprint includes tracked historical verification.json, which is
    # captured as a pinned source input but NEVER staged as a fresh receipt.
    # On execution the new native verifier must generate a new receipt.
    original_files = _registered_source_files(root, source)
    tracked = {path.relative_to(source).as_posix(): _sha(path) for path in original_files}
    staged = {name: sha for name, sha in tracked.items() if name != "verification.json"}
    if len(staged) < 9:
        raise CheckpointError("registered native SPI source inventory incomplete")
    fingerprint = hashlib.sha256(
        json.dumps(tracked, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return source, git, staged, tracked, fingerprint


def _validate_source(out: Path, source: Path, inventory: dict[str, str]) -> None:
    base = out / "source_copy"
    if base.is_symlink() or not base.is_dir():
        raise CheckpointError("staged source is absent or linked")
    for name, expected in inventory.items():
        if not _SHA.fullmatch(expected):
            raise CheckpointError("invalid pinned source hash")
        p = _file(out, "source_copy/" + name)
        if _sha(p) != expected or _sha(source / name) != expected:
            raise CheckpointError("source bytes changed after checkpoint: " + name)


def _validate_completed(out: Path, point: dict[str, Any]) -> None:
    done = point.get("completed")
    if not isinstance(done, list) or done != list(STAGES[:len(done)]):
        raise CheckpointError("checkpoint has non-prefix or duplicated stage history")
    report = point.get("artifacts_sha256")
    if not isinstance(report, dict) or set(report) != set(done):
        raise CheckpointError("checkpoint stage/receipt mismatch")
    for stage in done:
        expected_names = (tuple("source_copy/" + n for n in point["source_files"])
                          if stage == "source" else STAGE_OUTPUTS[stage])
        hashes = report[stage]
        if not isinstance(hashes, dict) or set(hashes) != set(expected_names):
            raise CheckpointError("stage expected artifacts missing: " + stage)
        for name in expected_names:
            if not isinstance(hashes[name], str) or not _SHA.fullmatch(hashes[name]):
                raise CheckpointError("invalid source or artifact digest")
            if _sha(_file(out, name)) != hashes[name]:
                raise CheckpointError("completed stage artifact hash mismatch: " + name)


@contextlib.contextmanager
def _exclusive(out: Path):
    path = out / ".checkpoint.lock"
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def _native(argv: list[str], *, stage: Path, home: Path, allow: tuple[int, ...] = (0,)) -> str:
    if not argv or argv[0] != "kicad-cli":
        raise CheckpointError("only allowlisted KiCad native tool may execute")
    env = dict(os.environ)
    for name in tuple(env):
        upper = name.upper()
        if any(s in upper for s in ("TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY", "API_KEY")):
            env.pop(name, None)
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        process = subprocess.run(
            argv, cwd=stage, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=75, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckpointError("native KiCad stage unavailable or timed out: " + type(exc).__name__) from exc
    if process.returncode not in allow:
        raise CheckpointError("native KiCad rejected stage, exit " + str(process.returncode) +
                              ": " + process.stdout[-1200:])
    return process.stdout


def _verifier(stage: Path):
    """Load the same trusted source verifier from the exact staged input copy."""
    import pcbnew  # Known local native KiCad 9 dependency.
    spec = importlib.util.spec_from_file_location(
        "_hs_staged_spi_verifier", stage / "verify_design.py"
    )
    if spec is None or spec.loader is None:
        raise CheckpointError("native verifier not importable")
    # design_checks.py and the exact verifier are source-hash-bound above.
    sys.path.insert(0, str(stage))
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def _step(stage_name: str, out: Path, source: Path, point: dict[str, Any]) -> dict[str, str]:
    stage = out / "source_copy"
    reports = out / "native_reports"
    home = out / "isolated_home"
    if stage_name == "source":
        if stage.exists() and any(stage.iterdir()):
            raise CheckpointError("uncommitted prior source stage needs human review")
        stage.mkdir(parents=True, exist_ok=True)
        if any(p.is_symlink() for p in source.rglob("*")):
            raise CheckpointError("source contains symlinks")
        for name in point["source_files"]:
            src = source / name
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        _validate_source(out, source, point["source_files"])
        return {"source_copy/" + name: _sha(_file(out, "source_copy/" + name))
                for name in point["source_files"]}
    _validate_source(out, source, point["source_files"])
    if reports.is_symlink() or home.is_symlink():
        raise CheckpointError("native report or isolated home is symlinked")
    reports.mkdir(mode=0o700, exist_ok=True)
    home.mkdir(mode=0o700, exist_ok=True)
    schematic = stage / "spi_flash_adapter_v1.kicad_sch"
    board = stage / "spi_flash_adapter_v1.kicad_pcb"
    if stage_name == "netlist":
        path = _safe_target(out, "native_reports/netlist.xml")
        _native(["kicad-cli", "sch", "export", "netlist", str(schematic),
                 "--format", "kicadxml", "-o", str(path)], stage=stage, home=home)
        # Reject incomplete native output before storing a resumable stage.
        root = ET.parse(path).getroot()
        if root.tag != "export":
            raise CheckpointError("KiCad native XML export unexpectedly shaped")
    elif stage_name == "erc":
        path = _safe_target(out, "native_reports/erc.json")
        _safe_target(out, "native_reports/erc.stdout.txt")
        text = _native(["kicad-cli", "sch", "erc", str(schematic), "-o", str(path),
                        "--format", "json", "--severity-all", "--exit-code-violations"],
                       stage=stage, home=home, allow=(0, 5))
        _atomic_text(reports / "erc.stdout.txt", text)
        verifier = _verifier(stage)
        verifier.validate_erc(_read(path), text)
    elif stage_name == "drc":
        path = _safe_target(out, "native_reports/drc.json")
        _safe_target(out, "native_reports/drc.stdout.txt")
        text = _native(["kicad-cli", "pcb", "drc", str(board), "-o", str(path),
                        "--format", "json", "--severity-all", "--schematic-parity",
                        "--exit-code-violations"], stage=stage, home=home, allow=(0, 5))
        _atomic_text(reports / "drc.stdout.txt", text)
        import pcbnew
        verifier = _verifier(stage)
        verifier.validate_drc(_read(path), text, verifier.compatible_library_footprints(
            pcbnew.LoadBoard(str(board))))
    elif stage_name == "verification":
        verifier = _verifier(stage)
        evidence = {}
        for completed in ("netlist", "erc", "drc"):
            evidence.update({
                Path(key).name: sha
                for key, sha in point["artifacts_sha256"][completed].items()
            })
        # Native ERC/DRC/netlist are NOT rerun: validate every original report
        # and the board/BOM/source contract with the exact HS native verifier.
        with contextlib.redirect_stdout(io.StringIO()):
            verifier.main(report_dir=reports, reused_native_report_hashes=evidence)
        receipt = _read(stage / "verification.json")
        checks = receipt.get("checks")
        if (receipt.get("toolchain", {}).get("kicad_cli") != point["toolchain"]["kicad_cli"]
                or receipt.get("toolchain", {}).get("pcbnew") != point["toolchain"]["pcbnew"]):
            raise CheckpointError("native verifier toolchain differs from pinned checkpoint")
        if (receipt.get("schema_version") != "hardware_splicer.reference_design_verification.v2"
                or receipt.get("result") != "pass"
                or not isinstance(checks, dict) or not checks
                or any(type(v) is not int or v != 0 for v in checks.values())):
            raise CheckpointError("HS native verification receipt did not pass exact contract")
        source_map = {
            "schematic": "spi_flash_adapter_v1.kicad_sch",
            "pcb": "spi_flash_adapter_v1.kicad_pcb",
            "project_rules": "spi_flash_adapter_v1.kicad_pro",
            "symbol_library": "HardwareSplicer.kicad_sym",
            "symbol_library_table": "sym-lib-table",
            "bom": "BOM.csv",
            "design_manifest": "design_manifest.json",
            "verifier": "verify_design.py",
            "electrical_contract": "design_checks.py",
        }
        if (set(receipt.get("artifact_sha256", {})) != set(source_map)
            or any(receipt["artifact_sha256"][k] != point["source_files"].get(name)
                   for k, name in source_map.items())):
            raise CheckpointError("HS native receipt source hashes differ from tracked inputs")
        authority = receipt.get("authority") or {}
        if (authority.get("physical_authority_granted") is not False
                or authority.get("fabrication_ready") is not False
                or authority.get("power_on_ready") is not False
                or authority.get("physical_correctness") != "UNPROVEN"
                or authority.get("modeled_evidence_only") is not True):
            raise CheckpointError("HS physical authority cannot be inferred from CAD checks")
        output = _base(SPI_ID, point["source_sha256"], execute=True)
        output["status"] = "verified_design_only_physical_blocked"
        output["engineering_acceptance"] = True
        output["open_actions"] = [
            "Independent human EE review of exact sourced design and parts.",
            "Owner approval before fabrication or power-on.",
            "Measure power, timing and host compatibility on a real assembled board.",
        ]
        for earlier in STAGES[:4]:
            _trace(output, earlier, "source-pinned native HS stage", "passed",
                   "Completed and SHA-256 checked; resumed stages reused exact outputs.")
        _trace(output, "verification", "existing verify_design.py with hash-bound native reports",
               "passed", "Native KiCad reports reused; original parity/BOM/ground checks executed.")
        output["tool_versions"] = receipt.get("toolchain") or {}
        output["artifacts_sha256"] = {
            "source_copy/verification.json": _sha(stage / "verification.json"),
            **{name: point["source_files"][name]
               for name in ("spi_flash_adapter_v1.kicad_sch", "spi_flash_adapter_v1.kicad_pcb",
                            "design_manifest.json")},
        }
        output["canonical_machine_release"] = _machine_release(output)
        _atomic_json(out / "HS_OPERATOR_RESULT.json", output)
        _atomic_text(out / "ENGINEERING_HANDOFF.md", _handoff(output))
    else:
        raise CheckpointError("unregistered native checkpoint stage")
    for item in STAGE_OUTPUTS[stage_name]:
        _file(out, item)
    return {item: _sha(_file(out, item)) for item in STAGE_OUTPUTS[stage_name]}


def run(
    *, repo_root: Path, out: Path, resume: bool = False,
    interrupt_after: str | None = None,
) -> dict[str, Any]:
    """Execute or resume one fixed SPI workload; never re-run completed stages."""
    if interrupt_after is not None and interrupt_after not in STAGES:
        raise CheckpointError("interruption stage is not allowlisted")
    out = Path(out).absolute()
    if out.is_symlink() or any(p.is_symlink() for p in out.parents):
        raise CheckpointError("operator output cannot traverse symlinks")
    repo_root = Path(repo_root).resolve(strict=True)
    source, head, source_files, tracked_source_files, fingerprint = _source_inventory(repo_root)
    toolchain = _toolchain()
    if shutil.disk_usage(out.parent).free < MIN_FREE_BYTES:
        raise CheckpointError("less than 1 GiB free: stop engineering pipeline")
    if resume:
        if not out.is_dir():
            raise CheckpointError("cannot resume missing output directory")
    else:
        if out.exists():
            raise CheckpointError("fresh run must use a nonexistent output path")
        out.mkdir(parents=True, mode=0o700)
    with _exclusive(out):
        if resume:
            point = _read(out / "checkpoint.json")
            if (point.get("schema") != SCHEMA
                    or point.get("case_id") != SPI_ID
                    or point.get("source_head") != head
                    or point.get("source_sha256") != fingerprint
                    or point.get("source_files") != source_files
                    or point.get("tracked_source_files") != tracked_source_files
                    or point.get("toolchain") != toolchain
                    or point.get("physical_authority") is not False):
                raise CheckpointError("untrusted or stale source-bound checkpoint")
            _validate_completed(out, point)
            _validate_source(out, source, source_files)
        else:
            point = {
                "schema": SCHEMA, "case_id": SPI_ID,
                "source_head": head, "source_sha256": fingerprint,
                "source_files": source_files,
                "tracked_source_files": tracked_source_files,
                "toolchain": toolchain,
                "completed": [],
                "artifacts_sha256": {}, "physical_authority": False,
                "attempts": 0, "state": "started",
            }
            _atomic_json(out / "checkpoint.json", point)
        if point["completed"] == list(STAGES):
            return {"status": "already_completed", "stages_reused": len(STAGES),
                    "stages_executed": 0, "run_dir": str(out),
                    "physical_authority": False}
        reused = len(point["completed"])
        executed = []
        for step in STAGES[reused:]:
            t0 = time.monotonic()
            hashes = _step(step, out, source, point)
            _validate_source(out, source, source_files)
            point["completed"].append(step)
            point["artifacts_sha256"][step] = hashes
            point["attempts"] += 1
            point.setdefault("timings_seconds", {})[step] = round(time.monotonic()-t0, 3)
            point["state"] = "completed" if step == STAGES[-1] else "running"
            _atomic_json(out / "checkpoint.json", point)
            executed.append(step)
            if interrupt_after == step:
                print(json.dumps({"status": "checkpointed_then_interrupted",
                                  "step": step, "previous_stages_reused": reused,
                                  "completed": point["completed"]}), flush=True)
                os._exit(77)
        return {
            "status": "verified_design_only_physical_blocked",
            "stages_reused": reused, "stages_executed": len(executed),
            "executed_stage_names": executed, "run_dir": str(out),
            "source_sha256": fingerprint, "source_head": head,
            "physical_authority": False,
            "engineering_acceptance": True,
        }
