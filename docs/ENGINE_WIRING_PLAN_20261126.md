# Engine wiring plan: connect what HS already has before building anything new (2026-11-26)

**Superseded the same day by `docs/CAPABILITY_CONSOLIDATION.md`.** The counts below came from a map that matched modules
by bare file name; resolved by full import path, 453 modules are shipped and none is reached by nothing. Device review,
part lookup, battery runtime and propeller data are now toolbelt tools; §5 of the consolidation page lists what is next.

Read `docs/CAPABILITY_MAP.md` (generated) first. On 2026-11-26 the engine toolbelt reached 21 of HS's 607 modules
(transitively); the REST product API reached 321; 262 engineering modules (65,000 lines) were reached by no entry point.
The benchmark's "missing features" were largely features HS had but the engine did not call.

## 1. Overlaps with what was built on 2026-11-26: read both, then merge, replace or keep

| Built on 2026-11-26 | Existing module (its own description) | Decision needed |
|---|---|---|
| `objective_project` | `machine_project` ("semantic spine", 80 tests), `engineering_status` ("one coherent engineering status and ranked next-action surface") | Should the objective ledger sit on the machine project spine? |
| `engineering_toolbelt` | `sdk` ("programmatic agent SDK: compose, salvage, verify", 23 tests), `workshop_operator` ("composing existing vetted engineering capabilities") | Should the toolbelt wrap the SDK instead of parallel code? |
| `engine_benchmark` | `robot_guidance_benchmark` ("whether HS can guide a real robot build") | Merge the scoring |
| `projects/hs-rover-salvage-a` package | `device_lab` ("a lab pack ... parts on the desk to a device that runs"), `mission_delivery` | Generate packages through these |

## 2. Wire into the engine: existing capabilities that close benchmark gaps

| Benchmark gap | Existing module(s) | Native venv needed |
|---|---|---|
| Printed-part strength | `mechanical_cad_fem`, `mechanical_quadratic_fem`, `mechanical_fem_crosscheck`, `mechanical_fastener_bearing` | Gmsh, scikit-fem |
| Thermal, RF, power, printing review | `device_engineering` | no |
| Arm design, URDF, kinematics | `robot_arm_design`, `robot_arm_kinematics`, `robot_model_import`, `robotics_simulation` | PyBullet for kinematics |
| Pump and motor drive | `circuit_synthesis.motor_driver_planner` | no |
| Battery power path | `circuit_synthesis.battery_power_planner`, `battery_runtime` | no |
| Propeller thrust from measured data | `prop_static` (UIUC database) | no |
| Firmware starters | `firmware_scaffold`, `integrations.esphome_export`, `device_application` | no |
| Identify salvaged chips | `part_lookup` (KiCad's symbol library), `board_vision_salvage`, `donor_capture` | no |
| Design from owned salvage | `inventory_topology`, `salvage_intelligence` | no |
| Build order, change impact, remote physical tests | `assembly_plan`, `change_impact`, `remote_physical_validation` | no |

Each is wired only after its own tests pass, including the ones skipped without the native venv (38 skipped on
2026-11-26), and the benchmark is re-run after each.

## 3. Still missing after wiring

Underwater checks (buoyancy, thrust against drag, pressure housing), a battery pack built from tested salvaged cells,
linear-axis sizing, sizing from a salvaged motor's measured values, and a general enclosure tool.

## 4. Orphans

262 engineering modules reached by no entry point: each is a library used by scripts, a research spike, or dead code.
Sort them with the map's area tables before deleting or reviving any.
