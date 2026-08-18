"""Console entrypoints for pip-installed Hardware-Splicer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def main_doctor() -> None:
    from hardware_splicer.sdk import engine_doctor

    print(json.dumps(engine_doctor(), indent=2))
    raise SystemExit(0)


def main_serve() -> None:
    import uvicorn

    host = "127.0.0.1"
    port = 8787
    args = sys.argv[1:]
    if "--host" in args:
        host = args[args.index("--host") + 1]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    uvicorn.run("hardware_splicer.product_api:app", host=host, port=port, reload=False)


def main_mcp() -> None:
    from hardware_splicer.mcp_server import main as mcp_main
    import asyncio

    asyncio.run(mcp_main())


def main_backend_mcp() -> None:
    """Expose the complete canonical product backend through the OpenAPI-backed MCP gateway."""

    from hardware_splicer.backend_mcp_server import main as mcp_main
    import asyncio

    asyncio.run(mcp_main())


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_or_print(payload: Any, out: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def main_capability_freeze() -> None:
    """Freeze a capability manifest as a projection of canonical MachineProject state."""

    from hardware_splicer.capability_manifest import project_capability_manifest
    from hardware_splicer.machine_project import MachineProject

    parser = argparse.ArgumentParser(
        prog="hs-capability-freeze",
        description=(
            "Project selected canonical MachineProject objects into a revision/hash-bound "
            "capability manifest for later derivative reuse analysis."
        ),
    )
    parser.add_argument("--project", type=Path, required=True, help="MachineProject JSON.")
    parser.add_argument("--project-revision", required=True)
    parser.add_argument("--capability-id", required=True)
    parser.add_argument("--revision", required=True, help="Capability-manifest revision.")
    parser.add_argument(
        "--dependencies",
        type=Path,
        required=True,
        help="JSON list, or object containing dependency_specs.",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    try:
        project_payload = _load_json(args.project)
        project = MachineProject.model_validate(project_payload)
        specs_payload = _load_json(args.dependencies)
        if isinstance(specs_payload, list):
            dependency_specs = specs_payload
        elif isinstance(specs_payload, dict):
            dependency_specs = specs_payload.get("dependency_specs")
        else:
            dependency_specs = None
        if not isinstance(dependency_specs, list) or not dependency_specs:
            raise ValueError("dependency specs must be a non-empty JSON list")

        manifest = project_capability_manifest(
            project,
            capability_id=args.capability_id,
            revision=args.revision,
            project_revision=args.project_revision,
            dependency_specs=dependency_specs,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        payload = {
            "status": "invalid",
            "error": str(exc),
            "physical_authority_granted": False,
        }
        _write_or_print(payload, args.out)
        raise SystemExit(2)

    _write_or_print(manifest, args.out)
    raise SystemExit(0)


def main_derive() -> None:
    """Plan selective evidence reuse between two frozen capability manifests."""

    from hardware_splicer.derivative_reuse import predict_derivative_reuse

    parser = argparse.ArgumentParser(
        prog="hs-derive",
        description=(
            "Compare a validated capability manifest with a candidate derivative, "
            "freeze the change set, and report retained/invalidated/blocked evidence."
        ),
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
        help="JSON list, or object containing evidence_items/inherited_evidence_items.",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    try:
        baseline = _load_json(args.baseline)
        candidate = _load_json(args.candidate)
        evidence_payload = _load_json(args.evidence)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        _write_or_print(
            {"status": "invalid", "error": str(exc), "physical_authority_granted": False},
            args.out,
        )
        raise SystemExit(2)

    if isinstance(evidence_payload, list):
        evidence_items = evidence_payload
    elif isinstance(evidence_payload, dict):
        evidence_items = (
            evidence_payload.get("inherited_evidence_items")
            or evidence_payload.get("evidence_items")
            or []
        )
    else:
        evidence_items = []

    prediction = predict_derivative_reuse(baseline, candidate, evidence_items)
    _write_or_print(prediction, args.out)
    raise SystemExit(0 if prediction.get("status") == "predicted" else 2)
