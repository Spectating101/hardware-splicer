#!/usr/bin/env python3
"""One entry point for the consolidated HS 5V witness software review.

Runs native CAD/SPICE and both HS->Policy Lab synthetic paths, source and
physical-evidence negative controls, and G1 interlocks. It is a REPRODUCIBLE
SOFTWARE REVIEW, never a fabrication, acquisition, calibration or power-on
authorization. Exit 2 = software review completed but mandatory physical HOLD.
Exit 1 = software/integration error; no success claim is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
HS = HERE.parents[2]
EXPECTED_POLICY_LAB_COMMIT = "9f06f669e9252d2ff105581c2aaa6750d007dcd9"  # PL #180 known integration reference
TEST_FILES = [
    "test_verify_fixture.py",
    "test_audit_readiness.py",
    "test_measurement_screen.py",
    "test_bench_candidate_replay.py",
    "test_g1_evidence_gate.py",
    "test_protection_preflight.py",
    "test_reference_scpi_bracket.py",
    "test_g1_commissioning_gate.py",
    "test_g1_stream_binding.py",
    "test_source_suitability.py",
    "test_review_witness.py",
]

PHYSICAL_FALSE = (
    "fabrication_allowed", "fabrication_released", "energization_authorized",
    "physical_ready", "metrological_agreement_proven",
)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tool(cmd, *, cwd=HERE, timeout=100, env=None):
    result = subprocess.run(cmd, cwd=cwd, text=True,
                            capture_output=True, timeout=timeout, env=env)
    return result.returncode, result.stdout, result.stderr


def must_hold(path: Path, keys: tuple[str, ...]) -> dict:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    for name in keys:
        if evidence.get(name) is not False:
            raise AssertionError(f"{path}: {name} must be explicitly false")
    return evidence


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pl-root", type=Path, required=True,
                        help="Checkout containing frozen Policy Lab PLRS-6 converter")
    parser.add_argument("--out", type=Path, required=True,
                        help="A nonexistent output DIRECTORY, outside the source tree")
    parser.add_argument("--expected-pl-commit",
                        default=EXPECTED_POLICY_LAB_COMMIT,
                        help="Pin Policy Lab receiving branch commit for reproducible replay")
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if out.exists():
        parser.error("Evidence output must not already exist")
    if out.is_relative_to(HS.resolve()):
        parser.error("Keep generated review evidence outside tracked HS checkout")
    out.mkdir(parents=True)
    report = {
        "schema": "hardware_splicer.consolidated_witness_software_review.v1",
        "overall": "SOFTWARE_INTEGRATION_UNVERIFIED_HOLD",
        "physical_ready": False, "fabrication_allowed": False,
        "energization_authorized": False, "metrological_agreement_proven": False,
        "product_certified": False,
        "require_independent_physical_operator": True,
        "steps": [],
        "repo": {},
        "dependencies": {},
    }
    report_path = out / "review.json"
    report["repo"]["git_head"] = tool(["git", "rev-parse", "HEAD"], cwd=HS)[1].strip()
    report["repo"]["branch"] = tool(["git", "branch", "--show-current"], cwd=HS)[1].strip()
    report["repo"]["source_spec_sha256"] = sha256(HERE / "station-spec-5v.json")
    report["repo"]["original_pcb_sha256"] = sha256(HERE / "low_voltage_witness_fixture_v0.kicad_pcb")
    report["repo"]["original_schematic_sha256"] = sha256(HERE / "low_voltage_witness_fixture_v0.kicad_sch")
    report["repo"]["working_tree_clean_before"] = not bool(tool(
        ["git", "status", "--porcelain"], cwd=HS
    )[1].strip())
    pl = args.pl_root.resolve()
    report["dependencies"]["policy_lab_root"] = str(pl)
    report["dependencies"]["plrs6_available"] = (
        (pl / "scripts/equipment/dc_bench_capture.mjs").is_file()
    )
    report["dependencies"]["policy_lab_commit"] = (
        tool(["git", "rev-parse", "HEAD"], cwd=pl)[1].strip()
        if report["dependencies"]["plrs6_available"] else None
    )
    report["dependencies"]["expected_policy_lab_commit"] = args.expected_pl_commit
    report["dependencies"]["policy_lab_worktree_clean"] = (
        not bool(tool(["git", "status", "--porcelain"], cwd=pl)[1].strip())
        if report["dependencies"]["plrs6_available"] else False
    )
    report["dependencies"]["executables"] = {
        name: shutil.which(name) for name in ("kicad-cli", "ngspice", "node")
    }
    try:
        import pcbnew  # type: ignore
        report["dependencies"]["pcbnew_available"] = True
    except ImportError:
        report["dependencies"]["pcbnew_available"] = False

    def step(label: str, cmd: list[str], expected_exit: int, artifact: Path | None = None,
             false_flags: tuple[str, ...] = ()) -> dict:
        code, stdout, stderr = tool(cmd, env={**os.environ, "HS_POLICY_LAB_ROOT": str(pl)})
        row = {
            "stage": label,
            "exit_code": code,
            "expected_exit_code": expected_exit,
            "stdout_tail": stdout[-850:],
            "stderr_tail": stderr[-850:],
            "passed_expected_behavior": code == expected_exit,
        }
        if artifact is not None and artifact.is_file():
            row["artifact_path"] = str(artifact)
            row["artifact_sha256"] = sha256(artifact)
            evidence = must_hold(artifact, false_flags)
            row["reported_status"] = (
                evidence.get("status") or evidence.get("decision") or
                evidence.get("structural_status") or evidence.get("research_scope")
            )
        elif artifact is not None:
            row["passed_expected_behavior"] = False
            row["error"] = "Missing output evidence: " + str(artifact)
        report["steps"].append(row)
        if not row["passed_expected_behavior"]:
            raise AssertionError(f"{label} returned {code}; expected {expected_exit}")
        return row

    try:
        if (not report["dependencies"]["plrs6_available"] or
            not report["dependencies"]["pcbnew_available"] or
            any(v is None for v in report["dependencies"]["executables"].values())):
            raise RuntimeError("Full review dependencies absent: cannot claim all stages ran")
        if not report["repo"]["working_tree_clean_before"]:
            raise RuntimeError("Uncommitted HS changes: full review requires a clean source revision")
        if not report["dependencies"]["policy_lab_worktree_clean"]:
            raise RuntimeError("Policy Lab checkout has uncommitted changes")
        if report["dependencies"]["policy_lab_commit"] != args.expected_pl_commit:
            raise RuntimeError("Policy Lab revision changed since the reviewed receiver snapshot")
        tests = step("all_unit_tests", [sys.executable, "-m", "unittest", "-q", *TEST_FILES], 0)
        match = re.search(r"Ran (\d+) tests", tests["stderr_tail"])
        if not match or ("skipped=" in tests["stderr_tail"]) or "FAILED" in tests["stderr_tail"]:
            raise AssertionError("Unit test count absent or tests were skipped/failed")
        tests["completed_tests"] = int(match.group(1))
        native = out / "native"
        step("original_native_kicad_spice_hs_pl", [
            sys.executable, str(HERE/"verify_and_replay.py"),
            "--pl-root", str(pl), "--out", str(native)
        ], 0, native/"verification.json", ("fabrication_released",))
        base = json.loads((native/"verification.json").read_text())
        if (base.get("native_erc") != "ZERO_VIOLATIONS" or
                not base.get("native_drc", "").startswith("ZERO_VIOLATIONS") or
                base.get("pl_intake_decision") !=
                "TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS"):
            raise AssertionError("Native CAD/PL verification claim inconsistent")
        a = out / "audit"
        step("legacy_7_synthetic_faults_and_physical_hold", [
            sys.executable, str(HERE/"audit_readiness.py"),
            "--pl-root", str(pl), "--native-replay", str(native),
            "--out", str(a), "--fail-if-held"
        ], 2, a/"report.json", ("fabrication_allowed", "metrological_agreement_proven"))
        audit = json.loads((a/"report.json").read_text())
        if not all(audit["checks"].values()):
            raise AssertionError("Original seven-case audit behavior changed")
        new = out / "precision_12r"
        step("12ohm_candidate_hs_pl_fixture_only", [
            sys.executable, str(HERE/"bench_candidate_replay.py"),
            "--pl-root", str(pl),
            "--baseline-verification", str(native/"verification.json"),
            "--out", str(new), "--fail-if-held"
        ], 2, new/"report.json", ("fabrication_allowed", "physical_ready"))
        source_out = out / "source_selection.json"
        step("vendor_sourcing_research_only", [
            sys.executable, str(HERE/"source_suitability.py"),
            "--out", str(source_out)
        ], 2, source_out, ("fabrication_allowed", "physical_ready", "energization_authorized"))
        p = out / "g1_packet_review.json"
        step("blank_g1_evidence_must_hold", [
            sys.executable, str(HERE/"g1_evidence_gate.py"),
            "--packet", str(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json"),
            "--out", str(p), "--fail-if-held"
        ], 2, p, ("fabrication_allowed", "energization_authorized"))
        prot = out / "protection.json"
        step("unselected_source_fuse_must_hold", [
            sys.executable, str(HERE/"protection_preflight.py"),
            "--input", str(HERE/"G1_PROTECTION_INPUT_TEMPLATE.json"),
            "--out", str(prot)
        ], 2, prot, ("fabrication_allowed", "energization_authorized"))
        mock = out / "scpi_mock"
        step("scpi_dual_meter_mock_nonphysical", [
            sys.executable, str(HERE/"reference_scpi_bracket.py"),
            "--transport", "fixture", "--samples", "3",
            "--period-s", "0.05", "--out", str(mock)
        ], 2, mock/"reference-session.json", ("fabrication_allowed", "physical_ready"))
        hold = out / "g1_combined.json"
        step("g1_combined_authority_hold", [
            sys.executable, str(HERE/"g1_commissioning_gate.py"),
            "--g1-packet", str(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json"),
            "--protection-input", str(HERE/"G1_PROTECTION_INPUT_TEMPLATE.json"),
            "--reference-session", str(mock/"reference-session.json"),
            "--out", str(hold)
        ], 2, hold, ("fabrication_allowed", "physical_ready", "energization_authorized"))
        report["overall"] = "SOFTWARE_INTEGRATION_VERIFIED_PHYSICAL_HOLD"
    except (Exception, KeyboardInterrupt) as exc:
        report["errors"] = [type(exc).__name__ + ": " + str(exc)]
        report["overall"] = "SOFTWARE_REVIEW_FAILED_OR_INCOMPLETE_HOLD"
    finally:
        report["repo"]["working_tree_clean_after"] = not bool(tool(
            ["git", "status", "--porcelain"], cwd=HS
        )[1].strip())
        if not report["repo"]["working_tree_clean_after"]:
            report.setdefault("errors", []).append("HS source checkout modified during review")
            report["overall"] = "SOFTWARE_REVIEW_FAILED_OR_INCOMPLETE_HOLD"
        report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["overall"],
        "stages_executed": len(report["steps"]),
        "tests": next((x.get("completed_tests") for x in report["steps"] if x["stage"]=="all_unit_tests"), None),
        "physical_ready": False,
        "fabrication_allowed": False,
        "report": str(report_path),
    }, indent=2))
    return 2 if report["overall"] == "SOFTWARE_INTEGRATION_VERIFIED_PHYSICAL_HOLD" else 1


if __name__ == "__main__":
    raise SystemExit(main())
