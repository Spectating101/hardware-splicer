# RealPCB pilot: HS lays out one production board (2026-11-26)

[RealPCB](https://www.esunalabs.com/realpcb/) (Esuna Labs, grader Apache-2.0, [repo](https://github.com/esunalabs/realpcb))
hands an agent a real production board with its free parts unplaced and nothing routed, and grades the finished layout
with KiCad's rule check and layout-quality measures against the layout the board's own engineer released. Leaderboard
(53 private boards): GPT-6.2 Astra 69.8%, GPT-6.2 Sol 66.0%, Fable 5.2 in Claude Code 60.4%, Sonnet 5.5 43.4%,
Haiku 5.5 13.2%.

## What was run

* Public task `pcb-8fca292701a9`: the carrier board of [open-bed-climate](https://github.com/moinsen-dev/open-bed-climate)
  (Apache-2.0), 100 x 100 mm, 2 layers, 126 footprints of which 93 free, 112 nets: Pico 2 and ESP32-S3 sockets, 12 V
  input with fuse, TVS and reverse-polarity FET, LM2596 buck, ADS1115 with four NTC dividers, SP3485, ten MOSFET drivers.
* Grader set-up check: the engineer's layout scores 1.0 and passes; the start board scores 0.
* HS pipeline: `place_free_footprints.py` (new, this branch) places the 93 parts; HS's FreeRouting set-up routes (net
  classes: 1.0 mm supply and switch node, 0.8 mm load drains, 0.5 mm 3V3); ground pours on both layers with solid pad
  connections, 208 stitching vias, start board's setup block kept. Engineer's placement never looked at.

## Result: reward 0.48 of 2, not a pass

| Check | Result |
|---|---|
| Integrity, copper faults, assembly errors, pour width, parts on board, 1 mm edge margin | pass |
| Decoupling loop (median 9.9 mm, limit 15.5) and direct decoupling wiring | pass |
| Buck hot loop 14.4 mm (limit 51.2; engineer 34.1) and switch-node area 30 mm^2 (limit 87) | pass |
| Supply-copper resistance 1,171 squares (limit 2,355) and ground reference | pass |
| **Connectivity: 11 open of 251** (7 signal connections FreeRouting did not finish, 4 ground pins/islands) | **fail** |

Every layout-quality measure passed, several better than the engineer's; the layout fails only because the router left
connections unfinished. Unofficial: the task image has no autorouter and the official protocol gives the agent none, a
single public board can be in a model's training data, and one board is a pilot, not a score.

A second attempt (wider gaps around fine-pitch ICs) never produced a board: FreeRouting 2.1 ignored the pass limit and
the job timeout in its settings, was killed at 20 minutes and saves nothing when killed; its best moment was 5 open.

## What this shows HS needs

1. **A placer.** HS had none (HS-BUS-A was placed by hand). `place_free_footprints.py` now places by connectivity,
   ties decoupling capacitors to their IC's supply pin, keeps courtyard, pads and silkscreen clear, and hides labels.
2. **A router that stops and keeps its best.** `routing_engine.FreeRoutingEngine` discards everything on timeout, and
   FreeRouting 2.1 ignores `-mp`, `max_passes` and `job_timeout`: the first run reached its best (3 open) by pass 69
   and then spent about 900 passes and 30 minutes gaining nothing. Needs a pass cap that works (newer FreeRouting or
   a watchdog that requests a save) and partial results kept.
3. **A completion step.** The last few connections (fine-pitch pins, two long UART runs, ground pins hemmed in by
   other pins) decide pass or fail; a targeted re-route or via fan-out for open connections is the missing piece.
4. **Cleanup checked against the grader.** HS's dangling-track cleanup did not cause the opens here, but nothing had
   tested it against an independent connectivity check before.

The grader itself is Apache-2.0 and measures what HS's own checks do not (decoupling loops, hot loops, ground
reference, supply resistance); it can serve as an independent layout check, called from a pinned download rather than
copied in (its files carry a do-not-train canary).
