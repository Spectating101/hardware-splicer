# Repair Challenge 04 — Source-bound electrical observations from KiCad netlists

**Status:** executed digital integration trial; **not** physical measurements, repair success, safe power-on, fabrication signoff, or a competitor victory. Date: 2026-10-24.

## Why this matters

Previously, HS's **existing KiCad sexpr netlist importer** appeared to accept `examples/main_ctrl_esp32_servo.net` and produce PCB placement. But it stringified nested `(name ...)`, `(ref ...)`, and `(pin ...)` arrays, so electrical nets carried **zero real pin memberships**. The ensuing "clean" router result tested a mostly empty electrical problem—not the exported circuit. This was a critical failure of external engineering-tool reuse.

The corrected `src/hardware_splicer/netlist/import_kicad.py` reads actual nested KiCad S-expressions. On the **unchanged repository netlist example** the parsed result is:

| Source property | Former parser | Corrected parser |
| --- | ---: | ---: |
| Components | 9 | 9 |
| Net documents | 14 | 14 |
| Real `REF.PIN` memberships | **0** | **40** |
| `J1.1` maps to VBUS; `U3.1` to GND | No | **Yes** |
| PCB router fed original wire connectivity | No | **Yes** |
| Internal fallback copper-crossing reports (without KiCad CLI) | Hidden by missing wiring | **2 errors, 1 warning** |
| Independent KiCad CLI PCB DRC (properly installed/configured) | Not meaningful on dropped connectivity | **Passes (0 KiCad DRC errors)** |
| Fabrication authorized | **No** | **No — no independent KiCad ERC approval for this compiled netlist** |

**Checker disagreement matters:** When KiCad CLI is unavailable, HS's fallback geometry checker flags crossings between `Net-2` and `Net-11` on F.Cu, and `Net-2` and `Net-1` on B.Cu. Once actual KiCad 9.0.8 is installed, its PCB DRC reports **0 errors** on the compiled layout, although the compilation remains `fabrication_ready=false` and `fab_recommendation=blocked_erc`. We must NOT describe those fallback crossing warnings as independently proven physical shorts. This is **two verification methods disagreeing**; any manufacturing conclusion requires real KiCad DRC/ERC evidence, source verification and a review of routing. The previous fixture's clean result with fake pin identities was still misleading.

On both tested configurations `build_graph_compiled=true`, `wire_count=26` and `fabrication_ready=false`. No router redesign was implemented here.

## Source-bound measurement ingestion

New `src/hardware_splicer/repair_electrical_evidence.py` consumes an exported KiCad netlist **and** CSV with explicit operator/instrument/probe metadata. It checks:

- exact `component_ref` and pin membership against exported source connectivity; rejects unknown pins/components and pins assigned to multiple nets,
- supported units `dc_voltage/V`, `resistance/ohm`, `continuity/boolean`,
- numerical finiteness, nonnegative resistance and Boolean continuity, unique observation IDs, timezone-aware timestamps and required declared instrument/operator/condition,
- bounded source and CSV sizes and number of rows,
- different reported observations **at the same physical pin with the same named instrument** under different conditions, calculating *only* the numerical delta and never inferring failure of a part.

The source and CSV SHA-256 hashes are recorded. **Named operator and instrument IDs are user claims, not authenticated provenance**. Shared power or ground net membership must never be automatically interpreted as a functional failure path.

### Working software demonstration (entirely synthetic readings)

Example CSV: `examples/repair_electrical_evidence/SYNTHETIC_ONLY_measurements.csv`. The words **SYNTHETIC** are deliberate: no one measured these readings. The actual CLI output was:

- matched `J1.1` twice to source `VBUS`, `U3.1` to source `GND`,
- total 3 claims and one **synthetic** condition comparison with delta **-0.3 V**,
- `physical_repair_verified=false`, `failed_component_identified=false`, `power_on_authorized=false`, `instrument_authenticated=false`.

```bash
pip install -e '.[dev]'
python -m hardware_splicer.repair_electrical_evidence \
  --netlist examples/main_ctrl_esp32_servo.net \
  --csv examples/repair_electrical_evidence/SYNTHETIC_ONLY_measurements.csv \
  --out /tmp/hs_evidence_demo
```

