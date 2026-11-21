# Hardware Splicer — Optiplex Claude handoff: real salvage → functioning product

**Prepared 2026-11-05 (Taiwan). This is an executable project handoff, not evidence of a physical repair or of profit.**

**Repository:** [Spectating101/hardware-splicer](https://github.com/Spectating101/hardware-splicer)
**Active development:** [draft PR #286](https://github.com/Spectating101/hardware-splicer/pull/286), branch `feature/hs-arbitrage-marketpilot-20261105`.
**Snapshot I inspected:** `cba83dda5bb0b8661001bb6628e156536619934e` (follow later commits on the same branch).
**Base at this snapshot:** `origin/main` at `38dbad2b759a9313b81a5b10bfde7f20d64f308c`. **Do not assume #286 is merged.**
**Existing working checkout on this Optiplex at handoff:** `/tmp/hs-arbitrage-marketpilot-20261105` (a git worktree; do not assume its directory remains forever).
**Other guidance:** root [`CLAUDE.md`](../CLAUDE.md), [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md), [`docs/MACHINE_PROJECT_SPINE.md`](MACHINE_PROJECT_SPINE.md) and [`docs/INTEGRATION_STACK.md`](INTEGRATION_STACK.md). Existing contract is evidence-first; nothing is implicitly upgraded to physical authority.

## The mission

**Turn HS into a useful engineering operator for legitimately acquired junk electronics, capable of choosing and delivering a complete, physically testable, commercially sensible product.** Not a new spreadsheet app, bracket generator, new generic viewer or synthetic CAD-only demonstration.

- Starting input: an owner-authorized **actual device or documented multi-device salvage lot**, with title/resale permissions, exact models, condition, measurements, missing parts and photographs.
- Desired outcomes (rank by *net value per engineering hour*): **restore whole device**, **upgrade whole device into a verified useful system**, **repurpose tested subassemblies into a new complete device**, **sell independently tested parts**, or **reject/recycle**.
- Required output: provenance; observed vs inferred inventory; diagnostic/repair/reuse route; electrical/firmware/mechanical interfaces as needed; BOM; time and risk estimates; verified market pricing; actual acceptance tests; go/no-go bid cap; explicit physical proof or open blockers.
- Only treat a device as functioning after real, independently reviewed measurements on that specific physical device. A live OS on the unrelated Optiplex is **not** proof a salvaged PC works.

**Important correction:** commodity 3D-printed router brackets in the old pilot are deliberately a **low-margin negative control**, **not** the flagship HS product or target. The owner wants finished systems and real arbitrage.

## Start here — paste/run from a clean repo root

```bash
git fetch origin
# If this feature branch already exists locally, switch to it.
git switch feature/hs-arbitrage-marketpilot-20261105 \
  || git switch --track -c feature/hs-arbitrage-marketpilot-20261105 origin/feature/hs-arbitrage-marketpilot-20261105
git status -sb
git log -3 --oneline
python3 scripts/hs_salvage_handoff_preflight.py --tests
```

If another agent has uncommitted edits, **do not force checkout, reset, clean or overwrite them**; use a separate git worktree. The preflight is non-destructive, checks existing evidence-status boundaries and optionally runs focused tests; it **does not** validate physical equipment.

### Exact repo capability map — reuse before inventing

| Existing implementation | What it really contributes | Caveat |
|---|---|---|
| `apps/circuit-ai/src/intelligence/salvage_splice_planner.py` / `SalvageSplicePlanner` | Functional block candidates, reuse/splice plans, hazard/evidence gates | Can propose a camera *mount* from an untested chassis; **do not treat catalogue candidates as verified viable products** |
| `apps/circuit-ai/src/intelligence/hardware_plan.py` / `HardwarePlanOrchestrator` | Existing repair/reuse/resource orchestration and repair-authority summary | Generic BOM suggestions on a NUC/Zebra listing are **not** part-number-grounded repairs; explicitly excluded from price screens |
| `apps/circuit-ai/src/intelligence/salvage_workflow_engine.py`, `salvage_pipeline.py`, `salvage_opportunity_engine.py` | Inventory/listing ingestion, candidate product recipes and reports | Some paths mix vendor listing/prospective inventory and output USD catalogue values; **do not equate with physical ownership or profit** |
| `apps/circuit-ai/scripts/intake_real_board_case.py` and `src/intelligence/bench_topology_capture.py` | Physical board casefile/photo/manual bench capture templates | Vision/output guesses have no production or electrical authorization |
| `src/hardware_splicer/salvage_bringup.py`, `docs/AGENT_HANDOFF.md` | Existing hardware-splicer SDK/MCP, splice compile/DRC, bench gates and release semantics | KiCad DRC is not actual electrical/fit/fabrication/power validation |
| `examples/arbitrage_lab/salvage_lot/channel_20261105/read_only_bench.py` | Actually executed **read-only** CPU/RAM/block-device metadata capture on authorized Optiplex | Does not run memtest, SMART, drive erase, hardware POST, power-stage checks or claim new salvage |
| `examples/arbitrage_lab/refurb_nuc11/` | Real no-power NUC11PAH case, manufacturer-specific repair gates and risk-aware economics | Seller lists no LEDs, no RAM/SSD, CPU i3/i5/i7 variant unknown; **NO BUY** |
| `examples/arbitrage_lab/industrial_printer/` | ZT230/ZPL offline barcode acceptance fixture, printhead replacement downside and TSC no-head rejection | Synthetic ZPL **never printed**, printhead/printing on real machine untested |
| `examples/arbitrage_lab/salvage_lot/` | Real sourced giveaway/paid-lead scenarios, lawful ownership checks and economic paths | PTT Give prohibits gift resale; **zero legally acquired commercial stock** |
| `examples/arbitrage_lab/salvage_lot/channel_20261105/` | Actual Zhongli recycler contact lead, working-claimed Acer counterfactual, supplier RFQ and batch sensitivity | Recycler's NT$140 is a **scrap BUYBACK it pays owners**, **not** its selling price to HS |

Use `rg` to find related parts and their tests **before** adding a new subsystem. Avoid rebuilding vision, CAD, economics, stock/asset ledger, generic repair planner or remote worker runner that the repo already has.

## Frozen evidence to read (these files exist)

- [Main product/economics pilot entry](../examples/arbitrage_lab/README.md)
- [Real sourced salvage lot and legal-rights evidence](../examples/arbitrage_lab/salvage_lot/README.md) · [machine-run decision](../examples/arbitrage_lab/salvage_lot/evidence/salvage_decision.json)
- [Zhongli/Daxi commercial supplier channel study](../examples/arbitrage_lab/salvage_lot/channel_20261105/README.md) · [source snapshot](../examples/arbitrage_lab/salvage_lot/channel_20261105/sources.json) · [run decision](../examples/arbitrage_lab/salvage_lot/channel_20261105/evidence/channel_decision.json) · [batch sensitivity](../examples/arbitrage_lab/salvage_lot/channel_20261105/evidence/batch_sensitivity.csv)
- [Chinese legal-transfer commercial-lot inquiry — **NOT SENT**](../examples/arbitrage_lab/salvage_lot/channel_20261105/SUPPLIER_RFQ_ZH.md)
- [Actual running Optiplex read-only probe (not a salvaged unit)](../examples/arbitrage_lab/salvage_lot/channel_20261105/evidence/optiplex_control_readonly.json)
- [NUC condition/economics](../examples/arbitrage_lab/refurb_nuc11/evidence/refurb_decision.json) · [Zebra condition/economics](../examples/arbitrage_lab/industrial_printer/evidence/industrial_refurb_screen.json)
- [Dedicated GitHub CI workflow](../.github/workflows/hs-arbitrage-market-pilot.yml): exercises each source/condition/economic scenario and uploads *research-only* artifacts.

### Numeric boundary — scenarios, not achievements

- Five **hypothetical** retired desktops at **NT$250 purchase per PC** (not quoted by a seller), NT$600 lot pickup and NT$2,200 **assumed** resale per working PC: expected **−NT$400 for batch at 50% recovery**, **+NT$560 at 65%**, **+NT$1,520 at 80%**. At 65% hypothesized yield, max bid **NT$212/unit** to retain NT$150 expected profit/unit.
- A *working-claimed* Acer TC-865 i5-8400 is advertised **NT$2,800**. At NT$5,000 hypothetical resale, profit if genuinely validated and sold **NT$525**, but expected **−NT$245** at an **assumed** 80% success probability. High-end NT$6,300 comparator is **better-equipped**, not proof this PC sells for that.
- ZT230 unit for NT$1,200 is power-on-*claimed*, not print-tested. Head replacement at **NT$7,000 assumed** makes all screen prices economically negative.
- Paid damaged i5-7400+Z170M NT$600, with CPU-only public asks about NT$500, is a **reject** despite cheap entry.
- **None of the sale values, recovery probabilities, scrap-lot availability or yield rates is verified.** Donor/source names are leads, not contracts. No purchases, contact messages or physical scrap pickups have occurred.

### CI status at inspected SHA

- Focused local economics/rights/bench tests: **60 passed**.
- PR-specific **HS Salvage / Functional Refurb Product Evidence** GitHub workflow: **success**.
- Broad **Core Diagnostics** CI: **failure**, but **Full Python regression suite**, **Project store and review regression** and **Engineering core fast bar** jobs **passed**. The separate `diagnose` job failed during KiCad 9 PPA setup with an external **Launchpad 503 Service Unavailable**, and subsequent steps failed because the expected `.venv` had not been created. **Do not conflate this CI infrastructure failure with proof of a source-engineering defect.** Re-evaluate fresh branch CI after modifications.
- No specific salvage product has passed physical release or generated revenue.

## First concrete Claude mission — NOT another 1,000-line scenario simulator

**Priority P0: capability consolidation and a single genuine end-to-end product path.** Do this in **small, testable commits**, on a separate branch or worktree off #286 (do not accidentally merge draft research as production truth).

1. **Audit existing systems** for salvage → casefile → repair authority → functional validation → market bid → release. Produce a short matrix with **existing API/function, status, one runnable invocation, missing connection, and evidence ceiling**. Look specifically at the real Circuit-AI `SalvageWorkflowEngine`, `HardwarePlanOrchestrator`, `SalvageSplicePlanner`, bench capture and HS SDK. Validate module behavior by running actual calls, not solely reading names.
2. **Select one full product vertical:** a **refurbished, working desktop PC** from an authorized retired unit or small mixed-PC lot. Compare *repair whole machine* vs *part-out* vs *NAS/edge upgrade* **only if tested CPU/RAM/storage/PSU are actually available**. Do not pick the plastic bracket, display mount or arbitrary motor controller as a substitute for a complete saleable product.
3. **Bridge existing engines without duplicating them:** design a narrow evidence-typed adapter/casefile that takes a sourced lot with owner rights, component provenance and actual bench readings. Missing CPU, working state, identity, profitability or permission must remain **unknown / blocked**. Feed the verified subsets into existing salvage and engineering routines; output a single `go/no-go` decision with BOM, diagnostics, functional tests, acquisition ceiling and the basis for all prices.
4. **Exercise the real Optiplex safely as a control** using existing read-only diagnostics. You may extend **read-only** proof capture *only if you can demonstrate no data/OS/device changes*. Keep results segregated: `control_host`, **not** `salvaged_unit`. Actual repairs on an unrelated system are still unproven.
5. **Validate against one independent publicly documented PC restoration/teardown case** from source images/video/text if available, distinguishing the source's observations from HS inference. This can demonstrate reconstruction of a repair plan but is *not a hardware experiment*. Prefer genuine, citable public materials to fabricated fixtures.
6. **Before any physical unit is obtained**, produce the operator's first-physical-session checklist (exact meter/test equipment, inspection steps, evidence fields, fault-branching, PC secure wipe and acceptance). Do not falsely close hardware gates.
7. **Open a draft PR** from a clean feature branch with source paths, reproducible commands/tests, pass/fail results and **specific unresolved physical dependency**. Do not merge automatically.

**Do not add another broad UI, CAD product or listicle of arbitrage opportunities.** The next integration should lower the cost/time to *physically validate and resell an entire computer*. If you discover an existing complete flow, show it and close missing tests instead of writing a replacement.

## Acceptance criteria for your first Claude PR

- One exact, existing repo function/CLI path goes from **provenance-aware candidate intake → real HS engines → actionable diagnostics/BOM/product choice → auditable release gate and profit gate**.
- A **no-hardware case** rejects: missing permission, unknown model/parts, contradictory measurements, unrealized asking-price comparators and guessed success probabilities **without being marked physically verified**.
- If no real lot exists, label any sample **public case** or **fixture** and do not silently import it as owner stock. Real Optiplex read-only reports remain a *separate control*.
- A functional product means genuine POST+memory+SMART/storage sanitization+thermal/ports/network checks on **the actual acquired machine** (or equivalent physically verified tests for non-PC products), not a simulator/CSV/CI pass.
- Show a clear margin threshold **after labor, transport, components, fees, returns/disposal and tested yield**. Unknown yield means the **bid stays provisional**, regardless of advertised recycler buyback.
- No destructive disk writes/erase, flashing, power alteration, unsolicited merchant contact/offer/purchase, accessing third-party data, municipal bin collecting, breaking-in, opening mains PSU, or physical device actuation **without separate explicit authorization and appropriate physical safety controls**.
- Existing contracts/release semantics stay intact; targeted regression and relevant end-to-end tests pass. If infrastructure fails, identify *which step and why*.

## What to report back to the owner

Please give a concise, executable report with:

1. **Exact repo branch/commit/PR**; files added or changed.
2. **What reused existing HS versus genuinely missing**; no speculative "feature complete" claims.
3. **One functional product case and what is actually observed**; unresolved physical tests and acquisition permission.
4. **Economics with stated assumptions**, bid/no-bid recommendation, and whether a seller *actually* agreed to sell at the modeled price.
5. **Proof:** commands, artifacts, test failures/passes; differentiate software evidence vs actual product function.
6. **One physical next requirement** if real progress depends on an actual device. Do not ask for hardware until it materially blocks a valuable further software step.

**If all you can prove is that a script generated a report, call that a report—not a working product.**
