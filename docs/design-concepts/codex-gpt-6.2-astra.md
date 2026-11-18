# Hardware Splicer · Follow the change

Open a project and resume the engineering question you left on the bench. For the pen plotter it might be “Will the donor motor fit the X carriage?” The carriage drawing fills the screen at the mounting face. The donor’s hole spacing reads **unknown** beside the model dimension. Those values belong together even when there is evidence for only one. This is the everyday view. The project remembers the question, revision, selection and camera so a trip through a datasheet ends back at the same hole.

## Moving through a project

Projects is home. Start with a goal and requirements, a tray of owned units, or a registered reference study. Each creates a project with a saved starting revision. A project without geometry opens on its requirements or parts. Press **/** for the assembly navigator or search by BOM line, requirement, finding or refdes. Selecting one gives it the working surface. A short trail above it records the relationships traversed. A temporary inspector opens the source for any step. Back retraces the trail.

The BOM gives each design position a stable address. M1 links to a particular salvaged unit, its proposed catalogue identity and any catalogue alternates. Keep those records distinct. From a teardown photo, follow a marking to the cited identity source, then to the InvenTree material record and the positions using it. A repair question can open on competing diagnoses instead. A safety gate interrupts the proposed diagnostic step in place and exposes its reason and missing evidence. All workshop actions concern digital records and runs.

### 1 · The working bench

Illustrative plotter session. New agent results arrive along the revision strip without moving the camera.

```text
┌─ Projects / Ender 3 plotter / r4 ───────────────────────────── [Find part or claim /] ┐
│ Will the donor motor fit the X carriage?                            [Change question] │
│ M1 · X motor  ›  mounting pattern  ›  carriage drawing                         [Back] │
├──────────────────────────────────────────────────────────────────────────────────────┤
│          o ┄┄┄┄┄┄┄┄ o           CadQuery · carriage · front                          │
│          ┆    ◯     ┆           ① Hole centres in this model                         │
│          o ┄┄┄┄┄┄┄┄ o           Donor hole centres     ? unknown                     │
│                                 [Open source drawing]    [Compare alternate]         │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Findings   ① Mounting pattern [Locate]       Rated current    ? unknown · unlinked   │
│ r3 ─── r4 viewing ──┬── donor drawing search · Codex · last receipt 10:42            │
│                     └── catalogue alternate · Claude · proposal available            │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Inspecting a consequence

Choose an alternate on M1 to fork a draft. Unroll the recorded dependency paths touched by that edit. Follow the driver-limit path to see the previous motor evidence, the proposed value with its source, and the check that consumes it. An unlinked record ends the path with a request for the missing mapping. Show gaps in dependency coverage alongside known impacts.

Compare two saved revisions or preview a labelled draft against its base. Start with differences only. Expand a row to recover unchanged context. Old results stay bound to their inputs. For a released BOM line, route the diff through a change order recording affected positions, reviewer and disposition while preserving the released revision.

### 2 · Alternate under review

```text
┌─ Ender 3 plotter / M1 ─────────────────────────── Base r4 ⇢ Target draft A ──────────┐
│ Differences only [on]                        [Scrub registered views]     [All rows] │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ BOM line        r4                          Draft A                                  │
│ M1              donor unit D17              catalogue candidate C2                   │
│ Rated current   ? unknown                   candidate datasheet §3          [Source] │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ M1 ─┬─ mount pattern ── carriage fit         CAD result from r4            [Inspect] │
│     ├─ winding current ─ driver limit        target check outstanding      [Inspect] │
│     └─ lead order ───── harness J2           ? candidate pinout            [Request] │
│ Selected path   J2 / lead order / wiring check             Board location unlinked   │
│ [Keep r4]     [Request wiring evidence]     [Review draft changes]                   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Each finding has an address. Open it from a sortable list or a numbered pin to see the same claim, backend authority label verbatim, input revision, producing engine and source excerpt. Jump to the artifact and its digest, then back to the pin. Fabrication assessment opens on the backend blocker list. Distinguish an absent assessment from one reporting zero blockers. Accepting an edit records a design decision. Only the backend can revise claim authority on the strength of evidence.

## One surface, several instruments

The artifact determines the controls. Inspect a CadQuery section through the Fielddeck enclosure, plotter mount or PCB inspection nest. On a KiCad board, select a footprint to reach its BOM line, wiring checks and DRC findings. Open ERC findings in schematic coordinates. In a PyBullet drone run, scrub the trajectory and battery trace together by recorded simulation time. Link selections only through supplied object IDs, coordinates or timestamps. Unlocated findings stay in the list. Lock comparison cameras only with known registration. Otherwise show labelled independent views. Download the offline-rerunnable package from the revision’s run beside its inputs and manifest.

## Directing the agents

Give each agent a question, base revision, allowed inputs and deliverable. Human actions and external MCP calls share the project history. Each receipt updates the strip with actor, operation, time and artifact. Open it to narrow the next step or stop pending work. If reporting stops, retain the last receipt and mark current activity unknown. Authorizing a scoped run and accepting its proposed diff are separate decisions. If another task advances the base, require a fresh comparison before applying the proposal.

### 3 · Authorizing the next operation

```text
┌─ Ender 3 plotter / Agent work / Draft A ─────────────────────────────────────────────┐
│ Claude    r4 → draft A   Proposed M1 catalogue change                 [Inspect diff] │
│ Codex     r4             Drawing search · last receipt 10:42           [See receipt] │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Decision requested     Run wiring check on draft A                                   │
│ Inputs                 Draft A harness + candidate part record         [View hashes] │
│ Allowed output         One diagnostic report attached to draft A                     │
│ Open question          Candidate pinout source missing                               │
│ Expected coverage      Report documented connections and unresolved leads            │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [Authorize this run]      [Return with narrower scope]      [Decline]                │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Tool discovery also starts with a question, such as comparing PCB revisions. The proposal shows the normalized GitHub discovery record, licence, exact commit and reviewed adapter. An unfamiliar commit waits for human adapter review. For an approved tool such as kdif, show the requested inputs before execution, then attach the no-network sandbox receipt, output hashes and native diff. For sealed evaluations, show the protocol, engine version, aggregate outcomes and abstentions while keeping held-out answers sealed during work. The result belongs to the evaluated capability. Project findings retain their own evidence requirements.

## Phone use

Open a deep link to M1 with revision and question intact. The source crop and one finding fill the screen. Swipe between findings or use labelled Previous and Next buttons. Tap a pin for its evidence sheet. Agent requests queue beneath the current question. Expand the exact diff or run scope before approval. Resume the same view on desktop when a footprint overlay needs more room.

## First cut

Build the plotter journey on Projects, saved revisions, DigitalStudyPanel and existing evidence records. Ship the BOM finder, restorable trail, source jump and differences-only revision comparison first. Test whether the owner can open a motor’s source and return to the original mount in two actions. Sparse mappings are the main risk. Test an unlinked finding as deliberately as a linked one. Show the original artifact when a viewer lacks anchors.

Then add draft impact paths and agent receipts. Expand one dependency path at a time, with a count of remaining paths, to keep dense assemblies legible. Exercise two proposals against the same base before enabling acceptance. Add collaborator identities and permissions when friends get sign-in. Revision-bound decisions can carry change orders and formal business review later.
