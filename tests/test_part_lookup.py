"""Looking a marking up in KiCad's own libraries: real data, honest tiers, and checked against an independent reading of the same files."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hardware_splicer import part_lookup as pl
from hardware_splicer.kicad_diff import parse_kicad_sexp

pytestmark = pytest.mark.skipif(not pl.libraries_available(), reason="KiCad's libraries are not installed")


def _props(tree) -> dict[str, str]:
    out: dict[str, str] = {}
    for child in tree:
        if isinstance(child, list) and child and child[0] == "property" and len(child) > 2:
            out.setdefault(str(child[1]), str(child[2]))
    return out


def test_the_index_agrees_with_an_independent_reading_of_the_same_symbols() -> None:
    index = pl._index()
    sample = index.rows[:: max(1, len(index.rows) // 400)]
    assert len(sample) >= 300
    for row in sample:
        text = Path(row.path).read_text(encoding="utf-8")[row.start : row.end]
        tree = None
        for candidate in (text, text.rstrip()[:-1]):
            try:
                tree = parse_kicad_sexp(candidate)
                break
            except Exception:
                continue
        assert tree is not None, row.name
        props = _props(tree)
        assert tree[1] == row.name
        assert row.description == pl._clean(props.get("Description", ""), 200), (row.library, row.name)
        assert row.datasheet == pl._clean(props.get("Datasheet", ""), 300), (row.library, row.name)
        assert row.footprint == pl._clean(props.get("Footprint", ""), 120), (row.library, row.name)


def test_a_part_gets_its_own_datasheet_and_footprint_not_its_neighbours() -> None:
    by_name = {m["name"]: m for m in pl.lookup_part("NE555")["matches"]}
    assert by_name["NE555D"]["footprint"] == "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
    assert by_name["NE555P"]["footprint"] == "Package_DIP:DIP-8_W7.62mm"
    assert by_name["NE555P"]["datasheet"] == "http://www.ti.com/lit/ds/symlink/ne555.pdf"


def test_a_marking_is_matched_in_three_honest_tiers_and_says_what_each_means() -> None:
    exact = pl.lookup_part("LM358")["matches"]
    assert exact[0]["tier"] == "exact" and exact[0]["name"] == "LM358" and "exactly this name" in exact[0]["tier_text"]
    variant = pl.lookup_part("TLV75518PDBVR")["matches"]
    assert variant[0]["tier"] == "variant" and variant[0]["name"] == "TLV75518PDBV" and "different package or grade" in variant[0]["tier_text"]
    family = pl.lookup_part("W25Q128JWSIQ")["matches"]
    assert family and {m["tier"] for m in family} == {"family"} and all(m["name"].startswith("W25Q128J") for m in family)
    assert all("not this one" in m["tier_text"] for m in family)
    assert all(m["description"] for m in family)


def test_what_the_library_does_not_know_is_an_empty_answer_not_a_guess() -> None:
    nothing = pl.lookup_part("L9110S")
    assert nothing["matches"] == [] and nothing["source"]["name"] == "KiCad symbol library"
    assert pl.lookup_part("QZXJ7")["matches"] == []
    short = pl.lookup_part("ab")
    assert short["matches"] == [] and "at least 3 characters" in short["reason"]


@pytest.mark.parametrize("bad", ["x" * 41, "NE‮555", "NE​555", "a\u0000b"])
def test_a_marking_that_cannot_be_looked_up_is_refused(bad: str) -> None:
    with pytest.raises(pl.PartLookupError):
        pl.lookup_part(bad)


@pytest.mark.parametrize("bad", [None, 5, ["NE555"], {"a": 1}, b"NE555"])
def test_something_that_is_not_text_is_refused(bad) -> None:
    with pytest.raises(pl.PartLookupError, match="must be text"):
        pl.lookup_part(bad)


def test_only_web_links_come_back_as_datasheets_and_every_answer_names_its_source() -> None:
    result = pl.lookup_part("NE555")
    assert result["source"]["version"] == "9.0" and result["source"]["symbols"] > 20000 and "not proof" in result["source"]["note"]
    for match in result["matches"]:
        assert match["datasheet"] is None or match["datasheet"].startswith(("http://", "https://"))
    assert pl._safe_url("javascript:alert(1)") is None and pl._safe_url("file:///etc/passwd") is None and pl._safe_url("~") is None
    assert pl._safe_url("https://example.com/a b") is None and pl._safe_url("https://example.com/ds.pdf") == "https://example.com/ds.pdf"


def test_a_symbols_pins_are_read_with_their_names_and_types_including_for_derived_symbols() -> None:
    pins = pl.symbol_pins("Timer", "NE555P")
    assert pins["pins_total"] == 8
    by_number = {p["number"]: p for p in pins["pins"]}
    assert by_number["8"]["name"] == "VCC" and by_number["8"]["type"] == "power_in" and by_number["1"]["name"] == "GND"
    derived = next(r for r in pl._index().rows if r.extends)
    assert pl.symbol_pins(derived.library, derived.name)["pins_total"] > 0
    with pytest.raises(pl.PartLookupError):
        pl.symbol_pins("Timer", "NOT_A_PART")


def test_the_measurements_to_make_come_from_the_pins_and_never_claim_what_the_reading_should_be() -> None:
    gates = pl.power_gates("Timer", "NE555P", "Package_DIP:DIP-8_W7.62mm")
    kinds = [g["kind"] for g in gates]
    assert kinds[0] == "voltage" and kinds[-1] == "isolation"
    assert "pin 8 (VCC)" in gates[0]["instruction"] and "pin 1 (GND)" in gates[0]["instruction"]
    assert "Pin 1 is the corner with the dot or notch" in gates[0]["instruction"]
    assert "datasheet" in gates[0]["expect"] and not any(ch.isdigit() for ch in gates[0]["expect"])     # no invented range
    assert "Pin 1 is the corner" not in pl.power_gates("Timer", "NE555P", None)[0]["instruction"]        # only said where it is true
    assert pl.power_gates("Timer", "NOT_A_PART", None) == []


def test_package_sizes_are_the_libraries_courtyards_and_a_name_cannot_walk_out_of_the_library() -> None:
    soic = pl.footprint_size("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    assert (soic["width_mm"], soic["length_mm"]) == (7.4, 5.4) and "courtyard" in soic["source"]
    assert pl.footprint_size("Package_DIP:DIP-8_W7.62mm")["width_mm"] > 9
    for bad in ("../../etc:passwd", "Package_SO:../../../../etc/passwd", "Nope:Nope", "", "no colon", "a:b/../c"):
        assert pl.footprint_size(bad) is None


def test_it_is_deterministic_and_fast_after_the_first_look() -> None:
    first = pl.lookup_part("74HC595")
    start = time.perf_counter()
    for _ in range(50):
        again = pl.lookup_part("74HC595")
    assert again == first and (time.perf_counter() - start) / 50 < 0.02


def test_without_libraries_it_says_so_instead_of_pretending(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_DIR", str(tmp_path))
    pl.clear_cache()
    try:
        result = pl.lookup_part("NE555")
        assert result["matches"] == [] and "not installed" in result["reason"]
    finally:
        monkeypatch.undo()
        pl.clear_cache()
