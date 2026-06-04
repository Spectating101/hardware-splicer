from __future__ import annotations

import argparse
from typing import Optional


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="circuit-ai-fastapi",
        description="Run the secondary Circuit-AI FastAPI server",
    )
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", default=8000, type=int)
    ap.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    ap.add_argument("--log-level", default="info")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    import uvicorn

    uvicorn.run(
        "src.api.v1.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
