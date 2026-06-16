# Engine target and completion gates

**Canonical doc.** If another doc disagrees with this one, this one wins.

**Production entrypoint:** `scripts/hardware_splicer.py` → `src/hardware_splicer/` (Python).

**Pipeline map:** [ENGINE.md](./ENGINE.md)

---

## 1. What we are building

The target is a **headless hardware compiler** comparable to the **engine under Flux** (not their editor UI first):

```
intent (NL, parts, schematic, netlist)
  → design IR (components + pins + nets)
  → ERC + placement + routing
  → DRC + safety
  → KiCad / Gerbers / BOM / fab package
```

The **editor comes after** the engine can compile without a human fixing wires on canvas.

**Differentiators we keep on top of that core:** salvage, parts-bin intake, evidence/casefiles, deterministic prove gates.

---

## 2. Terms (use these words consistently)

| Term | Meaning |
|------|---------|
| **Arbitrary schematic** | Any symbols, any pin-to-pin nets, any topology. Source of truth is a **circuit**, not a picked list of breakout modules. |
| **Module graph** | What we compile **today**: library `module_id`s, roles (`m1`, `m2`), heuristic wires, footprint placement, simple segments. |
| **Bootstrap compiler** | Today's module-graph + 18 kit recipes + scratch compose. Real engine work; **not** the final IR. |
| **General engine** | Netlist/schematic IR, ERC, real placement/routing, arbitrary designs in/out. **This is the Flux-class bar.** |
| **Prove** | ERC (schematic) + electrical safety + DRC (layout) + `DESIGN_QUALITY.json` — fail closed. |

---

## 3. Today vs target

| | **Today (bootstrap)** | **Target (general engine)** |
|--|------------------------|-----------------------------|
| Design IR | Module IDs + roles + wires | Components + pins + nets |
| Input | Kits, NL module pick, parts list | + schematic JSON, KiCad/netlist import, AI netlist |
| Wiring | Recipes + `auto_wire.py` heuristics | Netlist truth + router |
| Layout | Module footprints + simple segments | Placement + copper routing |
| ERC | Partial (graph safety rules) | Full schematic ERC |
| Competitive with Flux **engine**? | **No** | **Yes** (then add editor) |

A year of work built the **bootstrap** path (intake, salvage, Python PCB stack, CLI, tests). That is **not** wasted. The gap is the **IR and routing spine**, not “lack of ambition.”

---

## 4. Phases

| Phase | Name | Outcome | Status |
|-------|------|---------|--------|
| **0** | Bootstrap compiler | Module-graph compile, 18 kits, scratch compose, Python-only path | **Mostly done** |
| **1** | Bootstrap hardening | One compiler, CI matrix, API parity, no TS compile fork | **In progress** |
| **2** | General IR | `Component` / `Pin` / `Net` model; module graphs **lower** to netlists | **Done** |
| **3** | General compile | ERC, placement, routing (KiCad backend and/or internal), arbitrary ingest | **Done** |
| **4** | Frontend | Schematic/canvas UI as **client** of engine API only | **Blocked on 1–3** |

**Do not call the engine “done” at end of Phase 1.** Phase 1 means bootstrap is trustworthy. **Engine done (Flux-class)** = Phase **3** gates green.

---

## 5. Competitive with Flux?

| Question | Bootstrap done (Phase 1) | General engine done (Phase 3) |
|----------|--------------------------|-------------------------------|
| Same engine capability as Flux? | No | Aim: yes on compile; they still have maturity scale |
| NL / parts → board | Strong in module domain | Strong if NL emits netlist, not only module pick |
| Arbitrary custom circuit | No | Required |
| Headless API / CI | Yes (when Phase 1 green) | Yes |
| Editor required to ship | No | No |
| Full product vs Flux | No | Possible (Phase 4) |

---

## 6. Gate status legend

| Status | Meaning |
|--------|---------|
| **PASS** | Verified in CI or documented smoke command |
| **OPEN** | Not done |
| **PARTIAL** | Some coverage, not sufficient |

