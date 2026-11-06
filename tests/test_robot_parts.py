from __future__ import annotations

import copy
import json

import pytest

from hardware_splicer import robot_parts as rp

DS = "https://example.com/jga25-370-datasheet.pdf"
LISTING = "https://www.ruten.com.tw/item/22222222222222/"


def _fact(value, unit, source=DS, basis="published", **extra):
    return {"value": value, "unit": unit, "basis": basis, "source": source, **extra}


def _good() -> dict:
    facts = {
        "rated_voltage": _fact(12, "V"),
        "output_free_speed_rpm": _fact(130, "rpm"),
        "rated_current": _fact(0.3, "A"),
        "stall_current": _fact(1.6, "A"),
        "stall_torque": _fact(0.43, "N·m"),
        "gear_ratio": _fact(78, "ratio"),
        "encoder_cpr": _fact(11, "count/rev_motor"),
        "encoder_supply_voltage": _fact(3.3, "V"),
        "shaft_diameter": _fact(4, "mm"),
        "body_dimensions": _fact([25, 25, 61], "mm"),
        "mass": _fact(95, "g"),
        "connector": _fact("6-pin PH2.0", "text", source=LISTING),
    }
    quotes = [{"claim": name, "quote": f"quote for {name}", "source": f["source"]} for name, f in facts.items()]
    return {
        "id": "jga25-370-12v-130rpm-encoder", "kind": "drive_motor", "name": "JGA25-370 12 V 130 rpm with Hall encoder",
        "status": "SOURCED_NOT_MEASURED",
        "listing": {"url": LISTING, "marketplace": "ruten", "variant": "12V 130RPM", "price_twd": 280,
                    "captured": "2026-11-07", "seller_claims": ["含霍爾編碼器"]},
        "sources": [{"label": "maker datasheet", "url": DS, "as_of": "2026-11-07"}],
        "facts": facts, "quotes": quotes, "unconfirmed": [],
    }


GOOD = _good()


def problems(entry):
    return rp.validate_part(entry)


def test_valid_entry_has_no_problems():
    assert problems(GOOD) == []


def test_fact_source_must_be_declared():
    e = copy.deepcopy(GOOD)
    e["facts"]["mass"]["source"] = "https://elsewhere.example/page"
    e["quotes"] = [q for q in e["quotes"] if q["claim"] != "mass"]
    assert any("mass" in p and "source" in p for p in problems(e))


def test_wrong_unit_rejected():
    e = copy.deepcopy(GOOD)
    e["facts"]["output_free_speed_rpm"]["unit"] = "rad/s"
    assert any("output_free_speed_rpm" in p and "unit" in p for p in problems(e))


def test_missing_required_fact_needs_unconfirmed_entry():
    e = copy.deepcopy(GOOD)
    del e["facts"]["stall_current"]
    e["quotes"] = [q for q in e["quotes"] if q["claim"] != "stall_current"]
    assert any("stall_current" in p for p in problems(e))
    e["unconfirmed"] = [{"fact": "stall_current", "reason": "no source publishes it; measure on bench"}]
    assert problems(e) == []


def test_unconfirmed_needs_a_reason():
    e = copy.deepcopy(GOOD)
    del e["facts"]["stall_current"]
    e["quotes"] = [q for q in e["quotes"] if q["claim"] != "stall_current"]
    e["unconfirmed"] = [{"fact": "stall_current", "reason": ""}]
    assert any("stall_current" in p for p in problems(e))


def test_typical_basis_needs_bench_note():
    e = copy.deepcopy(GOOD)
    e["facts"]["mass"] = _fact(95, "g", basis="typical")
    e["quotes"] = [q for q in e["quotes"] if q["claim"] != "mass"]
    assert any("mass" in p and "measure" in p for p in problems(e))
    e["facts"]["mass"]["note"] = "typical for the class; measure on the bench"
    assert problems(e) == []


def test_measured_basis_is_not_allowed_without_bench_evidence():
    e = copy.deepcopy(GOOD)
    e["facts"]["mass"]["basis"] = "measured"
    assert any("mass" in p and "basis" in p for p in problems(e))


def test_conflicting_needs_two_sourced_alternatives():
    e = copy.deepcopy(GOOD)
    e["facts"]["encoder_cpr"] = {"alternatives": [{"value": 11, "source": DS}], "unit": "count/rev_motor",
                                 "basis": "published", "confidence": "conflicting"}
    assert any("encoder_cpr" in p for p in problems(e))
    e["facts"]["encoder_cpr"]["alternatives"].append({"value": 12, "source": LISTING})
    e["quotes"].append({"claim": "encoder_cpr", "quote": "12 pulses", "source": LISTING})
    assert problems(e) == []


def test_published_fact_needs_quote_from_its_source():
    e = copy.deepcopy(GOOD)
    e["quotes"] = [q for q in e["quotes"] if q["claim"] != "gear_ratio"]
    assert any("gear_ratio" in p and "quote" in p for p in problems(e))


