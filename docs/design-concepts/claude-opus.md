# Hardware Splicer · The Casefile

An HS project is a chain of claims: parts rest on requirements, geometry on parts, checks on geometry, the release assessment on everything. The other three concepts arrange panels around that chain. I propose making the chain the interface.

**The Casefile** is one live document per project, running top to bottom in the order evidence flows: Goal → Requirements → Parts → Geometry and circuit → Studies and checks → Release assessment. Each section is a typed *cell* with an address, the backend's authority label, producer, age, and the cells it depends on. Viewers live inside cells. When something upstream changes, the cells below visibly go stale, each naming its cause. The page moves only when evidence moves: dynamic without decoration, which is my answer to "too rigid and too static". The ordering adapts marimo's dependency graph and lazy stale marking (P25) and Zoo's GUI-actions-are-edits-to-a-plain-artifact (P26) [A]; the name is the backend's own (`casefile.py`).

## 1 · What the user sees most of the time

The casefile fills the window between two margins:

- **Dependency rail (left, 24 px):** a minimap with one glyph per cell: settled `▪`, stale `≈`, unknown `?`, blocker `✕`, changed in draft `Δ`, holds selection `◆`. Like a code editor's overview ruler, it shows where in the chain the trouble sits; click to jump. This answers the finding that blockers at the bottom of a pane get missed and need persistent counts plus markers [H, verdict and #3].
- **Margin (right, ~240 px):** agent activity, comments and approval requests beside the cell they touch, as AllSpice and Altium 365 anchor comments [H][A, P21/P24], not in a separate feed.

A fixed header carries backend counts (`Blockers 3 · Unknown 2 · Stale 0 · Not assessed: power`; "not assessed" is distinct from zero), the revision picker, selection and Inbox. It never shows a verdict. Printed keys: `J/K` cell to cell, `Space` peek a row (Linear, P10), `F` lift, `C` compare, `/` exact find by MPN, refdes or finding ID.

**Lift** (`F`) is the one mode change: a viewer cell fills the stage, the casefile shrinks to a titled rail, linked cells line up on the right, `Esc` drops it back. No user tiling, presets or layout engine.

## 2 · One grammar for every capability

| Capability | Lives as |
|---|---|
| Goal, owned/salvaged parts, reference study | Three ways to write the first cells; a study pre-fills cells 1–4. |
| BOM and sourcing | **Parts** cell: a full-width table, since a BOM is a table, not a narrow list [H]. Requirement, identified part, offer and stock unit stay separate records; alternates are ranked sub-rows (Altium, InvenTree [H]). |
| CadQuery, PyBullet, plotter toolpaths | **Study** cells: run, engine version, inputs, hashes, offline package. |
| KiCad ERC/DRC, footprints, fab gating | **Board** cell (KiCanvas) and **Check** cell in KiCad's list-plus-marker form, exclusions in their own tab [H]. |
| Wiring checks | **Wiring** cell with endpoints and coverage. |
| Teardown, salvage, InvenTree | Each unit is a small casefile (photo crops, proposed identity, sources, measurements, used in), cited by Parts cells. |
| Repair diagnosis | Casefile: Symptom → Observations → competing Hypotheses → Gated tests; a missing safety prerequisite opens itself. |
| GitHub tool factory | Casefile per tool: Discovery → Licence → Pinned commit → Adapter review → No-network hashed runs → Used in. A new upstream commit adds a blocking review cell. |
| Sealed evaluations | Casefile: Protocol → Sealed predictions (digest) → Scoring → Outcomes and abstentions. |
| MCP gateway, agents | Suggestion cells in any casefile (§4). |

**Projects** is home: project casefiles with backend counts and last unresolved cell, the cross-project Inbox, and a Workshop shelf of unit, tool and evaluation casefiles. A friend who learns one casefile can read all of them.

## 3 · Evidence, unknowns, blockers and the ripple

Each cell header prints the authority label verbatim with producer, source and age. A value carried from an older revision shows that revision and age (Foxglove lookback, P3). An unknown gets its own row, the missing datum and an evidence action. Glyphs mirror backend states; the UI computes nothing.

