# Hardware Splicer — Follow the evidence through a change

Open Projects to resume the last engineering question, or start with a goal, owned or salvaged stock, or a reference study. A missing part can start a project before geometry exists. Open a stuck BOM row directly from a shared link or a tool integration. Give the BOM the full width when sourcing. Each position connects a requirement, exact MPN, dated supplier offers, individual stock units and alternates. **Find the same MPN** preserves the design identity. **Assess an alternate** forks a draft. In a teardown, a photo crop can support a tentative donor identification while its connector and rating remain unknown. Record the physical unit in InvenTree with its own evidence. Offer suggestions on request, following ecoEDA’s intake study, the SO-ARM100 sourcing issues, and InvenTree’s part/stock distinction. [GitHub signals][signals] · [Hardware conventions][hardware]

## A bench that moves with the question

Start with one working view. **Open beside** brings up a second instrument and keeps the selected item in both. Saved presets such as Motion, Fit + Wiring, and Diagnosis recall panels, camera and layers. A finding can offer the relevant preset in one click. Resize, maximize or return to the previous layout. Use a compact, collapsible outline for navigation and a source drawer for detail. Keep visible actions and keyboard hints, with exact lookup by MPN, refdes or finding ID. This adapts Rerun blueprints and Foxglove saved layouts, plus Linear’s peek. [Advanced patterns][advanced]

A shareable address carries the project, immutable revision or specific draft snapshot, selected object and optional finding, run and recorded time. Interactive HTML BOM’s bidirectional cross-probing and tscircuit’s pad-to-schematic jump extend across CAD bodies, KiCad symbols and footprints, harness endpoints, BOM positions and evidence. Highlight peers only through explicit mappings. An unlinked item opens its native file or report. CadQuery studies show their generated artifacts, PyBullet shows recorded poses, and plotter toolpaths step through recorded commands. Load specialist viewers on demand and keep links back to source-native artifacts, as Copper’s KiCad integration suggests. [Hardware conventions][hardware] · [Advanced patterns][advanced] · [GitHub signals][signals]

**Step through a run.** A Rerun-style cursor drives pose, telemetry and timestamped findings from one recorded stream. Click a trace spike to pause at that sample, highlight the mapped component and open the check’s source. The board stays at the run’s input revision and can cross-highlight that selection. Show missing channels and mapping coverage, as LeRobot does. Draw a clearance overlay from the check’s own geometry, following RoboSimStudio. Show each run’s engine version, inputs, output hashes and offline rerun package. [Advanced patterns][advanced]

**Step through project history.** A separate revision and activity strip steps between discrete snapshots. Expand tracks for the selected part or requirement. Clicking “check finished” opens the producing run at its input snapshot, with an optional jump into recorded run time. Stepping back restores the evidence available then. Foxglove-style lookback shows a prior observation with its revision and age. An input change marks dependent checks stale with a reason, adapting marimo’s lazy invalidation. Later receipts increment **New activity** while playback, historical inspection or approval stays pinned. Choose **Go live** to receive new events in place, or open an individual receipt. Onshape’s branch and merge markers distinguish saved revisions from parallel drafts. [Advanced patterns][advanced]

Authority never upgrades implicitly. The inspector shows the backend label verbatim, claim scope, producer, source and receipt. **Unknown** occupies its own row with the missing input and an evidence action. Conflicting observations stay visible with their scopes. Show persistent backend blocker counts for the selected action, with separate states for an absent assessment and a scoped assessment reporting zero blockers. Blockers never become “ready.” Diagnosis lists competing hypotheses and the evidence that would distinguish them. The backend’s safety gate controls each proposed test and names the missing prerequisite. Use KiCad’s list-and-marker pattern and AllSpice’s sourced finding cards. [Hardware conventions][hardware] · [Advanced patterns][advanced]

### 1 · Inspect a saved run

Illustrative states throughout.

