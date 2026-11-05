from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


cf = _load("hs_pc_casefile", "casefile.py")
bc = _load("hs_pc_bench_collect", "bench_collect.py")

REAL_NVME = json.loads((ROOT / "fixtures/smart_nvme_control_healthy_redacted.json").read_text())
REAL_NVME_HOT = json.loads((ROOT / "control_host_optiplex/bundle/smart_nvme0n1.json").read_text())
REAL_ATA = json.loads((ROOT / "fixtures/smart_ata_usb_hdd_control_redacted.json").read_text())

DMI = """# dmidecode 3.6
Handle 0x0001, DMI type 1, 27 bytes
System Information
\tManufacturer: Dell Inc.
\tProduct Name: OptiPlex 7060
\tVersion: Not Specified

Handle 0x0004, DMI type 4, 48 bytes
Processor Information
\tVersion: Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz

Handle 0x1100, DMI type 17, 40 bytes
Memory Device
\tSize: 8 GB
\tType: DDR4
\tSpeed: 2666 MT/s
\tLocator: DIMM1

Handle 0x1101, DMI type 17, 40 bytes
Memory Device
\tSize: No Module Installed
"""
CPUINFO = "processor\t: 0\nmodel name\t: Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz\nprocessor\t: 1\n"
LSBLK = {"blockdevices": [{"name": "sda", "type": "disk", "size": 256060514304, "tran": "sata"},
                          {"name": "sdb", "type": "disk", "size": 16000000000, "tran": "usb"}]}
IP_OK = [{"ifname": "lo", "operstate": "UNKNOWN", "addr_info": [{"family": "inet"}]},
         {"ifname": "enp0s31f6", "operstate": "UP", "addr_info": [{"family": "inet"}]}]
THERMAL_OK = {"hs_status": "ran", "requested_seconds": 1200, "rc": 0, "wall_seconds": 1203.0,
              "samples": [{"t": 0, "temps_c": {"coretemp/temp1": 40.0}}, {"t": 5, "temps_c": {"coretemp/temp1": 78.0}}],
              "throttle_before": {"cpu0/core_throttle_count": 0}, "throttle_after": {"cpu0/core_throttle_count": 0}}
MEM_OK = {"hs_status": "ran", "tested_mb": 7000, "loops": 2, "rc": 0, "total_mb": 7900, "avail_mb_before": 7800}


def sata_ssd(**over):
    j = copy.deepcopy(REAL_NVME)
    j.pop("nvme_smart_health_information_log")
    j["ata_smart_attributes"] = {"table": [{"id": i, "name": str(i), "raw": {"value": 0}} for i in (5, 187, 188, 197, 198, 199)]}
    j["smartctl"]["exit_status"] = 0
    j["smart_status"] = {"passed": True}
    j.update(over)
    return j


def make_bundle(d: Path, *, role="target", memory=MEM_OK, thermal=THERMAL_OK, smart=None, dmi=DMI, ip=IP_OK,
                dmesg="", extra=None) -> Path:
    b = bc.Bundle(d, redact=False)
    b.text("dmidecode.txt", dmi)
    b.text("cpuinfo.txt", CPUINFO)
    b.text("meminfo.txt", "MemTotal:        8064000 kB\nMemAvailable:    7900000 kB\n")
    b.js("lsblk.json", LSBLK)
    b.text("dmesg_err.txt", dmesg)
    b.js("smart_sda.json", smart if smart is not None else sata_ssd())
    b.js("memtester.meta.json", memory)
    if memory.get("hs_status") == "ran":
        b.text("memtester.txt", "Loop 1/2:\n  Stuck Address       : ok\nDone.\n")
    b.js("thermal.json", thermal)
    b.js("ip_addr.json", ip)
    for k, v in (extra or {}).items():
        b.text(k, v)
    b.finish({"role": role, "mode": "bench", "host_fingerprint": "abc123"})
    return d


def make_wipe(d: Path, size=256060514304, **over) -> Path:
    b = bc.Bundle(d, redact=False)
    w = {"device": "/dev/sda", "size_bytes": size, "signatures_stdout": "", "signature_tool": "ok", "sampled_blocks": 130,
         "zero_blocks": 130, "min_entropy_bits_per_byte": 0.0, "operator_declared_method": "nvme/ATA secure erase"}
    w.update(over)
    b.js("wipe_sda.json", w)
    b.finish({"role": "target", "mode": "verify_wipe"})
    return d


CHECK = {k: {"pass": True, "note": "ok"} for k in cf.REQUIRED_CHECKLIST}


