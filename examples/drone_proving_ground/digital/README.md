# HS-3G-B digital flight workshop

The requested outcome is **simulation and a 3D representative only**. Parts, fabrication, firmware flashing and bench tests are outside this task. This delivers the same HS-3G-B design as an inspectable assembly and a runnable parameterized flight study.

**Open [the offline 3D workshop](reference/VIEWER.html)** in a WebGL browser. Orbit and zoom, explode the assembly, replay a flight, switch scenarios and scrub the timeline. The HTML includes its geometry, recorded physics states and pinned Three.js library; it needs no server or network access. The [ZIP package](HS3G_B_DIGITAL.zip) contains the viewer, editable CAD, images, telemetry, receipts and a standalone physics runtime.

Static alternatives are [the assembly](reference/ASSEMBLY.png), [the exploded assembly](reference/EXPLODED.png), [the flight recording](reference/FLIGHT.gif) and [telemetry plots](reference/TELEMETRY.png). Editable exports are [STEP](reference/HS3G_B_ASSEMBLY.step), in millimetres, and [GLB](reference/HS3G_B_ASSEMBLY.glb), in metres.

## Revise it in the app

Choose **Start digital design** on the existing Splice UI home screen. The app creates a saved project from the verified baseline. Enter **Add 10 g of payload**, then choose **Run and save new revision**. A background job regenerates the native assembly, mass distribution, centre of mass, inertia, three physics cases, images and offline viewer. A separate verifier reimports the outputs and reconciles the telemetry before the project receives a new revision.

Use the revision selectors to compare mass, remaining mass allowance, tracking error, gust recovery and current estimates. The earlier geometry remains available; open its 3D view or download either revision's complete package. Reopening the project restores its history and any queued/running job. Cancellation and late results cannot replace a completed revision; concurrent edits produce a revision conflict.

Payload requests support `Add 10 g of payload`, `Remove 5 g of payload` and `Set payload to 10 g`, with a total payload between 0 and 50 g. The payload is a visible 14 × 12 × 8 mm representative box above the front top plate with assigned mass and an assumed rigid attachment. This changes the model rather than relabeling a replay. Other prose requests are rejected with supported examples. The separate controls set the mass limit (150–500 g) and gust force multiplier (0–3). A gust multiplier is a scale on the declared force, not a wind-speed estimate.

**Run completed**, **mass budget passed** and **simulation acceptance** are separate results. The compatible `requirements_met` flag combines the declared requirement checks with simulation acceptance; it establishes no physical performance. The current requirement set reports `verdict_basis: "mass_budget_only"`. The default 250 g limit is checked both at nominal mass and with an extra 5 g uncertainty allowance, with `margin_g` on each check. At 10 g payload that uncertainty check has only 0.1 g remaining. The small omitted inertia products must also remain below the declared 5% approximation threshold. Optional `min_hover_endurance_min` and `min_thrust_to_weight` requirements use simulation assessment metrics; without an assessment they report `not_evaluated`. An intact computation can retain failed checks and its artifacts.

Install the existing `drone-sim` extra for fresh generation. The API uses its own native environment when available, the project-cache native environment, or the interpreter selected by `HARDWARE_SPLICER_DIGITAL_PYTHON` (with `HARDWARE_SPLICER_CAD_PYTHON` as a fallback). Saved results remain viewable when the native runtime is unavailable; the app explains the setup needed to run a new revision. No model-service key is required.

The product API exposes `POST /v1/digital/projects`, `GET /v1/projects/{id}/digital`, and `POST /v1/projects/{id}/digital/runs`. A run accepts `base_revision`, `change_request`, optional structured `requirements`, and an optional UUID `request_id` for idempotent submission. Existing `/v1/jobs/{id}` routes provide status, cancellation and logs. Artifact downloads are scoped to immutable project/run ownership and checked against the saved SHA-256 manifest; generic snapshot writes cannot replace digital results.

## Run the simulation again

The ZIP is self-contained. After unpacking, install `REQUIREMENTS.txt` into a Python virtual environment and run:

```bash
python -m pip install -r REQUIREMENTS.txt
python RERUN.py --out /path/to/new/simulation-run
# Add --render for new camera images and a GIF.
```

This reruns native PyBullet physics from the packaged model, contract and motor table. It does not require CAD software or the rest of the repository. It writes a fresh CSV for each scenario and a new `SIMULATION.json`, without replacing the included model or viewer.

To regenerate the CAD, simulations, viewer and independent verification through the existing repository operator:

```bash
python -m pip install -e '.[drone-sim]'
PYTHONPATH=src python scripts/hs_workshop_operator.py \
  --case hs3g_drone_digital --out /path/to/new/operator-run --execute
```

Use a Python environment with working native CadQuery/PyBullet dependencies. The current local native environment is `.cache/hardware-splicer/digital-native-venv`. The operator stages the Git-tracked source, regenerates and verifies revision B, builds the digital assembly, runs the solver, and starts a separate artifact verifier. No external model service, login or API key is required. `--execute` means software execution only.

