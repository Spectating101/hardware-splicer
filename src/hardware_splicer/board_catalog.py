"""Microcontroller boards from PlatformIO's board definitions (Apache-2.0, pinned snapshot), and checks that use them.

PlatformIO describes several hundred ESP32, ESP8266, AVR and RP2040 boards: chip, clock, flash, RAM, radios and, for ESP32
boards, the PSRAM memory type its Arduino build uses. HS reads that to:

* list the boards in the unified part catalogue;
* know whether a board carries Octal SPI PSRAM, which takes GPIO35 to GPIO37 on an ESP32-S3 module (Espressif's datasheet);
* cross-check the board data HS holds from WireStudio against PlatformIO's for the same board.

PlatformIO's values are the toolchain's settings, not measurements; nothing here approves a board for anything.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "third_party" / "platformio"
OCTAL_MEMORY_TYPES = {"qio_opi", "opi_opi"}


@lru_cache(maxsize=1)
def snapshot() -> dict[str, Any]:
    return {"meta": json.loads((SNAPSHOT_DIR / "SNAPSHOT.json").read_text(encoding="utf-8")),
            "boards": json.loads((SNAPSHOT_DIR / "boards.json").read_text(encoding="utf-8"))}


def find_board(platformio_id: str) -> dict[str, Any] | None:
    """A board by its PlatformIO id (``esp32dev``), whatever platform it belongs to."""
    boards = snapshot()["boards"]
    return next((b for key, b in sorted(boards.items()) if key.split(":", 1)[1] == platformio_id), None)


def octal_psram(board: dict[str, Any] | None) -> bool | None:
    """True or False from PlatformIO's memory type; None when PlatformIO does not say (most boards)."""
    if not board or board.get("mcu") != "esp32s3":
        return None
    memory = board.get("memory_type")
    if memory is None:
        return None
    return memory in OCTAL_MEMORY_TYPES


def _mb(text: Any) -> float | None:
    m = re.match(r"([\d.]+)\s*MB", str(text or ""), re.I)
    return float(m.group(1)) if m else None


def wirestudio_board_disagreements() -> list[dict[str, Any]]:
    """WireStudio board files compared with the PlatformIO board each names (its ``platformio_board``)."""
    from .wirestudio_bridge import snapshot as ws_snapshot

    out = []
    for ws_id, ws_board in sorted(ws_snapshot()["boards"].items()):
        pio_id = ws_board.get("platformio_board")
        pio = find_board(pio_id) if pio_id else None
        if pio is None:
            out.append({"wirestudio_board": ws_id, "platformio_board": pio_id, "issue": "PlatformIO has no board by this id"})
            continue
        chip = ws_board.get("chip_variant") or ws_board.get("mcu")
        if chip and pio.get("mcu") and chip != pio["mcu"]:
            out.append({"wirestudio_board": ws_id, "platformio_board": pio_id, "issue": f"chip {chip} in WireStudio, {pio['mcu']} in PlatformIO"})
        ws_flash, pio_flash = ws_board.get("flash_size_mb"), _mb(pio.get("flash_size"))
        if ws_flash and pio_flash and float(ws_flash) != pio_flash:
            out.append({"wirestudio_board": ws_id, "platformio_board": pio_id, "severity": "info",
                        "issue": f"flash {ws_flash} MB in WireStudio, {pio_flash:g} MB in PlatformIO's default for {pio_id}",
                        "note": "WireStudio may borrow a close board's PlatformIO id and set the flash size itself. Declaring less flash "
                                "than the chip has is safe; declaring more makes the bootloader fail, so the larger figure must match the real chip."})
    return out


def catalog_rows() -> list[dict[str, Any]]:
    meta = snapshot()["meta"]
    rows = []
    for key, board in sorted(snapshot()["boards"].items()):
        platform = board["platform"]
        rows.append({
            "id": f"platformio:{key}", "label": board.get("name") or board["id"], "library": "platformio", "category": "board",
            "capabilities": ["board_metadata"], "i2c_addresses": [],
            "sources": [u for u in (board.get("url"), f"https://github.com/platformio/{platform}/blob/{meta['commits'][platform]}/boards/{board['id']}.json") if u],
            "evidence": "PlatformIO's board definition (toolchain settings), imported unchanged (Apache-2.0)",
            "mcu": board.get("mcu"), **({"octal_psram": True} if octal_psram(board) else {}),
        })
    return rows
