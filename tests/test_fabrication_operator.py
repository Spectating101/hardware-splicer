from __future__ import annotations

import hashlib

import httpx
import pytest

from hardware_splicer.fabrication_operator import (
    FabricationAuthorityError,
    FabricationGrantStore,
    FabricationValidationError,
)
from hardware_splicer.printer_operator import (
    FabricationPrinter,
    MoonrakerBackend,
    OctoPrintBackend,
)
from hardware_splicer.printer_transport import HttpxPrinterTransport

HUMAN = {"kind": "human", "id": "project-owner"}
AGENT = {"kind": "agent", "id": "fabrication-agent"}
PROJECT = "monitor"
MISSION = "mission-1234567890abcdef"
PRINTER = "printer-lab"
GCODE = b"; generated for test only\nG28\n; no real printer is contacted\n"
SHA = hashlib.sha256(GCODE).hexdigest()


class FakeTransport:
    def __init__(self, *, fail_start: bool = False):
        self.calls = []
        self.fail_start = fail_start

    def request(self, method, path, *, json_body=None):
        self.calls.append(("request", method, path, json_body))
        is_start = (
            (
                path.startswith("/api/files/local/")
                and json_body == {"command": "select", "print": True}
            )
            or path.startswith("/printer/print/start?")
        )
        if self.fail_start and is_start:
            raise ConnectionError("ambiguous printer connection failure")
        return {"ok": True, "path": path}

    def upload(self, path, *, filename, data, fields):
        self.calls.append(("upload", path, filename, data, dict(fields)))
        if path == "/api/files/local":
            return {"files": {"local": {"path": filename}}}
        return {"item": {"path": f"jobs/{filename}"}}


def _printer(tmp_path, backend, *, fail_start=False):
    grants = FabricationGrantStore(tmp_path / "grants")
    transport = FakeTransport(fail_start=fail_start)
    printer = FabricationPrinter(
        printer_id=PRINTER,
        backend=backend,
        transport=transport,
        grants=grants,
    )
    return printer, grants, transport


def _grant(grants, *, action="start", sha=SHA):
    return grants.issue(
        project_id=PROJECT,
        mission_id=MISSION,
        operator_id=PRINTER,
        action=action,
        artifact_sha256=sha,
        author=HUMAN,
    )


def test_agent_cannot_mint_physical_fabrication_authority(tmp_path):
    grants = FabricationGrantStore(tmp_path / "grants")
    with pytest.raises(FabricationAuthorityError, match="human"):
        grants.issue(
            project_id=PROJECT,
            mission_id=MISSION,
            operator_id=PRINTER,
            action="start",
            artifact_sha256=SHA,
            author=AGENT,
        )


def test_grant_is_one_shot_and_bound_to_exact_artifact(tmp_path):
    grants = FabricationGrantStore(tmp_path / "grants")
    grant = _grant(grants)
    with pytest.raises(FabricationAuthorityError, match="artifact_sha256"):
        grants.consume(
            grant["grant_id"],
            project_id=PROJECT,
            mission_id=MISSION,
            operator_id=PRINTER,
            action="start",
            artifact_sha256="0" * 64,
        )
    used = grants.consume(
        grant["grant_id"],
        project_id=PROJECT,
        mission_id=MISSION,
        operator_id=PRINTER,
        action="start",
        artifact_sha256=SHA,
    )
    assert used["consumed_at"] is not None
    with pytest.raises(FabricationAuthorityError, match="already been consumed"):
        grants.consume(
            grant["grant_id"],
            project_id=PROJECT,
            mission_id=MISSION,
            operator_id=PRINTER,
            action="start",
            artifact_sha256=SHA,
        )


def test_octoprint_stage_never_selects_or_autostarts_and_start_needs_human_grant(tmp_path):
    printer, grants, transport = _printer(tmp_path, OctoPrintBackend())
    prepared = printer.stage_gcode(filename="field case.gcode", data=GCODE)
    assert prepared.artifact_sha256 == SHA
    assert transport.calls[0] == (
        "upload",
        "/api/files/local",
        "field case.gcode",
        GCODE,
        {"select": "false", "print": "false"},
    )
    with pytest.raises(FabricationAuthorityError):
        printer.start(prepared, project_id=PROJECT, mission_id=MISSION, grant_id="fg-missing")
    assert not any(call[0] == "request" for call in transport.calls)

    grant = _grant(grants)
    run = printer.start(prepared, project_id=PROJECT, mission_id=MISSION, grant_id=grant["grant_id"])
    assert run.artifact_sha256 == SHA
    assert transport.calls[-1] == (
        "request",
        "POST",
        "/api/files/local/field%20case.gcode",
        {"command": "select", "print": True},
    )


