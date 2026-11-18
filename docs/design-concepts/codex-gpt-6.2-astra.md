# Hardware Splicer · Follow the question

“Can the servo in bin B4 replace the elbow servo I can’t buy?” Open that question from the arm’s BOM. Pin the elbow at its closest approach to the bracket. Follow the donor’s marking into a teardown photo, then its lead into a wiring drawing. The pinned elbow stays beside you. **Return to question** restores that pose with the evidence you’ve collected and the gaps you still have to explain. The saved unit of work is a question with a comparison you can hand to another engineer. This borrows Linear’s temporary peek, Rerun’s shareable views and the actual C044/C046 sourcing problem in SO-ARM100. [Advanced patterns, P10/P24][A] · [GitHub signals, SO-ARM100][S]

A question can start with a goal, an owned unit or a study. In Projects, resume a question by its last unresolved finding. From inventory, start directly on the stock unit. Its photo, proposed catalogue identity, supplier offer and BOM requirement each retain their own address. An offer for the same MPN adds a sourcing option. Trying a different MPN opens a branch. Ask for candidates when you want them. In ecoEDA’s study, builders started from both ideas and available parts, and five participants wanted control over suggestions. [GitHub signals, ecoEDA and InvenTree][S] · [Hardware conventions, Altium alternate rows][H]

### 1 · Catch a moment in a study

Illustrative session throughout. Drag across the elbow trace. Each recorded sample moves the PyBullet pose and selects the corresponding check sample. Pinning a sample keeps its run, input revision, object, camera and timestamp together. Use the check’s own geometry for its overlay. If a channel has no sample, show the gap. A static KiCad footprint can follow a mapped part selection while staying at its input revision. Rerun’s linked frame views, RoboSimStudio’s verdict overlays and Interactive HTML BOM’s two-way selection supply the mechanics. [Advanced patterns, P1/P6/P8][A] · [Hardware conventions, Interactive HTML BOM][H]

```text
┌─ Arm study / r4 / Can B4 replace the elbow servo? ───────────────────────────────────┐
│ Pinned baseline · run 27                     [Previous sample] [Next sample] [Play]  │
├──────────────────────────────────────────┬───────────────────────────────────────────┤
│ PyBullet · elbow at closest approach     │ Modelled clearance / bracket              │
│             wrist o                      │            ╲      ╱                       │
│                  /                       │             ╲__●_╱                        │
│          elbow ●/   ┃ bracket            │                │ 2.8 s                    │
│               /     ┃                    │ Pin ① · run 27 · bracket / elbow          │
├──────────────────────────────────────────┴───────────────────────────────────────────┤
│ Run time      0 s ───────────●──────────────── 6 s        [Inputs] [Offline package] │
│ Project log   10:41 run 27 saved   10:43 MCP found donor photo [Peek beside pin ①]   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

The two clocks answer different questions. Seek in run time to inspect the motion. Step through dated project events to inspect what the engineer knew. Select the 10:43 receipt to open the photo alongside pin ①. Step back to 10:41 and the photo drops out of that historical view. Later receipts accumulate behind **New activity** while either view is pinned. For an older observation show its source revision and age. A run receipt opens its engine version, inputs, output digest and offline rerun package. This extends Foxglove’s timestamped events and lookback, Devin’s jump-to-action log and marimo’s reproducible files. [Advanced patterns, P2–P4/P11/P26][A]

### 2 · Pull the change through the assembly

Choose **Try B4** at pin ①. The baseline stays pinned while a draft follows one consequence at a time. Choose “lead order” and the other view becomes the harness endpoint. Select its KiCad refdes to cross-probe schematic, footprint or ERC/DRC marker through recorded mappings. An unmapped endpoint offers the native file and a request for the missing link. For mechanical fit, compare CadQuery sections with a wipe when registered, or independent labelled views otherwise. Coverage lists omitted objects and unchecked interfaces even with unchanged rows collapsed. [Hardware conventions, KiCad and Onshape][H] · [Advanced patterns, tscircuit and deltaKi, P6/P19/P20][A]

```text
┌─ Arm / elbow / Pin ① ─────────────────────────────── r4 vs draft B4.1 · changes only ┐
│ Missing evidence first          [Mount pattern] [Lead order ×] [Show unchanged]      │
├──────────────────────────────────────────┬───────────────────────────────────────────┤
│ Keep beside me · baseline                │ Follow lead order · draft B4.1            │
│ Run 27     elbow ●   ┃ bracket           │ Donor D17 ── cable ── ? ┄┄ J2 / pin 1     │
│ Sample     2.8 s     ①                   │ J2 → schematic [Locate]                   │
│ Inputs     r4 motor + bracket            │ D17 lead → J2 pin     ? mapping missing   │
├──────────────────────────────────────────┴───────────────────────────────────────────┤
│ Fit result   stale for draft · motor envelope changed       [Inspect r4 inputs]      │
│ Coverage     donor sweep unchecked · connector photo only   [Open teardown crop]     │
│ r4 ─┬─ B4.1 donor D17    [Ask agent for pinout source]       [Return to question]    │
│     └─ C.1  catalogue    torque at required voltage unknown [Compare missing data]   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Changing the envelope invalidates dependent fit results. Keep the baseline result inspectable and offer an explicit rerun against the draft. Every claim carries its backend authority verbatim. A plausible match, successful run or accepted edit can never implicitly upgrade authority. **Unknown** gets a row, the missing datum and an evidence action. Show the backend blockers for the proposed action, distinguish an absent assessment from zero scoped blockers, and keep every outstanding blocker visible through review. Blockers never read “ready.” In repair diagnosis, pin competing hypotheses beside the observation that distinguishes them. A gated test opens its missing safety prerequisite. [Advanced patterns, marimo and AllSpice, P21/P25][A] · [GitHub signals, PartCAD verdicts][S]

