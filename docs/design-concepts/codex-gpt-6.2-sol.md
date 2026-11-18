# Hardware Splicer — a revision workbench

## The project is a place you can rewind

Open a project into the last thing you were inspecting. The canvas owns most of the screen. Above it, a breadcrumb names the project, saved revision and selected object. Below it, a revision strip marks saved changes, runs and decisions. Choose a revision to replay its exact state, or choose two to inspect what changed. Ctrl/Cmd+K opens a searchable navigator for parts, requirements, findings, files and runs. Enter opens an inspector at the selection. Both can dock when a long task calls for it. The default view keeps the object and one selected question in focus.

Projects is home. Start from a goal, owned or salvaged units, or a reference study. Each creates the same kind of saved project. With no model yet, the canvas shows requirements and unresolved questions. The BOM is a first-class full-width view and the shared spine. A BOM line keeps its identity across revisions when the backend can map it. It links the design role, catalogue identity, specific owned stock or donor unit, and alternates. A suspected donor identification stays a sourced hypothesis. InvenTree contributes stock and catalogue records with their own provenance.

## Follow the question across tools

From a part, requirement or finding, open the relevant representation in place and keep a breadcrumb back. CAD covers the CadQuery Fielddeck, pen-plotter conversion and inspection nest. Electrical objects open KiCad schematics, footprints, board layers or native ERC/DRC findings. A harness opens its wiring diagram and checks. A run opens PyBullet flight playback and battery traces, or a plotter toolpath and its report. A repair intake opens hypotheses, the evidence that would distinguish them, and the backend safety gates. Teardown observations link to the sourced identities they support and the BOM lines where those units are being considered.

Every view shares an address with the revision, object and optional finding or run. Select a backed link to move between a BOM row, CAD body, board pad, graph cursor or evidence document. In sim replay, a single time cursor drives the pose and traces for that run. Unsupported links say “No mapped geometry” or the equivalent and still open the source artifact. Load viewers on demand. Preserve camera or layer state when returning, and synchronize compare cameras only where a shared frame is known. Use the original artifact and native report as the fallback for unsupported formats.

Runs carry engine version, inputs, outputs and hashes. Open an offline-rerunnable package from its run or revision, with a manifest and instructions. Sealed evaluations open as benchmark runs with protocol, sealed prediction digest, results and abstentions after scoring. Their scope stays attached to the benchmark.

## Turn a substitution into a walkable diff

From a BOM line, choose an alternate and assess it against a fixed base. Open the candidate beside the base with **Differences only** on by default. Start at the changed line and traverse the reported dependencies for fit, mounting, connections, electrical load, stock and downstream artifacts. A changed bezel can jump to an overlay, then to the check that supports its dimensions. A cable route with missing evidence points to the source or input needed. Show checked, stale and unknown items individually, and mark gaps in dependency coverage. Use side-by-side artifacts where correspondence is missing.

The revision header opens the backend’s blocker list for the selected action, such as fabrication or a repair step. Findings are listed, filterable and pinnable. A pin jumps to its exact revision and supported object or artifact anchor. The inspector shows the claim, backend authority verbatim, scope, source and run receipt. Conflicting checks stay visible with their scopes. When inputs change, show the older result under its original revision and surface the need for a new check. Saving a draft or approving a tool run changes the record of work. Authority changes require evidence and a new backend determination. If a scoped release exists, changing a released BOM line opens a change order with the affected scope, required checks and review history. The release remains addressable as its own revision.

## Agent work is reviewable while it happens

The revision strip shows project activity at the object it affects. Its inbox groups proposals, requests for input and failed runs by decision. Open an entry to see the agent or MCP caller, assigned question, base revision, proposed writes and run receipts. Select **Follow** for live updates on that task. Historical views and open approval cards stay pinned while newer events accumulate. Reconnect by fetching the current snapshot and replaying available events. Repository-side activity appears when an agent submits a project event or receipt.

Steer with a bounded request on a finding or part, such as “check display cable clearance using the imported drawing.” Narrow the scope, request evidence, or stop a supported run. Agents can return parallel proposals from the same base. The review card previews the exact operation, affected objects, required permission and expected revision. The owner can approve that operation, reject it or return it with a request. A moved base requires reassessment against the new revision and fresh approval. Approving execution and accepting a proposed revision are separate recorded decisions.

