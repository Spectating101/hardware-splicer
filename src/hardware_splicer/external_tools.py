"""HS's registry of the outside tools and data it plugs in: routers, checkers, CAD, interface, fab and data.

HS is the spine and these are its limbs. Each entry names the tool, its licence (which decides whether HS copies it in,
runs it as a separate program or only reads it), how HS uses it, its status and what it measured. The registry is data:
it authorises nothing, and an outside tool's output stays evidence (docs/INTEGRATION_STACK.md).

    PYTHONPATH=src python -m hardware_splicer.external_tools [--role routing]
"""
from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent / "data" / "external_tools.json"
COPYLEFT = ("GPL", "AGPL")


@lru_cache(maxsize=1)
def registry() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def tools(role: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    return [t for t in registry()["tools"] if (role is None or t["role"] == role) and (status is None or t["status"] == status)]


def summary() -> dict[str, Any]:
    out: dict[str, dict[str, int]] = {}
    for t in registry()["tools"]:
        out.setdefault(t["role"], {}).setdefault(t["status"], 0)
        out[t["role"]][t["status"]] += 1
    return {"tools": len(registry()["tools"]), "by_role": out}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--role")
    ap.add_argument("--status")
    a = ap.parse_args(argv)
    print(json.dumps({"summary": summary(), "tools": tools(a.role, a.status)}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