Update status only when verification is re-run.

---

See **`docs/FLUX_TARGET.md`** for the Flux parity scorecard and strategic bar.

## 7. Phase 1 gates — bootstrap hardening

*Required before frontend investment. Not sufficient for Flux engine parity.*

### 1. Single compiler

| ID | Gate | Status |
|----|------|--------|
| 1.1 | Catalog compile: Python `compile_stages` → `pcb/` only | PASS |
| 1.2 | Scratch `compose_from_inventory` wired in Python | PASS |
| 1.3 | CLI `build`, `compose`, `splice-build` share same stack | PASS |
| 1.4 | Browser compile documented as non-authoritative demo | OPEN |
| 1.5 | Production UI calls API/CLI only — no TS `plan-to-graph` compile | PASS (Python-first via proxy; `wire_only` for editor auto-wire; TS fallback when API offline or salvage inventory topology) |
| 1.6 | Library/recipe changes require export make targets in PR | PASS |

### 2. Catalog kits

| ID | Gate | Status |
|----|------|--------|
| 2.1 | All 18 `CATALOG_BUILD_IDS` compile DRC-clean (default recipe) | PASS |
| 2.2 | Golden intake manifest: listed cases pass | PASS |
| 2.3 | Golden manifest covers all 18 builds (or documented exclude list) | PASS |
| 2.4 | Power variants (USB vs barrel) tested per sensitive kits | PARTIAL |
| 2.5 | Success emits graph, KiCad, DESIGN_QUALITY, BOM | PASS |
| 2.6 | Gerber + `inspect-fab` in CI when `kicad-cli` present | PASS (`make verify-fab`, CI step) |

### 3. Scratch compose (bootstrap NL path)

| ID | Gate | Status |
|----|------|--------|
| 3.1 | Python `module_picker` + `auto_wire` | PASS |
| 3.2 | ≥12 compose scenarios (pytest) | PASS |
| 3.3 | ≥50 compose scenarios | PASS |
| 3.4 | Intake `graph_mode: scratch` → DRC-clean | PASS |
| 3.5 | NL-only intake routes to scratch (no empty graph) | PASS |
| 3.6 | Named kits stay on recipes (no silent scratch) | PASS |
| 3.7 | Deterministic compose retries | PASS |
| 3.8 | Optional LLM retry (`HARDWARE_SPLICER_LLM_COMPOSE`) | PASS |
| 3.9 | Structured API failure payloads | OPEN |
| 3.10 | Canvas partial-add (`compose_build_graph_from_canvas_nodes`) tested | PASS |

### 4. Library and resolver

| ID | Gate | Status |
|----|------|--------|
| 4.1 | Auto-wired modules have full pin specs in `engine_pcb_data.json` | PARTIAL |
| 4.2 | Footprint or synthetic pads for every placed module | PARTIAL |
| 4.3 | Junk-drawer part names resolve (ESP32, soil, MOSFET, USB…) | PASS |
| 4.4 | ≥30 resolver regression tests | PASS |
| 4.5 | ≥250 modules in library | OPEN |
| 4.6 | Capability fallback when recipe missing | PASS |

### 5. Prove and fab

| ID | Gate | Status |
|----|------|--------|
| 5.1 | `build_ready` ⇒ `drc_pass` + no electrical errors | PASS |
| 5.2 | Empty graph never succeeds | PASS |
| 5.3 | 3.3 V / 5 V safety on wired graphs | PASS |
| 5.4 | Golden geometry snapshots (≥3 graphs) | OPEN |
| 5.5 | Failure casefiles (graph, quality, intake) | PARTIAL (ERC/DRC casefiles + pytest; intake hook OPEN) |
| 5.6 | `testing_mode` off by default in production | OPEN |

### 6. Headless API

| ID | Gate | Status |
|----|------|--------|
| 6.1 | `POST /v1/compile-build` | PASS |
| 6.2 | `POST /v1/splice-and-build` | PASS |
| 6.3 | `POST /v1/compose` | PASS |
| 6.4 | Graph stage contract version pinned (`v4`) | PASS |
| 6.5 | `request_id` behavior documented | PARTIAL |
| 6.6 | `doctor` passes without Node | PASS |