**The ripple.** Choosing an alternate opens a *draft*. The casefile re-renders as differences only, unchanged cells collapsed to `┄ unchanged ┄` (Onshape, deltaKi; P19). The backend's `change_impact`/`evidence_impact` result then marks downstream cells in dependency order (`≈ stale: display envelope changed ◄ 3`), the `◄` linking back to the cause. Marks come only from that result, never a second computation (RoboSimStudio's overlay rule, P8). An unassessed cell reads **impact not assessed**, never "unchanged". Every compare carries a **Coverage** line of what it cannot see (deltaKi, P20). Stale cells keep their base result and offer **Run on draft**; nothing reruns silently. **Save** stores state and promotes no claim. From/To change orders apply only to released revisions [H, #6].

## 4 · Agents in the margin

A working agent is a margin card beside the cell it touches, with typed activity: started, finished with a result link, needs input, error (Linear, Devin; P11). Thoughts are folded. Silence reads `last contact 4 min · activity unknown`. Reconnecting catches up from `project_events` (Zoo Resume, P13 [S]).

Agents change things only through **suggestion cells**: tracked-change blocks where the change lands, pinned to a base revision; if the base moves, the block says *base moved* and needs a fresh compare. Approval is two steps (Agent Inbox, Circuitly; P12 [S]): **authorize the operation** (base, reads, writes, network, tool commit: Authorize / Narrow / Respond / Decline), then **review the result** as an ordinary draft with its ripple. Report-only operations can be batched; design diffs and newly pinned tools cannot. An agent's own checks (P16) appear as Check cells, failures included.

## 5 · Viewers: embedded, lifted, linked

- **Embedded:** a labelled snapshot until clicked; one live WebGL context at a time.
- **Linked selection:** selecting U1 on the board selects its BOM line and CadQuery body only through backend mappings (Interactive HTML BOM, tscircuit; P6). Off-screen hits show as `◆` in the rail; an unmapped item says **not linked** wherever it would appear.
- **Sim replay:** a Study cell with recorded time has transport (Space, ←/→ per sample, trail Off/Recent/Run; LeRobot, Foxglove; P1/P5). Lifted, **Follow run time** moves linked time-varying cells; static ones say `at r7 input · static`. Missing channels are listed. Revisions are never animated between.
- **Deep links** encode project, revision or draft, cell, selection and run time (Rerun, P24).

## Wireframes (illustrative states; FieldDeck labels from `docs/status/generated/fielddeck-display-swap-20261118.json`)

### 1 · Reading the casefile

```text
┌ FieldDeck 5 · r3 ▾ ────────── Blockers 3 · Unknown 2 · Stale 0 · Not assessed: power ┐
│ Casefile   [C] Compare   Selection: DISP SC1975              Inbox 1   [/] find      │
├──┬────────────────────────────────────────────────────────────┬──────────────────────┤
│▪ │ 1 GOAL  5-inch field terminal on a Pi 4, carried one-hand  │                      │
│▪ │ 2 REQUIREMENTS  6 rows · 0 unknown                    [▾]  │                      │
│◆ │ 3 PARTS  12 lines                     [Lines] [Stock units]│ codex · 10:42        │
│  │   Line  Requirement    Identified part   Source   Auth     │ Searched brief:      │
│  │ ◆ DISP  5" DSI touch   SC1975 Touch D.2  vendor   (label)  │ 2 pages attached     │
│  │   SBC   Pi 4 host      Pi 4 B            owned    ? unit   │ [Open receipt]       │
│◆ │ 4 ENCLOSURE · CadQuery run 14 · inputs r3                  │                      │
│  │   ┌──────────────────────────┐ nominal_geometry_checks     │                      │
│  │   │ snapshot · DISP body ◆   │ _passed · 288 changed pairs │                      │
│  │   │ (click to go live)       │ [Receipt] [Offline package] │                      │
│  │   └──────────────────────────┘ [F] Lift                    │                      │
│? │ 5 WIRING  FFC corridor obstruction-free                    │                      │
│  │   ? plug exits and bends not verified       [Coverage]     │                      │
│✕ │ 6 INTERFACE  generic_interface_result: unresolved          │ you · 09:10          │
│  │   ? pin_mapping_unknown  ? signal_voltage_unknown          │ need DSI pinout      │
│  │                                       [Supply evidence]    │ from the brief       │
│✕ │ 7 RELEASE ASSESSMENT  3 blockers (backend, verbatim)  [▾]  │                      │
└──┴────────────────────────────────────────────────────────────┴──────────────────────┘
```

### 2 · A substitution ripples through a draft while an agent asks to act

```text
┌ FieldDeck · Draft A · base r2 SC1635 7" → SC1975 5" ── Blockers 2→3 · Unknown 0→2 ───┐
│ Differences only ✓  [Base] [Target] [Split] [Blend]   Coverage: 2 gaps   [Swap A/B]  │
├──┬────────────────────────────────────────────────────────────┬──────────────────────┤
│  │ ┄ 1–2 Goal, Requirements unchanged ┄               [show]  │                      │
│Δ │ 3 PARTS  DISP  SC1635 7" ─► SC1975 5"   (your choice)      │                      │
│  │   alt  10" Touch D.2  blocked: enclosure_fit,              │                      │
│  │        connector_mismatch, protocol_mismatch       [why]   │ AGENT REQUEST        │
│≈ │ 4 ENCLOSURE  stale: display envelope changed  ◄ 3          │ codex · wiring check │
│  │   base run 9 still inspectable           [Run on draft]    │ Base   Draft A @ r2  │
│≈ │ 5 WIRING  stale: connector position changed  ◄ 3, 4        │ Reads  harness, DISP │
│? │ 6 INTERFACE  new ? pin mapping  ? signal voltage  ◄ 3      │ Writes 1 report      │
│  │   Coverage: no schematic mapping for DISP · kdif not run   │ Net    none          │
│✕ │ 7 RELEASE  +1 blocker: interface unresolved (backend)      │ [Authorize] [Narrow] │
│  │ ┄ 8 Fabrication: impact not assessed ┄             [show]  │ [Respond] [Decline]  │
├──┴────────────────────────────────────────────────────────────┴──────────────────────┤
│ [Discard draft]        [Save as r3: saves state, promotes no claim]                  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 3 · A study cell lifted, linked cells following run time

```text
┌ HS-3G-B drone · r7 · Lifted: 5 Flight study, run 38 ─── Blockers 4 · Unknown 3 ─ [Esc] ┐
├────────────┬─────────────────────────────────────────────┬─────────────────────────────┤
│ CASEFILE   │ PYBULLET · recorded run 38 · engine pinned  │ FOLLOWING RUN TIME          │
│ 1 Goal     │           o───┐   ┌───o                     │ 7 Power · battery model     │
│ 2 Reqs   ? │               ├───┤      ① voltage minimum  │  ────╲_●_╱──── at cursor    │
│ 3 Parts  ◆ │           o───┘   └───o                     │  pack resistance: assumed   │
│ 4 Frame  ▪ │                                             │  measured: ? [Request]      │
│ 5 Flight ▸ │ [Space] ▶  [←/→] sample  0 s ━━━━●━━━━ 12 s │ 6 Board · at r7 input       │
│ 6 Board  ◆ │ Trail: Off · Recent · Run                   │  ESC-1 highlighted, static  │
│ 7 Power  ? │ Channels: pose ✓ battery ✓ motor temp: none │ 3 Parts                     │
│ 8 Release✕ │ [Receipt] [Offline package] [Copy link @ t] │  ESC line linked · RX not   │
│            │                                             │  linked                     │
└────────────┴─────────────────────────────────────────────┴─────────────────────────────┘
```

### Phone · the same casefile, filtered to what needs a hand

```text
┌──────────────────────────────────┐
│ FieldDeck 5 · r3                 │
│ Blockers 3 · Unknown 2           │
│ ▪▪◆▪?✕✕   tap rail to jump       │
├──────────────────────────────────┤
│ ? 6 INTERFACE                    │
│ pin_mapping_unknown              │
│ Wanted: DSI pinout source        │
│ [Photo label] [Enter reading]    │
│ Staged for review, not evidence  │
├──────────────────────────────────┤
│ Inbox · codex · wiring check     │
│ Reads harness · writes 1 report  │
│ [Authorize] [Narrow] [Decline]   │
├──────────────────────────────────┤
│ Suggestion: DISP diff + ripple   │
│ [Review on desktop]              │
└──────────────────────────────────┘
```

## 6 · Phone

A casefile is already vertical: margins fold inline, viewers become snapshots with orbit on demand, and the default filter is **needs a hand** (unknowns, blockers, Inbox). At the bench, a photo or reading lands on an unknown row as staged, not evidence, until reviewed. A phone may authorize report-only operations; applying a diff or running a newly pinned tool says **Review on desktop**, because that decision needs the compare and its coverage.

## Patterns I reject

- Global graph and growth animation (gimmick #1): the rail is the graph's linear projection; `◄` links give a local depth-1 "why".
- Cursors and follow mode (#2); streaming thoughts (#3); semantic search without a reason (#4).
- Palette or layout engine before the verbs exist (#5), and user-composed layouts (Rerun/Foxglove, P22) outright: the casefile order is the layout.
- Assumption sliders (#6, CADAM): a changed assumption is a draft input plus an explicit run.
- Parallel agent panes (#7): candidates share one Parts sub-table, missing evidence first.
- Animation as state (#8), Altium's health score, suppressing blockers via "mark wrong", chat as home (Flux), and a permanent bottom timeline.

## Where I disagree with the others

**Argon.** Still the rejected three-pane layout plus a timeline. Its 240 px spine is the narrow BOM list the conventions research faults [H], and four tiled lenses is the cockpit the owner objected to. Glyph registers (`~ ASM`, `* MSR`) and copy like "fit ok", "Auth: NO UPGRADE" and "Guard: 0 auth upgrades" have the UI summarising authority. Every proposal as an ECO, with "Approve → Save r4" in one click, merges authorization, review and revision; one-thumb phone approval invites fatigue (P12 risk).

**Astra.** Pin, follow and return is the best detour mechanic here; Lift with `Esc` is my version. But a *question* as the saved unit contradicts Product Principle 3 (the project is the unit) and multiplies objects to find. In the Casefile a question is an unknown row with an address. A trail also hides the whole; the rail always shows every open unknown.

**Sol.** Closest on honesty (two-step approval, change orders only when released, missing evidence first). But one instrument plus "open beside" with presets is a tidier three-pane, the ripple is a side-panel list rather than something you watch cross the project, and two permanent time strips are chrome that only timed studies need.

## Risks

1. Reads as a report, not a tool. Mitigate with Lift, row actions and keyboard; test on FieldDeck with the owner first.
2. The order is honest only if the backend exposes dependencies; otherwise show "impact not assessed", never an invented order.
3. Long casefiles: collapse settled cells; the rail is the overview.
4. Viewer cost: one live context, lazy mounts, revision-labelled snapshots.
5. Cell-type sprawl: first build caps at seven (Goal, Requirements, Parts, Study, Board, Check, Release).

## Ranked first build

1. **FieldDeck read mode** from existing endpoints (`DigitalStudyPanel` becomes a Study cell), header counts, rail, "not assessed" distinct from zero.
2. **The ripple** on the real SC1635 → SC1975 swap: draft, differences only, `◄` causes, coverage, Run on draft, the 10-inch control blocked.
3. **Linked selection** with rail hits and "not linked"; a KiCanvas Board cell on the PCB inspection nest.
4. **Agent margin and suggestion cells** from `project_events` and the review store: two-step approval, base moved, resume.
5. **Lift and Follow run time** on the HS-3G-B PyBullet run.
6. **Phone** needs-a-hand filter and staged capture.
7. **Workshop casefiles**: akcli/kdif tool factory, then sealed evaluations.

Acceptance follows the signals research: time to a justified decision on FieldDeck and the unavailable SO-ARM100 servo, entered from Projects and from a direct BOM link; "need the voltage evidence" is a correct outcome [S].

[A]: ../design-research/ADVANCED_INTERFACE_PATTERNS_20261118.md
[H]: ../design-research/HARDWARE_TOOL_UI_CONVENTIONS_20261118.md
[S]: ../design-research/FRONTEND_GITHUB_SIGNALS_20261118.md
