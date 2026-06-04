#!/usr/bin/env python3
"""
Optional bridge to 3D Splicer (adjacent repo).
Takes a board spec (id, bbox_mm, mounts/keepouts/io_ports) and submits to 3d-splicer for case generation.

Usage:
  python scripts/splicer_bridge.py --board-spec path/to/board.json --splicer-url http://localhost:8000 --out artifacts/

Notes:
- This assumes the sibling repo ../3d-splicer is present (for circuit_ai_adapter.py and circuit_ai_client.py).
- Dependencies (requests, etc.) are defined in that repo; run this from a dev env where those are installed.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def load_adapter_and_client():
    """Dynamically import the adapter/client from ../3d-splicer."""
    sibling = Path(__file__).resolve().parents[1].parent / "3d-splicer"
    if not sibling.exists():
        raise SystemExit("3d-splicer repo not found next to Circuit-AI. Clone it adjacent to this project.")
    if str(sibling) not in sys.path:
        sys.path.insert(0, str(sibling))
    try:
        from circuit_ai_adapter import convert_circuit_ai_board  # type: ignore
        from circuit_ai_client import CircuitAIClient  # type: ignore
    except Exception as e:
        raise SystemExit(f"Failed to import adapter/client from 3d-splicer: {e}")
    return convert_circuit_ai_board, CircuitAIClient


def main():
    ap = argparse.ArgumentParser(description="Bridge Circuit-AI board spec to 3D Splicer.")
    ap.add_argument("--board-spec", required=True, help="Path to board spec JSON (id, bbox_mm, mounts, keepouts, io_ports, etc.)")
    ap.add_argument("--splicer-url", default=os.getenv("SPLICER_ENDPOINT", "http://localhost:8000"), help="3D Splicer base URL")
    ap.add_argument("--out", default="splicer_artifacts", help="Directory to save artifacts")
    ap.add_argument("--idempotency-key", default=None, help="Optional idempotency key")
    args = ap.parse_args()

    convert_circuit_ai_board, CircuitAIClient = load_adapter_and_client()

    board_path = Path(args.board_spec)
    if not board_path.exists():
        raise SystemExit(f"Board spec not found: {board_path}")

    board = json.loads(board_path.read_text())
    spec = convert_circuit_ai_board(board)

    client = CircuitAIClient(args.splicer_url)
    result = client.optimize_spec(spec=spec, output_dir=args.out, idempotency_key=args.idempotency_key)

    print("=== Splicer Result ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
