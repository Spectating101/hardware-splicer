#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Package a Mecha-Splicer bundle directory into a zip.")
    ap.add_argument("--bundle-dir", required=True, help="Path to a bundle output directory (contains mecha_splicer.bundle.json).")
    ap.add_argument("--out", default=None, help="Output zip path (default: <bundle-dir>.zip).")
    args = ap.parse_args()

    bundle_dir = Path(args.bundle_dir).resolve()
    if not bundle_dir.exists():
        raise SystemExit(f"Bundle dir not found: {bundle_dir}")
    if not (bundle_dir / "mecha_splicer.bundle.json").exists():
        raise SystemExit("Not a bundle dir: missing mecha_splicer.bundle.json")

    out = Path(args.out).resolve() if args.out else bundle_dir.with_suffix(".zip")
    out.parent.mkdir(parents=True, exist_ok=True)

    manifest = {"bundle_dir": str(bundle_dir), "files": []}
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bundle_dir.glob("*")):
            if not p.is_file():
                continue
            # Skip huge binary meshes if user re-runs; keep simple.
            arc = p.name
            z.write(p, arcname=arc)
            manifest["files"].append({"name": p.name, "bytes": p.stat().st_size})
        z.writestr("PACKAGE_MANIFEST.json", json.dumps(manifest, indent=2))

    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

