"""No-human-in-the-loop public source checks with hard source/physical boundaries."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.autonomous_source_observer import (
    observe_source, ZEBRA_SPEC, QNAP_SPEC, EPSON_DOC,
)
from hardware_splicer.autonomous_evidence_controller import run_public_evidence_investigation

ROOT=Path(__file__).resolve().parents[1]
REPAIR_URL="https://www.ruten.com.tw/item/22623851402690/"
EPSON_URL="https://www.ruten.com.tw/item/21447795842755/"
QNAP_URL="https://www.ruten.com.tw/item/22606139676402/"
APPLE_URL="https://www.ruten.com.tw/item/22613329448846/"
DATA={
    REPAIR_URL:('<title>Symbol Motorola LS2208 scanner 剪線未測</title><meta name="description" content="直購價: 50 - 50, 庫存: 1">',"text/html"),
    EPSON_URL:('<title>EPSON LQ-680  printer</title><meta name="description" content="直購價: 300 - 300, 庫存: 5">',"text/html"),
    QNAP_URL:('<title>QNAP TS-219P II NAS motherboard</title><meta name="description" content="直購價: 650 - 650, 庫存: 1">',"text/html"),
    APPLE_URL:('<title>Apple A1314 keyboard mouse</title><meta name="description" content="直購價: 500 - 500, 庫存: 1">',"text/html"),
    ZEBRA_SPEC:('<title>LS2208 Handheld Scanner Specification Sheet | Zebra</title><body><div>Supported Host Interfaces USB, RS232, Keyboard Wedge</div><div>Input Voltage Range 4.5 to 5.5 VDC</div></body>',"text/html"),
    QNAP_SPEC:('<title>TS-219P II | Hardware Specs | QNAP</title><body><div>USB 2.0 USB 3.2 Gigabit eSATA</div></body>',"text/html"),
    EPSON_DOC:('<title>EPSON Manual Web-Site</title><body><h1>LQ-680 / LQ-680Pro</h1><p>Reference Guide</p></body>',"text/html"),
}


def cases():
    return (
        json.loads((ROOT/"examples/dual_track/repair_ls2208_unverified.json").read_text()),
        json.loads((ROOT/"examples/dual_track/splice_four_marketplace_donors_unverified.json").read_text()),
    )


def controlled_fetch(url):
    html,mime=DATA[url]
    return 200,mime,html.encode("utf8"),url


def test_automatic_run_fetches_seven_unique_sources_and_reuses_repair_listing():
    repair,splice=cases()
    seen=[]
    def fetch(url):
        seen.append(url)
        return controlled_fetch(url)
    result=run_public_evidence_investigation(repair,splice,fetcher=fetch,observed_at="2026-10-20T00:00:00Z")
    assert len(seen)==7==len(set(seen))
    assert result["bounded_source_fetches"]==7
    assert any(a["selected_action"]=="reuse_previous_source_receipt" for a in result["actions"])
    assert result["repair"]["analysis"]["seller_cut_cable_description_reobserved"]
    assert result["repair"]["analysis"]["family_spec_state"]=="MANUFACTURER_FAMILY_SPEC_REOBSERVED"
    assert result["repair"]["analysis"]["first_hypothesis_id"]=="severed_interface_cable"
    assert not result["repair"]["analysis"]["diagnosis_proved"]
    assert len(result["splicing"]["candidate_source_audit"])==4
    assert all(x["public_listing_identity_status"]=="SELLER_ADVERTISEMENT_REOBSERVED_NOT_PART_VERIFIED" for x in result["splicing"]["candidate_source_audit"])
    assert all(x["official_model_family_source_status"]=="MANUFACTURER_FAMILY_SPEC_REOBSERVED"
               for x in result["splicing"]["candidate_source_audit"]
               if x["candidate_id"] in {"ls2208_scanner_engine","epson_paper_motion","qnap_embedded_compute"})
    assert len([x for x in result["splicing"]["interconnection_gaps"] if x["type"]=="interface_unknown"])==3
    assert all(not x["can_bind_electrical_interface"] for x in result["splicing"]["candidate_source_audit"])
    assert result["physical_operations_executed"]==0
    assert result["purchases_or_seller_contacts"]==0
    assert not result["repair"]["mission_success"]
    assert not result["splicing"]["mission_success"]


def test_marketplace_page_seller_claims_are_not_measurements_or_sold_prices():
    report=observe_source(source_id="s",url=REPAIR_URL,purpose="market_listing",expected_model="LS2208",
                          fetcher=controlled_fetch,observed_at="2026-10-20T00:00:00Z")
    assert report["status"]=="MARKET_LISTING_METADATA_REOBSERVED"
    assert report["seller_price_claim_twd"]=={"min":50,"max":50}
    assert report["seller_stock_claim_units"]==1
    assert report["content_sha256"]
    assert not report["physical_parts_verified"]
    assert not report["interfaces_measured"]
    assert not report["purchase_or_power_authorized"]


def test_manufacturer_family_spec_does_not_certify_particular_used_unit():
    r=observe_source(source_id="zebra",url=ZEBRA_SPEC,purpose="manufacturer_spec",
                     expected_model="LS2208",fetcher=controlled_fetch,observed_at="2026-10-20T00:00:00Z")
    assert r["status"]=="MANUFACTURER_FAMILY_SPEC_REOBSERVED"
    assert "USB" in r["manufacturer_family_interface_options"]
    assert "RS232" in r["manufacturer_family_interface_options"]
    assert "4.5 to 5.5 VDC" in r["manufacturer_family_voltage_range_claim"]
    assert not r["specimen_specification_verified"]


@pytest.mark.parametrize("url,purpose",[
    ("http://www.ruten.com.tw/item/22623851402690/","market_listing"),
    ("https://evil.example/item/22623851402690/","market_listing"),
    ("https://www.ruten.com.tw/item/22623851402690/?redirect=http://evil.example","market_listing"),
    ("https://www.ruten.com.tw/item/22623851402690/","manufacturer_spec"),
    ("https://www.zebra.com/us/en/other","manufacturer_spec"),
    ("https://user:pass@www.ruten.com.tw/item/22623851402690/","market_listing"),
])
def test_url_host_and_path_allowlist(url,purpose):
    with pytest.raises(ValueError):
        observe_source(source_id="s",url=url,purpose=purpose,expected_model="LS2208",fetcher=controlled_fetch)


def test_redirect_to_different_item_does_not_preserve_source_identity():
    def malicious_redirect(url):
        return 200,"text/html",DATA[REPAIR_URL][0].encode(),EPSON_URL
    report=observe_source(source_id="s",url=REPAIR_URL,purpose="market_listing",expected_model="LS2208",fetcher=malicious_redirect)
    assert report["status"]=="SOURCE_RETRIEVAL_BLOCKED"
    assert not report["source_available_at_check"]


def test_html_title_model_conflict_propagates_as_highest_priority_gap():
    repair,splice=cases()
    def swapped(url):
        if url==QNAP_URL:
            return 200,"text/html",b"<title>Totally different network device</title>",url
        return controlled_fetch(url)
    result=run_public_evidence_investigation(repair,splice,fetcher=swapped)
    qnap=next(x for x in result["splicing"]["candidate_source_audit"] if x["candidate_id"]=="qnap_embedded_compute")
    assert qnap["public_listing_identity_status"]=="CONFLICT_REQUIRES_NEW_SOURCE"
    assert result["splicing"]["interconnection_gaps"][0]["type"]=="source_identity_discrepancy"
    assert result["splicing"]["verified_distinct_donors"]==0


def test_unreachable_source_returns_bounded_blocker_without_retries_or_false_claim():
    repair,splice=cases()
    seen=[]
    def unreachable(url):
        seen.append(url)
        if url==REPAIR_URL:
            raise TimeoutError("busy")
        return controlled_fetch(url)
    result=run_public_evidence_investigation(repair,splice,fetcher=unreachable)
    assert len(seen)==7
    assert result["repair"]["analysis"]["seller_listing_state"]=="PUBLIC_SOURCE_RETRIEVAL_UNAVAILABLE"
    assert any(x["status"]=="SOURCE_RETRIEVAL_BLOCKED" for x in result["source_receipts"])
    assert not result["repair"]["analysis"]["actual_scanner_condition_verified"]


def test_untrusted_script_claims_do_not_prove_manufacturer_interfaces():
    html=b'<title>LS2208 Product</title><body><script>USB RS232 4.5 to 5.5 VDC</script><span>Manual inspection</span></body>'
    r=observe_source(source_id="zebra",url=ZEBRA_SPEC,purpose="manufacturer_spec",expected_model="LS2208",
                     fetcher=lambda url:(200,"text/html",html,url))
    assert r["status"]=="MANUFACTURER_FAMILY_SPEC_REOBSERVED"
    assert not r["manufacturer_family_interface_options"]
    assert r["manufacturer_family_voltage_range_claim"] is None


def test_html_refuses_bad_mime_and_oversized_payload():
    a=observe_source(source_id="s",url=REPAIR_URL,purpose="market_listing",expected_model="LS2208",
                     fetcher=lambda url:(200,"application/pdf",b"%PDF fake",url))
    assert a["status"]=="HTTP_OR_CONTENT_TYPE_UNACCEPTED"
    from hardware_splicer.autonomous_source_observer import MAX_READ
    b=observe_source(source_id="s",url=REPAIR_URL,purpose="market_listing",expected_model="LS2208",
                     fetcher=lambda url:(200,"text/html",b"x"*(MAX_READ+1),url))
    # Even injected fetchers cannot slip oversized body bytes past intake.
    assert b["status"]=="SOURCE_RETRIEVAL_BLOCKED"
    assert not b["source_available_at_check"]
    assert not b["physical_parts_verified"]


def test_reobserved_cut_cable_and_manufacturer_source_trigger_conditional_repair_route():
    repair,splice=cases()
    report=run_public_evidence_investigation(repair,splice,fetcher=controlled_fetch)
    revision=report["proposed_engineering_revision"]
    path=revision["repair_route"]
    assert path["route_id"]=="consider_exact_model_replacement_interface_cable"
    assert path["hypothesis_advanced"]=="severed_interface_cable"
    assert path["alternative_faults_eliminated"]==[]
    assert path["original_device_repaired"] is False
    assert "DO NOT invent" in path["safe_method"]
    assert not revision["repair_mission_success"]


def test_auto_revision_reclassifies_mouse_switch_as_not_safety_stop():
    repair,splice=cases()
    report=run_public_evidence_investigation(repair,splice,fetcher=controlled_fetch)
    machine=report["proposed_engineering_revision"]["new_product_revision"]
    apple=next(x for x in machine["module_dispositions"] if x["candidate_id"]=="mouse_button_switch")
    assert apple["disposition"]=="ONLY_NONSafety_UI_HYPOTHESIS"
    assert "operator input and stop" in machine["identified_critical_missing_functions"]
    assert any("safety-rated" in x for x in machine["external_support_components_likely_needed"])
    assert not machine["complete_system_demonstrated"]
    assert not machine["connection_authorized"]


def test_bad_qnap_source_changes_automated_architecture_does_not_request_operator_check():
    repair,splice=cases()
    def bad_qnap(url):
        if url==QNAP_URL:
            return 200,"text/html",b"<title>Unrelated stock</title>",url
        return controlled_fetch(url)
    report=run_public_evidence_investigation(repair,splice,fetcher=bad_qnap)
    machine=report["proposed_engineering_revision"]["new_product_revision"]
    qnap=next(x for x in machine["module_dispositions"] if x["candidate_id"]=="qnap_embedded_compute")
    assert qnap["disposition"]=="QUARANTINE_SOURCE_IDENTITY"
    compute=next(x for x in machine["provisional_functional_blocks"] if x["function"]=="local decision logic")
    assert "do not select" in compute["preferred_hypothesis"]
    assert "existing authorized Linux computer" in compute["fallback"]
    assert report["purchases_or_seller_contacts"]==0


def test_sdk_and_mcp_expose_actual_autonomous_research_tool(monkeypatch):
    import asyncio
    from hardware_splicer import mcp_server, sdk
    from hardware_splicer.autonomous_evidence_controller import run_public_evidence_investigation

    def stub_runner(repair,splice):
        return run_public_evidence_investigation(repair,splice,fetcher=controlled_fetch,observed_at="2026-10-20T00:00:00Z")

    monkeypatch.setattr("hardware_splicer.autonomous_evidence_controller.run_public_evidence_investigation",stub_runner)
    sdk_response=sdk.investigate_public_donor_sources()
    assert sdk_response["bounded_source_fetches"]==7
    tool_list=asyncio.run(mcp_server.list_tools())
    tool=next(x for x in tool_list if x.name=="hs_investigate_public_donors")
    assert "repair_intake" in tool.inputSchema["properties"]
    assert "splice_intake" in tool.inputSchema["properties"]
    payload=asyncio.run(mcp_server.call_tool("hs_investigate_public_donors",{}))
    data=json.loads(payload[0].text)
    assert data["repair"]["mission_success"] is False
    assert data["splicing"]["mission_success"] is False
    assert data["physical_operations_executed"]==0
    assert data["proposed_engineering_revision"]["new_product_revision"]["connection_authorized"] is False
