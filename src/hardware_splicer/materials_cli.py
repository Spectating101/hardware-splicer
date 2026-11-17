"""Operate project materials and the read-only InvenTree integration headlessly."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .project_materials import (
    assess_project_materials, import_inventree_materials, list_material_assessments,
    load_material_assessment, material_csv,
)
from .project_store import ProjectStore


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hs-materials", description=__doc__)
    parser.add_argument("--project-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("assess", "import-inventree", "history", "show", "csv"):
        item = commands.add_parser(name)
        item.add_argument("project_id")
        if name in {"assess", "import-inventree"}:
            item.add_argument("--expected-revision", type=int, required=True)
        if name == "assess":
            item.add_argument("--requirements", type=Path, required=True, help="JSON list of exact material requirements.")
            item.add_argument("--inventory", type=Path, help="InventoryCapture JSON. Omit to declare an empty inventory.")
        if name == "import-inventree":
            item.add_argument("--assembly-part-id", type=int, required=True)
            item.add_argument("--build-quantity", type=int, default=1)
        if name in {"show", "csv"}:
            item.add_argument("assessment_id")
    args = parser.parse_args(argv)
    try:
        store = ProjectStore(args.project_root)
        if args.command == "assess":
            requirements = _read(args.requirements)
            inventory = _read(args.inventory) if args.inventory else {
                "source": "declared", "captured_at": datetime.now(timezone.utc).isoformat(), "lots": []}
            result = assess_project_materials(store, args.project_id, expected_revision=args.expected_revision,
                                              requirements=requirements, inventory=inventory)
        elif args.command == "import-inventree":
            result = import_inventree_materials(store, args.project_id, expected_revision=args.expected_revision,
                                                assembly_part_id=args.assembly_part_id, build_quantity=args.build_quantity)
        elif args.command == "history":
            result = list_material_assessments(store, args.project_id)
        else:
            result = load_material_assessment(store, args.project_id, args.assessment_id)
            if args.command == "csv":
                print(material_csv(result["assessment"]), end="")
                return
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}))
        raise SystemExit(1) from None


def _read(path):
    if path.stat().st_size > 2_000_000:
        raise ValueError("input exceeds 2 MB")
    return json.loads(path.read_text())


if __name__ == "__main__":
    main()
