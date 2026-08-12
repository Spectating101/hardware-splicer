from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.evidence_contract_store import apply_interface_contract_update
from hardware_splicer.evidence_salvage_bridge import attach_evidence_first_integrations


def _write_plan(tmp_path: Path) -> str:
    package = attach_evidence_first_integrations(
        {
            "recommended_build_id": "robot_drive",
            "splice_plan": {
                "reusable_blocks": [
                    {
                        "board_id": "donor-board",
                        "block_id": "driver-01",
                        "name": "Donor motor driver",
                        "function_type": "actuator_driver",
                        "connector_refs": ["J_LOGIC"],
                    }
                ]
            },
            "firmware_scaffold": {"source": "generated/main.cpp"},
        }
    )
    (tmp_path / "SPLICE_PLAN.json").write_text(json.dumps(package), encoding="utf-8")
    return package["evidence_integrations"]["interfaces"][0]["interface_contract"]["interface_id"]


def _update(**extra) -> dict:
    body = {
        "operation": "upsert_signal",
        "signal_id": "enable",
        "contact_id": "J_LOGIC.1",
        "connector_ref": "J_LOGIC",
        "pin_number": "1",
        "direction": "input",
        "voltage_max_v": 3.3,
        "active_level": "high",
        "controller_pin": "GPIO16",
    }
    body.update(extra)
    return body


@pytest.mark.parametrize("missing", ["evidence_id", "method", "producer"])
def test_interface_update_refuses_synthesized_provenance(tmp_path: Path, missing: str) -> None:
    interface_id = _write_plan(tmp_path)
    update = _update(
        evidence_id="bench-interface-001",
        method="DMM plus protected stimulus",
        producer="operator_01+dmm_01",
    )
    update.pop(missing)

    with pytest.raises(ValueError, match="explicit physical evidence provenance"):
        apply_interface_contract_update(
            tmp_path,
            interface_id=interface_id,
            update=update,
        )

    stored = json.loads((tmp_path / "SPLICE_PLAN.json").read_text(encoding="utf-8"))
    interface = stored["evidence_integrations"]["interfaces"][0]
    assert interface["compile_status"] == "blocked"
    assert interface["interface_contract"]["firmware_authorized"] is False


def test_interface_update_preserves_explicit_provenance_verbatim(tmp_path: Path) -> None:
    interface_id = _write_plan(tmp_path)
    result = apply_interface_contract_update(
        tmp_path,
        interface_id=interface_id,
        update=_update(
            evidence_id="bench-interface-002",
            method="DMM plus protected stimulus",
            producer="operator_02+dmm_02",
            interface_complete=True,
        ),
    )

    evidence = result["evidence_integrations"]["evidence_graph"]["evidence"][-1]
    assert evidence["evidence_id"] == "bench-interface-002"
    assert evidence["method"] == "DMM plus protected stimulus"
    assert evidence["producer"] == "operator_02+dmm_02"
