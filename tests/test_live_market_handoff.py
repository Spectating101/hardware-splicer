"""One actual end-to-end acquired-pack-to-canonical-release regression.

Uses only synthetic public API fixtures; the HS pricing and machine-project inputs
are the exact pinned artifacts inherited from PR #294.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from hardware_splicer.market_signal_acquisition import acquire

ROOT = Path(__file__).resolve().parents[1]
PLAN = {"schema": "hs.discovery_plan.v1",
        "target_architecture": "dual_esp32_touch_4p3_rs485",
        "jobs": [{"id": "mobile-dev", "github_queries": ["ssh phone"], "github_title_terms": ["ssh","terminal","keyboard"]}],
        "github_per_page": 10, "max_pages": 1}


def fixture_source(url, headers):
    assert "api.github.com/search/issues?" in url
    return {"total_count": 1, "items": [{
        "number": 22, "title": "SSH shortcut key difficult on phone",
        "html_url": "https://github.com/sample/repo/issues/22",
        "updated_at": "2026-11-06T09:00:00Z"}]}


def test_fresh_acquisition_reuses_real_hs_gates_and_distinct_architectures():
    pack = acquire(PLAN, observed=datetime(2026, 11, 6, 11, tzinfo=timezone.utc),
                   getter=fixture_source, github_token="")
    with tempfile.TemporaryDirectory(prefix="hs_acquisition_test_", dir=ROOT) as tmp:
        source = Path(tmp) / "live_signals.json"
        target = Path(tmp) / "handoff.json"
        source.write_text(json.dumps(pack), encoding="utf-8")
        cmd = [sys.executable, "scripts/hs_market_evidence_handoff.py",
               "--signals", str(source.relative_to(ROOT)),
               "--out", str(target.relative_to(ROOT))]
        run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stdout + run.stderr
        result = json.loads(target.read_text(encoding="utf-8"))
        assert result["market_snapshot"]["validation"]["p25"]["recomputed_twd"] == 8057
        assert result["market_snapshot"]["reference_only_not_target_cost"] is True
        assert result["not_same_product"] is True
        assert result["hs_engineering"]["blocker_count"] == 6
        assert len(result["market_signals"]) == 1
        assert result["market_signals"][0]["interpretation"] == "qualitative_interest_not_purchase"
        assert result["verified_exact_customer_orders"] == 0
        assert result["safe_to_order_inventory"] is False


def test_live_acquisition_cannot_be_reinterpreted_as_earlier_evidence():
    pack = acquire(PLAN, observed=datetime(2026, 11, 7, 11, tzinfo=timezone.utc),
                   getter=fixture_source, github_token="")
    with tempfile.TemporaryDirectory(prefix="hs_acquisition_test_", dir=ROOT) as tmp:
        source = Path(tmp) / "live_signals.json"
        source.write_text(json.dumps(pack), encoding="utf-8")
        cmd = [sys.executable, "scripts/hs_market_evidence_handoff.py",
               "--signals", str(source.relative_to(ROOT)), "--as-of", "2026-11-06", "--check-only"]
        run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert run.returncode != 0
        assert "evaluation predates live source capture" in run.stderr
