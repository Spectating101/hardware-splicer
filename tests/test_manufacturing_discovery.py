"""Read-only automatic protocol selection from operator-enrolled endpoints."""
import httpx
import pytest

from hardware_splicer.manufacturing_operator import (
    connect_enrolled_controller, ManufacturingFleet, ManufacturingRequest,
    ManufacturingRefusal,
)


def test_recognize_octoprint_and_plan_without_brand_choice():
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"text": "OctoPrint 1.11.0", "server": "1.11.0"})
        if request.url.path == "/api/printer":
            return httpx.Response(200, json={"state": {
                "text": "Operational", "flags": {"operational": True,
                    "printing": False, "paused": False, "error": False}}})
        raise AssertionError(f"Unexpected device call: {request}")
    driver = connect_enrolled_controller(
        base_url="http://192.168.20.4:5000", api_key="fixture-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        fleet = ManufacturingFleet()
        fleet.enroll("workshop-A", driver)
        plan = fleet.plan(ManufacturingRequest(machine_type="fdm", artifact_suffix=".gcode"))
        assert plan.machine_id == "workshop-A"
        assert plan.controller == "octoprint"
        assert not plan.start_authorized
    finally:
        driver.client.close()
    assert seen == [("GET", "/api/version"),
                    ("GET", "/api/version"), ("GET", "/api/printer")]


def test_recognize_moonraker_without_moonraker_vendor_configuration():
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/version":
            return httpx.Response(404)
        if request.url.path == "/server/info":
            return httpx.Response(200, json={"result": {
                "moonraker_version": "0.9.3", "klippy_state": "ready"}})
        if request.url.path == "/printer/objects/query":
            return httpx.Response(200, json={"result": {"status": {
                "print_stats": {"state": "standby"}}}})
        raise AssertionError("Unexpected device call")
    driver = connect_enrolled_controller(
        base_url="http://192.168.10.8:7125",
        transport=httpx.MockTransport(handler),
    )
    try:
        fleet = ManufacturingFleet()
        fleet.enroll("workshop-B", driver)
        assert fleet.inspect("workshop-B").controller == "moonraker"
        assert fleet.plan(ManufacturingRequest("fdm", ".gcode")).requires_operator_approval
        with pytest.raises(ManufacturingRefusal):
            fleet.plan(ManufacturingRequest("fdm", ".gcode", need_staging=True))
    finally:
        driver.close()
    assert all(method == "GET" for method, _ in seen)


def test_unknown_api_refuses_without_guessing_any_commands():
    def handler(request):
        return httpx.Response(200, json={"generic": "some 3d printer"})
    with pytest.raises(ManufacturingRefusal, match="not a supported"):
        connect_enrolled_controller(
            base_url="http://192.168.1.71:80",
            transport=httpx.MockTransport(handler),
        )


def test_public_address_refused_before_network_probe():
    def fail_if_called(_request):
        raise AssertionError("Never probe an untrusted destination")
    with pytest.raises(ManufacturingRefusal):
        connect_enrolled_controller(
            base_url="http://8.8.8.8:5000",
            transport=httpx.MockTransport(fail_if_called),
        )
