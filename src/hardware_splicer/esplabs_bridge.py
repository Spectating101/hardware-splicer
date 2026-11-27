"""The esp-labs lessons (MIT, agharsallah/esp-labs-web) as HS labs: their wiring checked against Espressif's datasheet.

esp-labs is a 32-lesson ESP32-S3 course for the ESP32-S3-DevKitC-1 with an N16R8 module. Each lesson lists the header pins
it wires and reports its own status ("works on your board", "built, not flashed"). HS imports that data unchanged and adds:

* each lesson's pins checked against the ESP32-S3-WROOM-1 datasheet: strapping pins, the pins an Octal-PSRAM module (R8)
  takes for its PSRAM, and the native USB pins;
* esp-labs' own status mapped onto HS's lab ladder, marked as esp-labs' report and not something HS observed;
* a cross-check of the board data HS also holds from WireStudio for the same DevKitC-1, where it disagrees with the datasheet.

    PYTHONPATH=src python -m hardware_splicer.esplabs_bridge
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "third_party" / "esp_labs"
SCHEMA = "hardware_splicer.esplabs_review.v1"
S3_DATASHEET = "https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf"
S3_FACTS = {
    "strapping": {
        "pins": {0, 3, 45, 46},
        "quote": "Chip boot mode – Strapping pin: GPIO0 and GPIO46 ... JTAG signal source – Strapping pin: GPIO3",
        "locator": "ESP32-S3-WROOM-1 datasheet v1.8, section Boot Configurations (GPIO45 sets the VDD_SPI voltage)",
    },
    "octal_psram": {
        "pins": {35, 36, 37},
        "quote": "pins IO35, IO36, and IO37 are connected to the Octal SPI PSRAM and are not available for other uses",
        "locator": "ESP32-S3-WROOM-1 datasheet v1.8, pin definitions, note b (modules with ESP32-S3R8 or ESP32-S3R16V)",
    },
    "usb": {
        "pins": {19, 20},
        "quote": "IO19 ... USB_D-; IO20 ... USB_D+",
        "locator": "ESP32-S3-WROOM-1 datasheet v1.8, pin definitions, pins 13 and 14",
    },
}
# esp-labs' status words, mapped to the HS lab ladder. Every rung here is esp-labs' own report.
STATUS_TO_RUNG = {"works on your board": "observed", "on board, works": "observed", "built, not flashed": "built_not_flashed"}


@lru_cache(maxsize=1)
def snapshot() -> dict[str, Any]:
    def load(name: str) -> Any:
        return json.loads((SNAPSHOT_DIR / f"{name}.json").read_text(encoding="utf-8"))

    return {"meta": load("SNAPSHOT"), "lessons": load("lessons"), "kit": load("kit")}


def _fact(name: str) -> str:
    fact = S3_FACTS[name]
    return f"{fact['locator']}: \"{fact['quote']}\" ({S3_DATASHEET})"


def review_lesson(lesson: dict[str, Any], *, octal_psram: bool = True) -> dict[str, Any]:
    pins = sorted({int(p["pin"]) for p in lesson.get("pins", []) if re.fullmatch(r"\d+", str(p.get("pin", "")))})
    roles = {int(p["pin"]): p.get("role", "") for p in lesson.get("pins", []) if re.fullmatch(r"\d+", str(p.get("pin", "")))}
    findings = []
    for pin in pins:
        if octal_psram and pin in S3_FACTS["octal_psram"]["pins"]:
            findings.append({"severity": "error", "rule": "pin_taken_by_octal_psram", "pin": pin,
                             "message": f"GPIO{pin} ({roles[pin]}) is wired to the module's Octal PSRAM on an R8 module and cannot be used.",
                             "basis": _fact("octal_psram")})
        if pin in S3_FACTS["usb"]["pins"]:
            findings.append({"severity": "warning", "rule": "pin_is_native_usb", "pin": pin,
                             "message": f"GPIO{pin} ({roles[pin]}) is a native USB data line; using it gives up the S3's USB port.",
                             "basis": _fact("usb")})
        if pin in S3_FACTS["strapping"]["pins"]:
            findings.append({"severity": "info", "rule": "strapping_pin", "pin": pin,
                             "message": f"GPIO{pin} ({roles[pin]}) is a strapping pin: whatever is wired to it must not pull it the wrong way at reset."
                             + (" On the DevKitC-1 GPIO0 is the BOOT button, so reading it after boot is the intended use." if pin == 0 else ""),
                             "basis": _fact("strapping")})
    status = lesson.get("status", "")
    rung = STATUS_TO_RUNG.get(status, "reported_other")
    return {"id": lesson["id"], "track": lesson.get("track"), "title": lesson.get("title"), "pins": pins, "findings": findings,
            "status": {"esp_labs_says": status, "ladder_rung": rung, "provenance": "esp-labs' own report, not observed by HS"}}


def board_data_disagreements() -> list[dict[str, Any]]:
    """Where WireStudio's ESP32-S3-DevKitC-1 board file, also imported into HS, misses a datasheet fact esp-labs follows."""
    from .wirestudio_bridge import snapshot as ws_snapshot

    caps = ws_snapshot()["boards"]["esp32-s3-devkitc-1"]["gpio_capabilities"]
    out = []
    for pin in sorted(S3_FACTS["strapping"]["pins"]):
        if "strap" not in caps.get(f"GPIO{pin}", []):
            out.append({"source": "WireStudio board esp32-s3-devkitc-1", "pin": pin, "missing": "strap tag",
                        "basis": _fact("strapping")})
    for pin in sorted(S3_FACTS["octal_psram"]["pins"]):
        tags = caps.get(f"GPIO{pin}")
        if tags is not None and "psram" not in tags:
            out.append({"source": "WireStudio board esp32-s3-devkitc-1", "pin": pin,
                        "missing": "no PSRAM reservation (matters only on R8 modules; the board file does not say which module)",
                        "basis": _fact("octal_psram")})
        elif tags is None:
            out.append({"source": "WireStudio board esp32-s3-devkitc-1", "pin": pin,
                        "missing": "pin absent from the board file, so its PSRAM use is not recorded", "basis": _fact("octal_psram")})
    return out


