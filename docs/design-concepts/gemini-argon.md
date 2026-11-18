# Hardware Splicer: The Living Proof Stage

The rejected three-pane proposal failed not because engineers dislike `navigator + canvas + inspector`, but because collapsing the center into flat `Design | BOM | Changes` tabs freezes a multi-domain, multi-agent workflow. Swapping a 7-inch display for a 5-inch one hits CadQuery shells, power margin, cable routing, and open unknowns at once while Claude Code or Codex runs checks beside you.

Hardware Splicer should be a **composable multi-lens instrument over one live revision graph**—preserving engineering muscle memory while making cross-domain impact, agent activity, and revision time visible together.

---

## 1. Core Interaction Model & Daily View

Beneath a slim 40 px header, four synchronized regions share one `(project, revision, selection)` cursor:

- **Left — Canonical BOM & System Spine (collapsible, ~240 px):** Persistent tree (`Assembly → BOM Line → Stock Unit / Ports / Nets`). Each row displays origin (`OWN`, `SLV`, `CAT`, `CAD`), verbatim epistemic state (`? UNK`, `~ ASM`, `= DOC`, `* MSR`), blockers, alternates, and agent badge (`@codex`). Filter chips (`All`, `Blockers`, `Unknowns`, `Delta`, `Agent`) pivot the spine into triage in place.
- **Center — Composable Multi-Lens Stage (1–4 panes):** What the user watches 80% of the time. Neither an infinite whiteboard nor flat tabs, the Stage tiles up to four synchronized lenses. Presets (`1:Design`, `2:Sim+PCB`, `3:Swap`, `4:Repair`) reconfigure the split in one keypress; any lens splits or maximizes.
- **Right — Proof Inspector (collapsible, ~300 px):** Blockers pinned first for the active project, part, finding, or proposal, with verbatim authority and SHA-256 receipts below.
- **Bottom — Live Revision & Agent Timeline (44 px, expandable):** Git-style rail of immutable revisions (`r1 → r2 → r3`), parallel dashed Change Order tracks, and live engine runs (PyBullet, CadQuery, KiCad, sandboxed tools).

**Compare is an in-place mode (`C`), never a separate screen.** Structured lenses default to **differences-only** (`Show unchanged` optional); visual lenses switch to side-by-side, ghost overlay, or split-wipe.

---

## 2. How All Capabilities Live in One System

Four top-level spaces replace fragmented routes:

1. **Projects (Home + `Cmd+K`):** Saved projects with verbatim blocker/unknown counts and live agent pulses. **New Project** opens one intake sheet with three equal starts—*Goal*, *Owned/Salvaged Parts*, or *Reference Study* (HS-3G-B drone, FieldDeck, Ender-3 plotter, PCB inspection nest)—all opening the same Workbench.
2. **Workbench (Active Stage):** Every capability runs as a lens or check on one revision:
   - *Digital studies* drive CAD, PyBullet/G-code replay, and a one-click **Offline Package** drawer verifying `RERUN.py` and `SHA256SUMS`.
   - *KiCad ERC/DRC, footprints, wiring contracts (`WireViz`), and fabrication gating* feed Board/Wiring lenses and the shared Findings list.
   - *Teardown & salvage* binds sourced part identities (datasheet/guide hashes, pinouts) to owned stock units on the BOM spine.
   - *Repair diagnosis* runs as a **Safety-Gated Diagnostic Lens** locking hazardous tests behind measured gates and enforcing `repair_policy` (geometry fixups never alter identity or nets).
   - *`circuit-ai-frontend`* stays deep-linked in Slice 1, then its Board and Repair views move into Stage lenses.
