#!/usr/bin/env python3
"""Cross-agent commercial evidence handoff: PR291 prices + PR293 demand + PR292 HS gates.

Read-only. Can optionally consume a separately-acquired hs.market_signals.v1
snapshot and its collection date. Never authorizes purchase or production.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from hardware_splicer.commercial_evidence_bridge import (
    CommercialEvidenceError, from_files,
)

DEFAULT_MANIFEST = "examples/cyberdeck/dual_touch/market/inputs/handoff_manifest_20261106.json"
DEFAULT_OUT = "examples/cyberdeck/dual_touch/market/evidence/commercial_handoff.json"


def _repo_path(relative: str) -> Path:
    """No absolute/traversal references from a source manifest or CLI."""
    if not isinstance(relative, str) or not relative:
        raise CommercialEvidenceError("missing input path")
    p = Path(relative)
    if p.is_absolute():
        raise CommercialEvidenceError("absolute paths are not allowed")
    resolved = (REPO / p).resolve()
    if not resolved.is_relative_to(REPO):
        raise CommercialEvidenceError("path outside the HS repository")
    return resolved


def run(manifest_path: str = DEFAULT_MANIFEST, *,
        signals_override: str | None = None, as_of_override: date | None = None) -> dict:
    manifest = json.loads(_repo_path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("schema") != "hs.market_evidence_manifest.v1":
        raise CommercialEvidenceError("unsupported source-manifest schema")
    source = manifest.get("reference_evidence")
    if not isinstance(source, dict):
        raise CommercialEvidenceError("missing pinned source")
    if not source.get("source_agent_commit") or not source.get("source_file"):
        raise CommercialEvidenceError("missing original producing-agent provenance")
    signals_path = _repo_path(signals_override or manifest["signals_path"])
    if signals_override:
        # A live pack must carry a collection date so it cannot be quietly
        # backdated, stale, or promoted via the frozen 2026-11-06 manifest.
        signal_pack = json.loads(signals_path.read_text(encoding="utf-8"))
        if signal_pack.get("schema") != "hs.market_signals.v1":
            raise CommercialEvidenceError("unsupported acquired signal schema")
        if signal_pack.get("discovery") is None:
            raise CommercialEvidenceError("live acquired source provenance is missing")
        captured = signal_pack.get("captured_at_utc", "")
        from hardware_splicer.commercial_evidence_bridge import _iso_date
        acquired_date = _iso_date(captured, "live discovery capture")
        if as_of_override is None:
            as_of_override = acquired_date
        if as_of_override < acquired_date:
            raise CommercialEvidenceError("evaluation predates live source capture")
    return from_files(
        market_path=_repo_path(source["local_path"]),
        pinned_market_sha256=source["sha256"],
        source_ref=f"{source['source_repo']}@{source['source_agent_commit']}:{source['source_file']}",
        signals_path=signals_path,
        hs_release_path=_repo_path(manifest["engineering_release_path"]),
        hs_machine_project_path=_repo_path(manifest["engineering_machine_project_path"]),
        hs_budget_path=_repo_path(manifest["engineering_budget_path"]),
        as_of=as_of_override or date.fromisoformat(manifest["as_of_utc"]),
        reference_architecture=manifest["reference_architecture"],
        target_architecture=manifest["target_architecture"],
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--signals", help="live hs.market_signals.v1 pack; do not edit pinned curated pack")
    p.add_argument("--as-of", help="UTC evaluation date; defaults to live capture date for --signals")
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--check-only", action="store_true")
    opts = p.parse_args()
    result = run(opts.manifest, signals_override=opts.signals,
                 as_of_override=date.fromisoformat(opts.as_of) if opts.as_of else None)
    if not opts.check_only:
        path = _repo_path(opts.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("PR291 snapshot SHA256 verified:", result["market_snapshot"]["sha256"][:12])
    print("Separate target:", result["target_product"])
    print("Reference Pi5 build p25 (NOT target BOM):", result["market_snapshot"]["reference_build_p25_twd"])
    print("HS target budget (not supplier quote):", result["target_hs_estimated_parts_twd"])
    print("Signals:", len(result["market_signals"]), "all independently unverified for exact-product orders")
    print("HS blockers:", result["hs_engineering"]["blocker_count"])
    print("Decision:", result["commercial_readiness"], "safe_inventory:",result["safe_to_order_inventory"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
