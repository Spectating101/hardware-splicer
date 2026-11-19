# P002 · Ender-3 plotter conversion files

The [frozen HS design release](design-release.zip) contains the editable mount, manufacturer interface reference and notices, assembly models, a 100 × 80 mm demonstration path and the frozen verifier. It addresses the original Ender-3 carriage with 14 mm mounting pitch.

The [release replay](trial.json) checked the supplied geometry and command stream. All 48 checks passed. In a temporary copy, adding a single out-of-envelope command made the verifier flag the command-to-trajectory comparison and five related checks. All motion in this study was simulated.

Measure the donor's mount and tool offset. Check actual pen pressure, lift and drawn registration on scrap paper before relying on the conversion. The archive's BOM and design are for the named donor revision.

[Replay script for both source releases](../verify.py)

