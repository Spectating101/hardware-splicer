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


CANONICAL_APP = "hardware_splicer.product_api:app"


def main_serve() -> None:
    """Run the canonical product app (API, project scenes and the built UI) on one port."""

    import ipaddress
    import os

    import uvicorn

    parser = argparse.ArgumentParser(prog="hs-serve", description=main_serve.__doc__)
    parser.add_argument("--host", default=os.environ.get("HARDWARE_SPLICER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("HARDWARE_SPLICER_PORT", "8787")))
    ui = parser.add_mutually_exclusive_group()
    ui.add_argument("--ui", dest="ui", action="store_const", const="1",
                    help="Require the built UI; refuse to start without one.")
    ui.add_argument("--no-ui", dest="ui", action="store_const", const="0", help="API only.")
    parser.add_argument("--ui-dist", type=Path,
                        help="UI build directory; overrides HARDWARE_SPLICER_UI_DIST.")
    parser.add_argument("--repo-root", type=Path,
                        help="Hardware-Splicer checkout whose projects/ supply scenes; overrides "
                             "HARDWARE_SPLICER_REPO_ROOT (needed when running from an installed package).")
    parser.add_argument("--allow-remote", action="store_true",
                        help="Allow a non-loopback bind (only behind the nginx front in deploy/DEPLOY.md).")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        loopback = ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        loopback = args.host.lower() == "localhost"
    if not loopback:
        warning = "There is no in-app authentication yet; deploy/DEPLOY.md's nginx front is required."
        if not args.allow_remote:
            parser.error("Refusing non-loopback host without --allow-remote. " + warning)
        print(warning, file=sys.stderr)
    # Default: serve the UI when a build exists (packaged ui_dist, else apps/splice-ui/dist).
    if args.ui is not None:
        os.environ["HARDWARE_SPLICER_SERVE_UI"] = args.ui
    elif not os.environ.get("HARDWARE_SPLICER_SERVE_UI", "").strip():
        os.environ["HARDWARE_SPLICER_SERVE_UI"] = "auto"
    if args.ui_dist is not None:
        os.environ["HARDWARE_SPLICER_UI_DIST"] = str(args.ui_dist.expanduser().resolve())
    if args.repo_root is not None:
        os.environ["HARDWARE_SPLICER_REPO_ROOT"] = str(args.repo_root.expanduser().resolve())
    uvicorn.run(CANONICAL_APP, host=args.host, port=args.port, reload=False)


def main_mcp() -> None:
    from hardware_splicer.mcp_server import main as mcp_main
    import asyncio

    asyncio.run(mcp_main())


def main_backend_mcp() -> None:
    """Expose the complete canonical product backend through the current MCP gateway."""

    from hardware_splicer.backend_mcp_server import main as mcp_main

    mcp_main()


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