```text
┌ Projects / Drone study / r7 · pinned ──────────────────────── [New activity 2] [BOM] ┐
│ Battery / voltage dip                               [Fabrication blockers] [Source]  │
├───────────────────────────────────────────┬──────────────────────────────────────────┤
│ PYBULLET · saved pose                     │ BATTERY TRACE · sample at cursor         │
│          o───┐ ┌───o                      │ ──────────╲_●_╱────────                  │
│              ├─┤   ① Battery              │            ↑ ① voltage minimum           │
│          o───┘ └───o                      │ ① Model input: pack resistance assumed   │
│ [Open linked wiring]                      │ Measured resistance: ? unknown [Request] │
├───────────────────────────────────────────┴──────────────────────────────────────────┤
│ Run 38   [▶ Space] [←/→ Sample]  0 s ─────●───── 12 s    [Receipt] [Offline package] │
│ Project  r6 ──● r7 (run inputs) ──○ r8      r7 · MCP wiring report arrived [Open]    │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Compare consequences, then decide

Compare in place against a pinned base. Start differences-only, with a row for each reported downstream impact. Select the cable row to show the harness beside the enclosure section and trace the finding back to its input. Support Base/Target, split and blend with known registration. Otherwise show independent views. **Coverage** lists unrendered artifacts, unmapped objects and unchecked dependencies. Selecting a stale result shows what changed and offers a scoped rerun. A released line opens a change order with From/To items and affected scope, preserving the released revision and freezing the approved order. Use Onshape’s feature diff, deltaKi’s modes and coverage, and Duro’s affected-items convention. [Hardware conventions][hardware] · [Advanced patterns][advanced]

### 2 · Assess an alternate

```text
┌ FieldDeck / DISPLAY ─────────────────────────────────── Base r12 (7") → Draft A (5") ┐
│ [Differences only ✓] [Base] [Target] [Split] [Blend]               [Coverage 2 gaps] │
├───────────────────────────────────────┬──────────────────────────────────────────────┤
│ CadQuery section · registered overlay │ Follow an impact                             │
│   ┌────────────────────┐              │ Bezel         Changed files       [Inspect]  │
│   │  ┌──────────┐      │              │ Runtime       Modelled delta      [Inputs]   │
│   │  └──────────┘──①   │              │ › ① Cable     ? bend radius       [Request]  │
│   └────────────────────┘              │ Pin/voltage   Unchecked          [Coverage]  │
├───────────────────────────────────────┴──────────────────────────────────────────────┤
│ r12 ──┬── Draft A  ·  Fit receipt arrived [Open]                                     │
│       └── Draft B  ·  Donor identity unknown    [Compare candidates] [Review draft A]│
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Give agents a place in the work

Assign a question from a finding with visible object scope, base, allowed inputs and outputs. Each agent or MCP caller works on an isolated draft. Task tracks show started, receipt, needs input, failure and completion. Click a receipt to open what it touched. Group routine progress and show the last receipt time when activity becomes unknown. Reconnect by fetching the current snapshot and catching up on recorded events. Steer with a narrower request or stop a supported run. Compare parallel candidates in one table with missing evidence first. This uses Linear’s typed activity, Devin’s receipt navigation, Zoo’s resumability and Cursor’s isolated tasks. [Advanced patterns][advanced] · [GitHub signals][signals]

Agent Inbox and Circuitly’s file diffs inform a pinned review card. Authorize the exact operation with its arguments and permissions, then review the resulting diff as a separate decision. If the base advances, reopen the comparison and obtain fresh approval before applying. The same backend gates cover internal and MCP callers. The workshop queue gives GitHub discoveries the same review path with source, pinned commit, verified license, reviewed adapter, exact command and inputs. Execution requires human approval and a fail-closed no-network sandbox. Attach the hashed receipt. Link existing akcli inspection and kdif silkscreen diff from the affected artifact with their actual coverage. A sealed evaluation opens its protocol and sealed prediction digest, then outcomes and abstentions after scoring. Benchmark scope stays on the receipt. [Advanced patterns][advanced] · [GitHub signals][signals]

