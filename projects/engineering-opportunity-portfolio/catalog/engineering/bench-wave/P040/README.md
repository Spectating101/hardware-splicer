# P040 Aquarium automatic top-off unit

Automatic top-off logic traces cover dry reservoir, stuck-low demand, high cutoff, normal cycling and a restart with retained fault.

[Candidate CSV](trial.csv) · [Rejected CSV](rejected.csv) · [Editable dimensions and assumptions](../designs.json) · [Replay measurements](../results.json)

## Setup

The model uses 18 mL simulated increments, a 3,100 mL upper bound and an independent upper stop wired to block the pump. Allow up to nine consecutive pump ticks before latching off, and retain the fault across power cycling. The modeled upper sensor is asserted in the last 10 mL below the cap. Calibrate the volume from the measured reservoir geometry and worst actual pump flow, with an independent hardware cutoff before operating with livestock.

## Negative control

Extending the time limit to 23 steps for the same failed-low simulation reaches 3,264 mL. The candidate max is 3,098 mL across the five scenarios.

## Physical acceptance

Use a bench tank with a catch basin. Measure dose and cutoff under disconnected sensors, stuck low demand, overfill switch activation and power cycling.

The catalog models a 25-sale result of NT$ -22,755.00 at its proposed price. This is a planning estimate. The digital result applies to the geometry or synthetic operating assumptions in this trial.
