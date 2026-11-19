# P039 USB parts-counting and kit-check scale

Interval-based parts counter distinguishes all 18–22 part lots in 135 synthetic mass and sensor-corner scenarios.

[Candidate CSV](trial.csv) · [Rejected CSV](rejected.csv) · [Editable dimensions and assumptions](../designs.json) · [Replay measurements](../results.json)

## Setup

Tare with the working 37.5 g pan, sample a known part count from representative supplier lots and update the observed minimum and maximum part mass. This trial uses 0.812 ± 0.010 g per part and ±0.040 g aggregate reading uncertainty. The algorithm reports every integer count consistent with the measured mass interval and only accepts a kit when the configured count is the sole candidate.

## Negative control

Raising error to ±0.240 g creates 10 ambiguous samples in the factorial replay. Mixed part types that share mass can remain ambiguous even with a better sensor.

## Physical acceptance

Weigh known lots of 18–22 parts across three actual supplier lots, including count-19 samples, tare resets and several tray positions.

The catalog models a 25-sale result of NT$ 2,035.00 at its proposed price. This is a planning estimate. The digital result applies to the geometry or synthetic operating assumptions in this trial.