### 3 · Review a scoped operation

```text
┌ FieldDeck / Draft A / Agent activity ──────────────────────── [Workshop] [All tasks] ┐
│ 14:02  CAD via MCP · Fit report attached [Open]      14:05  Harness · Needs input    │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Request  Run wiring check on Draft A                  Expected base r12 · current r12│
│ Reads    Draft A harness and candidate part record    [Inspect inputs and hashes]    │
│ Writes   One diagnostic report on Draft A             [Inspect scope and coverage]   │
│ Open     Candidate pinout source missing              [Request from owner]           │
│ [Authorize this run]      [Return with narrower scope]      [Decline]                │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Phone at the bench

Open the same finding from a timestamped link, adapting Foxglove’s sharing and AllSpice’s anchored snippets. Stack before/after, show a source crop, and stage donor photos or readings with unit, method and provenance for review. Inspect the full scope before any approval. Offer **Resume on desktop** when the diff needs a larger view. [Advanced patterns][advanced]

```text
┌──────────────────────────────────────┐
│ FieldDeck / Draft A / Cable ①        │
│ Bend radius    ? unknown             │
│ [Source crop] [Coverage]             │
│ [Stage photo or reading]             │
├──────────────────────────────────────┤
│ Wiring check · approval requested    │
│ [Inspect exact scope]                │
│ [Resume on desktop]                  │
└──────────────────────────────────────┘
```

## Patterns to leave out

Obsidian’s global graph and growth animation obscure the short dependency path a decision needs. Figma-style participant cursors and viewport following add distraction and sync cost. Linear-style thought rows add noise to receipts. Foxglove-style semantic search earns a place only with an explained match and exact filters. Defer a general palette and layout editor until useful verbs and panels exist. Keep CADAM-style slider results explicitly assumed and require an explicit run for new evidence. Cursor-style parallel panes waste space when candidates lack the same evidence. Skip decorative transitions and simulated playback of static revisions. Zoo’s reduced animations and the distinction between a recorded sample and a saved snapshot both favor immediate, legible state changes. Altium BOM Portal’s aggregate health score can conceal a blocker, and AllSpice-style suppression can hide an unresolved gate. [Advanced patterns][advanced] · [Hardware conventions][hardware]

## What I took from the others / what I disagree with

I took presets and phone capture from Argon. I’d cap the default at two instruments to keep artifacts legible and reserve formal change orders for released scope so routine agent checks stay lightweight. I took Astra’s restorable trail and explicit unlinked endpoint. When fit and wiring depend on each other, I’d pin both views so the engineer can follow a finding without retracing the trail. [Argon](gemini-argon.md) · [Astra](codex-gpt-6.2-astra.md)

## Ranked first build

1. Reuse the FieldDeck study and substitution UI for linked compare, coverage, stale evidence and exact deep links. Include an intentionally unmapped path.
2. Add receipt tracks, scoped MCP approval and phone triage. Exercise competing drafts, a stale approval and reconnect. Surface existing akcli/kdif receipts in the same review.
3. Add recorded PyBullet playback with a trace-to-finding jump. Extend the linked bench to KiCad, wiring and a repair gate, then expose the sealed evaluation ledger.
4. Compare the direct BOM entry and Projects entry on FieldDeck and an unavailable SO-ARM100 servo. Measure time to a justified decision, missed dependencies and unsupported claims. Missing evidence can be the correct result. [GitHub signals][signals]

[advanced]: ../design-research/ADVANCED_INTERFACE_PATTERNS_20261118.md
[hardware]: ../design-research/HARDWARE_TOOL_UI_CONVENTIONS_20261118.md
[signals]: ../design-research/FRONTEND_GITHUB_SIGNALS_20261118.md
