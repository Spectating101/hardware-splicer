# Integration research — repos, libraries, MCP, skills

Living doc for **external tools we can adopt** to raise sophistication without reinventing Flux/KiCad/JLC stacks. Prioritized by fit with Hardware-Splicer’s thesis: **headless compile truth + salvage + evidence gates**.

Last reviewed: 2026-06 (post netlist engine hardening).

---

## How to use this doc

| Priority | Meaning |
|----------|---------|
| **P0** | Wire in next — closes an ENGINE_DONE gate or removes duplicate code |
| **P1** | High leverage after P0 — fab, library, or agent surface |
| **P2** | Valuable but heavier — new runtime, license, or human-in-loop product |
| **Watch** | Track; don’t depend on yet |

Integration pattern we prefer:

```
external tool → thin adapter in src/hardware_splicer/integrations/
              → pytest + verify-* target
              → optional MCP tool exposure via hardware_splicer.mcp_server
```

---

## P0 — Close gates / retire forks

### 1. Single Python compiler (gate **1.5**)

| Item | Status in repo |
|------|----------------|
| `POST /v1/compile-build`, `/v1/compose` | Done |
| Next.js proxy `/api/proxy/hardware-splicer/*` | **Added** |
| `NEXT_PUBLIC_HARDWARE_SPLICER_ENGINE=1` on `/build` | **Added** (catalog splice via Python) |
| Retire TS `plan-to-graph` for runtime compile | **OPEN** — keep for recipe export + fallback |

**Next:** Route `auto_wire` / canvas compose through proxy; delete TS DRC fork when API returns `design_quality_gate`.

### 2. Gerber + fab inspection CI (gate **2.6**)

| Item | Status |
|------|--------|
| `scripts/verify_fab.py` + `make verify-fab` | **Added** |
| CI step after `verify-engine` | **Added** |
| Uses existing `fabrication_inspection.py` + `kicad-cli` gerbers | Done |

**Borrow from (reference, not vendoring whole plugins):**

