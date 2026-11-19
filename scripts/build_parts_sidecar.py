"""Write a project revision's parts.json for a 3D viewer."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.part_scene import build_parts_sidecar, build_parts_sidecar_for

FIELDDECK = "cyberdeck-real-trial-20261020"


def _manifest_asset(project, relative):
    if not relative:
        raise ValueError("The revision has no asset path")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Expected a repo-relative asset path: {relative}")
    asset = (project.parent.parent / path).resolve()
    if not asset.is_relative_to(project):
        raise ValueError(f"Asset path is outside the project: {relative}")
    return asset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--project-dir", type=Path)
    source.add_argument("--manifest", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.manifest is None:
        if args.out is None or args.revision not in {"7", "5"}:
            parser.error("The legacy mode requires --revision {7,5} and --out")
        sidecar = build_parts_sidecar(args.project_dir or ROOT / "projects" / FIELDDECK, args.revision)
        target = args.out / "parts.json"
    else:
        try:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            project = args.manifest.resolve().parent
            revision = next((row for row in manifest["revisions"] if row["id"] == args.revision), None)
            if revision is None:
                raise ValueError(f"Unknown revision: {args.revision}")
            glb = _manifest_asset(project, revision["glb"])
            target = args.out / "parts.json" if args.out else _manifest_asset(project, revision["parts"])
            if manifest["project_id"] == FIELDDECK:
                sidecar = build_parts_sidecar(project, args.revision)
            else:
                sidecar = build_parts_sidecar_for(glb, project, args.revision,
                                                  glb_native_units=revision.get("glb_native_units"))
        except (FileNotFoundError, ValueError) as error:
            parser.error(str(error))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
