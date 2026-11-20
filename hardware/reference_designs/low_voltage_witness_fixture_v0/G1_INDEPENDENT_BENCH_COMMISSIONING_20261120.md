# G1 independent bench commissioning — instrument and fault-protection handoff

**Operator reference; physical HOLD remains.** For the latest G1 primary/reference stream-binding preflight and unified review, see [CONSOLIDATED_REVIEW.md](CONSOLIDATED_REVIEW.md).
20 November 2026 — HS witness v0, stacked on HS #364, #360, #358, #356.

**RELEASE HOLD.** No board, source, fuse link, instrument, calibration,
qualified operator or physical experiment has been verified. This is a
pre-commissioning research package. Nothing here authorizes fabrication,
energization or claiming physical research results.

## What changed at G1

- Prior work now has a sourced (but not selected) Vishay RE65G12R0C02
  12 ohm +/-1% load option with conservative resistance-power envelope
  2.331 W @ 5.25 V across supplier-listed component temperature bounds.
  **Actual thermal mounting, derating and output voltage remain unverified.**
- The old 0.65 A current limit versus 1 A fuse contradiction is formalized
  in a fail-closed protection dossier. Its worst-case illustrative product
  5.25 V * 0.65 A = 3.4125 W is a **continuous source-output bound only
  IF the real source limit works**. It is not a fault energy limit and
  can understate overshoot. A nominal 1 A fuse cannot be relied upon to
  clear a sustained 0.65 A fault.
- A read-only dual-DMM SCPI logger exists with an actual mock-transport
  test. It can log two independent **claimed** resource identities,
  183 time-bracketed readings and an immutable-by-default on-disk
  manifest; it sends no output-power or configuration-to-source commands.
  It has NOT communicated with any real meter.
- A combined commissioning preflight cross-checks G1 physical packet,
  source/fuse/thermal dossier, original SCPI reference trace hashes,
  183-sample / ~3min continuity, two DMM IDs and telemetry provenance.
  Even a completely filled manifest never grants approval.

## Physical commissioning sequence — qualified lab only

### Before any PCB order or powered wiring

1. Independent electrical reviewer selects a **specific 5 V isolated,
   current-limited bench supply** and records model, serial, actual
   voltage range, prospective short-current waveform (including
   overshoot/response), behavior on sustained fault and verified earth/
   ground isolation topology. Do not infer isolation from USB or INA228.
2. Select actual compatible 5 x 20 mm DC-rated **fuse link + SCHURTER
   0031.3551 holder**, documenting DC interrupt capability at worst-case
   prospective source fault current, time-current clearing at relevant
   fault conditions and holder power/ambient acceptance. A 1 A fuse
   with 0.65 A-limited source is **not yet a coordinated solution**.
   Never bypass the intended fuse holder or replace it with a jumper.
3. Select the exact four-terminal 10 mOhm reference shunt and 15 mOhm
   primary carrier assembly; inspect solder pads, solder jumper,
   Kelvin-only routing, high-side input common mode and actual
   reference-shunt calibration. Do not substitute a two-terminal part.
4. Select actual external 12 ohm load, chassis/heatsink, cable strain
   relief, screw terminals, DC ampacity, creepage/clearance and surface
   temperature constraints. Verify vendor derating at **actual** ambient
   and mounting, not just its advertised 10 W nominal rating.
5. Obtain two separately identified DC voltmeter channels for J5
   (Kelvin reference 4–5 mV) and J6 (J2 load bus ~5 V), or an
   equivalent independently traceable multi-channel standard.
   At least two genuine readings (shunt plus VBUS) are needed for
   reference energy. A separate INA228 and a second DMM measuring
   only shunt voltage are not enough for J2 energy by themselves.
6. The independent reviewer checks all wiring/earth/common-mode and
   instrument manuals, signs the controlled safety protocol and defines
   stop/abort criteria **before** any qualified operator can proceed
   with a physical commissioning run. No autonomous power-control
   software exists in this milestone.

### Physical capture requirements after approval

7. A trained lab operator records initial inspections and manufacturer
   identity/calibration data, source limit and thermal observations.
   Read-only capture must not be treated as a substitute for the
   independent electrical safety review.
8. Preferred acquisition: common verified hardware trigger/external
   clock with logged conversion aperture time for both reference
   channels and the primary INA228. If only host USB/LAN time brackets
   exist, **external synchronization is NOT established**.
9. Retain all raw manufacturer-native exports or raw SCPI responses,
   primary INA228 register stream + session receipt, exact identities,
   clock-trace data, calibration certificates, as-built photographs,
   thermal record and a second operator's signed review.
10. G1 software checks only assess structural consistency and file
    integrity. A qualified engineer separately validates physical
    safety, independence, calibration and timing. G2 needs a
    pre-registered uncertainty budget and blind true/false fault
    discrimination tests before any scientific acceptance claim.

