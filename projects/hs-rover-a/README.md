# HS-ROVER-A: an inspection rover, worked end to end through HS's agent interface

![chassis](rover_chassis.png)

**Status: design package only. Nothing has been bought, printed, wired, powered or driven.**

This is the first objective carried from a plain brief to a build package entirely through Hardware-Splicer's MCP server,
the interface any outside agent uses. An agent (Claude Code, on 2026-11-26) made the engineering decisions; every
calculation, CAD build, check and file came from an HS tool over MCP, and HS kept the whole record on one project
(`project/ledger.jsonl`, 34 steps, each tool call with its inputs).

## Objective and acceptance (set before any design)

> Build an affordable, useful CCTV/inspection rover from obtainable parts: drives on indoor floors and gentle ramps,
> streams live video over Wi-Fi to a phone or laptop, and can be printed and assembled by one person.

| Acceptance | Result | Step |
|---|---|---|
| Parts at or under US$250, every price cited | **Fails: US$263.44**, all 22 lines cited (quoted 2026-11-26); shipping not included | 30, open |
| 0.4 m/s on the flat, 15 degree ramp within maker limits | 0.79 m/s at full duty; 0.10 A cruise and 6.7% of stall torque on 15 degrees per motor | 17 |
| Prints on 220 mm, 15 mm ground clearance, no tip on 15 degrees | 180 x 120 x 64 mm part; 30.5 mm clearance; tips at 27 degrees (backward) at the earliest | 18 |
| Camera sees the floor ahead, chassis out of view | Nose out of view; floor visible from 113 mm ahead | 18 |
| At least 1 h patrol | About 5.0 h on 2.2 Ah cells at the 4.0 W average load (declared 2.8 W video, measured-model motor current); 0.6 A peak | 28 |
| Remaining risks listed for physical test | See below | status |

## How the design moved (all in the ledger)

1. **Prior art** (`hs_prior_art_search`, `hs_read_board`): the closest open board, roverbase, is GPL-3.0 with its own
   unfinished fixes; NASA-JPL's open rover is Apache but far larger; finished patrol robots are US$750-1,025.
   Decision: buy proven modules, print the chassis, no custom board.
2. **Drive** (`hs_size_rover_drive`): 29 of 38 cited gearmotors pass at 0.9 kg; chose Pololu 25D MP 12V 47:1 over the
   lowest-current 75:1 because 75:1 has no speed margin as the battery sags.
3. **Chassis** (`hs_rover_chassis`): first build failed (wheel 2.0 mm from the plate, 3 mm minimum); a 3.5 mm hub
   offset passed. The drive was re-checked at the chassis's own mass.
4. **Wheels**: Pololu's 90 mm wheel press-fits only 3 mm shafts; its holes take the 4 mm universal hub, so 90 mm
   replaced the assumed 80 mm and both checks re-ran.
5. **Budget** (`hs_bom_check`): four-wheel drive came to US$323.66 against US$250. Switched to rear two-wheel drive with
   a Pololu #2692 caster (29 mm tall, on a 1.5 mm printed boss), US$242.32. Chassis, drive and energy re-ran: still
   stable, with about 80% of the weight on the driven wheels.
6. **Software**: reuse MediaMTX (MIT) for WebRTC video from the Camera Module 3 and gpiozero's `PhaseEnableMotor` for
   the DRV8874 carriers in phase/enable mode; a 70-line drive page (`project/artifacts/software/`).
7. **Integration catch**: the Pi Zero 2 W needs the Zero camera cable, not the one supplied with Camera Module 3.

## Parts (`bom.json`)

