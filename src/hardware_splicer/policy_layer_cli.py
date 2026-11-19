"""Export saved HS engineering evidence or validate Policy Lab feedback."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from .digital_engine import DigitalStudyEngine
from .policy_layer import canonical_json_bytes, export_policy_evidence, validate_policy_feedback


def parser():
    command = argparse.ArgumentParser(prog="hs-policy", description=__doc__)
    command.add_argument("--project-root", type=Path, required=True)
    command.add_argument("--jobs-db", type=Path, required=True)
    actions = command.add_subparsers(dest="command", required=True)
    export = actions.add_parser("export", help="Observe and export an exact saved digital revision.")
    export.add_argument("project_id")
    export.add_argument("destination", type=Path)
    export.add_argument("--revision", type=int)
    feedback = actions.add_parser("feedback", help="Validate a proposed revision without executing it.")
    feedback.add_argument("evidence", type=Path)
    feedback.add_argument("review", type=Path)
    feedback.add_argument("destination", type=Path)
    return command


def write_new(path: Path, value: dict) -> dict:
    data = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents replacement of an earlier assessment record.
    with path.open("xb") as handle:
        handle.write(data)
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def dispatch(engine, args):
    if args.command == "export":
        value = export_policy_evidence(engine, args.project_id, args.revision)
    elif args.command == "feedback":
        value = validate_policy_feedback(engine, args.evidence.read_bytes(), args.review.read_bytes())
    else:
        raise ValueError("Unknown policy-layer command.")
    artifact = write_new(args.destination, value)
    return {"ok": True, "schema": value["schema"], "artifact": artifact,
            "project_id": value["project_id"], "revision": value.get("revision", value.get("base_revision")),
            "physical_authority_granted": False, "automatic_execution": False}


def run(argv=None):
    args = parser().parse_args(argv)
    try:
        with DigitalStudyEngine(project_root=args.project_root, job_db=args.jobs_db) as engine:
            result = dispatch(engine, args)
        code = 0
    except Exception as exc:
        result = {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
        code = 1
    print(canonical_json_bytes(result).decode("utf-8"), end="")
    return code


def main():
    raise SystemExit(run())


if __name__ == "__main__":
    main()
