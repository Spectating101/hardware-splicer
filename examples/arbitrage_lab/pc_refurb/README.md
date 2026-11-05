# pc_refurb: salvage a desktop PC into a verified, sellable product

Adds the missing middle between the PR #286 pilots (economics on paper) and a real machine on a bench. It does not
claim any machine works, any supplier agreed to a price, or any profit.

## Gaps found in #286 and what fills them

| Gap | Evidence | This directory |
|---|---|---|
| Three copies of one economics formula; failed units priced at zero salvage; no stages, no time model | `refurb_pilot.economics`, `channel_pilot.batch_unit`, `whole_working_control` | `staged_economics.py`. Reproduces the handoff's -400 / +560 / +1,520 and NT$212 exactly (tested) |
| Nothing generates the bench evidence the gates ask for; gates check hand-supplied paths | `refurb_pilot.checked_evidence` | `bench_collect.py` (read-only, hash-manifested) + `casefile.py` parses the raw smartctl/memtester/dmidecode/thermal output |
| No whole-PC logic in Circuit-AI (board/component blocks only) | `functional_salvage.py`, `salvage_splice_planner.py` | casefile gates for POST/RAM/SMART/thermal/wipe/network; `bridge_salvage_engine.py` feeds tested parts to the real `SalvageWorkflowEngine` ledger |
| Copilot review of the first cut found four real defects (raw memtest output optional, sparse bundles reaching READY, wipefs exit code ignored, malformed manifest crashed) | `copilot_review_commit` | all four reproduced with failing tests, then fixed (`bench_completeness` gate, strict manifest loading, `signature_rc`) |
| Resale price was one assumed NT$2,200 | `channel_20261105/sources.json` | `market_comps.py` snapshot (below) |
| Preflight `--tests` is environment-dependent and reports it as a bare "TESTS FAILED: 1": system `python3` has no pytest, and `test_committed_native_stl...` read the gitignored `outputs/` path (needs OpenSCAD) instead of the committed `evidence/` mesh | `scripts/hs_salvage_handoff_preflight.py`, `tests/test_arbitrage_pilot.py` | clear "pytest missing" message; the test accepts the committed mesh |

## What the research found (and what it did not)
* **Resale depends on machine class far more than on anything else.** `evidence/market_comps_20261105.json`
  (Ruten, 126 domestic-style listings fetched, 22 usable after dropping barebones/parts/masked-price rows): asks span about
  NT$2,000-16,500, median 5,250. A refurbished i5-8500/16 GB/512 GB SSD listing asks NT$7,200 with 68 sold; an old i5-6500
  8 GB asks about NT$2,000 with 0 sold. These are **asking prices**; `SoldQty` is cumulative per listing, undated.
  Ruten's long spec queries mostly return cross-border listings and no sales; short domestic queries work. 26 listings
  show masked prices (e.g. 993800) that need a human to open and read.
* **The handoff's NT$2,200 class is labor-fragile.** At NT$500/h of operator time its max bid is NT$0; the 8th-gen business class still
  allows about NT$1,090 (`evidence/staged_economics.json`, `sensitivity_labor_rate`). Do not scale scrap-desktop lots.
* **Inspecting each unit before paying is the largest controllable lever** (scrap-class ceiling NT$222 -> NT$345). A 3/3 sample
  inspection on a buy-everything lot barely helps, because the long bench stage cannot be observed before purchase.
* **Labor floor:** Taiwan 2026 minimum wage NT$196/h (public). It is a floor, not your time's value.
* **Windows:** Microsoft's refurbisher program targets high volume, so ship Linux/no OS unless the original COA is photographed.
* **Not established:** whether second-hand electronics trading needs a registered second-hand dealer licence (my searches did not
  reach the controlling text), tax registration, and exact consumer-return exposure for second-hand goods. These are
  `owner_legal_confirmations` gates; the owner confirms them with the local police precinct / city hall / tax office.
* **Government scrap auctions are not a channel here:** the notices found require waste-handling registration of bidders.

## Evidence boundary
| Item | Status |
|---|---|
| `control_host_optiplex/` | REAL read-only collector run on the authorised Optiplex (SMART, DMI, lsblk, ip; serials/MAC/IP/hostname redacted, leak-scanned). Role `control_host`: can never release. Memtest/burn-in deliberately not run on the working host |
| Control-host finding | the Optiplex's own NVMe was at **82 C (its warning threshold)** with `critical_warning=2` when captured; its counters show 1,662 min over warning and 9 min over critical temperature. Not a salvage result, but worth cooling/checking: the casefile reports it as *unknown (retest after cooling)*, not fail |
| Parsers | validated against REAL output: `smartctl -j` (NVMe and ATA, Optiplex), `memtester 4.6.0` and `stress-ng 0.15.06` and the thermal sampler (owner's laptop, `control_host` role). Fixtures in `fixtures/`. Real output exposed two parser hazards that are now tested: memtester's progress backspaces, and the harmless word "failed" in normal runs. The failure *formats* of memtester/stress-ng are still unobserved (no faulty RAM available), so fail paths rely on exit codes plus the documented `FAILURE` marker |
| Measured on hardware (laptop, 8 GiB, 8 threads) | memtester 1 GiB x 2 loops took **600 s** (so ~85% coverage of an 8 GiB machine is roughly an hour; a 16 GiB unit would be over two hours of unattended bench time); 60 s of `stress-ng` peaked at **65 C** with zero throttle events; a SATA SSD's self-test log is not trustworthy, so the collector now records `smartctl -t short`'s own answer |
| Supplier, price, yield, minutes | **assumed or asking-price only.** No contact made, nothing bought |
| Hash checks | detect tampering and mix-ups, not a dishonest operator; the independent reviewer is the control |

## Run
```bash
export PYTHONPATH=apps/mecha-splicer:apps/mecha-splicer/src
python3 examples/arbitrage_lab/pc_refurb/staged_economics.py          # -> evidence/staged_economics.json, inspection_walkaway.csv
python3 examples/arbitrage_lab/pc_refurb/casefile.py examples/arbitrage_lab/pc_refurb/control_host_optiplex/unit.json
python3 -m pytest -q examples/arbitrage_lab/pc_refurb/tests
python3 examples/arbitrage_lab/pc_refurb/market_comps.py              # ~15 requests; re-snapshot prices
```
First physical unit: `RUNBOOK_FIRST_SESSION.md`. Supplier inquiry draft (unsent): `RFQ_V2_ZH_DRAFT_NOT_SENT.md`.

## Path from here to a first sale (each step has an exit test)
1. **Price basis (human, ~1 hour):** open 15-20 *sold* domestic listings (logged-in "已售出" views) in the 8th-gen business class and record the actual prices. Replace `resale_twd`. Exit: a median from sales, not asks.
2. **Supplier (owner decides to send):** RFQ v2; need a per-unit price quote with per-unit pre-payment inspection. Exit: a written quote. Compare to the model ceiling; do not reveal the ceiling.
3. **Legal items (owner):** resolve the `owner_legal_confirmations`. Exit: all four true with notes.
4. **One to three units, inspected before paying.** Run the runbook, get real minutes and the stage at which units fail. Exit: casefile `READY_FOR_INDEPENDENT_REVIEW`, a filled time sheet.
5. **Update priors with the first tranche** (`posterior_ev_draws`); buy the next tranche only if the conservative ceiling clears the quoted price. Stop rule: two consecutive tranches below target EV at measured numbers.
