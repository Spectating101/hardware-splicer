"""Optional offline verification of downloaded Prusa source PDF bytes and values.

Usage: python eval/chemical_materials/verify_prusa_tds.py /tmp/hs_chemical_tds_20261020
This does NOT retrieve PDFs automatically, trust URLs as proof, or validate
the suitability of materials for any operating conditions.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader
from prusa_enclosure_screen_v1 import SOURCES

FILENAMES = {
    "asa": "prusament_asa.pdf",
    "pc_blend": "prusament_pc_blend.pdf",
}


def verify_source_files(directory: Path) -> dict:
    records: list[dict] = []
    for key, source in SOURCES.items():
        file = directory / FILENAMES[key]
        if not file.is_file():
            records.append({"material": key, "ok": False, "error": "source_file_missing"})
            continue
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        correct_digest = digest == source["sha256"]
        try:
            reader = PdfReader(str(file))
            # Printed PDF page 2 has index 1.
            text = reader.pages[1].extract_text()
            parsed = {}
            for load, measured in source["heat_deflection_c"].items():
                pattern = (r"Heat\s+Deflection\s+Temperature\s+"
                           r"\(" + f"{load:.2f}" + r"\s*MPa\)\s*"
                           r"\[°C\]\s*([0-9]+)\s+ISO\s+75")
                match = re.search(pattern, text)
                parsed[str(load)] = int(match.group(1)) if match else None
            correct_values = all(
                parsed[str(load)] == measured
                for load, measured in source["heat_deflection_c"].items()
            )
        except (ValueError, IndexError) as exc:
            correct_values = False
            parsed = {"parse_error": str(exc)[:200]}
        records.append({
            "material": key,
            "ok": correct_digest and correct_values,
            "pdf_sha256_matches_pinned": correct_digest,
            "manufacturer_iso75_values_match": correct_values,
            "parsed_hdt_c": parsed,
            "source_url": source["url"],
            "file_path": str(file),
        })
    return {
        "source_count": len(records),
        "verified_count": sum(record["ok"] for record in records),
        "results": records,
        "scope": "PDF version/hash and table transcription check only; no material qualification.",
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_prusa_tds.py <offline-pdf-directory>")
    report = verify_source_files(Path(sys.argv[1]))
    print(json.dumps(report, indent=2))
    if report["verified_count"] != report["source_count"]:
        raise SystemExit(1)
