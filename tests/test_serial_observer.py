from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.physical_authority import PhysicalPlanGrantStore
from hardware_splicer.physical_dispatch import PhysicalDispatcher
from hardware_splicer.physical_observation_store import PhysicalObservationStore
from hardware_splicer.physical_operator import PhysicalOperatorRegistry
from hardware_splicer.physical_presets import serial_observer_descriptor
from hardware_splicer.serial_observer import SerialObservationHandle


class FakeSerialSource:
    source_id = "dut-uart-0"

    def __init__(self):
        self.calls = 0

    def capture(self):
        self.calls += 1
        return b"BOOT\nsensor ready\n", {
            "transport": "test",
            "byte_count": 18,
            "truncated": False,
            "text_preview": "BOOT\nsensor ready\n",
        }


def _runtime(tmp_path):
    source = FakeSerialSource()
    observations = PhysicalObservationStore(tmp_path / "observations")
    handle = SerialObservationHandle(
        operator_id="serial-a",
        source=source,
        observations=observations,
    )
    operators = PhysicalOperatorRegistry()
    operators.register(
        serial_observer_descriptor(operator_id="serial-a", display_name="DUT UART"),
        handle,
    )
    dispatcher = PhysicalDispatcher(
        registry=operators,
        grants=PhysicalPlanGrantStore(tmp_path / "grants"),
    )
    return source, observations, operators, dispatcher


def test_serial_capture_is_read_only_observation_and_retains_transcript(tmp_path):
    source, observations, operators, dispatcher = _runtime(tmp_path)
    plan = operators.plan(
        operator_id="serial-a",
        project_id="project-a",
        mission_id="mission-a",
        action="capture_log",
        payload={},
    )
    receipt = dispatcher.dispatch(plan)
    assert receipt["authority"] == "not_required"
    result = receipt["result"]
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["interpretation_performed"] is False
    observation = result["observation"]
    assert observation["kind"] == "serial_log"
    assert observations.read_bytes(observation["observation_id"]) == b"BOOT\nsensor ready\n"
    assert source.calls == 1


def test_serial_status_does_not_read_or_claim_pass(tmp_path):
    source, observations, operators, dispatcher = _runtime(tmp_path)
    plan = operators.plan(
        operator_id="serial-a",
        project_id="project-a",
        mission_id="mission-a",
        action="status",
        payload={},
    )
    receipt = dispatcher.dispatch(plan)
    assert receipt["result"]["physical_correctness"] == "UNPROVEN"
    assert source.calls == 0
    assert observations.list_public() == []


def test_serial_descriptor_exposes_no_write_action(tmp_path):
    _source, _observations, operators, _dispatcher = _runtime(tmp_path)
    descriptor = operators.descriptor("serial-a")
    assert {action.name for action in descriptor.actions} == {"status", "capture_log"}
    with pytest.raises(FabricationValidationError, match="does not expose action"):
        descriptor.action("write")
