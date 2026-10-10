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
    assert [c["gate_kind"] for c in measures] == ["diode", "isolation", "voltage"]   # power-off first; output pin is still not a supply
    assert "(IN)" in measures[0]["detail"] and "(GND)" in measures[0]["to"]
    assert all("datasheet" in c["expect"] or "ohms" in c["expect"] or "both readings" in c["expect"] for c in measures)
    assert all(c["expect"].startswith("write down") for c in measures)
    assert not any(ch.isdigit() for c in measures[:2] for ch in c["expect"])                         # it never says what a reading should be
    assert "not from your chip" in step["instruction"] and "TLV75518PDBV" in step["instruction"]
    # A family match is not this chip, so it gets no measurements built from another chip's pins.
    assert not [c for c in _step(build_salvage_plan(REF.read_text(encoding="utf-8")), "U2")["checks"] if c["check"] == "measure"]


@needs_libraries
def test_a_typed_marking_that_the_library_knows_gets_its_gates_and_one_it_does_not_know_says_so() -> None:
    plan = build_donor_salvage_plan(_spec(("NE555P", ""), ("L9110S", "")))
    chip = _step(plan, "U1")
    assert "\"NE555P\": Precision Timers" in chip["instruction"] and "pin 8 (VCC)" in json.dumps(chip["checks"]) and "pin 1 (GND)" in json.dumps(chip["checks"])
    assert "dot or notch marks the pin-1 end" in json.dumps(chip["checks"])
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


# --- readings: what a person wrote down against each measurement ----------------------------------------------------------------


@needs_libraries
def test_the_lookup_api_offers_the_measurements_for_a_matched_chip_and_none_for_a_family_or_a_miss(api: TestClient) -> None:
    matched = api.get("/v1/parts/lookup", params={"marking": "NE555P"}).json()
    assert matched["gates_from"] == "NE555P" and [g["kind"] for g in matched["gates"]] == ["diode", "isolation", "voltage"]
    assert all(g["key"].startswith("Timer:NE555P|" + g["kind"] + "|pin ") for g in matched["gates"])   # the key names the chip: a reading cannot follow a new marking
    family = api.get("/v1/parts/lookup", params={"marking": "W25Q128JWSIQ"}).json()
    assert family["matches"] and family["gates"] == [] and family["gates_from"] is None
    assert api.get("/v1/parts/lookup", params={"marking": "L9110S"}).json()["gates"] == []


@needs_libraries
def test_recorded_readings_are_counted_shown_and_never_called_a_pass() -> None:
    gate_keys = [g["key"] for g in part_lookup.power_gates("Timer", "NE555P", "Package_DIP:DIP-8_W7.62mm")]
    assert gate_keys[0].startswith("Timer:NE555P|diode|")
    n = len(gate_keys)
    spec = _spec(("NE555P", ""))
    none = build_donor_salvage_plan(spec)
    assert none["parts"][0]["lookup"]["evidence"] == {"total": n, "recorded": 0, "ignored": 0}
    assert none["summary"]["evidence"] == {"chips_with_measurements": 1, "readings_recorded": 0, "readings_open": n}
    assert "Measurements still to record as notes" in none["steps"][-1]["instruction"] and "U1" in none["steps"][-1]["instruction"]
    assert "before you trust them" not in none["steps"][-1]["instruction"]

    spec["parts"][0]["readings"] = {gate_keys[0]: "5.02 V", "Timer:NE555P|voltage|pin 99 (NOPE)|pin 1 (GND)": "1 V"}
    some = build_donor_salvage_plan(spec)
    lookup = some["parts"][0]["lookup"]
    assert lookup["evidence"] == {"total": n, "recorded": 1, "ignored": 1}                      # a reading for a measurement that no longer exists is reported, not applied
    assert [g["reading"] for g in lookup["gates"]] == ["5.02 V"] + [None] * (n - 1)
    step = _step(some, "U1")
    assert f"Readings recorded: 1 of {n}" in step["instruction"] and "not a pass" in step["instruction"]
    assert [c["reading"] for c in step["checks"] if c["check"] == "measure"] == ["5.02 V"] + [None] * (n - 1)
    assert "pass" not in json.dumps(some["summary"]).lower().replace("compass", "")

    spec["parts"][0]["readings"] = {key: "noted" for key in gate_keys}
    full = build_donor_salvage_plan(spec)
    assert full["parts"][0]["lookup"]["evidence"]["recorded"] == n and full["summary"]["evidence"]["readings_open"] == 0
    assert "Measurements still to record" not in full["steps"][-1]["instruction"]


@pytest.mark.parametrize(
    "readings",
    ["text", ["a"], {"k" * 121: "x"}, {"k": "x" * 41}, {"k": 5}, {"k": ["x"]}, {"k‮": "x"}, {"k": "5​V"}, {f"k{i}": "x" for i in range(9)}],
)
def test_readings_that_are_not_short_plain_text_are_refused(readings) -> None:
    from hardware_splicer.donor_capture import DonorCaptureError

    spec = _spec(("NE555P", ""))
    spec["parts"][0]["readings"] = readings
    with pytest.raises(DonorCaptureError):
        build_donor_salvage_plan(spec)


