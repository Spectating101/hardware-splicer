from copy import deepcopy

from hardware_splicer.spi_model_campaign_adjudication import adjudicate_spi_model_campaign
from hardware_splicer.spi_model_execution_contract import (
    required_checks_for_execution,
    seal_spi_model_execution_result,
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


def _sealed_result(campaign: dict, execution: dict) -> dict:
    execution_id = execution["execution_id"]
    hashes = {
        model_id: campaign["model_captures"][model_id]["capture_sha256"]
        for model_id in execution["required_models"]
    }
    return seal_spi_model_execution_result(
        campaign,
        execution_id=execution_id,
        engine_name="synthetic-test-engine",
        engine_version="0-test",
        exit_code=0,
        raw_output=(execution_id + "\n").encode(),
        model_hashes=hashes,
        checks=[
            {"check_id": check_id, "status": "pass", "evidence": {"synthetic": True}}
            for check_id in sorted(required_checks_for_execution(execution_id))
        ],
        metrics={"synthetic_metric": 1.0},
    )


def _all_results(campaign: dict) -> list[dict]:
    return [_sealed_result(campaign, row) for row in campaign["planned_executions"]]


def test_complete_exact_campaign_passes_only_as_modeled_evidence() -> None:
    campaign = _ready_campaign()
    verdict = adjudicate_spi_model_campaign(campaign, _all_results(campaign))

    assert campaign["status"] == "ready_for_model_execution"
    assert verdict["status"] == "passed_modeled_campaign"
    assert verdict["campaign_pass"] is True
    assert all(verdict["checks"].values())
    assert verdict["missing_execution_ids"] == []
    assert verdict["duplicate_execution_ids"] == []
    assert verdict["foreign_execution_ids"] == []
    assert verdict["physical_correctness"] == "UNPROVEN"
    assert verdict["physical_authority_granted"] is False


def test_missing_execution_rejects_campaign() -> None:
    campaign = _ready_campaign()
    results = _all_results(campaign)[:-1]

    verdict = adjudicate_spi_model_campaign(campaign, results)

    assert verdict["campaign_pass"] is False
    assert verdict["status"] == "rejected_incomplete_or_failed_campaign"
    assert verdict["checks"]["exactly_one_result_per_execution"] is False
    assert verdict["missing_execution_ids"] == ["verilog-jedec-id-read-9f"]


def test_duplicate_execution_rejects_campaign() -> None:
    campaign = _ready_campaign()
    results = _all_results(campaign)
    results.append(deepcopy(results[0]))

    verdict = adjudicate_spi_model_campaign(campaign, results)

    assert verdict["campaign_pass"] is False
    assert verdict["checks"]["exactly_one_result_per_execution"] is False
    assert verdict["duplicate_execution_ids"] == [results[0]["execution_id"]]


def test_foreign_execution_rejects_campaign() -> None:
    campaign = _ready_campaign()
    results = _all_results(campaign)
    foreign = deepcopy(results[0])
    foreign["execution_id"] = "foreign-execution"
    results.append(foreign)

    verdict = adjudicate_spi_model_campaign(campaign, results)

    assert verdict["campaign_pass"] is False
    assert verdict["checks"]["no_foreign_executions"] is False
    assert verdict["foreign_execution_ids"] == ["foreign-execution"]


def test_failed_execution_audit_rejects_campaign() -> None:
    campaign = _ready_campaign()
    results = _all_results(campaign)
    results[0]["physical_authority_granted"] = True
    results[0]["authority_effect"] = "promote"

    verdict = adjudicate_spi_model_campaign(campaign, results)

    assert verdict["campaign_pass"] is False
    assert verdict["checks"]["all_execution_audits_pass"] is False
    assert results[0]["execution_id"] in verdict["rejected_execution_ids"]


def test_partial_campaign_cannot_receive_complete_campaign_credit() -> None:
    partial = build_spi_virtual_model_campaign(
        [_capture("txu0304-ibis-scem787", "1", "IBIS")]
    )

    verdict = adjudicate_spi_model_campaign(partial, [])

    assert partial["status"] == "partial_model_execution_ready"
    assert verdict["status"] == "rejected_campaign_not_ready"
    assert verdict["campaign_pass"] is False
    assert verdict["checks"]["campaign_ready"] is False
