# HS public-market acquisition — PR #294 follow-on

**Scope: working source-acquisition implementation for seeded jobs, not proof of product-market fit.**

This follow-on adds an independently executable **read-only** data-acquisition stage. It deliberately reuses PR #294's `hs.market_signals.v1` contract and canonical HS engineering gates rather than building a new product business engine or copying PR #291's BOM/pricing algorithm.

- GitHub's public issue search provides traceable self-reported developer friction (not buyer interviews). It paginates under explicit budgets, excludes PRs, deduplicates canonical issue URLs and records coverage/truncation.
- The existing PR #291 Ruten API endpoint family is used **only for product-discovery price observations**, with bounded search/detail calls. It does not redo BOM filtering, matching or profit calculations. Ruten `SoldQty` remains a seller-reported **cumulative** counter, never verified sales or sales velocity. Variant-price identity remains unverified.
- The plan covers mobile development, field terminals, and salvage/repair contexts. These are *seeded research lenses*; it does **not** yet discover genuinely novel product classes or scrape all social media.
- Source hashes, observation dates, public URLs, per-job provenance, missing pages and source failures are retained in `live_market_signals.json`. A provider failure causes an explicitly partial result; zero usable observations cause the refresh command to fail.
- `hs_market_evidence_handoff.py --signals ...` accepts the acquisition pack without changing PR #294's frozen curator pack or pinned PR #291 pricing source. It reruns the canonical `MachineProject` release gate, maintains separate Pi5/ESP32 identities and rejects any commercial authorization.

## Run

```bash
PYTHONPATH=src python3 scripts/hs_market_signal_refresh.py --plan-only
PYTHONPATH=src python3 -m pytest -q tests/test_market_signal_acquisition.py tests/test_commercial_evidence_bridge.py
# Explicitly opt in to external, read-only public API access:
PYTHONPATH=src python3 scripts/hs_market_signal_refresh.py --strict
PYTHONPATH=src python3 scripts/hs_market_evidence_handoff.py \
  --signals examples/cyberdeck/dual_touch/market/evidence/live_market_signals.json \
  --out examples/cyberdeck/dual_touch/market/evidence/live_commercial_handoff.json
```

Workflow `hs-public-market-signal-refresh.yml`: PRs run **offline tests only**. Manual dispatch can acquire fresh data from this branch. Weekly schedule becomes active only if merged into the default branch. Live snapshots are CI artifacts, **not silently committed** into the evidence record. GitHub API may rate limit; Ruten may refuse requests or change its API; every failure is visible, not hidden by static fallback research.

## Next genuine capability gates

1. Broader compliant source connectors and de novo topic clustering/novelty detection (rather than only predefined jobs), with source-rights review and drift metrics.
2. Exact SKU/variant and geography resolution before comparing alternatives or calculating arbitrage.
3. Qualified buyer sampling, price-specific willingness-to-pay and measured phone-versus-deck usability trials.
4. Supplier quotations, real unit tests, security and relevant Taiwan/Indonesia certification gates.

**No purchases, customer contacts, authenticated account scraping, inventory approval, engineering sign-off or autonomous manufacturing.** The new output is collected observational evidence only.
