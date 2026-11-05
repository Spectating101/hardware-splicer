"""Feed bench-verified components from a casefile into the existing Circuit-AI SalvageWorkflowEngine.

What this really integrates: the engine's persistent asset ledger (provenance, ``test_status``,
capabilities). What it does NOT do: price or sell parts. The engine is circuit-board oriented; given a
verified RAM stick it reports "collect more evidence". Resale valuation stays in ``staged_economics``.

Only components whose OWN gate passed (``partout_candidates``) from an acquired ``target`` unit are
ingested. Control hosts, fixtures, public cases and unacquired units are refused.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]


class BridgeRefused(Exception):
    pass


def ingest_partout(report: dict, inventory_path: Path) -> dict:
    if report.get("role") != "target" or report.get("acquired") is not True:
        raise BridgeRefused(f"refusing to ingest: role={report.get('role')!r} acquired={report.get('acquired')!r}")
    if report.get("decision") in ("DISPUTE_CLAIM_MISMATCH",):
        raise BridgeRefused("unit is disputed; resolve with the seller first")
    manifest = report["facts"].get("bench_manifest_sha256")
    if not manifest:
        raise BridgeRefused("no bench manifest hash: cannot bind provenance")
    rows = [{"listing": {"title": f"{c['name']} (from {report['unit_id']}, bench-verified)",
                         "expected_capabilities": [c["asset_type"]], "price_usd": 0.0, "condition": "used",
                         "source": f"casefile:{report['unit_id']}"},
             "notes": f"gate {c['evidence_gate']} passed; bench manifest sha256 {manifest}"}
            for c in report["partout_candidates"]]
    if not rows:
        return {"ingested_assets": [], "inventory": None, "note": "no component passed its own gate"}
    done = subprocess.run([sys.executable, "-I", str(HERE / "_engine_runner.py")], capture_output=True, text=True,
                          timeout=120, input=json.dumps({"repo": str(REPO), "inventory_path": str(inventory_path),
                                                         "listings": rows}))
    if done.returncode:
        raise RuntimeError("SalvageWorkflowEngine runner failed: " + done.stderr[-400:])
    out = json.loads(done.stdout.strip().splitlines()[-1])
    out["note"] = "ledger only; valuation is staged_economics, not the engine"
    return out
