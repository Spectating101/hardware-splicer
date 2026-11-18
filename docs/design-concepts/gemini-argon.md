# Hardware Splicer: The Living Proof Stage (v2)

Our earlier four-region cockpit was too static and dense: locking a narrow BOM sidebar beside stacked panes wasted width and froze multi-agent work. Research across CAD, robotics, EDA, and agent studios points to a sharper instrument: **a calm, composable Proof Stage over one live evidence graph**. It keeps our distinctive pieces—saved lens presets, scannable epistemic registers (`?`/`~`/`=`/`*`), and counterfactual ripple analysis—while cutting permanent chrome, global hairballs, and sliders that make assumptions look measured. **Authority never upgrades implicitly, unknown is first-class, and blockers never read "ready."**

## 1. Entry & De-Densified Stage

**Projects** resumes the last question by unresolved blockers, or starts from *Goal*, *Owned/Salvaged Parts*, or *Reference Study*, and also opens directly on a stuck BOM row. This matches ecoEDA’s multi-start study (suggestions only on request) and the SO-ARM100 sourcing failure where work starts from an unavailable part before CAD exists ([ecoEDA, SO-ARM100; GitHub signals][sig]).

To cut cockpit density, the Stage defaults to **one full-width instrument or two linked lenses**, splitting to three or four only on demand:

