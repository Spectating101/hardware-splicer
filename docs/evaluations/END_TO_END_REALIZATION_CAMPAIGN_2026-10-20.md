# Hardware Splicer: agent-led digital design to real-world handoff

**Test date:** 2026-10-20, authorized Linux Optiplex.
**Actual scope:** completed first-round digital fabrication handoff with a
genuine, independent external slicer and detailed human-operated deployment
procedure. **There is no physically finished machine, verified printer,
salvaged donor specimen, electrical harness, or independent stop.**

## Goal and decisive success criteria

User asked HS to continue beyond CAD and BOM until it can say how a real
person would produce and assemble the parts, print them on a named
printer, connect recovered peripherals, and test the machine.

A real build requires evidence at FIVE different levels:
1. Design identity and engineering source provenance
2. Executed CAD + assembly/BOM
3. Executed real slicer + independently evaluated printer toolpaths
4. Qualified physical fabrication, donor electrical interfaces and safety
5. Observed finished operating device

The current test demonstrates levels 1–3, a human-facing conditional
route to 4–5, and refusal to claim 4–5 without real equipment.

## Machine investigated

A stationary barcode-triggered label indexing concept. Earlier real live
Codex investigation of six archived public sources concluded that:
- Scanner interface and severed cable are not verified.
- Printer motor, feed mechanics, travel sensors, ratings unknown.
- Bare NAS board does not establish a controllable motor output.
- No actual donor parts have been acquired.
- No independently operating motion inhibitor has been tested.

This campaign uses HS's previously real native **100 x 75 x 35 mm**
two-part casing concept. It is NOT fitted to those donors.

## Genuine fabrication execution

SolidCraft v0.16.2 generated native editable base/lid, 2 distinct STLs,
3MF, STEP and working PartCAD assembled BOM (details PR #160).
New here: installed **real PrusaSlicer Debian 2.9.2** portable in /tmp
via extracted system packages and libraries without altering system
installation. Manufacturer PrusaResearch.ini profile inheritance was
resolved into a standalone test configuration:
- Printer: Original Prusa MK4S, 0.4 mm nozzle
- Profile: 0.20mm STRUCTURAL @MK4S 0.4
- Material: Prusament PLA @MK4S, initial 230 C nozzle and 60 C bed
  (later 225 C; these are unverified print settings for an actual machine)
- Configured plate: 250 x 210 mm
- Original two-object 3MF was EXPLICITLY RECENTERED to (125,105) mm
- Resulting object footprints: base x19..119, y67.5..142.5 and
  lid x131..231, y67.5..142.5 mm
- Real PrusaSlicer generated readable text G-code.
- Result: **175 layers, 74.10 g estimated PLA, 3h 13m 39s estimated**
- Actual G-code SHA256:
  b651096ce873cff5f5b28852d567a73c265f2efb384c1af251e6d58e907238f5
- Independent G-code check separately validated both object identities,
  real footprint and margin, selected model/nozzle/filament, plausible
  extrusion layers, heater start/end and machine command restrictions.

A CHECK remains open: the vendor-derived MK4S startup purge uses Y=-4 mm
outside the nominal bed polygon. It may be an intended motion envelope
on that machine but cannot be confirmed without the actual printer
hardware/firmware and operator. The gcode must NOT be directly sent to
an unrelated printer or silently treated as field-ready.

## Agent-generated real-world procedure

The actual ChatGPT-authenticated Codex CLI generated a 30-step guide
from the real slicer metadata, CAD evidence, six-source donor hypothesis,
absent printer and unknown electrical status. There are:
- Nine printer commissioning and printing preparation steps
- Seven mechanical measurement, tolerance and fit steps
- Eight hardware identification, connection, stop and electrical steps
- Six scanner firmware, bounded motion and commissioning steps

The guide explains how to confirm an actual intact USB scanner
interface before plugging an intact documented cable into a host,
while REFUSING to invent the pinouts of a cut cable or motor leads.

Independent guide validator requires nonempty evidence and STOP
conditions for each step, detects unverified claimed fabrication
authority and ungrounded controller pin connections, and enforces
30 independent physical release blockers. It accepted the conditional
guide and rejected falsified positive-authority variants.

## Real bytes through printer control code, no actual printer

HS FabricationPrinter/OctoPrintBackend staged the *actual 5 MB G-code*
using an in-memory transport; verified SHA256 and upload fields:
  select=false, print=false
A deliberately unapproved attempt to start was denied by the existing
one-shot human-grant mechanism. No real OctoPrint/Moonraker URL or
physical printer was contacted. This is a dry-run of the actual control
software, not proof any real printer/host protocol worked.

## Scanner/motion failure campaign

Ran existing independent adversarial virtual barcode/index controller
harness. Four out of four deliberate state-machine mutations were
rejected and two contradictory summary reports were caught. Three
real-world blockers remain:
- unauthenticated actual movement + scanner signal provenance,
- replayed same barcode without unique physical item identity,
- absent independently enforced watchdog timebase.

Physical controller release is BLOCKED regardless of software passes.

## What's still missing to get the final machine

No printer was in CUPS or USB devices. No recognized scanner, bench
instrument or serial/ACM controller connected. No physical donors
purchased, inspected, or characterized. No verified motor driver,
wiring, connection pins, real board mounts, thermals, stop circuit or
actual build operations. Even a successful physical casing print would
not prove a working barcode indexing system.

**The right next physical test** is a verified compatible printer and a
printer-specific PLA test coupon + case-first-article, then actual donor
measurement and documented/guarded low-voltage bench bring-up with a
separate human approval. We cannot execute those physical operations
from current peripherals, and this package does not authorize them.

## Downloadable reproducibility artifact

See examples/realization_pilot/HS_FABRICATOR_END_TO_END_CONDITIONAL_20261020.zip
(1.03 MB), containing the entire real G-code, CAD, BOM,
live Codex-generated RUNBOOK, independent audit receipts and hashes.

The standalone test profile is packaged inside and SHOULD NOT be used
on a real MK4S without comparing to the actual printer/nozzle/material
and contemporary Prusa presets.

Script entrypoints:
- scripts/run_realization_pilot.py: real installed slicer and copied CAD
- scripts/run_realization_printer_dryrun.py: stage actual bytes, deny start
- scripts/finalize_realization_pilot.py: validate live agent, actual G-code
  and control reports, generate runbook and reproducible archive

All commands run read-only/offline against physical hardware.

**Verdict:** End-to-end *digital fabrication and deployment handoff*
demonstrated. Complete *physical autonomous fabrication* NOT demonstrated.

## Real agent revisits the completed fabrication package

After the real slicer, virtual printer and assembly evidence were
generated, ran live ChatGPT-authenticated Codex again inside the HS
bounded engineering loop. The model independently selected:
1. inspect_fabrication_package: read actual recorded G-code/print
   geometry, material estimate and machine-readiness limitations.
2. audit_candidate: rerun original source-bound engineering audit.
3. finish: reject physical release and summarize necessary evidence
   needed before actual printer use, electrical wiring and motion.

MODEL_FINISHED with two actual HS tool actions, no test double,
approximately 124 seconds. Its complete model-choice and tool
receipts are in the zip file at CODEX_LIVE_FABRICATOR_TOOL_LOOP.json.
