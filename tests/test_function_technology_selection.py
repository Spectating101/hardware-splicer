"""Technology selection is a transparent, fail-closed *design study*."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.function_intent_bridge import package_intent
from hardware_splicer.function_technology_selection import (
    compare, compile_option_study, read_bound_function_package,
)

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "examples/functionality/water_filter_nonpotable_bench_001.json"
OPTIONS = ROOT / "examples/functionality/water_filter_technology_options_001.json"


def source():
    return json.loads(BRIEF.read_text()), json.loads(OPTIONS.read_text())


def prepared(tmp_path):
    brief, options = source()
    pkg = tmp_path / "functional"
    package_intent(brief, pkg)
    return pkg, options


def test_full_comparison_rejects_inadequate_methods_and_prefers_lowest_added_complexity(tmp_path):
    pkg, options = prepared(tmp_path)
    brief, model, gate, works = read_bound_function_package(pkg)
    report, handoff = compare(brief, options, works)
    assert report["source_spec_sha256"] == gate["source_spec_sha256"]
    assert report["selection_state"] == "PROVISIONAL_FOR_DESIGN_STUDY_ONLY"
    assert report["provisional_preferred_candidate_id"] == "passive_replaceable_depth_media"
    assert report["candidate_ids_eligible_for_design_study"] == [
        "passive_replaceable_depth_media", "active_membrane_cartridge"
    ]
    rejected = {row["candidate_id"]: row for row in report["candidate_screening"]
                if row["screening_state"] == "REJECT_INCOMPLETE_FUNCTIONAL_COVERAGE"}
    assert set(rejected) == {"coarse_strainer_only", "carbon_adsorption_only"}
    assert all(row["mandatory_requirements_missing"] == ["REQ_PARTICLE"]
               and row["declared_conflicts"] for row in rejected.values())
    assert all(row["qualifies_as_functioning_device"] is False
               for row in report["candidate_screening"])
    assert not report["water_quality_measured"]
    assert not report["human_consumption_authorized"]
    assert not report["physical_build_authorized"]
    assert len(handoff["discipline_assignments"]) == 5
    assert all(row["source_spec_sha256"] == gate["source_spec_sha256"]
               if "source_spec_sha256" in row else True
               for row in handoff["discipline_assignments"])
    assert any(row["engineering_specialty"] == "separation process and materials"
               and "Replaceable rated depth-media cartridge" in
               row["proposed_process_implementation"]
               for row in handoff["discipline_assignments"])
    assert all(row["verification_status"] == "not_executed"
               and not row["native_design_outputs_generated"]
               and row["planned_tests"]
               for row in handoff["discipline_assignments"])


def test_complete_technology_package_matches_source_receipts_and_refuses_overwrite(tmp_path):
    pkg, _ = prepared(tmp_path)
    out = tmp_path / "studies"
    receipt = compile_option_study(pkg, OPTIONS, out)
    decision = json.loads((out / "TECHNOLOGY_DECISION.json").read_text())
    handoff = json.loads((out / "PROVISIONAL_ARCHITECTURE_HANDOFF.json").read_text())
    assert receipt["source_spec_sha256"] == decision["source_spec_sha256"]
    assert receipt["technology_options_sha256"] == decision["technology_options_sha256"]
    assert handoff["source_spec_sha256"] == receipt["source_spec_sha256"]
    assert handoff["technology_options_sha256"] == receipt["technology_options_sha256"]
    assert not receipt["physical_authority_granted"]
    for name, details in receipt["files"].items():
        payload = (out / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == details["sha256"]
        assert len(payload) == details["bytes"]
    with pytest.raises(ValueError, match="overwrite"):
        compile_option_study(pkg, OPTIONS, out)


def test_incorrect_device_id_fails_before_option_screening(tmp_path):
    pkg, opts = prepared(tmp_path)
    brief, _, _, works = read_bound_function_package(pkg)
    opts["project_id"] = "unrelated_device"
    with pytest.raises(ValueError, match="different device"):
        compare(brief, opts, works)


def test_all_unqualified_approaches_produce_no_selection(tmp_path):
    pkg, opts = prepared(tmp_path)
    brief, _, _, works = read_bound_function_package(pkg)
    opts["options"] = opts["options"][2:]
    result, handoff = compare(brief, opts, works)
    assert result["selection_state"] == "NO_CANDIDATE_COVERS_REQUIRED_FUNCTIONS"
    assert result["provisional_preferred_candidate_id"] is None
    assert handoff["preferred_study_candidate_id"] is None
    assert handoff["discipline_assignments"] == []
    assert not handoff["physical_authority_granted"]


def test_cannot_hide_missing_required_function_without_rejection_reason(tmp_path):
    pkg, opts = prepared(tmp_path)
    brief, _, _, works = read_bound_function_package(pkg)
    opts["options"][0]["requirement_coverage"] = [
        r for r in opts["options"][0]["requirement_coverage"]
        if r["requirement_id"] != "REQ_PARTICLE"
    ]
    with pytest.raises(ValueError, match="explicit rejection reason"):
        compare(brief, opts, works)


def test_cannot_claim_verified_removal_or_measured_inputs(tmp_path):
    pkg, opts = prepared(tmp_path)
    brief, _, _, works = read_bound_function_package(pkg)
    opts["options"][0]["validated_treatment_performance"] = True
    with pytest.raises(ValueError, match="false health or measured-treatment"):
        compare(brief, opts, works)
    opts = source()[1]
    opts["options"][0]["assumptions"][0]["evidence_status"] = "measured"
    with pytest.raises(ValueError, match="misrepresented as verified"):
        compare(brief, opts, works)
    opts = source()[1]
    opts["options"][0]["requirement_coverage"][0]["evidence_status"] = "passed"
    with pytest.raises(ValueError, match="unsupported functional performance"):
        compare(brief, opts, works)


def test_fabrication_claim_and_redefined_existing_subsystem_rejected(tmp_path):
    pkg, opts = prepared(tmp_path)
    brief, _, _, works = read_bound_function_package(pkg)
    opts["options"][0]["manufacturing_authorized"] = True
    with pytest.raises(ValueError, match="physical authority"):
        compare(brief, opts, works)
    opts = source()[1]
    opts["options"][1]["additional_systems"][0]["id"] = "SUB_MEDIA"
    with pytest.raises(ValueError, match="redefines an upstream subsystem"):
        compare(brief, opts, works)


def test_source_package_mutation_is_rejected_even_with_updated_file_hash(tmp_path):
    pkg, opts = prepared(tmp_path)
    original = json.loads((pkg / "FUNCTIONAL_INPUT.json").read_text())
    original["requirements"][1]["statement"] = "Changed requirement with no consistent model"
    new = json.dumps(original, indent=2, sort_keys=True) + "\n"
    (pkg / "FUNCTIONAL_INPUT.json").write_text(new)
    receipt = json.loads((pkg / "PACKAGE_RECEIPT.json").read_text())
    receipt["files"]["FUNCTIONAL_INPUT.json"] = {
        "sha256": hashlib.sha256(new.encode()).hexdigest(), "bytes": len(new.encode())
    }
    (pkg / "PACKAGE_RECEIPT.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="not reproducible"):
        read_bound_function_package(pkg)


def test_functionality_mutation_changes_preferred_architecture_source_digest(tmp_path):
    brief, options = source()
    pkg1 = tmp_path / "base"
    package_intent(brief, pkg1)
    d1, _ = compare(*_brief_options_packages(pkg1, options))
    modified = copy.deepcopy(brief)
    modified["requirements"][1]["target"]["minimum_turbidity_reduction_percent"] = 75
    pkg2 = tmp_path / "changed"
    package_intent(modified, pkg2)
    d2, _ = compare(*_brief_options_packages(pkg2, options))
    assert d1["source_spec_sha256"] != d2["source_spec_sha256"]
    assert d1["technology_options_sha256"] == d2["technology_options_sha256"]
    assert d2["selection_state"] == "PROVISIONAL_FOR_DESIGN_STUDY_ONLY"


def _brief_options_packages(package_root, options):
    brief, _, _, work = read_bound_function_package(package_root)
    return brief, options, work


def test_selection_favors_existing_path_only_as_explicit_heuristic_not_proven_quality(tmp_path):
    pkg, options = prepared(tmp_path)
    brief, _, _, work = read_bound_function_package(pkg)
    # If removed, a more complex still-functionally-covered alternative
    # becomes a provisional study; nothing gains measured performance authority.
    options["options"] = options["options"][1:]
    decision, handoff = compare(brief, options, work)
    assert decision["provisional_preferred_candidate_id"] == "active_membrane_cartridge"
    assert not decision["demonstrated_contaminant_reduction"]
    assert not handoff["process_design_verified"]
    assert not handoff["physical_authority_granted"]
