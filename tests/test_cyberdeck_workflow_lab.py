"""HS measured real SSH browser workflow must never authorize hypothetical hardware."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from hardware_splicer.cyberdeck_workflow_acceptance import evaluate

ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/"examples/cyberdeck/workflow_lab"
BENCH=json.loads((LAB/"evidence/bench_results.json").read_text())
PRIOR=json.loads((ROOT/"examples/cyberdeck/electrical_feasibility/report.json").read_text())
SCREEN=(LAB/"evidence/touch_ssh_bench.png").read_bytes()
ACCEPTED=json.loads((LAB/"evidence/hs_workflow_acceptance.json").read_text())


def _run(b=None,p=None,screen=None):
    return evaluate(BENCH if b is None else b,
                    PRIOR if p is None else p,
                    SCREEN if screen is None else screen)


def test_real_runtime_receipt_replays_into_canonical_machine_project():
    result=_run()
    assert {k:v for k,v in ACCEPTED.items() if k!="provenance"}==result
    receipt=ACCEPTED["provenance"]
    assert receipt["benchmark_sha256"]==hashlib.sha256(
        (LAB/"evidence/bench_results.json").read_bytes()).hexdigest()
    assert receipt["prior_HS_electrical_sha256"]==hashlib.sha256(
        (ROOT/"examples/cyberdeck/electrical_feasibility/report.json").read_bytes()).hexdigest()
    assert receipt["browser_screenshot_sha256"]==hashlib.sha256(SCREEN).hexdigest()
    assert result["status"]=="SOFTWARE_INTERACTION_BENCH_ACCEPTED_PHYSICAL_BUILD_BLOCKED"


def test_real_touch_to_ssh_functionality_is_measured_not_mock_terminal():
    r=_run()
    w=BENCH["workflow"]
    assert r["real_software_requirements_passed"]==[
        "r-real-ssh","r-touch","r-editor","r-multiplexer","r-reconnect",
    ]
    assert len(r["real_software_requirements_passed"])==5
    assert r["loopback_echo_median_ms"]==15.8
    assert w["virtual_key_touches"]==27
    assert w["nano_arrow_insertion_file"]=="axbc"
    assert w["tmux_started_and_ctrl_b_d_detached"]
    assert w["ctrl_c_interrupts_running_command"]
    assert w["same_sandbox_workspace_file_survives_new_ssh_connection"]
    assert not w["same_tmux_server_survives_reconnect"]
    assert SCREEN[:8]==b"\x89PNG\r\n\x1a\n"


def test_hs_machine_project_never_promotes_physical_product():
    r=_run()
    assert not r["pocket_hardware_verified"]
    assert not r["fabrication_authorized"]
    assert not r["procurement_authorized"]
    assert r["physical_panel_and_power_requirements_passed"]==[]
    assert r["release_assessment"]["blockers"]
    assert r["machine_project"]["metadata"]["actual_hardware_fabricated"] is False
    assert r["machine_project"]["metadata"]["commercialization_required"] is False
    evidence={e["evidence_id"]:e for e in r["machine_project"]["evidence"]}
    assert evidence["real-loopback"]["authority"]=="measured"
    assert not evidence["real-loopback"]["simulated"]
    assert evidence["browser-screenshot"]["metadata"]["screens_are_browser_areas_not_physical_panels"]
    assert evidence["prior-packaging"]["simulated"]
    req_status={v["verification_id"]:v["status"]
                for v in r["machine_project"]["verifications"]}
    assert req_status["v-native-dual-dsi"]=="blocked"
    assert req_status["v-fitting"]=="failed"
    assert req_status["v-cell"]=="planned"
    assert req_status["v-ergonomics"]=="planned"


@pytest.mark.parametrize("k,value",[
    ("actual_physical_cyberdeck_built",True),
    ("actual_CM4_or_DSI_tested",True),
    ("marketing_or_company_required",True),
    ("result","SSH_STUB_PASSED"),
])
def test_fabricated_success_claims_rejected(k,value):
    b=deepcopy(BENCH);b[k]=value
    with pytest.raises(ValueError):_run(b)


@pytest.mark.parametrize("k",[
    "no_token_http_rejected","invalid_token_http_rejected",
    "cross_origin_websocket_rejected","no_token_websocket_rejected",
    "wrong_pinned_host_key_rejected_before_commands",
    "openssh_only_listens_on_loopback",
    "filesystem_home_and_network_namespace_isolated",
])
def test_security_gate_missing_credible_runtime_rejected(k):
    b=deepcopy(BENCH);b["security"][k]=False
    with pytest.raises(ValueError):_run(b)


def test_browser_must_be_real_xterm_over_local_ssh_not_static_strings():
    b=deepcopy(BENCH)
    b["workflow"]["connection_and_command_on_real_sshd"]=False
    with pytest.raises(ValueError,match="faked backend"):_run(b)


@pytest.mark.parametrize("k,v",[
    ("screen_mocked_hardware",False),
    ("network","WAN over untested carrier"),
    ("virtual_key_touches",2),
    ("same_tmux_server_survives_reconnect",True),
    ("nano_arrow_insertion_file","abc"),
])
def test_scope_must_not_exceed_observed_run(k,v):
    b=deepcopy(BENCH);b["workflow"][k]=v
    with pytest.raises(ValueError):_run(b)


def test_screen_evidence_pixels_match_browser_viewport():
    _run()
    with pytest.raises(ValueError,match="valid PNG"):_run(screen=b"not_a_screenshot")
    with pytest.raises(ValueError,match="match measured browser geometry"):
        fake=bytearray(SCREEN)
        fake[16:24]=b"\x00\x00\x02\x00\x00\x00\x02\x00"
        _run(screen=bytes(fake))


def test_no_unrealistic_wifi_latency_promotion():
    b=deepcopy(BENCH)
    b["workflow"]["input_output_loopback_ms"]["interpretation"]="real CM4 wireless p95"
    with pytest.raises(ValueError,match="WiFi"):_run(b)


def test_prior_physical_FAB_gate_still_blocks():
    p=deepcopy(PRIOR)
    p["release"]["manufacturing_authorized"]=True
    with pytest.raises(ValueError,match="fabrication"):_run(p=p)


def test_npm_renderer_pinned_and_no_rewritten_vt_terminal():
    package=json.loads((LAB/"web/package.json").read_text())
    assert package["dependencies"]=={
        "@xterm/xterm":"6.0.0",
        "@xterm/addon-fit":"0.11.0",
    }
    lock=json.loads((LAB/"web/package-lock.json").read_text())
    assert lock["packages"]["node_modules/@xterm/xterm"]["version"]=="6.0.0"
    assert lock["packages"]["node_modules/@xterm/addon-fit"]["version"]=="0.11.0"
    js=(LAB/"web/app.js").read_text()
    assert "const term = new Terminal(" in js
    assert "new FitAddon.FitAddon()" in js
    assert "window.hsBench" in js
    assert "Ctrl+B" in (LAB/"web/index.html").read_text()
    if subprocess.run(["node","--version"],capture_output=True).returncode==0:
        subprocess.run(["node","--check",str(LAB/"web/app.js")],check=True)


def test_forced_local_sandbox_and_host_key_pinning_are_not_removed():
    fixture=(LAB/"loopback_ssh.py").read_text()
    app=(LAB/"server.py").read_text()
    assert "--unshare-net" in fixture and "--unshare-pid" in fixture
    assert "legacy_tiocsti" in fixture
    assert "StrictHostKeyChecking=yes" in fixture
    assert "UserKnownHostsFile=" in fixture
    assert '"ListenAddress 127.0.0.1"' in fixture
    assert "AuthenticationMethods publickey" in fixture
    assert '"127.0.0.1",port' in app
    assert 'cross-origin websocket forbidden' in app


def test_no_user_tokens_or_keys_are_stored_in_evidence():
    text=json.dumps(BENCH)+"\n"+json.dumps(ACCEPTED)
    assert "PRIVATE KEY" not in text
    assert "identity.pub" not in text
    assert "?token=" not in text
    assert "spectating101@" not in text.lower()
