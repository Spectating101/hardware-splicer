"""The plain-language page runs the retained adapter, never a pretend JS solver."""
import hashlib
import importlib.util
import json
from pathlib import Path
import threading

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/demo_mouse_reuse.py"
spec = importlib.util.spec_from_file_location("mouse_demo", SCRIPT)
demo_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo_module)


@pytest.fixture
def demo():
    return demo_module.MouseDemo()


@pytest.fixture
def server(demo):
    server = demo_module.make_server(demo=demo)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def event(demo, kind, device=None):
    return {"type": kind, "device": device or demo.binding["device_alias"],
            **({"button": demo.binding["button"]} if kind in {"pressed", "released"} else {})}


def test_frozen_agent_plan_and_program_are_disclosed_not_claimed_as_a_live_agent(demo):
    assert demo.story["live_model"] is False
    assert demo.story["physical_specimen"] is False
    assert set(demo.story["recorded_candidate_ids"]) == {"intact_pedal", "remote_contact"}
    assert hashlib.sha256(demo.bundle).hexdigest() == demo_module.PACKAGE_SHA256
    assert b"not a new AI conversation" in demo.page
    assert b"no physical mouse or foot pedal" in demo.page


def test_demo_runs_actual_delivered_python_for_press_hold_other_mouse_and_reconnect(demo):
    rows = [event(demo, kind) for kind in ["connected", "released", "pressed", "pressed"]]
    result = demo.replay({"events": rows})
    assert result["actions_triggered"] == 1 and result["state"] == "wait_release"
    rows += [event(demo, "pressed", "another_mouse"), event(demo, "released", "another_mouse")]
    assert demo.replay({"events": rows})["actions_triggered"] == 1
    rows += [event(demo, kind) for kind in ["released", "pressed", "released"]]
    assert demo.replay({"events": rows})["actions_triggered"] == 2
    rows += [event(demo, kind) for kind in ["disconnected", "connected", "pressed"]]
    assert demo.replay({"events": rows})["actions_triggered"] == 2
    rows += [event(demo, kind) for kind in ["released", "pressed"]]
    assert demo.replay({"events": rows})["actions_triggered"] == 3
    assert demo.replay({"events": []})["actions_triggered"] == 0  # per-tab/reset state, no hidden shared session


@pytest.mark.parametrize("payload", [{}, {"events": "press"}, {"events": [None]}, {"events": [{"type": [], "device": "mouse"}]}, {"events": [{}]}, {"events": [{}]*513}])
def test_bad_replays_are_bounded(demo, payload):
    with pytest.raises((ValueError, TypeError)):
        demo.replay(payload)


def test_http_page_to_actual_program_and_download(server, demo):
    url = f"http://127.0.0.1:{server.server_port}"
    with httpx.Client(base_url=url, trust_env=False) as client:
        page = client.get("/")
        assert page.status_code == 200 and "One press should mean one action" in page.text
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
        story = client.get("/story").json()
        assert story["live_model"] is False
        replay = client.post("/try", json={"events": [event(demo, kind) for kind in ["connected", "released", "pressed"]]}, headers={"Origin": url})
        assert replay.status_code == 200
        assert replay.json()["actions_triggered"] == 1
        assert replay.json()["physical_device_used"] is False
        assert client.get("/bundle.zip").content == demo.bundle
        assert client.post("/try", json={"events": []}, headers={"Origin": "https://unrelated.example"}).status_code == 403
        assert client.get("/", headers={"Host": "unrelated.example"}).status_code == 403
        assert client.get("/../../CLAUDE.md").status_code == 404
        assert client.post("/try", content="not-json", headers={"Content-Type": "application/json"}).status_code == 400
        assert client.post("/try", content="x"*65537, headers={"Content-Type": "application/json"}).status_code == 413


def test_unexpected_program_bytes_are_never_executed(monkeypatch):
    actual_read = Path.read_bytes
    def tampered(path):
        return b"untrusted bytes" if path.name == "intact-input-review.zip" else actual_read(path)
    monkeypatch.setattr(Path, "read_bytes", tampered)
    with pytest.raises(ValueError, match="expected hash"):
        demo_module.MouseDemo()
