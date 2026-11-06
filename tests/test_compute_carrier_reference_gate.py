"""Evidence integrity tests for HS's compute carrier reuse decision."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import pytest

from hardware_splicer.compute_carrier_reference_gate import assess, CarrierGateError

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"examples/cyberdeck/compute_carrier/evidence/source_contract_20261107.json"
EVIDENCE=json.loads(SOURCE.read_text(encoding="utf-8"))

def change(mutator):
    obj=deepcopy(EVIDENCE)
    mutator(obj)
    return json.dumps(obj).encode()

def test_reference_designs_exist_but_fabrication_is_not_authorized():
    report=assess(SOURCE.read_bytes())
    assert report["source_designs_available"]
    assert report["blocker_count"] >= 15
    assert report["design_authorization"]=="RESEARCH_ONLY"
    assert not report["safe_to_fabricate"]
    assert not report["operationally_verified"]
    assert not report["compatible_compute_socket_claim"]
    assert not report["safe_to_power_any_cross_module_swap"]

def test_clone_upstream_pinout_and_power_blobs_are_quarantined():
    r=assess(SOURCE.read_bytes())
    codes={x["code"] for x in r["blockers"]}
    assert "identical_upstream_pinout_blobs" in codes
    assert "identical_upstream_power_blobs" in codes
    assert not r["upstream_db_trusted_for_pinout"]

def test_official_rk3576_conflicts_with_agent_data_rk3676_typo():
    r=assess(SOURCE.read_bytes())
    assert any(x["code"]=="upstream_soc_metadata_conflict" and x["scope"]=="radxa_cm4_rk3576" for x in r["blockers"])

def test_critical_5v_to_gpio_warning_cannot_be_deleted():
    def mutate(x):
        x["source_known_hazards"]=[v for v in x["source_known_hazards"] if v["id"]!="radxa_cm3_to_cm5_5v_gpio"]
    with pytest.raises(CarrierGateError,match="exceptions"):
        assess(change(mutate))

def test_critical_5v_to_gpio_pin_mapping_cannot_be_sanitized():
    def mutate(x):
        x["source_known_hazards"][0]["pins"]=[94,96]
    with pytest.raises(CarrierGateError,match="5V-to-GPIO"):
        assess(change(mutate))

def test_same_form_factor_cannot_be_promoted_to_direct_module_swap():
    def mutate(x):
        for m in x["modules"][:2]:
            m["revision_and_mechanical_fit_validated_by_hs"]=True
    r=assess(change(mutate))
    assert not r["compatible_compute_socket_claim"]
    assert not r["safe_to_power_any_cross_module_swap"]
    assert any(b["code"]=="direct_socket_swap_not_proven" for b in r["blockers"])

def test_unknown_power_and_pinout_remain_release_blockers():
    r=assess(SOURCE.read_bytes())
    codes=[x["code"] for x in r["blockers"]]
    assert codes.count("upstream_missing_voltage_limits")==2
    assert codes.count("upstream_placeholder_pin_map")==2
    assert codes.count("pinout_not_approved")==2
    assert codes.count("power_not_characterized")==2

def test_private_phone_board_cannot_claim_official_vendor_carrier():
    def mutate(x):
        x["modules"][2]["official_carrier_design"]="https://github.com/some-guess"
    with pytest.raises(CarrierGateError,match="proprietary"):
        assess(change(mutate))

def test_independent_physical_adapters_nonoptional():
    def mutate(x):
        x["device_contract"]["independent_module_adapters_required"]=False
    with pytest.raises(CarrierGateError,match="distinct"):
        assess(change(mutate))

def test_architecture_contract_is_not_kicad_pins():
    def mutate(x):
        x["device_contract"]["interface_scope"]="PHYSICAL_PINOUT_VERIFIED"
    with pytest.raises(CarrierGateError,match="logical services"):
        assess(change(mutate))

def test_no_missing_subsystems_can_be_hidden():
    def mutate(x):
        x["device_contract"]["functions"].pop()
    with pytest.raises(CarrierGateError,match="incomplete"):
        assess(change(mutate))

def test_mysteriously_recorded_erc_drc_never_trumps_missing_pin_map():
    def mutate(x):
        x["independent_erc_pass"]=True
        x["independent_drc_pass"]=True
        x["active_cad_outputs"]=100
        x["high_speed_signal_integrity_pass"]=True
    r=assess(change(mutate))
    assert not r["safe_to_fabricate"]
    assert any(x["code"]=="direct_socket_swap_not_proven" for x in r["blockers"])

def test_wrong_chip_variant_or_connector_count_fails():
    def mutate(x):
        x["modules"][0]["soc"]="RK3566"
    with pytest.raises(CarrierGateError,match="silicon"):
        assess(change(mutate))
    def bad(x):
        x["modules"][1]["vendor_connector_count"]=2
    with pytest.raises(CarrierGateError,match="connector"):
        assess(change(bad))
