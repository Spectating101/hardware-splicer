# Robot arm as a salvaged project and as fabrication instrument

Two genuinely model-generated ChatGPT Codex candidate designs and native third-party simulations were executed on Linux Optiplex on October 20, 2026.

A 450 mm chain passed a PyBullet URDF and IK exercise but failed realistic stress-screen comparisons when placeholder actuator torque was reduced and structural self-weight was considered.

A subsequent 420 mm design deliberately substituted stronger, still imaginary geared actuator classes; the pessimistic static screen passed for shoulder, elbow and wrist while base yaw dynamics remained unknown. Its PyBullet generic IK error of 5.035 mm missed the 5 mm threshold and its five-step pick-place motions reported proxy collisions with the base. No approved real robot motion.

Two actual SolidCraft parametric finger inserts exported independent manifold STL, STEP and 3MF; real PartCAD BOM counted one of each. An independent actual PrusaSlicer run generated 40-layer G-code, 5.43 g material estimate, 17m59s estimated. No physical printer or gripper was present.

ALL motor, mass, print-mechanical properties and tolerances are labeled BENCHMARK_ASSUMPTION_ONLY; they are hypothetical scenario values, not an empirically estimated population average, purchased part or physical measurement.

See docs/integrations/ROBOTIC_ARM_SPLICING_OPERATOR_HANDOFF_2026-10-20.md for the practical manufacture-and-commission process. The self-contained ZIP provides both design iterations, assumed catalog, URDFs, PyBullet results, manufactured CAD/STL/3MF, real G-code, PartCAD BOM and source hashes.

Verdict: robotic arm design, kinematic simulation, and candidate printer files are real digital capabilities. The entire physical arm, collision-safe trajectory, actual actuator compatibility and robotic assembly remain unproven.