The verifier prints its full JSON result to stdout by default. To save a receipt, give an explicit path **outside** the package being verified:

```bash
python examples/drone_proving_ground/digital/verify_digital.py /path/to/digital-package \
  --design /path/to/revision-b-design --out /path/to/digital-verification.json
```

Verification never updates the package's `verification.json` or other files, including on failure. `--study` changes the verifier's exit criterion to artifact integrity; it does not change failed engineering checks into passes.

## The model and scenarios

The native frame is retained from the 137 mm HS-3G-B. Component locations, the 234.90 g mass roll-up and the sourced F1404 KV2900/GF3028-3 motor table parameterize this model. It does not substitute the legacy 27 g Crazyflie demonstration from `examples/drone_lab`.

Component meshes and blades are representative, rather than detailed vendor CAD. Mass proxies and the parallel-axis theorem produce the centre of mass and inertia tensor; the small omitted products of inertia are reported. PyBullet integrates gravity, individual rotor thrust and yaw torques, declared drag, a force gust and rigid ground contact at 240 Hz. A simulation position PID and SO(3) attitude PD controller operate at 60 Hz. The aircraft is never reset to its target position during the physics run. Rendering and browser playback use recorded states.

The nominal mission takes off, tracks a 0.45 m square, turns through 90 degrees, recovers from a declared gust and lands. A second run adds 5 g at the centre of mass while retaining the nominal controller mass. A third deliberately stops one motor, detects loss of control and descends to the ground. Its failure is an expected model response, not successful fault-tolerant flight.

These low-throttle missions operate below the first maker bench-table row: thrust and current there are extrapolated, not measured. Thrust-table current is the single motor-current model for mission telemetry and steady hover estimates. The battery model uses revision B's CNHL MiniStar 85704G, 850 mAh 4S 70C pack with XT60. Revision B's `../revision_b/inputs/candidate.json#part_overrides.battery` overrides `../inputs/parts.json`, supplying capacity and continuous C-rating while inheriting the four-cell count. Each value's source is recorded in `simulation-contract.json`. The OCV curve and 0.08 ohm pack resistance are assumptions in [simulation.json](simulation.json). Coulomb counting reduces state of charge, terminal voltage is OCV minus current times resistance, and the available RPM ceiling scales with terminal voltage relative to the assumed 16.8 V bench reference. No usable thrust remains after modeled capacity is exhausted.

Simulation acceptance gates minimum loaded voltage at 3.3 V/cell, peak modeled current against the sourced continuous C-rating (or reports `not_gated: no rated C in source data`), and full-throttle thrust-to-weight at the lower of the observed minimum voltage and voltage threshold at 2.0 or greater. A steady hover estimate integrates to 80% depth of discharge, stopping earlier if voltage or available thrust becomes insufficient; it is gated only when an endurance requirement is declared. Its assumptions and stopping reason accompany the result. The original design power-law estimate, 3.58 A and 11.4 min, is reported as `alternate_estimate` with signed differences (alternate minus simulation). Both models now use 850 mAh and 234.9 g for the default study: compared on that basis, the power-law estimate is about 0.7 A higher and 2.7 min shorter than the thrust-table estimate (about 2.9 A initially and 14.1 min to 80% depth of discharge). Exact differences accompany each simulation assessment. The power-law estimate retains its nominal-voltage basis and lacks sag correction; this comparison does not validate either model against hardware. The former approximately 14.2 min simulation-current extrapolation omitted the new voltage and state-of-charge integration.

Motor lag, yaw drag, linear drag and controller gains are assumptions. State feedback is ideal. Frame flexibility, CFD, sensor/GNSS/RF behavior, detailed battery chemistry and INAV firmware execution are outside this representative model. Estimated current, energy and endurance are not hardware measurements.

## Completion and evidence

Digital completion means the model and exports exist, the offline viewer works, actual native solver trajectories satisfy the stated nominal/payload requirements, the stopped-motor case loses control as expected, and independent checks reconcile the artifacts and full telemetry. Physical acquisition and testing are not digital completion blockers.

The separate verifier reimports STEP and GLB, checks the retained frame geometry and mass/inertia roll-up, recomputes scenario metrics from the CSVs, checks position/velocity and force/acceleration consistency, reruns a zero-thrust analytic gravity comparison, and reconciles viewer states with physics logs. New verification results bind their verdict to output hashes and are printed or saved outside the inspected package. The [committed verification receipt](reference/verification.json) was produced by the operator run that regenerated the reference package with the battery model and revised checks. Changed mass or a teleported trajectory is rejected.

The original [revision B engineering package](../revision_b/README.md) remains available, including its separate hardware and firmware research. Its physical scope does not redefine this digital-only objective. No physical performance or operational authority is claimed.

Three.js 0.160.1 is vendored with its MIT licence and byte identities in [vendor/provenance.json](vendor/provenance.json). The classical build is intentionally pinned to support direct-file opening without module-server requirements. PyBullet documentation and the geometric-control reference are linked in `simulation.json`; the controller here is a simplified simulation PD/PID, not the full paper's tracking controller or its stability guarantees.