3. **Inventory (InvenTree-aligned):** Separates specific owned/salvaged **stock units** (unit measurements and unknowns) from **catalogue profiles** (published ratings, mounts, footprints). Assigning a unit links straight to its BOM line.
4. **Lab (Workshop Governance):**
   - *GitHub-Signal Tool Factory:* `Discovered → Adapter Review → Approved → Disabled` queue showing pinned Git SHA, SPDX license check, fail-closed no-network sandbox (`bwrap --unshare-net` or pinned Docker digest), and hashed receipts. Approved tools (`akcli`, `kdif`) appear natively inside project checks and diffs.
   - *Sealed Holdout Evals:* Read-only audit ledger (`unseen_devices 14/15 + 1 abstention`, `Sweep v2.2 4/5 + 1 abstention`) with commit SHAs and replay-hash checks.
   - *MCP Fleet:* Connected agents, task scopes (`bounded_pre_fabrication`, `engineering_assurance`), resource guards, and traces into proposals.

Zero-login for the owner today, every decision carries actor attribution and revision-pinned Change Orders—ready for friends behind nginx auth next and released-part ECOs for a hardware business later without faking customers today.

---

## 3. Live Agent Work, Steering & Approval

Agents (Claude Code, Codex, MCP clients) appear natively without hijacking focus or hiding engineering state inside chat:

- **Ambient presence, zero silent writes:** Streaming `project_events` renders read-only Spine badges (`@codex`) and Timeline progress bars. Agents never move the camera or overwrite the active revision.
- **One mutation primitive — the Staged Change Order (ECO):** Every agent proposal, DRC fixup, or change to a released part lands as a typed, base-revision-pinned track (`r3 ╌╌● ECO#12`).
- **Steering on artifacts:** Clicking an ECO opens **Review Diff Mode** (differences-only deltas, 3D/`kdif` wipe, ripple summary, and backend `review_flags` exposing any identity or authority hit). Pin a note directly onto a finding, BOM row, or PCB coordinate and choose **Approve → Save Rev**, **Run Sandbox Preview**, **Bounce with Constraint**, or **Reject**.

---

## 4. Evidence, Authority, Unknowns, Blockers & Substitution Ripples

Epistemic state comes verbatim from the backend—the UI never computes promotions:

- **Four epistemic registers:** `UNKNOWN` gets a loud dashed border and `?` (never blank or guessed); `ASSUMED/INFERRED` gets amber hatch (`~`); `REFERENCE/DATASHEET` gets ruled slate (`=`); `MEASURED/OBSERVED` gets a solid badge (`*`) with producer and SHA-256 hash. Authority labels (`unmodeled`, `interface_bound`, `design_compiled`, `blocked`) print verbatim.
- **Blockers, never "Ready":** The Inspector leads with backend blockers. Zero digital blockers reads `0 DIGITAL BLOCKERS · PHYSICAL UNPROVEN`.
- **Pinned findings with click-to-jump:** KiCad ERC/DRC, `akcli`, CadQuery fit checks, wiring contracts, and safety gates share one pinned list. Clicking any pin jumps linked lenses to the exact pad, solid, or BOM line with its hashed receipt. Unknowns offer inline **Supply Evidence** (datasheet claim, caliper reading, or stock unit) staging a new revision.
- **Alternates & ripples:** Expanding a BOM line shows compatible stock units and catalogue alternates. **Test Swap** opens a non-destructive counterfactual combining a **Cross-Domain Ripple Graph** (`change_impact`: Mechanical, Electrical, Power, Firmware, Verification) and a **Differences-Only Delta Table** (FieldDeck 7" → 5": watts, runtime, supply margin, 4 reprinted STLs, retained DSI cable, new `?` checks). Promoting opens an ECO; closing leaves the baseline untouched.

---

## 5. Embedding & Linking 3D, CAD, Board & Sim Viewers

Viewers plug in as **Stage Lenses** over one synchronization bus (`{entity_id, refdes, net_id, bbox_3d, rev_a, rev_b, sim_t}`):

