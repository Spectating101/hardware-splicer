# Incorporation research — don’t rebuild what the ecosystem already gives away

**Goal:** Flux-class engine by **integrating** proven OSS, not rewriting routing, KiCad I/O, ERC, parts search, or viewers from scratch.

**Bar:** Every layer below should answer: *can we vendor, subprocess, or API-call this in a week — not invent it in a quarter?*

---

## Executive summary — recommended stack

| Layer | Use this (primary) | Fallback | Do NOT build |
|-------|-------------------|----------|--------------|
| **Fab truth** | `kicad-cli` (DRC, ERC, gerber, netlist, STEP) | — | Custom DRC as sole gate |
| **Copper routing** | **FreeRouting** (DSN/SES or REST API) | `@tscircuit/capacity-autorouter` (MIT) | Toy A* grid router |
| **Schematic I/O** | **kiutils** or **kicad-skip** | `kicad-sch-api` | Hand-rolled sexpr forever |
| **Netlist / code circuits** | **SKiDL** (MIT) | Our `CircuitNetlist` IR | Duplicate ERC rules |
| **Part pick (JLC/LCSC)** | **yaqwsx/jlcparts** + **jlcsearch API** | `jlcpcb-mcp` for agents | Scrape DigiKey from zero |
| **Placement** | **OpenROAD SA-PCB** or HPWL SA (`simanneal`) | `learned-pcb-placement` (research) | Module-slot only forever |
| **Intermediate IR** | Our netlist + **circuit-json** adapter (optional) | — | Third parallel IR |
| **Schematic SVG / PCB view** | **@tscircuit/schematic-viewer**, **pcb-viewer** | Existing React Three in `/build` | Full canvas engine v1 |
| **Agent ↔ KiCad** | **EDA MCP** (Conare) patterns | `kicad-python` IPC | LLM writes pcbnew scripts |

**Strategic call:** KiCad is the **physics engine**. FreeRouting (or tscircuit autorouter) is the **copper engine**. SKiDL/kiutils are **schematic engines**. We own **intent → IR → orchestration → evidence**, not EDA internals.

---

## 1. KiCad as the compile backend (highest ROI)

You already have `kicad-cli` on PATH (9.0.2). This is the single biggest “don’t rewrite” win.

### What `kicad-cli` gives for free

| Command area | Use for |
|--------------|---------|
| `kicad-cli sch export netlist` | Schematic → netlist (already used in `api_server.py`) |
| `kicad-cli sch erc` | Real ERC JSON reports |
| `kicad-cli pcb drc` | Real DRC JSON (now wired in `kicad_cli_drc.py`) |
| `kicad-cli pcb export gerbers` | Fab output (partially via `gerber_generator.py`) |
| `kicad-cli pcb export step` | Mechanical / 3D evidence |

**Docs:** https://dev-docs.kicad.org/en/apis-and-binding/index.html

### KiCad IPC / `kicad-python` (KiCad 9+)

- **When:** Need live board read/write while KiCad is open (plugins, interactive fix loop).
- **Package:** `pip install kicad-python` — official IPC wrapper.
- **Note:** IPC is PCB-only in 9.0; schematic IPC coming later. Headless CI should prefer **CLI + file parsers**, not “KiCad must be running.”

### Already in this repo

- `apps/circuit-ai/api_server.py` — `kicad-cli sch export netlist`
- `apps/circuit-ai/src/engines/gerber_generator.py` — gerber via kicad-cli
- `apps/circuit-ai/src/engines/layout_advisor.py` — legacy `pcbnew` (deprecate → IPC or CLI)
- `src/hardware_splicer/pcb/kicad_cli_drc.py` — DRC on emitted PCB
- `src/hardware_splicer/netlist/import_kicad.py` — netlist sexpr parse (extend, don’t replace)
- `examples/kicad_pcb_fixtures/` — KiCad 9 demo boards for CI
- Frontend `lib/kicad/sexpr.ts` — sexpr tokenizer (KiCanvas-inspired)

**Action:** Make **every** compile artifact path through: emit `.kicad_pcb` → `kicad-cli pcb drc` → gerber export. Internal geometry DRC stays **fast pre-check** only.

