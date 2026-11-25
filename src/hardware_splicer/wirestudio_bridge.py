"""Review WireStudio designs with HS's electrical checks, using WireStudio's own part data (MIT, pinned snapshot).

WireStudio (github.com/moellere/WireStudio) turns a design.json into firmware, wiring, KiCad and an enclosure. Its part
files record each pin's voltage and each part's supply range, but its validator does not compare them with the design. HS
does that here:

* ``five_volt_signal_into_mcu``: a part pin that drives a voltage above the board's I/O limit into an MCU pin, with no level
  shifter or divider in the design;
* ``supply_outside_part_range``: a part on a rail outside the supply range its part file states;
* ``led_data_below_vih``: a WS2812-family strip powered at 5 V and fed 3.3 V data;
* ``part_file_disagrees_with_maker``: a WireStudio part file that disagrees with the maker's datasheet, listed with the quote.

Each finding names its basis: an HS-cited datasheet where HS has one, otherwise WireStudio's own part data, said plainly.
Parts a board carries itself (an onboard LED, the ESP32-CAM's camera) are skipped: they are the board maker's design, not
the user's wiring. The snapshot is WireStudio's data unchanged; nothing here edits it, and nothing approves building.

    PYTHONPATH=src python -m hardware_splicer.wirestudio_bridge [design.json ...]   # no arguments: every bundled example
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .device_plan import module_library

SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "third_party" / "wirestudio"
SCHEMA = "hardware_splicer.wirestudio_review.v1"
BOUNDARY = ("HS's checks over a WireStudio design and WireStudio's own part data. A finding is a reason to look, with its basis; "
            "no finding is not a pass, and nothing here was built or measured.")
MCU_INPUT_KINDS = {"digital_in", "analog_in", "uart_rx", "i2c_sda", "i2c_scl"}
SHIFTERS = {"level_shifter", "voltage_divider"}
LED_PARTS = {"ws2812b", "esp32_rmt_led_strip"}
WS2812B_DATASHEET = "https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf"
# Boards that carry a part WireStudio models as a component, where the board file does not list it as an onboard peripheral.
ONBOARD_BY_BOARD = {"esp32cam-ai-thinker": {"esp32_camera"}, "esp32-wrover-cam": {"esp32_camera"}}
# WireStudio part files that disagree with the maker's datasheet. Each carries the maker's words and where they are.
PART_FILE_ERRATA = {
    "ld2420": {
        "field": "electrical.vcc_min / vcc_max",
        "maker_value": "3.0 V to 3.6 V (3.3 V typical)",
        "vcc_range": (3.0, 3.6),
        "quote": "The power supply input voltage range is 3.0 V~3.6 V",
        "locator": "HLK-LD2420 User Manual V1.0 (Shenzhen Hi-Link, 24 Feb 2023), Power Supply Notes; also the spec table: Supply voltage 3.0 3.3 3.6 V",
        "source": "https://www.elemon.com.ar/images/productos/hojas-de-datos/radar-modulos/hlk-ld2420.pdf",
        "consequence": "A tool that picks the rail from WireStudio's range would put this 3.3 V radar on 5 V.",
    },
}


@lru_cache(maxsize=1)
def snapshot() -> dict[str, Any]:
    def load(name: str) -> Any:
        return json.loads((SNAPSHOT_DIR / f"{name}.json").read_text(encoding="utf-8"))

    return {"meta": load("SNAPSHOT"), "components": load("components"), "boards": load("boards"), "examples": load("examples")}


def _esp32_basis() -> str:
    esp = next(m for m in module_library()["modules"] if m["id"] == "esp32-devkitc-v4")
    return esp["electrical"]["input_high_basis"]


def _onboard(board: dict[str, Any], board_id: str, component: dict[str, Any], connections: list[dict[str, Any]]) -> bool:
    if component["library_id"] in ONBOARD_BY_BOARD.get(board_id, set()):
        return True
    onboard_pins = set()
    for peripheral in (board.get("onboard_peripherals") or {}).values():
        if isinstance(peripheral, dict):
            onboard_pins |= {v for v in peripheral.values() if isinstance(v, str) and v.startswith("GPIO")}
    pins = {c["target"].get("pin") for c in connections if c["component_id"] == component["id"] and c["target"].get("kind") == "gpio"}
    return bool(pins) and pins <= onboard_pins


def review_design(design: dict[str, Any]) -> dict[str, Any]:
    snap = snapshot()
    board_id = design.get("board", {}).get("library_id")
    board = snap["boards"].get(board_id)
    if board is None:
        raise ValueError(f"board {board_id!r} is not in the WireStudio snapshot")
    rails = {r["name"]: r.get("voltage") for r in board.get("rails", [])}
    chip = board.get("chip_variant") or board.get("mcu")
    components = {c["id"]: c for c in design.get("components", [])}
    connections = design.get("connections", [])
    used_ids = {c["library_id"] for c in components.values()}
    has_shifter = bool(used_ids & SHIFTERS)
    findings: list[dict[str, Any]] = []

    own_warnings = [w for w in design.get("warnings", []) if isinstance(w, dict) and isinstance(w.get("text"), str)]

    def finding(severity: str, rule: str, component: str, message: str, basis: str, mentions: tuple[str, ...] = (), **extra: Any) -> None:
        # A design may already carry a hand-written warning about the same thing; say so instead of presenting it as new.
        known = next((w for w in own_warnings if any(m and m.lower() in w["text"].lower() for m in mentions)), None)
        row = {"severity": severity, "rule": rule, "component": component, "message": message, "basis": basis, **extra}
        if known:
            row["design_already_warns"] = {"code": known.get("code"), "text": known["text"]}
        findings.append(row)

    io_limit = 3.6  # VDD 3.3 V + 0.3 V, the ESP32 figure HS cites
    for comp in components.values():
        part = snap["components"].get(comp["library_id"]) or {}
        electrical = part.get("electrical") or {}
        if _onboard(board, board_id, comp, connections):
            continue
        pins = {p["role"]: p for p in electrical.get("pins", []) if isinstance(p, dict)}
        rail = next((c["target"]["rail"] for c in connections if c["component_id"] == comp["id"]
                     and c["target"].get("kind") == "rail" and pins.get(c["pin_role"], {}).get("kind") == "power"), None)
        rail_v = rails.get(rail)
        for conn in connections:
            if conn["component_id"] != comp["id"] or conn["target"].get("kind") not in ("gpio", "bus"):
                continue
            pin = pins.get(conn["pin_role"], {})
            volts = pin.get("voltage")
            if pin.get("kind") in MCU_INPUT_KINDS and isinstance(volts, (int, float)) and volts > io_limit and not has_shifter:
                target = conn["target"].get("pin") or conn["target"].get("bus_id")
                if chip == "esp32":
                    basis = f"{_esp32_basis()} (VDD 3.3 V, so 3.6 V); the {volts:g} V level is WireStudio's part file"
                else:
                    basis = (f"WireStudio's part file gives {volts:g} V on this pin; HS has no cited input limit for the {chip} yet, "
                             f"and the part file's own note says: {str(part.get('notes', '')).strip()[:160]}")
                finding("error", "five_volt_signal_into_mcu", comp["id"],
                        f"{comp['id']} ({comp['library_id']}) {conn['pin_role']} drives {volts:g} V into {target} of the {chip} board, and the "
                        "design has no level shifter or divider.", basis, mentions=(str(target), str(conn["pin_role"])))
        vmin, vmax = electrical.get("vcc_min"), electrical.get("vcc_max")
        range_basis = "WireStudio's part file (electrical.vcc_min, vcc_max) and board file (rails)"
        erratum = PART_FILE_ERRATA.get(comp["library_id"])
        if erratum:  # the maker's range replaces the part file's wrong one
            (vmin, vmax), range_basis = erratum["vcc_range"], f"{erratum['locator']} ({erratum['source']})"
        stated = isinstance(vmin, (int, float)) and isinstance(vmax, (int, float)) and vmax > 0  # 0 to 0 V means no range given
        if rail_v is not None and stated and not vmin <= rail_v <= vmax:
            finding("warning", "supply_outside_part_range", comp["id"],
                    f"{comp['id']} ({comp['library_id']}) is on the {rail} rail ({rail_v:g} V) but its range is {vmin:g} to {vmax:g} V."
                    + ("" if erratum else " The range may be the bare chip's rather than the module's; check the module you have."),
                    range_basis)
        if comp["library_id"] in LED_PARTS and rail_v is not None and rail_v >= 4.5 and not has_shifter:
            chipset = str((comp.get("params") or {}).get("chipset", "WS2812")).upper()
            if chipset in {"WS2812", "WS2812B"}:
                finding("warning", "led_data_below_vih", comp["id"],
                        f"{comp['id']} is a {chipset} strip on {rail_v:g} V; its data input needs 0.7 x {rail_v:g} = {0.7 * rail_v:.2f} V for a high, "
                        "above a 3.3 V GPIO. Many strips work anyway; a level shifter or a first LED at lower voltage makes it reliable.",
                        f"WS2812B datasheet, Electrical Characteristics: VIH DIN 0.7VDD ({WS2812B_DATASHEET})")
            else:
                finding("info", "led_data_below_vih", comp["id"],
                        f"{comp['id']} is a {chipset} strip on {rail_v:g} V fed from a 3.3 V GPIO; HS has no cited input threshold for the {chipset}.",
                        "no cited datasheet for this chipset in HS")
        if comp["library_id"] in PART_FILE_ERRATA:
            erratum = PART_FILE_ERRATA[comp["library_id"]]
            finding("warning", "part_file_disagrees_with_maker", comp["id"],
                    f"WireStudio's {comp['library_id']} part file states {erratum['field']} that the maker's datasheet contradicts: "
                    f"{erratum['maker_value']}. {erratum['consequence']}",
                    f"{erratum['locator']}: \"{erratum['quote']}\" ({erratum['source']})")
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("error", "warning", "info")}
    counts["already_warned_by_design"] = sum("design_already_warns" in f for f in findings)
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "design": design.get("id") or design.get("name"), "board": board_id,
            "chip": chip, "findings": findings, "counts": counts, "physical_correctness": "UNPROVEN",
            "snapshot": {"source": snap["meta"]["source"], "commit": snap["meta"]["commit"]}}


def review_examples() -> dict[str, Any]:
    reviews = [review_design(design) for _, design in sorted(snapshot()["examples"].items())]
    flagged = [r for r in reviews if r["findings"]]
    by_rule: dict[str, int] = {}
    new = 0
    for review in reviews:
        for f in review["findings"]:
            by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
            new += "design_already_warns" not in f
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "designs": len(reviews), "designs_with_findings": len(flagged),
            "findings_by_rule": dict(sorted(by_rule.items())), "findings_not_already_in_the_designs": new, "reviews": flagged,
            "part_file_errata": PART_FILE_ERRATA, "snapshot": snapshot()["meta"]}


def generate_with_wirestudio(design: dict[str, Any], out_dir: Path, *, timeout_s: float = 120.0) -> dict[str, Any]:
    """ESPHome YAML and an ASCII wiring diagram from WireStudio itself, when a WireStudio install is configured.

    HS does not bundle WireStudio's code. Point ``HS_WIRESTUDIO_GENERATE`` at its ``wirestudio-generate`` command (from
    ``pip install wirestudio`` in its own environment). The design is reviewed by HS first; the files are WireStudio's
    output, unchanged, and generating them approves nothing.
    """
    import os
    import subprocess
    import tempfile

    review = review_design(design)
    command = os.environ.get("HS_WIRESTUDIO_GENERATE", "").strip()
    if not command:
        return {"generated": False, "reason": "HS_WIRESTUDIO_GENERATE is not set; install WireStudio and point it at wirestudio-generate",
                "review": review}
    if not Path(command).is_file():
        return {"generated": False, "reason": f"{command} does not exist", "review": review}
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "design.json"
        spec.write_text(json.dumps(design), encoding="utf-8")
        yaml_path, ascii_path = out_dir / "esphome.yaml", out_dir / "wiring.txt"
        try:
            run = subprocess.run([command, str(spec), "--out-yaml", str(yaml_path), "--out-ascii", str(ascii_path)],
                                 capture_output=True, text=True, timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            return {"generated": False, "reason": f"wirestudio-generate took longer than {timeout_s:g} s", "review": review}
    ok = run.returncode == 0 and yaml_path.is_file()
    return {"generated": ok, "files": sorted(p.name for p in out_dir.iterdir()) if ok else [], "review": review,
            "wirestudio_messages": (run.stderr or "").strip().splitlines()[-20:],
            **({} if ok else {"reason": f"wirestudio-generate exited {run.returncode}"})}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        out = review_examples() if not args else [review_design(json.loads(Path(a).read_text(encoding="utf-8"))) for a in args]
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
