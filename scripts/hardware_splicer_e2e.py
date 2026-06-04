#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hardware_splicer import HardwareCompileSpec, compile_hardware_bundle


def _smoke_spec() -> HardwareCompileSpec:
    return HardwareCompileSpec.from_dict(
        {
            "project_name": "hardware_splicer_e2e",
            "simulation_fidelity": "starter",
            "use_3d_splicer": True,
            "machine": {
                "machine_name": "HardwareSplicerE2E",
                "boards": [
                    {
                        "board_id": "main_ctrl",
                        "pcb_outline_mm": [80, 50, 1.6],
                        "capabilities": {"pwm_channels": 2, "actuation_current_budget_a": 0.8},
                    }
                ],
            },
            "mechanism": {
                "project_name": "hardware_splicer_e2e_mech",
                "pan_tilt": {"name": "pt", "pan_servo": "sg90", "tilt_servo": "sg90"},
            },
        }
    )


def run_smoke(*, port: int = 0, start_splicer: bool = True) -> Dict[str, Any]:
    out_dir = Path(tempfile.mkdtemp(prefix="hardware_splicer_e2e_"))
    result = compile_hardware_bundle(
        _smoke_spec(),
        out_dir=out_dir,
        start_splicer=start_splicer,
        splicer_port=port,
    )
    analysis = result.engineering.get("analysis") or {}
    mechanism = analysis.get("mechanism") or {}
    splicer3d = mechanism.get("splicer3d") or {}
    return {
        "ok": result.ok,
        "splicer_url": result.splicer_url,
        "mecha_root": mechanism.get("mecha_root"),
        "bundle_file": mechanism.get("bundle_file"),
        "hardware_bundle_file": result.bundle_file,
        "manifest_file": result.manifest_file,
        "artifacts": result.artifacts,
        "splicer3d_ok": bool(splicer3d.get("ok")),
        "splicer3d_mode": "script" if splicer3d.get("script") else "stl",
        "simulation_findings": len(mechanism.get("simulation") or []),
        "dfm_findings": len(mechanism.get("dfm") or []),
        "bridge": mechanism,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Circuit-AI -> Mecha-Splicer -> 3D-Splicer smoke test.")
    parser.add_argument("--port", type=int, default=0, help="3D-Splicer port. Defaults to a free local port.")
    parser.add_argument("--no-start-splicer", action="store_true", help="Use an already running 3D-Splicer service.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    args = parser.parse_args()

    try:
        result = run_smoke(port=args.port, start_splicer=not args.no_start_splicer)
    except (OSError, TimeoutError, ConnectionError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"ok={result['ok']}")
        print(f"splicer_url={result['splicer_url']}")
        print(f"mecha_root={result['mecha_root']}")
        print(f"bundle_file={result['bundle_file']}")
        print(f"hardware_bundle_file={result['hardware_bundle_file']}")
        print(f"manifest_file={result['manifest_file']}")
        print(f"splicer3d_ok={result['splicer3d_ok']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
