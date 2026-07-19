#!/usr/bin/env python3
"""Deep confidence audit: FW pins ⊆ graph, MCU present, mech real, no production theater."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.graph_pin_map import extract_pins_from_graph  # noqa: E402


def _gpio_nums_in_graph(graph: Dict[str, Any]) -> Set[int]:
    nums: Set[int] = set()
    for w in graph.get("wires") or []:
        for end in ("from", "to"):
            pin = str((w.get(end) or {}).get("pinId") or "")
            m = re.match(r"^(?:GPIO|GP|D|A)(\d+)$", pin, re.I)
            if m:
                nums.add(int(m.group(1)))
    return nums


def _module_ids(graph: Dict[str, Any]) -> Set[str]:
    return {str(n.get("moduleId") or "") for n in (graph.get("nodes") or []) if n.get("moduleId")}


def audit_path(out_dir: Path) -> Dict[str, Any]:
    failures: List[str] = []
    warnings: List[str] = []
    fw_path = out_dir / "firmware" / "FIRMWARE_SCAFFOLD.json"
    graph_path = out_dir / "build_compilation" / "build_graph.json"
    mech_path = out_dir / "MECHANISM_PACK.json"
    auth_path = out_dir / "MECHATRONICS_AUTHORITY.json"
    splice_path = out_dir / "SPLICE_PLAN.json"

    if not fw_path.is_file():
        failures.append("missing firmware scaffold")
        fw: Dict[str, Any] = {}
    else:
        fw = json.loads(fw_path.read_text(encoding="utf-8"))

    if not graph_path.is_file():
        failures.append("missing build_graph")
        graph: Dict[str, Any] = {}
    else:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))

    resolved = []
    if splice_path.is_file():
        sp = json.loads(splice_path.read_text(encoding="utf-8"))
        resolved = list(sp.get("resolved_modules") or [])

    graph_mods = _module_ids(graph)
    resolved_mcu = any(
        str(r.get("role")) == "mcu" or "esp32" in str(r.get("module_id") or "") or "pico" in str(r.get("module_id") or "")
        for r in resolved
    )
    graph_mcu = any(
        mid.endswith("-devkit") or mid in {"esp32-cam-module", "arduino-nano", "rpi-pico"} for mid in graph_mods
    )
    if resolved_mcu and not graph_mcu:
        failures.append("resolved MCU missing from compiled graph")

    graph_pins = extract_pins_from_graph(graph) if graph else {}
    fw_pins = {
        k: v
        for k, v in dict(fw.get("pins") or {}).items()
        if k not in {"sourced_from_graph", "sourced_from_bringup"} and isinstance(v, int)
    }
    gpio_set = _gpio_nums_in_graph(graph)

    # Control pins in firmware must appear on the MCU side of the graph
    control_keys = {
        "soil",
        "pump",
        "fan",
        "relay",
        "dht",
        "servo_pan",
        "servo_tilt",
        "in1",
        "in2",
        "in3",
        "in4",
    }
    src = str(fw.get("source") or "")
    for key, num in fw_pins.items():
        if key not in control_keys:
            continue
        if gpio_set and num not in gpio_set:
            # Allow if extract_pins agrees (graph may use node-local names)
            if graph_pins.get(key) != num:
                failures.append(f"firmware pin {key}={num} not on graph MCU wires (graph has {sorted(gpio_set)})")
        if key in graph_pins and graph_pins[key] != num:
            failures.append(f"firmware {key}={num} != graph extract {graph_pins[key]}")
        # Sketch body must use the same number (catches `or default` falsy-0 bugs)
        token_map = {
            "servo_pan": "PAN_PIN",
            "servo_tilt": "TILT_PIN",
            "relay": "RELAY_PIN",
            "fan": "FAN_PIN",
            "pump": "PUMP_PIN",
            "soil": "SOIL_PIN",
            "step": "STEP_PIN",
            "dir": "DIR_PIN",
            "in1": "IN1",
            "in2": "IN2",
            "in3": "IN3",
            "in4": "IN4",
        }
        tok = token_map.get(key)
        if tok and tok in src and f"{tok} = {num}" not in src and f"const int {tok} = {num}" not in src:
            # allow IN1 style without const int prefix variants
            if f"{tok} = {num}" not in src and f"{tok}={num}" not in src:
                failures.append(f"firmware source {tok} does not equal pins[{key}]={num}")

    if graph_pins.get("sourced_from_graph") and not fw.get("pins", {}).get("sourced_from_graph"):
        warnings.append("graph has extractable pins but firmware not marked sourced_from_graph")

    # Dual servo honesty
    sg90_n = sum(1 for mid in graph_mods if mid in {"sg90", "mg996r"})
    if sg90_n >= 2:
        if fw_pins.get("servo_pan") is None or fw_pins.get("servo_tilt") is None:
            failures.append("dual servo graph but firmware missing pan/tilt pins")
        if fw_pins.get("servo_pan") == fw_pins.get("servo_tilt"):
            failures.append("pan and tilt share the same GPIO")

    # Mechanism
    if mech_path.is_file():
        mech = json.loads(mech_path.read_text(encoding="utf-8"))
        if mech.get("status") != "ok":
            failures.append(f"mechanism status={mech.get('status')}: {mech.get('degraded_reason')}")
        outs = list(mech.get("outputs") or [])
        if not outs:
            failures.append("mechanism ok but empty outputs")
        bundle = out_dir / "mecha_bundle"
        for name in outs[:8]:
            if not (bundle / str(name)).is_file():
                failures.append(f"mecha output missing on disk: {name}")
    else:
        failures.append("MECHANISM_PACK.json missing")

    # Authority honesty
    if auth_path.is_file():
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        offline = dict(auth.get("offline_pack") or {})
        if not offline.get("ready"):
            failures.append("offline_pack.ready is not true")
        if auth.get("production_authorized") is True and auth.get("current_authority_level") != "production_mechatronics_release":
            failures.append("production_authorized theater")
    else:
        failures.append("MECHATRONICS_AUTHORITY.json missing")

    # Power-on must stay gated
    pkg_path = out_dir / "PROJECT_PACKAGE.json"
    if pkg_path.is_file():
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        if (pkg.get("gates") or {}).get("power_on_authorized") is True:
            failures.append("power_on_authorized without bench")

    return {
        "path": out_dir.name,
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "fw_pins": fw_pins,
        "graph_pins": {k: v for k, v in graph_pins.items() if k != "sourced_from_graph"},
        "graph_modules": sorted(graph_mods),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/tmp/hs_mechatronics_paths"),
        help="Directory containing per-path build folders",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    roots = sorted(p for p in args.root.iterdir() if p.is_dir() and (p / "SPLICE_PLAN.json").is_file())
    if not roots:
        print(f"No path builds under {args.root}", file=sys.stderr)
        return 2

    rows = [audit_path(p) for p in roots]
    passed = sum(1 for r in rows if r["passed"])
    report = {
        "schema_version": "hardware_splicer.mechatronics_confidence.v1",
        "passed_count": passed,
        "path_count": len(rows),
        "all_passed": passed == len(rows),
        "paths": rows,
    }
    out = args.root / "MECHATRONICS_CONFIDENCE_REPORT.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Mechatronics confidence: {passed}/{len(rows)} passed")
        print(f"report: {out}")
        for r in rows:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['path']} fw={r['fw_pins']} graph={r['graph_pins']}")
            for f in r["failures"]:
                print(f"         - {f}")
            for w in r["warnings"]:
                print(f"         ~ {w}")

    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
