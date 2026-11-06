#!/usr/bin/env python3
"""Price a parts list from current Ruten listings and compare BUILD against BUY.

Input: a product JSON (``drone_whoop65.json``, ``cyberdeck_pi5.json``) whose ``lines`` are the parts to buy and
whose ``buy_alternatives`` are finished products that do the same job. For every line and alternative the tool
searches Ruten (read-only, ~1 request/second), keeps listings whose title names the part and passes the
exclusions and price band, divides multi-packs ("4顆", "2入", "x4") into a unit price, and records the cheapest
listings so a human can open and check them.

Boundaries, stated once: these are ASKING prices on one platform on one day. A listing can be out of stock, a
different variant, or a cross-border item with long shipping. The output is a sourcing snapshot that a person
verifies before buying anything; it is not a quote and nothing is ordered.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEARCH = "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
DETAIL = "https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod"
UA = "HS-build-vs-buy/1 (single-user research snapshot; low volume)"
MASKED_PRICE_MIN = 100000  # seller-specific price masking (e.g. 993800): never treated as a price
DEFAULT_EXCLUDE = (r"故障|不開機|零件機|維修|報修|拆機|壞|瑕疵|二手|中古|福利品|展示|租|出租|收購|回收|代購|預購|"
                   r"貼紙|保護貼|保護殼|收納|包包|模型|玩具|教學|課程|說明書")
USED_WORDS = ("二手", "中古", "福利品", "展示")
PACK_WORD = re.compile(r"(?<![\d.])(\d{1,2})\s*(?:顆|個|入|支|片|只|pcs|PCS|pc)")
PACK_X = re.compile(r"(?<![\d.A-Za-z])[xX×]\s*(\d{1,2})(?!\d)(?!\s*(?:mm|cm|吋|V|mAh|G|K))")  # "x4" but not "M1.4x3"


def get(url: str, params: dict, tries: int = 3, backoff: float = 5.0) -> object:
    """One read-only request; a transient network error (DNS, reset, timeout) is retried with growing pauses."""
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            raise  # the server answered: a 4xx/5xx is not a network blip, so do not hammer it
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == tries:
                raise
            print(f"  network error ({e}); retry {attempt}/{tries - 1} in {backoff * attempt:.0f}s", flush=True)
            time.sleep(backoff * attempt)
    raise AssertionError("unreachable")


def pack_size(title: str, line: dict) -> int:
    """Units per listing. Only lines that declare ``packs: true`` are divided; others are one unit per listing."""
    if not line.get("packs"):
        return 1
    m = PACK_WORD.search(title) or PACK_X.search(title)  # spaces kept: "x4 1S" must not become "x41"
    n = int(m.group(1)) if m else 1
    return n if 1 <= n <= line.get("max_pack", 8) else 1


class Snapshot:
    def __init__(self, limit: int, sleep: float):
        self.limit, self.sleep, self.requests = limit, sleep, 0

    def listings(self, query: str) -> list[dict]:
        res = get(SEARCH, {"q": query, "type": "direct", "sort": "rnk/dc", "offset": 1, "limit": self.limit})
        self.requests += 1
        time.sleep(self.sleep)
        ids = [r["Id"] for r in res.get("Rows", [])][: self.limit]
        out = []
        for i in range(0, len(ids), 20):
            for d in get(DETAIL, {"id": ",".join(ids[i:i + 20])}):
                out.append({"id": d["ProdId"], "title": d["ProdName"], "price_twd": d["PriceRange"][0],
                            "price_range": d["PriceRange"], "sold_qty": d["SoldQty"], "stock": d.get("StockQty"),
                            "url": f"https://www.ruten.com.tw/item/{d['ProdId']}/"})
            self.requests += 1
            time.sleep(self.sleep)
        return out


def keep(row: dict, line: dict) -> str | None:
    """Reason to drop a listing, or None to keep it."""
    t = row["title"].replace(" ", "")
    if row["price_twd"] >= MASKED_PRICE_MIN:
        return "masked price"
    if not re.search(line["must"], t, re.I):
        return "title does not name the part"
    exclude = line.get("exclude", "")
    allowed = set(line.get("allow_words", ()))  # e.g. a seller named 大人的玩具 must not trip the 玩具 (toy) exclusion
    if line.get("allow_used"):  # e.g. a used-laptop baseline or a used donor: keep 二手/中古, still drop broken units
        allowed |= set(USED_WORDS)
    base = "|".join(w for w in DEFAULT_EXCLUDE.split("|") if w not in allowed)
    if re.search(base + (("|" + exclude) if exclude else ""), t, re.I):
        return "excluded keyword"
    lo, hi = line["unit_price_band_twd"]
    unit = row["price_twd"] / pack_size(row["title"], line)
    if not lo <= unit <= hi:
        return f"unit price {unit:.0f} outside band {lo}-{hi}"
    if row["price_range"][0] != row["price_range"][-1] and row["price_range"][-1] > hi * 3:
        return "variant listing: lowest variant is probably a different item"
    return None


def price_line(snap: Snapshot, line: dict) -> dict:
    rows, seen = [], set()
    for q in line["queries"]:
        for r in snap.listings(q):
            if r["id"] not in seen:
                seen.add(r["id"])
                rows.append(r)
    kept, dropped = [], {}
    for r in rows:
        why = keep(r, line)
        if why is not None:
            key = re.sub(r"\d+", "N", why)
            d = dropped.setdefault(key, {"count": 0, "examples": []})
            d["count"] += 1
            if len(d["examples"]) < 3:
                d["examples"].append(f"{r['price_twd']} | {r['title'][:60]}")
        if why is None:
            n = pack_size(r["title"], line)
            kept.append({**r, "pack": n, "unit_price_twd": round(r["price_twd"] / n, 1)})
    units = sorted(k["unit_price_twd"] for k in kept)
    p25 = statistics.quantiles(units, n=4)[0] if len(units) >= 4 else (units[0] if units else None)
    return {
        "id": line["id"], "qty": line.get("qty", 1), "role": line.get("role", "build"), "spec": line["spec"],
        "listings_seen": len(rows), "listings_kept": len(kept), "dropped": dropped,
        "unit_price_twd": {"min": units[0] if units else None, "p25": round(p25) if p25 else None,
                           "median": round(statistics.median(units)) if units else None},
        "with_sales": sum(1 for k in kept if k["sold_qty"]),
        "cheapest": sorted(kept, key=lambda k: k["unit_price_twd"])[:4],
        "fixed_price_twd": line.get("fixed_price_twd"), "fixed_price_basis": line.get("fixed_price_basis"),
    }


def line_cost(row: dict, which: str) -> float | None:
    if row["fixed_price_twd"] is not None:
        return row["fixed_price_twd"] * row["qty"]
    v = row["unit_price_twd"][which]
    return None if v is None else v * row["qty"]


def compare(product: dict, priced: list[dict], alts: list[dict]) -> dict:
    """BUILD total (p25 and median) vs each finished alternative's p25, for the same scope of use."""
    build = [r for r in priced if r["role"] == "build"]
    shared = [r for r in priced if r["role"] == "shared"]  # needed by build AND by the buy alternatives (radio, charger)
    out = {}
    for which in ("min", "p25", "median"):
        costs = [line_cost(r, which) for r in build]
        out[f"build_{which}_twd"] = None if any(c is None for c in costs) else round(sum(costs))
        both = costs + [line_cost(r, which) for r in shared]  # total cost of goods when the shared lines are bought too
        out[f"build_plus_shared_{which}_twd"] = None if any(c is None for c in both) else round(sum(both))
    out["unpriced_build_lines"] = [r["id"] for r in build if line_cost(r, "median") is None]
    out["shared_lines_excluded_from_both_sides"] = {r["id"]: line_cost(r, "median") for r in shared}
    rows = []
    for a in alts:
        p = a["unit_price_twd"]["p25"] or a["unit_price_twd"]["min"]
        rows.append({"alternative": a["id"], "spec": a["spec"], "buy_p25_twd": p, "listings_kept": a["listings_kept"],
                     "build_minus_buy_p25_twd": None if p is None or out["build_p25_twd"] is None else out["build_p25_twd"] - p})
    out["alternatives"] = rows
    return out


