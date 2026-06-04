#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Mecha-Splicer: spec → bundle (OpenSCAD + DFM + BOM).")
    ap.add_argument("--spec", required=True, help="Path to spec JSON")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument(
        "--use-3d-splicer",
        action="store_true",
        help="Also call sibling 3d-splicer for CadQuery script/STL (electronics+enclosure only).",
    )
    ap.add_argument(
        "--render-stl",
        action="store_true",
        help="With --use-3d-splicer, request STL rendering (requires CadQuery in 3d-splicer).",
    )
    ap.add_argument("--include-pricing", action="store_true", help="Generate BUY_LIST.csv + procurement lock report (uses local catalog + overrides).")
    ap.add_argument("--sku-overrides", default=None, help="Path to SKU overrides JSON (see config/sku_overrides_example.json).")
    ap.add_argument("--render-openscad-stl", action="store_true", help="Try to render OpenSCAD outputs to STL (local openscad or docker).")
    ap.add_argument("--openscad-docker-image", default=None, help="Optional Docker image to use for OpenSCAD rendering (e.g. openscad/openscad:latest).")
    ap.add_argument("--report-currency", default="TWD", help="Reporting currency for COGS summary (default: TWD).")
    ap.add_argument("--simulation-fidelity", choices=["starter", "high"], default=None, help="Simulation mode: starter (fast) or high (analytical + optional pybullet).")
    ap.add_argument("--high-fidelity", action="store_true", help="Shortcut for --simulation-fidelity high.")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))

    import sys

    sys.path.insert(0, str(_repo_root()))
    from src.mecha_splicer.runner import run  # type: ignore

    sim_fidelity = "high" if bool(args.high_fidelity) else args.simulation_fidelity

    bundle = run(
        spec,
        out_dir=args.out,
        use_3d_splicer=bool(args.use_3d_splicer),
        render_stl=bool(args.render_stl),
        include_pricing=bool(args.include_pricing),
        sku_overrides_path=args.sku_overrides,
        render_openscad_stl=bool(args.render_openscad_stl),
        openscad_docker_image=args.openscad_docker_image,
        report_currency=str(args.report_currency),
        simulation_fidelity=sim_fidelity,
    )
    print(json.dumps(bundle, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
