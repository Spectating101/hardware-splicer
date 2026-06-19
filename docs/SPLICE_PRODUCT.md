# Splice product — canonical reference

**Status:** living document for product, engineering, and roadmap decisions.
**Audience:** you (founder), future collaborators, and agents continuing this work.

---

## One sentence

**Hardware-Splicer splices real hardware** — dissect donor boards, extract functional blocks, plan safe interconnect contracts, compile a **carrier board** that mates with what you kept — with KiCad/DRC as judge.

This is **not** “another ECAD tool.” It is **hardware refactoring** with proof.

---

## Splice vs salvage vs compose

| Concept | Meaning | Product role |
|---------|---------|--------------|
| **Salvage** | “Here is what I own” (parts bin, listing, photo) | Input inventory |
| **Splice** | “Here is what **function** I can extract and **how** I reconnect it” | **Core operation** |
| **Compose** | Wire known modules into a catalog recipe | Carrier-board compiler |
| **Honest fab** | KiCad DRC + inspection gates | Trust layer on output |

**Salvage** answers *what do I have?*
**Splice** answers *what can I keep, cut, or harness — and what must I measure first?*
**Compose** answers *what new PCB glues the kept pieces to new logic?*

---

## Three splice layers (whole product)

```
┌─────────────────────────────────────────────────────────────┐
│  CIRCUIT SPLICE (Circuit-AI)                                │
│  vision / netlist → functional blocks → splice plan          │
│  extractability: whole_board | connector | cut_candidate    │
└───────────────────────────┬─────────────────────────────────┘
                            │ graph_input
┌───────────────────────────▼─────────────────────────────────┐
│  CARRIER COMPILE (hardware_splicer)                         │
│  splice-build → KiCad PCB + DRC + BOM + bring-up card       │
└───────────────────────────┬─────────────────────────────────┘
                            │ dimensions / mounts
┌───────────────────────────▼─────────────────────────────────┐
│  MECH SPLICE (mecha-splicer + 3d-splicer)                   │
│  enclosure, brackets, fixture around physical splice          │
└─────────────────────────────────────────────────────────────┘
```

**Market wedge:** circuit splice + carrier compile. Mech splice is differentiation, not day-one blocker.

---

## Maturity tiers (what “good” means)

Use these tiers to avoid pretending the product is more complete than it is.

| Tier | Name | User can… | Repo status (Jun 2026) |
|------|------|-----------|-------------------------|
| **S0** | Inventory reuse | List parts → get build suggestion | ✅ salvage planner + module resolver |
| **S1** | Splice plan | See blocks, extractability, measurements, wiring steps | ✅ `SalvageSplicePlanner` + eval 29/29 |
| **S2** | Carrier compile | `splice-build` → DRC-clean KiCad for catalog target | ✅ manifest cases, `verify-splice` |
| **S3** | Bench truth | Close evidence gates with real measurements | ✅ golden CI (`verify-splice-loop`, `verify-splice-real-bench`); field café = future |
| **S4** | Full product | Mech envelope + field validation + scoped release | 🟡 mecha/authority path exists; not splice-first UX |
| **S5** | Greenfield + splice | Arbitrary schematic editor **and** donor splice in one session | ❌ Flux-class; future on same spine |

**Current honest bar:** **S2** proven in CI (`verify-splice`). **S3** golden paths prove gate closure (`verify-splice-loop` simulated; `verify-splice-real-bench` hand-filled capture). Competition docs: [`COMPETITION_PROPOSAL.md`](COMPETITION_PROPOSAL.md).

---

## What is real in code (anchor files)

| Capability | Location |
|------------|----------|
| Functional blocks + extractability | `apps/circuit-ai/src/intelligence/functional_salvage.py` |
| Splice planning | `apps/circuit-ai/src/intelligence/salvage_splice_planner.py` |
| Intake → splice package | `src/hardware_splicer/salvage_bridge.py` |
| Donor context from intake | `load_project_intake()` + `donor_context` in salvage bridge |
| splice-build pipeline | `src/hardware_splicer/project_intake.py` → `splice_and_build_from_intake` |
| API / jobs | `POST /v1/splice-and-build`, `POST /v1/jobs/splice-build` |
| Demo manifest + verify | `examples/splice/manifest.json`, `scripts/verify_splice_demos.py` |
| Planner eval (29 cases) | `apps/circuit-ai/eval/salvage_splice_coverage/` |
| Circuit-AI reuse API | `POST /salvage/splice-plan`, `/salvage/splice-case` |

---

## Canonical demos (closed loop)

Defined in [`examples/splice/manifest.json`](../examples/splice/manifest.json):

| case_id | Story | Target build |
|---------|-------|--------------|
| `robot_drive_from_rc_toy` | RC toy H-bridge + motors → ESP32 carrier | `robot_drive_base` |
| `robot_drive_vision_junk` | Vision board_evidence + simulated bench closure | `robot_drive_base` |
| `robot_repair_cafe_s3` | repair_intake + PSU ramp + bench closure | `robot_drive_base` |
| `printer_motion_stage` | Inkjet stepper section + limits → motion carrier | `plotter_motion_stage` |

**Golden real (not in manifest — separate verify):** `examples/intakes/splice_robot_drive_golden_real_brief.json` + `make verify-splice-real-bench`.

```bash
make splice-demo                              # robot case (default)
make verify-splice                            # S2 manifest cases (CI bar)
make verify-splice-loop                       # S3 golden loop (3 cases)
make verify-splice-real-bench                 # S3 real photo + manual capture
python3 scripts/splice_demo.py --case printer_motion_stage --out /tmp/hs_splice_printer
```

Each case requires:

- ≥2 **circuit-backed** reusable blocks from donor fixture
- `connector_reuse` **and** `board_section_cut_candidate` extractability present
- **KiCad DRC pass** on carrier board (not donor board)

