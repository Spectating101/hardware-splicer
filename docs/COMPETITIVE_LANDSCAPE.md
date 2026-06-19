# Competitive landscape — Hardware Splicer vs ECAD / AI PCB tools

Honest positioning for **salvage → splice → carrier compile → bench-validated bring-up**. We are not trying to win the browser ECAD editor race first.

## One-line thesis

| Tool | Primary job |
|------|-------------|
| **Hardware Splicer** | Reuse **physical donor hardware** with explicit splice contracts, headless KiCad compile, and **bench evidence gates** before power-on |
| **Flux.ai** | Greenfield / iteration in a **browser ECAD** with AI copilot, parts, and collaboration |
| **Quilter** | **Autoroute + layout** from constraints; physics-aware placement |
| **DeepPCB / similar** | AI-assisted **routing** inside existing KiCad/Altium flows |
| **Repair / salvage shops** | Manual dissection, ad-hoc adapters, tribal knowledge |

## Capability matrix (today)

| Capability | Hardware Splicer | Flux | Quilter | Manual salvage |
|------------|------------------|------|---------|----------------|
| Donor board dissection plan | **Yes** (fixture + vision path) | No | No | Yes (informal) |
| Reuse donor connectors / harness | **Yes** (splice blocks) | No | No | Yes |
| Carrier PCB compile (KiCad) | **Yes** (headless) | Yes (native) | Partial / export | Ad-hoc perfboard |
| DRC on **new** carrier | **Yes** | Yes | Yes | Rare |
| Bench evidence before power-on | **Yes** (gates + capture) | No | No | Sometimes |
| Vision → salvage candidates | **Yes** (offline + live Qwen) | No | No | Eyeball |
| Agent-first (SDK / MCP / API) | **Yes** | API limited | Varies | No |
| Browser ECAD UX | No (by design) | **Yes** | Varies | No |
| Parts marketplace / BOM cloud | Catalog hooks | **Strong** | Varies | Digikey + memory |
| Mech + thermal co-design | Roadmap (S4) | Growing | **Strong** | Ad-hoc |
| Collaboration / review | Git artifacts | **Strong** | Varies | Slack + photos |

## Where we are stronger

1. **Salvage-native workflow** — donor fixtures, board evidence, `functional_salvage`, splice readiness verdicts.
2. **Honest validity model** — vision proposes; **bench_topology_capture** closes gates; KiCad DRC does not imply safe power-on with donor wiring.
3. **Headless compile + CI** — `verify-splice`, `verify-splice-loop`, golden intakes, manifest-driven demos without a GUI.
4. **Agent handoff** — documented MCP/SDK path (`docs/AGENT_HANDOFF.md`), not “open our app and click.”

## Where competitors are stronger

1. **Editor UX** — Flux wins interactive schematic/layout, placement, review in browser.
2. **Autoroute quality at scale** — Quilter / DeepPCB class tools on dense digital boards.
3. **Parts intelligence** — Flux supply chain, alternates, pricing in flow.
4. **Onboarding friction** — Flux: sign up and draw; Us: need donor story, intake JSON, KiCad toolchain.

## Strategic implication

- **Do not** position as “Flux but local.” Position as **“splice bench for dead boards and partial assemblies.”**
- **Do** integrate with Flux/notebook/web as **downstream viewers** for carrier artifacts, not as the source of truth for donor validity.
- **First wedge users:** makerspaces, repair cafes, robotics teams with bins of dead toys/printers, EE students doing salvage projects.

## Gaps to close (priority)

| Priority | Gap | Notes |
|----------|-----|-------|
| P0 | Real junk photos in CI | `donor_board_vision.live: true` + pinned golden outputs |
| P0 | Instrument auto-fill | Serial DMM/PSU → `BENCH_CAPTURE_TEMPLATE` |
| P1 | Dum-E / multi-view fuse | `multi_view_capture` → richer `board_evidence` on MCP |
| P1 | Thin capture UI | Web form for template, not raw JSON |
| P2 | Mech envelope (S4) | Carrier outline vs donor keep-out |
| P2 | Unified Circuit-AI package | One install boundary vs `apps/circuit-ai` import |

## Related docs

- [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) — maturity tiers S1–S4
- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — canonical agent flow
- [`REAL_WORLD_PARALLELS.md`](REAL_WORLD_PARALLELS.md) — community repair, RC retrofit, pro lab workflows
