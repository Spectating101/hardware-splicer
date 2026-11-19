# Five-device digital holdout

At HS commit `e6d428ac`, tracked-source searches found no prior cases for
MK3S, myCobot, PyGamer, OpenLog Artemis or MAX9744. We selected one design per
category. The operator chose the variants, candidate dimensions, joint angles,
board references and engineering questions. Design files were available during
case development. Commit the predictions before reading the answer sources.

* **Printer** — axis-aligned nominal envelopes at the specified orientation.
  Follow the MK3S slicer preset inheritance. Use the manufacturer's MK3S product
  specification or handbook for the published volume. Rotation, adhesion,
  supports, margins and successful printing are outside the claim.
* **Robot arm** — number the six movable joints in kinematic order and compare
  model limits with the manufacturer's 280 M5 joint-range table. Compare the
  payload question with its published rated payload. Collision, tool moment,
  trajectory, physical stops and operation are outside the claim.
* **Handheld** — compare card select, shared clock and button interface with
  Adafruit's PyGamer board definitions or guide.
* **Data logger** — compare the board's motion-sensor interface, card select
  and independent power controls with SparkFun's matching production firmware.
* **Audio amplifier** — compare input and output wiring with the MAX9744
  amplifier guide. An unidentified speaker is a missing-information control.

For each affirmative or negative claim, count opposite decisions as false
accepts or false rejects. Record unanswered known questions as abstentions.
Report an ambiguous revision or missing source as unscored. Keep the unmarked
speaker out of the known-answer denominator. Claims on one device are
correlated. The run measures source-assisted decisions using two existing HS
engines and new case adapters. It does not measure autonomous design discovery
or whole-device performance.
