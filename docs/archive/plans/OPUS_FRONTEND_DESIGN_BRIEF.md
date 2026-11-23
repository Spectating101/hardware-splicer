# Opus frontend design brief

Claude Opus 5.5 authored the proposal below on 2026-11-18 from a repository summary. Projects already opens by default. The workflows below are design targets. For digital-only trials, an imported drawing or existing measurement record can supply dimensional evidence.

# Hardware Splicer: app-wide product direction

## Where I disagree with the current app
The app is organised around studies: a design library of four registered studies plus separate workspaces. Users don't arrive with a study. They arrive with **a goal** ("I need an A4 pen plotter") or **a pile of parts** ("I have two printer steppers and a controller board"). The project should be the centre of the app, and studies should be one way to start a project. The cyberdeck-specific UI should not shape the app.

## Entry flows (all three lead to the same screen)
1. **Start from a goal.** The user enters a goal and requirements, and the app shows matching registered studies as starting points.
2. **Start from parts.** The user lists the parts they own (salvaged or bought). Each one is recorded as a specific unit they own, separate from the catalogue part it might be, as InvenTree separates a stock item from a part.
3. **Start from a reference study.** This replaces the design library as a home tab and is a secondary option.

**Projects** stays the home screen.

## Main screen: the project bench
- **Left: parts and requirements.** Each row shows where the part came from (owned, salvaged, catalogue), what is known about it (measured, from a datasheet, unknown), and any substitutions offered.
- **Centre: the design view.** It shows the geometry, artifacts and measurements from the current digital run. A "Compare" toggle shows two revisions side by side, the way Onshape and SimScale handle compare. Compare is a mode of this view, not a separate screen.
- **Right: evidence.** It lists each engineering claim with the authority level the backend returned and the evidence it rests on. The release assessment sits at the bottom as a list of **blockers**, never as a "ready" badge.

Selecting a part highlights its geometry only where the backend already provides that link. Where it doesn't, the row is labelled "not linked", not hidden. Use InteractiveHtmlBom's linked selection as the pattern, and apply it honestly.

## Example: a pen plotter from salvaged steppers
1. The owner starts from parts and lists two salvaged NEMA17 steppers with an unknown rated current.
2. The app matches them to the registered pen-plotter study.
3. The left pane flags the motor torque as **unknown**. The substitutions API offers a catalogue motor.
4. The owner measures the motor flange and enters the measurement. A new run persists it.
5. Compare shows revision 1 against revision 2: the gantry fit is now based on a measurement instead of an assumption.
6. Release assessment still lists "motor torque unverified" as a blocker.

Nothing in this flow is upgraded without evidence.

## Keep and move
| Existing UI | Action |
|---|---|
| Projects list | Keep as home |
| Design library | Move into New project as the "Start from a reference study" picker |
| DigitalStudyPanel | Becomes the centre pane of the bench |
| Revision comparison | Becomes the Compare toggle in the centre pane |
| CAD and workcell references | Move into a collapsible reference drawer |
| FieldDeckDisplayComparison | Show it only inside that study's evidence pane |
| circuit-ai-frontend | Keep it separate and link out to it; plan to add it later as an Electrical tab in the bench |

## First buildable slice (frontend only)
Build the two main entry options (goal and parts) and the bench, for the **four registered studies only**:
- Intake from the existing parts and requirements endpoints
- The parts pane, with the owned-unit vs catalogue-part distinction
- The centre pane from existing runs
- The Compare toggle
- An evidence pane that shows exactly what the backend returns

## What must be true for the flow to work
- The intake APIs return where each part came from and what is known about it per item. If they don't, the UI shows "unknown" and does not guess.
- Every claim's authority label comes from the backend. The UI never calculates a promotion and never shows "build-ready".
- Each run is tied to a project revision, so Compare always compares two real revisions.
- There is a mapping from a project to its registered study. If a project has no study, the bench shows an empty design pane with "no reference study yet". It must not show fake geometry.
- Any link between a part and the geometry that isn't backed by data is shown as "not linked".

## Not promised
The app does not generate CAD automatically, does not offer linked selection everywhere, and cannot re-simulate individual parts. The design and the copy must not suggest otherwise.