Pololu: 2 x 25D MP 12V 47:1 gearmotor (#3229), bracket pair (#2676), 2 x DRV8874 carrier (#4035), 5 V 2.5 A regulator
D24V22F5 (#2858), 90 x 10 mm wheel pair (#1435), 4 mm universal hubs (#1081), ball caster (#2692). Adafruit: Raspberry Pi
Zero 2 W, Camera Module 3, Zero camera cable, M2.5 standoffs. Pololu fasteners: M3 x 10 mm screws and nuts (brackets,
caster), M2.5 x 6 mm screws (Pi), #2-56 screws and nuts (camera, 2.2 mm holes).

Power, bought in Taiwan because Li-ion cells cannot be air-freighted from US shops: iNeno 18650 2200 mAh cells (BSMI,
4-pack, one spare), a KINYO two-slot USB charger (cells are charged one at a time, so no 3S balance charger) and a SanDisk
32 GB microSD, all PChome 24h and in stock on 2026-11-26. A DFRobot 3 x 18650 holder (78 x 59 x 21 mm, fits the 80 x 60
x 22 mm bay) and a 3S protection board (Core Electronics) come from abroad. NT$ and AU$ prices are converted at the
2026-11-25 rate; the PLA price (Bambu Lab, US$19.99/kg) is from a search result, as the store page is not machine-readable.

**Why it is over budget, and how to get under:** the three lines declared at US$36 actually cost US$57.12; fasteners in
25-packs alone are US$14.04. Already owning a microSD card and an 18650 charger saves US$19.65 (to US$243.79), and
screws from a local hardware shop cost less than the packs. Shipping from Pololu, Adafruit, DFRobot and Core
Electronics to Taiwan is not quoted (it needs a cart and an address) and comes on top.
Dimensions come from the makers' drawings: Pololu 25D datasheet rev 2.0, bracket bkt04c, caster cst05, Raspberry Pi
Zero 2 W and Camera Module 3 mechanical drawings (listed in `rover_chassis.py`).

## Against what is already sold (2026-11-26)

An unbranded wheeled pet camera ("Blinky Bot", V360 Pro app) sells for US$30-50, about NT$1,500 on Shopee: tracked,
1080p with pan and tilt, night vision, two-way audio, microSD and cloud ([CNX Software review](https://www.cnx-software.com/2025/08/12/low-cost-mobile-robot-and-security-camera-monitors-your-home-and-pets/)).
HS-ROVER-A's parts alone cost about six times that and it has no night vision, audio or pan/tilt, so it is **not a
home or pet camera product**. What it has that the toy does not: video that stays on the local network with no vendor
cloud, about 5 h runtime, 15 degree ramps, 30 mm clearance, and open, replaceable parts. The step 1 prior-art search
missed this whole consumer class (it looked at open boards and US$750-1,025 patrol robots); prior art now has to include
consumer marketplaces. Ledger steps 31-32.

**Salvaged instead (2026-11-26):** a broken phone plus a broken toy car, an ESP32-C3, a motor driver and 18650 cells
from dead laptop packs comes to NT$561 (US$17) on Ruten listings, NT$162 of it new; a broken Roomba 571 driven over its
serial port instead of the toy car comes to NT$1,139. Both pass `hs_bom_check` under the Blinky Bot's price (ledger
steps 33-34). Donors untested; shipping and assembly hours not counted. Sources: `docs/SALVAGE_SOURCING_TW_20261126.md`.

## TT-motor variant (2026-11-27, `tt-variant/`)

The same rover on OpenBot's drive tier, worked through the same tools on its own project record
(`tt-variant/project/ledger.jsonl`): two Adafruit TT gearmotors (#3777, 48:1) on 65 mm wheels, one DRV8833 for both, a
6 V step-down for the motor rail, and Pololu's 1/2 in ball caster. The chassis tool now builds this layout
(`motor: "tt"`): each motor lies fore-aft under the plate and bolts with two M3 x 25 screws through its gearbox to a
printed rib, from Adafruit's dimension drawing.

| | Pololu 25D (as built) | TT variant |
|---|---|---|
| Parts | US$263.44, fails the US$250 target | **US$187.50**, passes; 22 lines, all cited |
| All-up mass (chassis tool) | 564 g | 438 g |
| Ground clearance / first tip | 30.5 mm / 27 deg | 21.3 mm / 41 deg |
| Speed at cruise | 0.79 m/s | 0.64 m/s |
| Current per motor, cruise / 15 deg ramp | 0.10 A / 0.25 A at 12 V | 0.22 A / 0.53 A at 6 V |
| Runtime at the same 1 h duty | about 5.0 h | about 4.7 h |
| Unknown | none | the TT's torque limits (not published) |

Why each part: the pack is 3S (up to 12.6 V), above both the TT's 3-6 V and the DRV8833's 10.8 V, so the motors get
their own 6 V regulator, not the Pi's 5 V rail. Running them on PWM from the pack would save that regulator's US$27.95,
but drives them outside their rating. The 65 mm wheels put the plate 21.3 mm up, below the 29 mm caster, so the
13.5 mm caster sits on a 7.8 mm printed boss. The TT's stall current is Adafruit's measurement of one motor (1.5 A at
6 V); two stalled motors (3 A) exceed the 6 V regulator's 2.5 A, which then limits current. A stall test on the bench
settles it.

## Needs a physical test

Traction, turning (skid and caster drag are not modelled), print strength, wheel/hub/bracket stack-up (hub offset is
declared), real battery runtime and the declared 2.5 W video load, the drive page and MediaMTX config on a real Pi, the
camera image, and the 3 A fuse choice. The parts total is over budget by US$13.44 before shipping (see Parts).

## Reproduce

Each step's tool and inputs are in `project/ledger.jsonl`; replay them through `hs_*` tools over MCP
(`python -m hardware_splicer.mcp_server`) or REST (`POST /v1/toolbelt/<tool>`). The chassis alone:

```bash
HARDWARE_SPLICER_DIGITAL_PYTHON=<python with cadquery> python -m hardware_splicer.engineering_toolbelt hs_project_open '{"objective": "rover"}'
```
