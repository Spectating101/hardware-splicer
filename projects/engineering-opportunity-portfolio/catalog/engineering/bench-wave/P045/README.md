# P045 Auto-traverse pickup coil winder

Discrete pickup winder command model delivers 6,000 turns with 0.08–0.09 mm pitch and 53 layer reversals.

[Candidate CSV](trial.csv) · [Rejected CSV](rejected.csv) · [Editable dimensions and assumptions](../designs.json) · [Replay measurements](../results.json)

## Setup

Use an encoder index to count the spindle and linearly phase a stepper-driven guide once per revolution. The trial assumes a 10 mm winding window, 0.01 mm linear increments, 0.075 mm measured wire diameter and a 0.5 mm edge reserve. It models commanded positions across 6,000 turns. Establish tension and verify acceleration, spindle guarding and backlash on physical hardware before running the winding program.

## Negative control

Increasing the turns per traverse from 112 to 150 forces 0.06 mm spacing. After layer one, neighboring turns would overlap for the assumed wire diameter.

## Physical acceptance

Use sample bobbins and sacrificial wire. Measure turn count, edge buildup and tension after repeated reversals.

The catalog models a 25-sale result of NT$ 4,325.00 at its proposed price. This is a planning estimate. The digital result applies to the geometry or synthetic operating assumptions in this trial.
