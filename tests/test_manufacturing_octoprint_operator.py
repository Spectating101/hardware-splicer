"""Offline mock-device tests for first HS manufacturing operator adapter."""
import hashlib
import httpx
import pytest

from hardware_splicer.manufacturing_operator.octoprint import (
    ManufacturingRefusal, OctoPrintOperator, validate_local_printer_url,
)

URL = "http://192.168.50.8:5000"


def _make_client(handler, *, upload=False, reviewed=False):
    return OctoPrintOperator(
        base_url=URL, api_key="TEST_ONLY",
        transport=httpx.MockTransport(handler),
        upload_enabled_by_local_operator=upload,
        auto_start_plugins_checked=reviewed,
    )


def _ready(request):
    if request.url.path == "/api/printer":
        return httpx.Response(200, json={
            "state": {"text": "Operational", "flags": {
                "operational": True, "printing": False,
                "paused": False, "error": False}},
        })
    if request.url.path == "/api/job":
        return httpx.Response(200, json={"state": "Operational", "job": None, "progress": None})
    raise AssertionError("Unexpected printer operation: " + str(request.url))


def test_local_url_only():
    assert validate_local_printer_url(URL) == URL
    assert validate_local_printer_url("http://localhost:5000") == "http://localhost:5000"
    for invalid in ("https://public.example", "http://8.8.8.8:5000",
                    "http://bad.example", "http://user:password@192.168.1.3",
                    "http://192.168.1.3/api/job"):
        with pytest.raises(ManufacturingRefusal):
            validate_local_printer_url(invalid)


def test_read_only_status_and_job_never_operate_machine():
    seen = []
    def handler(req):
        seen.append((req.method, req.url.path))
        return _ready(req)
    with _make_client(handler) as device:
        assert device.printer_status()["state"]["text"] == "Operational"
        assert device.current_job()["state"] == "Operational"
    assert seen == [("GET", "/api/printer"), ("GET", "/api/job")]


def test_upload_disabled_without_local_operator_review(tmp_path):
    file = tmp_path / "sample.gcode"
    file.write_text("; mock only\nG1 X1\n")
    with _make_client(lambda r: (_ for _ in ()).throw(AssertionError("Network called"))) as device:
        with pytest.raises(ManufacturingRefusal, match="Local operator"):
            device.stage_gcode(file)


def test_upload_opted_in_never_sends_start_command(tmp_path):
    source = tmp_path / "test.gcode"
    content = b"; offline mock print\nG1 X5 Y5\n"
    source.write_bytes(content)
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/printer":
            return _ready(request)
        assert request.url.path == "/api/files/local"
        assert request.method == "POST"
        body = request.content
        assert b'name="print"' in body and b"false" in body
        assert b'name="select"' in body
        assert content in body
        return httpx.Response(201, json={"files": {"local": {"name": "test.gcode"}}})
    with _make_client(handler, upload=True, reviewed=True) as device:
        receipt = device.stage_gcode(source)
    assert receipt.gcode_sha256 == hashlib.sha256(content).hexdigest()
    assert receipt.staged_only
    assert not receipt.start_requested
    assert not receipt.human_start_approval_obtained
    assert not receipt.fabricated_object_verified
    assert seen == [("GET", "/api/printer"), ("POST", "/api/files/local")]


def test_busy_printer_refuses_upload(tmp_path):
    source = tmp_path / "test.gcode"
    source.write_text("G1 X1\n")
    def handler(request):
        assert request.method == "GET"  # never upload when busy
        return httpx.Response(200, json={"state": {"text": "Printing", "flags": {
            "operational": True, "printing": True}}})
    with _make_client(handler, upload=True, reviewed=True) as device:
        with pytest.raises(ManufacturingRefusal, match="not idle"):
            device.stage_gcode(source)


def test_bad_files_blocked(tmp_path):
    source = tmp_path / "design.stl"
    source.write_text("solid empty\nendsolid empty\n")
    with _make_client(_ready, upload=True, reviewed=True) as device:
        with pytest.raises(ManufacturingRefusal, match="pre-sliced"):
            device.stage_gcode(source)


def test_upload_http_failure_is_not_success(tmp_path):
    source = tmp_path / "test.gcode"
    source.write_text("G1 X1\n")
    def handler(req):
        if req.method == "GET":
            return _ready(req)
        return httpx.Response(409)
    with _make_client(handler, upload=True, reviewed=True) as device:
        with pytest.raises(ManufacturingRefusal, match="HTTP 409"):
            device.stage_gcode(source)
