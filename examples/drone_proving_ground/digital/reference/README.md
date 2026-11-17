# HS-3G-B completed digital study

The requested deliverable is digital only. No parts or hardware are needed.

**Start with `VIEWER.html`: open it directly in a WebGL browser.** It contains its 3D library, model and recorded states, and makes no network requests. Orbit, zoom, explode the assembly, choose a scenario, play, pause and scrub. PNG/GIF views are included if WebGL is unavailable.

## Included results

- `HS3G_B_ASSEMBLY.step`: named editable assembly in millimetres; native retained frame and explicitly representative components.
- `HS3G_B_ASSEMBLY.glb`: coloured assembly in metres for ordinary 3D viewers.
- `ASSEMBLY.png`, `EXPLODED.png`, `FLIGHT.gif`: actual native PyBullet camera renders.
- `nominal.csv`, `mass_plus_5g.csv`, `motor_failure.csv`: full 240 Hz physics states, forces, targets, rotor RPMs and estimated current.
- `TELEMETRY.png`: paths, altitude, position error and motor outputs.
- `model.json`: geometry, mass proxies, centre of mass and inertia tensor.
- `SIMULATION.json`, `simulation-contract.json`, `verification.json`: assumptions, acceptance results and artifact identities.

## What was simulated

The existing 137 mm HS-3G-B design is the model, rather than the separate legacy Crazyflie demonstration. Its modeled mass is 234.90 g. Native frame geometry and the retained component layout define the mass distribution. The sourced F1404 KV2900/GF3028-3 table defines rotor force; behavior below its first row is extrapolated. PyBullet integrates the body under per-rotor thrust, yaw torque, gravity, drag, a gust and ground contact. The controller reads the simulated state; it never resets the aircraft to its target. Nominal and +5 g payload runs take off, track a square, turn, recover from a gust and land. The payload is located at the modeled centre of mass; the controller still uses nominal mass. The stopped-motor scenario deliberately loses control and reaches the ground; detecting that loss is the expected digital result.

This is a parameterized representative, not a physically calibrated twin. The assembly uses simplified electronics and blades. The full calculated inertia tensor is recorded; the small off-diagonal terms are omitted by the dynamics model. Motor lag, yaw torque, drag and gains are declared assumptions. State feedback is ideal. There is no sensor/RF, INAV SITL, frame-flexibility, CFD, battery-chemistry or thermal simulation. Estimated current and short-mission energy are not measured endurance. The separate design package retains its firmware research; this simulation does not execute or flash that firmware.

## Completion

Digital completion requires the native assembly exports, working offline viewer, full mission telemetry, nominal/payload acceptance, detected motor-loss descent, analytic gravity comparison and separate artifact verification. Physical purchasing, fabrication, calibration and bench work are outside the requested scope and are not digital completion blockers. No physical performance or permission is established.

Regenerate via the registered `hs3g_drone_digital` workshop case; see the source directory README for the command and dependencies.

## Run the physics from this folder or the ZIP

Install the small runtime into a virtual environment, then run:

```bash
python -m pip install -r REQUIREMENTS.txt
python RERUN.py --out /path/to/new/simulation-run
# Add --render for fresh camera PNG/GIF output.
```

This runs the solver again from the included model, contract and thrust table. It needs neither the full repository nor CadQuery, the browser viewer, a controller board or a network connection after installing the runtime. Use a new output directory. The original exported CAD and viewer remain unchanged.