---

## 2. Routing — stop inventing; integrate

### A. FreeRouting (production-grade, GPL-3.0)

- **Repo:** https://github.com/freerouting/freerouting
- **Stars:** ~1.7k | **License:** GPL-3.0
- **Integration:** DSN in → SES out (classic); **or** REST API `https://api.freerouting.app/v1` (beta)
- **KiCad 9:** Plugin + hybrid JSON/IPC bridge (alpha) — https://github.com/freerouting/freerouting/tree/master/integrations/KiCad

**Pipeline:**

```
.kicad_pcb → export DSN (kicad or tscircuit/dsn-converter) → FreeRouting → SES → import → kicad-cli drc
```

**License note:** GPL is fine as **subprocess** (like Git). Do not statically link into proprietary core without legal review.

**Already in repo:** `apps/circuit-ai/src/engines/generative/routing_engine.py` — grid A* toy; **replace or demote** behind FreeRouting.

### B. tscircuit autorouter ecosystem (MIT — friendly fork)

| Package | Role |
|---------|------|
| [circuit-json](https://github.com/tscircuit/circuit-json) | Interchange IR (schematic + PCB + BOM + warnings) |
| [dsn-converter](https://github.com/tscircuit/dsn-converter) | circuit-json ↔ Specctra DSN |
| [@tscircuit/capacity-autorouter](https://github.com/tscircuit/tscircuit-autorouter) | MIT full-pipeline autorouter (Node) |
| [@tscircuit/routing](https://github.com/tscircuit/routing) | Lighter deterministic routes |

**Why care:** They already solved **IR → DSN → route → traces → gerber/svg**. Flux competes in this lane; tscircuit is MIT and agent-friendly.

**Action:** Add adapter `CircuitNetlist` / `BuildGraph` → `circuit-json` → capacity-autorouter OR dsn-converter → FreeRouting.

### C. OpenROAD / research placement (not routing copper yet)

- **SA-PCB:** https://github.com/The-OpenROAD-Project/SA-PCB — simulated annealing placement, C++
- **learned-pcb-placement:** GNN-biased SA, KiCad `.kicad_pcb` parser — research quality
- **RL_PCB:** RL placement — academic, heavy

Use for **placement** after routing path works, not before.

---

## 3. Schematic read/write — don’t parse sexpr by hand

| Library | License | Best for |
|---------|---------|----------|
| [kiutils](https://github.com/mvnmgrx/kiutils) | Check repo | Dataclass `.kicad_sch` / `.kicad_pcb` read/write, SCM-friendly |
| [kicad-skip](https://github.com/psychogenic/kicad-skip) | GPL? | Interactive schematic edit, spatial queries, wires |
| [kicad-sch-api](https://github.com/circuit-synth/kicad-sch-api) | MIT | Byte-exact `.kicad_sch` generation |
| Frontend `sexpr.ts` | In-tree | Browser parse only |

**Action:** Python engine adopts **kiutils** for `.kicad_sch` export from `CircuitNetlist`. Retire custom sexpr tokenizer in Python except netlist import.

**Agent path:** [EDA MCP Server](https://conare.ai/marketplace/mcp/eda-mcp) — 39 KiCad 9 tools (add symbol, wire, ERC, export). Good reference for Circuit.AI Jarvis tools calling **same** headless backend.

---

## 4. ERC / netlist / “circuits as code”

| Library | License | Use |
|---------|---------|-----|
| [SKiDL](https://github.com/devbisme/skidl) | MIT | Python circuits → netlist, built-in ERC |
| [Schemdraw](https://schemdraw.readthedocs.io/) | MIT | Documentation / teaching SVGs (not fab) |
| KiCad `kicad-cli sch erc` | — | Authoritative schematic ERC |

**SKiDL fit:** NL → SKiDL codegen → `generate_netlist(tool=KICAD9)` → existing import path. Faster than growing module-picker forever for **arbitrary** designs.

**Already planned:** `docs/ENGINE_DONE.md` gate 2.5 (NL → IR). SKiDL is a shortcut for codegen, not a replacement for our IR.

---

## 5. Parts library / BOM (Flux has LCSC; we need this)

| Project | What |
|---------|------|
| [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) | Source SQLite of full JLC catalog (~11GB raw) |
| [tscircuit/jlcsearch](https://github.com/tscircuit/jlcsearch) | Optimized search + **JSON API** (`*.json` URLs) |
| [casimir-engineering/jlc-search](https://github.com/casimir-engineering/jlc-search) | Self-hosted 3.5M+ parts, parametric filters |
| [Eyalm321/jlcpcb-mcp](https://github.com/Eyalm321/jlcpcb-mcp) | MCP for agents — search, stock, pricing |
| [mageoch/LCSC-MCP-Server](https://github.com/mageoch/LCSC-MCP-Server) | KiCad symbol/footprint download from LCSC |

**Action:** Module library stops at **breakout/board** level; passives and discretes come from **jlcsearch API** + auto-footprint. Matches how real designs are built.

**Example API:**

```bash
curl 'https://jlcsearch.tscircuit.com/resistors/list.json?resistance=1k&package=0603'
```

---

## 6. UI / viewers — borrow, don’t rebuild Flux canvas v1

You already have Circuit.AI `/build` (ReactFlow + Three.js). For Flux parity **views**:

| OSS | MIT? | Use |
|-----|------|-----|
| [@tscircuit/schematic-viewer](https://github.com/tscircuit/schematic-viewer) | Yes | Schematic render from circuit-json |
| [@tscircuit/pcb-viewer](https://github.com/tscircuit/pcb-viewer) | Yes | PCB render |
| [@tscircuit/3d-viewer](https://github.com/tscircuit/3d-viewer) | Yes | 3D board |
| [circuit-to-svg](https://github.com/tscircuit/circuit-to-svg) | Yes | Export SVG |

**Strategy:** Engine emits **circuit-json** or KiCad files; UI picks viewer. `/build` becomes a client, not a second compiler.

---

## 7. “Flux killers” to study (not necessarily fork)

| Project | Lesson |
|---------|--------|
| [tscircuit](https://github.com/tscircuit/tscircuit) | Code-first + circuit-json + autoroute + registry — closest OSS to Flux AI-native |
| [atopile](https://github.com/atopile/atopile) | Constraints, assertions, KiCad layout sync — validation philosophy |
| [Horizon EDA](https://github.com/horizon-eda/horizon) | Full GPL EDA — overkill to embed, good UX ideas |
| [LibrePCB](https://github.com/librepcb/librepcb) | Clean project model — different stack |

**Take:** Steal **IR + validation + package registry** patterns. Do not embed second full EDA.

---

## 8. What we already have (don’t duplicate)

| In-tree | Status | Verdict |
|---------|--------|---------|
| `plan-to-graph.ts` + Python parity | 18 recipes | Keep until IR covers all; then **lower** recipes to netlist |
| `auto_wire.py` / module picker | Bootstrap | Keep for maker UX; not Flux-class |
| `routing_engine.py` (A*) | Toy | **Replace** with FreeRouting or capacity-autorouter |
| `gerber_generator.py` | Works w/ kicad-cli | Keep |
| `netlist/` IR + ERC | Growing | **Center of truth** — adapters outward |
| `engine_pcb_data.json` modules | ~159 | Complement with jlcparts for discretes |
| Vision / salvage / repair APIs | Differentiated | Keep — Flux weak here |

---

## 9. Phased incorporation (engine-first)

### Phase A — Fab honesty (days–weeks)

1. KiCad 9 PCB serializer (done)
2. `kicad-cli pcb drc` on every compile (done)
3. `kicad-cli pcb export gerbers` in CI gate
4. `kicad-cli sch erc` when `.kicad_sch` exists

### Phase B — Real copper (weeks)

1. Subprocess **FreeRouting** DSN/SES OR `@tscircuit/capacity-autorouter`
2. Import routed SES back into `.kicad_pcb` (kiutils or kicad-cli)
3. Golden tests: route → DRC errors **down** vs cosmetic router

### Phase C — Schematic truth (weeks)

1. **kiutils**: `CircuitNetlist` → `.kicad_sch`
2. **kicad-cli sch export netlist** round-trip tests
3. Optional: SKiDL for NL → netlist codegen

### Phase D — Parts (weeks)

1. jlcsearch JSON client in `module_resolver` / BOM
2. MCP tools for Jarvis (jlcpcb-mcp patterns)
3. LCSC → KiCad symbol download for picked parts

### Phase E — UI (after B passes)

1. Retire TS compile authority → call Python API
2. Plug tscircuit viewers OR keep ReactFlow as edit layer on circuit-json

---

## 10. License quick reference

| Project | License | Integration style |
|---------|---------|-------------------|
| FreeRouting | GPL-3.0 | Subprocess / API only |
| SKiDL | MIT | pip dependency |
| kiutils | Check PyPI | pip dependency |
| tscircuit/* | MIT | npm + adapters |
| kicad-skip | GPL (verify) | Subprocess or avoid linking |
| OpenROAD SA-PCB | BSD-ish (verify) | Binary subprocess |
| jlcparts data | Check repo | Data download |

---

## 11. Anti-patterns (waste time)

- Writing another Manhattan router “until FreeRouting is wired” — wire FreeRouting first
- Maintaining **two** ERC systems as equals — KiCad ERC wins for schematic; IR ERC for pre-layout
- Growing module-picker to 10k “modules” — use jlcparts for passives
- LLM-generated `pcbnew` scripts as production path (see `GENERATIVE_KICAD_WORKFLOW.md`) — demos only
- Calling bootstrap kits “engine done” — see `FLUX_TARGET.md`

---

## 12. First three PRs to open — **DONE (2026-06)**

| PR | Status | Path |
|----|--------|------|
| FreeRouting bridge | **Wired** | `src/hardware_splicer/integrations/freerouting_bridge.py` → `geometry_compile.py` (`HARDWARE_SPLICER_AUTOROUTE=1`) |
| Schematic export + KiCad ERC | **Wired** | `integrations/schematic_export.py` + `pcb/kicad_cli_erc.py` → `netlist/compile.py` |
| jlcsearch client + BOM enrich | **Wired** | `integrations/jlcsearch_client.py` → `bom_generator.enrich_bom_with_jlcsearch` → `compile_stages.run_artifact_stage` |
| circuit-json adapter | **Wired** | `integrations/circuit_json_adapter.py` → `circuit_json.json` on compile |

### Environment flags

| Variable | Default | Purpose |
|----------|---------|---------|
| `HARDWARE_SPLICER_AUTOROUTE` | `0` | `1` enables FreeRouting (Java; opt-in when ready) |
| `HARDWARE_SPLICER_FREEROUTING_JAR` | — | Override JAR path (else cached under `~/.cache/hardware-splicer/freerouting/`) |
| `HARDWARE_SPLICER_FREEROUTING_VERSION` | `2.1.0` | JAR version (2.1.0 for Java 21; 2.2.x needs Java 25) |
| `HARDWARE_SPLICER_JLC_ENRICH` | `1` | `0` skips jlcsearch BOM enrichment |
| `HARDWARE_SPLICER_JLCSEARCH_BASE` | `https://jlcsearch.tscircuit.com` | API base URL |

### Tests

`tests/test_integrations.py` — schematic/circuit-json on compile, FreeRouting (skip without java+jar+pcbnew), jlcsearch mock.

---

## References

- FreeRouting: https://github.com/freerouting/freerouting
- tscircuit circuit-json: https://github.com/tscircuit/circuit-json
- tscircuit capacity-autorouter: https://github.com/tscircuit/tscircuit-autorouter
- kiutils: https://github.com/mvnmgrx/kiutils
- SKiDL: https://devbisme.github.io/skidl/
- jlcparts: https://github.com/yaqwsx/jlcparts
- jlcsearch: https://github.com/tscircuit/jlcsearch
- KiCad dev docs: https://dev-docs.kicad.org/
- EDA MCP (KiCad 9 tools): https://conare.ai/marketplace/mcp/eda-mcp
- Internal: `docs/FLUX_TARGET.md`, `docs/ENGINE_DONE.md`
