#!/usr/bin/env python3
"""
Robust bridge to 3D Splicer with multiple import strategies.

Takes a board spec (id, bbox_mm, mounts/keepouts/io_ports) and submits to 3d-splicer for case generation.

Usage:
  python scripts/splicer_bridge_robust.py --board-spec path/to/board.json --splicer-url http://localhost:8000 --out artifacts/

Import Strategy (in order of preference):
  1. Try importing from installed package (production)
  2. Try environment variable SPLICER_PATH (deployment flexibility)
  3. Fall back to sibling directory (development)

Installation:
  Production: pip install splicer3d
  Development: export SPLICER_PATH=/path/to/3d-splicer
"""
import argparse
import json
import os
import sys
from pathlib import Path


def load_adapter_and_client():
    """
    Dynamically import the adapter/client with robust fallback strategy.

    Returns:
        Tuple of (convert_circuit_ai_board function, CircuitAIClient class)

    Raises:
        SystemExit: If imports fail after trying all strategies
    """
    # Strategy 1: Try installed package (production)
    try:
        from circuit_ai_adapter import convert_circuit_ai_board
        from circuit_ai_client import CircuitAIClient
        print("✓ Loaded from installed package")
        return convert_circuit_ai_board, CircuitAIClient
    except ImportError:
        pass

    # Strategy 2: Try environment variable
    splicer_path = os.getenv("SPLICER_PATH")
    if splicer_path:
        splicer_dir = Path(splicer_path)
        if splicer_dir.exists():
            if str(splicer_dir) not in sys.path:
                sys.path.insert(0, str(splicer_dir))
            try:
                from circuit_ai_adapter import convert_circuit_ai_board
                from circuit_ai_client import CircuitAIClient
                print(f"✓ Loaded from SPLICER_PATH: {splicer_path}")
                return convert_circuit_ai_board, CircuitAIClient
            except ImportError:
                pass

    # Strategy 3: Try sibling directory (development)
    sibling = Path(__file__).resolve().parents[1].parent / "3d-splicer"
    if sibling.exists():
        if str(sibling) not in sys.path:
            sys.path.insert(0, str(sibling))
        try:
            from circuit_ai_adapter import convert_circuit_ai_board
            from circuit_ai_client import CircuitAIClient
            print(f"✓ Loaded from sibling directory: {sibling}")
            return convert_circuit_ai_board, CircuitAIClient
        except ImportError as e:
            raise SystemExit(f"Found 3d-splicer but import failed: {e}")

    # All strategies failed
    raise SystemExit(
        "Failed to import circuit_ai_adapter and circuit_ai_client.\n"
        "Try one of:\n"
        "  1. pip install splicer3d (production)\n"
        "  2. export SPLICER_PATH=/path/to/3d-splicer (custom path)\n"
        "  3. Clone 3d-splicer next to Circuit-AI (development)"
    )


def main():
    ap = argparse.ArgumentParser(
        description="Bridge Circuit-AI board spec to 3D Splicer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python scripts/splicer_bridge_robust.py --board-spec board.json

  # With custom splicer URL
  python scripts/splicer_bridge_robust.py --board-spec board.json --splicer-url http://splicer.example.com:8003

  # With idempotency key for deterministic results
  python scripts/splicer_bridge_robust.py --board-spec board.json --idempotency-key my-board-v1
        """
    )
    ap.add_argument(
        "--board-spec",
        required=True,
        help="Path to board spec JSON (id, bbox_mm, mounts, keepouts, io_ports, etc.)"
    )
    ap.add_argument(
        "--splicer-url",
        default=os.getenv("SPLICER_ENDPOINT", "http://localhost:8003"),
        help="3D Splicer base URL (default: $SPLICER_ENDPOINT or http://localhost:8003)"
    )
    ap.add_argument(
        "--out",
        default="splicer_artifacts",
        help="Directory to save artifacts (default: splicer_artifacts)"
    )
    ap.add_argument(
        "--idempotency-key",
        default=None,
        help="Optional idempotency key for deterministic results"
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum wait time in seconds (default: 300)"
    )
    args = ap.parse_args()

    # Load adapter and client
    convert_circuit_ai_board, CircuitAIClient = load_adapter_and_client()

    # Load board spec
    board_path = Path(args.board_spec)
    if not board_path.exists():
        raise SystemExit(f"Board spec not found: {board_path}")

    print(f"\n📋 Loading board spec: {board_path}")
    board = json.loads(board_path.read_text())

    # Convert to functional spec
    print("🔄 Converting Circuit-AI board to functional spec...")
    spec = convert_circuit_ai_board(board)

    # Submit to 3D Splicer
    print(f"🚀 Submitting to 3D Splicer: {args.splicer_url}")
    client = CircuitAIClient(args.splicer_url)

    try:
        job_id = client.submit_functional_spec(
            spec=spec,
            idempotency_key=args.idempotency_key
        )

        print(f"⏳ Job submitted: {job_id}")
        print(f"⏳ Waiting for completion (timeout: {args.timeout}s)...")

        result = client.wait_for_completion(
            job_id=job_id,
            max_wait=args.timeout
        )

        # Download artifacts
        output_dir = Path(args.out)
        output_dir.mkdir(parents=True, exist_ok=True)

        if "stl_path" in result or "artifact_path" in result:
            artifact_path = result.get("stl_path") or result.get("artifact_path")
            print(f"📦 Downloading artifacts to {output_dir}/...")

            # Download STL
            stl_data = client.download_artifact(job_id, "stl")
            stl_file = output_dir / f"{job_id}.stl"
            stl_file.write_bytes(stl_data)
            print(f"  ✓ {stl_file}")

            # Download GLB if available
            try:
                glb_data = client.download_artifact(job_id, "glb")
                glb_file = output_dir / f"{job_id}.glb"
                glb_file.write_bytes(glb_data)
                print(f"  ✓ {glb_file}")
            except Exception:
                pass  # GLB optional

            # Download report if available
            try:
                report_data = client.download_artifact(job_id, "report")
                report_file = output_dir / f"{job_id}_report.md"
                report_file.write_text(report_data.decode("utf-8"))
                print(f"  ✓ {report_file}")
            except Exception:
                pass  # Report optional

        print("\n=== Splicer Result ===")
        print(json.dumps(result, indent=2))

        print("\n✅ Success!")

    except TimeoutError:
        print(f"\n❌ Timeout: Job did not complete within {args.timeout}s")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
