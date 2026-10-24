#!/usr/bin/env python3
"""Capture original source UUIDs BEFORE using the third-party converter."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from hardware_splicer.integrations.kicad_native_origin_manifest import (
    capture_native_identity_manifest, canonical_manifest_sha256,
)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schematic", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.schematic.suffix != ".kicad_sch" or not args.schematic.is_file():
        p.error("A real .kicad_sch source file is required")
    cli = shutil.which("kicad-cli")
    if not cli:
        p.error("kicad-cli is required")
    source = args.schematic.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="hs-native-origin-") as folder:
        netlist = Path(folder) / "native.net"
        result = subprocess.run([
            cli, "sch", "export", "netlist", "--format", "kicadsexpr",
            "--output", str(netlist), str(args.schematic.resolve())
        ], capture_output=True, text=True, timeout=120)
        if result.returncode or not netlist.is_file():
            raise RuntimeError("KiCad export failed: " + result.stderr[-500:])
        manifest = capture_native_identity_manifest(source, netlist.read_text(encoding="utf-8"))
    manifest["canonical_manifest_sha256"] = canonical_manifest_sha256(manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"instances": manifest["physical_instance_count"],
                      "sha256": manifest["canonical_manifest_sha256"],
                      "upstream_transport_authenticated": False}, indent=2))

if __name__ == "__main__":
    main()
