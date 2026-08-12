#!/usr/bin/env python3
"""Evaluate a robot-arm proposal produced by an external live LLM.

This runner keeps model output separate from deterministic engineering judgment. It does
not call a provider itself: the proposal file is the external model artifact, while HS
parses the typed contract, validates visible identities/evidence, computes bounded checks,
and preserves closed physical authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.robot_arm_design import (
    evaluate_robot_arm_design,
    parse_robot_arm_design,
)
from hardware_splicer.robot_arm_experiment import (
    robot_arm_inventory,
    robot_arm_requirements,
    robot_arm_source_ids,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--out-dir", default="artifacts/robot-arm-live")
    args = parser.parse_args()

    proposal_path = Path(args.proposal)
    raw = json.loads(proposal_path.read_text(encoding="utf-8"))
    requirements = robot_arm_requirements()
    inventory = robot_arm_inventory()
    source_ids = robot_arm_source_ids()

    proposal = parse_robot_arm_design(
        raw,
        inventory=inventory,
        known_source_ids=source_ids,
    )
    evaluation = evaluate_robot_arm_design(
        proposal,
        requirements=requirements,
        inventory=inventory,
    )
    rendered = evaluation.model_dump(mode="json")
    findings = list(rendered.get("findings") or [])
    reach = [row for row in findings if row.get("code") == "GEOMETRIC_REACH_UPPER_BOUND"]
    torque = [row for row in findings if row.get("code") == "PAYLOAD_ONLY_TORQUE_BOUND"]

    checks = {
        "typed_contract_accepted": True,
        "geometric_reach_upper_bound_passes": bool(reach and reach[0].get("status") == "pass"),
        "all_visible_actuator_payload_bounds_pass": bool(torque and all(row.get("status") == "pass" for row in torque)),
        "no_hard_engineering_failure": int(rendered.get("summary", {}).get("hard_failure_count") or 0) == 0,
        "motion_authority_remains_closed": rendered.get("motion_authorized") is False,
        "power_authority_remains_closed": rendered.get("power_on_authorized") is False,
        "fabrication_authority_remains_closed": rendered.get("fabrication_authorized") is False,
        "release_authority_remains_closed": rendered.get("release_authorized") is False,
        "full_kinematics_not_falsely_claimed": rendered.get("summary", {}).get("full_kinematics_verified") is False,
        "full_dynamics_not_falsely_claimed": rendered.get("summary", {}).get("full_dynamics_verified") is False,
    }
    diagnostic_pass = all(checks.values())

    report = {
        "schema_version": "hardware_splicer.external_robot_arm_llm_run.v1",
        "provenance": {
            "model": "GPT-5.6 Sol",
            "generation_mode": "external_assistant_generated",
            "cleanroom_grade": "integration_only_not_source_blind",
            "proposal_file": str(proposal_path),
            "engineering_authority": "none",
        },
        "requirements": requirements,
        "visible_inventory": inventory,
        "visible_source_ids": source_ids,
        "proposal": proposal.model_dump(mode="json"),
        "evaluation": rendered,
        "checks": checks,
        "diagnostic_pass": diagnostic_pass,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "EXTERNAL_LLM_ROBOT_ARM_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    reach_outputs = reach[0].get("outputs", {}) if reach else {}
    lines = [
        "experiment=external_live_llm_robot_arm",
        "model=GPT-5.6 Sol",
        "cleanroom_grade=integration_only_not_source_blind",
        f"diagnostic_pass={diagnostic_pass}",
        f"evaluation_status={rendered.get('status')}",
        f"joint_count={rendered.get('summary', {}).get('joint_count')}",
        f"proposed_chain_length_mm={rendered.get('summary', {}).get('proposed_chain_length_mm')}",
        f"reach_margin_mm={reach_outputs.get('reach_margin_mm')}",
        f"payload_torque_checks={len(torque)}",
        f"payload_torque_checks_passed={sum(row.get('status') == 'pass' for row in torque)}",
        f"motion_authorized={rendered.get('motion_authorized')}",
        f"hard_failure_count={rendered.get('summary', {}).get('hard_failure_count')}",
        f"blocking_count={rendered.get('summary', {}).get('blocking_count')}",
    ]
    for row in torque:
        outputs = dict(row.get("outputs") or {})
        lines.append(
            "torque="
            + str(row.get("joint_id"))
            + f":required={outputs.get('payload_only_required_torque_nm')}"
            + f":margin={outputs.get('payload_only_torque_margin_nm')}"
        )
    (out_dir / "EXTERNAL_LLM_ROBOT_ARM_SUMMARY.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print((out_dir / "EXTERNAL_LLM_ROBOT_ARM_SUMMARY.txt").read_text(encoding="utf-8"), end="")
    return 0 if diagnostic_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
