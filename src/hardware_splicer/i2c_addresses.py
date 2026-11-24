"""I2C addresses for parts in the splice library, read from the sourced device library.

The device library cites a datasheet or vendor page for every address list. A splice part is
only given addresses when it is the same chip as a part in that library. A part with no
sourced addresses is reported as unknown and is never guessed.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

_DEVICE_MODULES = Path(__file__).parent / "data" / "device_modules.json"

# Splice-library id -> device-library id. Matched on the chip: the addresses are properties of the
# chip, so a different breakout board of the same chip answers on the same addresses. Which pin
# selects the alternate address does depend on the board, and is not claimed here.
SPLICE_TO_DEVICE_LIBRARY: Dict[str, str] = {
    "bme280": "adafruit-bme280-stemma-qt",
    "bh1750": "adafruit-bh1750-stemma-qt",
    "ds3231_rtc": "adafruit-ds3231-stemma-qt",
    "ssd1306-128x64": "ssd1306-096-i2c",
}


_HEX_ADDRESS = re.compile(r"^0[xX]([0-9a-fA-F]{1,2})$")

# 7-bit I2C addresses 0x00-0x07 and 0x78-0x7F are reserved by the I2C specification.
FIRST_DEVICE_ADDRESS = 0x08
LAST_DEVICE_ADDRESS = 0x77


def normalize_i2c_address(value: Any) -> Optional[str]:
    """A declared address as "0xNN" (upper-case hex), or None when it is not a valid 7-bit device address.

    Accepts an int or a hex string in either case ("0x3d", "0X3D"). Anything else, and anything in a
    reserved range or above 7 bits (an 8-bit write address such as 0xEE), is None.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        match = _HEX_ADDRESS.match(value.strip())
        if not match:
            return None
        number = int(match.group(1), 16)
    else:
        return None
    if not FIRST_DEVICE_ADDRESS <= number <= LAST_DEVICE_ADDRESS:
        return None
    return f"0x{number:02X}"


@lru_cache(maxsize=1)
def _device_library() -> Dict[str, Dict[str, Any]]:
    modules = json.loads(_DEVICE_MODULES.read_text(encoding="utf-8")).get("modules") or []
    rows = modules.values() if isinstance(modules, dict) else modules
    return {str(row["id"]): row for row in rows if isinstance(row, dict) and row.get("id")}


def i2c_addresses_for(module_id: str) -> Optional[Dict[str, Any]]:
    """Addresses the part can answer on, factory default first, or None when no source says."""
    device_id = SPLICE_TO_DEVICE_LIBRARY.get(str(module_id))
    row = _device_library().get(device_id or "")
    i2c = (row or {}).get("i2c") or {}
    addresses = [normalize_i2c_address(a) or str(a) for a in i2c.get("addresses") or []]
    if not addresses:
        return None
    return {
        "addresses": addresses,
        # The first address listed. Six of the seven library entries state in their source text that
        # it is the factory default; for the SSD1306 the datasheet gives both addresses and only a
        # seller listing in the entry's sources uses 0x3C, so treat it as the usual default.
        "default": addresses[0],
        "basis": str(i2c.get("address_basis") or ""),
        "selectable": len(addresses) > 1,
    }
