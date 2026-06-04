#!/usr/bin/env python3
"""
Demo bundle generator: runs a vision analysis on a sample PCB image and a design-assistant pass,
writing outputs into a demo folder for quick demos/sales.

Usage:
  python scripts/demo_bundle.py --out demo_output

Requires: LLM key for design assistant to produce a full narrative; vision runs offline.
"""
import argparse
import asyncio
import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(ROOT), str(SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

from circuit_agent import CircuitAgent, LLM_ENABLED  # noqa: E402
from scripts.design_assistant import run_design_assistant  # noqa: E402


SAMPLE_IMAGE = ROOT / "datasets" / "ElectroCom61 A Multiclass Dataset for Detection of Electronic Components" / "ElectroCom-61_v2" / "test" / "images" / "IMG_20240228_122819_jpg.rf.549f931f79ce6af1acb40d1d98720cd7.jpg"


async def run_vision(out_dir: Path):
    if not SAMPLE_IMAGE.exists():
        print(f"Sample image missing: {SAMPLE_IMAGE}")
        return
    agent = CircuitAgent(knowledge_path="knowledge_base")
    with open(SAMPLE_IMAGE, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    resp = await agent.process_request("Demo run", image_b64=img_b64, mode="standard")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "vision_report.txt").write_text(resp.get("vision_report", ""))
    if "augmented_image" in resp:
        (out_dir / "vision_overlay.png").write_bytes(base64.b64decode(resp["augmented_image"]))
    print("Vision demo saved.")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo_output", help="Output folder for demo artifacts")
    args = ap.parse_args()
    out_dir = Path(args.out)

    print("Running vision demo...")
    await run_vision(out_dir / "vision")

    print("Running design assistant demo...")
    # Call design assistant with sample use case/constraints; reuse its saving logic via CLI args.
    design_out_prefix = out_dir / "design" / "usb_pd_demo"
    sys.argv = [
        "design_assistant.py",
        "--use-case",
        "USB-C PD trigger delivering 12V/3A",
        "--constraints",
        "3A continuous, small PCB, safe/robust",
        "--out-prefix",
        str(design_out_prefix),
    ]
    await run_design_assistant()
    print(f"LLM_ENABLED: {LLM_ENABLED}")
    print(f"Demo artifacts saved under {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
