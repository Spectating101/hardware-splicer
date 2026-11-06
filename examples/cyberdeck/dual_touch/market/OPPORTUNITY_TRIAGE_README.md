# HS commercial opportunity triage (PR #296)

**Status:** read-only research; no independently verified orders or manufacturing authority.

This is the next stage of PR #295's public-source acquisition and PR #294's
cross-agent commercial evidence gate. It answers a narrower, grounded question:
**which user problems and adjacent competing devices merit a controlled next
experiment?** It does **not** infer a total addressable market or profitable
sales from source hits.

## Data and authority sequence

```text
Bounded GitHub issue search + Ruten listing/search  [PR #295]
  -> raw provenance + deterministic relevance filtering
  -> hs.market_signals.v1 (unverified observations)
  -> PR #294 cross-agent handoff:
       immutable PR #291 Pi5 reference pricing
       canonical PR #292 dual-ESP32 MachineProject release
       demand and source-integrity gates
  -> opportunity_rules.json / hs_market_opportunity_triage.py [this PR]
       source-backed issue reports vs topic-only mentions
       competitor model-title groups vs accessories/ambiguous variants
       candidate PRODUCT identity + independent review queue
       before/after source-record changes (no inferred sell-through)
       per-lane cheapest information-gain experiment
```

Read-only CLI:

```bash
PYTHONPATH=src python3 scripts/hs_market_signal_refresh.py --strict
PYTHONPATH=src python3 scripts/hs_market_evidence_handoff.py \
  --signals examples/cyberdeck/dual_touch/market/evidence/live_market_signals.json \
  --out examples/cyberdeck/dual_touch/market/evidence/live_commercial_handoff.json
PYTHONPATH=src python3 scripts/hs_market_opportunity_triage.py
PYTHONPATH=src python3 -m pytest -q tests/test_market_signal_acquisition.py \
  tests/test_live_market_handoff.py tests/test_market_opportunity_triage.py \
  tests/test_commercial_evidence_bridge.py
```

The CI workflow on pull requests executes **offline** and tests the true
canonical HS engineering release under synthetic, source-shaped signals.
The manual/weekly live workflow is only active when the workflow exists on
the **default branch**. A branch-only live smoke may be tested separately;
it does not activate ongoing live research. Generated live JSON files are
workflow artifacts, not automatically committed to the repository.

## Three distinct product tracks

| Lane | Product identity | Available evidence | First unresolved question |
|---|---|---|---|
| Mobile programming | `dual_esp32_touch_4p3_rs485` | Github issue titles, T-Deck Plus seller asks | Who performs real phone programming tasks, and what is the measurable performance gain at a stated price? |
| Field service | `field_terminal_unspecified` | UART/RS485 anecdotes, uConsole adjacent listings | Which field-bus functions, safety/isolation and actual form factor do technicians pay to integrate? |
| Salvage/repair | `repair_donor_unspecified` | Repair issue titles and used ThinkPad asking prices | What are the actual transferred inventory costs, repair yields and realized resale prices? |

**Only the first track inherits PR #292's engineering release assessment.**
The other two are product hypotheses, not alternate configurations of that
machine. No Pi5 reference BOM, used ThinkPad seller ask, or unquoted ESP32
parts projection is transferable across these identities.

## Evidence rules

- A public GitHub issue is a *self-reported title-level problem/feature
  request*. Count distinct repositories as different sources, **not**
  distinct paid customers. Topic-only mentions are separately retained.
- A marketplace listing matches a *name/model phrase*, not necessarily a
  verified exact SKU. Multi-model titles and accessories go to a review
  queue. Only the source's original asking price is retained. No listing
  price is interpreted as a delivered supplier quote.
- A selected source's raw record and displayed title/price must match its
  SHA256. The exact signal-pack bytes must be attested by the canonical
  PR #294 handoff; the target architecture and source-query-plan digest
  must also match.
- For consecutive snapshots, a vanished URL is only
  `not_seen_in_bounded_refresh`. It **cannot** prove the product was
  delisted, sold, out of stock or unwanted. Changed seller counters
  similarly do not prove purchase velocity.
- Even repeated GitHub issues across repositories plus many marketplace
  listings do **not** close the buyer-demand gate. Interview recruiting,
  price-labeled commitments, controlled usability measurements, supplier
  quotations and real engineering validation remain external tasks.

## Limitations and next development milestone

This is an evidence-qualified pipeline **for researcher-seeded lanes**,
not a general market search across all websites or arbitrary product ideas.
Title substring qualification is deliberately inspectable but still
error-prone. The next substantive capabilities are broader compliant
source acquisition, cross-language problem clustering/novelty detection,
seller/SKU entity resolution, and experimentally measured customer
willingness to pay. No scraped or model-created customer claim may
silently become an HS manufacturing authorization.

**Current decision authority: RESEARCH ONLY; safe inventory order = false.**
