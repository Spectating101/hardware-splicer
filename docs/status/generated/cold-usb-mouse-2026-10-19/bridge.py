"""Generic MCP transport adapter with a host-side full request/response trace.

Usage: python bridge.py TOOL_NAME 'JSON_ARGUMENTS'
No HS operation IDs, payloads, solutions or human credentials are embedded here.
"""
import asyncio
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time
from mcp import Client

ROOT = Path(__file__).resolve().parent
ALLOWED = {"hs_backend_status", "hs_backend_task_manifest", "hs_backend_list_operations", "hs_backend_describe_operation", "hs_backend_call"}


async def main():
    name, arguments = sys.argv[1], json.loads(sys.argv[2])
    if name not in ALLOWED or not isinstance(arguments, dict):
        raise SystemExit("Use a listed MCP tool and JSON object arguments")
    with (ROOT / "bridge.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        trace = ROOT / "trace.jsonl"
        rows = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
        if len(rows) >= 50 or sum(r.get("response_bytes", 0) for r in rows) >= 1500000:
            raise SystemExit("Frozen trial transport budget exhausted; stop and report")
        if time.time() - json.loads((ROOT / "preregistration.json").read_text())["started_at_unix"] > 1800:
            raise SystemExit("Frozen trial time budget exhausted; stop and report")
        started = time.time()
        row = {"seq": len(rows) + 1, "started_at_unix": started, "tool": name, "arguments": arguments}
        try:
            url = json.loads((ROOT / "connection.json").read_text())["url"]
            async with Client(url, read_timeout_seconds=45) as client:
                result = await client.call_tool(name, arguments)
                raw = result.model_dump(mode="json")
            text = "\n".join(block.get("text", "") for block in raw.get("content", []) if block.get("type") == "text")
            row.update({"response": raw, "response_bytes": len(text.encode()), "response_sha256": hashlib.sha256(text.encode()).hexdigest()})
            try:
                decoded = json.loads(text)
                row["http_status"] = decoded.get("status_code")
                row["ok"] = decoded.get("ok", not raw.get("isError", False))
            except (ValueError, AttributeError):
                row["ok"] = not raw.get("isError", False)
        except Exception as exc:
            text = json.dumps({"transport_error": type(exc).__name__, "message": str(exc)})
            row.update({"response_text": text, "response_bytes": len(text.encode()), "ok": False})
        row["elapsed_seconds"] = time.time() - started
        with trace.open("a") as out:
            out.write(json.dumps(row, sort_keys=True) + "\n")
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
