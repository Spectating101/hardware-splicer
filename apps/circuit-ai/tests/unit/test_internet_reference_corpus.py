from src.intelligence.authority_ledger import build_authority_ledger
from src.intelligence.internet_reference_corpus import internet_dataset_sources, internet_reference_cases


def test_internet_reference_corpus_has_usable_scale_and_source_lanes():
    sources = internet_dataset_sources()
    cases = internet_reference_cases()
    source_ids = {source["source_id"] for source in sources}

    assert len(cases) >= 10
    assert {"sparkfun_open_hardware", "adafruit_pcb_design_files", "fpic", "pcb_component_detection"} <= source_ids
    assert any("component_detection_eval" in source.get("authority_use", []) for source in sources)
    assert any("reference_topology" in source.get("authority_use", []) for source in sources)


def test_internet_reference_cases_do_not_grant_physical_authority():
    for case in internet_reference_cases():
        ledger = build_authority_ledger(case["payload"])
        can = ledger["can"]
        topology = ledger["evidence_summary"]["topology"]

        assert topology["reference_only"] is True, case["case_id"]
        assert topology["measurement_backed"] is False, case["case_id"]
        assert can["use_measured_pinout"] is False, case["case_id"]
        assert can["use_electrical_simulation"] is False, case["case_id"]
        assert can["power_or_splice_now"] is False, case["case_id"]
        assert can["claim_production_repair_release"] is False, case["case_id"]
