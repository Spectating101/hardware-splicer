# Practical drone build ecosystem for Hardware Splicer

This is a device-directed integration map, not a competitor-name list. Objective: **from a proposed quadcopter to sourced components, an assembled artifact and independently checked acceptance evidence.**

| Reusable project | Actual useful HS capability | Status / trap |
| --- | --- | --- |
| [Schematik](https://www.schematik.io/) | Reference product experience for AI → firmware, wiring and guided assembly; evaluate UI and exported artifacts | External hosted tool; not verified open-source or an API; public templates favor Arduino/ESP32/Pico low-voltage builds, not guaranteed PX4 aircraft powertrain support |
| [PX4 Autopilot](https://github.com/PX4/PX4-Autopilot) | Firmware, supported airframes, SITL flight-control regression | Official backend, not automatic motor/ESC fit validation |
| [QGroundControl](https://github.com/mavlink/qgroundcontrol) | PX4 firmware setup, motor mapping, sensor/RC calibration and flight logs | GUI setup, not BOM verification; real motors/props require supervised safety |
| [Pixhawk hardware](https://github.com/pixhawk/hardware) | Standardized electronics, flight controller hardware interfaces and reference design files | Individual revisions/connector footprints must be checked |
| [Holybro X500 V2 + Pixhawk 6C assembly](https://docs.px4.io/main/en/frames_multicopter/holybro_x500v2_pixhawk6c) | **Primary documented first-drone assembly reference** | Read actual hardware kit variant; battery/RC may be separate; power-module revision varies |
| [DroneSkeleton](https://github.com/colgecen/DroneSkeleton) | Full S500 OpenSCAD mechanical assembly; inspect clearances and frame/component space | Cloned on Optiplex at `15d139b`; OpenSCAD executable not installed, so no geometry export attempted; **not the same frame as Holybro X500 V2** |
| [DroneControllerUsing-STM32](https://github.com/IoT-App-Development-Company/DroneControllerUsing-STM32) | KiCad FC and ESC reference, BOM and CAD: practical verification negative control | Cloned at `a08820b`; KiCad 9.0.2 ERC found 364 violations and PCB DRC found 74; many missing libraries/footprint mismatches, but also actual hole-clearance violations. **Do not manufacture unreviewed** |
| [ArduPilot](https://github.com/ArduPilot/ardupilot) + [Mission Planner](https://github.com/ArduPilot/MissionPlanner) | Alternate flight firmware, setup and SITL path | Alternate to PX4, not interchangeable parameter files or flight-controller assumptions |
| [Crazyflie hardware](https://github.com/bitcraze/hardware) + [firmware](https://github.com/bitcraze/crazyflie-firmware) | Full-stack small drone reference and an alternate lower-mass practical pilot | Different architecture/scale; not a drop-in Pixhawk or X500 replacement |
| [KiCad](https://gitlab.com/kicad/code/kicad) | Schematic/PCB ERC, DRC, netlist and BOM checks | Already installed on Optiplex (`kicad-cli 9.0.2`); validation must interpret missing libraries versus real electrical/layout violations |
| [OpenSCAD](https://github.com/openscad/openscad) | Parametric frame export and STL/geometry reviews | Not installed on Optiplex at the time of the audit |

## Tested on Optiplex, 2026-10-20

The `DroneControllerUsing-STM32` clone was checked with the **installed KiCad CLI** against `KiCad/DroneController.kicad_sch` and `KiCad/DroneController.kicad_pcb`. Results: 364 ERC findings (including 138 missing symbol libraries, 98 off-grid endpoints, 68 pin-to-pin conflicts, 50 footprint-link findings) and 74 PCB DRC findings (49 library references, 18 footprint mismatches, two physical hole-clearance warnings/errors). Raw reports are under `/tmp/hs_drone_fc_erc.txt` and `/tmp/hs_drone_fc_drc.txt` on Optiplex. Validation exits were zero because CLI was not configured to treat violations as command failure. **They are findings, not successful validation.**

`DroneSkeleton` cloned and its complete assembled `drone.scad` was inspected. It includes prepositioned parts and parametric rail offsets. Geometry has not been rendered, collision-checked, or proven compatible with Pixhawk 6C.

## First-drone route: do not confuse design with assembly

**Start with an established Holybro X500 V2/Pixhawk 6C assembly**, not a custom-designed PCB and custom frame simultaneously. HS should read the X500 guide, identify exact supplied components and connector revisions, generate an ordered inventory/wiring/assembly sequence, help source only missing items, and capture evidence at each hold point. Use PX4 SITL for software behavior; propeller-removed bench checks require human authorization and do not imply flight readiness. A drone made from completely unrelated donor components remains a later more difficult challenge.

The machine-readable BOM, assembly sequence and unresolved interface gates are stored in [`x500_v2.json`](./x500_v2.json). It is a **reference specification**, not an actual purchase order, price quote, physical build or verified thrust/flight-time estimate.
