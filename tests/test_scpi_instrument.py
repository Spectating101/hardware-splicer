from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_operator import PhysicalOperatorRegistry
from hardware_splicer.physical_presets import bench_instrument_descriptor
from hardware_splicer.scpi_instrument import ScpiReadOnlyHandle

PROJECT = "fielddeck"
MISSION = "mission-scpi"


class Transport:
    def __init__(self):
        self.commands = []

    def query(self, command):
        self.commands.append(command)
        return {
            "*IDN?": "ACME,MODEL1,SN123,1.0",
            "MEAS:VOLT?": "4.912",
            "MEAS:CURR?": "0.118",
        }[command]


def _setup(tmp_path):
    transport = Transport()
    handle = ScpiReadOnlyHandle(
        operator_id="dmm-1",
        transport=transport,
        measurements={
            "rail_voltage": "MEAS:VOLT?",
            "rail_current": "MEAS:CURR?",
        },
    )
    operators = PhysicalOperatorRegistry()
    operators.register(bench_instrument_descriptor(operator_id="dmm-1", display_name="Bench Meter"), handle)
    dispatcher = PhysicalDispatcher(
        registry=operators,
        grants=PhysicalPlanGrantStore(tmp_path / "grants"),
    )
    return operators, dispatcher, transport


def test_scpi_status_and_measurement_are_observation_only(tmp_path):
    operators, dispatcher, transport = _setup(tmp_path)
    status = operators.plan(
        operator_id="dmm-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="status",
        payload={},
    )
    status_receipt = dispatcher.dispatch(status)
    assert status_receipt["authority"] == "not_required"
    assert status_receipt["result"]["value"] == "ACME,MODEL1,SN123,1.0"

    read = operators.plan(
        operator_id="dmm-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="read",
        payload={"measurement_id": "rail_voltage"},
    )
    receipt = dispatcher.dispatch(read)
    assert receipt["result"]["value"] == "4.912"
    assert transport.commands == ["*IDN?", "MEAS:VOLT?"]


def test_agent_cannot_send_raw_scpi_command(tmp_path):
    operators, dispatcher, transport = _setup(tmp_path)
    plan = operators.plan(
        operator_id="dmm-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="read",
        payload={"measurement_id": "MEAS:VOLT?"},
    )
    with pytest.raises(FabricationValidationError, match="measurement_id"):
        dispatcher.dispatch(plan)
    assert transport.commands == []


def test_read_only_adapter_refuses_output_or_configuration_writes(tmp_path):
    operators, dispatcher, transport = _setup(tmp_path)
    configure = operators.plan(
        operator_id="dmm-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="configure",
        payload={"recipe_id": "recipe-1"},
    )
    with pytest.raises(FabricationValidationError, match="does not permit instrument writes"):
        dispatcher.dispatch(configure)

    disable = operators.plan(
        operator_id="dmm-1",
        project_id=PROJECT,
        mission_id=MISSION,
        action="disable_output",
        payload={},
    )
    with pytest.raises(FabricationValidationError, match="does not permit instrument writes"):
        dispatcher.dispatch(disable)
    assert transport.commands == []
