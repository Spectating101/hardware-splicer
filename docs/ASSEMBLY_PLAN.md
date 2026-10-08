# Build sequence (assembly plan)

A visual, ordered build sequence for one retained PCB revision. It answers "what goes where, and in what order" by
animating the parts onto the real board, one group at a time, instead of describing it in text.

It is a **view of retained bytes**. It carries no engineering authority, never rewrites a snapshot, revision, pin, review or
thread, and approves nothing: a part drawn in place is not a part that works, and a suggested check is not a result.

## Endpoints

| Route | Returns |
|-------|---------|
| `GET /v1/projects/{id}/revisions/{rev}/assembly-plan` | `{ok, available, plan}`; `available: false` with a reason when the revision keeps no board file |
| `GET /v1/projects/{id}/revisions/{rev}/assembly-plan/board.glb` | The bare board from `kicad-cli` (outline, copper, pads, silkscreen, mask; no component models). ETag, 304, cached apart from the full 3D model |

## What the plan holds

- **Board:** outline (`rectangle`, or `bounding_box_of_irregular_outline` when it is not one), size, thickness and where the
  thickness came from.
- **Parts:** reference, value, footprint, kind, side, position, rotation and the four corners of the outline in board
  coordinates; a pin 1 point for chips and connectors; pad positions and nets for connectors.
- **Steps:** conventional order, low parts before tall, front before back, test points and connectors late, mounting
  hardware last, then a closing "check before first power" step. Parts with the same footprint and value share a step.
- **Suggested checks:** continuity between two pads on the same net, offered only once both ends are in the board, and
  supply-versus-ground isolation at the end. They are things to try, not results.
- **Connections:** for each connector, every pin with its net and what else is on that net.

## What is estimated, and says so

- A part's **height** is not in a KiCad board file. It comes from a small table of typical package heights;
  `height_basis` names the row used, or says it is a default.
- A part's **outline** is its courtyard. A footprint without one falls back to its pad extent and `outline_basis` says so.
- The **order** is conventional, not the manufacturer's.
- The viewer draws **stand-in shapes** (boxes, discs, a header body with pins) and labels them as such. Real component
  models are not needed and not pretended.

## Checked against KiCad

Outlines are compared with KiCad's own courtyard geometry after KiCad itself has turned and flipped parts
(`tests/test_assembly_plan.py`, skipped where `pcbnew` cannot be imported). The comparison fails if it compares fewer than
all parts, and if the mirror or rotation maths is broken. KiCad's courtyard includes half the line width, so agreement is
within about 0.05 mm.

## Viewer

The **Assemble** tab in the evidence workspace: Play, previous and next, a slider, arrow keys and Space. The part group for
the current step descends onto an outline of its target position; earlier steps stay in place. A back-side step turns the
board over. With reduced motion, parts appear without flying. Groups of more than eight parts are named in the panel
instead of labelled on the board.

## Not yet

- Real component models (needs KiCad's `kicad-packages3d`, and most modules have none anyway).
- Off-board parts: a screen, a battery or a case. Only what is on the retained board is drawn.
- "Connect A to B" wire animation between modules: the connector pin tables and pad positions are the groundwork.
