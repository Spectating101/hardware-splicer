# Hardware Splicer: executable new-product software benchmark

**Execution date:** 2026-10-20 on Optiplex; software-only. Based on the
Taiwan donor source case and the unattended seven-source evidence
investigation in PR #152.

The mission is to assemble a **new product from heterogeneous failed
devices**, separate from restoring original device functionality.
This milestone tests software control logic and the feasibility
of *hypothetical* electrical paths. It does not demonstrate a working
physical assembly.

## What HS executed without operator checks

HS selected a provisional new-product concept: a barcode inspection and
object-indexing station. Eight explicitly synthetic controller scenarios
were executed:
- Normal abstract load/motion/scan/ack cycle
- Stop during indexing
- Premature scan not credited
- Motion timeout
- Limit fault
- Reset cannot arm until the abstract interlock re-closes
- Stop requires fresh arming
- Invalid barcode input fails closed

**8/8 targeted software scenarios passed.** An independent bounded
virtual state audit evaluated **7,380 event sequences** over a
nine-event alphabet with length 1–4 (**28,602** simulated transitions).
No violations were found in the checked invariants. This does not
establish correctness for arbitrary long operation or physical safety.

The controller emits abstract virtual requests and receives simulated
events. It opens no USB device, drives no GPIO, powers no motor, and
simulates no certified safety interlock.

## Actual electrical feasibility check

The existing Hardware Splicer motor driver synthesis planner received
the conditional idea of a low-voltage *DC motor*. No donor measurements
were fabricated. It returned **blocked**, with these five missing
contracts:

1. load_current_estimate
2. supply_rail
3. control_signal_voltage
4. l298n_output_current_rating
5. flyback_or_driver_protection

Important: **the Epson LQ-680 mechanism has NOT been inspected and the
actual motor type is unknown**. The conditional DC motor branch does
not establish a DC motor rather than a stepper, nor authorize an L298N
driver or physical voltage selection.

## Honest authority and mission findings

**One software reference subgoal** is now verified using synthetic
input events, not physical donor interfaces.

Six physical gates remain open:
- Original barcode scanner and exact interface cable function
- Actual motor type, motion characteristics and mechanics
- Motor driver, power source, current limits and inductive protection
- Actual computer-to-hardware communication (QNAP bare board remains
  optional; current Linux host only runs software reference)
- A separate, safety-rated physical stop mechanism
- Physical multi-donor integration, measurements and real machine test

Physical donor count tested: zero. Original LS2208 repair successes:
zero. New product physical successes: zero. No purchasing, seller
contact, wiring, flashing, soldering, power-on or actuation occurred.

## Autonomous execution and reproduction

The new reference software and analysis are under
src/hardware_splicer/virtual_splice_reference_cell.py and
src/hardware_splicer/autonomous_splice_feasibility.py.

The single-command runner is
scripts/run_autonomous_splice_feasibility.py. It rechecks source evidence
through the existing public-source controller and executes software
functional tests, bounded state audit and the actual motor planner.

Programmatic interfaces:
- SDK: validate_virtual_splice_feasibility
- MCP: hs_validate_virtual_splice_feasibility

Live source recheck and software validation command:

    PYTHONPATH=src python -m scripts.run_autonomous_splice_feasibility --out /tmp/hs-feasibility

Offline replay from the already archived real source evidence:

    PYTHONPATH=src python -m scripts.run_autonomous_splice_feasibility --source-snapshot docs/evaluations/AUTONOMOUS_PUBLIC_DONOR_INVESTIGATION_2026-10-20.json --out /tmp/hs-feasibility-offline

The exact live execution is archived as
AUTONOMOUS_SPLICE_SOFTWARE_FEASIBILITY_2026-10-20.json.
The focused tests include the new virtual behavior, module boundaries,
motor-driver regressions, public source loop, MCP/SDK, and older
mission gates. **155 passed, 1 skipped, 1 warning.**

The next independent engineering task is source-specific interface
alternative evaluation and/or unattended **instrumented intake** if an
authorized real donor becomes available. No manual checking of market
pages is required for this milestone.
