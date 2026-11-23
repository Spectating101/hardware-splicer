"""Assess explicit project harnesses and export digital wiring review packages."""
import argparse
import json
from pathlib import Path

from .project_store import ProjectStore
from .project_wiring import assess_project_wiring, list_wiring_assessments, load_wiring_assessment, wiring_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hs-wiring", description=__doc__)
    parser.add_argument("--project-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("assess", "history", "show", "csv", "wireviz", "export"):
        item = commands.add_parser(name)
        item.add_argument("project_id")
        if name == "assess":
            item.add_argument("--expected-revision", type=int, required=True)
            item.add_argument("--materials", required=True, help="Material assessment ID on this revision.")
            item.add_argument("--specification", type=Path, required=True)
            item.add_argument("--render", action="store_true", help="Run the optional local WireViz CLI.")
        elif name != "history":
            item.add_argument("assessment_id")
        if name == "export":
            item.add_argument("--output", type=Path, required=True, help="New ZIP file; existing files are not overwritten.")
    args = parser.parse_args(argv)
    try:
        store = ProjectStore(args.project_root)
        if args.command == "assess":
            if args.specification.stat().st_size > 2_000_000:
                raise ValueError("wiring specification exceeds 2 MB")
            result = assess_project_wiring(store, args.project_id, expected_revision=args.expected_revision,
                material_assessment_id=args.materials, specification=json.loads(args.specification.read_text()), render=args.render)
        elif args.command == "history":
            result = list_wiring_assessments(store, args.project_id)
        else:
            result = load_wiring_assessment(store, args.project_id, args.assessment_id)
            if args.command in {"csv", "wireviz"}:
                print(result["assessment"]["cut_list_csv" if args.command == "csv" else "wireviz_document"], end="")
                return
            if args.command == "export":
                with args.output.open("xb") as handle:
                    handle.write(wiring_bundle(result["assessment"]))
                print(json.dumps({"ok": True, "output": str(args.output)}))
                return
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