- **Full-width BOM (`1:BOM`):** A narrow sidebar cannot hold a BOM ([Verdict; Hardware conventions][hw]). Sourcing opens a full-width table separating requirement, dated MPN offers, InvenTree-style owned stock units, and alternates ([InvenTree, Altium; Hardware conventions][hw]; [InteractiveHtmlBom #602; GitHub signals][sig]).
- **Saved presets:** One-key layouts (`1:BOM`, `2:Sim+PCB`, `3:Swap`, `4:Repair`) recall lenses, layers, and camera with an unsaved dot and `Reset`, adapting Rerun blueprints and Foxglove saved layouts ([P22; Advanced patterns][adv]). Findings offer their matching preset in one click.
- **Collapsible drawers & Peek:** Spine and Proof Drawer collapse during visual work. `Space` peeks any row or finding (Linear; [P10; Advanced patterns][adv]). Opened on demand, Proof rebuilds per selection with live authority and blockers above one flat `Interface/Parameters` fold (RoboSimStudio; [P7; Advanced patterns][adv]). Scoped blocker counts stay pinned in the 40 px header ([Shared #3; Hardware conventions][hw]).

## 2. How Time, Linked Views, Agents & Evidence Move Together

One deep link encodes `(project, rev/draft, selection, run_t, preset)` so teammates or a phone open the exact state (Rerun Share, Foxglove links; [P24; Advanced patterns][adv]). Four live layers move together without hijacking focus:

- **Two honest clocks:** Continuous **Run time** appears *only* on recorded temporal runs (PyBullet motion/flight, current/thermal traces, Ender-3 toolpaths). One Rerun cursor drives 3D pose, LeRobot trail (`Off/Recent/Episode`), RoboSimStudio verdict overlays drawn from the check’s own geometry, and plots together, with printed transport keys (`Space`, `←/→ ±100ms`, `Shift ±10ms`; LeRobot, Foxglove; [P1, P5, P8, P10; Advanced patterns][adv]). Clicking a spike pauses there, cross-highlights static views at the run’s input revision, and lets you **Pin** that sample across branches. Separately, a discrete **Project clock** draws Onshape coloured branches/merges (`r6→r7`, drafts) with expandable per-entity rows showing when measurements, offers, or checks landed (Rerun Streams, Foxglove; [P2, P18; Advanced patterns][adv]).
- **Evidence moves with time:** Stepping back restores historical state via Foxglove lookback with age (`* r5, 9d ago`) instead of blanking or leaking newer data ([P3; Advanced patterns][adv]). Editing an input triggers marimo lazy invalidation—echoing InvenTree’s validation reset—marking downstream checks **`! STALE`** with the reason rather than silently rerunning ([P25; Advanced patterns][adv]; [InvenTree; Hardware conventions][hw]).
- **Honest linked views:** Bidirectional cross-probing ties BOM rows, 3D solids (shaded CadQuery vs. wireframe `REFERENCE_ENVELOPE`), KiCad pads (`↗ U1 on Schematic`; tscircuit, Interactive HTML BOM; [P6; Advanced patterns][adv]; [Hardware conventions][hw]), and harness endpoints. Unmapped rows read `UNLINKED` and open source-native files, respecting tools like Copper ([Copper; GitHub signals][sig]).
- **Scoped live agents, zero hijack:** Claude Code, Codex, and MCP clients bind to a visible **selection scope chip** (Zookeeper, Cursor; [P15; Advanced patterns][adv]) on isolated draft branches (Cursor worktrees, Onshape; [P14, P18; Advanced patterns][adv]). Typed receipts turn active verbs past-tense (`Searching→Searched: 3 offers`; Linear) and jump to the touched artifact and base snapshot (Devin; [P11; Advanced patterns][adv]). Silence flags `activity unknown` with last contact. During scrubbing, history inspection, or diff review, events queue under **`New activity`** until **Go live**. Sessions survive reloads with Resume, queued cancel (`✕`), and read-only side questions (Zoo PR #15255, Claude Code web, Devin; [P13; Advanced patterns][adv]; [GitHub signals][sig]).
- **Two-tier authorization:** Draft tool runs use an **Agent Inbox** card (`Authorize`, `Edit scope`, `Decline`) showing exact args, input hashes, and no-network sandbox proof ([P12; Advanced patterns][adv]); resulting diffs review separately (Circuitly; [GitHub signals][sig]). Changing a **released** part opens a frozen **From/To Change Order (ECO)** (Duro, Fusion Manage; [Shared #6; Hardware conventions][hw]). If base HEAD advances mid-review, approval invalidates until re-compared (Onshape Workspace Protection; [P18; Advanced patterns][adv]).

## 3. Evidence Registers, Local Ripple Graph & Governance

**Registers, blockers & verbatim authority:** Backend labels (`unmodeled`, `interface_bound`, `design_compiled`, `blocked`) print verbatim—never promoted client-side. Five inline glyphs keep tables, overlays, and graphs scannable: **`?` UNKNOWN** (dashed row naming the missing datum + `[Supply]`), **`~` ASSUMED** (amber hatch—required on CADAM/marimo what-if sliders so modeled outputs never look measured; [P23; Advanced patterns][adv]), **`=` REF/DOC** (datasheet/offer + hash), **`*` MEASURED** (verified receipt + SHA-256 + age), and **`! STALE`** (input changed; [P25; Advanced patterns][adv]). Blockers use AllSpice structured cards (`claim, observed, requirement, consequence, evidence, repair`) paired with KiCad markers ([P21; Advanced patterns][adv]; [KiCad 9; Hardware conventions][hw]). Scoped gates separate `unassessed` from `0 digital blockers · physical unproven`—never "ready."

**Counterfactual swaps without hairballs:** From a stuck BOM row, **Find same MPN** keeps identity while **Assess alternate** forks a draft ([SO-ARM100; GitHub signals][sig]). Compare runs in place, differences-only by default (Onshape; [Shared #4; Hardware conventions][hw]), pairing registered `A/B/Split/Blend` wipe (deltaKi; [P19; Advanced patterns][adv]) with a **local, depth-limited (1–3) ripple graph** (Obsidian local graph; [P17; Advanced patterns][adv]) toggleable to a delta table. Every diff carries a deltaKi **`Coverage` strip** listing unmapped links, unrendered layers, and unchecked domains—bounding HS’s `akcli` and `kdif` receipts so visual delivery never implies electrical substitution ([P20; Advanced patterns][adv]; [Executed HS record; GitHub signals][sig]). Parallel drafts compare in one table with **missing evidence first** (Cursor; [P14; Advanced patterns][adv]).

**Lab, Repair & Phone:** External GitHub-Signal tools follow `Discovered→Adapter Review→Approved→Disabled` with pinned Git SHA, SPDX license, no-network sandbox (`bwrap --unshare-net` or pinned digest), and hashed receipts linked from reviews. Sealed holdout evals (`unseen_devices 14/15+1a`, `Sweep v2.2 4/5+1a`) keep answers sealed and scope scores to protocol and commit (PartCAD verdicts; [P16; Advanced patterns][adv]; [GitHub signals][sig]). Preset `4:Repair` pins competing hypotheses beside distinguishing observations behind backend safety gates. Opened from any deep link, **Phone** is a Bench Capture & Triage Remote—never shrunk CAD—staging photos or caliper readings as unreviewed `* OBSERVED` on an owned unit (InvenTree; [Hardware conventions][hw]), with scoped triage and **Resume on desktop**.

## 4. Observed Patterns Rejected & Why

- **Obsidian global graph & growth time-lapse** ([§3#1; Advanced patterns][adv]): decorative hairball burying causal paths; replaced by a depth 1–3 local ripple graph + table.
- **Figma live cursors & follow mode** ([§3#2; Advanced patterns][adv]): noisy sync overhead for a small workshop; keep deep links and anchored comments (`P24`).
- **Linear streaming agent "thoughts"** ([§3#3; Advanced patterns][adv]): buries receipts in prose; keep typed past-tense actions and fold raw thoughts.
- **Foxglove ungrounded semantic search** ([§3#4; Advanced patterns][adv]): engineers distrust unexplained ranks; put exact MPN/refdes/ID lookup first and require a visible matched field.
- **Premature command palette & layout builder** ([§3#5; Advanced patterns][adv]): theatre before verbs exist; ship four presets + split first, adding `Cmd+K` after 6+ verbs land (`P9`).
- **CADAM/MuJoCo sliders on measured traces** ([§3#6; Advanced patterns][adv]): makes estimates look measured; isolate sliders in `~ ASSUMED` and require explicit reruns.
- **Cursor parallel panes hiding missing evidence** ([§3#7; Advanced patterns][adv]): wastes width when branches lack proof; collapse into one missing-evidence-first table.
- **Decorative transitions & scrubbing static revisions** ([P1, §3#8; Advanced patterns][adv]): intermediate revisions never existed (Zoo v1.5.5 cut animations); snap snapshots and scrub only recorded runs.
- **Altium health score (X/10) & AllSpice silent suppression** ([Altium; Hardware conventions][hw]; [P21; Advanced patterns][adv]): aggregate scores hide fatal blockers and silent thumbs-down risks hiding gates; log waivers in a KiCad-style Ignored tab and never suppress backend blockers.

## 5. Wireframes

Illustrative states throughout.

### Screen 1 · Run Time, Linked Views & Agents (`HS-3G-B`, `2:Sim+PCB`)

```text
┌─ HS · Projects / HS-3G-B Drone · r7 (pinned) ──────────── [4 blockers · ? 2] [New: 2] ─┐
│ [1:BOM] [*2:Sim+PCB] [3:Swap] [4:Repair]   [+ Split]         [Spine ◂] [Proof ▸] [Lab] │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ PYBULLET 3D · saved pose  [Trail: Recent] │ BATTERY TRACE + LINKED PCB · r7 inputs     │
│        o───┐ ┌───o       gust →           │ 14.8V ───────╲_●_╱───────  ① 4.2s · 14.1V  │
│           [F405]  ① Batt    ╭──╮ verdict  │   ~ Pack R: assumed (r5 · 9d lookback)     │
│        o───┘ └───o          ╰──╯ clear.   │   ? Measured R: unknown  [Supply evidence] │
│ Solid: CAD · Wireframe: REF_ENVELOPE      │ ────────────────────────────────────────── │
│ Overlay = check geometry · RMS 11.4 mm    │ LINKED BOARD · KiCanvas F.Cu  [↗ Sch: U1]  │
│ [Pin sample ①]  [Space: Peek Batt]        │ * U1:F405 ↔ BOM · ! DRC-02 0.12mm   [Jump] │
│ Mapping: 4/4 motors · 1/2 sensors mapped  │ ? RX ELRS: UNLINKED  [Open source .kicad]  │
├───────────────────────────────────────────┴────────────────────────────────────────────┤
│ Run 38   [▶ Space] [←/→ ±100ms] [Shift ±10ms]   0s ━━━●━━━━ 12s ① 4.2s   [Offline pkg] │
│ Project  r6 ──● r7 (run base) ──○ r8   ┆  14:02 @codex: DRC → 1 flag [Jump]  [Go live] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Screen 2 · Counterfactual Swap & Local Ripple (`FieldDeck`, `3:Swap`)

```text
┌─ FieldDeck / DISP-01 · Base r12 (7") → Draft D-5in (5") ───────── [3 blockers · ? 2] ──┐
│ [Δ Only ✓]  [A] [B] [Split] [*Blend 50%]            [Coverage: 2 gaps]  [Exit Compare] │
├───────────────────────────────────────┬────────────────────────────────────────────────┤
│ CADQUERY SECTION · registered blend   │ LOCAL RIPPLE GRAPH · DISP-01  [Depth:2][Table] │
│   ┌───────────────║─────────┐         │ DISP-01 (7" → 5" draft · identity_changed)     │
│   │  7" base      ║ 5" draft│         │  ├─ MECH  4 shells    * CAD rebuilt (0 clash)  │
│   │  193×110 mm   ║145×88 mm│ ──① FPC │  ├─ PWR   2.4→1.35W   ~ modeled (+25% run)     │
│   └───────────────║─────────┘         │  │   └─ Load slider   ~ assumed (not measured) │
│ 4 reprinted STLs · 0 geometric clash  │  ├─ WIRE  ① DSI-FPC   ? bend rad.   [Supply]   │
│ [Swap A↔B] [kdif PCB: visual only]    │  └─ VERIF Fit (r12)   ! STALE (env Δ) [Rerun]  │
│ +11 unchanged hidden [Show unchanged] │ Coverage: 1 unmapped (I2C) · elec. unchecked   │
├───────────────────────────────────────┴────────────────────────────────────────────────┤
│ r12 ─┬─● D-5in  · ? 2 · 1 stale · 4 STLs     [Compare drafts (? first)] [Review D-5in] │
│      └─○ D-Salv · ? 4 · donor unverified     Auth: no implicit upgrade  [Pin baseline] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Screen 3 · Full-Width BOM & Scoped Agent Gate (`SO-ARM100`, `1:BOM`)

```text
┌─ SO-ARM100 / r4 · Direct BOM Entry ───────────────── [3 blockers · ? 2] [Lab · Evals] ─┐
│ [*1:BOM] [2:Sim+PCB] [3:Swap] [4:Repair]   Filter: [MPN / refdes / ID ]  [Space: Peek] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Pos   Requirement / Candidate         Origin · Stock     Evidence & Age   Action       │
│ ▸M2   Elbow Servo (C044 unavail.)     REQ · 0 on hand    ? torque @12V    [Find MPN]   │
│  ├─   Same MPN: STS3215-C044          OFFER · 2026-11-16 = ref (out)      [Open offer] │
│  ├─   Owned Unit: bin B4 (donor D17)  STOCK · 1 owned    ? pinout/rating  [Test swap]  │
│  └─   Alt MPN: STS3215-C046           CAT · 3 offers     ~ torque unchk   [Fork draft] │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ AGENT RECEIPTS · Scope: [M2 / Draft B4.1] │ APPROVE SCOPED RUN · Base r4 (current r4)  │
│ 10:43 @claude: Attached D17 crop  [Jump]  │ Tool   akcli@2126c32 · MIT · Approved      │
│ 10:45 @claude: Searched 3 offers  [Jump]  │ Guard  bwrap --unshare-net · 0 host mounts │
│ 10:47 @claude: Requests akcli run (wait)  │ Scope  Read: B4.1 sch · Write: 1 report    │
│ [Side question] [Cancel msg ✕] [Resume]   │ [Authorize run] [Edit scope] [Decline]     │
├───────────────────────────────────────────┴────────────────────────────────────────────┤
│ Lab: akcli/kdif receipts (bounded coverage) · Holdouts: 14/15+1a · 4/5+1a  [Audit Lab] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Phone · Bench Capture & Scoped Triage

```text
┌─ HS Phone · FieldDeck / D-5in ───────┐
│ [*Capture]  [Triage (1)]  [Pin ①]    │
├──────────────────────────────────────┤
│ DISP-01 / DSI-FPC · ? UNKNOWN        │
│ Missing: FPC bend radius (min mm)    │
│ [Source crop]  [Snap bench photo]    │
│ Reading: [ 4.5 mm ] Method: Caliper  │
│ → Stages * OBSERVED (needs review)   │
│ [Stage Evidence]  [Coverage: 2 gaps] │
├──────────────────────────────────────┤
│ TRIAGE · @claude · akcli check       │
│ Base r12 · 0 auth upgrades · no-net  │
│ Δ Blockers: 3 → 3 (FPC ? still open) │
│ [Inspect scope]  [Authorize] [Decl.] │
│ [Resume full diff on desktop ↗]      │
└──────────────────────────────────────┘
```

## What I Took from the Others / What I Disagree With

From **[Sol](codex-gpt-6.2-sol.md)**, I took the two-instrument default, full-width BOM table, separate continuous Run and discrete Project clocks with `New activity`/`Go live` pinning, and reserving formal From/To ECOs for released scope so draft checks stay lightweight. I disagree with dropping compact epistemic glyphs—across a 40-row BOM or diff, `?`/`~`/`=`/`*` (plus `! STALE`) communicate authority pre-attentively without chrome—and with flattening downstream impact into a plain list where a local depth-limited ripple graph exposes cross-domain chains immediately.

From **[Astra](codex-gpt-6.2-astra.md)**, I took the restorable question (**pin, follow, return**) carrying a pinned temporal sample across branches as a baseline, plus missing-evidence-first candidate comparison. I disagree with linear one-consequence-at-a-time trails: when fit, power, and harness bend couple, 2-lens presets plus a local ripple graph show coupled impacts beside the baseline, while a *collapsible* Spine keeps whole-machine context without stealing width.

## Ranked First-Build List

1. **FieldDeck `3:Swap` & `1:BOM` (single-port `hs-serve`):** Full-width BOM separating stock units from offers, registered `A/B/Split/Blend` compare, deltaKi `Coverage`, local depth-2 ripple graph + table toggle, `?`/`~`/`=`/`*` and `! STALE` with lookback age, deep links, and one `UNLINKED` path.
2. **Scoped Agent Inbox, Receipts & `akcli`/`kdif`:** Project clock with typed receipts, `New activity` pinning, resumable sessions, sandbox approval (competing drafts, stale-base invalidation), phone capture/triage, and existing `akcli`/`kdif` receipts with bounded coverage.
3. **Run Stage, Board Cross-Probe & Lab:** Continuous PyBullet playback (`2:Sim+PCB`) with spike jump, verdict overlays, and `Pin sample`; extend linked selection to KiCanvas, `4:Repair` safety gates, and read-only sealed holdout evals.
4. **Dual-Entry Acceptance Test:** Compare direct BOM entry against Projects home and the current file/viewer flow on FieldDeck and the unavailable SO-ARM100 servo—measuring engineer-minutes, missed dependencies, unsupported approvals, and setup cost separately, counting *"insufficient evidence"* as valid ([Acceptance cases; GitHub signals][sig]).

[adv]: ../design-research/ADVANCED_INTERFACE_PATTERNS_20261118.md
[hw]: ../design-research/HARDWARE_TOOL_UI_CONVENTIONS_20261118.md
[sig]: ../design-research/FRONTEND_GITHUB_SIGNALS_20261118.md
