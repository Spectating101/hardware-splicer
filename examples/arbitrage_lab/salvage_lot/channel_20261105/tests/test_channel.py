"""Commercial rights, price-direction and true bench observation tests."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
def module(name:str):
    spec=importlib.util.spec_from_file_location("hs_"+name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(m)
    return m

channel=module("channel_pilot")
bench=module("read_only_bench")

def load()->dict:
    return json.loads((ROOT/"sources.json").read_text())

def test_recycler_quote_direction_never_inverted():
    j=load()
    s=j["counterparties"][0]
    assert s["published_buyback_price_twd"]["complete_desktop"]==140
    assert s["quote_direction"]=="RECYCLER_PAYS_INBOUND_OWNER"
    r=channel.compute(j)
    assert r["confirmed_supplier_salvage_sale_quotes"]==0
    assert r["verified_scrap_pc_available"]==0
    assert r["confirmed_recovered_functional_products"]==0
    assert all(x["is_this_an_offer_to_sell_scrap_to_HS"] is False for x in r["recycler_channels"])

def test_recycler_bid_scenario_is_not_actual_sale_price():
    j=load()
    o=channel.batch_unit(j,0.65)
    assert o["price_per_unit_assumption_twd"]==250
    assert o["batch_obtained"] is False
    assert o["seller_sale_quote_obtained"] is False
    assert o["transfer_documented"] is False

@pytest.mark.parametrize("p,ev,maxbid",[
    (0.25,-400,0),(0.50,-80,20),(0.65,112,212),(0.80,304,404)])
def test_batch_economics(p,ev,maxbid):
    j=load()
    r=channel.batch_unit(j,p)
    assert r["net_if_functionally_verified_twd"]==560
    assert r["loss_if_unrecoverable_twd"]==-720
    assert r["expected_per_unit_twd"]==ev
    assert r["expected_per_batch_twd"]==ev*5
    assert r["max_price_per_unit_for_expected_target_twd"]==maxbid

@pytest.mark.parametrize("p",[-.1,1.0001])
def test_invalid_success_fraction(p):
    with pytest.raises(ValueError):
        channel.batch_unit(load(),p)

def test_observed_working_acer_competition_beats_bad_salvage_only_at_high_ask():
    j=load()
    lead=j["candidate_listings"][0]
    assert lead["ask_price_twd"]==2800
    assert lead["actual_acquired"] is False
    r=channel.whole_working_control(j,lead,5000,.8)
    assert r["success_conditional_profit_twd"]==525
    assert r["expected_contribution_twd"]==-245
    assert r["physically_validated"] is False
    assert r["break_even_success_probability"] > 0.86
    high=channel.whole_working_control(j,lead,6300,.8)
    assert high["expected_contribution_twd"]==691
    assert "better GPU" in high["comparability_warning"]

def test_bade_broken_ram_is_not_a_profitable_usable_asset():
    lead=load()["candidate_listings"][1]
    r=channel.reject_unverified_ram(lead)
    assert r["component_salvage_revenue_proved"]==0
    assert r["identity_verified"] is False
    assert r["working_verified"] is False

def test_read_only_cpu_mem_summary():
    x=bench.summarize_cpu("processor : 0\nmodel name : Intel Xeon E5\nprocessor : 1\n")
    assert x["cpu_model_generic"]=="Intel Xeon E5"
    assert x["logical_cpu_count"]==2
    assert bench.summarize_memory("MemTotal: 16384000 kB\n")["memory_total_gib"]>15

def test_read_only_lsblk_drops_identifiable_fields():
    fake={"blockdevices":[
        {"type":"disk","size":500000000000,"name":"nvme0n1","serial":"PRIVATE_SERIAL","wwn":"PRIVATE_WWN",
         "mountpoint":"/home/secret","uuid":"PRIVATE_UUID"},
        {"type":"loop","size":1000,"name":"loop0"}]}
    out=bench.summarize_disks(json.dumps(fake))
    assert out["physical_block_device_count"]==1
    assert out["smart_verified"] is False
    assert out["storage_data_wiped"] is False
    assert "PRIVATE" not in json.dumps(out)
    assert "/home" not in json.dumps(out)
    assert "nvme" not in json.dumps(out)

def test_real_optiplex_snapshot_is_only_calibration_not_salvage_proof():
    x=json.loads((ROOT/"evidence/optiplex_control_readonly.json").read_text())
    assert x["cpu"]["logical_cpu_count"]>0
    assert x["memory"]["memory_total_gib"]>1
    assert x["block_storage"]["physical_block_device_count"]>=1
    assert x["claim_gates"]["host_os_is_running"] is True
    assert x["claim_gates"]["real_salvage_observed"] is False
    assert x["claim_gates"]["a_salvaged_product_works"] is False
    assert x["claim_gates"]["resale_approval"] is False
    assert "serial" not in json.dumps(x).lower()
    assert "mountpoint" not in json.dumps(x).lower()

def test_real_economics_output_keeps_no_inventory():
    j=json.loads((ROOT/"evidence/channel_decision.json").read_text())
    assert j["all_transaction_status"]=="NO_COMMERCIALLY_ACQUIRED_HARDWARE"
    assert j["existing_engine"]["real_inventory_count"]==0
    assert j["existing_engine"]["designs_authorized_as_real_products"]==0
    assert all(not x["physical_passed_units"] for x in j["hypothetical_batch_recovery_scenarios"])
