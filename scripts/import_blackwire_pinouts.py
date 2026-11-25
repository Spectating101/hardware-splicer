"""Refresh HS's snapshot of the Black Wire pinout collection (CC-BY-4.0, valleytechsolutions/black-wire-pinouts).

    python scripts/import_blackwire_pinouts.py <dir with catalog/*.json and LICENSE> <40-hex commit>

The collection transcribes board connectors from cited pinout images (each record says how: single-entry, double-entry,
OCR-checked, partial) and lists maker parts with their pin labels and controller chips. HS keeps the pin data, review
level and image hashes, without the images, under the collection's CC-BY-4.0 licence with attribution to Valleytech
Solutions. Values are unchanged.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/third_party/black_wire"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"[0-9a-f]{40}", argv[1]):
        print(__doc__, file=sys.stderr)
        return 2
    src, commit = Path(argv[0]), argv[1]
    cat = src / "catalog"
    connectors = json.loads((cat / "board-connectors.json").read_text(encoding="utf-8"))
    devices = {d["boardId"]: d for d in json.loads((cat / "devices.json").read_text(encoding="utf-8"))["records"]}
    boards = {}
    for record in connectors["records"]:
        boards[record["recordId"]] = {
            "method": record.get("method"), "review": record.get("review"), "transcribed": record.get("transcribed"),
            "category": devices.get(record["recordId"], {}).get("category"),
            "image_sha256": [i.get("sha256") for i in record.get("images", []) if i.get("sha256")],
            "connectors": [{"id": c.get("id"), "name": c.get("name"), "rows": c.get("rows"),
                            "pins": [{"position": p.get("position"), "label": p.get("label"), "functions": p.get("functions", [])}
                                     for p in c.get("pins", [])]} for c in record.get("connectors", [])],
        }
    refs = json.loads((cat / "pin-references.json").read_text(encoding="utf-8"))
    parts = {}
    for part in json.loads((cat / "maker-parts.json").read_text(encoding="utf-8"))["parts"]:
        sources = sorted({r["source"]["url"] for r in refs.get(part["id"], []) if isinstance(r.get("source"), dict) and r["source"].get("url")})
        parts[part["id"]] = {k: part.get(k) for k in ("name", "brand", "category", "controllers", "pinLabels", "completePhysicalPinout",
                                                       "documentationStatus", "revision")} | {"sources": sources}
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / "LICENSE", OUT / "LICENSE")
    (OUT / "boards.json").write_text(json.dumps(boards, indent=None, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    (OUT / "parts.json").write_text(json.dumps(parts, indent=None, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    (OUT / "SNAPSHOT.json").write_text(json.dumps({
        "source": "https://github.com/valleytechsolutions/black-wire-pinouts", "commit": commit,
        "license": "CC-BY-4.0 (see LICENSE in this folder)",
        "attribution": "Black Wire Maker's Technical Reference Guide pinout collection, (c) Valleytech Solutions, CC BY 4.0. "
                       "Reduced by Hardware-Splicer to pin data, review levels and image hashes; images not included.",
        "counts": {"boards": len(boards), "pin_rows": sum(len(c["pins"]) for b in boards.values() for c in b["connectors"]), "parts": len(parts)},
        "scope_note": connectors.get("scope"),
    }, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"boards": len(boards), "parts": len(parts)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
