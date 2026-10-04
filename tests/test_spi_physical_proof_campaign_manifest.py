from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
MANIFEST = REFERENCE / "physical_proof_campaign_v1.json"
PROVIDER_TEMPLATE = REFERENCE / "provider_review_record_template_v1.json"
PROVIDER_SCORECARD = REFERENCE / "PROVIDER_SELECTION_SCORECARD.json"
PROVIDER_QUOTE_REQUEST = REFERENCE / "PROVIDER_QUOTE_REQUEST.md"
PACKAGE_SHA256 = "6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd"
PENDING_PROVIDER_RECORDS = [
    REFERENCE / "provider_review_jlcpcb_pending_v1.json",
    REFERENCE / "provider_review_pcbway_pending_v1.json",
]


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_campaign_binds_exact_frozen_subject():
    manifest = load_manifest()
    source = manifest["canonical_source"]
    assert manifest["schema_version"] == 1
    assert manifest["tracking_issue"] == "Spectating101/hardware-splicer#105"
    assert source["revision"] == "f892facd67c5124e2362860ebc999625afedc5d5"
    assert source["starting_state"] == "PACKAGED_NOT_PHYSICAL"
    assert source["physical_correctness"] == "UNPROVEN"
    assert source["successor_substitution_allowed"] is False


def test_all_physical_authority_starts_closed():
    authority = load_manifest()["authority"]
    assert authority == {
        "provider_selected": False,
        "fabrication_authorized": False,
        "assembly_accepted": False,
        "power_on_authorized": False,
        "functional_test_authorized": False,
        "release_authorized": False,
    }


def test_gate_order_is_explicit_and_only_review_is_active():
    gates = load_manifest()["gates"]
    assert [gate["id"] for gate in gates] == [
        "P0_independent_review",
        "P1_fabrication_decision",
        "P2_assembly_identity",
        "P3_cold_checks",
        "P4_controlled_power",
        "P5_bounded_functional_transaction",
        "P6_evidence_closure",
    ]
    assert gates[0]["status"] == "ACTIVE"
    assert all(gate["status"] == "BLOCKED" for gate in gates[1:])


def test_first_functional_transaction_is_read_only_and_bounded():
    gate = next(gate for gate in load_manifest()["gates"] if gate["id"] == "P5_bounded_functional_transaction")
    transaction = gate["transaction"]
    assert transaction["command"] == "0x9F"
    assert transaction["mode"] == 0
    assert transaction["frequency_hz"] == 5_000_000
    assert transaction["write_operations_allowed"] is False
    assert transaction["expected_jedec_id"] == "EF6018"


def test_real_physical_evidence_and_stale_invalidation_are_mandatory():
    evidence = load_manifest()["evidence_requirements"]
    assert evidence["physical_evidence_requires_simulated_false"] is True
    assert evidence["exact_revision_required"] is True
    assert evidence["failed_results_must_be_preserved"] is True
    assert evidence["repair_creates_successor_revision"] is True
    assert evidence["stale_evidence_must_be_invalidated_after_relevant_change"] is True


def test_campaign_cannot_be_used_for_generic_feature_expansion():
    guards = load_manifest()["scope_guards"]
    assert guards["generic_ai_feature_expansion"] is False
    assert guards["generic_eda_rebuild"] is False
    assert guards["routing_engine_work"] is False
    assert guards["evidence_semantics_change"] is False
    assert guards["frontend_reopen_without_concrete_gap"] is False
    assert guards["engineering_change_requires_concrete_artifact_or_evaluator_or_measurement_defect"] is True


def test_provider_review_template_is_quote_only_and_has_zero_authority_effect():
    record = json.loads(PROVIDER_TEMPLATE.read_text(encoding="utf-8"))
    assert record["campaign_id"] == "hs-spi-physical-proof-v1"
    assert record["subject"]["revision"] == load_manifest()["canonical_source"]["revision"]
    assert record["human_disposition"]["status"] == "needs_followup"
    assert record["authority_effect"] == {
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "functional_test_authorized": False,
        "release_authorized": False,
    }


def test_provider_selection_scorecard_cannot_trade_evidence_for_price():
    scorecard = json.loads(PROVIDER_SCORECARD.read_text(encoding="utf-8"))
    assert scorecard["campaign"] == "hs-spi-physical-proof-v1"
    assert scorecard["decision"] == "parallel_dual_quote"
    assert scorecard["authority_effect"] == "NONE"
    assert "pass_fail_only_without_required_raw_evidence" in scorecard["disqualifiers"]
    assert "cannot_bind_result_to_exact_board_and_revision" in scorecard["disqualifiers"]
    assert "silent_component_substitution" in scorecard["disqualifiers"]
    assert "evidence fidelity outranks headline price" in scorecard["selection_rule"].lower()


def test_both_provider_candidates_keep_exact_evidence_questions_open():
    scorecard = json.loads(PROVIDER_SCORECARD.read_text(encoding="utf-8"))
    providers = {provider["id"]: provider for provider in scorecard["providers"]}
    assert set(providers) == {"jlcpcb", "pcbway"}
    required = {
        "exact_revision_fidelity",
        "dnp_open_state_fidelity",
        "raw_cold_measurements",
        "staged_current_limited_power",
        "raw_rail_current_values",
        "bounded_0x9f_only_transaction",
        "raw_spi_or_jedec_result",
        "board_revision_traceability",
        "no_silent_rework_or_substitution",
    }
    for provider in providers.values():
        assert provider["status"] == "CONTACT_READY_EVIDENCE_UNCONFIRMED"
        assert required.issubset(set(provider["must_confirm_in_writing"]))


def test_campaign_and_provider_records_bind_release_digest():
    manifest = load_manifest()
    record = json.loads(PROVIDER_TEMPLATE.read_text(encoding="utf-8"))
    quote = PROVIDER_QUOTE_REQUEST.read_text(encoding="utf-8")
    assert manifest["canonical_source"]["package_sha256"] == PACKAGE_SHA256
    assert record["subject"]["package_sha256"] == PACKAGE_SHA256
    assert PACKAGE_SHA256 in quote
    assert manifest["canonical_source"]["revision"] == record["subject"]["revision"]


def test_pending_provider_records_are_contact_ready_but_authority_empty():
    for path in PENDING_PROVIDER_RECORDS:
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["contact_state"] == "PENDING_SEND"
        assert record["outbound_inquiry"]["state"] == "READY_NOT_SENT"
        assert record["received_at"] is None
        assert record["human_disposition"]["status"] == "needs_followup"
        assert all(value is False for value in record["authority_effect"].values())
        assert record["subject"]["package_sha256"] == PACKAGE_SHA256
