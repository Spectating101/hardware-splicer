#!/usr/bin/env python3
"""Headless agent-path verification — no FreeRouting, loads .env.local for Qwen."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.env_local import load_env_local
from hardware_splicer.sdk import apply_engine_defaults, compose_arbitrary, compose_design


def main() -> int:
    load_env_local()
    apply_engine_defaults()
    out_root = Path.home() / ".cache" / "hardware-splicer" / "verify_headless"
    out_root.mkdir(parents=True, exist_ok=True)

    report: dict = {"autoroute": False, "checks": []}

    def record(name: str, ok: bool, **extra) -> None:
        report["checks"].append({"name": name, "ok": ok, **extra})

    # 1) Qwen arbitrary → compile (headless)
    r1 = compose_arbitrary(
        "USB 5V ESP32 devkit with DHT22 temperature sensor on GPIO4",
        out_dir=out_root / "qwen_arbitrary",
        fab_profile=False,
        export_gerber=False,
    )
    q1 = r1.get("design_quality") or {}
    record(
        "qwen_arbitrary_compile",
        bool(r1.get("ok")),
        compose_mode=r1.get("compose_mode"),
        kicad_drc_errors=q1.get("kicad_drc_errors"),
        copper_tier=q1.get("copper_tier"),
    )

    # 2) Fab profile = gerbers only, no Java autoroute
    r2 = compose_design(
        module_ids=["usb-power-5v", "esp32-devkit", "dht22"],
        out_dir=out_root / "fab_gerber_only",
        fab_profile=True,
        export_gerber=True,
    )
    q2 = r2.get("design_quality") or {}
    autoroute_env = __import__("os").environ.get("HARDWARE_SPLICER_AUTOROUTE", "0")
    record(
        "fab_profile_gerbers_headless",
        bool(r2.get("ok")) and autoroute_env == "0" and not q2.get("freerouting_ok"),
        autoroute_env=autoroute_env,
        gerber_ready=q2.get("gerber_ready"),
        copper_tier=q2.get("copper_tier"),
        fab_recommendation=q2.get("fab_recommendation"),
        kicad_drc_errors=q2.get("kicad_drc_errors"),
    )

    report["ok"] = all(row["ok"] for row in report["checks"])
    out_path = out_root / "VERIFY_HEADLESS.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report: {out_path}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
