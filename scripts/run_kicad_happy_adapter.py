#!/usr/bin/env python3
"""Run the optional kicad-happy evidence adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.integrations.kicad_happy_adapter import run_kicad_happy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("schematic", "pcb", "gerbers"))
    parser.add_argument("input_path", help="KiCad file or Gerber directory")
    parser.add_argument("--analyzer-root", required=True, help="Path to a kicad-happy checkout or analyzer root")
    parser.add_argument("--output-dir", required=True, help="Directory for analyzer JSON and evidence envelope")
    parser.add_argument("--adapter-version", default="unversioned-checkout")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run_kicad_happy(
        analyzer_root=args.analyzer_root,
        profile=args.profile,
        input_path=args.input_path,
        output_dir=output_dir,
        adapter_version=args.adapter_version,
        timeout_s=args.timeout,
    )
    envelope_path = output_dir / f"KICAD_HAPPY_{args.profile.upper()}_ADAPTER.json"
    envelope_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": result.get("casefile") is None and not result.get("timed_out"), "envelope": str(envelope_path), **result}, indent=2))
    return 0 if result.get("casefile") is None and not result.get("timed_out") else 2


if __name__ == "__main__":
    raise SystemExit(main())
