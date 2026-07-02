"""Console entrypoints for pip-installed Hardware-Splicer."""

from __future__ import annotations

import json
import sys


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
    uvicorn.run("hardware_splicer.api:app", host=host, port=port, reload=False)


def main_mcp() -> None:
    from hardware_splicer.mcp_server import main as mcp_main
    import asyncio

    asyncio.run(mcp_main())