Outputs `REPAIR_ELECTRICAL_EVIDENCE.json` and `REPAIR_ELECTRICAL_EVIDENCE.md`.

### Integrated repair-triage path

The actual existing `repair_triage_cli.py` supports optional `--netlist` and `--measurements-csv` together:

```bash
python -m hardware_splicer.repair_triage_cli \
  example_repair_intake.json ./repair_report \
  --netlist examples/main_ctrl_esp32_servo.net \
  --measurements-csv examples/repair_electrical_evidence/SYNTHETIC_ONLY_measurements.csv
```

One run produces original `REPAIR_TRIAGE.json`, `REPAIR_TRIAGE.md` **plus** the two electrical evidence artifacts. The reports stay separate: **measurements never become verified fault labels or automatic high-confidence diagnoses**. Missing one of the two source inputs aborts rather than silently degrading.

## Getting a real electrical source file

KiCad's documented CLI supports netlist export from a genuine owned schematic:

```bash
kicad-cli sch export netlist \
  --format kicadsexpr \
  --output device.net device.kicad_sch
```

Official KiCad command reference: https://docs.kicad.org/master/en/cli/cli.html .

**A second, genuinely independent KiCad test was executed.** I installed KiCad CLI **9.0.8** in an isolated sandbox and invoked its actual netlist exporter on the unchanged checked-in `hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch`. The KiCad-produced `/tmp/hs-spi-flash-kicad.net` contained **36 schematic components, 19 named nets and 79 REF.PIN memberships**, all mapped by the corrected HS importer with no unknown component references.

HS also ingested **two deliberately synthetic** measurement rows on `C2.1` of KiCad net `/1V8` (1.8 V and 1.6 V), producing an arithmetic **-0.2 V** delta and explicitly **no physical measurement authentication or fault diagnosis**.

After installing and configuring the official KiCad schematic-symbol and footprint library tables, the KiCad **schematic ERC reported 0 violations on the original SPI-flash schematic**. An initial ERC run without these library assets reported 74 environment-related warnings, so this result requires a properly provisioned KiCad installation. ERC on this **SPI-flash schematic** does not certify the **separate ESP32/servo netlist's PCB routing**, nor physical manufacturability.

This direct official KiCad export is materially stronger interoperability evidence than our previous experimental KiCad-to-Circuit-JSON converter run, which kept components but lost all HS-imported nets. The alternate converter's original component count (40) also differs from KiCad's (36); we have **not** reconciled that external converter's extra records, and make no claim its output has reached parity. The source schematic is a real maintained HS repository design, not an independent vendor-supplied schematic.

## Acceptance and remaining work

**91 focused regression tests initially passed** on the fixture with the fallback verification path. The subsequent optional KiCad 9.0.8 source-export integration added its own pass, and the full focused suite is rerun with both verification methods. The KiCad compiler fixture assertions now distinguish between fallback geometry warnings and independently installed KiCad DRC results, **requiring fabrication to remain blocked until valid KiCad ERC evidence is available**; they do not falsely claim either algorithm's error count is a physical measurement.

Future engineering requirements:

1. Reconcile fallback geometry warnings against actual KiCad PCB DRC and schematic ERC; do not manufacture based on either preview alone.
2. Repeat the successful KiCad CLI export with a **third-party authorized schematic**, and independently compare its netlist `REF.PIN` counts. Reconcile the alternate Circuit JSON converter's differing component counts and lost connectivity.
3. Connect authenticated instrument captures or independent professional measurement reviews, rather than treating operator CSV values as self-proving measurements.
4. Only when the physical path and context have independently corroborated evidence, propose diagnostically discriminating measurements and score them against prospective repair outcomes.
5. Run the same artifacts in a genuine competing tool; no competitor was executed in this PR.

**Bottom line:** Source connectivity preservation and transparent measurement attribution are material repair/manufacturing prerequisites; they are not themselves evidence that HS has repaired a device or beaten an EDA competitor.
