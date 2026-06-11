#!/usr/bin/env python3
"""Score backend catalog builds vs raw-LLM-style failure modes (no API keys required)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hardware_splicer.build_compiler import compile_catalog_build  # noqa: E402

BUILD_IDS = [
    "automatic_plant_watering",
    "bench_power_adapter",
    "camera_ir_light_or_sensor_mount",
    "indicator_or_task_light",
    "inspection_motion_fixture",
    "low_voltage_motor_test_jig",
    "network_status_indicator",
    "plotter_motion_stage",
    "robot_drive_base",
    "salvaged_input_panel",
    "sensor_logger",
    "small_audio_amp_box",
    "smart_relay_box",
    "usb_fume_extractor",
    "usb_uart_debug_adapter",
]


def main() -> int:
    out_root = Path("/tmp/hardware_splicer_backend_benchmark")
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for build_id in BUILD_IDS:
        target = out_root / build_id
        result = compile_catalog_build(build_id, target, export_gerber=False)
        q = result.design_quality
        gate = {
            "build_ready": bool(q.get("build_ready")),
            "fabrication_ready": bool(q.get("fabrication_ready")),
            "electrical_warnings": int(q.get("electrical_warnings") or 0),
            "gerber_ready": bool(q.get("gerber_ready")),
            "bom_ready": bool(q.get("bom_ready")),
        }
        rows.append(
            {
                "build_id": build_id,
                "ok": result.ok,
                "drc_pass": q.get("drc_pass"),
                "electrical_safety_pass": q.get("electrical_safety_pass"),
                "electrical_warnings": gate["electrical_warnings"],
                "build_ready": gate["build_ready"],
                "fabrication_ready": gate["fabrication_ready"],
                "module_count": q.get("module_count"),
                "wire_count": q.get("wire_count"),
                "board_outline": q.get("board_outline"),
                "error": result.error,
            }
        )

    passed = sum(1 for row in rows if row["ok"] and row["electrical_warnings"] == 0)
    report = {
        "schema_version": "hardware_splicer.backend_design_benchmark.v1",
        "catalog_count": len(rows),
        "passed": passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "fabrication_ready_count": sum(1 for row in rows if row.get("fabrication_ready")),
        "zero_electrical_warning_count": sum(1 for row in rows if row.get("electrical_warnings") == 0),
        "vanilla_llm_baseline": {
            "deterministic_kicad": False,
            "drc_verified": False,
            "electrical_rules_verified": False,
            "fabrication_package": False,
            "note": "Raw ChatGPT/Claude typically returns prose or unverified schematics without fab-grade DRC.",
        },
        "rows": rows,
    }
    report_path = out_root / "BENCHMARK_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": passed, "total": len(rows), "report": str(report_path)}, indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
