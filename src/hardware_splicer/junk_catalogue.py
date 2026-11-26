"""Which discarded devices give the modules a design needs: HS's salvage-first step, before any new part is chosen.

``lookup(["drive_motors", "camera"])`` returns, for each capability, the devices that usually provide it (with what to
test first, the hazards and the price last seen), and the fewest donors that cover every need together. The catalogue
(``data/junk_devices.json``) records typical contents of whole devices; a donor's parts are unknown until it is opened
and tested, and nothing here approves using a salvaged part in a device.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent / "data" / "junk_devices.json"


@lru_cache(maxsize=1)
def catalogue() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _usable(device: dict[str, Any]) -> bool:
    return "always" not in device.get("skip_if", []) and bool(device.get("gives"))


def _price_low(device: dict[str, Any]) -> float:
    p = device.get("price_seen")
    return float(p["ntd"][0]) if p else float("inf")


def lookup(needs: list[str]) -> dict[str, Any]:
    cat = catalogue()
    known = cat["capabilities"]
    unknown = [n for n in needs if n not in known]
    if unknown:
        raise ValueError(f"unknown capabilities {unknown}; use one of {sorted(known)}")
    devices = [d for d in cat["devices"] if _usable(d)]
    per_need = {}
    for need in needs:
        hits = sorted((d for d in devices if need in d["gives"]), key=_price_low)
        per_need[need] = [{"device": d["id"], "name": d["name"], "gives": d["gives"][need], "price_seen": d.get("price_seen"),
                           "search_tw": d.get("search_tw", [])} for d in hits]
    # greedy cover: the donor giving the most still-missing needs (cheaper first on a tie)
    missing, plan = set(needs), []
    while missing:
        best = max(devices, key=lambda d: (len(missing & set(d["gives"])), -_price_low(d)))
        covered = missing & set(best["gives"])
        if not covered:
            break
        plan.append({"device": best["id"], "name": best["name"], "covers": sorted(covered), "hazards": best.get("hazards", []),
                     "first_tests": best.get("first_tests", []), "skip_if": best.get("skip_if", []),
                     "interfaces": best.get("interfaces", []), "reuse": best.get("reuse", []), "price_seen": best.get("price_seen"),
                     "search_tw": best.get("search_tw", [])})
        missing -= covered
    return {"schema": "hardware_splicer.junk_lookup.v1", "needs": needs, "by_need": per_need, "donor_plan": plan,
            "not_covered_by_junk": sorted(missing), "rule": cat["rule"]}