---

## Extractability taxonomy (product language)

| Class | Operator meaning | Product rule |
|-------|------------------|--------------|
| `whole_board_reuse` | Keep module intact (ESP32 devkit, USB-serial board) | Do not assume die-level extraction |
| `connector_reuse` | Keep harness; map pins before cutting | **Default safe path** |
| `board_section_cut_candidate` | Possible copper island cut | **Gated** — layout + thermal + isolation review |
| `not_recommended` | Do not pursue | Block or safety hold |

**Do not market “auto cut lines on Gerber” yet.** Today the product sells **contracts and gates**, not CNC-ready cut geometry.

---

## Personas (who pays attention)

1. **Salvage maker** — burned by bad boards; has junk drawer / e-waste
2. **Test/fixture builder** — donor board as probe block or breakout
3. **Agent/automation author** — headless splice + compile in CI
4. **Small NPI / edu lab** — audit trail + reproducible compile

**Not primary (yet):** professional EE doing arbitrary multi-sheet analog (→ S5 / Flux-class).

---

## vs Flux (and when you go there)

| | Flux / ECAD | Hardware-Splicer splice |
|--|-------------|-------------------------|
| Starting point | Blank schematic, parts cloud | **Donor hardware** |
| Core operation | Draw + route | **Dissect + recombine** |
| Trust model | Canvas + DRC | **KiCad truth + evidence gates** |
| Moat | Library, editor, routing | Salvage graph, splice contracts, headless spine |

**Sequence (do not skip):**

1. **Own S2 splice** — manifest green, one killer demo narrative, bench checklist
2. **S3 bench UX** — agent/MCP/API sessions ship (`docs/AGENT_HANDOFF.md`); rich operator UI still optional
3. **Expand catalog + library** — more carrier targets from donor classes
4. **S5 editor** — greenfield on **same** `compose_dispatch` spine, not a fork

Flux-class is **expansion**, not repositioning. You become *the splice company that grew up*, not a late Flux clone.

---

## Metrics to track (product, not vanity)

| Metric | Why |
|--------|-----|
| `circuit_backed_block_count` per intake | Donor dissection working? |
| % cases with `connector_reuse` path | Safe default adoption |
| `splice_readiness` distribution | `ready_for_first_splice` vs `blocked_until_evidence` |
| Manifest `verify-splice` pass rate | Regression bar |
| Time to `drc_pass` on carrier | Compile path health |
| % runs with closed evidence gates | S3 progress |
| Donor class → `build_id` accuracy | Planner + resolver quality |

---

## Known gaps (honest backlog)

### P0 — splice product (next 4–8 weeks)

- [ ] **Bench gate UX** — session UI to close `evidence_gates` from bring-up card
- [ ] **Splice-first landing** — lead with dissect→carrier, not “18 kits”
- [ ] **Vision → functional_salvage** — board photo / `board_evidence.v1` on intake (`hs_donor_board_vision`, `splice_robot_drive_vision_brief.json`); live Qwen when keyed
- [ ] **Pin-level splice contracts** on carrier graph (visual “donor harness J_MOTOR_L → carrier J1”)

### P1 — depth

- [ ] Cut-line **layout hints** (keepout, score line suggestion) for `board_section_cut_candidate`
- [ ] Third manifest case: `usb_fan` plan-only or compile to `usb_fume_extractor`
- [ ] MCP tools: `hs_splice_plan`, `hs_splice_build` with manifest parity

### P2 — Flux-class (months, explicit bet)

- [ ] Arbitrary netlist editor client
- [ ] Library scale + autoroute CI default
- [ ] Greenfield + splice in one project session

---

## How to proceed (decision tree)

```
Start here
    │
    ├─ Is verify-splice green?
    │     no → fix manifest cases / donor fixtures / resolver (engine)
    │     yes ↓
    │
    ├─ Do you need investors / users to *feel* splice in 10 min?
    │     yes → DEMO_SPLICE + robot case + SPLICE_DEMO_STORY.md
    │     no ↓
    │
    ├─ Is the bottleneck compile or trust?
    │     compile → catalog recipes, module library, DRC loop
    │     trust   → S3 bench sessions (agent-first), evidence gate closure, vision intake
    │
    └─ Ready to chase Flux-sized TAM?
          only after S2+S3 solid → editor sprint on same API (see FLUX_TARGET.md)
```

**Default recommendation:** stay on **S2 → S3** until a real user fails on **measurement gates** or **vision intake**, not until the editor feels tempting.

---

## Commands cheat sheet

```bash
make splice-demo                    # default robot case
make verify-splice                  # all manifest cases
make salvage-demo                   # inventory-only bring-up (no donor fixture)

python3 scripts/hardware_splicer.py splice-build \
  --brief examples/intakes/splice_robot_drive_brief.json \
  --out /tmp/hs_splice

python3 scripts/verify_splice_demos.py --json --out /tmp/hs_splice_verify
```

Docs: [`DEMO_SPLICE.md`](DEMO_SPLICE.md) (walkthrough) · [`FLUX_TARGET.md`](FLUX_TARGET.md) (long-term engine bar) · [`ENGINE_DONE.md`](ENGINE_DONE.md) (CI gates)

---

## Agent handoff note

When continuing this work:

1. Read `examples/splice/manifest.json` first — it is the product contract.
2. Do not weaken manifest checks to greenwash; fix intake/fixtures/resolver.
3. Prefer donor-context + functional_salvage over clever prose in intakes.
4. `result_ok` may be false while `drc_pass` is true (gate warnings); manifest uses **drc_pass + artifacts**, not `ok` alone.
5. Splice is the thesis; honest fab supports it; Flux-class editor is phase 4+.