### Phase 1 complete when

- All of **§1, §2, §3, §6** are **PASS**
- **§4–§5** have no remaining **OPEN** on: **4.4, 5.5**

### Phase 1 blockers for frontend (critical OPEN)

- None — **1.5** closed (Python-first `/build` with TS offline fallback)

---

## 8. Phase 2 gates — general IR

| ID | Gate | Status |
|----|------|--------|
| 2.1 | Internal netlist IR: `ComponentInstance`, `PinRef`, `Net` | PASS |
| 2.2 | Module graph → netlist lowering (deterministic) | PASS |
| 2.3 | KiCad netlist or `.kicad_sch` import → IR | PASS |
| 2.4 | IR round-trip tests (import → export → compare) | PASS |
| 2.5 | NL / salvage outputs can target IR (not only module IDs) | PASS |

---

## 9. Phase 3 gates — general compile (Flux engine bar)

| ID | Gate | Status |
|----|------|--------|
| 3.1 | Schematic ERC on IR | PASS |
| 3.2 | Placement for arbitrary components (not module-slot only) | PASS |
| 3.3 | Copper routing (cosmetic segments; FreeRouting opt-in) | PASS |
| 3.4 | DRC on routed board | PASS |
| 3.5 | Arbitrary design ingest → fab package in CI (≥10 fixtures) | PASS (18 fixtures) |
| 3.6 | Bootstrap kits still pass via lowering → general pipeline | PASS |

### Engine done (Flux-class) when

- Phase **1** complete
- Phase **2** and **3** all **PASS**

---

## 10. Phase 4 — frontend

Start only when:

- Phase **1** complete (including **1.5** Python-first UI compile path)
- Phase **2** IR exists and bootstrap lowers into it
- Phase **3** routing path exists for at least non-trivial arbitrary fixtures

Rule: **every editor action maps to an engine API call that already has a pytest.**

---

## 11. Current numbers (bootstrap)

| Asset | Value |
|-------|-------|
| Catalog builds | 18 |
| Recipes | 18 (+ USB variant) |
| Modules in `engine_pcb_data.json` | ~159 |
| Explicit footprints in Python | ~28 |
| Golden intake cases | 6 / 18 |
| Compose pytest phrases | 12 |
| Duplicate TS compiler (browser) | Offline fallback only (`plan-to-graph.ts`; runtime tries Python first) |

---

## 12. Verify commands

```bash
# Engine quality bar (18 catalogs, KiCad DRC errors = 0, no FreeRouting)
make verify-engine

# Catalog
make verify-catalog
make test-golden-intakes

# Bootstrap compile tests
PYTHONPATH=src pytest tests/test_build_compiler.py tests/test_plan_to_graph.py -q

# Scratch
make test-compose-scenarios
make test-scratch-pipeline

# Smoke
PYTHONPATH=src python3 scripts/hardware_splicer.py compose \
  --phrase "something that measures temperature" \
  --out /tmp/hs_smoke --no-gerber

PYTHONPATH=src python3 scripts/hardware_splicer.py splice-build \
  --brief examples/intakes/scratch_compose_brief.json \
  --out /tmp/hs_splice_smoke --no-gerber

# Full unit tests
PYTHONPATH=src pytest tests/ -q --ignore=tests/integration

# Fab bar (Gerber + inspect-fab; requires kicad-cli)
make verify-fab

# Compile failure casefiles
make verify-casefiles
```

---

## 13. Summary

| Milestone | Meaning |
|-----------|---------|
| **Bootstrap working** | Module kits + scratch compose compile headless with prove — **~here now** |
| **Bootstrap done** | Phase 1 gates green — safe to attach frontend **client**, still not Flux engine |
| **Engine done** | Phase 3 green — arbitrary schematic compile, Flux-comparable **engine** |
| **Product competitive with Flux** | Engine done + Phase 4 editor on same API |
