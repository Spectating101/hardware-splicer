from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("hs_priced_bom", ROOT / "priced_bom.py")
pb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pb)

PACKS = {"packs": True, "max_pack": 8}


@pytest.mark.parametrize("title,want", [
    ("RCinPower 0702 27000KV 無刷馬達 4顆", 4), ("0702 馬達 x4 1S", 4), ("1S 300mAh BT2.0 電池 5入", 5),
    ("BT2.0 300mAh 高壓鋰電", 1), ("18650 電池 3000mAh 2入", 2), ("BT2.0 300mAh 3.8V x 2", 2),
    ("M1.4x3 螺絲 50入", 1), ("0702 馬達×4", 4), ("BT2.0 1S 300mAh 4pcs", 4), ("1102 x 4 馬達 0702", 4),
])
def test_pack_size_reads_real_title_shapes(title, want):
    assert pb.pack_size(title, PACKS) == want


def test_pack_size_is_one_unless_the_line_declares_packs():
    assert pb.pack_size("0702 馬達 4顆", {}) == 1


def row(title, price, rng=None):
    return {"id": "1", "title": title, "price_twd": price, "price_range": rng or [price, price], "sold_qty": 0}


LINE = {"must": "0702", "exclude": "有刷", "unit_price_band_twd": [120, 900], "packs": True}


def test_keep_rules():
    assert pb.keep(row("0702 無刷馬達 4顆", 2000), LINE) is None               # 500/unit
    assert "band" in pb.keep(row("0702 無刷馬達", 2000), LINE)                  # 2000/unit
    assert pb.keep(row("1102 無刷馬達", 400), LINE) == "title does not name the part"
    assert pb.keep(row("0702 有刷馬達", 400), LINE) == "excluded keyword"
    assert pb.keep(row("0702 故障 馬達", 400), LINE) == "excluded keyword"       # default exclusion: broken units
    assert pb.keep(row("0702 馬達", 993800), LINE) == "masked price"
    assert "variant" in pb.keep(row("0702 馬達", 400, [400, 9000]), LINE)


def test_used_listings_are_dropped_unless_the_line_allows_them():
    line = {"must": "ThinkPad", "unit_price_band_twd": [1000, 20000]}
    assert pb.keep(row("二手 ThinkPad T450", 3200), line) == "excluded keyword"
    assert pb.keep(row("二手 ThinkPad T450", 3200), {**line, "allow_used": True}) is None
    assert pb.keep(row("二手 ThinkPad 故障", 3200), {**line, "allow_used": True}) == "excluded keyword"  # broken still out


def test_allow_words_lifts_only_the_named_default_exclusion():
    line = {"must": "FZ-M1", "unit_price_band_twd": [3000, 40000], "allow_used": True}
    seller = row("大人的玩具 Panasonic Toughpad FZ-M1 三防平板", 7500)  # 玩具 (toy) is the seller's name here
    assert pb.keep(seller, line) == "excluded keyword"
    assert pb.keep(seller, {**line, "allow_words": ["玩具"]}) is None
    assert pb.keep(row("大人的玩具 FZ-M1 故障", 7500), {**line, "allow_words": ["玩具"]}) == "excluded keyword"


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return b'{"ok": 1}'


def test_get_retries_network_errors_but_not_http_errors(monkeypatch):
    import urllib.error
    calls = []

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.URLError("Temporary failure in name resolution")
        return _Resp()

    monkeypatch.setattr(pb.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(pb.time, "sleep", lambda s: None)
    assert pb.get("https://example.invalid", {}) == {"ok": 1} and len(calls) == 3

    calls.clear()

    def always_down(req, timeout):
        calls.append(1)
        raise urllib.error.URLError("down")

    monkeypatch.setattr(pb.urllib.request, "urlopen", always_down)
    with pytest.raises(urllib.error.URLError):
        pb.get("https://example.invalid", {})
    assert len(calls) == 3  # gives up after the last try

    calls.clear()

    def http_500(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError("u", 500, "err", {}, None)

    monkeypatch.setattr(pb.urllib.request, "urlopen", http_500)
    with pytest.raises(urllib.error.HTTPError):
        pb.get("https://example.invalid", {})
    assert len(calls) == 1  # a server answer is not retried


def priced(id_, qty, mn, p25, med, role="build", fixed=None):
    return {"id": id_, "qty": qty, "role": role, "spec": "", "listings_kept": 5, "fixed_price_twd": fixed,
            "unit_price_twd": {"min": mn, "p25": p25, "median": med}}


def test_compare_sums_build_lines_excludes_shared_and_flags_unpriced():
    lines = [priced("frame", 1, None, None, None, fixed=526), priced("motors", 4, 200, 500, 700),
             priced("radio", 1, 3000, 3000, 3000, role="shared")]
    alts = [{"id": "BNF", "spec": "", "listings_kept": 3, "unit_price_twd": {"min": 2800, "p25": 2950, "median": 4000}}]
    c = pb.compare({}, lines, alts)
    assert (c["build_min_twd"], c["build_p25_twd"], c["build_median_twd"]) == (1326, 2526, 3326)
    assert c["shared_lines_excluded_from_both_sides"] == {"radio": 3000}
    assert c["build_plus_shared_p25_twd"] == 2526 + 3000  # cost of goods when the shared line is bought too
    assert c["alternatives"][0]["build_minus_buy_p25_twd"] == 2526 - 2950
    c2 = pb.compare({}, lines + [priced("fc", 1, None, None, None)], alts)
    assert c2["build_p25_twd"] is None and c2["unpriced_build_lines"] == ["fc"]
    assert c2["build_plus_shared_p25_twd"] is None
    c3 = pb.compare({}, lines + [priced("io", 1, None, None, None, role="shared")], alts)
    assert c3["build_p25_twd"] == 2526 and c3["build_plus_shared_p25_twd"] is None  # unpriced shared line blocks COGS


@pytest.mark.parametrize("name", ["drone_whoop65.json", "cyberdeck_pi5.json"])
def test_product_files_are_well_formed(name):
    d = json.loads((ROOT / name).read_text())
    for line in d["lines"]:
        assert ("queries" in line) != ("fixed_price_twd" in line), line["id"]
        if "fixed_price_twd" in line:
            assert line["fixed_price_basis"], line["id"]  # every non-market number says where it came from
        else:
            lo, hi = line["unit_price_band_twd"]
            assert 0 < lo < hi
    assert d["buy_alternatives"], "a build price means nothing without the buy alternative"