- [bennymeg/Fabrication-Toolkit](https://github.com/bennymeg/Fabrication-Toolkit) — CLI `python3 -m plugins.cli -p board.kicad_pcb` for JLC-shaped BOM/CPL/IPC; compare our zip layout.
- [Bouni/kicad-jlcpcb-tools](https://github.com/Bouni/kicad-jlcpcb-tools) — gold standard for JLC BOM/CPL from KiCad (plugin, not headless-first).

### 3. Failure casefiles (gate **5.5**)

| Item | Status |
|------|--------|
| `COMPILE_CASEFILE.json` on ERC / KiCad DRC fail | **Improved** (full quality on DRC) |
| `tests/test_compile_casefile.py` | **Added** |
| Intake failures attach `intake` blob | **OPEN** |

---

## P1 — KiCad / PCB engine

### KiCad MCP servers (agent control of live KiCad)

Use as **optional sidecar** when user has KiCad GUI open — not as compile truth (we keep KiCad CLI DRC/ERC in CI).

| Project | Fit | Notes |
|---------|-----|-------|
| [oaslananka/kicad-mcp](https://github.com/oaslananka/kicad-mcp) (kicad-mcp-pro) | **High** | Streamable HTTP + stdio; DFM/manufacturing export tools; profiles (`pcb_only`, `manufacturing`) |
| [belaszalontai/kipilot-mcp](https://github.com/belaszalontai/kipilot-mcp) | Medium | KiCad 10 IPC via `kicad-python`; live PCB session; good for “human has board open” |
| [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) | Medium | 100+ tools, FreeRouting + JLC catalog; heavy; evaluate license/ops |
| Seeed Studio kicad-mcp-server | Medium | Analysis/netlist trace focus |

**Integration sketch:**

```json
// .cursor/mcp.json or project MCP config (example)
{
  "mcpServers": {
    "kicad-pro": {
      "command": "uvx",
      "args": ["kicad-mcp-pro"],
      "env": { "KICAD_MCP_PROFILE": "manufacturing" }
    }
  }
}
```

Expose our engine separately via existing `make run-mcp` (`hardware_splicer.mcp_server`) — **two MCP layers**: compile truth (us) + live edit (KiCad MCP).

### Autorouting — FreeRouting

| Resource | Fit |
|----------|-----|
| [freerouting/freerouting](https://github.com/freerouting/freerouting) | Already bridged (`freerouting_bridge.py`); default off |
| [freerouting API](https://api.freerouting.app/v1) | Cloud routing jobs — optional when Java local is painful |
| KiCad FreeRouting plugin | User-facing; not CI default |

**Path:** `verify-autoroute` target on 2–3 fixtures with `HARDWARE_SPLICER_AUTOROUTE=1` before promoting default.

### Schematic / CAD interchange

| Library | Use |
|---------|-----|
| KiCad `kicad-cli` sch export/import | Already used |
| [tscircuit](https://tscircuit.com/) | `circuit_json_import.py` exists — expand for web-native parts |
| [tscircuit/circuit-json](https://github.com/tscircuit/circuit-json) | Structured interchange for agents |

---

## P1 — BOM / supply chain

| Project | Fit | Integration |
|---------|-----|-------------|
| [i2cjak/jlcpcb_api](https://github.com/i2cjak/jlcpcb_api) | **High** | Official OpenAPI client; extend `jlcsearch_client.py` for stock/pricing |
| [Bouni/kicad-jlcpcb-tools](https://github.com/Bouni/kicad-jlcpcb-tools) | Medium | Part DB patterns; we already have opt-in `HARDWARE_SPLICER_JLC_ENRICH` |
| [valtyr/pcb-jlcpcb](https://github.com/valtyr/pcb-jlcpcb) | Low (Rust) | BOM check CLI — subprocess for `bom check` in salvage |
| Octopart / Nexar API | Medium | MPN resolution when JLC has no SKU |

---

## P1 — Agents / skills / MCP in *our* repo

| Asset | Purpose |
|-------|---------|
| `src/hardware_splicer/mcp_server.py` | Already exposes compile/salvage — document tools in `docs/INTEGRATION.md` |
| Cursor skills (`docs/LLM_OPS.md` patterns) | Quota-aware Qwen/agy routing — add **hardware-splicer-verify** skill: run `make verify-engine && make verify-netlist-engine` |
| `scripts/verify_jarvis_llm.py` | Jarvis phrase eval — tie to compose phrase corpus |
| [Context7](https://context7.com) MCP | KiCad 9 / FastAPI docs in agent sessions |

**Suggested new MCP tools (us):**

- `compile_catalog(build_id)` → inline graph + DESIGN_QUALITY
- `compose_phrase(text)` → module pick + netlist compile
- `inspect_fab(build_dir)` → wrap `fabrication_inspection`
- `read_casefile(path)` → debug failed compiles

---

## P2 — Vision / salvage intake

| Area | Options |
|------|---------|
| Board photo → parts | Keep Qwen vision + `vision_inventory.py`; compare with KiCad MCP OCR tools |
| Datasheet RAG | [llama-index](https://github.com/run-llama/llama_index) or local PDF + embeddings for MPN pinout assist |
| Mechanical | CadQuery (already in 3d-splicer); [build123d](https://github.com/gumyr/build123d) as modern alternative |

---

## P2 — SPICE / simulation (trust loop)

| Project | Fit |
|---------|-----|
| [ngspice](https://ngspice.sourceforge.io/) | `spice_runner.py` exists — gate sim on pump/MOSFET fixtures |
| [PySpice](https://github.com/PySpice-org/PySpice) | Python wrapper for scripted ERC-adjacent checks |

---

## Comparison to “just use Flux”

| Flux gives you | We integrate instead |
|----------------|----------------------|
| Copilot in editor | Our MCP + Jarvis + phrase compose |
| Their router | FreeRouting + cosmetic preview default |
| Their part cloud | JLC API + curated `engine_pcb_data.json` |
| Their DRC | KiCad CLI (same ground truth) |

**Moat we keep:** salvage inventory, evidence gates, headless CI, mechatronics bundles — none of the above repos replace that; they **accelerate** PCB/fab depth.

---

## Recommended sequence (next 4–6 weeks)

1. **Finish 1.5** — canvas `auto_wire` via Python proxy; TS compile demo-only.
2. **JLC OpenAPI** — stock/price on `SALVAGE_BOM.json` when keys present.
3. **KiCad MCP sidecar** — document dev setup; optional `kicad-mcp-pro` for manual review sessions.
4. **Autoroute CI slice** — 3 fixtures with `AUTOROUTE=1`.
5. **MCP tool surface** — expose `compose_phrase` + `inspect_fab` on our server.
6. **Library import** — ingest footprints from KiCad official libs + [kicad-footprints](https://github.com/KiCad/kicad-footprints) for gate 4.5 (250+ modules).

---

## References

- Internal gates: [ENGINE_DONE.md](./ENGINE_DONE.md)
- Flux bar: [FLUX_TARGET.md](./FLUX_TARGET.md)
- LLM ops: [LLM_OPS.md](./LLM_OPS.md)
- Launch verify: [LAUNCH_PLAN.md](./LAUNCH_PLAN.md)
