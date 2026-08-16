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
    # Serve the canonical product composition: engine endpoints plus durable
    # project snapshots. The lower-level hardware_splicer.api app remains
    # available for engine-only embedding and focused tests.
    uvicorn.run("hardware_splicer.product_api:app", host=host, port=port, reload=False)


def main_mcp() -> None:
    from hardware_splicer.mcp_server import main as mcp_main
    import asyncio

    asyncio.run(mcp_main())


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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

    baseline = _load_json(args.baseline)
    candidate = _load_json(args.candidate)
    evidence_payload = _load_json(args.evidence)
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
    rendered = json.dumps(prediction, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    raise SystemExit(0 if prediction.get("status") == "predicted" else 2)