- **3D / CAD:** Shared Three.js/GLB canvas progressively replacing opaque `VIEWER.html` iframes (keeping iframe fallback for offline study bundles). Detailed CadQuery solids render shaded; `REFERENCE_ENVELOPE` shapes render as translucent wireframes so placeholders never mimic verified CAD.
- **Board / Schematic:** Embedded KiCanvas with copper-trace overlays and `kdif` HTML visual diff in Compare mode.
- **Sim / Motion:** PyBullet flight replay and Ender-3 G-code paths scrub in lockstep with current, battery-sag, and RMS plots.
- **Honest linked selection:** InteractiveHtmlBom-style cross-probing highlights peers *only* where backend links exist; unmapped rows show an explicit `UNLINKED` tag, never guessed or hidden.

---

## 6. Phone Use

Mobile is a **Workshop Companion & Approval Remote**, never shrunk CAD:

1. **ECO & Gate Triage:** Pending agent Change Orders and Tool-Factory adapter reviews showing differences-only metrics, blocker deltas, and one-thumb **Approve / Bounce / Reject**.
2. **Bench Capture:** Snap donor photos, add stock units, or key caliper/meter readings onto a `? UNKNOWN` row as hashed `observed` evidence awaiting review.
3. **Pocket Reference:** Read-only BOM, blocker list, wiring pinouts, and orbit-only 3D preview.

---

## 7. Three Key Screens