def test_octoprint_start_is_bound_to_exact_staged_remote_path(tmp_path):
    printer, grants, transport = _printer(tmp_path, OctoPrintBackend())
    prepared = printer.stage_gcode(filename="approved case.gcode", data=GCODE)
    printer.start(
        prepared,
        project_id=PROJECT,
        mission_id=MISSION,
        grant_id=_grant(grants)["grant_id"],
    )
    start_call = transport.calls[-1]
    assert start_call[2] == "/api/files/local/approved%20case.gcode"
    assert start_call[3] == {"command": "select", "print": True}
    assert not any(
        call[0] == "request" and call[2] == "/api/job" and call[3] == {"command": "start"}
        for call in transport.calls
    )


def test_pause_and_cancel_reduce_risk_without_new_authority_but_resume_needs_a_new_grant(tmp_path):
    printer, grants, transport = _printer(tmp_path, OctoPrintBackend())
    prepared = printer.stage_gcode(filename="case.gcode", data=GCODE)
    run = printer.start(prepared, project_id=PROJECT, mission_id=MISSION, grant_id=_grant(grants)["grant_id"])

    printer.pause(run)
    printer.cancel(run)
    assert ("request", "POST", "/api/job", {"command": "pause", "action": "pause"}) in transport.calls
    assert ("request", "POST", "/api/job", {"command": "cancel"}) in transport.calls

    start_grant = _grant(grants)
    with pytest.raises(FabricationAuthorityError, match="action"):
        printer.resume(run, grant_id=start_grant["grant_id"])
    resume_grant = _grant(grants, action="resume")
    printer.resume(run, grant_id=resume_grant["grant_id"])
    assert transport.calls[-1] == ("request", "POST", "/api/job", {"command": "pause", "action": "resume"})


def test_grant_is_spent_before_an_ambiguous_start_failure(tmp_path):
    printer, grants, _transport = _printer(tmp_path, OctoPrintBackend(), fail_start=True)
    prepared = printer.stage_gcode(filename="case.gcode", data=GCODE)
    grant = _grant(grants)
    with pytest.raises(ConnectionError, match="ambiguous"):
        printer.start(prepared, project_id=PROJECT, mission_id=MISSION, grant_id=grant["grant_id"])
    assert grants.get(grant["grant_id"])["consumed_at"] is not None
    with pytest.raises(FabricationAuthorityError, match="already been consumed"):
        printer.start(prepared, project_id=PROJECT, mission_id=MISSION, grant_id=grant["grant_id"])


def test_moonraker_stages_without_print_and_binds_start_to_staged_path(tmp_path):
    printer, grants, transport = _printer(tmp_path, MoonrakerBackend())
    prepared = printer.stage_gcode(filename="field case.gcode", data=GCODE)
    assert prepared.remote_path == "jobs/field case.gcode"
    assert transport.calls[0] == (
        "upload",
        "/server/files/upload",
        "field case.gcode",
        GCODE,
        {"root": "gcodes", "path": "", "print": "false"},
    )
    printer.start(prepared, project_id=PROJECT, mission_id=MISSION, grant_id=_grant(grants)["grant_id"])
    assert transport.calls[-1] == (
        "request",
        "POST",
        "/printer/print/start?filename=jobs/field%20case.gcode",
        None,
    )


def test_status_is_observation_only_and_never_claims_physical_correctness(tmp_path):
    printer, _grants, transport = _printer(tmp_path, MoonrakerBackend())
    observation = printer.status()
    assert observation["physical_correctness"] == "UNPROVEN"
    assert observation["schema"] == "hardware_splicer.printer_observation.v1"
    assert transport.calls[-1] == (
        "request",
        "GET",
        "/printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed",
        None,
    )


def test_http_transport_is_live_capable_but_mocked_in_tests(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers.get("X-Api-Key") == "test-only-key"
        if request.url.path == "/api/files/local":
            return httpx.Response(200, json={"files": {"local": {"path": "case.gcode"}}})
        if request.url.path == "/api/job":
            return httpx.Response(200, json={"state": "Operational"})
        if request.url.path == "/api/printer":
            return httpx.Response(200, json={"state": {"text": "Operational"}})
        return httpx.Response(404, json={"error": "unexpected test path"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpxPrinterTransport(
        "http://printer.test",
        headers={"X-Api-Key": "test-only-key"},
        client=client,
    )
    grants = FabricationGrantStore(tmp_path / "grants")
    printer = FabricationPrinter(
        printer_id=PRINTER,
        backend=OctoPrintBackend(),
        transport=transport,
        grants=grants,
    )
    prepared = printer.stage_gcode(filename="case.gcode", data=GCODE)
    assert prepared.remote_path == "case.gcode"
    assert printer.status()["physical_correctness"] == "UNPROVEN"
    assert [request.url.path for request in seen] == ["/api/files/local", "/api/job", "/api/printer"]
    client.close()


def test_http_transport_refuses_endpoint_credentials_and_query():
    for bad in ("printer.local", "http://user:pass@printer.local", "http://printer.local/?token=x"):
        with pytest.raises(FabricationValidationError, match="base_url"):
            HttpxPrinterTransport(bad)
