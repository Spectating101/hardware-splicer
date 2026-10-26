"""Offline multi-protocol fleet tests; no physical machine operations."""
from dataclasses import replace

import httpx
import pytest

from hardware_splicer.manufacturing_operator.fleet import (
    ManufacturingFleet, ManufacturingRequest, MachineCapabilities,
    MachineObservation, OctoPrintDriver,
)
from hardware_splicer.manufacturing_operator.moonraker import MoonrakerDriver
from hardware_splicer.manufacturing_operator.octoprint import (
    ManufacturingRefusal, OctoPrintOperator,
)


class FakeDriver:
    def __init__(self, *, state="idle", machine_type="fdm", monitor=True,
                 staging=True, verified=True):
        self.state = state
        self.machine_type = machine_type
        self.monitor = monitor
        self.staging = staging
        self.verified = verified
        self.probes = []

    def inspect(self, machine_id):
        self.probes.append(machine_id)
        return MachineObservation(
            machine_id=machine_id, controller="test-driver", state=self.state,
            controller_protocol_verified=self.verified,
            capabilities=MachineCapabilities(
                machine_type=self.machine_type,
                file_formats=(".gcode",) if self.machine_type == "fdm" else (".stl",),
                can_read_status=True, can_monitor_job=self.monitor,
                can_stage_file=self.staging,
            ),
        )


def test_routes_by_capability_without_brand_selection():
    fleet = ManufacturingFleet()
    fleet.enroll("maker-machine", FakeDriver(machine_type="fdm"))
    fleet.enroll("other-machine", FakeDriver(machine_type="resin"))
    plan = fleet.plan(ManufacturingRequest(machine_type="fdm", artifact_suffix=".gcode",
                                          need_staging=True))
    assert plan.machine_id == "maker-machine"
    assert plan.requires_operator_approval
    assert not plan.start_authorized
    assert not plan.automated_fabrication_authorized


def test_multiple_matches_must_be_disambiguated():
    fleet = ManufacturingFleet()
    fleet.enroll("one", FakeDriver())
    fleet.enroll("two", FakeDriver())
    req = ManufacturingRequest(machine_type="fdm", artifact_suffix=".gcode")
    with pytest.raises(ManufacturingRefusal, match="Multiple compatible"):
        fleet.plan(req)
    assert fleet.plan(req, machine_id="two").machine_id == "two"


@pytest.mark.parametrize("state", ["printing", "paused", "error", "offline", "unknown"])
def test_busy_unavailable_or_uncertain_printer_is_rejected(state):
    fleet = ManufacturingFleet()
    fleet.enroll("printer", FakeDriver(state=state))
    with pytest.raises(ManufacturingRefusal, match="No verified"):
        fleet.plan(ManufacturingRequest(machine_type="fdm", artifact_suffix=".gcode"))


def test_unknown_controller_is_not_trusted():
    fleet = ManufacturingFleet()
    fleet.enroll("fake", FakeDriver(verified=False))
    with pytest.raises(ManufacturingRefusal, match="protocol"):
        fleet.inspect("fake")


def test_missing_capability_blocks_routing():
    fleet = ManufacturingFleet()
    fleet.enroll("reader-only", FakeDriver(staging=False))
    with pytest.raises(ManufacturingRefusal):
        fleet.plan(ManufacturingRequest(machine_type="fdm", artifact_suffix=".gcode",
                                        need_staging=True))
    with pytest.raises(ManufacturingRefusal):
        fleet.plan(ManufacturingRequest(machine_type="fdm", artifact_suffix=".3mf"))


def test_octoprint_driver_requires_protocol_handshake_and_never_controls(tmp_path):
    seen = []
    def endpoint(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"text": "OctoPrint 1.11.0", "server": "1.11.0"})
        if request.url.path == "/api/printer":
            return httpx.Response(200, json={"state": {"text": "Operational",
                "flags": {"operational": True, "printing": False}}})
        raise AssertionError("Unexpected command")
    transport = httpx.MockTransport(endpoint)
    with OctoPrintOperator(base_url="http://192.168.1.10:5000",
                           api_key="mock", transport=transport) as client:
        fleet = ManufacturingFleet()
        fleet.enroll("A", OctoPrintDriver(client))
        obs = fleet.inspect("A")
        assert obs.controller == "octoprint"
        assert obs.state == "idle"
        assert obs.capabilities.can_stage_file is False
        assert fleet.plan(ManufacturingRequest("fdm", ".gcode")).machine_id == "A"
    assert seen == [("GET", "/api/version"), ("GET", "/api/printer")] * 2


def test_moonraker_driver_read_only_and_different_protocol():
    seen = []
    def endpoint(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/server/info":
            return httpx.Response(200, json={"result": {
                "klippy_state": "ready", "moonraker_version": "0.9"}})
        if request.url.path == "/printer/objects/query":
            assert "print_stats" in request.url.params
            return httpx.Response(200, json={"result": {"status": {
                "print_stats": {"state": "standby", "filename": ""}}}})
        raise AssertionError("Unexpected machine request")
    with MoonrakerDriver(base_url="http://10.0.0.20:7125",
                         transport=httpx.MockTransport(endpoint)) as driver:
        fleet = ManufacturingFleet()
        fleet.enroll("B", driver)
        obs = fleet.inspect("B")
        assert obs.state == "idle"
        assert obs.controller == "moonraker"
        assert obs.capabilities.can_monitor_job
        assert not obs.capabilities.can_stage_file
        assert not obs.capabilities.can_start_job
        with pytest.raises(ManufacturingRefusal):
            fleet.plan(ManufacturingRequest("fdm", ".gcode", need_staging=True))
    assert seen == [("GET", "/server/info"), ("GET", "/printer/objects/query")] * 2


def test_moonraker_unknown_or_bad_protocol_is_not_promoted():
    def endpoint(request):
        if request.url.path == "/server/info":
            return httpx.Response(200, json={"result": {"klippy_state": "ready"}})
        return httpx.Response(200, json={"result": {"status": {
            "print_stats": {"state": "unrecognized_state"}}}})
    with MoonrakerDriver(base_url="http://192.168.1.55:7125",
                         transport=httpx.MockTransport(endpoint)) as client:
        fleet = ManufacturingFleet()
        fleet.enroll("printer", client)
        assert fleet.inspect("printer").state == "unknown"
        with pytest.raises(ManufacturingRefusal):
            fleet.plan(ManufacturingRequest("fdm", ".gcode"))
