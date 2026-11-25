"""Refresh HS's snapshot of PlatformIO board definitions (Apache-2.0, github.com/platformio/platform-*).

    python scripts/import_platformio_boards.py <dir holding platform-* source trees> <SHAS file: "platform commit [github org]" lines>

Each board JSON is reduced to the fields HS uses (chip, clock, flash, RAM, radios, frameworks, maker link, PSRAM memory type)
without changing their values, and written with the Apache licence and the commit of each platform.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/third_party/platformio"


def _int(text: object) -> int | None:
    m = re.match(r"(\d+)", str(text or ""))
    return int(m.group(1)) if m else None


def slim(board_id: str, platform: str, data: dict) -> dict:
    build = data.get("build", {})
    upload = data.get("upload", {})
    flags = build.get("extra_flags", [])
    flags = flags if isinstance(flags, list) else str(flags).split()
    memory_type = (build.get("arduino") or {}).get("memory_type") or build.get("memory_type")
    return {"id": board_id, "platform": platform, "name": data.get("name"), "vendor": data.get("vendor"), "url": data.get("url"),
            "mcu": build.get("mcu"), "f_cpu_hz": _int(build.get("f_cpu")), "flash_size": upload.get("flash_size"),
            "max_flash_bytes": upload.get("maximum_size"), "max_ram_bytes": upload.get("maximum_ram_size"),
            "connectivity": data.get("connectivity", []), "frameworks": data.get("frameworks", []),
            "memory_type": memory_type, "declares_psram": any("BOARD_HAS_PSRAM" in str(f) for f in flags)}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(argv[0])
    shas, orgs = {}, {}
    for line in Path(argv[1]).read_text().splitlines():
        if line.strip():
            fields = line.split()
            shas[fields[0]] = fields[1]
            orgs[fields[0]] = fields[2] if len(fields) > 2 else "platformio"
    boards: dict[str, dict] = {}
    for platform in sorted(shas):
        if not re.fullmatch(r"[0-9a-f]{40}", shas[platform]):
            raise SystemExit(f"bad commit for {platform}")
        for path in sorted((root / platform / "boards").glob("*.json")):
            key = f"{platform.removeprefix('platform-')}:{path.stem}"
            boards[key] = slim(path.stem, platform, json.loads(path.read_text(encoding="utf-8")))
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / sorted(shas)[0] / "LICENSE", OUT / "LICENSE")
    (OUT / "boards.json").write_text(json.dumps(boards, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "SNAPSHOT.json").write_text(json.dumps({
        "source": "https://github.com/platformio", "commits": shas, "orgs": orgs, "license": "Apache-2.0 (see LICENSE in this folder)",
        "counts": {"boards": len(boards)},
        "note": "PlatformIO's board definitions, reduced to the fields HS reads; values unchanged. memory_type qio_opi or opi_opi "
                "means an Octal SPI PSRAM module, as PlatformIO's Arduino build settings declare it.",
    }, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"boards": len(boards)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