### 3 · Open the agent’s receipt inside the question

```text
┌─ Arm / B4.1 / D17 lead order ──────────────────────────────── Pin ① retained [Back] ─┐
│ 10:43  MCP attached teardown crop     10:47  MCP requests schematic inspection       │
├──────────────────────────────────────────┬───────────────────────────────────────────┤
│ Evidence at request                      │ Authorize one operation                   │
│ D17 label     [Open source crop]         │ Adapter   akcli  [Reviewed commit]        │
│ J2 pin 1      [Open KiCad sheet]         │ Read      B4.1 schematic [Hashes]         │
│ Donor pinout  ? source requested         │ Write     one inspection report on B4.1   │
│                                          │ Sandbox   no network [Inspect arguments]  │
├──────────────────────────────────────────┴───────────────────────────────────────────┤
│ Scope ends at board-side labels. Donor lead order still needs independent evidence.  │
│ [Authorize inspection]   [Edit scope]   [Decline]             [View last receipt]    │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Bind MCP work to the selected endpoint and draft snapshot. A typed receipt replaces “inspecting” with the report, failure or request for input. Silence shows last contact and unknown activity. Resume after navigation. Click a reported pin to open its source and the exact schematic on which the agent worked. Review any resulting design diff separately. A changed base requires fresh comparison and approval. Use a From/To change order for released items. [Advanced patterns, Linear, Devin and Agent Inbox, P11–P13][A] · [GitHub signals, Zoo Resume][S] · [Hardware conventions, Fusion Manage][H]

Follow the tool name upstream into the GitHub tool factory to inspect discovery, licence, pinned commit and human adapter review. A new commit waits for review before execution. Follow the sandbox receipt downstream to hashed outputs. HS’s existing akcli inspection and kdif silkscreen diff give this path real artifacts with bounded coverage. For “how reliable is this adapter?”, open a sealed evaluation at its protocol and tool version. Keep held-out answers sealed during work. After scoring, show aggregate outcomes and abstentions scoped to the evaluated capability. [GitHub signals, executed HS record][S] · [Advanced patterns, PartCAD verification and deltaKi coverage, P16/P20][A]

### At the parts bin

Open the same question on a phone, capture the missing source against the individual unit, and stage it for review. The desktop receives a receipt beside the pinned sample. Only a reviewed evidence record can change the answer. This combines AllSpice’s anchored snippets with InvenTree’s stock-unit distinction and Foxglove’s timestamp sharing. [Hardware conventions][H] · [Advanced patterns, P24][A]

```text
┌─ Arm / B4.1 / donor D17 ─────────┐
│ Which lead reaches J2 pin 1?     │
│ ? Donor pinout source missing    │
│ [Teardown crop]  [Capture label] │
│ Source note  [                  ]│
│ [Stage photo for review]         │
├──────────────────────────────────┤
│ Return to pin ① · r4 / 2.8 s     │
└──────────────────────────────────┘
```

### Patterns I would leave out

Obsidian’s global graph and growth animation bury the single missing edge. Figma-style cursors and follow mode would pull the engineer off the pinned sample. Linear thought streams would bury the receipt. Foxglove-style semantic matches need a visible matched field and exact lookup. Defer a general palette and layout editor until engineers have repeated verbs and views worth saving. Keep assumption sliders out of measured traces. Collapse parallel agent panels into a missing-evidence comparison when both lack the same source. Skip smooth transitions between discrete revisions because intermediate states never existed. Altium’s aggregate health score could conceal the very blocker the question depends on. [Advanced patterns, gimmick list §3][A] · [Hardware conventions, Altium BOM Portal][H]

## What I took from the others / what I disagree with

Argon’s phone capture makes a teardown photo part of the same investigation. Its permanent BOM spine costs too much of a small drawing when the engineer already has the part in hand. Sol’s separate history and playback controls preserve the meaning of a sample. I’d also let the engineer carry that sample into a different branch as an explicitly labelled baseline, so returning from a wiring detour restores the precise mechanical question. [Argon](gemini-argon.md) · [Sol](codex-gpt-6.2-sol.md)

### Ranked first build

1. Ship **pin, follow, return** on the existing FieldDeck display swap. From the changed enclosure follow the cable to an unresolved pin/voltage check and back. Test restoration and stale-input coverage.
2. Attach the existing akcli/kdif receipts to their own schematic and board review. Exercise an unlinked finding, a phone capture and a proposal whose base advances mid-review.
3. Bind one recorded PyBullet trace and pose to a shareable sample. Replay the project log across a late MCP receipt and confirm that the historical evidence set is reproducible.
4. Try the unavailable SO-ARM100 servo from a direct BOM link and from Projects. Measure engineer-minutes, missed dependencies and unsupported approvals against the existing workflow. Count a justified request for evidence as a completed decision. [GitHub signals, acceptance cases][S]

[A]: ../design-research/ADVANCED_INTERFACE_PATTERNS_20261118.md
[H]: ../design-research/HARDWARE_TOOL_UI_CONVENTIONS_20261118.md
[S]: ../design-research/FRONTEND_GITHUB_SIGNALS_20261118.md
