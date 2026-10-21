# SPI flash adapter: end-to-end prebuild acceptance

The canonical reference device is **already designed**, with a routed KiCad 9
schematic/PCB, reviewed component identities and a historical native KiCad
receipt in `hardware/reference_designs/spi_flash_adapter_v1/`.

This independent cross-layer check is **not a new PCB design** and does not
claim to re-run native ERC/DRC, measure a real flash chip, certify a source
PDF or produce fabrication authorization.

## One command

```bash
python scripts/audit_spi_reference.py --out /tmp/hs-spi-audit
```

Creates:

- `REFERENCE_HANDOFF_AUDIT.json` — nine SHA-256 receipt bindings,
  source-to-BOM footprint and manufacturer-part parity, open gates,
  quantities and source-specific first-use constraints
- `REFERENCE_ASSEMBLY_PICKLIST.csv` — actual source-BOM components with
  FIT/DNP flags (not automatically priced or verified in stock)
- `REFERENCE_ASSEMBLY_PLAN.json` — original KiCad-based view of component,
  test-pad and mounting-hole features
- `REFERENCE_DEVICE_DOSSIER.json` — source-bound geometry unknowns and,
  optionally, a preliminary enclosure-envelope screen
- `REFERENCE_PREBUILD_REVIEW.md` — compact human engineering-review checklist

### Assembly population is **not** 38 purchased parts

The reference board has **40 footprints**. They comprise 18 electrical BOM
positions, 18 exposed PCB test pads and four mounting holes. Two BOM resistors
(`R1`, `R4`) are deliberately DNP at first assembly, leaving **16 initially
fitted physical component positions**. `JP1` is a fitted two-pin header,
but its **enable shunt is absent**.

The generic `assembly_plan` counts 38 non-DNP footprints because exposed
test pads and mounting features are also present in the PCB drawing. The
audit intentionally does not treat those footprints as orderable components
or as instructions to solder the copper pads. Mounting hardware is *not*
included in the electrical BOM.

### What is evidence-backed

The audit only reports a clean **historical source-receipt** when:

1. Every frozen verification input file still matches its recorded SHA-256.
2. The historical receipt passes all declared checks and retains its
   physical-authority prohibitions.
3. All physically installed board positions reconcile with the canonical
   manufacturer/part/footprint BOM, DNP controls and input connector pinout.
4. The required 1.8 V target, translator and regulator orderable identities
   appear in the source BOM.

This is not independent authentication of the manufacturer PDFs. The
receipt could have been produced earlier, with different environment or tool
versions; a clean hash proves *source consistency*, not the historical
test-run's validity beyond its receipt.

### Native artifacts and physical work

To create **actual** review/fabrication CAM artifacts from the frozen
reference, use the reference directory's existing `build_package.py`,
which invokes `verify_design.py` and KiCad 9 before exporting Gerbers,
NC drill, placement CSV, assembly drawings and their own hashes.
To prepare a remote functional-test service campaign, use the existing
`build_remote_fct_campaign.py`.

Neither program is replaced by the new audit. The new report identifies
what is ready for an independent review and what evidence must be completed:

- independent electrical and PCB layout sign-off
- vendor/assembly constraints and exact source package/part identity
- populated board shorts, resistance and continuity checks
- explicitly authorized, current-limited rail and timing measurements
- read-only JEDEC-ID SPI transaction plus captured waveforms

No generic or reference-design output authorizes board manufacture, power,
firmware flashing, or a product release on its own.