### Screen 1: Active Workbench — Multi-Lens Proof Stage (`HS-3G-B Drone`, Sim + PCB Preset)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ HS  [Projects] [*Workbench] [Inventory] [Lab]   HS-3G-B Drone · r3    [Cmd+K] [Export] │
├──────────────────────┬────────────────────────────────────────┬────────────────────────┤
│ SPINE · BOM (14)     │ [1:Design][*2:Sim+PCB][3:Swap][C:Diff] │ PROOF · DESIGN_COMPILED│
│ [All][X4][?2][Δ][@]  ├────────────────────────────────────────┤ [X] 4 BLOCKERS · ? 2   │
│ ▾ Airframe (CAD)     │ LENS A · 3D + PYBULLET SIM    [Split]  ├────────────────────────┤
│  ├─ TopPlate  * CAD  │        +---o (M1)     gust ->          │ BLOCKERS (verbatim)    │
│  └─ BotPlate  * CAD  │       /  [===FC===]  ~~~~>             │ [X] Batt C-rate assumed│
│ ▾ Propulsion         │  (M4)o---+       +---o(M2)   . - .     │ [X] RX pinout unknown  │
│  ├─ F1404x4   = alt2 │           \     /          .' path'.   │ [X] DRC-02 pad clear.  │
│  └─ Batt 4S   ~ X1   │            o---' (M3)     o         *  │ [X] Physical unproven  │
│ ▾ Avionics           │  Shaded: CAD · Dash: REF_ENVELOPE      ├────────────────────────┤
│ ▸├─ FC F405   = @cdx │  > 04.2s ━━━●────── 12.0s  RMS 11.4mm  │ PINNED FINDINGS (jump) │
│  └─ RX ELRS   ? X1 u │  Ipk 24.8A · 14.1V · Mass 238/250g     │ ▸[DRC-02] U1-J3 0.12mm │
│ ▾ Wiring (6 nets)    ├────────────────────────────────────────┤  [AK-07]  sch lbl ovlp │
│  ├─ UART2-RX  * ok   │ LENS B · KICANVAS PCB (F.Cu) [ERC][DRC]│  [FIT-01] arm clr 2.1mm│
│  └─ 5V-BEC    = ok   │  +----------------------------------+  ├────────────────────────┤
│                      │  | [J3]---[U1:F405*]=====[M1..M4]   |  │ SELECTED: FC F405      │
│ Legend:              │  |   ![DRC-02]  ![AK-07]   [RX: ?]  |  │ Auth: interface_bound  │
│ *MSR =DOC ~ASM ?UNK  │  +----------------------------------+  │ Src : kicad-cli 9.0.2  │
│ u=unlinked @=agent   │  Linked: FC F405↔U1 · RX: UNLINKED     │ Hash: sha256:480a…7679 │
│                      │                                        │ [Supply Evid] [Receipt]│
├──────────────────────┴────────────────────────────────────────┴────────────────────────┤
│ TIMELINE  r1 ── r2 ──● r3(head)  ┆ + ECO#9 [@codex: DRC pad fixup · 2 files]  [Review] │
│ LIVE MCP  ● pybullet: ok (42s)   ┆ ○ @claude-code: auditing RX wiring (read-only)      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Screen 2: Counterfactual Substitution & Agent ECO Review (`FieldDeck 7" → 5"` Swap)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ HS  [Projects] [*Workbench] [Inventory] [Lab]   FieldDeck · r3 → ECO#12    [Exit Diff] │
├──────────────────────┬──────────────────────────────────────────┬──────────────────────┤
│ SPINE · Δ CHANGED (4)│ [1:Design][2:Sim][*3:Swap][*C:Δ Only]    │ ECO #12 · claude-code│
│ [All][X5][?2][*Δ4]   ├──────────────────────────────────────────┤ Base: r3 (pinned)    │
│ ▾ Display Subsystem  │ LENS A · 3D WIPE   r3(7") ◂║▸ ECO#12(5") │ Auth: NO UPGRADE     │
│ ▸├─ DISP-01  Δ SWAP  │   +------------+║+--------+  [REPRINTx4] ├──────────────────────┤
│  │  Base: 7" Touch   │   |  7" LCD    |║| 5" LCD |  bezel, tray │ REVIEW FLAGS         │
│  │  Alt1: 5" Touch < │   |  193x110mm |║|145x88mm|  +rear shell │ [!] identity_changed │
│  │  Alt2: Salv.HDMI ?│   +------------+║+--------+  0 overlaps  │ [X] FPC bend rad. ?  │
│  ├─ Bezel    Δ CAD   │   [Wipe ◂║▸] [Ghost] [Sync Cam] [STEP]   │ [X] touch I2C addr ? │
│  └─ DSI-FPC  = kept  ├──────────────────────────────────────────┼──────────────────────┤
│ ▾ Power              │ LENS B · RIPPLE GRAPH + DELTA (Ordinary) │ EVIDENCE RECEIPTS    │
│  └─ 5V Rail  Δ +0.4A │  DISP-01 ─┬─▸ MECH: 4 new STLs (fit ok)  │ * CadQuery: 4 solids │
│                      │           ├─▸ PWR : 4.4h → 5.5h (+25%)   │ * Power: sha256:7b41 │
│ +11 unchanged hidden │           ├─▸ WIRE: DSI kept · 1 ? open  ├──────────────────────┤
│ [Show unchanged]     │           └─▸ VERIF: +1 blocker (? FPC)  │ STEER / DECIDE       │
│                      │  Metric      │ r3 (7")  │ ECO#12 (5")    │ [Approve → Save r4 ] │
│ Stock: 0 owned units │  Display W   │ 2.40 W   │ 1.35 W (-44%)  │ [Run Sandbox Prev  ] │
│ (digital-only trial) │  Supply mgn  │ 0.82 A   │ 1.24 A (+51%)  │ [Bounce w/ Pin Note] │
│                      │  Open checks │ 1        │ 2      (+1 ?)  │ [Reject Proposal   ] │
├──────────────────────┴──────────────────────────────────────────┴──────────────────────┤
│ ECO LINEAGE  r3 ──╌╌● ECO#12(5in-swap, pending) ┆ Offline pkg: RERUN.py + SHA256SUMS   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Screen 3: Lab Governance Console (Left) & Phone Workshop Companion (Right)

