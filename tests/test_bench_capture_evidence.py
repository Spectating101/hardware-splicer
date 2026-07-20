from __future__ import annotations

import hashlib
import json

import pytest

from hardware_splicer.bench_capture_evidence import (
    BenchCaptureEvidenceError,
    project_bench_capture_to_evidence,
)
from hardware_splicer.machine_project import (
    AuthorityState,
    Component,
    Domain,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    Subsystem,
)


def project() -> MachineProject:
    return MachineProject(
        project_id="robot",
        name="Inspection robot",
        purpose="Inspect a building",
        subsystems=[
            Subsystem(
                subsystem_id="power",
                name="Power",
                domain=Domain.ELECTRICAL,
                component_ids=["battery"],
                interface_ids=["power-link"],
            ),
            Subsystem(
                subsystem_id="drive",
                name="Drive",
                domain=Domain.MECHANICAL,
                component_ids=["motor"],
                interface_ids=["power-link"],
            ),
        ],
        components=[
            Component(
                component_id="battery",
                name="Battery",
                domain=Domain.ELECTRICAL,
                subsystem_id="power",
                authority=AuthorityState.DECLARED,
            ),
            Component(
                component_id="motor",
                name="Motor",
                domain=Domain.MECHANICAL,
                subsystem_id="drive",
                authority=AuthorityState.DECLARED,
            ),
        ],
        interfaces=[
            Interface(
                interface_id="power-link",
                name="Battery to motor",
                kind="power",
                endpoints=[
                    InterfaceEndpoint(object_id="battery", port="output"),
                    InterfaceEndpoint(object_id="motor", port="power"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        values={"nominal_voltage_v": 12},
                        authority=AuthorityState.DECLARED,
                    )
                ],
                authority=AuthorityState.DECLARED,
            )
        ],
    )


def capture(*, calibration: str = "valid", simulated: bool = False) -> dict:
    return {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "power-load-001",
        "recorded_at": "2026-07-20T12:00:00Z",
        "operator_id": "tech-1",
        "simulated": simulated,
        "instruments": [
            {
                "instrument_id": "dmm-1",
                "instrument_type": "calibrated_dmm",
                "calibration_status": calibration,
            }
        ],
        "measurements": [
            {
                "measurement_id": "measure-power-link",
                "interface_id": "power-link",
                "kind": "voltage",
                "status": "pass",
                "value": 12.1,
                "unit": "V",
                "instrument_id": "dmm-1",
            }
        ],
    }


def test_calibrated_capture_promotes_exact_interface_to_measured() -> None:
    packet = capture()
    result = project_bench_capture_to_evidence(project(), packet)

    assert result["imported_count"] == 1
    assert result["promotions"] == [
        {"collection": "interfaces", "object_id": "power-link", "authority": "measured"}
    ]
    assert result["project"].interfaces[0].authority == AuthorityState.MEASURED
    evidence = result["project"].evidence[0]
    assert evidence.authority == AuthorityState.MEASURED
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert evidence.metadata["capture_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert evidence.metadata["instrument_id"] == "dmm-1"


def test_missing_calibration_limits_capture_to_observed() -> None:
    result = project_bench_capture_to_evidence(project(), capture(calibration="expired"))

    assert result["project"].interfaces[0].authority == AuthorityState.OBSERVED
    assert result["project"].evidence[0].authority == AuthorityState.OBSERVED
    assert result["warnings"][0]["code"] == "measurement_authority_limited"
    assert "expired" in result["warnings"][0]["message"]


def test_simulated_capture_records_evidence_without_physical_promotion() -> None:
    result = project_bench_capture_to_evidence(project(), capture(calibration="simulated", simulated=True))

    assert result["promotions"] == []
    assert result["project"].interfaces[0].authority == AuthorityState.DECLARED
    evidence = result["project"].evidence[0]
    assert evidence.simulated is True
    assert evidence.authority == AuthorityState.OBSERVED
    assert evidence.basis == "simulation"


def test_explicit_target_map_is_required_when_capture_has_no_exact_object_id() -> None:
    packet = capture()
    measurement = packet["measurements"][0]
    measurement.pop("interface_id")
    measurement["gate_id"] = "gate-battery-voltage"

    result = project_bench_capture_to_evidence(
        project(),
        packet,
        target_map={
            "gate-battery-voltage": {
                "collection": "components",
                "object_id": "battery",
            }
        },
    )
    assert result["project"].components[0].authority == AuthorityState.MEASURED

    with pytest.raises(BenchCaptureEvidenceError, match="produced no canonical evidence"):
        project_bench_capture_to_evidence(project(), packet)


def test_failed_rows_do_not_become_supporting_evidence() -> None:
    packet = capture()
    packet["measurements"][0]["status"] = "fail"

    with pytest.raises(BenchCaptureEvidenceError, match="produced no canonical evidence"):
        project_bench_capture_to_evidence(project(), packet)
