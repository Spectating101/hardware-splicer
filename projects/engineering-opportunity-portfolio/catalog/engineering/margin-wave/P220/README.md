# P220 Large-ball desktop USB pointer

Large-ball pointer housing and forty deterministic selection-and-drag scripts. A deadband change filters stationary jitter in all traces.

[Candidate SVG](trial.svg) · [Rejected SVG](rejected.svg) · [Candidate trace](trial.csv) · [Rejected trace](rejected.csv) · [Editable inputs](../designs.json) · [Replay evidence](../results.json)

## Setup

Use a wired USB donor controller and an assumed 55 mm ball. Support and clean the ball through a removable 65 mm ring with smooth edges. The draw identifies 22 mm buttons and 30 mm button edge clearance. Sensor, PCB fasteners and connector dimensions need measurement. The candidate trace uses 9 pixels per sensor count, a 0.35 count deadband and scripted target movements with jitter. It checks firmware behavior against precise synthetic events and uses no human performance data.

## Negative control

A 0.10 count deadband admits the synthetic rest noise and causes a 2.49 px jump on a single rest sample. The candidate filters the same noise to zero while passing a short drag.

## Physical acceptance

Run target selections with an intended user at the real display scale. Log misses, accidental presses and drag releases, and measure the force required both before and after cleaning.

The catalog models a 25-sale result of NT$ -1,787.50 at its proposed price. The result depends on catalog allowances and assumed sales.
