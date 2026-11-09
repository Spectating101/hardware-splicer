"""Small real HS operator, composing existing *vetted* engineering capabilities.

This is NOT a replacement for the canonical project/AI engines. It closes a
specific workflow gap: tool selection -> a bounded software engineering action
-> independent acceptance -> an evidence-bound human handoff. No LLM result,
design-rule success or simulated bench automatically authorizes physical work.

The two deliberately different registered routes are:
* SPI_REFERENCE: reproduce the native KiCad/Python parity, ERC, DRC and BOM
  verifier on a staged *copy* of the published SPI design.
* RC_REPAIR: use existing donor/repair intake; DO NOT invoke the generic
  catalog compiler when the actual donor architecture remains unresolved.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Mapping

OPERATOR_SCHEMA = "hardware_splicer.workshop_operator.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
SPI_ROOT = "hardware/reference_designs/spi_flash_adapter_v1"
SPLICE_MANIFEST = "examples/splice/manifest.json"
SPI_ID = "spi_flash_adapter_reference"
RC_ID = "robot_repair_cafe_s3"
REGISTERED = {
    SPI_ID: {
        "description": "Independent rebuild/check of the existing SPI adapter",
        "route": "reference_native_verifier",
        "source": SPI_ROOT,
    },
    RC_ID: {
        "description": "RC toy donor diagnosis and repair/splice build",
        "route": "existing_splice_intake",
        "source": "examples/intakes/splice_robot_drive_vision_repair_brief.json",
    },
}

SAFE_REL = re.compile(r"^[a-z0-9][a-z0-9_./-]{0,240}$")
MAX_STDOUT = 4000


def _hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _source_path(root: Path, name: str) -> Path:
    if not SAFE_REL.fullmatch(name) or ".." in Path(name).parts:
        raise ValueError("unapproved source path")
    p = (root / name).resolve()
    if root != p and root not in p.parents:
        raise ValueError("source escapes controlled repository")
    if not p.exists():
        raise ValueError(f"missing registered source {name}")
    if p.is_symlink():
        raise ValueError("source cannot be a symlink")
    return p


def _record_artifacts(paths: list[Path], root: Path) -> dict[str, str]:
    """Hash files only after checking they are *in* the operator's run."""
    result: dict[str, str] = {}
    for path in sorted(paths):
        resolved = path.resolve()
        if not path.is_file() or root not in resolved.parents:
            raise ValueError("artifact is missing or escapes the output root")
        result[path.relative_to(root).as_posix()] = _hash(path)
    return result


def _base(case_id: str, source_sha256: str, *, execute: bool) -> dict[str, Any]:
    cfg = REGISTERED[case_id]
    return {
        "schema_version": OPERATOR_SCHEMA,
        "case_id": case_id,
        "objective": cfg["description"],
        "chosen_route": cfg["route"],
        "registered_source": cfg["source"],
        "source_sha256": source_sha256,
        "execute_requested": execute,
        "status": "planned_not_executed",
        "engineering_acceptance": False,
        "physical_validation": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "real_repair_confirmed": False,
        "open_actions": [],
        "trace": [],
        "artifacts_sha256": {},
    }


def _trace(report: dict[str, Any], stage: str, tool: str, state: str,
           details: str, **fields: Any) -> None:
    report["trace"].append({
        "stage": stage, "existing_engine": tool, "state": state,
        "details": details, **fields,
    })


