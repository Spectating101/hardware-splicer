# P048 Registration frame for small PCB stencils

Hinged stencil frame holds four witness apertures within 0.064 mm of their registered pads across tolerance corners.

[Candidate SVG](trial.svg) · [Rejected SVG](rejected.svg) · [Editable dimensions](../designs.json) · [Replay results](../results.json)

## Setup

Use two rigid board-edge datums and one spring stop for the assumed 70 × 45 mm coupon. Fix the foil frame pivot 18 mm behind its nearby board edge. Adjust the stencil carrier in its closed position, with the stencil touching the coupon plane. The check evaluates the exported geometry under ±0.03 mm registration play per axis and ±0.04° about the drawn registration center. Cutting artwork and paste behavior depend on the actual board and foil.

## Negative control

Shifting the stencil offset 0.23 mm increases worst displacement from 0.063 to 0.282 mm. The aperture extends beyond the land, beyond the modeled limit of 0.08 mm.

## Physical acceptance

Load and remove dry coupons first. Inspect movement at 5° lift and whether the foil releases without dragging. Print and clean ten samples using the intended paste and measure relative position to the smallest pads.

The catalog models a 25-sale result of NT$ -2,715.00 at its proposed price. Use the fixture trial and physical acceptance costs to decide whether reuse is economical for the actual job.
