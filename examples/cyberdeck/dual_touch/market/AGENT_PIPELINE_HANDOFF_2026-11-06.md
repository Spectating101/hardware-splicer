# Cross-agent HS commercial evidence pipeline — executable handoff

**November 6, 2026 · research only · no autonomous market-discovery claim**

## What we tested

The repository contains several valid, independent agents already doing work:

1. **PR #291** `feature/hs-build-vs-buy-20261106`: read-only Ruten API market snapshot, BOM pricing and finished-equivalent comparisons. Specific source pinned at commit `afa56cafacc1d72c1459c58392738b86081589c0`, file `examples/arbitrage_lab/build_vs_buy/evidence/cyberdeck_pi5_20261106.json`. Source data copied intact into [`inputs/pr291_pi5_market_snapshot_20261106.json`](inputs/pr291_pi5_market_snapshot_20261106.json), SHA256 `b65a6f1ac8c10e4ef220d03da733e4e67c5d0bcce05b8ca271c79c1b8e9c40e4`. Full snapshot is ~30 KB; this adapter **does not rewrite its original price research**.
2. **PR #292** native Mecha-Splicer: dual Waveshare 4.3-inch clamshell real CGAL shell evidence. Canonical HS machine release `design_ready`, with six unresolved engineering blockers. The adapter loads and **re-evaluates HS `MachineProject.assess_release()`** and rejects a forged stored approval status.
3. **PR #293** market notes: external Crowd Supply, Kickstarter, GitHub research, and price/source evidence with clear limits. [`inputs/adjacent_market_signals_20261106.json`](inputs/adjacent_market_signals_20261106.json) converts some observations into **typed source records**. These are curated by a research assistant and **not automatically collected/verified by HS**.

**Actual execution:**

```bash
PYTHONPATH=src python3 scripts/hs_market_evidence_handoff.py
PYTHONPATH=src python3 -m pytest -q tests/test_commercial_evidence_bridge.py
```

Output: [`evidence/commercial_handoff.json`](evidence/commercial_handoff.json). CI workflow: `.github/workflows/hs-commercial-research-handoff.yml`.

## Output observed on original source records

| Check | Result |
|---|---|
| PR #291 raw source bytes match pinned SHA256 | PASS |
| PR #291 claimed new-parts Pi5 build min/p25/median independently recomputed from its row-level BOM | NT$6,505 / NT$8,057 / NT$9,374 |
| Label simulated/assumed component costs | `shell_print` and `cables_misc` flagged |
| Source listing benchmark: uConsole asking p25; used laptop asking p25 | NT$7,700 / NT$5,668 |
| Marketplace source is prices and seller-reported SoldQty, **not verified customer orders or sustained sales velocity** | Explicit |
| PR #291 reference hardware is not PR #292 target hardware | Distinct architecture IDs enforced |
| PR #292 target estimated bare BOM | NT$2,965, **unquoted**, no real delivered inventory |
| Canonical HS MachineProject release | `design_ready`; 6 actual blockers |
| Demand evidence | Adjacent Kickstarter/Crowd Supply + general developer activity; **0 verified exact-product buyers** |
| Purchase/manufacturing authority | **DENIED** |

The bridge's response is not "zero demand exists" but **"demand not demonstrated for this exact product yet"**. It emits structured **next_agent_tasks** for discovery, buyer qualification, exact-SKU sourcing and physical HS bench work. The records are suitable for a scheduler or controller to assign, but this branch **does not dispatch agents or place any orders**.

## Critical technical gaps to fill next

- **Autonomous opportunity discovery:** no production pipeline continuously searches GitHub, hobby communities, crowdfunding, e-commerce product listings and customer complaints for new product leads, with deduplication, entity/SKU identity, pagination, timestamps, legal source access and source quotations. Circuit-AI's `research_radar.py` primarily records model/tool candidates; legacy `research_service/dispatcher.py` still returns placeholder summaries. Those are **not** end-to-end market research agents.
- **Market-to-design identity:** multiple agents researched `cyberdeck`, but one priced a 7-inch **Raspberry Pi 5** design, another generated a dual **ESP32-S3** clamshell, and other work has a donated rugged **AIM8I FieldDeck**. These are **three different product architectures**; combining their costs as one would produce fabricated profitability. This bridge guards two of them explicitly.
- **Sales evidence quality:** Ruten's `SoldQty` is seller-reported cumulative sales, not dated, independently verified buyer transactions. Kickstarter backers are not proof buyers will purchase our cyberdeck. No local Taiwan or Indonesia product-specific cohort has been surveyed.
- **Real engineering work:** HS source import and project-to-tools integration are incomplete in October 2026 real cyberdeck experiment, and current PR #292 still lacks powered boards/firmware/host key, safe battery, physical screen fit. A designed bracket or software CI pass is not a functioning machine.
- **Feedback loop:** there is no experimentally measured "phone vs cyberdeck" development-task performance, pain-severity estimate, actual delivered supplier quote, buyer commitment, or dashboard tying market evidence to engineering release.

## How an agent can extend without repeating other work

1. **Read** `inputs/handoff_manifest_20261106.json`: it identifies the producing agent branch+SHA, original source file, SHA256, target/ref architecture. If the source agent advances its snapshot, **update the pinned file + digest deliberately**, then rerun the CI regression.
2. **Fetch/append real signals** using a separate lawful, rate-limited source connector (public API or explicitly permitted data); store stable URLs, observed timestamp, product identity, exact/adjacent relation, evidence kind and provenance. Do **not** invent purchases; with absent transactions emit `buyer_demand=unverified`.
3. **Enrich with exact-SKU supplier quotes** and real region-specific fulfillment costs, not just listing prices. The first gate should reject cases where the BOM has unpriced assumptions.
4. **Measure a real phone/cyberdeck task comparison** before extending the hardware architecture; record accuracy, time, failures and sample/recruitment method.
5. **Only then** promote to an audited commercial pilot review. The current bridge always denies inventory authorization because it cannot independently verify buyers, product fulfillment or compliance. A true approval path requires a separately authorized human/organization, not a score or LLM statement.

**Do not merge into another active worker's worktree:** this PR was developed on isolated branch `agent/hs-market-evidence-bridge-20261106`, stacked atop research PR #293 and using independent PR #291 results only as a pinned read-only data input.

**Bottom line:** HS can now **consume, reconcile and safely limit claims from its own separate research/engineering agents**. HS still does **not** independently discover demand, execute interviews, validate a delivered bill of materials or manufacture a working cyberdeck.
