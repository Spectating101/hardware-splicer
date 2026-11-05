#!/usr/bin/env python3
"""Snapshot Ruten (露天) listings for used-desktop resale comparables.

Read-only, low volume (<= ~25 requests, 1 s apart) against the same public JSON
endpoints the site's own search page uses. Records asking price AND the listing's
cumulative ``SoldQty`` so that "someone has bought at about this price" can be told
apart from "someone asks this price". Neither is a realized-margin claim:
  * SoldQty is cumulative per listing with no sale dates or prices per sale;
  * a listing's price may have changed since sales occurred;
  * a platform search returns what its ranking surfaces, not a random sample.
The output is a *price-basis snapshot* for the economics model, nothing more.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEARCH = "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
DETAIL = "https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod"
UA = "HS-market-comps/1 (single-user research snapshot; low volume)"

CLASSES = {
    "domestic_used_desktop_i5": {
        "queries": ["二手 桌機 i5", "i5 8500 二手 主機", "二手 商用電腦 主機", "二手 OptiPlex", "二手 EliteDesk",
                    "二手 ThinkCentre M720"],
        "must": r"i5|i7|8[3-6]00|9[3-6]00|7[3-6]00|6[3-6]00",
        "note": "short domestic-style queries; long spec queries mostly surface cross-border listings (see README)"},
}
MASKED_PRICE_MIN = 100000  # seller-specific price masking (e.g. 993800); NOT decoded here, flagged for a human
EXCLUDE = re.compile(r"準系統|空機|無CPU|無記憶體|無硬碟|主機板|主機殼|機殼|風扇|散熱|電源供應|變壓器|CPU\s*單|單賣|"
                     r"零件|故障|報修|維修|不開機|不過電|無法開機|壞|拆機|螢幕|筆電|筆記型|伺服器|工作站|貼紙|配件", re.I)


def get(url: str, params: dict) -> object:
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def exclusion_reason(r: dict, c: dict) -> str | None:
    t = r["title"].replace(" ", "")
    if r["price_twd"] >= MASKED_PRICE_MIN:
        return "masked/variant price >= 100000: open the listing to read the real price"
    if EXCLUDE.search(t):
        return "excluded keyword: " + EXCLUDE.search(t).group(0)
    if not re.search(c["must"], t, re.I):
        return "title does not name target CPU class"
    if not 1000 <= r["price_twd"] <= 20000:
        return "price outside 1,000-20,000 TWD sanity band"
    return None


def snapshot(limit: int = 40, sleep: float = 1.0) -> dict:
    out = {"schema": "hs.market_comps.v1", "captured_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "source": "ruten.com.tw public search/detail JSON", "classes": {}, "requests": 0}
    for cname, c in CLASSES.items():
        seen, rows = set(), []
        for q in c["queries"]:
            res = get(SEARCH, {"q": q, "type": "direct", "sort": "rnk/dc", "offset": 1, "limit": limit})
            out["requests"] += 1
            time.sleep(sleep)
            ids = [r["Id"] for r in res.get("Rows", []) if r["Id"] not in seen]
            seen.update(ids)
            for i in range(0, len(ids), 20):
                det = get(DETAIL, {"id": ",".join(ids[i:i + 20])})
                out["requests"] += 1
                time.sleep(sleep)
                for d in det:
                    rows.append({"id": d["ProdId"], "title": d["ProdName"], "price_twd": d["PriceRange"][0],
                                 "sold_qty": d["SoldQty"], "post_time": d.get("PostTime"), "stock": d.get("StockQty"),
                                 "shipping_twd": d.get("ShippingCost"), "query": q})
        keep, drop = [], []
        for r in rows:
            reason = exclusion_reason(r, c)
            (drop if reason else keep).append({**r, "excluded_reason": reason} if reason else r)
        prices = sorted(r["price_twd"] for r in keep)
        sold = sorted(r["price_twd"] for r in keep if r["sold_qty"] and r["sold_qty"] > 0)
        q = (lambda v, p: round(statistics.quantiles(v, n=4)[p]) if len(v) >= 4 else None)
        out["classes"][cname] = {
            "note": c["note"], "queries": c["queries"], "listings_fetched": len(rows), "kept": len(keep),
            "excluded": len(drop),
            "ask_twd": {"n": len(prices), "min": prices[0] if prices else None, "p25": q(prices, 0),
                        "median": round(statistics.median(prices)) if prices else None, "p75": q(prices, 2)},
            "listings_with_sales": {"n": len(sold), "min": sold[0] if sold else None,
                                    "median": round(statistics.median(sold)) if sold else None,
                                    "total_units_sold_cumulative": sum(r["sold_qty"] for r in keep)},
            "kept_listings": keep, "excluded_listings": drop,
            "basis": "asking prices; listings_with_sales shows demand exists near those prices but is NOT a realized-margin figure"}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "evidence" / "market_comps_20261105.json")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    snap = snapshot(a.limit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"requests={snap['requests']}")
    for k, v in snap["classes"].items():
        print(f"{k}: kept {v['kept']}/{v['listings_fetched']}  ask median={v['ask_twd']['median']} "
              f"p25={v['ask_twd']['p25']} p75={v['ask_twd']['p75']}  with-sales n={v['listings_with_sales']['n']} "
              f"median={v['listings_with_sales']['median']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