def _native_spi(run_dir: Path, source: Path, report: dict[str, Any]) -> None:
    stage = run_dir / "source_copy"
    if any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("source references symlink outside approved design")
    shutil.copytree(source, stage, ignore=shutil.ignore_patterns(
        "out", "__pycache__", "*.rpt", ".hardware-splicer-execution-home"
    ))
    # The source may contain an older green receipt. Remove it so a crashed
    # or mocked verifier can NEVER be mistaken for this run's new evidence.
    (stage / "verification.json").unlink(missing_ok=True)
    checker = stage / "verify_design.py"
    schematic = stage / "spi_flash_adapter_v1.kicad_sch"
    pcb = stage / "spi_flash_adapter_v1.kicad_pcb"
    for path in (checker, schematic, pcb, stage / "design_checks.py",
                 stage / "design_manifest.json", stage / "BOM.csv",
                 stage / "sym-lib-table"):
        if not path.is_file():
            raise ValueError(f"reference verifier source missing {path.name}")

    original_sha = {f.name: _hash(source / f.name) for f in (schematic, pcb, checker)}
    _trace(report, "source", "published SPI reference + SHA-256", "passed",
           "Staged the complete editable reference source; no synthesized replacement.",
           source_artifacts_sha256=original_sha)
    work_home = run_dir / "isolated_home"
    work_home.mkdir()
    env = dict(os.environ)
    env["HOME"] = str(work_home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "verify_design.py"], cwd=stage,
            env=env, shell=False, text=True, capture_output=True,
            timeout=90, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _trace(report, "verification", "verify_design.py (KiCad/ERC/DRC/BOM)", "blocked",
               f"Native verifier could not complete: {type(exc).__name__}")
        report["status"] = "blocked_tool_execution"
        report["open_actions"].append("Repair the local native KiCad/pcbnew verifier environment.")
        return
    receipt_path = stage / "verification.json"
    receipt: dict[str, Any] = {}
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text())
        except (ValueError, OSError):
            pass
    # The input itself must not be silently modified by the verifier.
    post_input_sha = {name: _hash(stage / name) for name in original_sha}
    source_unchanged = original_sha == post_input_sha
    checks = receipt.get("checks") or {}
    zero_problems = bool(checks) and all(type(value) is int and value == 0 for value in checks.values())
    receipt_source = receipt.get("artifact_sha256") or {}
    receipt_files = {
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
    receipt_matches_all_sources = all(
        (stage / name).is_file() and receipt_source.get(key) == _hash(stage / name)
        for key, name in receipt_files.items()
    ) and set(receipt_source) == set(receipt_files)
    contract = receipt.get("authority") or {}
    explicitly_nonphysical = (
        contract.get("physical_authority_granted") is False
        and contract.get("fabrication_ready") is False
        and contract.get("power_on_ready") is False
        and contract.get("physical_correctness") == "UNPROVEN"
        and contract.get("modeled_evidence_only") is True
    )
    passed = (proc.returncode == 0 and
              receipt.get("schema_version") == "hardware_splicer.reference_design_verification.v2"
              and receipt.get("result") == "pass"
              and zero_problems and source_unchanged and explicitly_nonphysical
              and receipt_matches_all_sources)
    _trace(report, "verification", "existing verify_design.py -> KiCad 9 ERC/DRC/parity/BOM",
           "passed" if passed else "failed",
           "Ran the project's own full native verifier, not a fabricated CAD PASS.",
           exit_code=proc.returncode, checks=checks,
           source_unchanged=source_unchanged,
           receipt_matches_all_sources=receipt_matches_all_sources,
           nonphysical_authority=explicitly_nonphysical,
           last_error=(proc.stderr or proc.stdout)[-MAX_STDOUT:] if not passed else "",
    )
    if passed:
        report["engineering_acceptance"] = True
        report["status"] = "verified_design_only_physical_blocked"
        report["open_actions"] = [
            "Independent human EE review of the exact sourced design and parts.",
            "Fabricate/assemble only after a separate owner approval.",
            "Measure supply, waveforms and host compatibility before claiming physical function.",
        ]
    else:
        report["status"] = "blocked_independent_verification"
        report["open_actions"] = [
            "Investigate the actual native KiCad/pcbnew errors or stale verification receipt.",
        ]
    report["artifacts_sha256"] = _record_artifacts(
        [stage / "spi_flash_adapter_v1.kicad_sch",
         stage / "spi_flash_adapter_v1.kicad_pcb",
         stage / "design_manifest.json",
         stage / "verification.json"], run_dir
    ) if receipt_path.is_file() else {}
    report["tool_versions"] = receipt.get("toolchain") or {}


def _repair(run_dir: Path, intake_path: Path, report: dict[str, Any]) -> None:
    from .project_intake import load_project_intake, plan_project_from_intake
    from .splice_manifest import get_splice_case, load_splice_manifest
    from .splice_manifest import run_splice_case, evaluate_splice_case

    case = get_splice_case(load_splice_manifest(REPO_ROOT / SPLICE_MANIFEST), RC_ID)
    if (REPO_ROOT / case["intake"]).resolve() != intake_path:
        raise ValueError("registered repair input changed in the native splice manifest")
    intake = load_project_intake(intake_path)
    plan = plan_project_from_intake(intake)
    package = plan.get("salvage_package") or {}
    splice = package.get("splice_plan") or {}
    blocks = splice.get("reusable_blocks") or []
    selected = package.get("recommended_build_id")
    expected = case["expected_build_id"]
    donor_report = plan.get("donor_board_vision_report") or {}
    evidence_report = plan.get("evidence_extraction_report") or {}
    repair_context = intake.get("repair_intake_context") or {}
    reasons: list[str] = []
    if not selected or selected == "generic_low_voltage_build":
        reasons.append("No evidenced non-generic build identity was resolved.")
    elif selected != expected:
        reasons.append(f"Proposed build {selected!r} differs from registered repair target {expected!r}.")
    if not blocks:
        reasons.append("No donor functional block was resolved for a physical splice.")
    if not repair_context.get("symptoms"):
        reasons.append("Missing normalized repair symptoms.")
    if int(donor_report.get("applied_board_count") or 0) < 1:
        reasons.append("No approved offline donor board evidence was applied.")
    _trace(report, "intake", "project_intake.load_project_intake", "passed",
           "Normalized real user-provided case symptoms and registered donor source.",
           symptom_count=len(repair_context.get("symptoms") or []),
           source_attestation="registered offline fixture, not a measured real broken unit")
    _trace(report, "planning", "project_intake.plan_project_from_intake + salvage bridge",
           "blocked" if reasons else "passed",
           "No generic placeholder board is accepted as a successful RC repair.",
           expected_build_id=expected,proposed_build_id=selected,
           donor_vision_applied=donor_report.get("applied_board_count",0),
           extracted_evidence_accepted=evidence_report.get("accepted_count",0),
           reusable_blocks=len(blocks),
           blockers=reasons)
    if reasons:
        report["status"] = "blocked_unresolved_donor_architecture"
        report["open_actions"] = reasons + [
            "Obtain pin-level donor identification and measured electrical evidence before compilation.",
            "Do not energize the salvaged board; power topology and protection remain unverified.",
        ]
        # This is the most valuable action: ABORT before fallback catalog
        # compiler manufactures a plausible but irrelevant generic board.
        _trace(report, "execution", "splice_manifest.run_splice_case", "skipped",
               "Unsafe or unsupported to compile a wrong generic donor replacement.")
        return

    # Reuse the canonical existing native compiler only after the preflight.
    build_root=run_dir / "compiled"
    metrics=run_splice_case(case,out_dir=build_root,export_gerber=False)
    evaluation=evaluate_splice_case(metrics,case)
    package_path=build_root / "PROJECT_PACKAGE.json"
    manufacturing: dict[str,Any]={}
    if package_path.is_file():
        manufacturing=json.loads(package_path.read_text()).get("manufacturing_reconciliation") or {}
    bench_path=build_root / "SPLICE_BENCH_SESSION.json"
    bench: dict[str,Any]={}
    if bench_path.is_file():
        bench=json.loads(bench_path.read_text())
    verified=(evaluation.get("passed") is True and metrics.get("drc_pass") is True
              and metrics.get("build_id")==expected and manufacturing.get("package_ready") is True)
    _trace(report, "execution", "splice_manifest.run_splice_case", "passed" if verified else "failed",
           "Native splice compiler and independent case + manufacturing reconciliation.",
           case_evaluation=evaluation,manufacturing=manufacturing,
           bench_open_gates=bench.get("open_gate_count"))
    report["engineering_acceptance"]=verified
    report["status"]="verified_compiled_design_only_physical_blocked" if verified else "blocked_compiled_case_or_manufacturing"
    report["open_actions"]=list(evaluation.get("failures") or [])
    report["open_actions"].extend(
        str(item.get("message") or item) for item in manufacturing.get("blockers",[])
    )
    report["open_actions"].append("Real donor bench measurements and human physical authorization remain pending.")
    if bench.get("power_on_authorized") is not False:
        report["status"]="blocked_unverified_bench_authority"
        report["engineering_acceptance"]=False
        report["open_actions"].append("Bench authority was not explicitly false; refuse any physical claim.")
    report["artifacts_sha256"]=_record_artifacts(
        [p for p in (build_root/"SPLICE_PLAN.json",build_root/"PROJECT_PACKAGE.json",
                      build_root/"SPLICE_BENCH_SESSION.json") if p.is_file()],run_dir)



def _machine_release(report: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse the canonical HS release authority model, never a custom PASS flag."""
    from .machine_project import (
        AuthorityState, EvidenceRef, MachineProject, ReleaseState,
        Requirement, RequirementKind, VerificationMethod,
        VerificationStatus, VerificationType,
    )
    software_passed = report["engineering_acceptance"] is True
    evidence = ([EvidenceRef(
        evidence_id="bounded-software-tool-receipt",
        kind="independent native engineering execution",
        basis="Native KiCad + project verification; no energized physical device",
        ref="HS_OPERATOR_RESULT.json",
        authority=AuthorityState.OBSERVED,
        simulated=False,
        supports=["req-software"],
        metadata={"physical_product_observed":False,
                  "source_sha256":report["source_sha256"]},
    )] if software_passed else [])
    project=MachineProject(
        project_id="hs-work-order-"+report["case_id"].replace("_","-"),
        name="HS one work-order: "+report["case_id"],
        purpose=str(report["objective"]),
        requested_release_state=ReleaseState.OPERATIONALLY_AUTHORIZED,
        requirements=[
            Requirement(requirement_id="req-software",
                statement="Native design artifact satisfies the specific engineering problem",
                kind=RequirementKind.FUNCTIONAL,
                verification_method_ids=["verify-software"]),
            Requirement(requirement_id="req-physical",
                statement="Actual hardware has been independently tested and human authorized",
                kind=RequirementKind.SAFETY,
                verification_method_ids=["verify-physical"]),
        ],
        verifications=[
            VerificationMethod(verification_id="verify-software",
                name="Native software design verification",
                method_type=VerificationType.TEST,
                status=(VerificationStatus.PASSED if software_passed
                        else VerificationStatus.BLOCKED),
                requirement_ids=["req-software"],
                evidence_ids=["bounded-software-tool-receipt"] if software_passed else []),
            VerificationMethod(verification_id="verify-physical",
                name="Independent hardware measurement and authorization",
                method_type=VerificationType.TEST,
                status=VerificationStatus.PLANNED,
                requirement_ids=["req-physical"]),
        ],
        evidence=evidence,
        metadata={"software_only":True,"fabrication_authorized":False,
                  "power_on_authorized":False},
    )
    assessment=project.assess_release()
    if assessment.allowed or not assessment.blockers:
        raise ValueError("canonical MachineProject authority cannot be open")
    return {
        "requested":assessment.requested_state.value,
        "achieved":assessment.achieved_state.value,
        "allowed":assessment.allowed,
        "blockers":[{"code":b.code,"message":b.message} for b in assessment.blockers],
        "verification_states":{
            v.verification_id:v.status.value for v in project.verifications},
        "software_evidence_count":len(evidence),
        "physical_measurements_count":0,
    }


def _handoff(report: Mapping[str,Any]) -> str:
    lines=[
        "# Hardware Splicer — one engineering operator run",
        "",
        f"Case: **{report['case_id']}**",
        f"Engineering status: **{report['status']}**",
        f"Real physical verification: **NO**",
        f"Fabrication / power-on authorization: **NO**",
        "",
        "## Executed native stages",
        "",
    ]
    for stage in report["trace"]:
        lines.append(f"- **{stage['stage']}** — {stage['existing_engine']}: "
                     f"{stage['state']}. {stage['details']}")
    lines.extend(["","## Evidence-bounded next actions",""])
    for row in report["open_actions"]:
        lines.append("- "+str(row))
    lines.extend(["","## What this does not establish","","No real device was built, repaired, powered, sold or bench-validated.",
                  "This report is not a human fabrication authorization.",""])
    return "\n".join(lines)


def list_cases() -> list[dict[str,str]]:
    return [{"case_id":cid,**cfg} for cid,cfg in REGISTERED.items()]


def run_workshop_operator(case_id:str,*,out_dir:str|Path,execute:bool=False,
                          repo_root:Path|None=None)->dict[str,Any]:
    """Select registered native workflow, run one bounded software route, inspect evidence."""
    if case_id not in REGISTERED:
        raise ValueError(f"case not registered: {case_id!r}; allowed: {sorted(REGISTERED)}")
    root=(repo_root or REPO_ROOT).resolve()
    source=_source_path(root,REGISTERED[case_id]["source"])
    # Source identity is defined by source state, not a self-reported model answer.
    if source.is_dir():
        items=[p for p in sorted(source.rglob("*")) if p.is_file()
               and not p.is_symlink() and "out" not in p.relative_to(source).parts
               and "__pycache__" not in p.parts]
        source_hash=hashlib.sha256(json.dumps(
             {p.relative_to(source).as_posix():_hash(p) for p in items},
             sort_keys=True).encode()).hexdigest()
    else:
        source_hash=_hash(source)
    report=_base(case_id,source_hash,execute=execute)
    output=Path(out_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("operator output must be new/empty; stale artifacts cannot be reused")
    output.mkdir(parents=True,exist_ok=True)
    if not execute:
        _trace(report,"selection","registered HS capability routing","planned",
               "Dry-run only; no engineering tool executed.")
        report["open_actions"]=["Run with --execute for bounded software-only engineering checks."]
    elif case_id==SPI_ID:
        _native_spi(output,source,report)
    elif case_id==RC_ID:
        _repair(output,source,report)
    else:
        raise AssertionError("unregistered adapter")
    # Final authority is bounded irrespective of internal model/case output.
    assert not report["physical_validation"]
    assert not report["fabrication_authorized"]
    assert not report["power_on_authorized"]
    assert not report["real_repair_confirmed"]
    report["canonical_machine_release"] = _machine_release(report)
    (output/"HS_OPERATOR_RESULT.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n")
    (output/"ENGINEERING_HANDOFF.md").write_text(_handoff(report))
    return report