def lessons_for_kit(have: list[str]) -> dict[str, Any]:
    """esp-labs lessons ready with the kit on the bench, and those one item away (each `need` entry is a set of alternatives)."""
    kit = snapshot()["kit"]
    known = {item["id"] for item in kit["items"]}
    unknown = sorted(set(have) - known)
    if unknown:
        raise ValueError(f"not esp-labs kit items: {', '.join(unknown)} (known: {', '.join(sorted(known))})")
    owned, ready, one_away = set(have), [], []
    for lesson_id, entry in sorted(kit["lesson_kit"].items()):
        missing = [group for group in entry.get("need", []) if not owned & set(group)]
        row = {"lesson": lesson_id, "missing_one_of": missing}
        (ready if not missing else one_away if len(missing) == 1 else []).append(row)
    return {"have": sorted(owned), "ready": [r["lesson"] for r in ready], "one_item_away": one_away,
            "note": "esp-labs' own kit table; every lesson also needs the board and a USB-C data cable."}


def review_esplabs() -> dict[str, Any]:
    snap = snapshot()
    reviews = [review_lesson(lesson) for _, lesson in sorted(snap["lessons"].items())]
    rungs: dict[str, int] = {}
    for r in reviews:
        rungs[r["status"]["ladder_rung"]] = rungs.get(r["status"]["ladder_rung"], 0) + 1
    by_rule: dict[str, int] = {}
    for r in reviews:
        for f in r["findings"]:
            by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    return {"schema_version": SCHEMA, "lessons": len(reviews), "board": snap["meta"]["board"], "status_by_rung": rungs,
            "findings_by_rule": by_rule, "reviews": reviews, "board_data_disagreements": board_data_disagreements(),
            "snapshot": snap["meta"], "physical_correctness": "UNPROVEN",
            "note": "esp-labs' statuses are its own reports. HS checked pin choices against Espressif's datasheet only."}


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(review_esplabs(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
