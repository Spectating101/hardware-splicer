# Mapping robot: new-parts build and vacuum splice (design)

Date: 2026-11-06. Branch: `agent/hs-mapping-robot-20261106`.

## Why this exists

The owner wants proof that Hardware Splicer (HS) can take obtainable parts, including junk, and produce a new working
thing. That proof has two tests, and only these two are in scope:

- **Test 1, the parts are real and understood.** Every part comes from a real, current source (a Ruten listing, a
  manufacturer page, a teardown) and its identity, dimensions, electrical interface and pinout are documented with
  sources. Anything nobody has confirmed is marked unconfirmed, never guessed.
- **Test 2, HS turns them into something new that works.** HS produces the design: board, enclosure, firmware and robot
  software, and shows the robot working in simulation.

A third test, whether it is worth money, is deliberately **out of scope** (mission doc track 2, "Never conflate profit
with utility"). Earlier pricing work (PR #291) is the reason it was separated. The mission doc,
`docs/HARDWARE_SPLICER_MISSION_FREEZE.md`, is not on `main` yet; it lives on the integration branches (for example
`integration/hs-unified-engineering-20261021`) and is read from there.

The product is the same for both builds: **a small indoor robot that drives around a room and builds a map of it**
(a 2D LiDAR mapping robot, the kind schools and hobbyists use to learn robotics). Requirement, taken from HS's existing
`examples/robotics_guidance/linorobot2_apartment_mapper.json` scenario (designer's call, not the owner's words):
map and autonomously navigate a small apartment, fit through 70 cm doors, run at least 60 minutes, stay repairable
with accessible parts.

## The two builds, in order

**Build 1, new parts (do first).** Every component is bought new from e-commerce, identified by an exact Ruten listing
(or official store when Ruten has none): drive motors with encoders, wheels, a 2D LiDAR, a microcontroller, motor
driver silicon, an IMU, a finished battery pack with BMS, a buck converter. HS designs everything else: the main
board (KiCad), the printed chassis (CAD from the real part dimensions), the firmware and the ROS 2 robot.
This is design and manufacturing, not assembly of a kit.

**Build 2, splice from a junk vacuum (do second).** One Xiaomi/Roborock first-generation-class robot vacuum (exact
model chosen during its test 1, using Ruten listings and teardowns) supplies the chassis, drive modules (motor,
gearbox, encoder, wheel), bumper and cliff sensors where identifiable, and its LiDAR. Its main board is replaced by a
variant of the Build 1 board. The firmware and ROS 2 stack from Build 1 are reused with the donor's parameters.
The donor battery is reused only as an intact pack; otherwise a bought pack is used. If the donor's motors, encoders
or sensors cannot be identified from public sources, that is recorded as the test 1 result and Build 2 stops there
honestly; it is not papered over with assumptions.

The Roomba route discussed earlier is dropped: it is mostly repair plus an add-on.

## What "passed" means

For each build:

- Test 1: a parts table where every row has an exact identity, a source URL, dimensions and interface facts with their
  own sources, and a confidence label. For Build 2, also a donor map: which donor part is reused, how it connects, and
  what is unconfirmed (the Xiaomi LDS02RR pin count is already known to be disputed between sources).
  - **Where parts may come from** (designer's call). Bought modules and assemblies (motors, wheels, LiDAR, battery
    pack, microcontroller module, IMU module, buck converter) come from Ruten first, then Taiwan maker shops or
    official stores, then cross-border marketplaces such as AliExpress, labelled as cross-border. Shopee is not used
    (automated reads hit a captcha). Components placed on the HS board (ICs, passives, connectors) come from the
    LCSC/JLCPCB assembly catalogue with datasheets, as any board designer would, not from Ruten.
  - **Build 2: stop or go ahead** (designer's call). The donor's drive modules and LiDAR are essential; bumper and
    cliff sensors are optional. A conflict between sources (such as the LDS02RR pin count) is first resolved with
    more sources. If it stays open, the board goes ahead with a connector or jumper that handles every documented
    reading, and the conflict becomes a named bench check. Build 2 stops at test 1 only when an essential part's
    basic interface is unknown, for example no source at all on what the encoder outputs.
- Test 2, all of:
  1. a KiCad board that passes ERC and DRC with the repo's KiCad 9 tooling, exported as fab-ready files for
     JLCPCB (Gerbers, drill, assembly BOM and placement), with the microcontroller as a soldered module; nothing is
     ordered (designer's call);
  2. printed-part CAD that fits the real part dimensions, with a clearance check;
  3. firmware that compiles, and whose LiDAR decoding is tested against real recorded scan data from a public source;
  4. a ROS 2 robot model generated from the design geometry, driving with SLAM and navigation in a Gazebo simulated
     apartment and producing a map, with screenshots and logs kept as evidence;
  5. HS's own drive, power and runtime calculations. For Build 1 they must **pass**: the design is resized until it
     runs 60 minutes of continuous mapping (driving at 0.2 m/s with LiDAR, microcontroller and on-board computer all
     running). For Build 2 they are **reported**: the donor sets the limits, and a shortfall is recorded, or a bought
     pack replaces the donor's (designer's call);
  6. a bench checklist for the day real parts exist.
- The result is labelled **designed and simulated, not built**. The repository rule "authority is never implicitly
  upgraded" applies: nothing here claims a physical robot works.

## How it gets made

The active agent drives the work, but **HS's own tools do it wherever they exist**, because the test is of HS:
`robot_topology` (rover archetype), `robotics_simulation` (drive, power, runtime maths), `robotics_platform_geometry`
(drive base and board geometry), the KiCad pipeline, the `platformio` firmware backend, `donor_capture` and
`teardown_search` (donor intake). Outside tools are allowed where HS has nothing (ROS 2, Gazebo, SLAM Toolbox, Nav2,
run in Docker since none is installed; the open `kaiaai/LDS` library for LiDAR decoding). Every fallback to an outside
tool is written in a **gap log**. A gap that blocks the work is fixed inside HS, with tests, in its own commit.

linorobot2 is prior art to learn from, not a template: the mission doc forbids duplicating a reference kit. HS picks
parts and topology from the requirement.

**When a missing capability is built into HS, and when an outside tool is used** (designer's call). A step is built
into HS, with tests, when it turns HS's own project model into a standard engineering format or would be needed by any
future robot project. The first known case is generating the ROS 2 robot description (URDF) from HS's `robot_topology`
and platform geometry: HS has no generator today (`robot_reference_e2e` uses a fixture URDF). Everything else uses
mature outside tools and is logged: ROS 2, Gazebo, SLAM Toolbox and Nav2 in Docker; Freerouting or KiCad for routing
unless HS's `routing_engine` handles the board; CadQuery for the chassis; PlatformIO installed into a project venv;
`kaiaai/LDS` for LiDAR decoding. A one-off script the agent writes in the design folder (like
`spi_flash_adapter_v1`'s `generate_pcb.py`) is project work, not HS capability, and the gap log says so.

**Which HS is tested** (designer's call): `main`. Before a gap is logged, the open draft PRs are checked; a gap already
filled on an unmerged branch is logged as "filled on PR #N, not merged" rather than rebuilt.

## Constraints

- Nothing is bought and no seller is contacted. Ruten reads are read-only, about one request per second.
- No mains wiring. No lithium cell repacking; batteries are finished packs with a BMS or intact donor packs.
- The repository is public: no secrets, no personal data.
- Commits are small, one concern each, imperative mood (see `CLAUDE.md`).
- Generated artefacts follow the repo's tracked/untracked rules; durable evidence goes under a dated path.

## Non-goals and anti-goals

Non-goals: profitability or pricing decisions; a physical build; the Roomba route; cameras or vision; outdoor use.

It counts as a failure, even if every check passes, if: the output is mostly JSON outlines, checklists or open
questions instead of a real board, CAD, firmware and a simulated run; a pinout or dimension is invented; a part is
silently swapped for a different one; or the result is described as a working robot.

## Left to the builder

Microcontroller and host computer choice, exact motor, LiDAR and IMU models (within test 1's sourcing rule), chassis
shape, ROS 2 distribution, simulated world, where artefacts live in the repo (a `hardware/reference_designs/` folder
is the obvious home), and how to split the work into checkpoints. Designer's call: check in with the owner after each build's test 1,
before the heavy design work starts.
