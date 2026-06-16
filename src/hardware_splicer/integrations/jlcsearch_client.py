"""JLC/LCSC parts search via jlcsearch.tscircuit.com JSON API."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional


DEFAULT_BASE = os.environ.get("HARDWARE_SPLICER_JLCSEARCH_BASE", "https://jlcsearch.tscircuit.com")

_MPN_SEARCH_CATEGORIES = (
    "microcontrollers",
    "mosfets",
    "diodes",
    "leds",
    "capacitors",
    "resistors",
)


@dataclass
class JlcSearchClient:
    base_url: str = DEFAULT_BASE
    timeout_s: float = 30.0

    def _get_json(self, path: str, params: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
        query = urllib.parse.urlencode(dict(params or {}))
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "hardware-splicer/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def search_resistors(
        self,
        *,
        resistance: str,
        package: str = "0603",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        data = self._get_json(
            "resistors/list.json",
            {"resistance": resistance, "package": package},
        )
        rows = list(data.get("resistors") or [])
        return rows[:limit]

    def search_capacitors(
        self,
        *,
        capacitance: str,
        package: str = "0603",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        data = self._get_json(
            "capacitors/list.json",
            {"capacitance": capacitance, "package": package},
        )
        rows = list(data.get("capacitors") or data.get("results") or [])
        return rows[:limit]

    def search_keyword(self, category_path: str, **params: str) -> List[Dict[str, Any]]:
        data = self._get_json(f"{category_path}/list.json", params)
        for key in ("results", "parts", "items"):
            if isinstance(data.get(key), list):
                return list(data[key])
        for value in data.values():
            if isinstance(value, list):
                return list(value)
        return []

    def search_by_mpn(self, mpn: str, *, limit: int = 1) -> Optional[Dict[str, Any]]:
        """Best-effort LCSC match by manufacturer part number substring."""
        needle = str(mpn or "").strip().lower()
        if len(needle) < 4:
            return None
        for category in _MPN_SEARCH_CATEGORIES:
            try:
                rows = self.search_keyword(category)
            except Exception:
                continue
            for row in rows:
                mfr = str(row.get("mfr") or row.get("mpn") or "").lower()
                if needle in mfr or mfr in needle:
                    return row
                if len(needle) >= 6 and needle[:6] in mfr:
                    return row
            if limit <= 0:
                break
        return None


def search_passives(
    *,
    resistance: Optional[str] = None,
    capacitance: Optional[str] = None,
    package: str = "0603",
) -> Dict[str, Any]:
    client = JlcSearchClient()
    out: Dict[str, Any] = {"package": package, "resistors": [], "capacitors": []}
    if resistance:
        out["resistors"] = client.search_resistors(resistance=resistance, package=package)
    if capacitance:
        out["capacitors"] = client.search_capacitors(capacitance=capacitance, package=package)
    return out
