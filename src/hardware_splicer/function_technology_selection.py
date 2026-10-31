"""Requirement-grounded screening of technology candidates for a function-first HS project.

This is a transparent candidate-study selector, NOT validated process modeling.
It compares proposed ways to satisfy each function with full planned test
traceability, rejects declared incompatibilities, and emits discipline handoffs.
All physical performance, market/supplier, and authorization gates stay CLOSED.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .function_intent_bridge import canonical, parse_intent, discipline_work_packages

SCHEMA = "hardware_splicer.function_technology_options.v1"
DECISION_SCHEMA = "hardware_splicer.technology_study_decision.v1"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError("Technology screening refused: " + message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique(rows: list[dict], key: str) -> set[str]:
    values = [row.get(key) for row in rows]
    require(all(isinstance(x, str) and bool(x.strip()) for x in values),
            "missing or blank " + key)
    require(len(values) == len(set(values)), "duplicate " + key)
    return set(values)


def read_bound_function_package(root: Path) -> tuple[dict, dict, dict, dict]:
    root = Path(root)
    receipt = json.loads((root / "PACKAGE_RECEIPT.json").read_text())
    require(receipt.get("schema_version") == "hardware_splicer.function_intent_receipt.v1",
            "source package receipt version changed")
    expected = {"FUNCTIONAL_INPUT.json", "FUNCTIONAL_GATE.json",
                "MACHINE_PROJECT.json", "DISCIPLINE_WORK_PACKAGES.json"}
    require(set(receipt.get("files", {})) == expected,
            "functionality source package incomplete")
    for name, recorded in receipt["files"].items():
        content = (root / name).read_bytes()
        require(sha(content) == recorded.get("sha256") and
                len(content) == recorded.get("bytes"),
                "source artifact changed: " + name)
    brief = json.loads((root / "FUNCTIONAL_INPUT.json").read_text())
    machine, gate = parse_intent(brief)
    expected_project = canonical(machine.model_dump(mode="json"))
    actual_project = (root / "MACHINE_PROJECT.json").read_bytes()
    require(expected_project == actual_project,
            "MachineProject not reproducible from functional source")
    require(canonical(gate) == (root / "FUNCTIONAL_GATE.json").read_bytes(),
            "functional gate not reproducible")
    packages = discipline_work_packages(machine)
    require(canonical(packages) == (root / "DISCIPLINE_WORK_PACKAGES.json").read_bytes(),
            "discipline handoffs not reproducible")
    require(gate["source_spec_sha256"] == receipt.get("source_spec_sha256"),
            "functional source digest mismatch")
    require(gate["status"] == "FUNCTIONAL_CONCEPT_ONLY" and
            not any(gate["physical_authority"].values()),
            "upstream function contract asserts physical authorization")
    require(all(row.status.value == "planned" and not row.evidence_ids
                for row in machine.verifications),
            "upstream interface claims measured/passed verification")
    return brief, machine.model_dump(mode="json"), gate, packages


def compare(brief: Mapping[str, Any], options: Mapping[str, Any],
            work_packages: Mapping[str, Any]) -> tuple[dict, dict]:
    require(options.get("schema_version") == SCHEMA,
            "unrecognized technology catalog version")
    require(options.get("project_id") == brief.get("project_id") ==
            work_packages.get("project_id"), "candidate catalog for a different device")
    source_sha = sha(canonical(brief))
    require(source_sha == work_packages.get("source_spec_sha256"),
            "functional requirements and work packages have different source revisions")
    require(options.get("catalog_status") == "DESIGN_HYPOTHESES_NOT_VENDOR_RATED",
            "candidate data misleadingly marked vendor-qualified")
    policy = options.get("selection_policy", {})
    require(policy.get("outcome_authority") == "PROVISIONAL_STUDY_ONLY",
            "selection authority exceeds design study")
    require(policy.get("tie_break") ==
            "fewest_added_active_or_complex_subsystems_then_fewest_unresolved_assumptions_then_id",
            "unknown or hidden selection ranking policy")
    requirements = {row["id"]: row for row in brief["requirements"]}
    must = {id_ for id_, row in requirements.items()
            if row.get("priority") == "must"}
    base_ids = {row["subsystem_id"] for row in work_packages["packages"]}
    cases = options.get("options")
    require(isinstance(cases, list) and bool(cases) and all(isinstance(c, dict) for c in cases),
            "no candidate technology approaches")
    unique(cases, "id")
    results = []
    for candidate in cases:
        cid = candidate["id"]
        mechanism = candidate.get("mechanism", {})
        require(isinstance(mechanism, dict) and bool(mechanism.get("physical_principle"))
                and mechanism.get("substantiation") == "process_hypothesis_only",
                "candidate mechanism must be stated as an unverified hypothesis: " + cid)
        require(candidate.get("new_health_or_potable_claim") is False
                and candidate.get("validated_treatment_performance") is False,
                "false health or measured-treatment claim from " + cid)
        require(candidate.get("physical_authority_granted") is not True
                and candidate.get("manufacturing_authorized") is not True,
                "candidate asserts physical authority: " + cid)
        coverage = candidate.get("requirement_coverage")
        conflicts = candidate.get("declared_incompatibilities")
        assumptions = candidate.get("assumptions")
        additions = candidate.get("additional_systems")
        design = candidate.get("assembly_concept")
        require(all(isinstance(v, list) and all(isinstance(r, dict) for r in v)
                    for v in (coverage, conflicts, assumptions, additions))
                and isinstance(design, dict),
                "malformed candidate requirement, conflict or engineering declarations")
        covered = unique(coverage, "requirement_id")
        require(covered <= requirements.keys(),
                "candidate maps unknown functional requirement: " + cid)
        for binding in coverage:
            require(isinstance(binding.get("proposed_solution"), str)
                    and binding["proposed_solution"].strip()
                    and binding.get("evidence_status") == "unverified_hypothesis",
                    "unsupported functional performance assertion: " + cid)
        exclude = unique(conflicts, "requirement_id")
        require(exclude <= requirements.keys() and not (covered & exclude),
                "declared incompatibilities contradict functional coverage: " + cid)
        require(all(isinstance(row.get("reason"), str) and row["reason"].strip()
                    for row in conflicts), "exclusion lacks an engineering reason")
        missing = sorted(must - covered)
        require(set(missing) == exclude & must, 
                "all uncovered mandatory requirements need an explicit rejection reason: " + cid)
        ids = unique(assumptions, "id")
        require(bool(ids), "candidate must declare open physical parameter assumptions")
        for assumption in assumptions:
            require(isinstance(assumption.get("parameter"), str) and
                    bool(assumption["parameter"].strip()) and
                    isinstance(assumption.get("validation"), str) and
                    bool(assumption["validation"].strip()) and
                    assumption.get("evidence_status") == "not_collected",
                    "assumed input misrepresented as verified: " + cid)
        extra = unique(additions, "id")
        require(not (extra & base_ids), "candidate redefines an upstream subsystem")
        for addition in additions:
            require(addition.get("domain") in {
                    "mechanical","electrical","firmware","software","system","sourcing",
                    "assembly","verification"} and
                    isinstance(addition.get("purpose"), str) and addition["purpose"].strip(),
                    "additional subsystem has no engineering rationale")
        require(set(design) <= base_ids and
                all(isinstance(value, str) and value.strip() for value in design.values()),
                "candidate assembly concepts must reference real HS subsystems")
        eligible = not missing
        results.append({
            "candidate_id":cid,
            "name":candidate.get("name", cid),
            "mechanism_category":mechanism.get("category"),
            "physical_principle_hypothesis":mechanism["physical_principle"],
            "screening_state":"ELIGIBLE_FOR_STUDY_ONLY" if eligible else
                              "REJECT_INCOMPLETE_FUNCTIONAL_COVERAGE",
            "proposed_requirement_coverage":len(covered),
            "mandatory_requirements_missing":missing,
            "declared_conflicts":[dict(row) for row in conflicts],
            "extra_subsystems_count":len(extra),
            "unverified_parameters_count":len(assumptions),
            "unverified_parameter_ids":sorted(ids),
            "all_proposed_performance_unmeasured":True,
            "qualifies_as_functioning_device":False,
            "native_artifacts_generated":False,
            "vendor_component_selected":False,
            "declared_quality_or_drinking_water_performance":False,
        })
    eligible = [row for row in results if row["screening_state"] == "ELIGIBLE_FOR_STUDY_ONLY"]
    eligible.sort(key=lambda row: (row["extra_subsystems_count"],
                                   row["unverified_parameters_count"],
                                   row["candidate_id"]))
    chosen_id = eligible[0]["candidate_id"] if eligible else None
    proposed = next((row for row in cases if row["id"] == chosen_id), None)
    delegated = []
    if proposed is not None:
        for pack in work_packages["packages"]:
            assignment = dict(pack)
            assignment["preferred_study_candidate_id"] = chosen_id
            assignment["proposed_process_implementation"] = proposed["assembly_concept"].get(
                pack["subsystem_id"], "Concept not yet defined — engineering review needed")
            assignment["additional_candidate_subsystems"] = [
                dict(row) for row in proposed["additional_systems"]]
            assignment["unverified_candidate_assumptions"] = [
                dict(row) for row in proposed["assumptions"]]
            assignment["native_design_outputs_generated"] = False
            assignment["verification_status"] = "not_executed"
            delegated.append(assignment)
    decision = {
        "schema_version":DECISION_SCHEMA,
        "source_spec_sha256":source_sha,
        "technology_options_sha256":sha(canonical(options)),
        "project_id":brief["project_id"],
        "selection_basis":"explicit_requirement_coverage_then_incremental_subsystems_and_unverified_inputs",
        "not_a_verified_technical_superiority_or_cost_comparison":True,
        "candidate_screening":results,
        "candidate_ids_eligible_for_design_study":[r["candidate_id"] for r in eligible],
        "provisional_preferred_candidate_id":chosen_id,
        "selection_state":"PROVISIONAL_FOR_DESIGN_STUDY_ONLY" if chosen_id else
                          "NO_CANDIDATE_COVERS_REQUIRED_FUNCTIONS",
        "demonstrated_contaminant_reduction":False,
        "material_and_pressure_ratings_verified":False,
        "vendor_parts_qualified":False,
        "process_model_executed":False,
        "water_quality_measured":False,
        "human_consumption_authorized":False,
        "physical_build_authorized":False,
        "critical_next_evidence":[
            "Define and independently characterize incoming particle challenge",
            "Measure available pressure, flow, and hydraulic loss with selected real media",
            "Verify contamination/removal against paired physical water samples",
            "Choose exact rated wet-path components, seals and qualified materials",
            "Review housing design, bypass paths, servicing, and instrumentation",
            "Require independent domain review before any actual system construction or use",
        ],
    }
    handoff = {
        "schema_version":"hardware_splicer.technology_study_handoff.v1",
        "source_spec_sha256":source_sha,
        "technology_options_sha256":decision["technology_options_sha256"],
        "preferred_study_candidate_id":chosen_id,
        "discipline_assignments":delegated,
        "engineering_authority":"concept_study_only",
        "supplier_purchasing_authorized":False,
        "process_design_verified":False,
        "native_toolchain_executed":False,
        "physical_authority_granted":False,
    }
    return decision, handoff


def compile_option_study(function_root: Path, option_path: Path, out: Path) -> dict:
    brief, machine, gate, packages = read_bound_function_package(function_root)
    raw = Path(option_path).read_bytes()
    options = json.loads(raw)
    decision, handoff = compare(brief, options, packages)
    out = Path(out)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refuse overwrite of prior technology comparison")
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "FUNCTIONAL_SOURCE_RECEIPT.json":(Path(function_root)/"PACKAGE_RECEIPT.json").read_bytes(),
        "TECHNOLOGY_OPTIONS.json":canonical(options),
        "TECHNOLOGY_DECISION.json":canonical(decision),
        "PROVISIONAL_ARCHITECTURE_HANDOFF.json":canonical(handoff),
    }
    for name, body in files.items():
        (out / name).write_bytes(body)
    receipt = {
        "schema_version":"hardware_splicer.technology_study_receipt.v1",
        "source_spec_sha256":gate["source_spec_sha256"],
        "technology_options_sha256":decision["technology_options_sha256"],
        "files":{name:{"sha256":sha(body),"bytes":len(body)}
                 for name,body in sorted(files.items())},
        "physical_authority_granted":False,
        "function_validation_performed":False,
    }
    (out / "TECHNOLOGY_STUDY_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
