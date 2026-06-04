#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="One-command pricing lock workflow for Mecha bundles.")
    ap.add_argument("--spec", required=True, help="Path to spec JSON")
    ap.add_argument("--out", required=True, help="Output bundle directory")
    ap.add_argument("--report-currency", default="TWD")
    ap.add_argument("--high-fidelity", action="store_true")
    ap.add_argument("--seed-example-overrides", action="store_true", help="Seed SKU_OVERRIDES.json from config/sku_overrides_example.json if missing.")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3",
        "scripts/mecha_splicer_spec.py",
        "--spec",
        str(args.spec),
        "--out",
        str(out_dir),
        "--include-pricing",
        "--report-currency",
        args.report_currency,
    ]
    if args.high_fidelity:
        cmd.append("--high-fidelity")

    subprocess.check_call(cmd, cwd=repo)

    # Generate template every run so pricing edits are easy.
    subprocess.check_call([
        "python3",
        "scripts/generate_sku_overrides.py",
        "--bundle-dir",
        str(out_dir),
    ], cwd=repo)

    sku_overrides = out_dir / "SKU_OVERRIDES.json"
    if args.seed_example_overrides and not sku_overrides.exists():
        src = repo / "config" / "sku_overrides_example.json"
        if src.exists():
            shutil.copyfile(src, sku_overrides)

    # If active overrides exist, re-run once to lock costs with edited mappings.
    if sku_overrides.exists():
        subprocess.check_call(cmd, cwd=repo)

    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
