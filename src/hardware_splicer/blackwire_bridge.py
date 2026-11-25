"""The Black Wire pinout collection (CC-BY-4.0, (c) Valleytech Solutions) in HS: boards, parts, and a second opinion on pins.

Black Wire transcribes board connectors from cited pinout images and lists maker parts with their pin labels. Each board
record says how it was transcribed (single-entry, double-entry, OCR-checked, partial); none of it is electrical
verification. HS uses it to:

* list 595 boards and 600 parts in the unified catalogue;
* compare the pin names of HS's cited Adafruit planner modules with Black Wire's labels for the same product, as an
  independent second reading. Names are compared after folding the usual spellings together (VIN/VCC, 3Vo/3V3/3.3V,
  Data/SDA, Clk/SCL, BAT/VBAT, and Adafruit's _5.0V net suffixes). A mismatch is a reason to look, not a verdict.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "third_party" / "black_wire"
ALIASES = {"VCC": "VIN", "VIN": "VIN", "3VO": "3V3", "3.3V": "3V3", "3V3": "3V3", "3V": "3V3", "DATA": "SDA", "CLK": "SCL",
           "SCK/SCL": "SCL", "SDI/SDA": "SDA", "BAT": "VBAT", "VBAT": "VBAT", "32KHZ": "32K", "!RTC_RST": "RST", "RTC_RST": "RST",
           "SDO/ADR": "SDO", "DC/SA0": "DC"}


@lru_cache(maxsize=1)
def snapshot() -> dict[str, Any]:
    def load(name: str) -> Any:
        return json.loads((SNAPSHOT_DIR / f"{name}.json").read_text(encoding="utf-8"))

    return {"meta": load("SNAPSHOT"), "boards": load("boards"), "parts": load("parts")}


def _fold(label: str) -> str:
    text = re.sub(r"_\d(\.\d)?V$", "", str(label).strip().upper())
    return ALIASES.get(text, text)


def _product_words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 2 and w not in {"adafruit", "stemma", "qwiic", "breakout", "product", "the", "and", "with"}}


def corroborate_planner_pins() -> list[dict[str, Any]]:
    """For each Adafruit planner module, the Black Wire Adafruit part with the same chip and the most shared name words."""
    from .device_plan import module_library

    parts = snapshot()["parts"]
    out = []
    for module in module_library()["modules"]:
        if "adafruit" not in module["name"].lower():
            continue
        chips = {re.sub(r"[^A-Z0-9]", "", c["marking"].upper()) for c in module.get("chips", [])}
        words = _product_words(module["name"])
        candidates = []
        for part_id, part in parts.items():
            controllers = {re.sub(r"[^A-Z0-9]", "", str(c).upper()) for c in part.get("controllers") or []}
            if (part.get("brand") or "").lower() == "adafruit" and chips & controllers:
                candidates.append((len(words & _product_words(part["name"])), part_id, part))
        if not candidates:
            out.append({"module": module["id"], "black_wire_part": None, "note": "no Adafruit part with this chip in Black Wire"})
            continue
        _, part_id, part = max(candidates, key=lambda c: (c[0], c[1]))
        ours = {_fold(p["name"]) for p in module["pins"]}
        theirs = {_fold(label) for label in part.get("pinLabels") or []}
        out.append({"module": module["id"], "black_wire_part": part_id, "black_wire_name": part["name"],
                    "agree": sorted(ours & theirs), "only_in_hs": sorted(ours - theirs), "only_in_black_wire": sorted(theirs - ours),
                    "black_wire_sources": part.get("sources", [])[:3]})
    return out


def catalog_rows() -> list[dict[str, Any]]:
    meta = snapshot()["meta"]
    rows = []
    for board_id, board in sorted(snapshot()["boards"].items()):
        rows.append({"id": f"blackwire:{board_id}", "label": board_id, "library": "black_wire", "category": board.get("category") or "board",
                     "capabilities": ["pinout"], "i2c_addresses": [], "sources": [meta["source"]],
                     "evidence": f"Black Wire transcription from cited images ({board.get('review')}), CC-BY-4.0; not electrical verification",
                     "pins": sum(len(c["pins"]) for c in board["connectors"])})
    for part_id, part in sorted(snapshot()["parts"].items()):
        rows.append({"id": f"blackwire:{part_id}", "label": part.get("name") or part_id, "library": "black_wire",
                     "category": part.get("category"), "capabilities": ["pin_labels"], "i2c_addresses": [],
                     "sources": part.get("sources") or [meta["source"]],
                     "evidence": "Black Wire maker-part record (pin labels, controller chips), CC-BY-4.0"})
    return rows
