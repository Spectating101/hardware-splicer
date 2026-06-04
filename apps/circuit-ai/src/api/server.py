from __future__ import annotations

import argparse
import os
from typing import Optional


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="circuit-ai-api",
        description="Run the canonical Circuit-AI Flask API server",
    )
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", default=int(os.getenv("PORT", "5000")), type=int)
    ap.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=(os.getenv("DEBUG", "true").lower() == "true"),
        help="Enable or disable Flask debug mode",
    )
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    from api_server import app

    app.run(debug=args.debug, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
