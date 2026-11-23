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

## Re-check, 2026-10-09

What the sources below say, read on that date. Where I could not check a claim, it says so. This is a snapshot of public pages, not hands-on testing of the competing products.

| Tool | What it does that matters here | Source |
|------|-------------------------------|--------|
| **Flux** | Text prompt to schematic, layout and BOM, and (announced 2026-09-24) 3D-printable enclosures that match the board's geometry, with latches, screw holes, vents and port cut-outs, in one browser tab | [Flux press release](https://www.globenewswire.com/news-release/2026/09/24/3368248/0/en/flux-launches-new-ai-capabilities-to-take-hardware-designs-from-pcb-to-prototype.html), [Flux Copilot](https://www.flux.ai/p/blog/flux-copilot-the-first-ai-powered-hardware-design-assistant) |
| **Wokwi** | Runs the firmware on a simulated ESP32 / STM32 / Arduino with parts wired in a `diagram.json` (an ESP32 and an SSD1306 are a standard example) | [Wokwi diagram format](https://docs.wokwi.com/diagram-format), [Espressif's guide to it](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/third-party-tools/wokwi.html) |
| **Fritzing, Tinkercad Circuits, Cirkit Designer** | Breadboard-style wiring views; Fritzing goes on to PCB and fabrication, Tinkercad simulates | [Breadboard tools, 2026](https://www.breadboardhub.com/articles/breadboard-circuit-design-free-tools-for-makers-in-2026) |
| **Boardsort OSCAR** and e-scrap vision research | Photo of a circuit board to a scrap grade and price, for recyclers; research systems detect components on waste boards | [Recycling Today](https://www.recyclingtoday.com/news/boardsort-launches-ai-electronic-scrap-pricing-grading-tool-oscar/) |

I found no tool that takes a donor board and tells a maker which block of it can be reused in a new device and which measurements must close first. That is a statement about what I found, not a proof that none exists.

### Where Hardware Splicer is now

| Strength | Why it counts |
|----------|---------------|
| Every figure names its source or says it is typical, and the plan tells you to measure | Neither a simulator nor a generator tells you which of its numbers are real |
| Wiring is checked against pin roles and as nets, each finding with its basis | The checks caught reset-pin and 5 V mistakes that a visual wiring tool would draw without comment |
| Whole-device assembly as an animation of the real parts, wires pin to pin | Breadboard tools show the wiring; none of those above shows the case, the display and the lid going together |
| Take-apart plan for a board, with a verdict and a reason per part | The e-scrap tools price a board by weight and grade; this says which parts are worth a maker's time |
| Authority is never implied: reports report, checks are suggestions | A plan that says "nothing here approves building" is rarer than it should be |

### Where it is behind

| Gap | Honest size |
|-----|-------------|
| Generating a design from a sentence | Flux does this; we do not |
| Running the firmware | Wokwi does this; we do not |
| A printable case | Flux has one; ours is a proposal in the viewer, not printed and with no export |
| Module coverage | Two modules in the device library (an ESP32 dev board, an OLED); a breadboard tool has thousands of parts |
| Identifying a physical board with no file | The take-apart plan needs the board's file. The repo's donor path has a vision step, but there is no capture path that puts a photographed board into the 3D view |
| Scale and polish | One maintainer against funded teams |

### What this says about direction

The 3D layer makes the evidence-first idea visible, and it is worth having for that. It does not make Hardware Splicer a better generator or simulator than the tools above, and trying to would be the wrong race. The strongest position is the one nobody else is building: take a real piece of hardware, including a donor board from e-waste, say exactly what is known and what must be measured, and show the way through it. The next step on that path is a capture route for boards that have no file.

### Reused rather than built (2026-10-10)

KiCad's installed symbol and footprint libraries give offline marking lookup, pin names and real package sizes; the repo's parts providers
(with jlcsearch, free and keyless) give optional online lookup; iFixit's public search gives teardown links. See `docs/PART_LOOKUP.md`,
which also lists what was looked at and left alone, and why.
