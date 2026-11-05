#!/usr/bin/env python3
"""Read-only checkpoint for a Claude agent receiving HS salvage PR #286.

Does not inspect private data, alter any hardware, contact vendors, rewrite
repo artifacts, purchase equipment or imply a physical product exists.
--tests also runs the already-tracked focused pytest suite.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "examples" / "arbitrage_lab"

EXPECTED_PATHS = [
    "CLAUDE.md",
    "docs/SALVAGE_TO_PRODUCT_CLAUDE_HANDOFF_2026-11-05.md",
    "apps/circuit-ai/src/intelligence/salvage_splice_planner.py",
    "apps/circuit-ai/src/intelligence/hardware_plan.py",
    "apps/circuit-ai/src/intelligence/salvage_workflow_engine.py",
    "src/hardware_splicer/salvage_bringup.py",
    "examples/arbitrage_lab/refurb_nuc11/evidence/refurb_decision.json",
    "examples/arbitrage_lab/industrial_printer/evidence/industrial_refurb_screen.json",
    "examples/arbitrage_lab/salvage_lot/evidence/salvage_decision.json",
    "examples/arbitrage_lab/salvage_lot/channel_20261105/evidence/channel_decision.json",
    "examples/arbitrage_lab/salvage_lot/channel_20261105/evidence/optiplex_control_readonly.json",
    ".github/workflows/hs-arbitrage-market-pilot.yml",
]

FOCUSED_TESTS = [
    "examples/arbitrage_lab/pc_refurb/tests",
    "examples/arbitrage_lab/salvage_lot/channel_20261105/tests/test_channel.py",
    "examples/arbitrage_lab/salvage_lot/tests/test_salvage_pilot.py",
    "examples/arbitrage_lab/industrial_printer/tests/test_printer_pilot.py",
    "examples/arbitrage_lab/refurb_nuc11/tests/test_refurb_pilot.py",
    "examples/arbitrage_lab/tests/test_arbitrage_pilot.py",
    "apps/mecha-splicer/tests/test_bundle.py",
]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def g(data: dict, *path: str):
    obj = data
    for item in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(item)
    return obj


def check(name: str, condition: bool, detail: str) -> tuple[str, bool, str]:
    return (name, bool(condition), detail)


def git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=ROOT, text=True, capture_output=True,
            check=True, timeout=8,
        )
        return r.stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def inspect() -> list[tuple[str, bool, str]]:
    checks = []
    for path in EXPECTED_PATHS:
        checks.append(check("path " + path, (ROOT / path).is_file(), "required handoff source"))
    if any(not passed for _, passed, _ in checks):
        return checks

    nuc = load("examples/arbitrage_lab/refurb_nuc11/evidence/refurb_decision.json")
    zebra = load("examples/arbitrage_lab/industrial_printer/evidence/industrial_refurb_screen.json")
    salvage = load("examples/arbitrage_lab/salvage_lot/evidence/salvage_decision.json")
    channel = load("examples/arbitrage_lab/salvage_lot/channel_20261105/evidence/channel_decision.json")
    host = load("examples/arbitrage_lab/salvage_lot/channel_20261105/evidence/optiplex_control_readonly.json")
    checks.extend([
        check("NUC has not been acquired", g(nuc, "actual_acquired") is False, "seller-only case"),
        check("NUC not physically released", g(nuc, "released_as_functional") is False, "no repair proof"),
        check("Zebra has not been acquired", g(zebra, "device_acquired") is False, "seller-only case"),
        check("Zebra test labels never printed", g(zebra, "physical_prints_made") == 0, "offline ZPL only"),
        check("No legal commercial salvage stock", g(salvage, "confirmed_resale_authorized_lots") == 0, "historical source state"),
        check("No functional salvage product", g(salvage, "functional_products_produced") == 0, "not manufactured"),
        check("No recycler sales quotes obtained", g(channel, "confirmed_supplier_salvage_sale_quotes") == 0, "advertised buyback is not a sale offer"),
        check("No scrap PCs verified available", g(channel, "verified_scrap_pc_available") == 0, "no actual stock"),
        check("No computer recovered from new salvage", g(channel, "confirmed_recovered_functional_products") == 0, "no physical product"),
        check("Actual host probe ran", g(host, "claim_gates", "host_os_is_running") is True, "Optiplex is a pre-existing host"),
        check("Host is NOT treated as salvage", g(host, "claim_gates", "a_salvaged_product_works") is False, "control-only"),
        check("Host NOT approved for resale", g(host, "claim_gates", "resale_approval") is False, "control-only"),
    ])
    return checks


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tests", action="store_true", help="run known focused tests, no hardware operations")
    args = p.parse_args()
    print("HS salvage Claude handoff / SOURCE CHECKPOINT (not physical proof)")
    print("Repo:", ROOT)
    print("Branch:", git("branch", "--show-current"), "HEAD:", git("rev-parse", "--short", "HEAD"))
    print("Snapshot PR: https://github.com/Spectating101/hardware-splicer/pull/286")
    try:
        checks = inspect()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("EVIDENCE CHECK ERROR:", type(exc).__name__, str(exc))
        return 1
    bad = []
    for name, passed, detail in checks:
        print(("PASS" if passed else "FAIL"), name, "—", detail)
        if not passed:
            bad.append(name)
    if bad:
        print("STOP: evidence checkpoint differs from handoff. Audit changes, don't claim physical proof.")
        return 1
    print("SOURCE CHECKPOINT PASS:", len(checks), "checks; verified physical salvage products = 0")
    if not args.tests:
        print("Optional: python3 scripts/hs_salvage_handoff_preflight.py --tests")
        return 0
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, ["apps/mecha-splicer", "apps/mecha-splicer/src", env.get("PYTHONPATH")])
    )
    if importlib.util.find_spec("pytest") is None:
        print(f"TESTS BLOCKED: pytest is not installed for {sys.executable}. "
              "Re-run with the repo virtualenv, e.g. .venv/bin/python scripts/hs_salvage_handoff_preflight.py --tests")
        return 2
    print("FOCUSED REGRESSION:", *FOCUSED_TESTS, sep="\n  ")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS],
            cwd=ROOT, env=env, timeout=180,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print("TESTS BLOCKED:", type(exc).__name__, str(exc))
        return 2
    if r.returncode:
        print("TESTS FAILED; NOT A PHYSICAL RELEASE:", r.returncode)
        return r.returncode
    print("FOCUSED REGRESSION PASS. This does not authorize acquisition, repair, sale or electrical power.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
