#!/usr/bin/env python3
"""Verify JARVIS LLM wiring: Qwen compose + trust narrative + salvage path."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.env_local import load_env_local
from hardware_splicer.integrations.qwen_text_client import qwen_configured
from hardware_splicer.jarvis_build import jarvis_build
from hardware_splicer.sdk import apply_engine_defaults


def main() -> int:
    load_env_local()
    apply_engine_defaults()
    out_root = Path.home() / ".cache" / "hardware-splicer" / "verify_jarvis_llm"
    out_root.mkdir(parents=True, exist_ok=True)

    report: dict = {"qwen_configured": qwen_configured(), "checks": []}

    def record(name: str, ok: bool, **extra) -> None:
        report["checks"].append({"name": name, "ok": ok, **extra})

    # Open goal — LLM-first compose
    r1 = jarvis_build(
        "USB-powered ESP32 wifi temperature logger with DHT22 on GPIO4",
        out_dir=out_root / "open_dht_logger",
        export_gerber=False,
    )
    q1 = r1.get("design_quality") or {}
    j1 = r1.get("jarvis") or {}
    record(
        "jarvis_open_compose",
        bool(r1.get("ok")),
        compose_mode=r1.get("compose_mode"),
        llm_first=r1.get("llm_first"),
        kicad_drc_errors=q1.get("kicad_drc_errors"),
        simulation_pass=(q1.get("electrical_simulation") or {}).get("pass"),
        jarvis_ok=j1.get("ok"),
        jarvis_headline=j1.get("headline"),
    )

    # Salvage parts path
    parts = [
        {"name": "ESP32 dev board", "type": "microcontroller"},
        {"name": "capacitive soil moisture sensor", "type": "soil_moisture"},
        {"name": "5V mini water pump", "type": "pump", "voltage_v": 5.0, "current_a": 0.55},
        {"name": "USB power bank", "type": "power_source", "voltage_v": 5.0},
    ]
    r2 = jarvis_build(
        "Automatic plant watering from salvaged ESP32, soil sensor, and pump",
        parts=parts,
        out_dir=out_root / "salvage_plant",
        export_gerber=False,
    )
    q2 = r2.get("design_quality") or {}
    j2 = r2.get("jarvis") or {}
    record(
        "jarvis_salvage_compose",
        bool(r2.get("ok")),
        compose_mode=r2.get("compose_mode"),
        build_id=r2.get("build_id"),
        kicad_drc_errors=q2.get("kicad_drc_errors"),
        jarvis_ok=j2.get("ok"),
        jarvis_headline=j2.get("headline"),
    )

    report["ok"] = all(row["ok"] for row in report["checks"])
    out_path = out_root / "VERIFY_JARVIS_LLM.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report: {out_path}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
