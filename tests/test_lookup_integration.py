"""Marking lookup in the plans, the lookup API and the teardown search: real library data in the advice, never proof."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer import part_lookup, teardown_search
from hardware_splicer.donor_capture import build_donor_salvage_plan
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.salvage_plan import MAX_LOOKUPS, build_salvage_plan

needs_libraries = pytest.mark.skipif(not part_lookup.libraries_available(), reason="KiCad's libraries are not installed")
REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1" / "spi_flash_adapter_v1.kicad_pcb"


def _spec(*chips: tuple[str, str]) -> dict:
    return {"name": "x", "board": {"width_mm": 80, "length_mm": 60},
            "parts": [{"ref": f"U{i + 1}", "kind": "ic", "package": "DIP", "marking": marking, "x_mm": 8 + 12 * (i % 6), "y_mm": 8 + 12 * (i // 6)} for i, (marking, _) in enumerate(chips)]}


def _step(plan: dict, ref: str) -> dict:
    return next(s for s in plan["steps"] if ref in s["refs"])


@needs_libraries
def test_a_board_files_chips_are_looked_up_and_each_answer_says_how_close_it_is() -> None:
    plan = build_salvage_plan(REF.read_text(encoding="utf-8"))
    assert plan["lookup_source"]["name"] == "KiCad symbol library" and plan["lookup_source"]["version"] == "9.0"
    by_ref = {p["ref"]: p["lookup"] for p in plan["parts"] if p.get("lookup")}
    assert by_ref["U3"]["tier"] == "variant" and by_ref["U3"]["match"]["name"] == "TLV75518PDBV"      # the regulator the file names
    assert by_ref["U2"]["tier"] == "family" and by_ref["U2"]["match"] is None and "W25Q128JVS" in by_ref["U2"]["family"]
    assert by_ref["U1"]["tier"] == "none"
    assert "R2" not in by_ref and "J1" not in by_ref                                                  # only chips are looked up
    text = {ref: _step(plan, ref)["instruction"] for ref in ("U1", "U2", "U3")}
    assert "KiCad's library has a part called \"TLV75518PDBV\"" in text["U3"] and "a variant" in text["U3"]
    assert "same family (W25Q128JVE" in text["U2"] and "but not this one" in text["U2"]
    assert "does not list it" in text["U1"]


@needs_libraries
def test_the_measurements_come_from_the_library_pins_and_say_where_the_pin_names_came_from() -> None:
    step = _step(build_salvage_plan(REF.read_text(encoding="utf-8")), "U3")
    measures = [c for c in step["checks"] if c["check"] == "measure"]
    assert [c["gate_kind"] for c in measures] == ["voltage", "voltage", "isolation"]
    assert "(IN)" in measures[0]["detail"] and "(GND)" in measures[0]["to"]
    assert all("datasheet" in c["expect"] or "ohms" in c["expect"] for c in measures)
    assert not any(ch.isdigit() for c in measures[:2] for ch in c["expect"])                         # it never says what a reading should be
    assert "not from your chip" in step["instruction"] and "TLV75518PDBV" in step["instruction"]
    # A family match is not this chip, so it gets no measurements built from another chip's pins.
    assert not [c for c in _step(build_salvage_plan(REF.read_text(encoding="utf-8")), "U2")["checks"] if c["check"] == "measure"]


@needs_libraries
def test_a_typed_marking_that_the_library_knows_gets_its_gates_and_one_it_does_not_know_says_so() -> None:
    plan = build_donor_salvage_plan(_spec(("NE555P", ""), ("L9110S", "")))
    chip = _step(plan, "U1")
    assert "\"NE555P\": Precision Timers" in chip["instruction"] and "pin 8 (VCC)" in json.dumps(chip["checks"]) and "pin 1 (GND)" in json.dumps(chip["checks"])
    assert "Pin 1 is the corner with the dot or notch" in json.dumps(chip["checks"])
    unknown = _step(plan, "U2")
    assert "does not list it" in unknown["instruction"] and not [c for c in unknown["checks"] if c["check"] == "measure"]
    assert plan["lookup_source"]["version"] == "9.0"


@needs_libraries
def test_looking_a_chip_up_never_changes_the_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(("NE555P", ""), ("L9110S", ""), ("W25Q128JWSIQ", ""), ("motor driver", ""))
    with_library = build_donor_salvage_plan(spec)
    monkeypatch.setattr(part_lookup, "libraries_available", lambda: False)
    without = build_donor_salvage_plan(spec)
    assert [p["salvage"]["verdict"] for p in with_library["parts"]] == [p["salvage"]["verdict"] for p in without["parts"]]
    assert without["lookup_source"] is None and all("lookup" not in p for p in without["parts"])


@needs_libraries
def test_the_number_of_lookups_is_bounded() -> None:
    spec = _spec(*[("NE555P", "")] * 60)
    spec["parts"] = [{**p, "ref": f"U{i + 1}", "x_mm": 3 + (i % 20) * 3.5, "y_mm": 3 + (i // 20) * 8} for i, p in enumerate(spec["parts"])]
    plan = build_donor_salvage_plan(spec)
    assert sum(1 for p in plan["parts"] if p.get("lookup")) == MAX_LOOKUPS


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_JLC_ENRICH", raising=False)
    teardown_search.clear_cache()
    return TestClient(create_product_app(ProjectStore(tmp_path / "store")))


@needs_libraries
def test_the_lookup_api_returns_matches_with_their_source_and_a_link_only_for_a_short_code(api: TestClient) -> None:
    body = api.get("/v1/parts/lookup", params={"marking": "NE555"}).json()
    assert body["ok"] and {m["name"] for m in body["matches"]} == {"NE555D", "NE555P"} and body["source"]["version"] == "9.0"
    assert body["search_links"] == {}                                                                  # a long part number is not a top-mark code
    short = api.get("/v1/parts/lookup", params={"marking": "KZ17"}).json()
    assert short["matches"] == [] and short["search_links"]["smd_code"] == "https://www.s-manuals.com/smd/kz17"
    assert api.get("/v1/parts/lookup", params={"marking": "NE‮555"}).status_code == 422
    assert api.get("/v1/parts/lookup", params={"marking": "x" * 41}).status_code == 422
    online = api.get("/v1/parts/lookup", params={"marking": "NE555", "online": "true"}).json()
    assert online["online"]["status"] in {"not_checked", "unavailable", "not_found", "unknown"} or isinstance(online["online"]["records"], list)


def _fake(rows: list[dict] | str, calls: list[str] | None = None):
    def fetch(url: str, timeout: float) -> bytes:
        if calls is not None:
            calls.append(url)
        if rows == "boom":
            raise OSError("offline")
        return json.dumps({"results": rows}).encode()
    return fetch


GOOD = {"title": "Roku Teardown", "url": "https://www.ifixit.com/Teardown/Roku/1", "type": "teardown", "summary": "Inside the box"}


def test_a_teardown_search_returns_titles_and_links_with_credit_and_nothing_unsafe() -> None:
    teardown_search.clear_cache()
    rows = [
        {"title": "Disassembly", "url": "https://www.ifixit.com/Guide/x/2", "type": "disassembly"},
        GOOD,
        {"title": "Evil", "url": "https://evil.example/ifixit.com/x", "type": "teardown"},
        {"title": "Script", "url": "javascript:alert(1)", "type": "teardown"},
        {"title": "Odd‮title", "url": "https://www.ifixit.com/Teardown/y/3", "type": "teardown"},
        {"title": 5, "url": "https://www.ifixit.com/Teardown/z/4"},
        "not a row",
    ]
    result = teardown_search.search_teardowns("roku stick", fetch=_fake(rows))
    assert [r["title"] for r in result["results"]] == ["Roku Teardown", "Disassembly"]                 # teardowns first, only ifixit.com links
    assert "CC BY-NC-SA" in result["attribution"] and "links to their pages" in result["attribution"]
    assert result["available"] is True


def test_the_search_is_cached_and_an_outage_is_reported_and_not_remembered() -> None:
    teardown_search.clear_cache()
    calls: list[str] = []
    assert teardown_search.search_teardowns("roku stick", fetch=_fake([GOOD], calls))["results"]
    assert teardown_search.search_teardowns("ROKU  stick", fetch=_fake([GOOD], calls))["results"] and len(calls) == 1
    teardown_search.clear_cache()
    down = teardown_search.search_teardowns("router thing", fetch=_fake("boom"))
    assert down["available"] is False and "could not be reached" in down["note"] and down["results"] == []
    assert teardown_search.search_teardowns("router thing", fetch=_fake([GOOD]))["results"]            # the next try works: the failure was not kept
    empty = teardown_search.search_teardowns("nothing at all", fetch=_fake([]))
    assert empty["results"] == [] and "No guides found" in empty["note"]


@pytest.mark.parametrize("bad", [None, 5, "ab", "x" * 61, "roku​stick", "a\u0000b c"])
def test_a_search_that_cannot_be_made_is_refused(bad) -> None:
    with pytest.raises(teardown_search.TeardownSearchError):
        teardown_search.search_teardowns(bad, fetch=_fake([]))


def test_an_oversized_or_wrongly_shaped_answer_is_treated_as_an_outage() -> None:
    teardown_search.clear_cache()
    assert teardown_search.search_teardowns("big answer", fetch=lambda u, t: b"x" * (teardown_search.MAX_BYTES + 5))["available"] is False
    assert teardown_search.search_teardowns("odd answer", fetch=lambda u, t: b'{"results": "nope"}')["available"] is False
    assert teardown_search.search_teardowns("not json", fetch=lambda u, t: b"<html>")["available"] is False


def test_the_teardown_api_answers_and_refuses(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(teardown_search, "_fetch", _fake([GOOD]))
    body = api.get("/v1/teardowns/search", params={"q": "roku stick"}).json()
    assert body["ok"] and body["results"][0]["url"] == GOOD["url"]
    assert api.get("/v1/teardowns/search", params={"q": "ab"}).status_code == 422


@pytest.mark.skipif(not __import__("os").environ.get("HS_LIVE_NET"), reason="set HS_LIVE_NET=1 to call iFixit for real")
def test_live_ifixit_still_answers_in_the_shape_we_read() -> None:
    teardown_search.clear_cache()
    result = teardown_search.search_teardowns("roku remote teardown")
    assert result["available"] is True and result["results"] and all(r["url"].startswith("https://www.ifixit.com/") for r in result["results"])