def make_unit(tmp: Path, *, role="target", acquired=True, claimed=None, wipe=True, rights=True, bundle_kw=None,
              review=None, legal=None, checklist=CHECK, licence=None):
    make_bundle(tmp / "bundle", role=role, **(bundle_kw or {}))
    unit = {"unit_id": "u1", "lot_id": "lot1", "role": role, "acquired": acquired, "bundles": {"bench": "bundle"},
            "operator": {"name": "operator-a"}, "operator_checklist": checklist,
            "licence": licence or {"os_to_ship": "linux"}}
    if claimed:
        unit["claimed"] = claimed
    if wipe:
        make_wipe(tmp / "wipe")
        unit["bundles"]["wipe"] = ["wipe"]
    if rights:
        unit["rights"] = {}
        for k in cf.REQUIRED_RIGHTS:
            (tmp / f"{k}.txt").write_text("signed receipt scan placeholder")
            unit["rights"][k] = {"evidence": f"{k}.txt"}
    if review:
        unit["review"] = review
    if legal:
        unit["owner_legal_confirmations"] = legal
    (tmp / "unit.json").write_text(json.dumps(unit))
    return tmp / "unit.json"


def sub(tmp: Path, name: str) -> Path:
    d = tmp / name
    d.mkdir()
    return d


def gates(rep):
    return {g["gate"]: g for g in rep["gates"]}


ALL_LEGAL = {k: True for k in cf.OWNER_LEGAL_ITEMS}


# ------------------------------------------------------------- real-format parsers
def test_real_nvme_smart_parses_as_pass():
    st, detail, facts = cf.eval_smart(REAL_NVME)
    assert st == "pass", detail
    assert facts["media_errors"] == 0 and facts["power_on_hours"] and facts["power_on_hours"] < 200000


def test_real_hot_nvme_capture_is_retest_not_fail_and_not_pass():
    # Real capture: same drive at 82 C (its warning threshold) with critical_warning=2. smartctl itself says
    # "FAILED" and exit_status 8; that is a thermal flag, so the gate must say unknown (blocks release), never pass.
    h = REAL_NVME_HOT["nvme_smart_health_information_log"]
    assert h["critical_warning"] == 2 and REAL_NVME_HOT["smart_status"]["passed"] is False
    st, detail, facts = cf.eval_smart(REAL_NVME_HOT)
    assert st == "unknown" and "temperature flag" in detail and "cool" in detail
    assert facts["temperature"] == 82 and facts["critical_comp_time"] > 0


def test_temperature_flag_cannot_mask_a_real_nvme_fault():
    for extra in ({"media_errors": 2}, {"percentage_used": 97}, {"available_spare": 3}):
        j = copy.deepcopy(REAL_NVME_HOT)
        j["nvme_smart_health_information_log"].update(extra)
        assert cf.eval_smart(j)[0] == "fail", extra
    j = copy.deepcopy(REAL_NVME_HOT)
    j["nvme_smart_health_information_log"]["critical_warning"] = 2 | 4  # temperature + reliability degraded
    assert cf.eval_smart(j)[0] == "fail"


def test_real_ata_power_on_hours_come_from_power_on_time_not_packed_attr9():
    st, detail, facts = cf.eval_smart(REAL_ATA)
    assert st == "pass", detail
    attr9 = next(a for a in REAL_ATA["ata_smart_attributes"]["table"] if a["id"] == 9)["raw"]["value"]
    assert attr9 > 10**12, "fixture should show the packed raw value that must not be used"
    assert facts["power_on_hours"] == REAL_ATA["power_on_time"]["hours"] < 200000


def test_smart_failures_are_failures_and_unreadable_is_unknown():
    bad = sata_ssd()
    bad["ata_smart_attributes"]["table"][0]["raw"]["value"] = 12  # reallocated sectors
    assert cf.eval_smart(bad)[0] == "fail"
    assert cf.eval_smart(sata_ssd(smart_status={"passed": False}))[0] == "fail"
    nv = copy.deepcopy(REAL_NVME)
    nv["nvme_smart_health_information_log"]["media_errors"] = 3
    assert cf.eval_smart(nv)[0] == "fail"
    worn = copy.deepcopy(REAL_NVME)
    worn["nvme_smart_health_information_log"]["percentage_used"] = 95
    assert cf.eval_smart(worn)[0] == "fail"
    assert cf.eval_smart({"hs_status": "tool_missing"})[0] == "unknown"
    cant_read = sata_ssd()
    cant_read["smartctl"]["exit_status"] = 2
    assert cf.eval_smart(cant_read)[0] == "unknown"  # a device we could not read is not a pass
    failing = sata_ssd()
    failing["smartctl"]["exit_status"] = 8
    assert cf.eval_smart(failing)[0] == "fail"


