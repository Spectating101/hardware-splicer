# Sweep v2.2 digital holdout

HS baseline is `0f211aa5224438b3d19dff18fc30c96a99f3f2cf`. A tracked-tree
search found no prior references to davidphilipbarr, Ferris Sweep, Sweepv2 or
half-swept. The public discovery snippet identified a compatibility table and
another variant. We selected v2.2 and withheld its table row, build guide and
firmware from the prediction program. This is a public, human-selected case.

Inputs are the native PCB and five independent KiSwitch footprint files, pinned
in `inputs.json`. The operator supplied the board variant, component families,
controller name and direct-wired keyboard hypothesis. Record both the existing HS
key detector and the new probe. The probe reconstructs switch-to-controller pad
assignments from PCB net declarations. For direct PCB compatibility it compares
the centered footprint at four quarter turns. Both unpolarized contacts must land
on plated switch contacts. A positive also requires the board footprint to name
the series and the donor locating-hole centers to agree. Different recommended
drill diameters alone cannot establish a physical interference fit. The comparison
covers nominal PCB support. Plate, cap, firmware, solder joints, and donor
condition are outside that decision.

Freeze the predictions in git before retrieving the project README. Use the
upstream v2.2 support table as the answer for each named family. A grouped
matrix column counts as one independent published label even when it covers two
candidate footprints. Score false accepts, false rejects, correct decisions,
and abstentions on known answers. Keep an unknown or missing oracle label
unscored. The unmarked donor is a separate missing-information control whose
physical identity is unknown. Use the upstream build description to check the
overall key count. Preserve first-run results after any repairs.