The GitHub tool factory brings discovered candidates into this same inbox. Show the source, commit, verified license, reviewed adapter, exact command, inputs and sandbox policy. Discovery and vetting can produce proposals. Execution requires a human-approved pin and adapter, runs without network access, and returns input and output hashes. Internal and MCP callers use the same backend gates. Friends get named identities once sign-in exists. Later, business teams can assign execution, change-order and release permissions to distinct roles.

## Phone

Open a shared link at the exact revision and finding. Use a single-column queue for blockers, decisions and work in progress. Tap a finding for the source or a cropped annotated preview. Read compare as a list of changes with before and after stacked. Owners can reply, assign a bounded follow-up, or approve a specific run after expanding its scope and provenance. If review depends on an artifact the phone cannot display legibly, save the review position for desktop. Load interactive 3D on demand.

## Three screens

Illustrative UI using the Fielddeck study. The states shown are example review states.

### Work in a saved revision

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Projects / Fielddeck / 7-inch base                         [Find ⌘K] [Inbox]           │
│ Assembly / Display module                                    [BOM] [Blockers]          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  CAD                                          [Section] [Explode] [Open source]        │
│                   __________________________                                           │
│                  /      display assembly   /|                                          │
│                 /_________________________/ |                                          │
│                 |                       ● | /     ● Cable clearance                    │
│                 |_________________________|/        Open finding ↗                     │
│                                                                                        │
│  Selected BOM line   DISPLAY                         [Alternates] [Inspect]            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Revisions    ● 7-inch base ───── ◇ candidate study                                    │
│                ↑ Viewing          ↑ Open differences     [Follow agent work]           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Assess a BOM alternate

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Fielddeck / DISPLAY / Assess 5-inch alternate                     [Open BOM]           │
│ Base  7-inch assembly       Target  5-inch candidate       [Differences only ✓]        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  CAD overlay / bezel and mount                          [Fit view] [Sources]           │
│               . . . . . . . . . . . .      · Base outline                              │
│               .   ┌────────────┐    .      ─ Candidate outline                         │
│               .   └────────────┘    .                                                  │
│               . . . . . . . . . . . .                                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Follow a dependency                                                                   │
│    DISPLAY ── Bezel and mount      Changed        [Jump to overlay]                    │
│            ├─ Cable clearance     Unknown        [Open evidence request]               │
│            └─ Power check         Needs rerun    [Open run inputs]                     │
│                                            [Inspect assessment] [Review draft]         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Review an agent operation

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Fielddeck / Inbox / Display study                       [Back to assembly]             │
│ Proposal from CAD agent via MCP                               [Open receipts]          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Save proposed 5-inch candidate                                                        │
│  Base revision     7-inch assembly             Current revision matches base           │
│  Preview           DISPLAY alternate and bezel artifacts         [Open diff]           │
│  Requested write   Save a draft revision                                               │
│  Open question     Cable clearance                             [Open finding]          │
│  Evidence          CadQuery outputs and input manifest          [View hashes]          │
│                                                                                        │
│  [Request evidence]              [Reject]                 [Approve draft save]         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Project activity                                                                      │
│  14:02  CAD agent submitted proposal          14:01  Digital fit run recorded          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

## Build first

Ship one end-to-end Fielddeck display review. Reuse the existing study/comparison UI, substitution assessment, findings and project event stream. Build the shared address, saved-revision strip, alternate-to-diff path and one review card for proposing the candidate. A useful acceptance check is whether the owner can open the saved base, jump from the alternate to its evidence, find an unresolved dependency, and reopen the exact decision from a phone. Also exercise a stale proposal after a competing save.

Stable cross-revision IDs and dependency coverage are the largest risks. Start with explicit mappings from the available manifests and let gaps show. Event noise can bury decisions. Group routine progress and keep pending decisions visible. Viewer load and embedded tool output are separate risks. Start with existing artifact previews and isolate external HTML. Add live agent controls and a second, dissimilar workflow with KiCad and wiring before generalizing the workbench.
