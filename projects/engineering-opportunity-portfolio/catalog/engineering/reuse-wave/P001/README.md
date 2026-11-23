# P001 · PCB inspection dock files

One common dock accepts carriers for OpenLog Artemis, MAX9744, PyGamer and Feather M4 Express. The [frozen HS design release](design-release.zip) includes the editable geometry, per-board STEP and STL, four assembly models, upstream notices and instructions.

The new [fit replay](trial.json) reopened the solids and compared the carrier mesh volume with its STEP solid. Each correctly seated assembly had zero modeled interference to five decimal places. Rotating the fully seated carrier 180° about the dock's vertical axis created 71.333 mm³ of intersection on all four. Support contact on the bare boards ranged from 32.223 to 46.841 mm². This control uses full seating depth.

Print the keyed dock and at least two carriers, measure repeatable seating and check the underside components of the intended populated boards. The financial offer is a download. Whether buyers pay for these revisions is a separate question.

[Replay script for both source releases](../verify.py)

