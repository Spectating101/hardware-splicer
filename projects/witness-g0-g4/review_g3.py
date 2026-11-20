#!/usr/bin/env python3
"""Read-only structural check of the *unchanged* HS→PLRS-6 synthetic witness replay.

Never turns a fixture PASS into physical truth or financial/issuance authority.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

from assessment import Hold


def _load(path):
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Hold(f"source file unavailable or invalid: {path}") from exc
    if not isinstance(record, dict):
        raise Hold("source record must be a JSON object")
    return record


def review(original, intake, screen, session, *, expected_evidence_root=None):
    if original.get("schema") != "hardware_splicer.5v_witness_design_replay.v1":
        raise Hold("unexpected HS native verification schema")
    if original.get("status") != "SOFTWARE_DESIGN_VALIDATED_ONLY" or original.get("native_erc") != "ZERO_VIOLATIONS" or original.get("native_drc") != "ZERO_VIOLATIONS_ZERO_UNCONNECTED_ZERO_PARITY_ERRORS":
        raise Hold("native software design replay not consistently validated")
    if original.get("pl_intake_decision") != "TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS":
        raise Hold("native replay promoted Policy Lab fixture")
    for flag in ("fabrication_released", "hardware_powered", "calibration_verified", "physical_equipment_built"):
        if original.get(flag) is not False:
            raise Hold(f"HS replay cannot authorize physical activity: {flag}")
    if intake.get("schema") != "policylab.plrs6_offline_intake_receipt.v1" or intake.get("decision") != original["pl_intake_decision"] or intake.get("capture_kind") != "TEST_FIXTURE":
        raise Hold("intake schema, status, or evidence class does not agree with original source")
    for flag in ("physical_ready", "grid_export_eligible", "spk_issuance_allowed",
                 "calibration_documents_content_verified", "independent_device_custody_verified",
                 "physical_channel_identity_verified", "circuit_safety_review_verified",
                 "timebase_verified_against_external_clock"):
        if intake.get(flag) is not False:
            raise Hold(f"Policy Lab intake falsely claims external assurance: {flag}")
    # Canonical PLRS-6 records *counts* of verified hashes, not boolean flags.
    # Do not coerce bool to int, since True must not impersonate a verified file count.
    normalized_count = intake.get("normalized_capture_hashes_verified")
    supporting_count = intake.get("supporting_file_hashes_verified")
    if (type(normalized_count) is not int or normalized_count < 2 or
            type(supporting_count) is not int or supporting_count < 1):
        raise Hold("original intake lacks verified normalized-capture/supporting-file hash counts")
    evidence_root = intake.get("evidence_root_sha256")
    if not isinstance(evidence_root, str) or not len(evidence_root) == 64:
        raise Hold("intake evidence root missing")
    if original.get("pl_intake_evidence_root") != evidence_root:
        raise Hold("HS vs Policy Lab evidence root disagreement")
    if expected_evidence_root is not None and evidence_root != expected_evidence_root:
        raise Hold("evidence root disagrees with independently pinned value")
    if screen.get("schema") != "hardware_splicer.witness_fixture_discrimination.v1" or screen.get("decision") != "PASS_FIXTURE_DISCRIMINATION_ONLY":
        raise Hold("strict G2 fixture screen did not pass")
    for flag in ("physical_ready", "metrological_agreement_proven", "fabrication_allowed",
                 "reference_independence_verified", "reference_calibration_verified",
                 "external_timebase_verified"):
        if screen.get(flag) is not False:
            raise Hold(f"fixture discrimination promoted physical truth: {flag}")
    if screen.get("fixture_only") is not True or screen.get("primary_receipt_verified") is not True:
        raise Hold("unverified primary source or unsupported fixture status")
    if session.get("capture_kind") != "TEST_FIXTURE" or session.get("source_kind") != "register_fixture" or session.get("status") != "COMPLETE":
        raise Hold("primary capture does not remain complete synthetic register fixture")
    samples = session.get("completed_samples")
    if type(samples) is not int or samples != screen.get("samples_paired") or samples != original.get("primary_samples_fixture"):
        raise Hold("HS/PL capture counts differ")
    return {"schema": "hs.policy_lab_fixture_replay_check.v1",
            "software_structural_replay": "PASS",
            "evidence_root": evidence_root,
            "samples": samples,
            "source_authenticity": "NOT_ESTABLISHED",
            "metrological_agreement": "NOT_ESTABLISHED",
            "physical_operation_authorized": False,
            "token_issuance_authorized": False,
            "financial_performance": "NOT_ASSESSED"}


def verify_full_source_replay(bundle, screen_path, pl_root, *, expected_evidence_root=None):
    """Recompute G2 from raw source and PLRS-6 from original captures.

    No network, instrument connection, or hardware control. The external source
    pin should be supplied separately; comparing self-published receipts alone
    cannot authenticate a sensor or human operator.
    """
    base = Path(bundle).resolve()
    pl = Path(pl_root).resolve()
    decoder_path = (Path(__file__).resolve().parents[2] / "hardware" / "reference_designs" /
                    "low_voltage_witness_fixture_v0" / "measurement_screen.py")
    if not decoder_path.is_file():
        raise Hold("HS witness screen not present at pinned repository path")
    spec = importlib.util.spec_from_file_location("_witness_g2_source_replay", decoder_path)
    if spec is None or spec.loader is None:
        raise Hold("cannot load G2 screen")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        recomputed_screen = module.screen(
            base/"primary"/"samples.csv", base/"reference-fixture.csv",
            base/"primary"/"session.json", base/"primary"/"registers.jsonl")
    except (module.ScreeningError, OSError) as exc:
        raise Hold(f"original G2 capture rejected: {exc}") from exc
    frozen_screen = _load(screen_path)
    if recomputed_screen != frozen_screen:
        raise Hold("G2 screening receipt does not reproduce from original capture bytes")

    converter = pl/"scripts"/"equipment"/"dc_bench_capture.mjs"
    if not converter.is_file() or not (base/"capture-config.json").is_file():
        raise Hold("Policy Lab PLRS-6 converter or original manifest missing")
    with tempfile.TemporaryDirectory(prefix="plrs6-independent-review-") as d:
        dest=Path(d)/"intake"
        command=["node",str(converter),"--primary",str(base/"primary"/"samples.csv"),
                 "--reference",str(base/"reference-fixture.csv"),
                 "--primary-sidecar",str(base/"primary"/"session.json"),
                 "--primary-registers",str(base/"primary"/"registers.jsonl"),
                 "--config",str(base/"capture-config.json"),"--out",str(dest)]
        process=subprocess.run(command,cwd=pl,capture_output=True,text=True,timeout=180)
        if process.returncode:
            raise Hold(f"PLRS-6 independent replay failed (exit {process.returncode}): {process.stderr[-300:]}")
        independent_receipt = _load(dest/"intake-receipt.json")
        frozen_receipt = _load(base/"policy-lab-intake"/"intake-receipt.json")
        if independent_receipt != frozen_receipt:
            raise Hold("original PLRS-6 intake receipt differs from independent raw-byte replay")
        decision=review(_load(base/"verification.json"),independent_receipt,
                        recomputed_screen,_load(base/"primary"/"session.json"),
                        expected_evidence_root=expected_evidence_root)
    decision["raw_capture_to_screen_recomputed"] = "PASS"
    decision["plrs6_source_capture_recomputed"] = "PASS"
    decision["independent_physical_provenance"] = "NOT_ESTABLISHED"
    return decision


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native-replay",required=True,type=Path)
    p.add_argument("--screen",required=True,type=Path)
    p.add_argument("--pl-root",type=Path,
                   help="Run the source-bound PLRS-6 intake again in an isolated temporary directory")
    p.add_argument("--expect-evidence-root",help="Optional separately trusted 64-hex evidence root")
    args=p.parse_args()
    base=args.native_replay
    if args.pl_root:
        result=verify_full_source_replay(base,args.screen,args.pl_root,
                                         expected_evidence_root=args.expect_evidence_root)
    else:
        result=review(_load(base/"verification.json"), _load(base/"policy-lab-intake"/"intake-receipt.json"),
                      _load(args.screen), _load(base/"primary"/"session.json"),
                      expected_evidence_root=args.expect_evidence_root)
        result["raw_capture_to_screen_recomputed"] = "NOT_PERFORMED"
        result["plrs6_source_capture_recomputed"] = "NOT_PERFORMED"
    print(json.dumps(result, indent=2))


if __name__=="__main__":
    main()
