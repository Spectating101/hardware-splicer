#!/usr/bin/env python3
"""Fast HTTP smoke for v1.1 interface-layer APIs (no browser required)."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("VERIFY_UI_BASE_URL", "http://127.0.0.1:8787").rstrip("/")


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    print(f"==> ui interface smoke: {BASE}")

    health = _get("/health")
    if not health.get("ok"):
        raise SystemExit(f"health failed: {health}")
    print(f"    health ok version={health.get('version')}")

    catalog = _get("/v1/integrations/catalog")
    if not catalog.get("ok") or not catalog.get("integrations"):
        raise SystemExit(f"integrations catalog failed: {catalog}")
    print(f"    integrations ok wired={catalog.get('wired_count')}/{catalog.get('total_count')}")

    fixtures = _get("/v1/examples/netlist-fixtures")
    rows = fixtures.get("fixtures") or []
    if not fixtures.get("ok") or not rows:
        raise SystemExit(f"netlist fixtures failed: {fixtures}")
    missing_desc = [row["id"] for row in rows if not row.get("description")]
    if missing_desc:
        raise SystemExit(f"fixtures missing description: {missing_desc[:5]}")
    print(f"    netlist fixtures ok count={len(rows)}")

    vision = _get("/v1/vision/capabilities")
    if not vision.get("hardware_splicer"):
        raise SystemExit(f"vision capabilities failed: {vision}")
    print("    vision capabilities ok")

    health = _get("/health")
    if "llm_policy" not in health:
        raise SystemExit(f"health missing llm_policy: {health}")
    print("    health llm_policy ok")

    print("verify_ui_interface_smoke: passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"verify_ui_interface_smoke: FAILED — {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
