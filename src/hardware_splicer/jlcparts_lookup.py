"""JLCPCB/LCSC parts, stock and prices from the jlcparts public tables (https://github.com/yaqwsx/jlcparts, MIT).

    python -m hardware_splicer.jlcparts_lookup "FT232RL" "SN74AHCT1G125DBVR" [--qty 5]

jlcparts republishes JLCPCB's parts list daily as small static files: a search index (one line per part: LCSC code,
data shard, lower-case search text) and per-category shards (one JSON array per part). This module downloads the index
and only the shards a query needs into a local cache, so pricing a board costs a few megabytes and no account. Nothing
here is stored in the repository; the cache is regenerable.

A record is ``[lcsc, mpn, _, description, datasheet, price_tiers, _, _, attribute_ids, stock, subcategory_id]``.
Prices are JLCPCB's in USD per unit by quantity break, as published on the manifest's ``created`` date.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterable

BASE = "https://yaqwsx.github.io/jlcparts/data"
SOURCE = "JLCPCB parts list via jlcparts (https://github.com/yaqwsx/jlcparts)"


def cache_dir() -> Path:
    root = os.environ.get("HARDWARE_SPLICER_TMP_ROOT") or str(Path(__file__).resolve().parents[2] / ".cache" / "hardware-splicer")
    path = Path(root) / "jlcparts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get(name: str, refresh: bool = False) -> Path:
    path = cache_dir() / name
    if refresh or not path.is_file():
        req = urllib.request.Request(f"{BASE}/{name}", headers={"User-Agent": "hardware-splicer-jlcparts"})
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 - fixed https host
            data = resp.read()
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)
    return path


def manifest(refresh: bool = False) -> dict[str, Any]:
    return json.loads(_get("manifest.json", refresh).read_text())


def _index_rows(refresh: bool = False) -> Iterable[tuple[str, str, str]]:
    with gzip.open(_get(manifest(refresh)["searchIndex"], refresh), "rt", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) == 3:
                yield parts[0], parts[1], parts[2]


def _record(lcsc: str, shard: str) -> dict[str, Any] | None:
    with gzip.open(_get(shard), "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(f'["{lcsc}"'):
                r = json.loads(line)
                return {"lcsc": r[0], "mpn": r[1], "description": r[3], "datasheet": r[4],
                        "price_tiers": r[5] or [], "stock": r[9] if len(r) > 9 else None}
    return None


def unit_price(tiers: list[dict[str, Any]], qty: int) -> float | None:
    for t in tiers:
        if t["qFrom"] <= qty and (t["qTo"] is None or qty <= t["qTo"]):
            return t["price"]
    return tiers[-1]["price"] if tiers else None


def search(query: str, *, limit: int = 5, qty: int = 1, rows: list[tuple[str, str, str]] | None = None) -> list[dict[str, Any]]:
    """Parts whose search text contains every word of the query, exact manufacturer-number matches first, then by stock."""
    words = query.lower().split()
    hits = [(lcsc, shard) for lcsc, shard, text in (rows or _index_rows()) if all(w in text for w in words)]
    out = []
    for lcsc, shard in hits[:200]:
        rec = _record(lcsc, shard)
        if rec:
            rec["unit_price_usd"] = unit_price(rec["price_tiers"], qty)
            rec["exact_mpn"] = rec["mpn"].lower() == query.lower()
            out.append(rec)
    out.sort(key=lambda r: (not r["exact_mpn"], -(r["stock"] or 0)))
    return out[:limit]


def price_bom(lines: list[dict[str, Any]], *, boards: int = 1) -> dict[str, Any]:
    """Each line: {"refs": [...], "query": "<MPN or words>", "qty_per_board": n} or {"lcsc": "C8690", ...}.
    Picks the exact MPN if present, else the best-stocked match, and prices it at the total quantity."""
    rows = list(_index_rows())
    by_code = {lcsc: shard for lcsc, shard, _ in rows}
    priced, total, missing = [], 0.0, []
    for line in lines:
        qty = line.get("qty_per_board", len(line.get("refs", [])) or 1) * boards
        if line.get("lcsc"):
            rec = _record(line["lcsc"], by_code[line["lcsc"]]) if line["lcsc"] in by_code else None
            if rec:
                rec["unit_price_usd"] = unit_price(rec["price_tiers"], qty)
                rec["match"] = "lcsc_code"
        else:
            found = search(line["query"], limit=1, qty=qty, rows=rows)
            rec = found[0] if found else None
            if rec:
                # A keyword hit can be the wrong part (a "yellow" query matched a white LED with a yellow lens): say so.
                rec["match"] = "exact_mpn" if rec["exact_mpn"] else "keyword, check the description"
        if not rec or rec["unit_price_usd"] is None:
            missing.append(line)
            continue
        ext = rec["unit_price_usd"] * qty
        total += ext
        priced.append({**{k: line[k] for k in line if k != "qty_per_board"}, "qty": qty, "lcsc": rec["lcsc"], "mpn": rec["mpn"],
                       "stock": rec["stock"], "match": rec["match"], "unit_usd": rec["unit_price_usd"], "extended_usd": round(ext, 4),
                       "description": rec["description"][:120]})
    return {"boards": boards, "lines": priced, "parts_total_usd": round(total, 2), "per_board_usd": round(total / boards, 2),
            "not_found": missing, "source": SOURCE, "prices_as_of": manifest().get("created"),
            "claim_boundary": "JLCPCB unit prices for the parts only: no PCB, assembly, setup, shipping or tax."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("query", nargs="+")
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--limit", type=int, default=3)
    args = ap.parse_args(argv)
    rows = list(_index_rows())
    for q in args.query:
        for r in search(q, limit=args.limit, qty=args.qty, rows=rows):
            print(f"{q:24s} {r['lcsc']:9s} {r['mpn'][:28]:28s} stock {r['stock']!s:>8s}  ${r['unit_price_usd']}  {r['description'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
