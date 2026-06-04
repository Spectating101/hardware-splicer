#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_latest_path() -> Path:
    p = _repo_root() / "dist_ready_for_sale/mecha_splicer_mint.latest.md"
    text = p.read_text(encoding="utf-8")
    # format: "- `/path`"
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- `") and line.endswith("`"):
            return Path(line[3:-1])
    raise RuntimeError("Could not parse latest mint path.")


def _zip_dir(src_dir: Path, out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src_dir.rglob("*")):
            if p.is_dir():
                continue
            z.write(p, arcname=str(p.relative_to(src_dir)))


def main() -> int:
    ap = argparse.ArgumentParser(description="Package the latest Mecha-Splicer mint run into a zip.")
    ap.add_argument("--out", default="dist_ready_for_sale/mecha_splicer_mint.latest.zip", help="Output zip path (repo-relative)")
    args = ap.parse_args()

    latest = _read_latest_path()
    out_zip = _repo_root() / args.out
    _zip_dir(latest, out_zip)

    meta = {"latest": str(latest), "zip": str(out_zip)}
    (_repo_root() / "dist_ready_for_sale/mecha_splicer_mint.latest.zip.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