@pytest.mark.parametrize("tail", ["\u0000https://evil.example/", "ok\u001b[31m", "a\u0008b", "a\u0001b", "a b", "x\"onmouseover=\"", "<script>", "‮", "é"])
def test_a_teardown_link_with_a_control_byte_or_anything_outside_plain_ascii_is_dropped(tail: str) -> None:
    teardown_search.clear_cache()
    row = {"title": "T", "url": "https://www.ifixit.com/" + tail, "type": "teardown"}
    assert teardown_search.search_teardowns("some device", fetch=_fake([row, GOOD]))["results"] == [{"title": "Roku Teardown", "url": GOOD["url"], "type": "teardown", "summary": "Inside the box"}]


def test_ordinary_ifixit_links_still_pass_the_stricter_filter() -> None:
    teardown_search.clear_cache()
    urls = ["https://www.ifixit.com/Teardown/Roku+RC-MC1+remote+Teardown/148825", "https://www.ifixit.com/Guide/Some%20Thing/2?x=1&y=2#top".replace("#top", ""), "https://www.ifixit.com/"]
    rows = [{"title": f"T{i}", "url": u, "type": "guide"} for i, u in enumerate(urls)]
    assert {r["url"] for r in teardown_search.search_teardowns("anything here", fetch=_fake(rows))["results"]} == set(urls)


@needs_libraries
def test_a_reading_does_not_follow_a_new_marking_to_a_different_chip_with_the_same_pins() -> None:
    first = part_lookup.power_gates("Timer", "NE555P", None)
    second = part_lookup.power_gates("Timer", "NE555D", None)
    assert [g["from"] for g in first] == [g["from"] for g in second]                              # the same pin numbers and names...
    assert not {g["key"] for g in first} & {g["key"] for g in second}                              # ...but a reading belongs to the chip it was taken from
    spec = _spec(("NE555D", ""))
    spec["parts"][0]["package"] = "SOIC"          # NE555D is SOIC; a DIP choice would correctly emit no pins
    spec["parts"][0]["readings"] = {first[0]["key"]: "5.02 V"}
    plan = build_donor_salvage_plan(spec)
    assert plan["parts"][0]["lookup"]["evidence"] == {"total": len(second), "recorded": 0, "ignored": 1}


@needs_libraries
def test_a_typed_dip_uses_the_dip_library_entry_not_the_first_variant() -> None:
    plan = build_donor_salvage_plan(_spec(("ATMEGA328P", "")))
    lookup = plan["parts"][0]["lookup"]
    assert lookup["match"]["name"] == "ATmega328P-P"
    blob = json.dumps(_step(plan, "U1")["checks"])
    assert "pin 7 (VCC)" in blob and "pin 8 (GND)" in blob
    assert "pin 4 (VCC)" not in blob


@needs_libraries
def test_a_package_that_does_not_fit_the_library_entry_gets_no_pin_numbers() -> None:
    spec = _spec(("ATMEGA328P", ""))
    spec["parts"][0]["package"] = "BGA"
    plan = build_donor_salvage_plan(spec)
    lookup = plan["parts"][0]["lookup"]
    assert lookup["match"] is not None and lookup["gates"] == []
    text = _step(plan, "U1")["instruction"]
    assert "pin numbers would not be yours" in text
    assert lookup["match"]["name"] in text


@needs_libraries
def test_finish_step_calls_readings_notes_and_does_not_make_them_a_trust_gate() -> None:
    plan = build_donor_salvage_plan(_spec(("NE555P", "")))
    finish = plan["steps"][-1]["instruction"]
    assert "before you trust them" not in finish
    assert "Measurements still to record as notes" in finish
    assert "none of them shows a removed chip works" in finish
    assert "U1" in finish


def test_the_teardown_fetch_follows_no_redirect_and_speaks_only_https() -> None:
    opener = teardown_search._opener()
    names = {type(h).__name__ for h in opener.handlers}
    assert "HTTPSHandler" in names and not names & {"FileHandler", "FTPHandler", "DataHandler", "HTTPHandler"}
    assert any(isinstance(h, teardown_search._NoRedirect) for h in opener.handlers)
    assert teardown_search._NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://169.254.169.254/") is None
    with pytest.raises(ValueError):
        teardown_search._fetch("http://127.0.0.1/", 1.0)
    with pytest.raises(ValueError):
        teardown_search._fetch("https://evil.example/api", 1.0)


def test_the_teardown_cache_is_bounded() -> None:
    teardown_search.clear_cache()
    for i in range(teardown_search.MAX_CACHE + 60):
        teardown_search.search_teardowns(f"device number {i:04d}", fetch=_fake([GOOD]))
    assert len(teardown_search._CACHE) <= teardown_search.MAX_CACHE
    assert "device number 0000" not in teardown_search._CACHE and f"device number {teardown_search.MAX_CACHE + 59:04d}" in teardown_search._CACHE