def test_dmi_parser_reads_cpu_and_installed_dimms_only():
    d = cf.parse_dmi(DMI)
    assert d["system"]["Product Name"] == "OptiPlex 7060"
    assert "i5-8500" in d["processors"][0]
    assert [x["size_mb"] for x in d["dimms"]] == [8192, 0]


# ------------------------------------------------------------- authority rules
def test_control_host_bundle_never_releases(tmp_path):
    rep = cf.evaluate(ROOT / "control_host_optiplex/unit.json")
    assert rep["decision"] == "NOT_A_PRODUCT_CONTROL_HOST"
    assert rep["approved_for_sale"] is False
    assert rep["facts"]["excluded_usb_disks"] == 1  # the external USB disk is not treated as product storage
    g = gates(rep)
    assert g["memory_test"]["status"] == "unknown" and g["thermal_stress"]["status"] == "unknown"
    assert g["storage_health:nvme0n1"]["status"] == "unknown"  # the committed real capture is the hot one
    assert "temperature flag" in g["storage_health:nvme0n1"]["detail"]
    assert g["checklist:video_output"]["authority"] == "none"


def test_role_mismatch_between_unit_and_bundle_is_a_failure(tmp_path):
    p = make_unit(tmp_path)
    u = json.loads(p.read_text())
    make_bundle(tmp_path / "bundle", role="control_host")  # a control-host capture presented for a target unit
    rep = cf.evaluate(p)
    assert gates(rep)["bench_role_matches_unit"]["status"] == "fail"
    assert rep["decision"] != "READY_FOR_INDEPENDENT_REVIEW"


def test_not_acquired_unit_is_pre_acquisition_even_if_every_gate_passes(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path, acquired=False))
    assert rep["decision"] == "PRE_ACQUISITION" and rep["approved_for_sale"] is False


def test_all_gates_pass_still_only_ready_for_review_never_approved_alone(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path))
    assert [g["gate"] for g in rep["gates"] if g["status"] not in ("pass", "not_applicable")] == []
    assert rep["decision"] == "READY_FOR_INDEPENDENT_REVIEW" and rep["approved_for_sale"] is False


def test_unknown_is_not_pass_missing_memtest_blocks(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path, bundle_kw={"memory": {"hs_status": "not_run", "total_mb": 7900}}))
    assert gates(rep)["memory_test"]["status"] == "unknown"
    assert rep["decision"] == "BLOCKED_MISSING_EVIDENCE"


def test_short_memtest_is_insufficient_not_pass(tmp_path):
    one_loop = {**MEM_OK, "loops": 1}
    assert gates(cf.evaluate(make_unit(tmp_path, bundle_kw={"memory": one_loop})))["memory_test"]["status"] == "unknown"


def test_memtest_failure_and_thermal_throttle_fail_the_unit(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path, bundle_kw={"memory": {**MEM_OK, "rc": 1}}))
    assert gates(rep)["memory_test"]["status"] == "fail" and rep["decision"] == "REJECT_OR_REPAIR"
    hot = copy.deepcopy(THERMAL_OK)
    hot["throttle_after"] = {"cpu0/core_throttle_count": 7}
    rep = cf.evaluate(make_unit(sub(tmp_path, "x"), bundle_kw={"thermal": hot}))
    assert gates(rep)["thermal_stress"]["status"] == "fail"


def test_short_stress_run_is_unknown(tmp_path):
    short = {**THERMAL_OK, "wall_seconds": 300.0}
    assert gates(cf.evaluate(make_unit(tmp_path, bundle_kw={"thermal": short})))["thermal_stress"]["status"] == "unknown"


def test_fatal_kernel_errors_fail_boot_health(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path, bundle_kw={"dmesg": "blk_update_request: I/O error, dev sda, sector 123\n"}))
    assert gates(rep)["boot_and_kernel_health"]["status"] == "fail"


def test_claim_mismatch_is_a_dispute_not_a_silent_pass(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path, claimed={"cpu": "i7-8700", "ram_gb": 16, "storage_gb": 256}))
    assert gates(rep)["identity_matches_claim"]["status"] == "fail"
    assert rep["decision"] == "DISPUTE_CLAIM_MISMATCH"
    ok = cf.evaluate(make_unit(sub(tmp_path, "ok"),
                               claimed={"cpu": "i5-8500", "ram_gb": 8, "storage_gb": 256}))
    assert gates(ok)["identity_matches_claim"]["status"] == "pass"


