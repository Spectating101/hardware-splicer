"""Refresh HS's pinned snapshot of WireStudio's part library, boards and example designs (MIT, moellere/WireStudio).

Run with a Python that has PyYAML, against an unpacked WireStudio source tree at a known commit:

    python scripts/import_wirestudio_snapshot.py <wirestudio source dir> <commit sha>

It writes JSON into src/hardware_splicer/data/third_party/wirestudio/ with WireStudio's licence and the commit. HS reads the
JSON only, so HS itself needs no YAML library. The data is WireStudio's, unchanged; HS's own checks and its notes on
WireStudio's data live in hardware_splicer.wirestudio_bridge, never in these files.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import yaml  # dev-only: needed to refresh the snapshot, not to use it

OUT = Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/third_party/wirestudio"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"[0-9a-f]{40}", argv[1]):
        print("usage: import_wirestudio_snapshot.py <wirestudio source dir> <40-hex commit>", file=sys.stderr)
        return 2
    src, commit = Path(argv[0]), argv[1]
    lib = src / "wirestudio" / "library"
    components = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((lib / "components").glob("*.yaml"))}
    boards = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((lib / "boards").glob("*.yaml"))}
    examples = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((src / "wirestudio" / "examples").glob("*.json"))}
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / "LICENSE", OUT / "LICENSE")
    for name, data in (("components", components), ("boards", boards), ("examples", examples)):
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
    (OUT / "SNAPSHOT.json").write_text(json.dumps({
        "source": "https://github.com/moellere/WireStudio", "commit": commit, "license": "MIT (see LICENSE in this folder)",
        "counts": {"components": len(components), "boards": len(boards), "examples": len(examples)},
        "note": "WireStudio's own data, unchanged. Imported into HS as data without HS citations; see hardware_splicer.wirestudio_bridge.",
    }, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"components": len(components), "boards": len(boards), "examples": len(examples)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
