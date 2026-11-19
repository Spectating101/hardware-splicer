# P187 · Machine vision calibration board

Detect a printed-scale ChArUco pattern after perspective distortion. OpenCV renders a 4x4_50 pattern, reads the emitted image and checks the corner identities after a perspective warp. A smaller print scale yields an incorrect pitch despite remaining detectable.

[Full-scale layout](layout.svg) · [Model outputs](results.json) · [Editable design inputs](../designs.json)

| Modeled quantity | Result |
|---|---|
| clean corners | 24 |
| warped corners | 24 |
| pitch mm | 24 |
| max warp residual px | 0.243 |
| scaled 97pct pitch mm | 23.296 |
| expected corners | 24 |

**Physical acceptance.** Measure pitch at five points per axis and both diagonal flatness readings, recording gauge uncertainty.

[OpenCV ChArUco board documentation](https://docs.opencv.org/4.12.0/df/d4a/tutorial_charuco_detection.html)
