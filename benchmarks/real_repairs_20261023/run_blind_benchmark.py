"""Run existing HS repair-intake baseline and sealed blind path-repair challenge.

The gold file is deliberately opened ONLY after all inferences complete.
No LLM or simulated physical repair is used. This is a four-case *development*
benchmark, not a held-out evaluation of a mature diagnostic model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from hardware_splicer.repair_intake import repair_intake_report, extract_repair_context, apply_repair_intake_context
from hardware_splicer.repair_path_diagnostics import rank_repair_hypotheses


def run(root: Path) -> dict:
    # Baseline only captures symptoms; it does not diagnose physical root causes.
    cases = json.loads((root / "blind_cases.json").read_text(encoding="utf-8"))["cases"]
    baseline = {}
    predictions = {}
    for case in cases:
        identifier = case["case_id"]
        intake = extract_repair_context(case)
        baseline[identifier] = {
            "symptoms_extracted": len(intake["symptoms"]),
            "physical_root_cause_rankings": 0,
            "physical_repair_diagnosis_present": False,
        }
        # Exercise the actual HS repair-intake API, not only an isolated helper.
        enriched = apply_repair_intake_context(case)
        inspection = repair_intake_report(case)
        assert enriched["repair_path_diagnostic"] == inspection["repair_path_diagnostic"]
        assert enriched["repair_path_diagnostic"] == rank_repair_hypotheses(case)
        predictions[identifier] = enriched["repair_path_diagnostic"]
    # No inference can read the reference outcome above this line.
    gold = json.loads((root / "sealed_evaluation.json").read_text(encoding="utf-8"))
    scored = {}
    for reference in gold["cases"]:
        identifier = reference["case_id"]
        outcome = predictions[identifier]
        top = (outcome.get("candidates") or [{}])[0].get("component_id")
        expected = reference.get("expected_first_component")
        matches = (top == expected) if expected else (
            outcome["verdict"] == reference.get("expected_verdict")
        )
        scored[identifier] = {
            "reference_strength": reference["gold_strength"],
            "top_candidate": top,
            "expected_candidate": expected,
            "verdict": outcome["verdict"],
            "matches_reference_class": matches,
            "credit": (
                "one_reference_confirmed_repair_prediction"
                if reference["gold_strength"] == "poster_confirmed_component_replacement_success" and matches
                else "expert_opinion_alignment_not_repair_proof"
                if reference["gold_strength"] == "expert_hypothesis_not_confirmed" and matches
                else "synthetic_sanity_check"
                if reference["gold_strength"] == "synthetic_negative_control" and matches
                else "appropriate_abstention_on_underdetermined_case"
                if reference["gold_strength"] == "real_generic_symptom_underdetermined" and matches
                else "mismatch"
            ),
        }
    output = {
        "schema_version": "hardware_splicer.blind_repair_result.v1",
        "input_case_count": len(cases),
        "real_source_cases": 3,
        "synthetic_control_cases": 1,
        "inference_provider": "HS bounded deterministic shared-path ranker",
        "baseline_repair_intake": baseline,
        "proposed_diagnostics": predictions,
        "evaluation": scored,
        "reference_confirmed_positive_matches": sum(
            int(x["matches_reference_class"])
            for x in scored.values()
            if x["reference_strength"] == "poster_confirmed_component_replacement_success"
        ),
        "no_physical_work_performed": True,
        "no_llm_inference_performed": True,
        "claims_not_tested": [
            "Unknown-device diagnosis generalization",
            "Physical repair execution",
            "Reduction in diagnosis labor/time",
            "Superiority over a competing diagnostic system",
        ],
    }
    return output


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    result = run(root)
    payload = json.dumps(result, indent=2) + "\n"
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "output": str(dest),
        "confirmed_positive_matches": result["reference_confirmed_positive_matches"],
        "scores": result["evaluation"],
        "physical_work_performed": False,
    }, indent=2))
