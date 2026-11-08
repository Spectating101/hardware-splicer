"""Integrated HS two independent display surfaces: measured vs imagined authority."""
from __future__ import annotations
import json
from pathlib import Path
import re,sys,struct

import pytest

ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/"examples/cyberdeck/integrated_bench"
sys.path.insert(0,str(LAB))
from first_boot_probe import collect
from hardware_splicer.cyberdeck_integrated_prototype_gate import evaluate,run

RESULT=json.loads((LAB/"evidence/dual_surface_integration.json").read_text())
HARDWARE=json.loads((LAB/"evidence/optiplex_first_boot_probe.json").read_text())
CONTRACT=json.loads((LAB/"bench_contract.json").read_text())


def test_two_separate_real_chrome_surfaces_reach_a_real_loopback_ssh_shell():
    assert RESULT["schema"]=="hs.two_independent_surface_local_ssh_integration.v1"
    assert RESULT["result"]=="TWO_SEPARATE_BROWSER_SURFACES_TO_REAL_OPENSSH_PASSED"
    b=RESULT["browser"]
    assert b["two_separate_720x1280_browser_pages"]
    assert b["two_distinct_websockets"]
    assert b["lower_touch_events"]>=20
    assert b["real_nano_file"]=="hs dual"
    assert b["tmux_detach"]
    assert b["symbol_layer_to_real_shell"]
    assert b["upper_cells"]["cols"]>=40 and b["upper_cells"]["rows"]>=30
    assert b["upper_output_bytes"]>300
    assert b["terminal_has_no_input_API"] and b["keyboard_has_no_output_API"]
    assert b["javascript_errors"]==[]


def test_two_actual_browser_png_files_are_not_fake_device_photos():
    for stem in ("upper_terminal_720x1280","lower_keyboard_720x1280"):
        img=(LAB/"evidence"/(stem+".png")).read_bytes()
        assert img[:8]==b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II",img[16:24])==(720,1280)
        assert len(img)>10000
    assert not RESULT["actual_CM5_tested"]
    assert not RESULT["actual_DSI_pair_tested"]
    assert not RESULT["battery_power_applied"]
    assert not RESULT["fabrication_authorized"]


def test_browser_process_roles_enforced_by_server_not_merely_Javascript():
    data=(LAB/"dual_panel_server.py").read_text()
    assert "def terminal(self,req:" in data
    assert "def keyboard(self,req:" in data
    assert "terminal_input_forbidden_use_keyboard" in data
    assert "keyboard_cannot_resize_or_read_output" in data
    assert "keyboard display must connect first" not in data
    assert "terminal display must connect first" in data
    assert "send_bytes(data)" in data
    assert "self.session.write(value)" in data
    assert "one independent input surface only" in data
    assert "one trusted terminal process only" in data
    # The live test rejects actual unauthorized network connections.
    assert all(RESULT["security"].values())


def test_cm5_reference_carrier_contract_is_real_not_a_safe_custom_PCB():
    b=CONTRACT["bench"]
    assert b["official_carrier"]=="Raspberry Pi Compute Module 5 IO Board"
    assert b["board_dimensions_mm"]==[160,90]
    assert b["power"]=="regulated vendor-qualified USB-C 5V 5A PSU for CM5 IO, NOT direct LiPo"
    assert b["display"]["quantity"]==2
    assert b["display"]["px"]==[720,1280]
    assert b["display"]["simultaneous_pair_not_proven"]
    assert b["display"]["max_front_face_mm"]==[70.7,126.9]
    assert b["display"]["full_vendor_step_depth_mm"]==13.608
    assert len(b["mipi_connectors"])==2
    assert all(c["pins"]==22 for c in b["mipi_connectors"])
    assert "J6" in b["i2c_jumper_notice"]
    assert "dtoverlay=" in b["display"]["dsi0_single_test_overlay"]
    assert "dtoverlay=" in b["display"]["dsi1_single_test_overlay"]
    assert b["board_mechanical_status"]=="OUTSIDE handheld target; separate desk bench fixture"


def test_rig_host_is_x86_and_no_CM5_physical_test_is_claimed():
    # Saved actual Optiplex read-only probe, not an invented positive trace.
    assert HARDWARE["schema"]=="hs.cm5_two_DSI_first_boot_probe.v1"
    assert HARDWARE["source"]=="read_only_actual_Linux_sysfs_and_procfs"
    assert not HARDWARE["cm5_identified_from_device_tree"]
    assert not HARDWARE["drm_two_DSI_ports_with_720x1280"]
    assert not HARDWARE["has_two_distinct_touch_like_handlers"]
    assert "host_is_not_Raspberry_Pi_Compute_Module_5" in HARDWARE["blockers"]
    assert HARDWARE["ready_for_handheld_fabrication"] is False
    assert HARDWARE["mobile_battery_pack_safe"] is False
    assert HARDWARE["no_dsi_or_touch_emulation_substituted"] is True
    assert not any(CONTRACT["unverified_and_blocking"].values())


def test_live_probe_same_machine_no_autopromotion():
    probe=collect()
    assert probe["cm5_identified_from_device_tree"] is False
    assert probe["ready_for_handheld_fabrication"] is False
    assert probe["mobile_battery_pack_safe"] is False
    assert "physical_touch_coordinate_mapping_requires_manual_per_panel_test" in probe["blockers"]


