# Native donor planning: passive switch boundary

Native donor modules extend the existing device planner, not the global module catalogue or the authority model.
An accepted mission's frozen `donor_read` is the only runtime context source. The ordinary device endpoint cannot
resolve donor IDs from an embedded contract, module map or agent claim.

This development tranche proceeds under the user's instruction to continue. The old handover's accepted live
trial reruns have not been completed and are not represented as passed by these software tests.

## Supported implementation

A candidate adds `{"id": "buttons", "module": "donor:radio:buttons"}` to `modules`, names that donor in
`donors_used`, and wires `buttons.KEY` and `buttons.GND` through normal `connections`. The example labels here
describe a schema, not a measured board. Donor IDs come from intake references, not a catalogue analogy.

`donor_device_plan.mission_donor_modules` projects the frozen facts into a private per-call module map. It never
updates the cached library or rereads mutable source files. The executor passes that context to the canonical
planner, engineering review and case exporter. The standalone catalogue/schema stay library-only; Python callers
can request the schema extension explicitly with `device_spec_json_schema(include_project_donors=True)`.

The first profile is deliberately narrow:

- One to four passive switch-to-ground outputs and exactly one ground reference.
- Switch `protocol` is accepted measured `switch_to_ground`, direction `output`, polarity `low`, and Vmax at least
  the proposed nominal 3.3 V. The declared `controller_pin` must resolve to the chosen controller's actual pin ID
  or printed label. `ground_reference` is measured, passive and has Vmax zero. No ground role is inferred from a name.
- ESP32-DevKitC V4 and Raspberry Pi Pico only. Reset, flash, strapping, USB-serial and input-only pins are refused.
  A signal connects directly to its declared unreserved GPIO, not a supply, another peripheral or another donor.
- No powered domains, arbitrary active outputs, motor drivers, unknown protocols or inherited L298N-style pinouts.
- Top-facing 2.54 mm male-header contacts, explicit measured contact tips, no below-board protrusions. Housings
  must fit inside the board outline and not overlap. Mounting strength and switch actuation mechanics are not modeled.

All donor contacts must be wired. In native mode every `donors_used` entry must have exactly one placed module;
duplicate physical blocks, missing intake membership and mixed implemented/tracking-only donor lists are refused.
A repair cannot remove the native module while keeping its donor as a tracking reference.

Legacy P4 specs containing only `donors_used` remain tracking-only for compatibility. Their historical READY state
does not retroactively acquire donor implementation. Only an actual native plan has the `donor_scope` marker.

## Geometry in the existing contract

`InterfaceContract` gains optional `planner_geometry: EvidenceValue`. It round-trips through the existing evidence
contract reader/writer. When absent, it is omitted from canonical serialization, preserving existing contract bytes.
It does not affect the electrical `recompute_status` rule or grant firmware/power authority.

Its value has exactly these keys (illustrative coordinates only):

```json
{
  "pcb_mm": {"x": 20, "y": 12, "z": 1.6},
  "above_board_mm": 5,
  "below_board_mm": 0,
  "connector": "male_header_2_54",
  "contacts": [
    {"contact_id": "J1.1", "x_mm": 2.54, "y_mm": 2.54, "z_mm": 4.6},
    {"contact_id": "J1.2", "x_mm": 5.08, "y_mm": 2.54, "z_mm": 4.6}
  ]
}
```

Coordinates use the board's own frame: x/y in the top-view rectangle, z upward from its underside. The z tip must
be between PCB thickness and PCB thickness plus the measured above-board extent. Contact identities link geometry
to the exact contract signals, never to similarly named catalogue pins. Dimensions are finite and bounded; board
sizes are 0.5–300 mm and above-board extent 0–100 mm. Explicit units other than mm are refused. Existing jumper
housing height, bend allowance, printing and mounting assumptions remain assumptions, not new measurements.

Geometry is frozen with `person_measurement` grade only for accepted measured values whose evidence IDs all resolve
to matching, unique, passing, non-simulated dimensional envelopes for this project and donor. Signal/protocol facts
continue to require matching electrical envelopes. Both lookups use the same loaded snapshot. No new evidence
store, contract import endpoint or geometry-promotion route is added; the owning reviewed contract workflow remains
responsible for these records. Mission-supplied electrical feedback does not create geometry or promote the contract.

## Deliverables and readiness

Native planning produces real module boxes, contact coordinates, wiring curves, topology findings, assembly-step
proposals and case geometry. Engineering coverage includes the donor as a separate module, with missing current,
thermal, input configuration, debounce and contact-life information explicitly unassessed.

The deterministic mission package retains `donor_read.json`, a `donor_scope.json` limitation record, the actual
native plan and generated enclosure STL/OpenSCAD. Donor firmware is **blocked**, not silently replaced by a
library-only sketch. Application generation/runtime requests record a refusal. Package generation still follows
the existing READY contract, which can contain explicitly blocked deliverables; READY is not physical validation.

Wiring validation is topology-only for declared nominal 3.3 V passive contacts. Rail tolerance, leakage, transient
limits, pull-up implementation, debounce and actual device function are not established. No GPIO is configured,
firmware flashed, switch actuated, enclosure printed or board powered by this code.

## Trust and verification

The existing persistence trust boundary remains: hashes verify retained identity/integrity, not instrument truth,
raw-byte attestation, authenticated review or accurate transcription. Snapshot-PUT and filesystem writers are
trusted; someone with those privileges can forge evidence. This extension does not solve that broader boundary.

Regression tests use synthetic temporary project/measurement fixtures, not real bench observations. They exercise
the actual planner, review, case exporter, mission executor, HTTP routes and deterministic ZIP builder without
mocking their output. Tests reject missing/forged geometry, reference-only protocols, active supplies, bad GPIOs,
overlaps, wrong units, source replacement after acceptance, duplicate donors, dropped modules and embedded contexts.

`physical_correctness` stays `UNPROVEN`; mission firmware/power authorization stays false. See the dated status
handover for exact test results and verification that was not performed.