def test_missing_rights_evidence_blocks(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path, rights=False))
    assert rep["decision"] == "BLOCKED_MISSING_EVIDENCE"
    assert all(gates(rep)["rights:" + k]["status"] == "unknown" for k in cf.REQUIRED_RIGHTS)


def test_operator_attestation_is_never_labelled_instrument_evidence(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path))
    g = gates(rep)
    for k in cf.REQUIRED_CHECKLIST:
        assert g["checklist:" + k]["authority"] == "operator_attested"
    for k in cf.REQUIRED_RIGHTS:
        assert g["rights:" + k]["authority"] == "operator_attested"
    assert g["memory_test"]["authority"] == "instrument_log"


def test_storage_not_wiped_blocks_and_signatures_fail(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path, wipe=False))
    assert gates(rep)["storage_sanitized:sda"]["status"] == "unknown"
    w = sub(tmp_path, "w")
    make_unit(w)
    make_wipe(w / "wipe", signatures_stdout='{"signatures":[{"type":"ext4"}]}')
    assert gates(cf.evaluate(w / "unit.json"))["storage_sanitized:sda"]["status"] == "fail"


# ------------------------------------------------------------- integrity & review binding
def test_tampering_with_any_bundle_file_is_detected(tmp_path):
    p = make_unit(tmp_path)
    (tmp_path / "bundle" / "smart_sda.json").write_text(json.dumps(sata_ssd(smart_status={"passed": True}), indent=4))
    rep = cf.evaluate(p)
    assert gates(rep)["bench_bundle_integrity"]["status"] == "fail"
    assert rep["decision"] == "REJECT_OR_REPAIR"


def test_unlisted_extra_file_in_bundle_fails_integrity(tmp_path):
    p = make_unit(tmp_path)
    (tmp_path / "bundle" / "extra_pass_log.txt").write_text("trust me")
    assert gates(cf.evaluate(p))["bench_bundle_integrity"]["status"] == "fail"


def _approved(tmp_path, **review_over):
    p = make_unit(tmp_path, legal=ALL_LEGAL)
    man = cf.evaluate(p)["facts"]["bench_manifest_sha256"]
    u = json.loads(p.read_text())
    u["review"] = {"reviewer": "reviewer-b", "covers_manifest_sha256": man, "date": "2026-11-06", **review_over}
    p.write_text(json.dumps(u))
    return p


def test_independent_review_bound_to_manifest_approves(tmp_path):
    rep = cf.evaluate(_approved(tmp_path))
    assert rep["decision"] == "APPROVED_FOR_SALE" and rep["approved_for_sale"] is True


def test_operator_cannot_review_their_own_work(tmp_path):
    rep = cf.evaluate(_approved(tmp_path, reviewer="operator-a"))
    assert rep["approved_for_sale"] is False and "different person" in rep["review_note"]


def test_review_of_a_different_or_stale_bundle_does_not_carry_over(tmp_path):
    rep = cf.evaluate(_approved(tmp_path, covers_manifest_sha256="0" * 64))
    assert rep["approved_for_sale"] is False and "does not cover" in rep["review_note"]


def test_owner_legal_items_gate_release(tmp_path):
    p = _approved(tmp_path)
    u = json.loads(p.read_text())
    u["owner_legal_confirmations"]["second_hand_trade_licence_status_confirmed"] = False
    p.write_text(json.dumps(u))
    rep = cf.evaluate(p)
    assert rep["approved_for_sale"] is False and "second_hand_trade_licence" in rep["review_note"]


def test_windows_needs_a_photographed_coa(tmp_path):
    assert gates(cf.evaluate(make_unit(tmp_path, licence={"os_to_ship": "windows_with_coa"})))["os_licence"]["status"] == "unknown"


def test_partout_candidates_only_come_from_components_that_passed_their_own_gate(tmp_path):
    rep = cf.evaluate(make_unit(tmp_path))
    names = [c["asset_type"] for c in rep["partout_candidates"]]
    assert "ram_module" in names and "storage" in names
    rep = cf.evaluate(make_unit(sub(tmp_path, "f"), bundle_kw={"memory": {**MEM_OK, "rc": 1}}))
    assert "ram_module" not in [c["asset_type"] for c in rep["partout_candidates"]]