def test_multi_variant_listing_names_variant():
    e = copy.deepcopy(GOOD)
    e["listing"]["variant"] = ""
    assert any("variant" in p for p in problems(e))


def test_cross_border_marketplace_is_labelled():
    e = copy.deepcopy(GOOD)
    e["listing"]["marketplace"] = "shopee"
    assert any("marketplace" in p for p in problems(e))
    for ok in ("ruten", "maker_shop", "official_store", "cross_border"):
        e["listing"]["marketplace"] = ok
        assert problems(e) == []


def test_status_cannot_claim_authority():
    e = copy.deepcopy(GOOD)
    e["status"] = "VERIFIED"
    assert any("status" in p for p in problems(e))


def test_quote_source_must_be_declared():
    e = copy.deepcopy(GOOD)
    e["quotes"].append({"claim": "mass", "quote": "95 g", "source": "https://undeclared.example/"})
    assert any("undeclared" in p for p in problems(e))


def test_quote_claim_names_a_fact():
    e = copy.deepcopy(GOOD)
    e["quotes"].append({"claim": "colour", "quote": "black", "source": DS})
    assert any("colour" in p for p in problems(e))


def test_unknown_kind_rejected():
    e = copy.deepcopy(GOOD)
    e["kind"] = "flux_capacitor"
    assert any("kind" in p for p in problems(e))


def _library(tmp_path, parts):
    path = tmp_path / "robot_parts.json"
    path.write_text(json.dumps({"schema_version": rp.SCHEMA_VERSION, "rule": "r", "parts": parts}), encoding="utf-8")
    return path


def test_load_parts_raises_with_every_problem(tmp_path):
    a = copy.deepcopy(GOOD)
    a["status"] = "VERIFIED"
    b = copy.deepcopy(GOOD)
    b["id"] = "second-motor"
    b["listing"]["marketplace"] = "shopee"
    with pytest.raises(rp.RobotPartError) as err:
        rp.load_parts(_library(tmp_path, [a, b]))
    assert "status" in str(err.value) and "marketplace" in str(err.value)


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(rp.RobotPartError, match="duplicate"):
        rp.load_parts(_library(tmp_path, [GOOD, GOOD]))


def test_load_parts_returns_valid_parts(tmp_path):
    assert [p["id"] for p in rp.load_parts(_library(tmp_path, [GOOD]))] == [GOOD["id"]]


def test_shipped_library_loads():
    assert isinstance(rp.load_parts(), list)


# --- quote verification against captured sources ----------------------------------------------------------------------

def _captures(tmp_path, files: dict[str, str]):
    d = tmp_path / "captures"
    d.mkdir()
    index = {}
    for n, (url, text) in enumerate(files.items()):
        name = f"source_{n}.txt"
        (d / name).write_text(text, encoding="utf-8")
        index[url] = name
    (d / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return d


def _one_quote_part(quote: str, source: str = DS) -> dict:
    e = copy.deepcopy(GOOD)
    e["quotes"] = [{"claim": "rated_voltage", "quote": quote, "source": source}]
    return e


def test_quote_found_after_normalisation(tmp_path):
    caps = _captures(tmp_path, {DS: "The motor’s rated\n   voltage is 12 V – nominal."})
    result = rp.verify_quotes([_one_quote_part("The motor's rated voltage is 12 V - nominal.")], caps)
    assert result["pass"] is True and result["quotes_checked"] == 1 and result["failed"] == []


def test_quote_missing_fails(tmp_path):
    caps = _captures(tmp_path, {DS: "Rated voltage 6 V."})
    result = rp.verify_quotes([_one_quote_part("Rated voltage 12 V.")], caps)
    assert result["pass"] is False
    assert result["failed"][0]["claim"] == "rated_voltage" and "not found" in result["failed"][0]["reason"]


def test_quote_without_capture_fails(tmp_path):
    caps = _captures(tmp_path, {"https://other.example/": "Rated voltage 12 V."})
    result = rp.verify_quotes([_one_quote_part("Rated voltage 12 V.")], caps)
    assert result["pass"] is False and "no capture" in result["failed"][0]["reason"]


def test_sha256_recorded(tmp_path):
    import hashlib
    text = "Rated voltage 12 V."
    caps = _captures(tmp_path, {DS: text})
    result = rp.verify_quotes([_one_quote_part("Rated voltage 12 V.")], caps)
    assert result["sources"][DS]["sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_no_quotes_is_not_a_pass(tmp_path):
    caps = _captures(tmp_path, {DS: "x"})
    e = copy.deepcopy(GOOD)
    e["quotes"] = []
    result = rp.verify_quotes([e], caps)
    assert result["quotes_checked"] == 0 and result["pass"] is False


def test_html_to_text_drops_markup_scripts_and_entities():
    html = "<html><head><style>p{}</style><script>var x=1</script></head><body><p>Rated&nbsp;voltage:<b>12&#8239;V</b></p></body></html>"
    text = rp.html_to_text(html)
    assert "var x" not in text and "p{}" not in text and "<" not in text
    assert rp.normalise("Rated voltage: 12 V") in rp.normalise(text)
