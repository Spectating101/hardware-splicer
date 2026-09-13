from hardware_splicer.spi_model_execution_contract import (
    RESULT_SCHEMA_VERSION,
    audit_spi_model_execution_result,
    required_checks_for_execution,
)
from hardware_splicer.spi_virtual_model_campaign import build_spi_virtual_model_campaign


def _capture(model_id: str, byte: str, kind: str) -> dict:
    return {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": model_id,
        "expected_model_kind": kind,
        "recognized_expected_model_file_count": 1,
        "capture_status": "captured_hashed_unreviewed",
        "sha256": "sha256:" + byte * 64,
        "size_bytes": 1024,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "authority_effect": "none",
        "physical_authority_granted": False,
    }


def _ready_campaign() -> dict:
    return build_spi_virtual_model_campaign(
        [
            _capture("txu0304-ibis-scem787", "1", "IBIS"),
            _capture("w25q128jwsiq-ibis-da03-aag072", "2", "IBIS"),
            _capture("w25q128jw-q-verilog-da02-aag072", "3", "Verilog"),
        ]
    )


def _nominal_result(campaign: dict) -> dict:
    execution_id = "ibis-nominal-3v3-to-1v8"
    required = sorted(required_checks_for_execution(execution_id))
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "execution_id": execution_id,
        "target_candidate_id": campaign["target_candidate_id"],
        "engine": {"name": "synthetic-ibis-test-engine", "version": "0.0-test"},
        "exit_code": 0,
        "raw_output_sha256": "sha256:" + "a" * 64,
        "model_hashes": {
            "txu0304-ibis-scem787": campaign["model_captures"]["txu0304-ibis-scem787"]["capture_sha256"],
            "w25q128jwsiq-ibis-da03-aag072": campaign["model_captures"]["w25q128jwsiq-ibis-da03-aag072"]["capture_sha256"],
        },
        "checks": [
            {"check_id": check_id, "status": "pass", "evidence": {"synthetic": True}}
            for check_id in required
        ],
        "metrics": {"worst_overshoot_v": 1.95, "minimum_logic_margin_v": 0.2},
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def test_complete_result_is_accepted_only_as_modeled_evidence() -> None:
    campaign = _ready_campaign()
    result = _nominal_result(campaign)

    audit = audit_spi_model_execution_result(campaign, result)

    assert campaign["status"] == "ready_for_model_execution"
    assert audit["status"] == "accepted_modeled_result"
    assert audit["audit_pass"] is True
    assert all(audit["checks"].values())
    assert audit["physical_correctness"] == "UNPROVEN"
    assert audit["physical_authority_granted"] is False


def test_result_is_rejected_when_campaign_has_not_captured_models() -> None:
    not_ready = build_spi_virtual_model_campaign()
    result = _nominal_result(_ready_campaign())

    audit = audit_spi_model_execution_result(not_ready, result)

    assert audit["status"] == "rejected_campaign_not_ready"
    assert audit["checks"]["campaign_ready"] is False


def test_wrong_model_hash_is_rejected() -> None:
    campaign = _ready_campaign()
    result = _nominal_result(campaign)
    result["model_hashes"]["txu0304-ibis-scem787"] = "sha256:" + "f" * 64

    audit = audit_spi_model_execution_result(campaign, result)

    assert audit["audit_pass"] is False
    assert audit["checks"]["model_hash_binding"] is False
    assert audit["details"]["model_hash_binding_errors"] == ["txu0304-ibis-scem787"]


def test_missing_required_simulation_check_is_rejected() -> None:
    campaign = _ready_campaign()
    result = _nominal_result(campaign)
    result["checks"] = [
        row for row in result["checks"] if row["check_id"] != "overshoot_absolute_maximum"
    ]

    audit = audit_spi_model_execution_result(campaign, result)

    assert audit["checks"]["required_checks_present"] is False
    assert audit["details"]["missing_required_checks"] == ["overshoot_absolute_maximum"]
    assert audit["audit_pass"] is False


def test_failed_required_simulation_check_is_rejected() -> None:
    campaign = _ready_campaign()
    result = _nominal_result(campaign)
    for row in result["checks"]:
        if row["check_id"] == "settling_before_sample":
            row["status"] = "fail"

    audit = audit_spi_model_execution_result(campaign, result)

    assert audit["checks"]["required_checks_pass"] is False
    assert audit["details"]["failed_required_checks"] == ["settling_before_sample"]


def test_engine_cannot_self_grant_physical_authority() -> None:
    campaign = _ready_campaign()
    result = _nominal_result(campaign)
    result["measured_evidence_present"] = True
    result["physical_correctness"] = "VERIFIED"
    result["fabrication_ready"] = True
    result["power_on_ready"] = True
    result["physical_authority_granted"] = True
    result["authority_effect"] = "promote"

    audit = audit_spi_model_execution_result(campaign, result)

    assert audit["checks"]["authority_boundary"] is False
    assert audit["audit_pass"] is False
    assert audit["physical_correctness"] == "UNPROVEN"
    assert audit["physical_authority_granted"] is False


def test_nonfinite_numeric_metric_is_rejected() -> None:
    campaign = _ready_campaign()
    result = _nominal_result(campaign)
    result["metrics"]["minimum_logic_margin_v"] = float("nan")

    audit = audit_spi_model_execution_result(campaign, result)

    assert audit["checks"]["finite_numeric_metrics"] is False
    assert audit["details"]["nonfinite_numeric_metrics"] == ["minimum_logic_margin_v"]