```text
┌────────────────────────────────────────────────────┐  ┌────────────────────────────────┐
│ HS  [Projects] [Workbench] [Inventory] [*Lab]      │  │ PHONE · WORKSHOP COMPANION     │
├────────────────────────────────────────────────────┤  ├────────────────────────────────┤
│ GITHUB-SIGNAL TOOL FACTORY (no-net sandboxed)      │  │ [*Triage(2)] [Capture] [Parts] │
├────────────────────────────────────────────────────┤  ├────────────────────────────────┤
│ Tool   SHA     Lic  Sandbox         State          │  │ ECO #12 · FieldDeck · @claude  │
│ akcli  2126c32 MIT  bwrap:--no-net  ● APPROVED(27) │  │ Swap DISP-01 → 5" Touch        │
│ kdif   9f41a08 MIT  kicad@sha256    ● APPROVED     │  │ Δ Power   : 2.40W → 1.35W      │
│ bomx   e81c201 GPL3 unreviewed      ○ VETTING [->] │  │ Δ Blockers: 4 → 5 (+1 ? FPC)   │
│ Last run: sha256:0883…e192 · 0 host/net mounts     │  │ Authority : unchanged          │
├────────────────────────────────────────────────────┤  │ [Approve r4] [Note] [Reject]   │
│ MCP GATEWAY & LIVE AGENT FLEET                     │  ├────────────────────────────────┤
│ @claude-code  bounded_pre_fab   FieldDeck  ECO#12  │  │ BENCH CAPTURE -> ? UNKNOWN     │
│ @codex        eng_assurance     HS-3G-B    ECO#9   │  │ Project: Ender-3 Plotter · r2  │
│ Guard: 0 auth upgrades · 2/4 slots active  [Pause] │  │ Target : M1 NEMA17 (? flange)  │
├────────────────────────────────────────────────────┤  │ [CAM Donor]  [DIM Caliper]     │
│ SEALED HOLDOUT EVALS (blind · replay-verified)     │  │ Entry: [ 42.3 mm ] + photo     │
│ unseen_devices  14/15 · 1 abst  3cc0adda  * match  │  │ -> Staged OBSERVED (unrev.)    │
│ sweep_v2.2       4/5  · 1 abst  6b56c2f4  * match  │  │ [Stage Evidence]  [Cancel]     │
└────────────────────────────────────────────────────┘  └────────────────────────────────┘
```

---

## 8. Risks & What to Build First

**Key Risks:**
- **Pane clutter:** Unbounded tiling causes cockpit fatigue. *Mitigation:* cap at 4 lenses, default to 1–2 via presets, persist per project.
- **Visual over-claiming:** Polished meshes disguise assumptions. *Mitigation:* wireframe-ghost `REFERENCE_ENVELOPE` parts, keep `? UNKNOWN` loud, never compute authority client-side.
- **Agent race conditions:** Concurrent MCP edits against stale revisions cause drift. *Mitigation:* debounce `project_events`, isolate writes in base-pinned ECOs, flag conflicts if HEAD advances.
- **Dual-frontend drift:** Running `splice-ui` beside `circuit-ai-frontend` splits state. *Mitigation:* standardize on `hs-serve` product APIs and absorb Board and Repair lenses incrementally.

**What to Build First (Single-Port `hs-serve` Slices):**
1. **Slice 1 — Stage Spine (4 Studies):** 3-path Intake + BOM Spine (stock units vs. catalogue, verbatim epistemic/blocker tags, `UNLINKED` badges) + 2-pane Stage (GLB/Study + BOM/Alternates) + Blockers-first Inspector + Differences-Only Compare (`HS-3G-B`, `FieldDeck 7"/5"`, `Ender-3 Plotter`, `PCB Nest`).
2. **Slice 2 — Live Agents & Ripples:** Bottom Revision/Agent Rail (`project_events`) + ECO Review (`machine_project_diff`, `ai_project_conversation`) + Substitution Ripple lens (`part_substitution`, `change_impact`) + Phone Triage/Capture.
3. **Slice 3 — Lab & Team Convergence:** KiCanvas + `kdif` diff + Safety-Gated Repair lens + Lab Console (Tool Factory, MCP fleet, sealed holdouts) + nginx sign-in for friends and released-part ECOs.
