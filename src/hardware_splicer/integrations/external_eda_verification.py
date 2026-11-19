"""Optional, pinned external EDA checkers with independent native KiCad authority.

No agent installation or arbitrary command runner: only KiSkill kx check,
akcli verify, and kicad-cli pcb drc. The commands operate on copied inputs.
This is not a hardened OS sandbox; only evaluate trusted, reviewed source.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path


DRC_PATTERNS = {
    "violations": r"Found\s+(\d+)\s+DRC violations",
    "unconnected_pads": r"Found\s+(\d+)\s+unconnected pads",
    "footprint_errors": r"Found\s+(\d+)\s+Footprint errors",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_source(repo: Path, expected_commit: str) -> dict:
    repo = repo.resolve(strict=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, timeout=10
    ).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", expected_commit) or commit != expected_commit:
        raise ValueError("external engine commit differs from reviewed lock")
    license_file = repo / "LICENSE"
    if not license_file.is_file() or "MIT License" not in license_file.read_text():
        raise ValueError("external engine license was not verified as MIT")
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain"], text=True, timeout=10
    ).strip():
        raise ValueError("external engine checkout has local modifications")
    return {"commit": commit, "license": "MIT", "license_sha256": digest(license_file)}


def parse_native_drc(report: str) -> dict[str, int] | None:
    counts: dict[str, int] = {}
    for key, pattern in DRC_PATTERNS.items():
        matches = re.findall(pattern, report)
        if len(matches) != 1:
            return None
        counts[key] = int(matches[0])
    return counts


def verdict(kx_exit: int, akcli_report: dict | None, drc: dict | None,
            native_exit: int) -> dict:
    structural = (kx_exit == 0)
    connectivity = (isinstance(akcli_report, dict)
                    and akcli_report.get("equivalent") is True
                    and akcli_report.get("mode") == "sch-pcb")
    native = (native_exit == 0 and drc is not None
              and all(value == 0 for value in drc.values()))
    return {
        "kiskill_roundtrip": structural,
        "akcli_schematic_pcb_equivalent": bool(connectivity),
        "native_kicad_drc_clean": native,
        "digital_review_pass": bool(structural and connectivity and native),
        "physical_test_performed": False,
    }


def invoke(label: str, command: list[str], work: Path,
           timeout_seconds: int = 90) -> tuple[dict, bytes]:
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=work, capture_output=True,
                                timeout=timeout_seconds, check=False)
        rc = result.returncode
        stdout, stderr = result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        rc = -1
        stdout = exc.stdout or b""
        stderr = (exc.stderr or b"") + b"\nTimed out"
    (work / (label + ".stdout.txt")).write_bytes(stdout)
    (work / (label + ".stderr.txt")).write_bytes(stderr)
    return {
        "exit_code": rc,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }, stdout


def verify_board(
    schematic: Path,
    board: Path,
    output: Path,
    *,
    kiskill_repo: Path,
    kiskill_commit: str,
    akcli_repo: Path,
    akcli_commit: str,
    native_cli: str = "kicad-cli",
) -> dict:
    schematic, board = Path(schematic).resolve(strict=True), Path(board).resolve(strict=True)
    if schematic.suffix != ".kicad_sch" or board.suffix != ".kicad_pcb":
        raise ValueError("expected native KiCad schematic and PCB")
    sources = {"schematic": digest(schematic), "board": digest(board)}
    kx = pinned_source(kiskill_repo, kiskill_commit)
    ak = pinned_source(akcli_repo, akcli_commit)
    native = shutil.which(native_cli)
    if not native:
        raise FileNotFoundError("native KiCad CLI unavailable")
    kx_bin = Path(kiskill_repo).resolve() / "bin/kx"
    ak_bin = Path(akcli_repo).resolve() / "bin/akcli"
    if not kx_bin.is_file() or not ak_bin.is_file():
        raise FileNotFoundError("verified engine has no expected CLI")

    work = Path(output).resolve()
    if work == schematic.parent or work == board.parent:
        raise ValueError("output must not overwrite source directory")
    work.mkdir(parents=True, exist_ok=True)
    ins = work / "inputs"
    ins.mkdir(exist_ok=True)
    copied_sch, copied_pcb = ins / "design.kicad_sch", ins / "design.kicad_pcb"
    shutil.copyfile(schematic, copied_sch)
    shutil.copyfile(board, copied_pcb)
    if digest(copied_sch) != sources["schematic"] or digest(copied_pcb) != sources["board"]:
        raise ValueError("input snapshot differs from original source")

    kx_run, _ = invoke("kiskill", [str(kx_bin), "check", str(copied_pcb)], work)
    akcli_run, akcli_output = invoke(
        "akcli", [str(ak_bin), "--json", "verify",
                  str(copied_sch), str(copied_pcb)], work
    )
    try:
        akcli_report = json.loads(akcli_output)
    except (ValueError, UnicodeDecodeError):
        akcli_report = None
    native_run, _ = invoke(
        "native-kicad",
        [native, "pcb", "drc", "--output", str(work / "native-drc.rpt"),
         str(copied_pcb)], work
    )
    report_file = work / "native-drc.rpt"
    native_report = report_file.read_text(errors="replace") if report_file.is_file() else ""
    drc = parse_native_drc(native_report)
    checks = verdict(kx_run["exit_code"], akcli_report, drc, native_run["exit_code"])
    if any(digest(p) != sources[k] for k, p in
           (("schematic", schematic), ("board", board))):
        raise ValueError("source bytes unexpectedly changed")
    if digest(copied_sch) != sources["schematic"] or digest(copied_pcb) != sources["board"]:
        raise ValueError("external verifier modified its input copy")

    receipt = {
        "schema": "hs.external_eda_verification.v1",
        "source_sha256": sources,
        "upstream": {"kiskill": kx, "akcli": ak},
        "commands": {"kiskill": kx_run, "akcli": akcli_run, "native_kicad": native_run},
        "native_drc_counts": drc,
        "akcli_findings": [
            {"code": f.get("code"), "severity": f.get("severity")}
            for f in ((akcli_report or {}).get("findings") or [])
        ] if isinstance(akcli_report, dict) else [],
        "checks": checks,
        "limits": [
            "External tools are read-only on copied inputs, not OS-sandboxed",
            "No manufacturer, physical contact, or powered-device validation",
            "Equivalence and DRC do not establish electrical design intent",
        ],
    }
    (work / "verification-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
