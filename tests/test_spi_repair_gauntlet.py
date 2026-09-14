from copy import deepcopy

from hardware_splicer.spi_repair_gauntlet import (
    actor_packets_only,
    build_repair_gauntlet,
    run_scripted_repair_control,
    score_repair,
)


def _packet(challenge_id: str):
    packets = actor_packets_only()["packets"]
    return next(row for row in packets if row["challenge_id"] == challenge_id)


def test_gauntlet_freezes_twelve_bounded_actor_packets_without_gold_repairs() -> None:
    gauntlet = build_repair_gauntlet()
    actor = actor_packets_only()

    assert gauntlet["challenge_count"] == 12
    assert actor["challenge_count"] == 12
    assert actor["gold_repairs_present"] is False
    assert gauntlet["packet_budget"]["budget_pass"] is True
    assert gauntlet["packet_budget"]["observed_max_packet_bytes"] <= 12_000
    assert gauntlet["packet_budget"]["observed_total_packet_bytes"] <= 96_000
    assert all("profile" not in packet for packet in actor["packets"])
    assert all("expected_post_outcome" not in packet for packet in actor["packets"])
    assert all(packet["physical_authority_granted"] is False for packet in [{**p["authority_boundary"]} for p in actor["packets"]])


def test_scripted_control_solves_every_frozen_challenge() -> None:
    control = run_scripted_repair_control()

    assert control["control_pass"] is True
    assert control["status"] == "passed_scripted_control"
    assert control["challenge_count"] == 12
    assert control["accepted_count"] == 12
    assert all(row["score_pass"] is True for row in control["rows"])
    assert control["physical_correctness"] == "UNPROVEN"
    assert control["physical_authority_granted"] is False


def test_scope_violation_is_rejected_even_if_candidate_becomes_safe() -> None:
    packet = _packet("rg-v1-002")
    proposal = deepcopy(packet["candidate"])
    proposal["signals"]["MISO"] = "dut_to_host"
    proposal["estimated_load_a"] = 0.02

    score = score_repair("rg-v1-002", proposal)

    assert score["score_pass"] is False
    assert score["checks"]["injected_defect_removed"] is True
    assert score["checks"]["mutation_scope_respected"] is False
    assert "estimated_load_a" in score["changed_paths"]


def test_noop_and_schema_deletion_are_rejected() -> None:
    packet = _packet("rg-v1-006")

    noop = score_repair("rg-v1-006", deepcopy(packet["candidate"]))
    assert noop["score_pass"] is False
    assert noop["checks"]["nonempty_repair"] is False

    missing = deepcopy(packet["candidate"])
    missing.pop("signals")
    rejected = score_repair("rg-v1-006", missing)
    assert rejected["score_pass"] is False
    assert rejected["checks"]["candidate_schema_exact"] is False


def test_mixed_timing_challenge_accepts_local_repair_but_remains_unsafe() -> None:
    packet = _packet("rg-v1-008")
    proposal = deepcopy(packet["candidate"])
    proposal["signals"]["MISO"] = "dut_to_host"

    score = score_repair("rg-v1-008", proposal)

    assert score["score_pass"] is True
    assert score["checks"]["injected_defect_removed"] is True
    assert score["expected_post_outcome"] == "unsafe"
    assert score["observed_post_outcome"] == "unsafe"
    assert any(
        row["check_id"] == "derived_half_cycle_timing" and row["status"] == "fail"
        for row in score["post_result"]["findings"]
    )


def test_mixed_power_challenge_cannot_be_fixed_by_changing_the_load() -> None:
    packet = _packet("rg-v1-009")
    proposal = deepcopy(packet["candidate"])
    proposal["direct_connection"] = False
    # Reuse the exact fixed-direction translator from a clean packet.
    proposal["translator"] = deepcopy(_packet("rg-v1-002")["candidate"]["translator"])
    proposal["estimated_load_a"] = 0.10

    score = score_repair("rg-v1-009", proposal)

    assert score["score_pass"] is False
    assert score["checks"]["injected_defect_removed"] is True
    assert score["checks"]["mutation_scope_respected"] is False


def test_actor_packet_contains_only_actionable_findings() -> None:
    packet = _packet("rg-v1-011")

    assert packet["verifier_findings"]
    assert all(row["status"] in {"fail", "blocked"} for row in packet["verifier_findings"])
    assert packet["packet_size_bytes"] < 12_000
    assert packet["authority_boundary"]["physical_correctness"] == "UNPROVEN"
    assert packet["authority_boundary"]["physical_authority_granted"] is False
