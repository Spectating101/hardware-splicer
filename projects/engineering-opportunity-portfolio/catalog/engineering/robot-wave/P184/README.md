# P184 · Teaching robot odometry pod

Calibrate the rolling distance per encoder turn. Quantized pulses are replayed for a 2 m run under three assumed slip ratios. The calibration input is synthetic. The adverse run adds 3.5% slip.

[Full-scale layout](layout.svg) · [Model outputs](results.json) · [Editable design inputs](../designs.json)

| Modeled quantity | Result |
|---|---|
| calibrated error pct | smooth -0.1867, mat -0.5911, jointed -1.2132 |
| calibration input | assumed rolling circumference |
| geometric wheel error pct | smooth 0.8137, mat 0.4053, jointed -0.223 |
| high slip error pct | -3.5149 |

**Physical acceptance.** Tape a 2 m baseline, measure actual loaded circumference and record forward and reverse error on three floor finishes.
