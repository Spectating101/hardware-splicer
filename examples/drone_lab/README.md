# HS Drone Lab: fly now, build the microdrone next

This is a **working drone simulator and a concrete DIY airframe**. It replaces the "pass N/N repairs" direction with an actual product you can control. The simulator was exercised on the connected Linux Optiplex: a Crazyflie dynamics model climbed to ~0.45 m with individual motor RPMs and reacted to a forward command. Its 14-second square-flight recording climbed to **0.427 m** and generated a **56-frame GIF** and **672 rows of position, attitude, motor RPM and target telemetry**.

## Fly it on your computer

The aircraft already runs on the connected Optiplex in an isolated directory:

`~/chatgpt-work/hs-drone-lab-20261104/`

Open **http://127.0.0.1:8765** on that same computer while the cockpit process is running. This is a local-only server; it never connects to a physical flight controller.

- **T** take off; **W A S D** move; **R / F** ascend/descend; **Q / E** yaw
- **Space** hover; **M** fly an autonomous square in simulation; **L** land; **X** reset
- The web page renders the upstream PyBullet camera and polls actual position, motor outputs and flight mode. It does not fake motion or implement custom aircraft physics.

Restart from this repository on another Linux machine:

```bash
bash examples/drone_lab/launch_drone_lab.sh serve
# Then open http://127.0.0.1:8765 on that machine.
```

Or render a GIF and CSV that you can inspect/share **without the web cockpit**:

```bash
bash examples/drone_lab/launch_drone_lab.sh demo
# Outputs: ~/.cache/hs-drone-lab/results/real_pybullet_drone_flight.gif
#          ~/.cache/hs-drone-lab/results/flight_telemetry.csv
#          ~/.cache/hs-drone-lab/results/flight_summary.json
```

The launcher downloads the **existing** [learnsyslab/gym-pybullet-drones](https://github.com/learnsyslab/gym-pybullet-drones) at pinned commit `15c426c85ac8e7a5db66d8b100f48858133357f6`, uses its `CtrlAviary`, `DSLPIDControl` and Crazyflie physics model, and installs dependencies into an isolated `uv` Python 3.11 environment. It doesn't alter host system Python packages and doesn't write firmware. Python 3.11 is used specifically because published PyBullet 3.2.7 wheels for Linux are available for cp311; the pinned upstream source has been successfully imported and run on 3.11 even though its current packaging declares 3.12.

## Build a physical DIY 65 mm 1S whoop

**Build target:** a guarded, hand-piloted 65 mm 1S brushless whoop. Physical build manifest: [hs_whoop65_build.json](hs_whoop65_build.json).

The **printable** variant deliberately follows a **published assembly** so we do not invent another airframe:

- [vsergeev's 65mm 26x26 printable whoop frame, OpenSCAD and STL](https://github.com/vsergeev/3d-parametric-whoop), CC-BY-4.0, original author credited
- [BETAFPV Matrix 1S 5IN1 FC/4-in-1 5A ESC/ELRS/VTX](https://betafpv.com/products/matrix-1s-brushless-flight-controller): 1S only, 26x26 mm mounting, BT2.0, JST1.25 motor connectors, integrated ELRS 2.4 GHz
- **4× RCinPower 0702 27000KV 1S brushless motors**, the printable-frame designer's exact reference
- **4× Gemfan 1210-2 31mm props**, with correct CW/CCW orientation, designer's reference
- **BETAFPV C03** optional camera with printable 26x26 canopy for FPV; goggles required for FPV, not first direct line-of-sight flight
- **1S ~300 mAh BT2.0 battery** with an appropriate dedicated matching 1S LiHV/LiPo charger; **ELRS 2.4 GHz radio transmitter**, e.g. RadioMaster Pocket ELRS variant
- Exact compatible screws, hardware and battery retainer specified by the frame designer; confirm available motor plug and battery dimensions before ordering.

The creator's published **65mm example** reports 24.4 g (ASA, without battery) with the Matrix 1S/C03/0702/Gemfan configuration. Treat that as their reported build, not a weighed HS specimen.

### Printable files already retrieved to the Optiplex

```text
~/chatgpt-work/hs-drone-lab-20261104/3d-parametric-whoop/stl/
    65mm_26x26_whoop.stl
    betafpv_c03_26x26_canopy.stl
    betafpv_c03_camera_harness.stl
```

This is **ready-to-slice source STL**, not an actual print. For materials and slicer settings follow the creator's [source instructions](https://github.com/vsergeev/3d-parametric-whoop#recommended-print-settings). No 3D printer has been commanded, parts ordered or physical drone assembled in this session.

### Junk/salvage route

Using donor parts is optional; never just swap components because they fit a picture.

| Donor item | Use? | Condition |
| --- | --- | --- |
| 65mm plastic ducted frame | Maybe | Uncracked motor mounts, no rubbing against 31mm props, exact FC clearance |
| 0702/0802-class brushless motor | Maybe | Three phase wires, verified shaft/mount dimensions, matched KV/load/1S, healthy bearings |
| Old brushed toy motor (two wires) | **No for this Matrix 1S build** | A brushless 4-in-1 ESC does not drive it correctly |
| Propellers | Maybe | Only uncracked, matched geometry, shaft hub and rotation; damaged props replaced |
| Battery from junk drawer | **Do not use** | Chemistry/cell health, swelling and charging history unknown |
| Proprietary toy-drone flight controller | Usually no | Can't assume ELRS, Betaflight, MCU target, 1S ESC or pinouts |

### Actual physical assembly sequence

1. **Dry-fit:** measure the printed frame, controller 26x26 mounts, motor bores, prop clearance and battery cage. Do not attach propellers while working.
2. **Install hardware:** mount 0702 brushless motors; fit Matrix 1S on dampers, orient its arrow to the actual craft front, retain battery, and route all wiring away from rotor sweep.
3. **Connect electronics:** match motor plugs, wire/camera pinout and battery BT2.0 polarity against the exact board revision; do not guess.
4. **Configure radio and flight controller:** Betaflight target, ESC motor order/direction, ELRS link, channel map and arming switch. [Betaflight's official setup guide](https://betaflight.com/docs/wiki/getting-started/setup-guide) is the authority for the real aircraft.
5. **Props-off bench check:** verify gyro orientation, motor numbering/spin direction, arm/disarm and receiver failsafe **without any props attached**. Correct a failed check before flying.
6. **First real hover:** only once assembly and radio are verified, install correctly handed undamaged props; use a clear indoor area with guards, low throttle, short hover and controlled landing. Save a real video and post-flight battery/motor inspection.

**This physical craft has not been built or flown.** The current Crazyflie simulation is a genuine flying model, but its 27 g brushed Crazyflie parameters are **not** calibrated to the published 65mm brushless Matrix 1S kit. Do not transfer PID motor RPM or thrust numbers from the simulator directly to the real kit.

## What would count as a product result

We now have a working flight simulation, a browser cockpit and concrete 3D printable airframe files. The remaining product steps are **material acquisition, physical printing/assembly, actual Betaflight setup and a real safe first hover**. We should measure whether the aircraft flies, not whether our report's test counters are green.

There is no autonomous flight hardware control in this repo code, no on-air radio transmission, no connected propeller motor, and no physical permission to energize unverified salvage components.