def run(product_path: Path, limit: int, sleep: float) -> dict:
    product = json.loads(product_path.read_text(encoding="utf-8"))
    snap = Snapshot(limit, sleep)
    priced = []
    for line in product["lines"]:
        if "queries" in line:
            priced.append(price_line(snap, line))
        else:
            priced.append({"id": line["id"], "qty": line.get("qty", 1), "role": line.get("role", "build"), "spec": line["spec"],
                           "listings_seen": 0, "listings_kept": 0, "unit_price_twd": {"min": None, "p25": None, "median": None},
                           "with_sales": 0, "cheapest": [], "fixed_price_twd": line["fixed_price_twd"],
                           "fixed_price_basis": line["fixed_price_basis"]})
        print(f"  line {priced[-1]['id']:<14} kept {priced[-1]['listings_kept']:>2}/{priced[-1]['listings_seen']:<3} "
              f"unit p25={priced[-1]['unit_price_twd']['p25']} med={priced[-1]['unit_price_twd']['median']} "
              f"fixed={priced[-1]['fixed_price_twd']}", flush=True)
    alts = []
    for a in product.get("buy_alternatives", []):
        alts.append(price_line(snap, a))
        print(f"  buy  {alts[-1]['id']:<14} kept {alts[-1]['listings_kept']:>2}/{alts[-1]['listings_seen']:<3} "
              f"p25={alts[-1]['unit_price_twd']['p25']} med={alts[-1]['unit_price_twd']['median']}", flush=True)
    return {"schema": "hs.build_vs_buy.v1", "product": product["product"], "source_design": product["source_design"],
            "captured_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "requests": snap.requests,
            "lines": priced, "buy_alternatives": alts, "comparison": compare(product, priced, alts),
            "boundary": "Ruten asking prices on one day; verify each cheapest listing by hand before buying. Nothing ordered."}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("product", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--sleep", type=float, default=1.0)
    a = ap.parse_args()
    res = run(a.product, a.limit, a.sleep)
    out = a.out or HERE / "evidence" / f"{a.product.stem}_{datetime.now().strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    c = res["comparison"]
    print(f"BUILD p25={c['build_p25_twd']} median={c['build_median_twd']} unpriced={c['unpriced_build_lines']} requests={res['requests']}")
    for r in c["alternatives"]:
        print(f"  vs {r['alternative']:<22} buy p25={r['buy_p25_twd']}  build-buy={r['build_minus_buy_p25_twd']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