def test_even_ideal_two_DSI_touch_mock_probe_never_auto_certifies_product(tmp_path):
    # Synthetic TEST fixture is not evidence of actual hardware on host.
    (tmp_path/"proc/device-tree").mkdir(parents=True)
    (tmp_path/"proc/device-tree/model").write_text("Raspberry Pi Compute Module 5 Rev 1.0")
    (tmp_path/"proc/bus/input").mkdir(parents=True)
    (tmp_path/"proc/bus/input/devices").write_text(
        'N: Name="Goodix Capacitive Touchscreen A"\nH: Handlers=event3 mouse0\n\n'
        'N: Name="Goodix Capacitive Touchscreen B"\nH: Handlers=event4 mouse1\n')
    for i in (0,1):
        d=tmp_path/"sys/class/drm"/f"card0-DSI-{i+1}"
        d.mkdir(parents=True)
        (d/"status").write_text("connected")
        (d/"modes").write_text("720x1280\n")
    p=collect(tmp_path/"sys",tmp_path/"proc")
    assert p["ready_for_manual_powered_display_validation"] is True
    assert p["ready_for_handheld_fabrication"] is False
    assert p["tested_each_touch_coordinate_input"] is False
    assert p["tested_CM5_compile_thermal_and_power"] is False
    assert p["mobile_battery_pack_safe"] is False


def test_no_automatic_config_mutation_or_unsafe_power_actions():
    code=(LAB/"first_boot_probe.py").read_text()
    assert "read_only_actual_Linux_sysfs_and_procfs" in code
    assert "subprocess.run" not in code
    assert "i2cdetect" not in code
    assert "/boot/firmware/config.txt" not in code
    assert all(v is False for v in CONTRACT["release"].values())


def test_canonical_HS_build_release_keeps_measured_software_distinct_from_hardware():
    upper=(LAB/"evidence/upper_terminal_720x1280.png").read_bytes()
    lower=(LAB/"evidence/lower_keyboard_720x1280.png").read_bytes()
    r=evaluate(RESULT,HARDWARE,CONTRACT,upper,lower)
    from_file=json.loads((LAB/"evidence/hs_integrated_gate.json").read_text())
    assert {k:v for k,v in from_file.items() if k!="provenance_sha256"}==r
    assert r["status"]=="DUAL_INDEPENDENT_SOFTWARE_SURFACES_PASS_CM5_HARDWARE_GATE_BLOCKED"
    assert r["verified_real_software_requirements"]==[
        "r-separate-surfaces","r-real-terminal","r-actual-editing",
        "r-tmux-controls","r-local-security"]
    assert r["release_assessment"]["blockers"]
    assert not r["hardware_fabrication_authorized"]
    assert not r["battery_wiring_authorized"]
    assert not r["connected_cm5_detected"]
    assert r["machine_project"]["metadata"]["software_BENCH_not_physical_product"]
    v={x["verification_id"]:x["status"] for x in r["machine_project"]["verifications"]}
    assert v["v-dual-720x1280-DSI"]=="blocked"
    assert v["v-hinge-screen"]=="failed"
    assert v["v-power"]=="planned"


def test_CI_replay_has_no_file_non_determinism(tmp_path):
    r=run(LAB,tmp_path/"report.json")
    assert r==json.loads((LAB/"evidence/hs_integrated_gate.json").read_text())
    assert (tmp_path/"report.json").read_bytes()==(
        LAB/"evidence/hs_integrated_gate.json").read_bytes()


def test_software_success_cannot_be_false_promoted_to_real_CM5():
    from copy import deepcopy
    sample=deepcopy(RESULT)
    sample["actual_CM5_tested"]=True
    with pytest.raises(ValueError,match="promoted"):
        evaluate(sample,HARDWARE,CONTRACT,b"",b"")
    sample=deepcopy(HARDWARE)
    sample["cm5_identified_from_device_tree"]=True
    upper=(LAB/"evidence/upper_terminal_720x1280.png").read_bytes()
    lower=(LAB/"evidence/lower_keyboard_720x1280.png").read_bytes()
    with pytest.raises(ValueError,match="does NOT contain"):
        evaluate(RESULT,sample,CONTRACT,upper,lower)


def test_CI_replay_refuses_missing_either_actual_browser_surface():
    upper=(LAB/"evidence/upper_terminal_720x1280.png").read_bytes()
    lower=(LAB/"evidence/lower_keyboard_720x1280.png").read_bytes()
    with pytest.raises(ValueError,match="screenshot"):
        evaluate(RESULT,HARDWARE,CONTRACT,upper,b"")
    with pytest.raises(ValueError,match="screenshot"):
        evaluate(RESULT,HARDWARE,CONTRACT,b"",lower)


def test_kernel_truth_no_user_cost_or_shell_fabrication_assumed():
    a=CONTRACT
    assert a["user_intent"]["local_linux_programming"]
    assert a["user_intent"]["physical_keyboard"] is False
    assert a["user_intent"]["commercial_launch"] is False
    assert a["bench"]["display"]["simultaneous_pair_not_proven"] is True
    assert a["bench"]["bench_price_status"].startswith("not ordered")
    assert set(a["release"].values())=={False}
