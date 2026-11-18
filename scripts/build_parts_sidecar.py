"""Write a Fielddeck assembly's parts.json for a 3D viewer."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.part_scene import build_parts_sidecar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=ROOT / "projects/cyberdeck-real-trial-20261020")
    parser.add_argument("--revision", required=True, choices=("7", "5"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sidecar = build_parts_sidecar(args.project_dir, args.revision)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "parts.json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