## Available executable tools

All commands below are safe software-only checks **unless an explicitly
authorized operator deliberately selects live dual-DMM resources**.
No PSU or load control is implemented.

From the existing witness-fixture directory:

    python3 -m unittest -v test_protection_preflight.py
    python3 protection_preflight.py \
        --input G1_PROTECTION_INPUT_TEMPLATE.json \
        --out /tmp/new-protection-screen.json

That script always exits code 2 because no physical review authority
is delegated to the machine, even if someone fills in all fields.
An empty dossier should report missing source, DC fuse, cable,
thermal and operator evidence.

    python3 reference_scpi_bracket.py \
        --transport fixture --samples 3 --period-s 0.05 \
        --out /tmp/new-scpi-mock

That is a **TEST_FIXTURE** using two simulated SCPI instruments.
Outputs are reference-preview.csv, reference-query-raw.jsonl and
reference-session.json; hashes, raw responses and query start/end
times are retained. The derived reference-preview timestamp is a
**HOST QUERY-BRACKET MIDPOINT**, not the DMM's ADC acquisition time.
Even mocked fixture success exits code 2 (no physical promotion).

A **future, already-safe, physically authorized** lab operator could
use the *read-only* transport with two explicit unique PyVISA resource
strings and the explicit --physical-read-only-authorized switch,
after installing the optional PyVISA/driver backend and validating
instrument compatibility. This code issues *IDN? and
MEAS:VOLT:DC? 0.2 / MEAS:VOLT:DC? 20 only; it does not drive source
voltage or communicate with a power supply. Do not use it until the
source/earth/common-mode review is completed. Even for actual meters
it creates only DECLARED_REFERENCE_BRACKETED_UNVERIFIED evidence;
the actual range and ADC aperture must be independently established.

    python3 g1_commissioning_gate.py \
        --g1-packet G1_BENCH_EVIDENCE_TEMPLATE.json \
        --protection-input G1_PROTECTION_INPUT_TEMPLATE.json \
        --reference-session /tmp/new-scpi-mock/reference-session.json \
        --out /tmp/new-commissioning-screen.json

The combined gate returns exit code 2. It detects mismatched data,
implausible timestamps, different claimed meter roles sharing a
device, incomplete packets or simulated inputs. Forged full files
and even matching SHA-256 hashes cannot establish device authenticity.

## Specific instrument documentation

- Siglent SDM3055 Remote Manual (SCPI syntax, MEAS:VOLT:DC? fixed range,
  external trigger support, data-buffered acquisition):
  https://seltokphotonics.com/media/brander_product_attachments/s/i/siglent_technologies_sdm3055_remote_manual.pdf
- SCHURTER FAB 0031.3551 holder (rated **250 VAC holder**, does NOT
  establish a DC fuse link interruption rating):
  https://www.schurter.com/en/part/0031.3551
- SCHURTER engineering holder selection guidance (fuse-link power
  dissipation, ambient derating, holder matching, conductor gauges):
  https://www.schurter.com/en/knowledge/fuseholder

The SDM3055 is a **specification/SCPI integration lead**, not a
selected, borrowed, calibrated or connected meter. A single meter
cannot measure 4mV shunt and 5V VBUS simultaneously simply by
switching ranges. Sequential readings under varying load are not
equivalent to synchronized channels.

## G1 source/OVP qualification follow-up (20 Nov 2026)

Vendor research and new `source_suitability.py` identify the Rigol DP832A CH1 as a preferred *borrow-only* source lead with programmable OVP/OCP. The Siglent SPD3303X-E has CC/OCP but vendor support says it lacks user-settable OVP and cannot be taken as a standalone 5.25 V protection solution. The G1 protection input now requires verified OVP enabled state, proposed trip level below 5.25 V and actual observed J2 fault-event peak. See [G1_SOURCE_SELECTION_AND_INSTRUMENT_BORROW_20261120.md](G1_SOURCE_SELECTION_AND_INSTRUMENT_BORROW_20261120.md). None of this means a source is available or meets the physical trip transient. Borrowing two calibrated DC voltage channels and obtaining high-side-safe independent timing remains unclosed.

## Unclosed gates and honest end state

PHY-01...PHY-10 remain subject to their original build hold.
In particular PHY-04/05 (source/fuse/earth) and PHY-06/08
(reference instrument/operator) are still OPEN. The 12 ohm precision
candidate does not prove thermal mounting. No device has been
energized or measured. Software test outcomes are valuable for
revealing contradictions, but do not justify a hardware release.

Next independent engineering decision: choose exact source with
fault-current proof and real DC fuse link/holder coordination,
then secure borrowed calibrated reference instrumentation
and an authorized qualified bench operator. Complete the blank
G1 packet only with real raw measurements and source records.
