"""jlcparts lookup: price breaks, exact-part preference and BOM totals, offline (no network)."""
from __future__ import annotations

from hardware_splicer import jlcparts_lookup as jl

TIERS = [{"qFrom": 1, "qTo": 9, "price": 7.31}, {"qFrom": 10, "qTo": 29, "price": 6.50}, {"qFrom": 30, "qTo": None, "price": 5.97}]
RECORDS = {
    "C8690": {"lcsc": "C8690", "mpn": "FT232RL-REEL", "description": "USB to UART SSOP-28", "datasheet": "", "price_tiers": TIERS, "stock": 9832},
    "C1": {"lcsc": "C1", "mpn": "FT232RL", "description": "USB to UART SSOP-28", "datasheet": "", "price_tiers": TIERS, "stock": 5},
    "C2": {"lcsc": "C2", "mpn": "RC0603FR-0710KL", "description": "10kΩ ±1% 0603", "datasheet": "",
           "price_tiers": [{"qFrom": 1, "qTo": None, "price": 0.001}], "stock": 10_000_000},
}
ROWS = [("C8690", "s", "c8690 ft232rl-reel usb to uart"), ("C1", "s", "c1 ft232rl usb to uart"),
        ("C2", "s", "c2 rc0603fr-0710kl 10kω ±1% 0603 chip resistor")]


def _offline(monkeypatch) -> None:
    monkeypatch.setattr(jl, "_record", lambda lcsc, shard: dict(RECORDS[lcsc]))
    monkeypatch.setattr(jl, "_index_rows", lambda refresh=False: iter(ROWS))
    monkeypatch.setattr(jl, "manifest", lambda refresh=False: {"created": "2026-11-26T03:01:58+00:00"})


def test_unit_price_follows_the_quantity_breaks() -> None:
    assert jl.unit_price(TIERS, 1) == 7.31
    assert jl.unit_price(TIERS, 10) == 6.50
    assert jl.unit_price(TIERS, 500) == 5.97
    assert jl.unit_price([], 3) is None


def test_search_prefers_the_exact_part_number_over_stock(monkeypatch) -> None:
    _offline(monkeypatch)
    hits = jl.search("FT232RL", rows=ROWS)
    assert [h["lcsc"] for h in hits] == ["C1", "C8690"]  # exact MPN first even though C8690 has more stock


def test_price_bom_totals_lines_and_reports_misses(monkeypatch) -> None:
    _offline(monkeypatch)
    bom = jl.price_bom([{"refs": ["U1"], "qty_per_board": 1, "lcsc": "C8690"},
                        {"refs": ["R1", "R2"], "qty_per_board": 2, "query": "0603 10k 1%"},
                        {"refs": ["X1"], "qty_per_board": 1, "query": "unobtainium"}], boards=10)
    assert [line["lcsc"] for line in bom["lines"]] == ["C8690", "C2"]
    assert bom["lines"][0]["unit_usd"] == 6.50 and bom["lines"][1]["qty"] == 20
    assert bom["parts_total_usd"] == round(6.50 * 10 + 0.001 * 20, 2)
    assert [m["refs"] for m in bom["not_found"]] == [["X1"]]
    assert [line["match"] for line in bom["lines"]] == ["lcsc_code", "keyword, check the description"]
    assert bom["prices_as_of"].startswith("2026-11-26")
